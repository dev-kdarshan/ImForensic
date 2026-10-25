# ImForensic

## 1. What Is ImForensic?

ImForensic is a multi-engine digital image forensics platform designed to analyze suspicious images and identify potential signs of AI generation, digital manipulation, and inconsistencies in image provenance.

The platform combines multiple independent forensic engines to examine an image from different perspectives, including metadata, pixel-level characteristics, AI-generated content detection, watermarks, and visual consistency.

Instead of relying on a single detection model, ImForensic collects evidence from multiple engines and combines their findings into a structured analysis report. The report presents observations, detection results, confidence estimates where supported, and limitations to help users interpret the evidence.

The system is being developed using a microservices architecture, with asynchronous processing, containerization, and cloud deployment as key parts of the implementation.

## 2. What We Aim to Learn and Achieve

ImForensic is both a digital forensics project and a practical learning platform for cloud engineering, data engineering, and DevOps.

### Cloud Engineering

- Deploy a multi-service application on a cloud platform.
- Learn cloud networking, identity and access management, secrets management, and security fundamentals.
- Configure cloud storage for controlled image storage.
- Deploy containerized microservices using managed cloud services.
- Implement monitoring, logging, health checks, and service availability.
- Understand cloud resource management, scaling, and cost optimization.

### Data Engineering

- Understand event-driven architecture and asynchronous data processing.
- Use Apache Kafka for task distribution and result messaging.
- Design data flows between independent processing services.
- Store analysis records, metadata, and structured forensic findings in PostgreSQL.
- Learn data validation, schema design, data serialization, and message handling.
- Implement retries, idempotent processing, error handling, and dead-letter queues.
- Track analysis status and combine results from multiple data-producing services.

### DevOps and Infrastructure

- Containerize services using Docker.
- Manage multi-container environments using Docker Compose.
- Learn CI/CD pipelines for automated testing and deployment.
- Use Git and GitHub for version control and collaborative development.
- Manage environment variables, configuration, and secrets securely.
- Implement application health checks, centralized logging, and monitoring.
- Explore infrastructure automation and deployment strategies.

### Image Forensics and AI

- Extract image metadata and provenance-related information.
- Investigate pixel-level artifacts and visual inconsistencies.
- Evaluate AI-generated image detection models.
- Explore supported watermark detection and content credentials.
- Combine findings from different engines while preserving uncertainty and conflicting evidence.
- Produce structured forensic reports that distinguish observations from interpretations.

## 3. Forensic Engines

ImForensic is designed around six specialized forensic engines. Each engine performs a distinct analysis and returns structured findings that can be processed by the evidence correlation service.

### 3.1 Metadata and Provenance Engine

**Purpose**

Extract available image metadata and inspect information that may help establish an image's properties, editing history, or provenance.

**What it does**

- Extracts EXIF metadata, including camera information and capture timestamps when available.
- Identifies image format, dimensions, colour mode, and file size.
- Examines available metadata fields and embedded information.
- Looks for software tags and descriptive metadata.
- Supports future integration with Content Credentials and C2PA verification tools.

**Expected output**

- Image properties.
- Available EXIF and related metadata.
- Software and descriptive tags.
- Metadata availability indicators.
- SHA-256 hash and provenance-related observations.
- Warnings about missing or unverifiable information.

**How we will implement it**

We use Python, Pillow, and FastAPI to extract image properties and available EXIF metadata. Additional parsers and compatible provenance-verification tools can be integrated as the service evolves.

Missing metadata does not prove that an image is AI-generated, and extracted metadata is not automatically trustworthy.

### 3.2 Model Fingerprint Analysis Engine

**Purpose**

Investigate whether an image contains patterns that may be associated with particular image-generation models or model families.

**What it does**

- Examines potentially useful statistical or learned image characteristics.
- Evaluates model-specific signals when suitable reference models or validated methods are available.
- Compares observed characteristics against supported reference patterns.
- Reports uncertainty when model attribution is inconclusive.

**Expected output**

- Candidate model or model-family associations, when supported.
- Relevant fingerprint observations.
- Similarity scores or other validated measurements.
- Confidence estimates and limitations.

**How we will implement it**

We will evaluate suitable research methods, pretrained models, and reference datasets. Candidate approaches may include feature extraction, statistical analysis, and supervised classification using labelled images from known sources.

Reliable attribution requires representative training data and independent evaluation. The engine must not claim to identify a specific model when the evidence does not support that conclusion.

### 3.3 Pixel Forensics Engine

**Purpose**

Examine image-level characteristics for potential traces of editing, compositing, recompression, or other transformations.

**What it does**

- Analyzes pixel and noise characteristics.
- Investigates compression artifacts and inconsistencies.
- Examines potential differences between image regions.
- Supports error-level and related forensic techniques where appropriate.
- Identifies regions or characteristics that may warrant further examination.

**Expected output**

- Pixel-level analysis measurements.
- Potentially suspicious regions or artifact indicators.
- Visualizations or heatmaps where supported.
- Findings with limitations and relevant processing details.

**How we will implement it**

We will use Python image-processing libraries, numerical analysis tools, and selected forensic algorithms. OpenCV, NumPy, and other appropriate libraries can be introduced as individual techniques are implemented and evaluated.

Compression, resizing, and ordinary editing can also create artifacts. Therefore, these observations must be interpreted in context.

### 3.4 AI Content Detection Engine

**Purpose**

Estimate whether an image exhibits characteristics associated with AI-generated content.

**What it does**

- Runs supported AI-image detection models.
- Evaluates model outputs for the supplied image.
- Records detection scores and model information.
- Reports uncertainty and known limitations.

**Expected output**

- Detection score or probability, according to the model's actual output.
- Model identifier and version.
- Assessment category when supported by a defined threshold.
- Relevant limitations and processing status.

**How we will implement it**

We will evaluate suitable pretrained AI-image detection models and integrate them into a Python-based inference service. Model execution can be handled independently from the API gateway so that inference workloads can be scaled separately.

We will test models against suitable datasets and different image transformations. Detection scores will not be treated as definitive proof of AI generation.

### 3.5 Watermark Detection Engine

**Purpose**

Detect supported image watermarks or content-identification signals that may provide information about an image's origin.

**What it does**

- Checks for supported visible watermarks.
- Integrates compatible detectors for supported invisible watermarking schemes.
- Examines available content-identification signals.
- Records whether a supported watermark was detected or could not be evaluated.

**Expected output**

- Watermark detection status.
- Detected watermark type or scheme, when identifiable.
- Relevant extracted information, where supported.
- Verification status and limitations.

**How we will implement it**

We will integrate available watermark-detection libraries, model-specific tools, or compatible verification utilities. Each detector will support only the watermark schemes it can actually recognize.

A watermark's presence does not automatically establish authenticity, and failure to detect one does not establish that an image is original.

### 3.6 Visual Consistency Engine

**Purpose**

Examine visual relationships within an image to identify potential inconsistencies that deserve further investigation.

**What it does**

- Examines lighting and shadow relationships.
- Investigates reflections and perspective where measurable.
- Identifies potential irregularities around object boundaries.
- Uses computer vision to inspect relevant image regions.
- Supports future integration of specialized visual reasoning models.

**Expected output**

- Visual consistency observations.
- Potentially suspicious regions or relationships.
- Measurements or model outputs where supported.
- Findings with uncertainty and limitations.

**How we will implement it**

We will combine computer vision techniques with suitable pretrained models where useful. Individual checks will be developed and evaluated separately before being combined into an overall engine.

Visual inconsistencies may result from photography, perspective, lighting, editing, or image generation. They are investigative signals rather than proof of manipulation.

## 4. Project Architecture

ImForensic follows a microservices-based architecture in which image intake, forensic processing, evidence correlation, and result delivery are separated into independent components.

### 4.1 Architecture Overview

```text
                       USER / FRONTEND
                              |
                              v
                    +--------------------+
                    |    API Gateway     |
                    |      FastAPI       |
                    +--------------------+
                              |
                    Validate and hash image
                              |
                              v
                    +--------------------+
                    | Temporary / Object |
                    |      Storage       |
                    +--------------------+
                              |
                              v
                    +--------------------+
                    |   Orchestrator     |
                    | Analysis Workflow  |
                    +--------------------+
                              |
                              v
                    +--------------------+
                    |    Apache Kafka    |
                    |   Task Messages    |
                    +--------------------+
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
      +-------------+  +-------------+  +-------------+
      |  Metadata   |  | AI Content  |  |   Pixel     |
      | Provenance  |  |  Detection  |  | Forensics   |
      +-------------+  +-------------+  +-------------+
             |                |                |
             +----------------+----------------+
                              |
                    Other forensic engines
                              |
                              v
                    +--------------------+
                    | Evidence Correlation|
                    |   and Aggregation   |
                    +--------------------+
                              |
                    +---------+----------+
                    |                    |
                    v                    v
             +-------------+      +-------------+
             | PostgreSQL  |      | API Results |
             | Analysis DB |      | / Frontend  |
             +-------------+      +-------------+
```

This diagram represents the target architecture. Individual components will be integrated incrementally as development progresses.

### 4.2 API Gateway

The API gateway is the entry point for image-analysis requests.

Responsibilities include:

- Accepting image uploads.
- Enforcing file-size and supported-format restrictions.
- Checking image signatures against the declared content type.
- Generating a unique analysis ID.
- Calculating the SHA-256 hash.
- Storing the image temporarily or obtaining a controlled storage reference.
- Coordinating the analysis workflow.
- Returning analysis status and results.

The gateway should avoid performing computationally intensive forensic analysis directly. This allows individual services to be developed and scaled independently.

### 4.3 Orchestrator

The orchestrator coordinates the lifecycle of an analysis.

Responsibilities include:

- Creating analysis tasks.
- Publishing tasks to Kafka.
- Tracking the status of each engine.
- Managing timeouts, retries, and partial failures.
- Collecting references to completed results.
- Triggering evidence correlation when sufficient results are available.

The orchestrator manages the workflow rather than implementing every forensic algorithm itself.

### 4.4 Apache Kafka

Kafka provides asynchronous messaging between the orchestrator and the forensic services.

The intended workflow is:

1. The orchestrator publishes an analysis task.
2. Each eligible engine receives the task.
3. The engine obtains the image through an authorized storage reference.
4. The engine performs its analysis.
5. The engine publishes a structured result.
6. The correlation service consumes available results.

Messages should contain identifiers, task metadata, storage references, and relevant status information rather than large image payloads.

We will introduce appropriate topic design, consumer groups, message schemas, idempotent processing, bounded retries, and dead-letter handling as the pipeline is implemented.

### 4.5 Forensic Microservices

Each forensic engine runs as an independent service with a defined input and output contract.

This separation allows engines to:

- Use different libraries and machine-learning models.
- Scale according to their computational requirements.
- Fail independently without necessarily stopping the entire analysis.
- Be tested and updated separately.
- Publish structured findings for downstream processing.

FastAPI will be used for service endpoints where appropriate. Kafka consumers and producers will support asynchronous processing in the distributed workflow.

### 4.6 Evidence Correlation Service

The evidence correlation service combines the outputs from the forensic engines.

Responsibilities include:

- Collecting findings from individual engines.
- Tracking missing, failed, and completed results.
- Identifying agreement and disagreement between signals.
- Preserving the source and context of each finding.
- Producing a structured summary with appropriate uncertainty.
- Avoiding unsupported conclusions when evidence is incomplete.

The correlation logic will be developed and validated separately. It must not treat several correlated detector outputs as independent evidence without justification.

### 4.7 PostgreSQL Database

PostgreSQL will store structured application and analysis data, including:

- Analysis IDs and timestamps.
- Image hashes and storage references.
- Engine execution status.
- Metadata findings and detector outputs.
- Error records and processing history.
- Correlated results and report references.

Large image files should generally remain in controlled file or object storage rather than being stored directly in ordinary analysis records.

### 4.8 Redis

Redis is planned for supporting capabilities such as caching, temporary state, and coordination where appropriate.

It may also support rate limiting or task-processing infrastructure, depending on the final design. It will not replace Kafka as the primary event-streaming system or PostgreSQL as the persistent analysis database.

### 4.9 Frontend and Results

The React frontend will provide the user interface for:

- Uploading images.
- Initiating analysis.
- Viewing analysis status.
- Examining results from individual engines.
- Reviewing the combined evidence summary.
- Inspecting limitations and failed checks.
- Viewing or exporting forensic reports as reporting features are implemented.

Server-sent events or WebSockets may be introduced to deliver progressive status updates.

## 5. Technology Stack

| Category | Technologies |
|---|---|
| Frontend | React, Vite |
| API and microservices | Python, FastAPI, Uvicorn |
| Image analysis | Pillow, NumPy, OpenCV and selected forensic libraries |
| AI inference | Evaluated pretrained models and suitable machine-learning libraries |
| Messaging and streaming | Apache Kafka |
| Database | PostgreSQL |
| Caching and supporting services | Redis |
| Containers | Docker, Docker Compose |
| Cloud platform | Cloud services selected for deployment and experimentation |
| DevOps | Git, GitHub, CI/CD, automated testing, logging and monitoring |

Technologies will be introduced as required by the implementation rather than treating every listed component as already deployed.

## 6. Development Workflow

Development will proceed incrementally:

1. Implement and test the API gateway and temporary image storage.
2. Build and validate each forensic engine independently.
3. Define shared schemas for analysis tasks and results.
4. Integrate the orchestrator and Kafka messaging.
5. Implement persistent analysis records in PostgreSQL.
6. Develop evidence correlation and report generation.
7. Connect the frontend to the analysis workflow.
8. Containerize the services and run the complete system locally.
9. Deploy the application to a cloud platform.
10. Implement CI/CD, monitoring, security controls, and operational improvements.

The implementation will be tested at the service, integration, and end-to-end levels as the system grows.

## 7. Current Development Status

The project currently has a working local API gateway that validates supported image uploads, calculates SHA-256 hashes, and stores images temporarily.

The Metadata and Provenance service can independently analyze an image and return its dimensions, format, available EXIF fields, embedded-information keys, and hash.

The gateway-to-metadata integration and the remaining forensic engines are still under development. Kafka orchestration, persistent result storage, evidence correlation, the complete frontend workflow, and cloud deployment will be implemented in subsequent stages.

ImForensic is an evolving project. Its findings are intended to support human investigation and must be interpreted in light of the methods used, available evidence, and known limitations.
