"""
키워드 기반 매칭 모듈.

역할: 사용자 입력(직무, 기술스택, 경력 등)과 공고 텍스트를 비교해서
순수 코드만으로 점수를 매긴다.

왜 AI가 아니라 코드가 먼저인가?
1. **비용**: 공고가 수백 건이다. 전부 AI에 넣으면 비싸고 느리다.
   코드 필터로 후보를 줄인 뒤 상위 N건만 AI에 넘긴다.
2. **안정성**: AI API가 실패해도 이 단계는 항상 동작한다.
   그래도 사용자에게는 최소한의 추천 결과를 줄 수 있다.
3. **설명 가능성**: 과제 목표가 '왜 이런 결과가 나왔는지 설명'이다.
   키워드 일치 근거는 코드가 계산하므로 100% 재현된다.
"""

# 공고 텍스트에서 자주 쓰이는 직무/스킬 키워드.
# 사용자가 입력한 단어가 여기 있는 키워드와 겹치면 점수를 준다.
SKILL_KEYWORDS = [
    # 언어
    "python", "javascript", "typescript", "java", "kotlin", "go", "golang",
    "rust", "c++", "c#", "ruby", "php", "swift", "scala", "r",
    # 웹 프론트
    "react", "vue", "angular", "svelte", "next.js", "nextjs", "html", "css",
    "tailwind", "redux", "web", "frontend", "front-end", "ui",
    # 백엔드
    "node", "nodejs", "express", "django", "flask", "fastapi", "spring",
    "backend", "back-end", "server", "api", "rest", "graphql",
    # 데이터/인프라
    "sql", "postgres", "mysql", "mongodb", "redis", "aws", "gcp", "azure",
    "docker", "kubernetes", "k8s", "terraform", "linux", "devops", "cicd",
    "git", "github",
    # AI/ML
    "ai", "ml", "machine learning", "deep learning", "llm", "pytorch",
    "tensorflow", "nlp", "data science", "data engineer",
    # 모바일
    "android", "ios", "react native", "flutter", "mobile",
    # 기타 개발 일반
    "test", "testing", "pytest", "jest", "ci/cd", "security", "performance",
]

# 직무 계열. 직무 입력과 공고 제목/태그를 대조할 때 쓴다.
ROLE_KEYWORDS = {
    "프론트": ["frontend", "front-end", "front end", "react", "vue", "angular",
               "ui engineer", "web developer"],
    "백엔드": ["backend", "back-end", "back end", "server", "api", "django",
               "flask", "spring", "node"],
    "풀스택": ["fullstack", "full-stack", "full stack", "mern", "mean"],
    "데이터": ["data", "analytics", "analyst", "scientist", "etl", "bi "],
    "ai": ["ai", "ml", "machine learning", "llm", "nlp", "deep learning"],
    "모바일": ["android", "ios", "mobile", "flutter", "react native"],
    "devops": ["devops", "sre", "infrastructure", "platform", "cloud",
               "kubernetes", "terraform"],
    "qa": ["qa", "quality", "test", "tester", "automation"],
}

# 기술 수준 → 연차 가중치. 경력이 많을수록 포지션 레벨이 높은 공고를 우선한다.
SENIORITY_KEYWORDS = {
    "junior": ["junior", "entry", "intern", "associate", "new grad", "0-1"],
    "mid": ["mid", "intermediate", "ii", "2-3"],
    "senior": ["senior", "sr", "lead", "staff", "principal", "5+", "expert"],
}


# IT/개발 직군 관련성을 가리는 키워드.
#
# 왜 이게 필요한가:
# 사용한 원천 API 중 Arbeitnow 는 '_general' 이라는 이름과 달리_IT 외에
# 청소, 배달, 제조 등 일반 고용 공고까지 섞여 있다.
# 실제로 "Autowaschstraße(세차장) - Reinigung" 같은 공고가 상위에 올라온 적이 있다.
# 파이썬 백엔드 개발자에게 이를 추천하면 신뢰가 깨지므로,
# 개발 직군 공고에 가산점을 주고(중립) 일반 고용 공고에는 감점을 준다.
TECH_SIGNALS = [
    "developer", "engineer", "developer", "programmer", "software", "devops",
    "sre", "full stack", "fullstack", "frontend", "backend", "web", "api",
    "database", "cloud", "linux", "python", "javascript", "typescript",
    "react", "vue", "angular", "node", "java", "golang", "rust", "c++",
    "data", "machine learning", "ai ", "ml ", "dev", "qa", "test automation",
    "mobile", "ios", "android", "security", "product manager", "designer",
    "ux", "ui ", "figma", "notion", "slack",
]

# 확실히 개발/전문직이 아닌 일반 고용 공고 신호.
NON_TECH_SIGNALS = [
    "reinigung", "kundenservice", "pflege", "hilfskraft", "produktion",
    "logistik", "lager", "gastronom", "küche", "hausmeister", "fahrer",
    "verkauf", "Einzelhandel", "flushing", "quereinsteiger", "zulagen",
]


def tech_relevance(job):
    """공고가 IT/전문직인지 0~1 로 평가한다.

    1.0 = 확실히 IT 직군, 0.5 = 판단 불가(중립), 0.0 = 확실히 일반 고용
    """
    text = "{} {} {}".format(
        job.get("title", ""), " ".join(job.get("tags", [])), job.get("job_type", "")
    ).lower()

    has_non_tech = any(signal in text for signal in NON_TECH_SIGNALS)
    if has_non_tech:
        return 0.0

    has_tech = any(signal in text for signal in TECH_SIGNALS)
    return 1.0 if has_tech else 0.5


def _text_of(job):
    """공고에서 비교 가능한 텍스트를 하나로 모은다."""
    parts = [job.get("title", ""), job.get("company", ""), job.get("job_type", "")]
    parts += job.get("tags", [])
    parts.append(job.get("description", ""))
    return " ".join(parts).lower()


def score_job(job, profile):
    """공고 1건에 대해 사용자 프로필과의 적합 점수(0~100)를 계산한다.

    점수 구성 (합계 100):
      - 직무 연관성      최대 40점
      - 기술스택 일치    최대 35점
      - 급여 선호        최대 15점
      - 신입/경험 정합    최대 10점
    """
    text = _text_of(job)
    title_and_tags = "{} {}".format(
        job.get("title", ""), " ".join(job.get("tags", []))
    ).lower()

    score = 0
    reasons = []

    # 1) 직무 연관성 (최대 40점)
    wanted_role = (profile.get("role") or "").lower()
    if wanted_role:
        matched_terms = [
            term for term in ROLE_KEYWORDS.get(wanted_role, [wanted_role])
            if term in title_and_tags
        ]
        if matched_terms:
            # 일치하는 항목이 많을수록 좋지만, 3개 이상이면 충분히 확실한 것으로 본다.
            gain = min(40, 12 * len(matched_terms))
            score += gain
            reasons.append("직무 '{}'와 관련 있는 포지션 ({})".format(
                wanted_role, ", ".join(matched_terms[:3])))

    # 2) 기술스택 일치 (최대 35점)
    skills = [s.strip().lower() for s in (profile.get("skills") or "").split(",") if s.strip()]
    hit_skills = []
    for skill in skills:
        # "c++" 처럼 기호가 들어간 단어도 대소문자 무시하고 부분 일치로 찾는다.
        if skill in text:
            hit_skills.append(skill)
    if skills:
        ratio = len(hit_skills) / len(skills)
        gain = int(35 * ratio)
        score += gain
        if hit_skills:
            reasons.append("입력한 기술 {} 중 {}건이 공고에 등장".format(
                ", ".join(skills), len(hit_skills)))
        else:
            reasons.append("입력한 기술 스택이 공고 텍스트에 직접적으로 나타나지 않음")

    # 3) 급여 선호 (최대 15점)
    min_salary = profile.get("min_salary")
    job_max = job.get("salary_max") or 0
    if min_salary:
        try:
            wanted = int(min_salary)
        except (TypeError, ValueError):
            wanted = 0
        if wanted and job_max:
            if job_max >= wanted:
                score += 15
                reasons.append("공고 상한 금여 {}가 희망 {} 이상".format(job_max, wanted))
            elif job_max >= wanted * 0.8:
                score += 7
                reasons.append("공고 상한 금여 {}가 희망치에 다소 미흡".format(job_max, wanted))
            else:
                reasons.append("공고 상한 금여 {}가 희망 {}보다 낮음".format(job_max, wanted))
        elif wanted and not job_max:
            # 급여 정보가 없는 공고는 불이익을 주지 않는다(정보 없음 ≠ 조건 불일치).
            score += 6

    # 4) 경력 수준 정합 (최대 10점)
    level = (profile.get("level") or "").lower()
    if level:
        matched_level = [
            term for term in SENIORITY_KEYWORDS.get(level, [])
            if term in title_and_tags
        ]
        if matched_level:
            score += 10
            reasons.append("경력 수준 '{}'에 맞는 포지션".format(level))
        else:
            reasons.append("공고에 '{}' 레벨 표기가 명확하지 않음".format(level))

    # 5) 직군 적합도 가산/감점 (최대 ±12점)
    #    개발 직군 공고는 살짝 올리고, 일반 고용 공고는 확실히 내린다.
    relevance = tech_relevance(job)
    if relevance == 1.0:
        score += 8
    elif relevance == 0.0:
        score -= 12
        reasons.append("IT/전문직 공고가 아닌 일반 고용 공고입니다")

    return max(0, min(100, score)), reasons


def prefilter(jobs, profile, limit=20):
    """전체 공고에서 점수 상위 limit 건만 남긴다.

    AI에 넘길 후보를 줄이는 용도. 0점인 공고는 어차피 추천할 이유가 없으니 버린다.
    """
    scored = []
    for job in jobs:
        score, reasons = score_job(job, profile)
        if score <= 0:
            continue
        scored.append({"job": job, "score": score, "reasons": reasons})

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]
