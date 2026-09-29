"""
RemoteOK 프로바이더.

- 출처: https://remoteok.com/api
- 인증: API 키 불필요 (공개 엔드포인트)
- 사용 약관: RemoteOK 출처를 명시하고 링크해야 한다.
            → 화면 하단 '데이터 출처' 영역과 README에 반영했다.
- 특이사항: 응답 배열의 첫 번째 원소는 항상 약관 안내용 메타데이터다.
            job을 그대로 쓰면 "안내문"이 공고 1건으로 잡히므로 반드시 건너뛴다.
"""

import json
import urllib.request

from _lib.normalize import build_job

API_URL = "https://remoteok.com/api"
SOURCE = "RemoteOK"
TIMEOUT = 10  # 초. 오래 걸리면 다음 프로바이더로 넘어가야 하므로 짧게 잡는다.


def fetch(limit=60):
    """RemoteOK에서 공고 목록을 가져와 공통 형태로 변환해 돌려준다.

    실패하면 빈 리스트를 돌려준다. 예외를 밖으로 던지지 않는 이유는
    이 API가 죽어도 나머지 프로바이더와 서비스 전체는 계속 동작해야 하기 때문.
    """
    try:
        request = urllib.request.Request(
            API_URL,
            headers={"User-Agent": "JobFit/1.0 (educational project)"},
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))

        jobs = []
        for raw in payload[1:limit + 1]:  # [0]은 약관 메타데이터
            if not isinstance(raw, dict) or not raw.get("position"):
                continue

            jobs.append(
                build_job(
                    job_id="remoteok:{}".format(raw.get("id") or raw.get("slug")),
                    source=SOURCE,
                    title=raw.get("position"),
                    company=raw.get("company"),
                    location=raw.get("location"),
                    apply_url=raw.get("url") or raw.get("apply_url") or "",
                    description=raw.get("description", ""),
                    tags=raw.get("tags"),
                    salary_min=raw.get("salary_min", 0),
                    salary_max=raw.get("salary_max", 0),
                    posted_at=raw.get("date", ""),
                )
            )
        return jobs
    except Exception:
        # 여기서 로그를 남기면 Vercel 로그에서 원인을 볼 수 있다.
        print("[remoteok] failed to fetch")
        return []
