"""
공고 정규화(Normalization) 모듈.

외부 API마다 필드 이름과 형태가 제각각이다.
예를 들어 회사명은 RemoteOK에서는 `company`, Remotive에서는 `company_name`이다.
사용자(그리고 AI) 입장에서는 이 차이를 몰라도 되게,
모든 공고를 아래 '공통 형태'로 바꿔서 내보낸다.

공통 형태(Job):
    {
      "id":          "remoteok:1137434",   # 중복 방지용 고유 ID
      "source":      "RemoteOK",           # 어느 API에서 왔는지
      "title":       "Senior Frontend Engineer",
      "company":     "SIHO Insurance",
      "location":    "Columbus, IN",
      "remote":      True,                 # 원격 근무 여부
      "tags":        ["react", "typescript"],
      "salary_min":  0,                    # 0이면 정보 없음
      "salary_max":  0,
      "salary_text": "",                   # 원본이 텍스트로 준 경우
      "job_type":    "full_time",
      "posted_at":   "2026-09-26T16:00:26Z",
      "apply_url":   "https://...",
      "description": "...",
    }
"""

import re
import html as html_module

# HTML 태그를 제거하고 텍스트만 남긴다. 공고 설명에 HTML이 포함된 경우가 많다.
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(raw):
    """HTML 조각을 평문 텍스트로 바꾼다.

    AI에게 보낼 때 태그가 그대로 들어오면 토큰을 낭비하고 품질도 떨어지므로
    반드시 한 번 정리해 준다.
    """
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", str(raw))
    text = html_module.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def normalize_tags(tags, limit=12):
    """태그 배열을 정리한다. None이거나 문자열이면 빈 리스트로 처리."""
    if not tags:
        return []
    if isinstance(tags, str):
        tags = [tags]
    cleaned = []
    for tag in tags:
        text = str(tag).strip()
        if text and text.lower() not in [t.lower() for t in cleaned]:
            cleaned.append(text)
    return cleaned[:limit]


def parse_salary_range(raw):
    """'50000 - 70000 EUR / Year' 같은 문자열에서 숫자 최솟값/최댓값을 뽑는다.

    실제 데이터에서 '105k', '$150,000' 처럼 표기가 제각각이라 단위를 함께 처리한다.
        "90k - 105k"        → (90000, 105000)
        "$100,000 - 150,000" → (100000, 150000)
        "competitive"        → (0, 0)   ← 정보 없음

    뽑지 못하면 (0, 0)을 돌려준다. 0은 "정보 없음"이라는 뜻이다.
    """
    if not raw:
        return 0, 0

    # 숫자 뒤에 k / m 가 붙는지까지 한 번에 잡아낸다.
    # 숫자 사이 구분자는 ','(영미권)와 '.'(유럽권) 둘 다 본다.
    matches = re.findall(r"(\d[\d,.]*)\s*([kKmM]?)", str(raw))
    values = []
    for digits, suffix in matches:
        try:
            # 마지막 구분자 뒤가 정확히 3자리면 천 단위 구분자로 해석한다.
            # ("45.000" → 45000)  그렇지 않으면 소수점이라고 보고 떼어낸다.
            # ("45.5" → 45.5 → 45)  이 분기를 안 하면 45000 으로 잘못 읽힌다.
            if re.search(r"[,.]\d{3}$", digits):
                number = int(re.sub(r"[,.]$", "", digits).replace(",", "").replace(".", ""))
            else:
                number = int(float(digits.replace(",", "")))
        except ValueError:
            continue
        if suffix.lower() == "k":
            number *= 1000
        elif suffix.lower() == "m":
            number *= 1000000
        # 연봉이므로 비현실적으로 큰 값은 오탐으로 보고 버린다.
        if 0 < number <= 10_000_000:
            values.append(number)

    if not values:
        return 0, 0
    return min(values), max(values)


def to_int(value):
    """문자열/None을 정수로 안전하게 바꾼다. 실패하면 0."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def looks_remote(text):
    """'Remote' / '원격' / 'Anywhere' 같은 단어가 들어 있으면 원격으로 본다."""
    if not text:
        return True  # 원격 전용 API이므로 기본값은 True
    lowered = str(text).lower()
    keywords = ["remote", "anywhere", "worldwide", "원격", "재택", "location independent"]
    return any(keyword in lowered for keyword in keywords)


def build_job(job_id, source, title, company, location, apply_url,
              description="", tags=None, salary_min=0, salary_max=0,
              salary_text="", job_type="", posted_at=""):
    """모든 정규화 함수들을 한데 모아 공통 형태의 공고 딕셔너리를 만든다.

    provider 모듈들이 각각 이 함수를 호출하면, 필드 빠뜨리는 실수를 줄일 수 있다.
    """
    return {
        "id": job_id,
        "source": source,
        "title": strip_html(title) or "제목 미지정",
        "company": strip_html(company) or "회사명 미지정",
        "location": strip_html(location) or "원격",
        "remote": looks_remote(location),
        "tags": normalize_tags(tags),
        "salary_min": to_int(salary_min),
        "salary_max": to_int(salary_max),
        "salary_text": strip_html(salary_text),
        "job_type": job_type,
        "posted_at": posted_at,
        "apply_url": apply_url,
        # AI에게 넘길 때는 설명을 길게 보내면 비용이 커지므로 1200자로 자른다.
        "description": strip_html(description)[:1200],
    }


def dedupe(jobs):
    """같은 공고가 여러 API에 중복으로 들어 있는 경우를 제거한다.

    같은 회사의 같은 포지션이 RemoteOK와 Remotive에 둘 다 올라오는 경우가 실제로 있다.
    정규화한 제목 + 회사명을 비교 기준으로 삼는다.
    """
    seen = set()
    unique = []
    for job in jobs:
        key = (
            re.sub(r"[^a-z0-9가-힣]", "", job["title"].lower()),
            re.sub(r"[^a-z0-9가-힣]", "", job["company"].lower()),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique
