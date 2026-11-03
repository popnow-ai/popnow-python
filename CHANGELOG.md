# Changelog

## 0.3.0 — 2026-11-03

- Support the expanded live model catalog and embedding task outputs, including measured input usage.
- Preserve exact multimodal USD rate metadata and document native embedding/speech interfaces.


All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-11-01

The PopNow API bills in USD from a separate API balance (not popnow.ai website credits). This release moves
the SDK to the USD fields. Nothing is removed: code written for 0.1.x keeps working.

### Added

- USD fields, all exact decimal strings: `TaskQuote.max_charge_usd` and `expected_charge_usd`,
  `TaskCreated.estimated_cost_usd`, `Task.cost_usd`, `Balance.available_usd`, `held_usd` and `total_usd`,
  `Model.usd` (USD rate snapshot). When a response only has the older USD alias (`maxCharge`, `cost`,
  `available` ...), the new attribute is filled from it.
- `jobs.create(expected_cost_usd=...)` sends `expectedCostUsd`; pass `quote.max_charge_usd`. Also accepted by
  `create_and_wait()` and the `images` / `videos` / `audio` helpers. Accepts a string or `decimal.Decimal`
  (written without an exponent); a `float` raises `TypeError`.
- `InsufficientBalanceError` for code `40201`.

### Deprecated

- Credit fields, now display projections at 1 credit = $0.001: `Task.credits`, `TaskSummary.credits`,
  `TaskCreated.estimated_credits`, `TaskQuote.max_credits` and `expected_credits`,
  `Balance.available_credits`, `held_credits` and `total_credits`, `Usage.total_credits`, `UsageDay.credits`,
  `UsageModel.credits`, `Model.credits`. They still parse.
- `jobs.create(expected_credits=...)` and `jobs.create(expected_cost=...)` still send their fields but emit a
  `DeprecationWarning`; use `expected_cost_usd`.
- `InsufficientCreditsError` is now an alias of `InsufficientBalanceError` (the same class).

### Changed

- README, examples and `llms.txt` use USD: `task.cost_usd`, `quote.max_charge_usd`, `balance.available_usd`.
  The API balance is funded in API billing (https://popnow.ai/api/console/billing); prices are on
  https://popnow.ai/api/pricing.
- MCP and skills links point to the developer MCP server (`https://api.popnow.ai/api/v1/mcp`,
  https://popnow.ai/api/mcp, `popnow-ai/popnow-api-mcp`) and https://popnow.ai/api/skills.

## [0.1.0] - 2026-10-19

### Added

- `PopNow` and `AsyncPopNow` clients (`httpx`), configured by `api_key` / `POPNOW_API_KEY`,
  `base_url` / `POPNOW_BASE_URL`, `timeout`, `max_retries`, `language`, `http_client`.
- `models.list()` / `models.get()`.
- `jobs.quote()`, `create()` (idempotency key, quote lock, retention, server-side `wait`), `get()`,
  `list()` / `iter()`, `wait()` with back-off, `create_and_wait()`, `retry()`, `purge()`, `download_url()`.
- `files.upload()` (upload ticket, PUT, commit), `create_upload_url()`, `commit()`, `import_lora()`, `download()`.
- `assets.*`: list, iterate, get, save (task output, upload, URL), update, delete, usage, characters.
- `account.balance()` and `account.usage()`.
- Helpers: `images.generate()` / `edit()`, `videos.generate()`, `audio.speech()` / `music()` / `transcribe()`.
- Typed exceptions mapped from the error envelope, with `code`, `status_code`, `request_id` and `reason`.
- Automatic retries for network errors and codes `429`, `500`, `503`, `50301`, honouring `Retry-After`.
- `popnow.webhooks`: task callback (`X-Webhook-Signature`) and Standard Webhooks endpoint verification.
