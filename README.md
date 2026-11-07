# Outcome Document Extraction Service

**Role:** Software Developer

A durable asynchronous document-extraction API for PDF, DOCX, XLSX and CSV files.

## Run

1. Copy `.env.example` to `.env` and set `LLM_API_KEY`.
2. Run `docker compose up --build`.
3. Check `http://localhost:8080/health`.

## API

- `POST /jobs` — submit a document and JSON field schema as multipart form data.
- `GET /jobs/{job_id}` — retrieve job status and, when complete, its extraction result.
- `GET /health` — liveness check.

## Sample evaluation

Scores will be added after running `tools/validate.py` against all sample outputs.
