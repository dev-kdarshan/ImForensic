# Security notes

- Uploads are limited by byte size, media type, file signature, decoded image format, and pixel count.
- The Gateway sends image bytes to the Metadata service; the service does not accept arbitrary server filesystem paths.
- Storage is private to the application container and persisted in a named Docker volume.
- Do not expose the development stack publicly without authentication, authorization, rate limiting, TLS, encryption at rest, monitoring, and a reviewed retention policy.
- C2PA manifests and signatures are not verified by the current engine.
- Metadata values are untrusted input and must be escaped before rendering in other contexts.
- Add scheduled retention cleanup and object-storage lifecycle policies before handling real sensitive evidence at scale.
