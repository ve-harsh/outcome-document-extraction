# Design decisions

## Role and goals

I am applying for the **Software Developer** role. The service prioritizes durable asynchronous execution, safe concurrency, idempotency, provider resilience, observability and extraction correctness.

## Architecture

The API and workers are separate processes. PostgreSQL is the durable job store and work queue. Workers claim jobs transactionally with `FOR UPDATE SKIP LOCKED`, so multiple workers can process jobs concurrently without claiming the same row. A lease allows recovery when a worker dies while processing. The API returns after persisting a job rather than waiting for extraction.

## Reliability

Submissions are deduplicated using a hash of the document bytes and canonicalized schema. Job state transitions are guarded so terminal states cannot be overwritten. Transient provider errors are retried with bounded exponential backoff and jitter; malformed model output is validated and retried or marked partial/failed with useful logs.

## Extraction and model strategy

All model traffic uses the OpenAI-compatible gateway configured by `LLM_BASE_URL` and `LLM_API_KEY`. Only models listed in the assignment brief will be used. Model selection, actual usage and cost will be recorded after evaluation.

## Tradeoffs and follow-up

The implementation favors a small number of understandable services over unnecessary infrastructure. Further work would include richer tracing, adaptive model routing, stronger document-layout handling and load testing at larger worker counts.

## Evaluation results

Pending implementation and sample validation.
