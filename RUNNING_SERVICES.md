# ImForensic --- Running Services & Local Development Guide

This document contains the local URLs, startup commands, testing
instructions, and current development status of ImForensic services.

It is intended to help developers run the project locally, verify
available endpoints, troubleshoot common issues, and document new
services as they become operational.

**Important:** These instructions describe the current local
development setup. A service is considered working only after its
endpoints have been tested successfully.

---

## 1. Project Directory

The current project is located at:

```text

C:\Users{=tex}\Administrator{=tex}\Downloads{=tex}\ImForensic{=tex}-VSCode-Starter\ImForensic{=tex}

```

The relevant directory structure is:

```text

ImForensic/

├── frontend/

├── backend/

│   ├── api-gateway/

│   │   ├── app/

│   │   │   ├── main.py

│   │   │   ├── routes/

│   │   │   │   └── upload.py

│   │   │   └── services/

│   │   │       └── storage.py

│   │   ├── temp_uploads/

│   │   └── .venv/

│   ├── orchestrator/

│   └── services/

│       └── metadata-provenance/

│           ├── app/

│           │   ├── main.py

│           │   ├── analyzer.py

│           │   └── __init__.py

│           └── requirements.txt

├── infrastructure/

├── database/

├── scripts/

├── tests/

├── docs/

├── README.md

└── RUNNING_SERVICES.md

```

The structure above is a guide to the relevant project files. Some
directories may not contain a running or completed implementation yet.

---

**## Prerequisites

Install the tools required for the services you intend to run:
- Python 3.12 for the current backend development environment.
- Node.js and npm for the React/Vite frontend.
- Git for source control.
- Docker Desktop and Docker Compose when working on containerized
  infrastructure.
Verify Python and Node.js installations:
python --version
node --version
npm --version
The current backend setup uses backend/api-gateway/.venv for both
backend services. This is a development convenience; separate service
environments may be introduced later.
2. Local Services and Running Links**
All URLs below use `127.0.0.1`, which refers to the developer's own
computer. Other developers must start the services on their own machines
to use these URLs.

### 2.1 API Gateway

| Property | Value |

|---|---|

| Service | API Gateway |

| Framework | FastAPI |

| Port | `8000` |

| Base URL | `http://127.0.0.1:8000\` |

| Health check | http://127.0.0.1:8000/health |

| Swagger UI | http://127.0.0.1:8000/docs |

| ReDoc | http://127.0.0.1:8000/redoc |

| Upload endpoint | `POST /api/v1/analyses` |

| Status | Upload and temporary storage tested successfully; metadata
integration needs verification |

#### Start the API Gateway

Open a terminal in VS Code and run:

```powershell

cd
C:\Users{=tex}\Administrator{=tex}\Downloads{=tex}\ImForensic{=tex}-VSCode-Starter\ImForensic{=tex}\backend{=tex}\api{=tex}-gateway

```

Activate the existing virtual environment:

```powershell

.\.venv\Scripts{=tex}\Activate{=tex}.ps1

```

Install the HTTP client dependency if needed:

```powershell

python -m pip install httpx

```

Start the service:

```powershell

python -m uvicorn app.main:app --reload --port 8000

```

Keep this terminal open while using the gateway.

#### Test the API Gateway

Open:

- Health check: http://127.0.0.1:8000/health

- API documentation: http://127.0.0.1:8000/docs

In Swagger UI, expand `POST /api/v1/analyses`, click **Try it
out**, select a supported image, and click **Execute**.

The successful upload response should include fields such as:

- `analysis_id`

- `filename`

- `content_type`

- `size_bytes`

- `sha256`

- `status`

- `storage_ref`

- `metadata_status`

- `metadata`

A successful upload confirms that the upload workflow worked. Check
`metadata_status` separately to determine whether metadata integration
succeeded.

Uploaded files are currently stored in:

```text

backend/api-gateway/temp_uploads/

```

This is temporary local storage, not production-grade evidence storage.

---

### 2.2 Metadata & Provenance Service

| Property | Value |

|---|---|

| Service | Metadata & Provenance |

| Framework | FastAPI |

| Port | `8001` |

| Base URL | `http://127.0.0.1:8001\` |

| Health check | http://127.0.0.1:8001/health |

| Swagger UI | http://127.0.0.1:8001/docs |

| ReDoc | http://127.0.0.1:8001/redoc |

| Analysis endpoint | `POST /analyze` |

| Status | Health check and direct image analysis tested successfully
|

#### Start the Metadata Service

Open a second terminal in VS Code. The current setup uses the virtual
environment inside `backend/api-gateway/.venv`.

Run:

```powershell

cd
C:\Users{=tex}\Administrator{=tex}\Downloads{=tex}\ImForensic{=tex}-VSCode-Starter\ImForensic{=tex}\backend{=tex}\services{=tex}\metadata{=tex}-provenance

```

Activate the existing environment:

```powershell

..\..\api{=tex}-gateway\.venv\Scripts{=tex}\Activate{=tex}.ps1

```

Install the metadata service dependencies:

```powershell

python -m pip install -r requirements.txt

```

Start the service:

```powershell

python -m uvicorn app.main:app --reload --port 8001

```

Keep this terminal open while testing the service.

#### Test the Metadata Service

Open:

- Health check: http://127.0.0.1:8001/health

- API documentation: http://127.0.0.1:8001/docs

The health endpoint should return:

```json

{

  "status": "ok",

  "service": "metadata-provenance"

}

```

In Swagger UI, expand `POST /analyze`, click **Try it out**,
and provide a JSON request containing the full path to an existing
image.

Example:

```json

{

  "image_path":
"C:/path/to/ImForensic/backend/api-gateway/temp_uploads/YOUR_IMAGE_UUID.jpg"

}

```

Replace the example path with the actual path and filename on your
computer.

The response should contain image properties, the SHA-256 hash,
available EXIF metadata, embedded-information keys, and limitations.

**Security note:** This endpoint currently accepts a filesystem
path. Keep it restricted to local development; do not expose it publicly
in its current form.

---

** ### 2.3 React Frontend
  Property                            Value
  Service                             ImForensic Frontend

  Framework                           React + Vite (planned project
                                      stack; startup not yet verified)

  Expected development port           5173

  Expected local URL                  http://localhost:5173

  Status                              Startup and API integration not yet
                                  verified
Prerequisites
Install Node.js (which includes npm) and verify the installation:
node --version
npm --version
Start the Frontend
Open a new VS Code terminal and navigate to the project root:
cd C:\Users\Administrator\Downloads\ImForensic-VSCode-Starter\ImForensic
cd frontend
Confirm that package.json exists:
Get-ChildItem package.json
Install dependencies:
npm install
Check the scripts configured in package.json:
npm run
If a dev script is listed, start the development server:
npm run dev
Open the exact URL printed by the terminal. Vite commonly uses
http://localhost:5173, but it may choose another port if that port is
already occupied.
Verify the Frontend
1. Open the URL printed by Vite.
2. Confirm that the page loads.
3. Check the browser developer console for errors.
4. Test the upload interface only if it is implemented.
5. Verify the frontend API configuration before expecting it to call
   the API Gateway.
Starting the frontend does not confirm that it is integrated with the
backend. Its startup and end-to-end workflow must be tested separately.
Frontend API Configuration
Inspect the frontend code before adding environment variables. If the
application is configured to read a Vite environment variable, a local
.env file may contain:
VITE_API_BASE_URL=http://127.0.0.1:8000
Use the variable name expected by the actual frontend code. Variables
prefixed with VITE_ are exposed to browser-side code; never store
passwords, API secrets, or private credentials in them.
3. Running Both Services Together**
The API Gateway and Metadata & Provenance service run independently on
different ports. The React frontend can be started in a third terminal
if its package.json contains a dev script.

### Recommended startup sequence

1. Open VS Code and the ImForensic project.

2. Open two separate terminals.

3. Start the Metadata & Provenance service on port `8001`.

4. Start the API Gateway on port `8000`.

5. Verify both health endpoints.

6. Test metadata analysis directly.

7. Upload an image through the gateway and inspect the response.

The two terminal commands are:

**Terminal 1 --- Metadata Service**

```powershell

cd
C:\Users{=tex}\Administrator{=tex}\Downloads{=tex}\ImForensic{=tex}-VSCode-Starter\ImForensic{=tex}\backend{=tex}\services{=tex}\metadata{=tex}-provenance

..\..\api{=tex}-gateway\.venv\Scripts{=tex}\Activate{=tex}.ps1

python -m uvicorn app.main:app --reload --port 8001

```

**Terminal 2 --- API Gateway**

```powershell

cd
C:\Users{=tex}\Administrator{=tex}\Downloads{=tex}\ImForensic{=tex}-VSCode-Starter\ImForensic{=tex}\backend{=tex}\api{=tex}-gateway

.\.venv\Scripts{=tex}\Activate{=tex}.ps1

python -m uvicorn app.main:app --reload --port 8000

```

Run each sequence in its own terminal. Do not close the terminals while
you are testing the services.

---

## 4. Current Integration Status

The following distinction is important when testing the application.

| Test | Current status |

|---|---|

| Gateway health endpoint | Tested successfully |

| Upload image through Swagger UI | Tested successfully |

| Validate supported image signatures | Implemented |

| Enforce 20 MB upload limit | Implemented |

| Calculate SHA-256 hash | Tested successfully |

| Store image in `temp_uploads` | Tested successfully |

| Metadata service health endpoint | Tested successfully |

| Direct metadata analysis through Swagger UI | Tested successfully |

| Gateway automatically receives metadata results | Needs verification
|

| React frontend end-to-end workflow | Not yet verified |

| Kafka-based asynchronous workflow | Not yet verified |

| PostgreSQL persistence of analysis results | Not yet verified |

| Cloud deployment | Not yet verified |

### Known integration issue

The gateway has previously returned:

```json

{

  "metadata_status": "failed",

  "metadata": null,

  "message": "Image stored; metadata analysis failed."

}

```

At that time, the same image could be analyzed successfully by calling
the metadata service directly.

Therefore, the upload and direct metadata-analysis features work
independently, but the combined gateway-to-metadata workflow must still
be verified and corrected.

When troubleshooting this issue, check the gateway terminal for the
diagnostic message:

```text

Metadata service request failed: ...

```

Do not mark the integration as fully working until an upload through the
gateway returns `metadata_status: "completed"` and contains the
metadata result.

---

## 5. Troubleshooting

### Error: Virtual environment activation fails

Ensure you are using the correct working directory.

For the gateway:

```powershell

.\.venv\Scripts{=tex}\Activate{=tex}.ps1

```

For the metadata service, from its own directory:

```powershell

..\..\api{=tex}-gateway\.venv\Scripts{=tex}\Activate{=tex}.ps1

```

The shared virtual environment is the current development setup.
Dedicated environments may be introduced later.

### Error: `Attribute "app" not found`

Check that the service's `app/main.py` file contains a FastAPI
instance named `app`.

For example:

```python

app = FastAPI(

    title="ImForensic Metadata & Provenance Service",

    version="0.1.0",

)

```

### Error: `cannot import name 'analyze_image'`

Check that `backend/services/metadata-provenance/app/analyzer.py`
contains the function:

```python

def analyze_image(image_path: str) -> dict:

```

Save the file before restarting the service.

You can verify the import from the metadata service directory:

```powershell

python -c "from app.analyzer import analyze_image; print('Analyzer
import successful')"

```

### Error: Port already in use

Another process may already be using port `8000` or `8001`. Stop the
previous server with `Ctrl+C` in its terminal before starting it
again.

### Error: Metadata status is failed

Check that:

1. The metadata service is running on port `8001`.

2. Its `/health` endpoint responds successfully.

3. The gateway uses the expected metadata service URL.

4. The stored image path exists and is accessible to the metadata
service.

5. The gateway terminal does not report a connection error or HTTP
error.

---

## 6. Future Developer Instructions: Add Running Links Here

Every developer who starts a new service, integrates a component, or
deploys the application should update this document.

### Rules

1. Verify the service before recording it as working.

2. Add its local URL, public URL, or non-HTTP access instructions.

3. Include the health endpoint and main endpoint when applicable.

4. Record whether it is local, development, staging, or production.

5. Update the status and verification date.

6. Document known integration issues.

7. Never commit secrets, credentials, private tokens, or sensitive
connection strings.

8. Remove or update stale URLs when services move or stop being
available.

### Running Services Register

| Component | Environment | URL / Access Instructions | Status |
Last Verified |

|---|---|---|---|---|

| API Gateway | Local | `http://127.0.0.1:8000/docs\` | Upload
tested; integration needs verification | 2026-10-25 |

| Metadata & Provenance | Local | `http://127.0.0.1:8001/docs\` |
Direct analysis tested | 2026-10-25 |

| React Frontend | Local | Add URL after testing | Not verified |
--- |

| Orchestrator | Local | Add URL or startup instructions | Not
verified | --- |

| Kafka | Local / Cloud | Add safe connection instructions | Not
verified | --- |

| PostgreSQL | Local / Cloud | Add safe connection instructions |
Not verified | --- |

| Redis | Local / Cloud | Add safe connection instructions | Not
verified | --- |

| Evidence Correlation | Local / Cloud | Add URL after testing | Not
verified | --- |

| Cloud Deployment | Cloud | Add public application URL after testing
| Not verified | --- |

The dates reflect the development checkpoint documented in this guide.
Recheck the services and update the dates when verifying them again.

### Template for New Services

Copy this template whenever a new service becomes available:

```text

Service name:

Environment:

Base URL or access instructions:

Health endpoint:

Main endpoint:

Startup command:

Status:

Last verified:

Verified by:

Known issues:

Dependencies:

```

A URL should only be marked as working after a successful test. For
cloud deployments, also verify that the URL is reachable from the
intended network and does not expose development-only endpoints.

---

## 7. Related Documentation

- `PROJECT_OVERVIEW.md` --- Project overview, objectives,
architecture, and forensic engines.

- `RUNNING_SERVICES.md` --- Local startup commands, working links,
troubleshooting, and service status.

Update this file as the implementation evolves so that developers can
quickly understand what runs, how to start it, and which integrations
still need work.