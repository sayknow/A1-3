"""
POST /api/recommend — AI 맞춤 추천 엔드포인트.

처리 순서 (이 순서가 비용과 속도를 결정한다):
    1) 입력 검증        → 잘못된 입력을 여기서 걸러낸다
    2) 공고 수집/캐시    → 없으면 503
    3) 코드 사전 필터    → 후보를 상위 8건으로 줄인다 (비용 절감)
    4) AI 판정           → 실패하면 None, 그럼 3단계 결과로 대체
    5) 응답 조립         → 결과 + 사용된 방식(ai / fallback) 을 함께 반환

요청 예시:
    POST /api/recommend
    {"role": "백엔드", "skills": "python, aws, docker", "level": "mid", "min_salary": 50000, "top_n": 5}
"""

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler

# _lib 패키지는 이 파일과 같은 폴더(api/)에 있으므로 그 폴더를 넣는다.
API_DIR = os.path.dirname(os.path.abspath(__file__))
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from _lib import ai  # noqa: E402
from _lib.aggregate import get_jobs  # noqa: E402
from _lib.matching import prefilter  # noqa: E402

# AI에 넘길 후보 수. 너무 많으면 비용·지아가 함께 늘어난다.
AI_CANDIDATE_LIMIT = 8
MAX_TOP_N = 10


def _run(request):
    """요청을 받아 추천 결과를 JSON 으로 돌려주는 실제 로직.

    Vercel 진입점과 분리해 두어 로컬 개발 서버에서 그대로 재사용한다.
    """
    started = time.time()

    # ------------------------------------------------------------------
    # 1) 입력 검증  (실패 처리 1: 빈 입력 / 잘못된 입력)
    # ------------------------------------------------------------------
    if request.method != "POST":
        return _json({"error": "POST 방식만 지원합니다."}, 405)

    try:
        body = json.loads(request.body or "{}")
    except (json.JSONDecodeError, TypeError):
        return _json({"error": "요청 본문을 읽을 수 없습니다."}, 400)

    if not isinstance(body, dict):
        return _json({"error": "요청 형식이 올바르지 않습니다."}, 400)

    profile = {
        "role": _clean_text(body.get("role"), 40),
        "skills": _clean_text(body.get("skills"), 200),
        "level": _clean_text(body.get("level"), 20),
        "min_salary": _clean_int(body.get("min_salary")),
        "summary": _clean_text(body.get("summary"), 600),  # 자유 서술(선택)
    }

    # 필수값 검사: 아무 조건도 없으면 추천의 의미가 없다.
    if not profile["role"] and not profile["skills"] and not profile["summary"]:
        return _json(
            {"error": "최소 한 가지 이상 입력해 주세요. 직무 또는 기술스택을 입력하는 것을 권장합니다."},
            400,
        )

    try:
        top_n = int(body.get("top_n", 5))
    except (TypeError, ValueError):
        top_n = 5
    top_n = max(1, min(top_n, MAX_TOP_N))

    # ------------------------------------------------------------------
    # 2) 공고 확보  (실패 처리 2: 원천 서버 장애)
    # ------------------------------------------------------------------
    try:
        jobs = get_jobs(limit_per_source=60)
    except Exception as error:
        print("[api/recommend] collect failed {}".format(error))
        return _json({"error": "공고 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."}, 503)

    if not jobs:
        return _json(
            {"error": "지금은 원천 서버에서 공고를 가져오지 못해 추천할 수 없습니다. 잠시 후 다시 시도해 주세요."},
            503,
        )

    # ------------------------------------------------------------------
    # 3) 코드 사전 필터 (비용 절감)
    # ------------------------------------------------------------------
    candidates = prefilter(jobs, profile, limit=AI_CANDIDATE_LIMIT)

    # 실패 처리 3: 조건이 너무 구체적이어서 후보가 0건
    if not candidates:
        return _json(
            {
                "error": "입력한 조건과 일치하는 공고를 찾지 못했습니다. 기술스택을 더 일반적인 단어로 적어 보세요.",
                "results": [],
                "total_jobs": len(jobs),
            },
            404,
        )

    # ------------------------------------------------------------------
    # 4) AI 판정 (실패 처리 4: AI 없음 / 호출 실패 / 응답 파싱 실패)
    # ------------------------------------------------------------------
    ai_verdicts = None
    ai_status = "disabled"
    ai_error = None

    if ai.is_available():
        ai_verdicts = ai.recommend(profile, candidates)
        if ai_verdicts is None:
            ai_status = "failed"
            ai_error = "AI 분석에 실패해 코드 기준 점수만 보여 드립니다."
        else:
            ai_status = "ok"

    # ------------------------------------------------------------------
    # 5) 결과 조립
    # ------------------------------------------------------------------
    results = []
    for item in candidates[:top_n]:
        job = item["job"]
        verdict = (ai_verdicts or {}).get(job["id"], {})

        # 최종 점수: AI가 점수를 줬으면 그 값을, 아니면 코드 점수를 쓴다.
        final_score = verdict.get("match_score")
        if not isinstance(final_score, (int, float)):
            final_score = item["score"]

        results.append({
            "job": job,
            "code_score": item["score"],
            "match_score": max(0, min(100, int(final_score))),
            "reasons": verdict.get("reasons") or item["reasons"],
            "concern": verdict.get("concern") or "",
            "action": verdict.get("action") or "",
            "ai_used": bool(verdict),
        })

    results.sort(key=lambda item: item["match_score"], reverse=True)

    return _json(
        {
            "results": results,
            "ai_status": ai_status,
            "ai_message": ai_error,
            # 어떤 provider 가, 어떤 모델로 판정했는지 투명하게 알린다.
            # 키 값은 담기지 않는다(describe()가 키를 노출하지 않는다).
            "ai_provider": ai.describe(),
            "profile": profile,
            "total_jobs": len(jobs),
            "candidate_count": len(candidates),
            "elapsed_ms": int((time.time() - started) * 1000),
        },
        200,
    )


def _clean_text(value, max_length):
    """문자열로 정리하고 길이를 제한한다. None/비문자열은 빈 문자열."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()[:max_length]


def _clean_int(value):
    """정수로 정리한다. 실패하면 None (없다는 뜻)."""
    if value in (None, "", "0"):
        return None
    try:
        number = int(float(value))
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _json(payload, status):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store",
        },
        "body": body.decode("utf-8"),
    }


# ==========================================================================
# Vercel 진입점 (api/recommend.py)
# handler 는 BaseHTTPRequestHandler 서브클래스여야 한다.
# ==========================================================================


class _Request:
    """BaseHTTPRequestHandler 를 _run() 이 기대하는 형태로 바꿔주는 어댑터."""

    def __init__(self, raw):
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(raw.path)
        self.args = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        length = int(raw.headers.get("Content-Length", 0) or 0)
        self.body = raw.rfile.read(length).decode("utf-8") if length else "{}"
        self.method = raw.command


class handler(BaseHTTPRequestHandler):  # noqa: N801 (Vercel 이 요구하는 이름)
    """POST /api/recommend — AI 맞춤 추천."""

    protocol_version = "HTTP/1.1"

    def do_POST(self):  # noqa: N802 (BaseHTTPRequestHandler 규약)
        try:
            result = _run(_Request(self))
        except Exception as error:  # 마지막 방어선
            print("[api/recommend] fatal {}".format(error))
            result = _json(
                {"error": "서버에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."},
                500,
            )

        body = result["body"].encode("utf-8")
        self.send_response(result["statusCode"])
        for key, value in result["headers"].items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        """GET 요청에는 405 를 돌려준다 (POST 전용 엔드포인트임을 알림)."""
        result = _json({"error": "POST 방식만 지원합니다."}, 405)
        body = result["body"].encode("utf-8")
        self.send_response(405)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print("[api/recommend] " + format % args)
