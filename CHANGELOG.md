# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

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
