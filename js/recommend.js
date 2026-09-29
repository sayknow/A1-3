/* ==========================================================================
   recommend.js — AI 추천 페이지 전용 스크립트

   이 파일이 과제의 핵심 흐름을 그대로 보여준다:
       사용자 입력 → fetch 로 서버에 전달 → 서버(AI) 처리 → 응답을 화면에 렌더링
   ========================================================================== */

/* DOM 요소 참조. 반복해서 쓸 것이므로 미리 변수에 담아둔다. */
const form = document.getElementById("recommend-form");
const submitBtn = document.getElementById("submit-btn");
const resetBtn = document.getElementById("reset-btn");
const alertBox = document.getElementById("form-alert");
const alertText = document.getElementById("form-alert-text");
const initialHint = document.getElementById("initial-hint");
const loadingSection = document.getElementById("loading-section");
const loadingSkeletons = document.getElementById("loading-skeletons");
const resultsSection = document.getElementById("results-section");
const resultsBox = document.getElementById("results");
const resultsSub = document.getElementById("results-sub");
const aiFallbackAlert = document.getElementById("ai-fallback-alert");
const aiFallbackText = document.getElementById("ai-fallback-text");
const aiBadge = document.getElementById("ai-badge");

const STORAGE_KEY = "jobfit:last-profile";

/* ---------- UI 상태 전환 헬퍼 ---------- */

/** 모든 영역을 숨기고 로딩만 보여준다. */
function showLoading() {
  initialHint.hidden = true;
  resultsSection.hidden = true;
  loadingSection.hidden = false;
  hideAlert();
  showSkeletons(loadingSkeletons, 4);
}

/** 로딩을 끝내고 결과를 보여준다. */
function showResults() {
  loadingSection.hidden = true;
  resultsSection.hidden = false;
}

/** 안내 메시지를 표시한다. (실패 처리 UX) */
function showAlert(message) {
  alertText.textContent = message;
  alertBox.hidden = false;
  alertBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function hideAlert() {
  alertBox.hidden = true;
}

/** 필수 입력값 중 비어 있는 필드에 테두리를 표시한다. */
function markFieldError(fieldId, hasError) {
  const el = document.getElementById(fieldId);
  if (el) el.classList.toggle("has-error", hasError);
}

/* ---------- 폼 값 읽기 ---------- */

function readProfile() {
  return {
    role: document.getElementById("role").value,
    skills: document.getElementById("skills").value,
    level: document.getElementById("level").value,
    min_salary: document.getElementById("min_salary").value,
    summary: document.getElementById("summary").value,
    top_n: document.getElementById("top_n").value,
  };
}

/**
 * 빈 입력 검사 (실패 처리 1).
 * 서버에도 같은 검사가 있지만, 화면에서 먼저 잡아주는 편이 훨씬 빠르고 UX가 좋습니다.
 */
function validate(profile) {
  const missing = [];
  if (!profile.role && !profile.skills.trim()) {
    missing.push("희망 직무 또는 기술스택");
  }

  if (missing.length > 0) {
    markFieldError("role", !profile.role);
    markFieldError("skills", !profile.skills.trim());
    showAlert(
      missing.join(" 또는 ") + "을(를) 입력해 주세요. 추천을 위한 최소 조건입니다."
    );
    return false;
  }

  markFieldError("role", false);
  markFieldError("skills", false);

  // 급여는 숫자만 받는 칸이지만, 혹시 잘못된 값이 들어오면 걸러낸다.
  if (profile.min_salary && Number(profile.min_salary) < 0) {
    markFieldError("min_salary", true);
    showAlert("희망 금여는 0 이상의 숫자로 입력해 주세요.");
    return false;
  }
  markFieldError("min_salary", false);

  return true;
}

/* ---------- 결과 렌더링 ---------- */

function renderResults(data) {
  const results = data.results || [];

  if (results.length === 0) {
    showEmptyState(
      resultsBox,
      "추천할 공고를 찾지 못했습니다",
      "조건을 조금 더 넓게 입력해 보세요. 기술스택에서 너무 구체적인 단어를 빼면 결과가 나올 수 있습니다."
    );
    return;
  }

  resultsSub.textContent =
    "전체 " + data.total_jobs + "건 중 " + results.length +
    "건을 추천합니다 · AI 판단 " + results.filter((r) => r.ai_used).length + "건";

  resultsBox.innerHTML = results
    .map((item) => {
      const job = item.job;

      // AI 가 붙여준 추가 설명 (근거 / 아쉬운 점 / 다음 행동)
      const aiBlock =
        '<div style="border-top:1px solid var(--border);padding-top:12px;margin-top:4px;">' +
          '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px;">' +
            '<span class="ai-note' + (item.ai_used ? "" : " ai-note--off") + '">' +
              (item.ai_used ? "AI 분석" : "코드 분석") +
            "</span>" +
            '<span class="badge">' + escapeHtml(scoreLabel(item.match_score)) + "</span>" +
          "</div>" +
          '<ul class="reason-list">' +
            (item.reasons || [])
              .slice(0, 3)
              .map((reason) => "<li>" + escapeHtml(reason) + "</li>")
              .join("") +
          "</ul>" +
          (item.concern
            ? '<p style="margin:8px 0 0;font-size:0.87rem;color:var(--warn);">⚠ 아쉬운 점: ' +
              escapeHtml(item.concern) + "</p>"
            : "") +
          (item.action
            ? '<p style="margin:6px 0 0;font-size:0.87rem;color:var(--accent);">→ 제안: ' +
              escapeHtml(item.action) + "</p>"
            : "") +
        "</div>";

      return renderJobCard(job, {
        score: item.match_score,
        extraHtml: aiBlock,
      });
    })
    .join("");

  // 결과 영역이 보일 때 스크롤을 아래로 내린다 (긴 결과가 잘리지 않도록).
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- AI 상태 배지 ---------- */

function updateAiBadge(status) {
  if (status === "ok") {
    aiBadge.hidden = false;
    aiBadge.className = "ai-note";
    aiBadge.textContent = "AI 분석 적용됨";
    aiFallbackAlert.hidden = true;
  } else if (status === "failed") {
    aiBadge.hidden = false;
    aiBadge.className = "ai-note ai-note--off";
    aiBadge.textContent = "코드 분석으로 대체됨";
    aiFallbackAlert.hidden = false;
    aiFallbackText.textContent =
      "AI 분석 요청에 실패했습니다. 아래 결과는 AI 대신 키워드 일치 기반으로 계산한 점수입니다. 잠시 후 다시 시도해 주세요.";
  } else {
    aiBadge.hidden = false;
    aiBadge.className = "ai-note ai-note--off";
    aiBadge.textContent = "AI 미연동 상태";
    aiFallbackAlert.hidden = false;
    aiFallbackText.textContent =
      "AI API 키가 설정되어 있지 않아 AI 분석 없이 키워드 매칭 점수만 표시합니다. " +
      "기능은 정상 동작합니다.";
  }
}

/* ---------- 메인 제출 핸들러 ---------- */

async function handleSubmit(event) {
  event.preventDefault();

  const profile = readProfile();

  // 1) 클라이언트 검증
  if (!validate(profile)) return;

  // 2) 로딩 상태로 전환하고 버튼 비활성화 (중복 전송 방지)
  showLoading();
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span> 분석 중';

  try {
    // 3) 서버에 요청. 이 한 줄이 프론트 → 백엔드 연결 지점이다.
    const data = await fetchRecommendations(profile);

    // 4) 결과 표시
    updateAiBadge(data.ai_status);
    renderResults(data);
    showResults();

    // 5) 다음 방문 때 재입력하지 않도록 조건을 저장
    store.set(STORAGE_KEY, profile);

  } catch (error) {
    // 5-1) 실패 처리: 400(입력) / 404(결과없음) / 5xx / 타임아웃을
    //      서버가 보낸 메시지 그대로 사용자에게 보여준다.
    showResults();
    showEmptyState(
      resultsBox,
      error.isTimeout ? "응답 시간이 초과되었습니다" : "추천을 완료하지 못했습니다",
      error.message
    );
    showAlert(error.message);
    updateAiBadge("failed");

  } finally {
    // 성공/실패와 상관없이 버튼을 반드시 복구한다.
    submitBtn.disabled = false;
    submitBtn.textContent = "추천 받기";
  }
}

/* ---------- 초기화 ---------- */

function restoreLastProfile() {
  const saved = store.get(STORAGE_KEY);
  if (!saved) return;

  const roleEl = document.getElementById("role");
  const levelEl = document.getElementById("level");
  const topNEl = document.getElementById("top_n");

  // 저장된 값이 현재 옵션 목록에 없으면 넣지 않는다 (오류 방지).
  const hasOption = (select, value) =>
    !value || Array.from(select.options).some((o) => o.value === value);

  if (hasOption(roleEl, saved.role)) roleEl.value = saved.role;
  if (hasOption(levelEl, saved.level)) levelEl.value = saved.level;
  if (hasOption(topNEl, saved.top_n)) topNEl.value = saved.top_n;

  document.getElementById("skills").value = saved.skills || "";
  document.getElementById("min_salary").value = saved.min_salary || "";
  document.getElementById("summary").value = saved.summary || "";
}

function handleReset() {
  form.reset();
  store.set(STORAGE_KEY, null);
  ["role", "skills", "min_salary"].forEach((id) => markFieldError(id, false));
  hideAlert();
  aiFallbackAlert.hidden = true;
  aiBadge.hidden = true;
  resultsSection.hidden = true;
  loadingSection.hidden = true;
  initialHint.hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ---------- 이벤트 연결 ---------- */

form.addEventListener("submit", handleSubmit);
resetBtn.addEventListener("click", handleReset);

document.addEventListener("DOMContentLoaded", restoreLastProfile);
