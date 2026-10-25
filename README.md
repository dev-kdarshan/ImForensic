# ImForensic

**An image forensics platform for examining image metadata, provenance, and digital evidence.**

ImForensic is a modular project designed to investigate digital images through multiple forensic analysis engines. It aims to combine metadata examination, pixel-level analysis, model fingerprinting, AI-content detection, watermark detection, and visual consistency checks into a unified analysis workflow.

The project is being developed incrementally, with a focus on backend engineering, asynchronous processing, data engineering, and cloud-native architecture.

> **Development status:** ImForensic is under active development. Not all analysis engines and integrations are fully implemented or verified yet.

## Documentation

Start with the document that matches what you need:

| Document | Description |
|---|---|
| [Project Overview](PROJECT_OVERVIEW.md) | Project objectives, architecture, planned forensic engines, technology stack, and learning goals. |
| [Running Services Guide](RUNNING_SERVICES.md) | Local setup instructions, startup commands, service URLs, API documentation, testing steps, and troubleshooting. |
| [Architecture Documentation](docs/architecture.md) | Detailed system architecture and component interactions. |
| [API Specification](docs/api-specification.md) | API endpoints and request/response design. |
| [Kafka Design](docs/kafka-design.md) | Planned asynchronous messaging and event-processing design. |
| [Security Documentation](docs/security.md) | Security considerations and handling of sensitive data. |
| [Data Retention Policy](docs/data-retention.md) | Data retention and cleanup considerations. |

## Quick Start

For complete instructions, see the [Running Services Guide](RUNNING_SERVICES.md).

### Prerequisites

- Python
- Node.js and npm
- Git
- VS Code or another code editor

Docker is part of the planned development workflow for running supporting infrastructure and services.

### Start the Backend

The current local development setup includes:

- **API Gateway:** `http://127.0.0.1:8000`
- **Gateway health check:** `http://127.0.0.1:8000/health`
- **Gateway API documentation:** `http://127.0.0.1:8000/docs`
- **Metadata & Provenance service:** `http://127.0.0.1:8001`
- **Metadata service API documentation:** `http://127.0.0.1:8001/docs`

These URLs work when the corresponding services are running on your local machine.

Follow the [Running Services Guide](RUNNING_SERVICES.md) for the exact commands and testing instructions.

### Start the Frontend

The frontend is located in the `frontend/` directory and uses React with Vite.

Follow the frontend setup instructions in the [Running Services Guide](RUNNING_SERVICES.md). Frontend startup and end-to-end integration should be verified separately.

## Planned Forensic Engines

1. **Metadata & Provenance** — Examine image properties, EXIF metadata, embedded information, and file hashes.
2. **Model Fingerprinting** — Investigate potential model-related patterns and fingerprints.
3. **Pixel Forensics** — Examine image-level and pixel-level forensic indicators.
4. **AI Content Detection** — Assess signals that may indicate AI-generated or AI-modified content.
5. **Watermark Detection** — Search for supported watermark signals.
6. **Visual Consistency** — Investigate visual inconsistencies that may warrant further analysis.

These engines are intended to contribute evidence to a combined analysis. Individual signals are not definitive proof of an image's origin or authenticity.

## Technology Stack

The project uses or plans to use:

- **Frontend:** React, Vite
- **Backend APIs:** Python, FastAPI
- **Messaging:** Apache Kafka
- **Database:** PostgreSQL
- **Caching and supporting infrastructure:** Redis
- **Containerization:** Docker and Docker Compose

The implementation status varies by component. Refer to the project documentation for current capabilities and verified integrations.

## Repository Structure

```text
backend/          Backend API, orchestration, and forensic services
frontend/         React frontend
database/         Database schema and migrations
infrastructure/   Docker Compose and supporting infrastructure
docs/             Architecture, API, security, and design documentation
scripts/          Setup and maintenance scripts
tests/            Integration and end-to-end test structure
```

## Important Notes

- Image analysis results should be interpreted as evidence and indicators, not automatic proof of authenticity or manipulation.
- Missing metadata alone does not prove that an image is AI-generated or altered.
- Local development endpoints should not be exposed publicly without appropriate security controls.
- Temporary uploads and sensitive evidence should be handled carefully.
- Check the [Running Services Guide](RUNNING_SERVICES.md) for known integration limitations and current testing status.

## Getting Started

- New to the project? Read the [Project Overview](PROJECT_OVERVIEW.md).
- Want to run the application? Follow the [Running Services Guide](RUNNING_SERVICES.md).
- Want to understand the system design? Read the [Architecture Documentation](docs/architecture.md).
