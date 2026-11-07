# Outcome Document Extraction Service

**Role: Software Developer**

Initial milestone: HTTP contract, PostgreSQL-backed job intake and idempotent submission. Background processing and extraction are the next milestones.

## Run

1. Copy `.env.example` to `.env` and set a valid, rotated `LLM_API_KEY`.
2. Run `docker compose up --build`.
3. Check `http://localhost:8080/health`.

## API

- `GET /health`
- `POST /jobs` — multipart fields `file`, `schema`, optional `webhook_url`.
- `GET /jobs/{job_id}`

## Sample validation

Once outputs are generated:

```bash
python tools/validate.py outputs/ --schema-dir sample/schemas --truth-dir sample/sample-data-output-validated
```

## Implementation checklist

- [x] Required HTTP routes
- [x] PostgreSQL-backed job records
- [x] File type, size and schema validation
- [x] Organization-scoped job reads
- [x] Content/schema idempotency
- [ ] Background workers and crash recovery
- [ ] PDF/DOCX/XLSX/CSV parsing
- [ ] LLM extraction and output validation
- [ ] Webhook delivery
- [ ] Sample-set evaluation
