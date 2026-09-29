"""
공고 수집 총괄 모듈.

프로바이더 3종(RemoteOK / Remotive / Arbeitnow)을 호출해서
하나의 공고 목록으로 합치고, 캐시에 보관한다.

설계 원칙: **부분 실패를 허용한다.**
세 API 중 하나가 죽어도 나머지 둘로 서비스를 계속 제공한다.
사용자에게 "공고가 하나도 없다"보다 "일부만 수집됐다"가 훨씬 낫다.
"""

import time

from _lib import cache
from _lib.normalize import dedupe
from _lib.providers import arbeitnow, remoteok, remotive

CACHE_KEY = "all_jobs"
CACHE_TTL = 600  # 10분


def collect_jobs(limit_per_source=60):
    """3개 API를 모두 호출해 공고 목록을 만든다. (캐시 미사용 직접 호출)"""
    started = time.time()

    collected = []
    # 여기서 try/except로 감싸지 않아도 각 프로바이더가 스스로 예외를
    # 삼키고 빈 리스트를 돌려준다. 그 설계 덕분에 여기서는 단순해진다.
    collected += remoteok.fetch(limit_per_source)
    collected += remotive.fetch(limit_per_source)
    collected += arbeitnow.fetch(limit_per_source)

    # 서로 다른 API에 같은 공고가 올라와 있을 수 있으므로 정리한다.
    unique = dedupe(collected)

    # 최근 공고가 위로 오도록 정렬. 날짜 형식이 제각각이라 안전하게 비교한다.
    unique.sort(key=lambda job: job.get("posted_at") or "", reverse=True)

    print(
        "[aggregate] collected={} unique={} in {}ms".format(
            len(collected), len(unique), int((time.time() - started) * 1000)
        )
    )
    return unique


def get_jobs(limit_per_source=60, force_refresh=False):
    """캐시를 확인하고, 없거나 만료됐을 때만 실제로 수집한다.

    force_refresh=True 이면 캐시를 무시하고 새로 수집한다.
    (화면의 '새로고침' 버튼에서 사용)
    """
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached

    jobs = collect_jobs(limit_per_source)
    if jobs:
        # 아무것도 못 받았을 때는 캐시를 덮어쓰지 않는다.
        # 기존에 있던 정상 데이터를 살려두는 편이 낫다.
        cache.set(CACHE_KEY, jobs, ttl=CACHE_TTL)
    return jobs


def describe_sources(jobs):
    """어느 소스에서 몇 건씩 왔는지 집계한다. 화면의 '데이터 출처' 영역에 쓰인다."""
    counts = {}
    for job in jobs:
        source = job.get("source", "unknown")
        counts[source] = counts.get(source, 0) + 1
    return counts
