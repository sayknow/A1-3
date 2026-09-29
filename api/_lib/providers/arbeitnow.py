"""
Arbeitnow 프로바이더.

- 출처: https://www.arbeitnow.com/api/job-board-api
- 인증: API 키 불필요 (공개 엔드포인트)
- 응답 형태: {"data": [ ... ], "links": ..., "meta": ...}
- 특이사항: 게시 시각이 Unix 타임스탬프(정수)로 온다. ISO 문자열로 바꿔야
            다른 프로바이더와 정렬 순서를 맞출 수 있다.
            급여 정보는 아예 없다.
"""

import json
import urllib.request
from datetime import datetime, timezone

from _lib.normalize import build_job, to_int

API_URL = "https://www.arbeitnow.com/api/job-board-api"
SOURCE = "Arbeitnow"
TIMEOUT = 10


def _timestamp_to_iso(epoch):
    """Unix 타임스탬프를 '2026-09-26T16:00:26Z' 형태의 문자열로 변환한다."""
    seconds = to_int(epoch)
    if seconds <= 0:
        return ""
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (OverflowError, OSError, ValueError):
        return ""


def fetch(limit=60):
    """Arbeitnow 공고를 가져와 공통 형태로 변환한다. 실패 시 빈 리스트."""
    try:
        request = urllib.request.Request(
            API_URL,
            headers={"User-Agent": "JobFit/1.0 (educational project)"},
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))

        jobs = []
        for raw in payload.get("data", [])[:limit]:
            if not isinstance(raw, dict) or not raw.get("title"):
                continue

            is_remote = bool(raw.get("remote"))
            location = raw.get("location") or ("Remote" if is_remote else "On-site")

            job_types = raw.get("job_types") or []

            jobs.append(
                build_job(
                    job_id="arbeitnow:{}".format(raw.get("slug")),
                    source=SOURCE,
                    title=raw.get("title"),
                    company=raw.get("company_name"),
                    location=location,
                    apply_url=raw.get("url", ""),
                    description=raw.get("description", ""),
                    tags=raw.get("tags"),
                    job_type=job_types[0] if job_types else "",
                    posted_at=_timestamp_to_iso(raw.get("created_at")),
                )
            )
        return jobs
    except Exception:
        print("[arbeitnow] failed to fetch")
        return []
