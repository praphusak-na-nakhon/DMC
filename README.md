# DMC Assistant

Monorepo scaffold for the DMC Assistant MVP.

## Layout

- `apps/desktop`: Tauri + React desktop shell
- `apps/sidecar`: Python sidecar for automation and local persistence
- `apps/cloud`: FastAPI backend for licensing, config, and telemetry
- `packages/shared-schemas`: shared JSON schemas for IPC and API contracts
- `packages/module-configs`: signed-config candidates for portal modules

## Current Status

This repository currently contains:

- the legacy prototype script at `fill_obec_portal.py`
- the M1 scaffold defined by `docs/PRD.md` and `docs/TDD.md`

## M1 Goals

- monorepo structure
- JSON-RPC sidecar skeleton
- local SQLite persistence for license and jobs
- cloud API skeleton
- desktop shell placeholder
