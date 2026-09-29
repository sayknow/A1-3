/* ==========================================================================
   jobs.js — 공고 목록 페이지 전용 스크립트

   이 페이지는 AI 없이 "데이터 수집 + 필터링" 만 보여주는 페이지다.
   recommend.js 와의 차이점이 과제 설명에서 비교하기 좋은 부분이다.
   ========================================================================== */

/** 서버에서 받아 온 공고 전체를 메모리에 보관한다. */
let allJobs = [];
let filteredJobs = [];

const listBox = document.getElementById("job-list");
const listMeta = document.getElementById("list-meta");
const searchInput = document.getElementById("search");
const sourceFilter = document.getElementById("source-filter");
const sortSelect = document.getElementById("sort");
const refreshBtn = document.getElementById("refresh-btn");
const alertBox = document.getElementById("jobs-alert");
const alertText = document.getElementById("jobs-alert-text");

/* ---------- 안내 메시지 ---------- */

function showAlert(message) {
  alertText.textContent = message;
  alertBox.hidden = false;
}

function hideAlert() {
  alertBox.hidden = true;
}

/* ---------- 필터링과 정렬 ---------- */

/**
 * 현재 입력값에 맞게 공고를 걸러내고 정렬한다.
 * 필터링은 서버가 아니라 브라우저에서 한다.
 * → 공고 100건 내외의 데이터로는 충분하고, 페이지 이동도 즉시 이뤄진다.
 */
function applyFilters() {
  const keyword = searchInput.value.trim().toLowerCase();
  const source = sourceFilter.value;
  const sort = sortSelect.value;

  filteredJobs = allJobs.filter((job) => {
    // 출처 필터
    if (source && job.source !== source) return false;

    // 키워드 검색: 제목 + 회사 + 태그 + 설명을 함께 본다.
    if (keyword) {
      const haystack = [
        job.title, job.company, job.location,
        (job.tags || []).join(" "),
        job.description,
      ].join(" ").toLowerCase();

      if (!haystack.includes(keyword)) return false;
    }
    return true;
  });

  // 정렬
  if (sort === "salary") {
    filteredJobs.sort((a, b) => (b.salary_max || 0) - (a.salary_max || 0));
  } else if (sort === "company") {
    filteredJobs.sort((a, b) => a.company.localeCompare(b.company));
  } else {
    // 최신순: 서버에서 이미 내림차순으로 정렬해 보냈지만, 안전하게 다시 정렬한다.
    filteredJobs.sort((a, b) => (b.posted_at || "").localeCompare(a.posted_at || ""));
  }

  render();
}

/* ---------- 렌더링 ---------- */

function render() {
  if (filteredJobs.length === 0) {
    showEmptyState(
      listBox,
      "조건에 맞는 공고가 없습니다",
      "검색어를 줄이거나 출처 필터를 '전체'로 바꿔 보세요."
    );
    listMeta.textContent = "0건";
    return;
  }

  listBox.innerHTML = filteredJobs.map((job) => renderJobCard(job)).join("");
  listMeta.textContent = "전체 " + allJobs.length + "건 중 " + filteredJobs.length + "건 표시";
}

/* ---------- 출처 필터 옵션 만들기 ---------- */

function buildSourceOptions(sources) {
  const names = Object.keys(sources || {}).sort();
  names.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name + " (" + sources[name] + "건)";
    sourceFilter.appendChild(option);
  });
}

/* ---------- 메인 로딩 ---------- */

async function loadJobs(options = {}) {
  const refresh = options.refresh === true;

  refreshBtn.disabled = true;
  refreshBtn.innerHTML = '<span class="spinner"></span> 불러오는 중';
  hideAlert();
  showSkeletons(listBox, 6);
  listMeta.textContent = "불러오는 중…";

  try {
    const data = await fetchJobs(120, refresh);

    allJobs = data.jobs || [];

    // 출처 옵션은 최초 1회만 만든다 (새로고침 시 중복 방지)
    if (sourceFilter.options.length === 1) {
      buildSourceOptions(data.sources);
    }

    const collectedText = data.collected_at
      ? new Date(data.collected_at).toISOString().replace("T", " ").slice(0, 16) + " UTC 수집"
      : "";

    applyFilters();

    if (collectedText) {
      listMeta.textContent += " · " + collectedText;
    }

  } catch (error) {
    // 실패 처리: 타임아웃이면 그 사실부터 알려주고, 서버 메시지를 덧붙인다.
    const title = error.isTimeout ? "불러오기 시간이 초과되었습니다" : "공고를 불러오지 못했습니다";
    showEmptyState(listBox, title, error.message);
    listMeta.textContent = "0건";
    showAlert(error.message);

  } finally {
    refreshBtn.disabled = false;
    refreshBtn.textContent = "최신으로 새로고침";
  }
}

/* ---------- 이벤트 ---------- */

// 검색어 입력 시 바로 반응한다. 디바운스로 입력마다 API를 다시 부르지 않는다.
let debounceTimer = null;
searchInput.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(applyFilters, 180);
});

sourceFilter.addEventListener("change", applyFilters);
sortSelect.addEventListener("change", applyFilters);
refreshBtn.addEventListener("click", () => loadJobs({ refresh: true }));

document.addEventListener("DOMContentLoaded", () => loadJobs());
