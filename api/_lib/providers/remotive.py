"""
Remotive 프로바이더.

- 출처: https://remotive.com/api/remote-jobs
- 인증: API 키 불필요 (공개 엔드포인트)
- 응답 형태: {"job-count": 16, "jobs": [ ... ]}
- 특이사항: 급여가 숫자가 아니라 문자열로 온다. ("$100k - $150k" 같은 형식)
            → parse_salary_range 로 숫자를 뽑아낸다.
"""

import json
import urllib.request

from _lib.normalize import build_job, parse_salary_range

API_URL = "https://remotive.com/api/remote-jobs"
SOURCE = "Remotive"
TIMEOUT = 10


def fetch(limit=60):
    """Remotive 공고를 가져와 공통 형태로 변환한다. 실패 시 빈 리스트."""
    try:
        request = urllib.request.Request(
            API_URL,
            headers={"User-Agent": "JobFit/1.0 (educational project)"},
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))

        jobs = []
        for raw in payload.get("jobs", [])[:limit]:
            if not isinstance(raw, dict) or not raw.get("title"):
                continue

            salary_text = raw.get("salary") or ""
            salary_min, salary_max = parse_salary_range(salary_text)

            # 원격 전용 서비스지만 지원 국가 제한이 붙어 있다. 함께 표출한다.
            location = raw.get("candidate_required_location") or "Remote"

            jobs.append(
                build_job(
                    job_id="remotive:{}".format(raw.get("id")),
                    source=SOURCE,
                    title=raw.get("title"),
                    company=raw.get("company_name"),
                    location=location,
                    apply_url=raw.get("url", ""),
                    description=raw.get("description", ""),
                    tags=raw.get("tags") or [raw.get("category")],
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_text=salary_text,
                    job_type=raw.get("job_type", ""),
                    posted_at=raw.get("publication_date", ""),
                )
            )
        return jobs
    except Exception:
        print("[remotive] failed to fetch")
        return []
