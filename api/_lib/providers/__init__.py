"""
공공 모듈 마커 파일.

`api/_lib` 안의 파일들이 서로를 `import` 할 수 있도록 패키지 표시를 해 둔다.
Vercel은 `api/` 아래의 모든 파일을 하나의 진입점으로 보지 않고,
`api/*.py` 만 엔드포인트로 취급한다. 따라서 `_lib` 과 `providers` 는
엔드포인트가 아니라 내부 코드다( 밑줄로 시작하는 폴더는 Vercel이 무시한다 ).
"""

# 이 파일은 비워 두되, 프로바이더 목록을 한 곳에서 관리한다.
PROVIDERS = ["remoteok", "remotive", "arbeitnow"]

__all__ = ["PROVIDERS"]
