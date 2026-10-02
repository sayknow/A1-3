#!/usr/bin/env python3
"""
로컬 개발용 서버 (Vercel 계정 없이 테스트하기 위함).

Vercel 이 배포 환경에서 어떻게 동작하는지를 로컬에서 재현한다.
    - public/ 아래 정적 파일(html/css/js) 서빙
    - /api/jobs, /api/recommend 엔드포인트 실행

엔드포인트의 실제 로직은 api/ 의 _run() 함수를 직접 호출한다.
(배포에서는 Vercel 이 같은 로직을 BaseHTTPRequestHandler 로 감싸 실행한다)

실행:
    python3 dev_server.py
브라우저에서 http://localhost:8000 접속

주의: 이 파일은 개발 편의를 위한 도구이며, 배포에는 사용되지 않습니다.
Vercel 은 이 파일 없이도 정상 동작합니다(진짜 엔드포인트는 api/ 안의 파일).
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "api"))

# 정적 파일은 public/ 아래에 있다. (Vercel 은 이 폴더를 정적 루트로 삼는다)
PUBLIC_ROOT = os.path.join(ROOT, "public")

from api.jobs import _run as jobs_run      # noqa: E402
from api.recommend import _run as recommend_run  # noqa: E402

# 포트 번호. 환경변수 이름으로 PORT 를 쓰면 호스트 환경의 PORT 와 충돌할 수 있어
# JOBFIT_PORT 라는 전용 이름을 사용한다.
PORT = int(os.environ.get("JOBFIT_PORT", 8000))

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    """요청을 받아 정적 파일 또는 API 함수로 라우팅한다."""

    def _send_json_from_handler(self, result):
        """엔드포인트가 돌려준 {statusCode, headers, body} 를 실제 HTTP 응답으로 바꾼다."""
        status = result.get("statusCode", 200)
        payload = result["body"].encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_api(self, path, query, body):
        """api/ 엔드포인트를 실행한다."""
        request = _FakeRequest(path, query, body)

        if path == "/api/jobs":
            result = jobs_run(request)
        elif path == "/api/recommend":
            result = recommend_run(request)
        else:
            self._error(404, "없는 API 경로입니다: " + path)
            return

        self._send_json_from_handler(result)

    def _serve_static(self, path):
        """정적 파일을 내려준다. 디렉터리 경로면 index.html 로 처리."""
        rel = path.lstrip("/")
        if rel == "" or rel.endswith("/"):
            rel += "index.html"

        # 디렉터리 탈출(..) 차단
        full = os.path.normpath(os.path.join(PUBLIC_ROOT, rel))
        if not full.startswith(PUBLIC_ROOT):
            self._error(403, "접근이 허용되지 않는 경로입니다.")
            return

        if not os.path.isfile(full):
            self._error(404, "파일을 찾을 수 없습니다: " + rel)
            return

        ext = os.path.splitext(full)[1].lower()
        with open(full, "rb") as file:
            content = file.read()

        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _error(self, status, message):
        body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path.startswith("/api/"):
            self._serve_api(parsed.path, query, None)
        else:
            self._serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"

        if parsed.path.startswith("/api/"):
            self._serve_api(parsed.path, parse_qs(parsed.query), body)
        else:
            self._error(404, "POST 는 /api/ 경로에서만 동작합니다.")

    def log_message(self, format, *args):
        """접근 로그를 간단히 출력한다."""
        print("  [dev] " + format % args)


class _FakeRequest:
    """
    Vercel 이 함수에 넘겨주는 request 객체를 흉내 낸다.
    실제 배포에서는 Vercel 런타임이 이 객체를 만들어 준다.
    """

    def __init__(self, path, query, body):
        self.path = path
        self.args = {key: value[0] for key, value in (query or {}).items()}
        self.body = body
        self.method = "POST" if body is not None else "GET"
        self.headers = {}


if __name__ == "__main__":
    print("=" * 52)
    print("  JobFit 로컬 개발 서버")
    print("  http://localhost:{}".format(PORT))
    print("  종료하려면 Ctrl+C 를 누르세요")
    print("=" * 52)
    HTTPServer(("", PORT), Handler).serve_forever()
