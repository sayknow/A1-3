/**
 * 증빙용 스크린샷 수집 스크립트.
 *
 * 과제 제출 항목 "스크린샷 (데스크톱 + 모바일 + AI 기능 동작 장면)" 을 만들기 위한 도구.
 * 서비스 코드와 무관하며, 실행에 필요하지 않은 개발 보조 스크립트입니다.
 *
 * 실행:
 *     npm i -D playwright
 *     python3 dev_server.py          # 별도 터미널에서 서버 실행
 *     node scripts/capture-screenshots.js
 *
 * 환경변수:
 *     BASE_URL  대상 서버 (기본 http://127.0.0.1:8000)
 *     OUT_DIR   저장 폴더 (기본 docs/screenshots)
 *
 * 저장 위치: docs/screenshots/
 */

const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
// 저장 위치: 기본값은 이 저장소의 docs/screenshots.
// 스크립트를 다른 위치에서 실행할 때는 OUT_DIR 로 덮어쓴다.
const OUT = process.env.OUT_DIR || path.join(__dirname, "..", "docs", "screenshots");

const VIEWPORTS = {
  desktop: { width: 1280, height: 900 },
  mobile: { width: 390, height: 844 },
};

/** 공고 API 응답이 준비될 때까지 기다린다 (외부 API 호출이므로 시간이 걸린다). */
async function waitForJobs(page, timeout = 60000) {
  await page.waitForFunction(
    () => document.querySelectorAll("#job-list .job-card").length > 0,
    { timeout }
  );
}

/** AI 추천 결과가 렌더될 때까지 기다린다. */
async function waitForResults(page, timeout = 90000) {
  await page.waitForFunction(
    () => document.querySelectorAll("#results .job-card").length > 0,
    { timeout }
  );
}

async function shoot(page, name, options = {}) {
  const file = path.join(OUT, name);
  // 공고 목록처럼 항목이 수십 개 넘으면 전체 페이지 캡처가 수 MB 까지 커지고
  // 증빙으로서 오히려 읽기 어려워지므로, 기본은 뷰포트만 캡처한다.
  await page.screenshot({
    path: file,
    fullPage: options.fullPage === true,
  });
  console.log("  saved", name);
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  // 로컬에 설치된 Chrome 을 사용한다. Playwright 전용 브라우저를
  // 별도로 설치받지 않아도 되므로 실행이 가볍다.
  const browser = await chromium.launch({ channel: "chrome" });

  // ---------- 데스크톱 ----------
  const desktop = await browser.newContext({
    viewport: VIEWPORTS.desktop,
    deviceScaleFactor: 2,
  });
  const page = await desktop.newPage();

  console.log("[1/6] 홈 (데스크톱)");
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.waitForFunction(
    () => document.querySelectorAll("#source-stats .card").length > 0,
    { timeout: 60000 }
  );
  await shoot(page, "01-home-desktop.png");

  console.log("[2/6] 공고 목록 (데스크톱)");
  await page.goto(BASE + "/jobs.html", { waitUntil: "networkidle" });
  await waitForJobs(page);
  await page.waitForTimeout(500);
  await shoot(page, "02-jobs-desktop.png");

  console.log("[3/6] AI 추천 결과 (데스크톱)");
  await page.goto(BASE + "/recommend.html", { waitUntil: "networkidle" });
  await page.selectOption("#role", "백엔드");
  await page.fill("#skills", "python, docker, aws");
  await page.selectOption("#level", "mid");
  await page.fill("#min_salary", "50000");
  await page.selectOption("#top_n", "5");
  await shoot(page, "03-recommend-form.png");
  await page.click("#submit-btn");
  await waitForResults(page);
  await page.evaluate(() =>
    document.getElementById("results-section").scrollIntoView({ block: "start" })
  );
  await page.waitForTimeout(700);
  await shoot(page, "04-recommend-result-ai.png");

  console.log("[4/6] 실패 처리 (빈 입력)");
  await page.goto(BASE + "/recommend.html", { waitUntil: "networkidle" });
  // 입력 폼을 완전히 비운다. localStorage 는 자동 복원되므로
  // 폼 필드도 함께 초기화해야 '빈 입력' 상태를 재현할 수 있다.
  await page.evaluate(() => {
    localStorage.clear();
    document.getElementById("recommend-form").reset();
  });
  await page.click("#submit-btn");
  await page.waitForSelector("#form-alert:not([hidden])", { timeout: 10000 });
  await page.waitForTimeout(400);
  await shoot(page, "05-error-empty-input.png");

  console.log("[5/6] 서비스 소개 (데스크톱)");
  await page.goto(BASE + "/about.html", { waitUntil: "networkidle" });
  await shoot(page, "06-about-desktop.png");

  // ---------- 모바일 ----------
  console.log("[6/6] 모바일 (390x844)");
  const mobile = await browser.newContext({
    viewport: VIEWPORTS.mobile,
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
  });
  const mpage = await mobile.newPage();

  await mpage.goto(BASE + "/", { waitUntil: "networkidle" });
  await mpage.waitForFunction(
    () => document.querySelectorAll("#source-stats .card").length > 0,
    { timeout: 60000 }
  );
  await shoot(mpage, "07-home-mobile.png");

  await mpage.goto(BASE + "/jobs.html", { waitUntil: "networkidle" });
  await waitForJobs(mpage);
  await mpage.waitForTimeout(500);
  await shoot(mpage, "08-jobs-mobile.png");

  await mpage.goto(BASE + "/recommend.html", { waitUntil: "networkidle" });
  await mpage.selectOption("#role", "프론트");
  await mpage.fill("#skills", "react, typescript, css");
  await mpage.selectOption("#top_n", "3");
  await mpage.click("#submit-btn");
  await waitForResults(mpage);
  await mpage.evaluate(() =>
    document.getElementById("results-section").scrollIntoView({ block: "start" })
  );
  await mpage.waitForTimeout(700);
  await shoot(mpage, "09-recommend-result-mobile.png");

  await browser.close();
  console.log("\n완료: " + OUT);
}

main().catch((error) => {
  console.error("실패:", error.message);
  process.exit(1);
});
