import http.server
import socketserver
import os
import sys

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PORT = 8080
DIRECTORY = os.path.join(os.path.dirname(__file__), "dashboard")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)


def main():
    if not os.path.exists(DIRECTORY):
        print(f"디렉토리가 존재하지 않습니다: {DIRECTORY}")
        sys.exit(1)

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"==================================================")
        print(f"🚀 GA4 대시보드 로컬 서버가 시작되었습니다!")
        print(f"👉 접속 URL: http://localhost:{PORT}")
        print(f"종료하려면 Ctrl+C를 누르세요.")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n서버를 종료합니다.")


if __name__ == "__main__":
    main()
