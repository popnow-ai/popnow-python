"""Show the price first, then lock it in and run the task.

    python examples/quote_and_create.py
"""

from popnow import PopNow, QuoteMismatchError, new_idempotency_key

MODEL = "alibaba/wan-3.0/image-to-video"
INPUT = {
    "image_url": "https://media.popnow.ai/movie/lighthouse.webp",
    "prompt": "Waves roll in slowly, the camera drifts toward the lighthouse",
    "resolution": "720p",
    "duration_seconds": 5,
}

client = PopNow()

balance = client.account.balance()
quote = client.jobs.quote(model=MODEL, input=INPUT)
print(f"This clip costs at most {quote.max_credits} credits; you have {balance.available_credits}.")

# Create the key once per piece of work and reuse it on every retry.
key = new_idempotency_key()
try:
    created = client.jobs.create(
        model=MODEL,
        input=INPUT,
        quote_id=quote.quote_id,
        expected_credits=quote.max_credits,
        idempotency_key=key,
    )
except QuoteMismatchError:
    raise SystemExit("The price changed or the quote expired; quote again.")

print("accepted", created.task_id, "holding", created.estimated_credits, "credits")
task = client.jobs.wait(created, timeout=1800)
print(task.state, task.urls)
