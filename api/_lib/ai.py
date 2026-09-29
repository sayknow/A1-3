"""
AI 연동 모듈 (OpenAI Chat Completions).

설계상 중요한 원칙 두 가지:

1) **키는 절대 코드에 넣지 않는다.**
   os.environ 으로만 읽는다. Vercel 대시보드에서 환경변수로 등록하면
   코드·로그·브라우저 어디에도 키가 노출되지 않는다.

2) **AI 호출이 실패해도 서비스는 죽지 않는다.**
   recommend() 는 실패하면 None 을 돌려주고, 호출한 쪽은
   '코드 점수만으로 계산한 결과 + AI unavailable 안내' 로 대체한다.
   이게 과제 제약사항의 '실패 상황 고려' 를 충족한다.
"""

import json
import os
import urllib.error
import urllib.request


# 모델명은 환경변수로 갈아끼울 수 있게 해 둔다.
DEFAULT_MODEL = "gpt-4o-mini"
API_URL = "https://api.openai.com/v1/chat/completions"
TIMEOUT = 25  # 초. 너무 길게 잡으면 Vercel 함수 타임아웃에 걸린다.


def get_api_key():
    """환경변수에서 API 키를 읽는다. 없으면 빈 문자열."""
    return os.environ.get("OPENAI_API_KEY", "").strip()


def is_available():
    """키가 설정되어 있는지 여부. 화면에서 'AI 꺼짐' 배지를 표시할 때 쓴다."""
    return bool(get_api_key())


def build_prompt(profile, candidates):
    """OpenAI에 보낼 프롬프트를 만든다.

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

    prompt = """너는 원격 구직匹配的 경력자다. 아래는 구직자의 조건과 후보 공고 목록이다.

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

    messages = [
        {
            "role": "system",
            "content": "당신은 공고 평가 보조 AI입니다. 반드시 유효한 JSON만 출력합니다.",
        },
        {"role": "user", "content": prompt},
    ]

    body = json.dumps({
        "model": os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
        "messages": messages,
        "temperature": 0.2,   # 일관된 판정을 위해 낮은 값
        "max_tokens": 1600,  # 비용 상한
    }).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": "Bearer {}".format(key),
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))

        content = payload["choices"][0]["message"]["content"]
        return _parse_ai_json(content)

    except urllib.error.HTTPError as error:
        # 429(쿼터 초과), 401(키 오류) 등은 사용자에게 그대로 노출하면
        # 내부 구현이 드러나므로, 상태 코드만 로그에 남긴다.
        print("[ai] HTTPError {}".format(error.code))
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
