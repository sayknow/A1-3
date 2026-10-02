/* ==========================================================================
   common.js — 3개 페이지가 공통으로 쓰는 함수들
   ========================================================================== */

/**
 * 현재 위치에 해당하는 내비게이션 링크에 is-active 클래스를 붙인다.
 * HTML 을 손으로 매번 class="is-active" 를 적을 필요가 없어진다.
 */
function markActiveNav() {
  const path = window.location.pathname.replace(/\/index\.html$/, "/");
  const links = document.querySelectorAll(".nav a");

  links.forEach((link) => {
    const href = link.getAttribute("href") || "";
    const isMatch = href === path || (path === "/" && href === "/index.html");
    if (isMatch) {
      link.classList.add("is-active");
      link.setAttribute("aria-current", "page");
    }
  });
}

/**
 * 금액을 사람이 읽기 좋은 형태로 바꾼다.
 * 0 이거나 정보가 없으면 "급여 정보 없음" 을 돌려준다.
 */
function formatSalary(job) {
  const min = job.salary_min;
  const max = job.salary_max;

  if (!max) return "급여 정보 없음";
  if (!min) return "~" + max.toLocaleString("en-US");

  return min.toLocaleString("en-US") + " ~ " + max.toLocaleString("en-US");
}

/**
 * 게시일 문자열을 "3일 전" 같은 상대 시각으로 바꾼다.
 * 잘못된 형식이 들어와도 예외를 던지지 않고 원본을 그대로 보여준다.
 */
function formatPostedAt(isoString) {
  if (!isoString) return "";

  const date = new Date(isoString);
  if (isNaN(date.getTime())) return "";

  const diffSeconds = Math.floor((Date.now() - date.getTime()) / 1000);

  if (diffSeconds < 0) return "방금";
  if (diffSeconds < 3600) return Math.max(1, Math.floor(diffSeconds / 60)) + "분 전";

  const hours = Math.floor(diffSeconds / 3600);
  if (hours < 24) return hours + "시간 전";

  const days = Math.floor(hours / 24);
  if (days < 30) return days + "일 전";

  return date.toISOString().slice(0, 10);
}

/**
 * 사용자 입력이나 외부 API 데이터를 HTML 에 넣을 때 반드시 쓴다.
 *
 * 왜 필요하냐: 공고 제목/회사에 <script> 같은 문자열이 들어올 수 있다.
 * 이스케이프 없이 innerHTML 에 넣으면 브라우저가 태스크립트로 실행해 버린다.
 * → XSS(교차 사이트 스크립팅) 방어의 기본기.
 */
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * 점수에 따라 색과 라벨을 정한다. 100에 가까울수록 좋은 색.
 */
function scoreTone(score) {
  if (score >= 75) return "";
  if (score >= 50) return "score-ring--mid";
  return "score-ring--low";
}

function scoreLabel(score) {
  if (score >= 75) return "높은 적합도";
  if (score >= 50) return "보통 적합도";
  if (score > 0) return "낮은 적합도";
  return "판단 보류";
}

/**
 * 공고 카드 HTML 한 개를 문자열로 만든다.
 * (공통 목록 페이지와 추천 결과 페이지가 함께 쓴다)
 */
function renderJobCard(job, options = {}) {
  const extra = options.extraHtml || "";
  const showScore = typeof options.score === "number";

  const scoreHtml = showScore
    ? '<div class="score-ring ' + scoreTone(options.score) +
      '" style="--pct:' + options.score + '" title="적합도 ' + options.score + '점">' +
      "<span>" + options.score + "</span></div>"
    : "";

  const tagsHtml = (job.tags || [])
    .slice(0, 5)
    .map((tag) => '<span class="tag">' + escapeHtml(tag) + "</span>")
    .join("");

  const postedText = formatPostedAt(job.posted_at);
  const salaryText = formatSalary(job);

  return (
    '<article class="job-card">' +
      '<div class="job-card__top">' +
        "<div>" +
          '<h3 class="job-card__title">' + escapeHtml(job.title) + "</h3>" +
          '<p class="job-card__company">' + escapeHtml(job.company) + "</p>" +
        "</div>" +
        scoreHtml +
      "</div>" +
      '<div class="job-card__meta">' +
        '<span class="badge badge--source">' + escapeHtml(job.source) + "</span>" +
        (job.remote ? '<span class="badge badge--remote">원격</span>' : "") +
        (job.job_type ? "<span>" + escapeHtml(job.job_type) + "</span>" : "") +
        "<span>📍 " + escapeHtml(job.location) + "</span>" +
        "<span>💰 " + escapeHtml(salaryText) + "</span>" +
        (postedText ? "<span>🕒 " + escapeHtml(postedText) + "</span>" : "") +
      "</div>" +
      (tagsHtml ? '<div class="tags">' + tagsHtml + "</div>" : "") +
      extra +
      '<div class="job-card__foot">' +
        '<a class="btn btn--ghost btn--sm" href="' + escapeHtml(job.apply_url) +
          '" target="_blank" rel="noopener noreferrer">공고 원문 보기 ↗</a>' +
      "</div>" +
    "</article>"
  );
}

/**
 * 로딩 스켈레톤 N 개를 만들어 넣는다.
 * (API 응답 전까지 빈 화면 대신 뼈대를 보여 UX 를 개선)
 */
function showSkeletons(container, count = 6) {
  if (!container) return;
  let html = "";
  for (let i = 0; i < count; i += 1) html += '<div class="skeleton"></div>';
  container.innerHTML = html;
}

/** 스켈레톤을 지우고 안내 메시지(빈 상태)를 보여준다. */
function showEmptyState(container, title, description) {
  if (!container) return;
  container.innerHTML =
    '<div class="empty">' +
      '<div class="empty__icon">🔍</div>' +
      "<h3>" + escapeHtml(title) + "</h3>" +
      "<p>" + escapeHtml(description || "") + "</p>" +
    "</div>";
}

/**
 * 로컬스토리지에 간단히 저장/읽기. 추천 조건을 새로고침해도 유지되게.
 * (JSON 직렬화 예외는 무시 — 브라우저 저장소가 막힌 경우 흔함)
 */
const store = {
  set(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      /* 저장 불가 환경에서는 조용히 무시한다 */
    }
  },
  get(key) {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  },
};

/* 페이지 공통 초기화 */
document.addEventListener("DOMContentLoaded", markActiveNav);
