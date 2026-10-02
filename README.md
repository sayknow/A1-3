<div align="center">

# 🎯 JobFit — 구직 맞춤 AI 추천 서비스

**"내 조건에 맞는 원격 구직 공고를 AI가 골라 이유와 함께 알려줍니다"**

순수 HTML / CSS / JavaScript + Vercel Serverless Functions (Python) 로 만든 구직 추천 웹 서비스

[데모 보기](https://jobfit-seven.vercel.app) · [기획서](docs/서비스기획서.md) · [저장소](https://github.com/sayknow/A1-3)

> **실제 배포 주소: https://jobfit-seven.vercel.app**
> (`jobfit.vercel.app` 은 이미 다른 서비스가 선점한 도메인이라 Vercel 이
> 임의의 이름을 붙였다. 별도 도메인 구매·연결 없이 동작한다.)

</div>

---

## 📌 서비스 소개

채용 공고는 여러 사이트에 흩어져 있고, 같은 공고가 중복되며, 급여나 조건 정보가 모호한 경우도 많습니다.
구직자는 "내가 이 공고에 맞는 걸까?"를 매번 스스로 판단해야 합니다.

**JobFit** 는 이 판단을 도와줍니다.

1. **실제로 올라온 공고만 씁니다** — 하드코딩한 예시 데이터가 아니라, 공개 원천 API 3곳에서 실시간 수집합니다.
2. **점수뿐 아니라 이유를 알려줍니다** — 매칭 근거, 아쉬운 점, 다음 행동을 함께 제시합니다.
3. **실패해도 죽지 않습니다** — 원천 서버 장애, AI 지연, 빈 입력까지 모두 처리하고 안내합니다.

### 주요 기능

| 기능 | 설명 |
| --- | --- |
| 🤖 AI 맞춤 추천 | 조건 입력 → 적합도 점수 + 근거 + 아쉬운 점 + 행동 제안 |
| 📋 공고 목록 탐색 | 출처 필터, 키워드 검색, 급여/최신 정렬 |
| 📊 데이터 출처 통계 | 어디서 몇 건이 왔는지 실시간 표시 |
| 📱 완전 반응형 | 모바일 / 태블릿 / 데스크톱 |

---

## 🛠 기술 스택

### 프론트엔드
- **순수 HTML / CSS / JavaScript** — 프레임워크·빌드 도구 없음
- `fetch()` API로 백엔드와 통신
- CSS Variables(`:root`)로 디자인 토큰 관리
- 반응형: 768px / 480px 브레이크포인트

### 백엔드
- **Vercel Serverless Functions (Python 3.12)**
- `api/` 폴더의 각 `.py` 파일이 독립적인 엔드포인트
- 외부 패키지 의존성 **0개** (표준 라이브러리 `urllib`, `json`만 사용)

### AI
- **provider-agnostic 구조**: 기본은 Google Gemini(`gemini-3.5-flash-lite`), `AI_PROVIDER=openai` 로 바꾸면 OpenAI(`gpt-4o-mini`)도 그대로 동작
- 일시적 과부하(503·429)에는 **짧은 지수 백오프로2회 재시도** 후 그래도 실패하면 폴백
- 키는 Vercel 환경변수로만 주입 → 브라우저에 절대 노출되지 않음
- 키가 없어도 **키워드 매칭 점수로 정상 동작** (기능 저하 시 안내)
- 키가 있어도 호출이 실패해도(인증 오류·쿼터 초과·파싱 실패) 자동으로 폴백하며, 어떤 상태였는지 응답의 `ai_status` 로 구분해 알려 줌

### 데이터 출처 (모두 API 키 불필요)

| 출처 | 엔드포인트 | 이용 약관 |
| --- | --- | --- |
| RemoteOK | `https://remoteok.com/api` | [remoteok.com](https://remoteok.com) |
| Remotive | `https://remotive.com/api/remote-jobs` | [remotive.com](https://remotive.com) |
| Arbeitnow | `https://www.arbeitnow.com/api/job-board-api` | [arbeitnow.com](https://www.arbeitnow.com) |

> 세 출처 모두 이용 약관에 따른 출처 명시를 화면 하단과 본 문서에 반영했습니다.
> 공고 내용은 원천 서버에 등록된 것을 그대로 옮긴 것이며, JobFit는 이를 보증하지 않습니다.

---

## 📂 프로젝트 구조

```
.
├── public/                 # ← Vercel 이 정적 루트로 서빙하는 폴더
│   ├── index.html          #   홈 — 소개 / 사용 흐름 / 데이터 출처
│   ├── recommend.html      #   AI 추천 (핵심 기능)
│   ├── jobs.html           #   공고 목록 (필터 · 검색 · 정렬)
│   ├── about.html          #   서비스 소개 · 실패 처리 기준 · 한계
│   ├── css/
│   │   └── style.css       #   공통 스타일시트 (4개 페이지 공유)
│   ├── js/
│   │   ├── common.js       #   공통 유틸 (포맷, 이스케이프, 카드 렌더링)
│   │   ├── api.js          #   fetch 래퍼 (타임아웃 · 오류 처리)
│   │   ├── home.js         #   홈 페이지 전용
│   │   ├── recommend.js    #   AI 추천 페이지 전용
│   │   └── jobs.js         #   공고 목록 페이지 전용
│   └── images/             #   이미지 (현재 비어 있음)
│
├── api/                    # ← Vercel Serverless Functions (루트에 있어야 인식됨)
│   ├── jobs.py             # GET  /api/jobs       공고 목록
│   ├── recommend.py        # POST /api/recommend  AI 추천
│   ├── requirements.txt    # 파이썬 의존성 (현재 없음)
│   └── _lib/               # 내부 모듈 (엔드포인트 아님)
│       ├── aggregate.py    #   3개 소스 병합 · 캐시
│       ├── cache.py        #   인메모리 TTL 캐시
│       ├── normalize.py    #   필드 통일 · 중복 제거
│       ├── matching.py     #   키워드 사전 매칭 · 점수 산식
│       ├── ai.py           #   provider 레지스트리 · LLM 호출 · 폴백 처리
│       └── providers/      #   소스별 어댑터
│           ├── remoteok.py
│           ├── remotive.py
│           └── arbeitnow.py
│
├── docs/
│   ├── 서비스기획서.md      # 서비스 기획서 (제출 항목)
│   └── screenshots/        # 증빙용 스크린샷 9장
│
├── scripts/
│   └── capture-screenshots.js   # Playwright 자동 캡처
│
├── dev_server.py           # 로컬 개발 서버 (배포에는 미사용)
├── .env.example            # 환경변수 예시 (실제 키 없음)
└── .gitignore              # .env 등 키 파일 제외 규칙
```

> **배포 설정에 `vercel.json` 이 없는 이유**
> 이 프로젝트는 Vercel **zero-config** 로 배포됩니다. `api/` 와 `public/` 만 있으면
> Vercel 이 서버리스 함수와 정적 파일을 동시에 자동 인식합니다.
>
> 실제로 `outputDirectory` 를 `vercel.json` 에 명시하면 Vercel 이
> "빌드 출력이 지정된 디렉터리" 모드로 전환하면서 `api/` 를 함수로 보지 않고
> 정적 자산으로 취급해 `/api/*` 가 404가 됩니다. 설정 파일이 오히려
> 자동 인식을 방해하는 경우입니다.
>
> Vercel 대시보드의 **Framework Preset** 은 `Other` 로 두어야 합니다.
> `Python` 으로 지정하면 Vercel 이 단일 엔트리포인트(`app.py` 등)를
> 찾으려고 해 `api/` 아래 여러 엔드포인트 구조와 맞지 않습니다.

---

## 🚀 실행 방법

### 방법 1 — 로컬에서 바로 실행 (추천)

Python 3.9 이상이면 **의존성 설치 없이** 실행됩니다.

```bash
git clone https://github.com/sayknow/A1-3.git
cd A1-3
python3 dev_server.py
```

브라우저에서 **http://localhost:8000** 접속

> `dev_server.py` 는 Vercel 이 로컬에서 어떻게 동작하는지 재현하는 개발용 서버입니다.
> 배포에는 사용되지 않으며, 이 파일 없이도 Vercel 은 정상 동작합니다.
> 로컬 서버는 엔드포인트의 실제 로직인 `api/jobs.py` 의 `_run()` 을 직접 호출하고,
> 배포 환경에서는 Vercel 이 같은 `_run()` 을 `BaseHTTPRequestHandler` 로 감싸 실행합니다.

### 방법 2 — Vercel CLI 사용

```bash
npm i -g vercel
vercel login
vercel          # 개발용
vercel --prod   # 프로덕션 배포
```

### 포트 변경

```bash
JOBFIT_PORT=3000 python3 dev_server.py
```

---

## 🔑 환경 변수 설정

### 왜 환경 변수를 써야 하나?

API 키를 코드에 적어 두면 저장소에 공개됩니다. 누군가 그 저장소를 복제하면
키를 그대로 가져가 과금당할 수 있습니다. 환경 변수는 **서버에서만 읽히고
브라우저에는 전혀 전달되지 않기** 때문에 안전합니다.

### 필요한 변수

| 변수명 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `AI_PROVIDER` | 선택 | `gemini` | 사용할 AI 제공자 (`gemini` / `openai`) |
| `GEMINI_API_KEY` | 선택 | 없음 | Google Gemini API 키. 없으면 키워드 매칭만 동작 |
| `GEMINI_MODEL` | 선택 | `gemini-3.5-flash-lite` | 사용할 모델 |
| `OPENAI_API_KEY` | 선택 | 없음 | `AI_PROVIDER=openai` 일 때만 사용 |
| `OPENAI_MODEL` | 선택 | `gpt-4o-mini` | `AI_PROVIDER=openai` 일 때의 모델 |

> **AI 키 없이도 서비스는 100% 동작합니다.** AI 대신 키워드 점수를 계산해
> 결과를 보여주고, 화면에 "AI 미연동 상태" 배지를 표시합니다.

### 로컬에서 설정

```bash
cp .env.example .env.local
# .env.local 안에 실제 키 입력
```

`.env.local` 은 `.gitignore` 에 등록되어 있어 커밋되지 않습니다.

### Vercel 에서 설정

1. Vercel 대시보드 → 해당 프로젝트 → **Settings** → **Environment Variables**
2. `AI_PROVIDER=gemini` 과 `GEMINI_API_KEY` 추가 (Production / Preview / Development 모두 체크)
3. Redeploy

또는 CLI 로:

```bash
vercel env add GEMINI_API_KEY production
```

### 키 유출 시 대응

1. Vercel 대시보드에서 해당 변수를 **삭제**
2. AI 제공자 대시보드에서 키를 **폐기(Revoke)** 하고 새로 발급 (Gemini: [AI Studio](https://aistudio.google.com/apikey))
3. 새 키를 Vercel 에 등록 후 Redeploy

> 이 저장소에는 키가 커밋된 적이 없으므로 **커밋 이력 정리(rebase·history rewrite)가 불필요**합니다.

---

## 🔌 API 문서

### `GET /api/jobs`

공고 목록을 반환합니다.

| 파라미터 | 기본값 | 설명 |
| --- | --- | --- |
| `limit` | 60 | 반환 개수 (1~200) |
| `refresh` | — | `1` 이면 서버 캐시를 무시하고 새로 수집 |

```json
{
  "jobs": [ { "id": "...", "source": "RemoteOK", "title": "..." } ],
  "total": 133,
  "sources": { "RemoteOK": 59, "Arbeitnow": 58, "Remotive": 16 },
  "collected_at": "2026-09-29T07:43:00Z",
  "cache_age_seconds": 120
}
```

### `POST /api/recommend`

AI 맞춤 추천을 반환합니다.

```json
// 요청
{
  "role": "백엔드",
  "skills": "python, docker, aws",
  "level": "mid",
  "min_salary": 50000,
  "top_n": 5
}
```

```json
// 응답
{
  "results": [
    {
      "job": { "...": "공고 정보" },
      "match_score": 70,
      "code_score": 70,
      "reasons": ["직무 '백엔드'와 관련 있는 포지션", "..."],
      "concern": "",
      "action": "",
      "ai_used": true
    }
  ],
  "ai_status": "ok",          // ok | failed | disabled
  "total_jobs": 133,
  "candidate_count": 8
}
```

### 오류 응답

모든 오류는 `{ "error": "사용자용 한국어 메시지" }` 형태입니다.
프론트엔드는 이 메시지를 그대로 화면에 표시합니다.

| 상태 | 의미 |
| --- | --- |
| 400 | 입력값 오류 / JSON 형식 오류 |
| 404 | 조건에 맞는 공고 없음 |
| 405 | 잘못된 HTTP 메서드 |
| 503 | 원천 서버 3곳 모두 실패 |

---

## 🛡 실패 처리 대응표

과제 요구사항에 따라 **빈 입력 · API 오류 · 지연/타임아웃** 을 모두 처리했습니다.

| 상황 | 처리 방식 |
| --- | --- |
| 빈 입력 (필수값 누락) | 400 + 어느 칸인지 안내 + 빨간 테두리 |
| 잘못된 JSON | 400 + 안내 메시지 |
| HTTP 메서드 오류 | 405 + 안내 메시지 |
| 원천 서버 전체 실패 | 503 + "잠시 후 다시 시도" (빈 화면 아님) |
| AI 키 미설정 | 200 + "AI 미연동" 배지 + **코드 점수로 정상 제공** |
| AI 호출 실패 | 200 + "코드 분석으로 대체됨" 배지 + **결과 정상 제공** |
| 응답 지연 (45초) | `AbortController` 로 요청 중단 + 타임아웃 안내 |
| 네트워크 단절 | "서버에 연결하지 못했습니다" 안내 |
| 소스 1곳 실패 | 나머지 소스로 계속 제공 (부분 실패 허용) |
| 서버 내부 예외 | 핸들러가 500 JSON 응답으로 변환 (프로세스 죽지 않음) |

### 운영 환경 검증 결과 (실제 배포 주소 기준)

`https://jobfit-seven.vercel.app` 에서 확인한 실제 응답입니다.

| 요청 | 응답 |
| --- | --- |
| `GET /api/jobs?limit=100` | 200 · 전체 135건 (Arbeitnow 60 / RemoteOK 59 / Remotive 16) |
| `POST /api/recommend` (정상 입력) | 200 · 후보 8건 축소 후 top_n 건 선별 · AI 연동 시 `ai_status: "ok"`, `ai_used: true` |
| `GET /api/jobs?limit=abc` | 400 |
| `GET /api/jobs?limit=9999` | 400 |
| `GET /api/recommend` | 405 |
| `POST /api/recommend` (빈 본문) | 400 |
| `POST /api/recommend` (깨진 JSON) | 400 |
| `GET /api/nope` | 404 |

### AI 경로 3가지 상태 모두 실측

`ai_status` 필드로 사용자에게 어떤 경로로 응답했는지 구분해 알려 줍니다.

| 상태 | 조건 | 실제 확인 내용 |
| --- | --- | --- |
| `ok` | 정상 | AI 가 코드 점수(70·59·49)를 재랭킹해 75·58·52로 조정, 항목별 `ai_used: true`, 근거·아쉬운 점·제안 모두 채워짐. 화면 배지 "AI 분석 적용됨" |
| `failed` | 키가 있으나 호출 실패 | `503 UNAVAILABLE (high demand)` · `400` 때도 로그에 provider 가 알려준 사유를 남김(키 마스킹). **결과는 코드 점수로 정상 반환** (HTTP 200) |
| `disabled` | 키 없음 | `ai_used: false`, 근거는 키워드 사전 매칭, `concern`/`action` 공백. 화면 배지 "AI 미연동 상태" |

> `failed` 로 내려가는 순간에도 서비스는 죽지 않고 폴백 결과로 응답합니다.
> 일시적 과부하(429·5xx)에는 짧은 재시도(2회)를 거쳐 다시 AI 경로를 시도합니다.

> AI 키 없이 배포된 상태이므로 `ai_status: "disabled"` 로 응답하며,
> 화면에는 "AI 미연동 상태" 배지와 함께 코드 점수 기반 결과가 정상 표시됩니다.

---

## 🔐 보안 관련

| 항목 | 조치 |
| --- | --- |
| API 키 | 코드에 없음. Vercel 환경변수로만 주입 |
| 키 커밋 방지 | `.env`, `.env.local`, `.vercel` 을 `.gitignore` 에 등록 |
| 예시 파일 | `.env.example` 은 값 없이 설명만 포함 (커밋 대상) |
| XSS | 외부 API 데이터를 `escapeHtml()` 로 이스케이프 후 DOM 삽입 |
| 경로 탈출 방지 | 개발 서버가 `..` 경로 차단 |
| 내부 정보 노출 | AI 오류는 서버 로그에만 남기고(키 값은 마스킹), 사용자에게는 일반 메시지 |

---

## 📱 반응형 확인

| 화면 크기 | 확인 결과 |
| --- | --- |
| 1280 × 900 (데스크톱) | ✅ 카드 3열, 폼 2열 |
| 390 × 844 (모바일) | ✅ 카드 1열, 내비게이션 2줄, **가로 스크롤 없음** |

접근성: `aria-label`, `aria-current`, `role="alert"`, `:focus-visible`,
`prefers-reduced-motion` 반영

---

## ⚠️ 알려진 한계

1. **국내 공고 미포함** — 사용한 API가 모두 해외 원격 공고 중심 (국내는 API 승인 절차 필요)
2. **캐시가 휘발적** — Serverless 메모리 캐시라 인스턴스 종료 시 사라짐
3. **비-IT 공고 혼재** — Arbeitnow 출처의 일반 고용 공고는 직군 적합도로 감점 처리
4. **추천은 참고용** — 실제 적합도 아님. 지원 가능 여부는 공고 원문 판단이 우선

---

## 🤖 AI 코딩 도구 사용 증빙

본 프로젝트는 **AI 코딩 도구(Freebuff Desktop)의 Buffy 에이전트와의 대화**를 통해
기획부터 구현·검증까지 진행했습니다.

### 작업 과정 요약

| 단계 | 내용 |
| --- | --- |
| 1. 조사 | 과제 요구사항 분석 → 공고 API 후보 조사 (curl 실데이터 확인) |
| 2. 설계 | 데이터 소스·AI 기능 형태 결정 → 모듈 구조 설계 |
| 3. 구현 | 백엔드(`api/_lib/`) → 프론트(4페이지) 순서로 작성 |
| 4. 검증 | 단위 테스트 9종 → 브라우저 실동작 → 반응형 2사이즈 확인 |
| 5. 수정 | 발견된 실제 버그 3건을 대화 중 즉시 수정 |

### 대화 중 실제로 발견하고 수정한 버그

1. **급여 파싱 오류** — `"90k - 105k"` 형태를 읽지 못하고 `105` 로 파싱 → 단위(`k`/`m`)와 유럽식 표기(`€45.000`) 처리 로직 추가
2. **`fetchJobs is not defined`** — `index.html` 에 `api.js` 스크립트 누락 → 스크립트 태그 추가
3. **환경변수 `PORT` 충돌** — 호스트 환경의 `PORT` 와 겹쳐 서버가 의도치 않은 포트로 실행 → `JOBFIT_PORT` 로 분리
4. **비-IT 공고 오염** — 세차장 공고가 백엔드 개발자에게 1위 추천 → 직군 적합도 가중치 도입으로 완전 배제

> **증빙 자료**: AI 코딩 도구 사용 대화 로그 또는 스크린샷을 별도로 제출합니다.

---

## 📄 라이선스 / 출처

- 코드: 과제 수행용 작성물
- 공고 데이터: [RemoteOK](https://remoteok.com) · [Remotive](https://remotive.com) · [Arbeitnow](https://www.arbeitnow.com) 각 이용 약관 준범
- AI: Google Gemini API (`gemini-3.5-flash-lite`), provider 교체 가능 구조
