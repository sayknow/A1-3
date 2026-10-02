"""
GET /api/jobs — 공고 목록 엔드포인트.

역할:
- 3개 외부 API에서 공고를 모아 정규화해 내려준다.
- 캐시를 사용하므로 빠르게 응답한다.
- '어디서 온 데이터인가, 언제 수집했는가'를 함께 알려준다.
  (데이터 출처를 숨기지 않는 것이 이 서비스의 신뢰도 원칙)

요청 예시:
    GET /api/jobs?limit=40&refresh=1
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

# Vercel 은 이 파일을 /var/task/api/jobs.py 로 복사해 실행한다.
# _lib 패키지는 이 파일과 같은 폴더(api/)에 있으므로, 그 폴더를
# sys.path 에 넣어야 `from _lib import ...` 가 된다.
# (프로젝트 루트를 넣으면 _lib 을 못 찾는다 — 실제로 500이 났던 원인)
API_DIR = os.path.dirname(os.path.abspath(__file__))
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from _lib import cache  # noqa: E402
from _lib.aggregate import describe_sources, get_jobs  # noqa: E402


def _now_iso():
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(request):
    """요청을 받아 JSON 응답을 돌려주는 실제 로직.

    Vercel 이 요구하는 진입점(_http.Handler 클래스)과 분리해 두었다.
    덕분에 이 로직은 로컬 개발 서버에서 request 객체만 만들어 주면
    그대로 재사용할 수 있다.
    """
    started = time.time()

    # --- 입력 검증 (실패 처리 1: 잘못된 요청) ---
    try:
        limit = int(request.args.get("limit", 60))
    except (TypeError, ValueError):
        return _json({"error": "limit 값이 올바르지 않습니다."}, 400)

    if limit < 1 or limit > 200:
        return _json({"error": "limit 은 1 이상 200 이하이어야 합니다."}, 400)

    refresh = request.args.get("refresh") == "1"

    # --- 수집 (이 모듈 내부에서 예외를 삼키므로 여기서는 보통 예외가 없다) ---
    try:
        jobs = get_jobs(limit_per_source=60, force_refresh=refresh)
    except Exception as error:  # 마지막 방어선
        print("[api/jobs] unexpected {}".format(error))
        return _json(
            {"error": "공고 데이터를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요."},
            503,
        )

    # --- 실패 처리 2: 공고가 0건 (외부 API가 모두 실패했을 가능성) ---
    if not jobs:
        return _json(
            {
                "error": "지금은 원천 서버에서 공고를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.",
                "jobs": [],
                "total": 0,
                "sources": {},
                "collected_at": _now_iso(),
                "stale": True,
            },
            503,
        )

    sources = describe_sources(jobs)
    cache_age = cache.age("all_jobs")

    return _json(
        {
            "jobs": jobs[:limit],
            "total": len(jobs),
            "sources": sources,
            "source_note": "공고 데이터는 아래 출처 API 서버에서 실시간 수집한 것입니다.",
            "collected_at": _now_iso(),
            "cache_age_seconds": cache_age,
            "stale": False,
            "elapsed_ms": int((time.time() - started) * 1000),
        },
        200,
    )


def _json(payload, status):
    """JSON 응답을 만든다. (로컬 개발 서버에서 재사용)"""
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
# Vercel 진입점
#
# Vercel 의 파이썬 런타임은 api/ 아래의 .py 파일마다 함수를 만들되,
# 그 파일 안에 아래 이름 중 하나가 반드시 있어야 한다.
#     app / application / handler(BaseHTTPRequestHandler 서브클래스)
# 이 중 handler 서브클래스 방식을 쓴다.
#
# 주의: 여기서 예외가 밖으로 나가면 Vercel 이 500 을 뱉는다.
# 그래서 어떤 경우에도 JSON 응답을 만들어 내려간다. (과제: 실패 처리)
# ==========================================================================


class _Request:
    """BaseHTTPRequestHandler 를 _run() 이 기대하는 형태로 바꿔주는 어댑터."""

    def __init__(self, raw):
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(raw.path)
        self.args = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self.body = None
        self.method = raw.command


class handler(BaseHTTPRequestHandler):  # noqa: N801 (Vercel 이 요구하는 이름)
    """GET /api/jobs — 공고 목록."""

    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler 규약)
        try:
            result = _run(_Request(self))
        except Exception as error:  # 마지막 방어선: 서버가 죽지 않게
            print("[api/jobs] fatal {}".format(error))
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

    def log_message(self, format, *args):
        """접근 로그를 Vercel 로그로 남긴다."""
        print("[api/jobs] " + format % args)
