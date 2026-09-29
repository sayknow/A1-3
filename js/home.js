/* ==========================================================================
   home.js — 홈(index.html) 전용 스크립트
   "데이터 출처" 영역에 실제 수집 통계를 보여준다.
   여기서 fetch 를 한 번 사용해보면, 이후 페이지에서 재사용되는 흐름이 이해된다.
   ========================================================================== */

async function loadSourceStats() {
  const container = document.getElementById("source-stats");
  if (!container) return;

  try {
    const data = await fetchJobs(30);

    const SOURCE_META = {
      RemoteOK: {
        url: "https://remoteok.com",
        note: "글로벌 원격 직군을 다루며 개발·기획 계열이 대부분. 급여 정보가 없는 공고가 많음.",
      },
      Remotive: {
        url: "https://remotive.com",
        note: "원격 직군을 폭넓게 다루며 일부 공고는 급여 범위를 함께 제공.",
      },
      Arbeitnow: {
        url: "https://www.arbeitnow.com",
        note: "유럽(주로 독일) 중심 채용 공고. 게시 시각 정보가 가장 정확함.",
      },
    };

    const counts = data.sources || {};
    const keys = Object.keys(counts);

    if (keys.length === 0) {
      showEmptyState(container, "출처 정보를 불러오지 못했습니다", "잠시 후 새로고침해 주세요.");
      return;
    }

    container.innerHTML = keys
      .map((name) => {
        const meta = SOURCE_META[name] || { url: "#", note: "" };
        return (
          '<div class="card">' +
            '<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;">' +
              "<h3 style='margin:0;'>" + escapeHtml(name) + "</h3>" +
              '<span class="badge badge--source">' + counts[name] + "건</span>" +
            "</div>" +
            '<p style="color:var(--text-dim);font-size:0.9rem;margin:10px 0;">' +
              escapeHtml(meta.note) +
            "</p>" +
            '<a href="' + escapeHtml(meta.url) + '" target="_blank" rel="noopener noreferrer">원문 보기 ↗</a>' +
          "</div>"
        );
      })
      .join("");

  } catch (error) {
    // 홈 페이지이므로 실패해도 본문을 막지 않고, 조용히 안내만 남긴다.
    showEmptyState(
      container,
      "통계를 불러오지 못했습니다",
      error.message || "잠시 후 다시 시도해 주세요."
    );
  }
}

document.addEventListener("DOMContentLoaded", loadSourceStats);
