"""
인메모리 캐시 모듈.

왜 캐시가 필요한가?
- 외부 공고 API(RemoteOK/Remotive/Arbeitnow)를 매 요청마다 호출하면
  (1) 느리고, (2) 상대 서버에 부담을 주며, (3) 사용자가 몰릴 때 실패하기 쉽다.
- 그래서 한 번 모은 공고를 일정 시간 동안 재사용한다.

한계: Vercel Serverless Functions의 인스턴스는 수명이 짧고 요청 간에
재사용되지 않을 수 있다. 따라서 이 캐시는 "성능 최적화"이지 "영구 저장"이 아니다.
어떤 인스턴스에서도 캐시가 비어 있으면 그때 다시 수집한다.
그래도 사용자 1명이 5초 안에 10번 새로고침하는 상황에서는 확실히 효과적이다.
"""

import time
import threading

# 전역 캐시 저장소
_cache = {}
_lock = threading.Lock()

# 기본 TTL(초). 외부 API를 너무 자주 때리지 않기 위한 값.
DEFAULT_TTL = 600  # 10분


def get(key):
    """캐시에서 값을 읽는다. TTL이 지났거나 없으면 None을 반환한다."""
    with _lock:
        item = _cache.get(key)
        if item is None:
            return None

        value, expires_at, stale_fallback = item

        if time.time() < expires_at:
            return value

        # TTL은 지났지만 마지막 정상 값이 남아 있으면 그것을 살려서 쓴다.
        # (외부 API 장애 시 서비스를 완전히 죽이지 않기 위한 안전장치)
        if stale_fallback is not None:
            _cache[key] = (stale_fallback, expires_at, stale_fallback)
            return stale_fallback

        _cache.pop(key, None)
        return None


def set(key, value, ttl=DEFAULT_TTL):
    """캐시에 값을 저장한다. 기존 값이 있다면 '안전장치 값'으로 함께 보관한다."""
    with _lock:
        previous = _cache.get(key)
        stale_fallback = previous[2] if previous else None
        _cache[key] = (value, time.time() + ttl, stale_fallback)


def age(key):
    """해당 키가 캐시에 저장된 지 얼마나 지났는지(초). 없으면 None."""
    with _lock:
        item = _cache.get(key)
        if item is None:
            return None
        return int(time.time() - (item[1] - DEFAULT_TTL))


def clear():
    """테스트용. 캐시를 전부 비운다."""
    with _lock:
        _cache.clear()
