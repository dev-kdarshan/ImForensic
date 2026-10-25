# Security checklist

- Enforce byte-size and decoded-dimension limits; verify actual file content rather than trusting extension or MIME type.
- Decode images in a constrained worker; keep libraries patched.
- Store uploads privately with short TTL and least-privilege access.
- Avoid logging image contents, secrets, or unnecessary personal data.
- Apply rate limits and resource quotas to public no-login uploads.
- Clean up temporary files on success, failure, timeout, and expiry.
