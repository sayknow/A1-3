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

# Vercel 이 실행 디렉터리를 다르게 잡는 경우가 있어, 프로젝트 루트를
# sys.path 에 직접 넣어 `from _lib...` 임포트가 항상 되게 한다.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from _lib import cache  # noqa: E402
from _lib.aggregate import describe_sources, get_jobs  # noqa: E402


def _now_iso():
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def handler(request):
    """Vercel Serverless Function 진입점."""
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
    """JSON 응답을 만든다. Vercel 의 Node 런타임과 파이썬 런타임 모두에 맞춘 형태."""
    import base64

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store",
        },
        "body": base64.b64encode(body).decode("ascii"),
        "encoding": "base64",
    }
