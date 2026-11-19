# CareOn Infrastructure & Deployment

This directory contains infrastructure, container manifests, and deployment configuration for CareOn services:

- `docker-compose.yml`: Root service orchestration (PostgreSQL 17 + PostGIS, Redis, FastAPI backend).
- `nginx/`: Production reverse proxy and SSL termination configurations.
- `pwa/`: Static web hosting configurations for `apps/citizen-web/dist`.
