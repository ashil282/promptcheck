import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class FakeLLM:
    """Tiny OpenAI-compatible server. Set .replies[prompt_substring] = text."""

    def __init__(self):
        self.replies = {}
        self.calls = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                user = body["messages"][-1]["content"]
                outer.calls.append(body)
                if user.startswith("Criteria:"):
                    text = outer.replies.get("__judge__", "PASS\nlooks fine")
                else:
                    text = next((v for k, v in outer.replies.items() if k in user), "???")
                if text == "__500__":
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b"boom")
                    return
                payload = json.dumps(
                    {
                        "choices": [{"message": {"content": text}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def llm():
    s = FakeLLM()
    yield s
    s.close()
