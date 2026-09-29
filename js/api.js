/* ==========================================================================
   api.js — 백엔드 통신 전담 모듈
   프론트엔드에서 fetch 를 직접 쓰면 페이지마다 중복 코드가 생기므로,
   '서버에 요청 보내기' 를 이 파일 한 곳에 모았다.

   특히 중요한 것: TIMEOUT.
   fetch 는 기본적으로 시간이 끝나도 요청을 취소하지 않는다.
   사용자는 몇 분을 그냥 기다려야 할 수도 있다.
   그래서 AbortController 로 제한 시간을 강제하고,
   사용자에게 '응답이 늦고 있습니다' 라고 알린다. (과제 요구사항: 지연/타임아웃 처리)
   ========================================================================== */

/** 요청이 이 시간(밀리초) 안에 끝나지 않으면 중단하고 오류로 처리한다. */
const TIMEOUT_MS = 20000;

const API_BASE = ""; // 같은 도메인의 /api 를 쓴다. 배포 시 자동 매칭된다.

/**
 * 서버가 보낸 오류 응답에서 사람이 읽을 메시지를 뽑는다.
 * 백엔드는 {"error": "..."} 형태로 메시지를 보내도록 맞춰져 있다.
 */
function extractMessage(payload, fallback) {
  if (payload && typeof payload.error === "string" && payload.error) {
    return payload.error;
  }
  return fallback;
}

/**
 * 상태 코드(HTTP code)에 따라 적절한 문구를 만든다.
 * 서버가 detailed message 를 줬으면 그걸 우선 사용한다.
 */
function describeError(status, payload) {
  const serverMessage = extractMessage(payload, null);
  if (serverMessage) return serverMessage;

  if (status === 404) return "요청하신 정보를 찾을 수 없습니다.";
  if (status === 405) return "지원하지 않는 요청 방식입니다.";
  if (status === 429) return "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.";
  if (status >= 500) return "서버에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.";
  if (status === 0) return "서버에 연결하지 못했습니다. 네트워크 상태를 확인해 주세요.";
  return "알 수 없는 오류가 발생했습니다. (HTTP " + status + ")";
}

/**
 * 타임아웃을 강제하는 fetch 래퍼.
 *
 * @param {string} path        - 예: "/api/recommend"
 * @param {object} options     - { method, body, timeout }
 * @returns {Promise<object>}  파싱된 JSON
 * @throws  {Error} message 가 사용자용 한국어 메시지를 담은 에러
 */
async function request(path, options = {}) {
  const timeout = options.timeout || TIMEOUT_MS;

  // AbortController = "이 시간이 지나면 취소해라" 라는 신호를 만든다.
  const controller = new AbortController();
  const timerId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(API_BASE + path, {
      method: options.method || "GET",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });

    // 응답 본문이 JSON 이 아닐 수도 있으므로 안전하게 파싱한다.
    let payload = null;
    try {
      payload = await response.json();
    } catch (parseError) {
      payload = null;
    }

    if (!response.ok) {
      const error = new Error(describeError(response.status, payload));
      error.status = response.status;
      error.isTimeout = false;
      throw error;
    }

    if (!payload) {
      const error = new Error("서버 응답을 해석하지 못했습니다.");
      error.status = response.status;
      throw error;
    }

    return payload;

  } catch (error) {
    // abort = 사용자가 기다리다 만료(타임아웃). 다른 오류와 구분해 메시지를 바꾼다.
    if (error.name === "AbortError") {
      const timeoutError = new Error(
        "응답이 너무 오래 걸려 요청을 중단했습니다. 원천 서버가 느린 상황일 수 있습니다. 잠시 후 다시 시도해 주세요."
      );
      timeoutError.isTimeout = true;
      throw timeoutError;
    }
    // 이미 한국어 메시지를 가진 에러(위에서 만든 것)는 그대로 통과시킨다.
    if (error.status !== undefined) throw error;

    const networkError = new Error(
      "서버에 연결하지 못했습니다. 네트워크 상태를 확인해 주세요."
    );
    networkError.isNetwork = true;
    throw networkError;

  } finally {
    // 성공/실패와 관계없이 타이머는 반드시 정리한다(메모리 누수 방지).
    clearTimeout(timerId);
  }
}

/* ---------- 실제 API 호출 함수들 ---------- */

/**
 * 공고 목록을 가져온다.
 * @param {number} limit - 최대 몇 건 받을지
 * @param {boolean} refresh - true 면 서버 캐시를 무시하고 새로 수집
 */
function fetchJobs(limit = 60, refresh = false) {
  const query = "?limit=" + encodeURIComponent(limit) + (refresh ? "&refresh=1" : "");
  return request("/api/jobs" + query);
}

/**
 * AI 맞춤 추천을 요청한다.
 * @param {object} profile - { role, skills, level, min_salary, summary, top_n }
 */
function fetchRecommendations(profile) {
  return request("/api/recommend", {
    method: "POST",
    body: profile,
    // AI 호출이 포함되므로 다른 요청보다 여유를 준다.
    timeout: 45000,
  });
}
