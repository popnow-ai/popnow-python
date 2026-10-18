"""A minimal task-callback receiver using only the standard library.

Run it behind a public HTTPS URL (for example a tunnel while developing) and
pass that URL as callback_url when you create a task:

    export POPNOW_WEBHOOK_SECRET="..."   # API console > Webhooks
    python examples/webhook_receiver.py
"""

import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from popnow import WebhookVerificationError, webhooks

SECRET = os.environ["POPNOW_WEBHOOK_SECRET"]
seen_deliveries = set()  # use a database with a unique index in production


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            event = webhooks.verify_task_callback(raw, dict(self.headers), SECRET)
        except WebhookVerificationError:
            self.send_response(401)
            self.end_headers()
            return

        # Acknowledge quickly; retries reuse the same request_id.
        self.send_response(200)
        self.end_headers()
        if event["request_id"] in seen_deliveries:
            return
        seen_deliveries.add(event["request_id"])

        task = webhooks.task_from_event(event)
        print(task.task_id, task.state, task.error_code or "", task.urls)


HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
