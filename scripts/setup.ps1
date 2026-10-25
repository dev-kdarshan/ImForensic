$ErrorActionPreference = "Stop"
Write-Host "ImForensic scaffold is already laid out in this folder."
Write-Host "Next: copy .env.example to .env, then start infrastructure:"
Write-Host "  docker compose -f infrastructure/docker-compose.yml up -d"
