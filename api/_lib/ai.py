"""
AI 연동 모듈 (provider-agnostic).

설계상 중요한 원칙 세 가지:

1) **키는 절대 코드에 넣지 않는다.**
   os.environ 으로만 읽는다. Vercel 대시보드에서 환경변수로 등록하면
   코드·로그·브라우저 어디에도 키가 노출되지 않는다.

2) **AI 호출이 실패해도 서비스는 죽지 않는다.**
   recommend() 는 실패하면 None 을 돌려주고, 호출한 쪽은
   '코드 점수만으로 계산한 결과 + AI unavailable 안내' 로 대체한다.
   이게 과제 제약사항의 '실패 상황 고려' 를 충족한다.

3) **provider 는 환경변수 하나로 갈아끼운다.**
   AI_PROVIDER 에 'gemini' 또는 'openai' 를 넣으면 되고,
   어느 쪽이든 recommend() 를 호출하는 코드(api/recommend.py)는
   provider 를 전혀 모른다. SDK 를 쓰지 않고 urllib + 표준 라이브러리만 쓴다.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


# ---------------------------------------------------------------------------
# provider 레지스트리
#
# 새 provider 를 붙일 때는 여기에 항목 하나만 추가하면 된다.
# 그 provider 는 recommend() 안에서 쓰지 않으므로 스위칭 비용이 0이다.
# ---------------------------------------------------------------------------
PROVIDERS = {
    "gemini": {
        "label": "Google Gemini",
        "key_env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
        # 신규 프로젝트는 3.5 Flash-Lite 또는 3.8 Flash 를 쓰라고 공식 안내하고 있다
        # (2.5 계열은 신규 접근 제한). 실제로 3.8 Flash 는 혼잡할 때 503 을 던져
        # 재시도 없이는 간헐적으로 폴백으로 내려가므로, 기본값은 더 가벼운
        # 3.5 Flash-Lite 로 잡고 3.8 은 GEMINI_MODEL 로 선택할 수 있게 남긴다.
        "default_model": "gemini-3.5-flash-lite",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        # Gemini 는 키를 쿼리스트링(?key=)으로 받는다.
        "auth": "query",
    },
    "openai": {
        "label": "OpenAI",
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-4o-mini",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "auth": "bearer",
    },
}

DEFAULT_PROVIDER = "gemini"
TIMEOUT = 25  # 초. 너무 길게 잡으면 Vercel 함수 타임아웃에 걸린다.

# 일시적 장애용 재시도. 이 값들을 안 고치면 provider 서버가 혼잡할 때마다
# 그 순간 그냥 폴백으로 내려가 버린다(사용자 입장에서는 'AI가 가끔 안 된다').
RETRY_STATUS = (429, 500, 502, 503, 504)
RETRY_DELAYS = (0.8, 1.8)  # 초. 짧게 두 번만 시도해서 총 지연은 2.6초 이내.


def active_provider_name():
    """현재 사용할 provider 이름. 모르는 값이면 기본값으로 떨어진다."""
    name = os.environ.get("AI_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    return name if name in PROVIDERS else DEFAULT_PROVIDER


def get_api_key():
    """환경변수에서 API 키를 읽는다. 없으면 빈 문자열."""
    spec = PROVIDERS[active_provider_name()]
    return os.environ.get(spec["key_env"], "").strip()


def get_model():
    """현재 provider 에서 쓸 모델명."""
    spec = PROVIDERS[active_provider_name()]
    return os.environ.get(spec["model_env"], "").strip() or spec["default_model"]


def describe():
    """로그·응답에 붙일 provider 정보. 키 자체는 절대 포함하지 않는다."""
    name = active_provider_name()
    spec = PROVIDERS[name]
    return {
        "provider": name,
        "label": spec["label"],
        "model": get_model(),
        "configured": bool(get_api_key()),
    }


def is_available():
    """키가 설정되어 있는지 여부. 화면에서 'AI 꺼짐' 배지를 표시할 때 쓴다."""
    return bool(get_api_key())


def build_prompt(profile, candidates):
    """LLM에 보낼 프롬프트를 만든다.

    토큰 절약을 위해 후보 공고는 미리 잘라서(설명 600자, 상위 8건) 넣는다.
    """
    lines = []
    for index, item in enumerate(candidates, start=1):
        job = item["job"]
        salary = "{}~{}".format(job["salary_min"], job["salary_max"]) \
            if job.get("salary_max") else "정보없음"

        lines.append(
            "[{index}] 제목: {title}\n"
            "    회사: {company} ({source})\n"
            "    지역: {location} | 근무형태: {job_type} | 금여: {salary}\n"
            "    태그: {tags}\n"
            "    설명: {description}\n"
            "    코드 기준 사전 점수: {score}점 / 근거: {reasons}\n".format(
                index=index,
                title=job["title"],
                company=job["company"],
                source=job["source"],
                location=job["location"],
                job_type=job.get("job_type") or "미지정",
                salary=salary,
                tags=", ".join(job["tags"]) or "없음",
                description=(job.get("description") or "")[:600],
                score=item["score"],
                reasons="; ".join(item["reasons"]) or "사전 매칭 근거 없음",
            )
        )

    prompt = """너는 원격 구직 매칭 경력자다. 아래는 구직자의 조건과 후보 공고 목록이다.

[구직자 조건]
- 직무: {role}
- 기술스택: {skills}
- 경력 수준: {level}
- 최소 희망 금여: {min_salary}

[후보 공고]
{job_list}

[출력 규칙]
1. 아래 JSON 배열만 출력하라. 설명문이나 마크다운 코드블록(```)으로 감싸지 마라.
2. 각 공고마다 match_score(0~100), reasons(배열, 3개 이내), concern(부족한 점 한 줄 또는 빈 문자열), action(구직자가 다음에 할 행동 한 줄) 을 넣는다.
3. reasons 는 반드시 해당 공고의 제목/태그/설명에 실제로 있는 내용만 근거로 삼아라. 없는 정보를 지어내지 마라.
4. JSON 형태 예시: [{{"id": "remoteok:123", "match_score": 85, "reasons": ["이유1", "이유2", "이유3"], "concern": "없음", "action": "행동"}}]
   - id 값은 반드시 후보 공고에 적힌 id 를 그대로 복사하라.
5. 순위는 코드 사전 점수가 높은 순서를 따르되, 구직자 조건과의 실질적 부합도로 소폭 조정할 수 있다.
6. 후보 개수만큼만 출력하라.
""".format(
        role=profile.get("role") or "미지정",
        skills=profile.get("skills") or "미지정",
        level=profile.get("level") or "미지정",
        min_salary=profile.get("min_salary") or "미지정",
        job_list="\n".join(lines),
    )

    return prompt


SYSTEM_PROMPT = "당신은 공고 평가 보조 AI입니다. 반드시 유효한 JSON만 출력합니다."


def recommend(profile, candidates):
    """AI에게 추천 근거를 요청한다.

    Returns:
        dict: {job_id: {...판정...}} 형태의 매핑
        None : AI를 쓸 수 없거나 호출이 실패한 경우
    """
    key = get_api_key()
    if not key or not candidates:
        return None

    prompt = build_prompt(profile, candidates)

    try:
        if active_provider_name() == "openai":
            text = _call_openai(key, prompt)
        else:
            text = _call_gemini(key, prompt)
    except urllib.error.HTTPError as error:
        # 상태 코드만으론 원인을 알 수 없다 (키 오류인지 모델명 오류인지 구분 안 됨).
        # 응답 본문에는 provider 가 알려준 정확한 사유가 들어 있으므로 로그에 남긴다.
        # 단, 본문에 키가 되비쳐 나올 수 있어 마스킹한 뒤에 남긴다.
        print("[ai] {} HTTPError {} {}".format(
            active_provider_name(),
            error.code,
            _read_error_body(error, key),
        ))
        return None
    except urllib.error.URLError as error:
        print("[ai] URLError {}".format(getattr(error, "reason", error)))
        return None
    except (KeyError, IndexError, ValueError, TypeError) as error:
        print("[ai] parse error {}".format(error))
        return None
    except Exception as error:
        print("[ai] unexpected error {}".format(error))
        return None

    return _parse_ai_json(text)


# ---------------------------------------------------------------------------
# provider 별 실제 HTTP 호출부
# ---------------------------------------------------------------------------


def _call_gemini(key, prompt):
    """Google Gemini generateContent 호출 → 텍스트 조각."""
    spec = PROVIDERS["gemini"]
    model = get_model()
    url = spec["endpoint"].format(model=model)
    url = "{}?key={}".format(url, urllib.parse.quote(key, safe=""))

    body = json.dumps({
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,   # 일관된 판정을 위해 낮은 값
            "maxOutputTokens": 1600,  # 비용 상한
            # JSON만 나오도록 지정. 그래도 아래 파서가 안전망을 한 겹 더 둔다.
            "responseMimeType": "application/json",
        },
    }).encode("utf-8")

    payload = _post_json(url, body, {})
    candidates = payload["candidates"]
    parts = candidates[0]["content"]["parts"]
    return "".join(part.get("text", "") for part in parts)


def _call_openai(key, prompt):
    """OpenAI Chat Completions 호출 → 텍스트."""
    body = json.dumps({
        "model": get_model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1600,
    }).encode("utf-8")

    payload = _post_json(
        "https://api.openai.com/v1/chat/completions",
        body,
        {"Authorization": "Bearer {}".format(key)},
    )
    return payload["choices"][0]["message"]["content"]


def _post_json(url, body, headers):
    """공통 POST 헬퍼. 일시적 오류에는 짧게 재시도한다.

    Authorization 헤더가 필요 없는 provider 는 빈 dict 를 넘긴다.
    재시도해도 실패하면 마지막 예외를 그대로 올려서 호출부가 처리한다.
    """
    last_error = None

    for attempt in range(len(RETRY_DELAYS) + 1):
        request = urllib.request.Request(
            url,
            data=body,
            headers=dict({"Content-Type": "application/json"}, **headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            last_error = error
            # 재시도해도 같은 답이 나오는 오류(인증 실패, 잘못된 요청 등)는
            # 기다릴 이유가 없으므로 곧장 올려서 원인을 드러낸다.
            if error.code not in RETRY_STATUS:
                raise
            if attempt >= len(RETRY_DELAYS):
                raise
            print("[ai] retry on HTTP {} (attempt {}/{})".format(
                error.code, attempt + 2, len(RETRY_DELAYS) + 1))
            time.sleep(RETRY_DELAYS[attempt])

    raise last_error


def _read_error_body(error, key, limit=300):
    """에러 응답 본문에서 사람이 읽을 수 있는 사유만 뽑아낸다.

    provider 를 바꿀 때 실제로 자주 나는 원인들:
      - 400 INVALID_ARGUMENT : 모델명이 틀렸거나 지원하지 않는 파라미터를 보냄
      - 401 UNAUTHENTICATED : 키가 잘렸거나 공백이 섞였거나 폐기됨
      - 403 PERMISSION_DENIED: API가 꺼져 있거나 할당량 초과
      - 429 RESOURCE_EXHAUSTED: 요청이 너무 빠름
    키는 로그에 새지 않도록 반드시 치환한다.
    """
    try:
        raw = error.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - 본문을 못 읽어도 로깅은 계속돼야 한다
        return "(본문 읽기 실패)"

    detail = ""
    try:
        payload = json.loads(raw)
        # Gemini: {"error": {"message": "...", "status": "..."}}
        # OpenAI: {"error": {"message": "..."}} 또는 {"message": "..."}
        node = payload.get("error", payload)
        if isinstance(node, dict):
            detail = node.get("message", "")
            status = node.get("status", "")
            if status:
                detail = "{} / {}".format(status, detail)
        else:
            detail = str(node)
    except (json.JSONDecodeError, AttributeError):
        detail = raw

    detail = " ".join(str(detail).split())[:limit]
    return detail.replace(key, "***") if key else detail


def _parse_ai_json(content):
    """AI가 준 텍스트에서 JSON 배열을 안전하게 뽑아낸다.

    모델이 종종 마크다운 코드블록(```json ... ```)으로 감싸거나
    앞뒤에 잡담을 붙인다. 그래서 가장 먼저 '[' 와 마지막 ']' 사이만 잘라낸다.
    """
    if not content:
        return None

    text = content.strip()

    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        print("[ai] no JSON array in response")
        return None

    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError as error:
        print("[ai] JSONDecodeError {}".format(error))
        return None

    if not isinstance(parsed, list):
        return None

    result = {}
    for item in parsed:
        if isinstance(item, dict) and item.get("id"):
            result[item["id"]] = item
    return result or None