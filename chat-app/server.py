#!/usr/bin/env python3
"""Server kecil untuk demo chatbot Knowledge Base (Python standar, tanpa pip install).

- Menyajikan index.html.
- GET  /api/bots        -> daftar chatbot (tanpa API key).
- POST /api/ask/<id>    -> diteruskan ke API Gateway: POST {gateway_url}/api/v1/gateway/ask/<path>
                           dengan header `apikey` milik chatbot tsb.

API key hanya ada di server (config.json), tidak pernah dikirim ke browser.

Jalankan:  python3 server.py            (buka http://localhost:8765)
           python3 server.py --port 9000 --config config.json
"""
import argparse
import json
import pathlib
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve().parent


def load_config(path: pathlib.Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    config["gateway_url"] = config["gateway_url"].rstrip("/")
    return config


class Handler(BaseHTTPRequestHandler):
    config: dict = {}

    def _send_json(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            data = (HERE / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/api/bots":
            bots = [{k: bot.get(k, "") for k in ("id", "label", "description")} for bot in self.config["bots"]]
            self._send_json(200, {"bots": bots})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if not self.path.startswith("/api/ask/"):
            self._send_json(404, {"error": "Not found"})
            return
        bot_id = self.path.removeprefix("/api/ask/")
        bot = next((b for b in self.config["bots"] if b["id"] == bot_id), None)
        if bot is None:
            self._send_json(404, {"error": f"Chatbot '{bot_id}' tidak ada di config"})
            return
        try:
            question = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))["question"]
        except (ValueError, KeyError):
            self._send_json(400, {"error": "Body harus berisi {\"question\": \"...\"}"})
            return

        request = urllib.request.Request(
            f"{self.config['gateway_url']}/api/v1/gateway/ask/{bot['path']}",
            data=json.dumps({"question": question}).encode("utf-8"),
            headers={"Content-Type": "application/json", "apikey": bot["apikey"]},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                self._send_json(200, json.loads(response.read())["data"])
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail)["error"]["message"]
            except (ValueError, KeyError, TypeError):
                pass
            self._send_json(exc.code, {"error": f"Gateway menolak ({exc.code}): {detail}"})
        except (urllib.error.URLError, TimeoutError) as exc:
            self._send_json(502, {"error": f"Gateway tidak bisa dihubungi: {exc}"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config", default=str(HERE / "config.json"))
    args = parser.parse_args()
    Handler.config = load_config(pathlib.Path(args.config))
    print(f"Chatbot demo: http://localhost:{args.port}  ({len(Handler.config['bots'])} chatbot)")
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
