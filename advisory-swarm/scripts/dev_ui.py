"""Temporary dev UI for the financial_advisor specialist — NOT the real web/index.html.

Stdlib only (no Flask/FastAPI), so it has zero extra dependencies beyond `anthropic`. Lets you
type a scenario, run a draft, and run a rebuttal against a pasted counterpart quote, and see the
tool-call activity log alongside the structured JSON output. Talks to the live API using
ANTHROPIC_API_KEY from advisory-swarm/.env or the environment.

Usage: python scripts/dev_ui.py   then open http://localhost:8765
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from specialist_runner import run_draft, run_rebuttal  # noqa: E402

PORT = 8765

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>financial_advisor — dev harness</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1 { font-size: 1.2rem; } h2 { font-size: 1rem; margin-top: 2.5rem; }
  textarea, input { width: 100%; box-sizing: border-box; font-family: inherit; font-size: 0.9rem; padding: 0.5rem; }
  textarea { height: 4.5rem; }
  button { margin-top: 0.5rem; padding: 0.5rem 1rem; cursor: pointer; }
  pre { background: #f4f4f4; padding: 0.75rem; overflow-x: auto; font-size: 0.8rem; white-space: pre-wrap; }
  .tool-log { color: #555; font-size: 0.8rem; }
  .badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 3px; font-size: 0.75rem; margin-left: 0.5rem; }
  .hold { background: #fde68a; } .concede { background: #bbf7d0; } .qualify { background: #bfdbfe; }
  .loading { opacity: 0.5; }
  .error { color: #b91c1c; white-space: pre-wrap; }
</style>
</head>
<body>
<h1>financial_advisor — dev harness (temp, not the real UI)</h1>

<h2>Draft mode</h2>
<textarea id="scenario">Client scenario: significant concentration in a single pre-IPO employer-stock grant. Pull the portfolio and market assumptions, then give your recommendation.</textarea>
<button onclick="runDraft()">Run draft</button>
<div id="draft-out"></div>

<h2>Rebuttal mode (quoted span only, no full draft)</h2>
<input id="question" value="Should the client begin selling the concentrated position now, or wait for the QSBS date?">
<textarea id="quote">Selling any portion of the position before 2027-03-01 forfeits the QSBS exclusion on approximately $2.22M of gain, so the client should hold until the date passes.</textarea>
<button onclick="runRebuttal()">Run rebuttal</button>
<div id="rebuttal-out"></div>

<script>
async function post(path, body, outEl) {
  outEl.innerHTML = '<p class="loading">running...</p>';
  try {
    const res = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const data = await res.json();
    if (!res.ok) { outEl.innerHTML = '<pre class="error">' + (data.error || res.statusText) + '</pre>'; return data; }
    return data;
  } catch (e) {
    outEl.innerHTML = '<pre class="error">' + e + '</pre>';
    throw e;
  }
}

function renderToolLog(calls) {
  if (!calls || !calls.length) return '<p class="tool-log">(no tool calls)</p>';
  return '<p class="tool-log">' + calls.map(c => c.tool + '(' + JSON.stringify(c.input) + ')').join('<br>') + '</p>';
}

async function runDraft() {
  const out = document.getElementById('draft-out');
  const data = await post('/api/draft', {scenario: document.getElementById('scenario').value}, out);
  if (!data || data.error) return;
  out.innerHTML = renderToolLog(data.tool_calls) + '<pre>' + JSON.stringify(data.draft, null, 2) + '</pre>';
}

async function runRebuttal() {
  const out = document.getElementById('rebuttal-out');
  const data = await post('/api/rebuttal', {
    question: document.getElementById('question').value,
    quote: document.getElementById('quote').value,
  }, out);
  if (!data || data.error) return;
  const pos = data.rebuttal.position;
  out.innerHTML = renderToolLog(data.tool_calls) + '<span class="badge ' + pos + '">' + pos + '</span>' +
    '<pre>' + JSON.stringify(data.rebuttal, null, 2) + '</pre>';
}
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/draft":
                tool_log = []
                draft = run_draft(payload["scenario"], tool_log=tool_log)
                self._send_json({"draft": draft, "tool_calls": tool_log})
            elif self.path == "/api/rebuttal":
                tool_log = []
                rebuttal = run_rebuttal(payload["question"], payload["quote"], tool_log=tool_log)
                self._send_json({"rebuttal": rebuttal, "tool_calls": tool_log})
            else:
                self._send_json({"error": "not found"}, 404)
        except Exception as exc:  # dev tool — surface the error in the browser instead of a 500 page
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def log_message(self, fmt, *args):
        print("  " + (fmt % args))


def main():
    print(f"financial_advisor dev UI: http://localhost:{PORT}")
    ThreadingHTTPServer(("localhost", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
