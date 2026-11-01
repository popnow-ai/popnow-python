"""Show the USD price first, then lock it in and run the task.

    python examples/quote_and_create.py

Amounts are exact USD decimal strings. Compare them with decimal.Decimal, never float.
"""

from decimal import Decimal

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
print(f"This clip costs about ${quote.expected_charge_usd}, at most ${quote.max_charge_usd}.")
print(f"Your API balance: ${balance.available_usd}.")
if Decimal(balance.available_usd or "0") < Decimal(quote.max_charge_usd or "0"):
    raise SystemExit("Add funds at https://popnow.ai/api/console/billing first.")

# Create the key once per piece of work and reuse it on every retry.
key = new_idempotency_key()
try:
    created = client.jobs.create(
        model=MODEL,
        input=INPUT,
        quote_id=quote.quote_id,
        expected_cost_usd=quote.max_charge_usd,  # the exact USD hold you showed
        idempotency_key=key,
    )
except QuoteMismatchError:
    raise SystemExit("The price changed or the quote expired; quote again.")

print("accepted", created.task_id, "holding", created.estimated_cost_usd, "USD")
task = client.jobs.wait(created, timeout=1800)
# Once settled, cost_usd is the final charge (never above the hold); failed tasks cost nothing.
print(task.state, task.cost_usd, "USD", task.urls)
