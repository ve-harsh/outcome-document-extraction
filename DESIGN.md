# Design decisions

## Role and goals

Role: **Software Developer**. The service prioritizes durable asynchronous execution, safe concurrency, idempotency, provider resilience, observability and extraction correctness.

## Initial architecture

FastAPI exposes the fixed HTTP contract. PostgreSQL stores job state, schema and metadata; uploaded document bytes are stored on a shared Docker volume. The API returns HTTP 202 after persisting a job rather than waiting for extraction. A separate worker service will claim work transactionally with `FOR UPDATE SKIP LOCKED` and use leases to recover work after crashes.

## Initial reliability decisions

- Identical document bytes + canonical schema are deduplicated within an organization.
- Job reads are scoped by `X-Organization-Id`.
- LLM credentials are read from `LLM_BASE_URL` and `LLM_API_KEY`; no key is stored in source control.
- Terminal states will be guarded in the worker implementation.

## Tradeoffs and remaining work

This first milestone establishes intake and persistence only; jobs remain PENDING until the worker pipeline is implemented. Remaining work includes lease-based workers, document parsing, allowed-model integration, output validation, retries, webhook delivery, sample evaluation and load testing. Model choice and cost will be recorded after measured runs rather than guessed.

## Evaluation results

Pending implementation and sample validation.
