# ImForensic architecture

1. React frontend submits an image to the FastAPI gateway.
2. Gateway validates size and format, hashes the image, and stores it temporarily.
3. Orchestrator publishes an analysis request and dispatches engine tasks through Kafka.
4. Six independent engine services publish structured results.
5. Evidence correlation consumes results and derives a cautious overall assessment.
6. API/SSE exposes status and findings to the browser.

Kafka transports events; it does not store image bytes or replace PostgreSQL/object storage.
