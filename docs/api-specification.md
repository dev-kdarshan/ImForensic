# API specification (planned)

- `POST /api/v1/analyses`: validate and accept an image, return `analysis_id`.
- `GET /api/v1/analyses/{analysis_id}`: return status and current findings.
- `GET /api/v1/analyses/{analysis_id}/events`: SSE progress stream.

These endpoints are planned and are not implemented by the scaffold yet.
