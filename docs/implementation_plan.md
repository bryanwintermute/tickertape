# Tickertape v0 Implementation Plan

This plan addresses the open design questions from the project brief and proposes a v0 architecture for `tickertape`, a user-facing app for sending short messages to your Rongta RP332 thermal receipt printer.

## User Review Required

Please review the proposed design decisions below. If you agree with these defaults, I can proceed with scaffolding the application.

> [!IMPORTANT]
> The biggest decision is the **Tech Stack**. 
> The brief mentions considering Python (consistent with `unspooled`), Go (single binary), or JS/TS (better for web UI).
> 
> **My Proposal:** **Python** (using standard library `http.server` or a minimal framework like `FastAPI`/`Flask` if preferred, though `http.server` is proposed below for zero dependencies) for the backend service, and **vanilla HTML/CSS/JS** for the frontend. This keeps it consistent with `unspooled` and meets your "minimal-dependency Python" convention.

## Open Questions & Proposed Answers

Here are the proposed answers to the 10 design questions from `HANDOFF.md`:

1. **Service Architecture**: **HTTP Service on the Pi**. It's much friendlier for the mobile/web integrations than an SSH-based push.
2. **Minimum Feature Set**: **All of the above**. We'll support an "echo" endpoint, a specific shopping list format, and a queue for reminders.
3. **Phone UX**: **Mobile-friendly web UI (HTML form)**. The Python service will serve a simple, responsive HTML/JS/CSS frontend that feels like an app.
4. **Authentication**: **None / IP Allowlist** for v0, assuming it runs on a trusted LAN or Tailscale tailnet. We can add a simple token later if needed.
5. **Persistence + Queueing**: **SQLite**. A simple table (`id`, `payload`, `status`, `created_at`) to queue prints. If the printer is offline, they queue up.
6. **Multi-printer**: **Yes**. The API schema will include an optional `printer_id` field defaulting to the primary Rongta.
7. **Concurrent Prints**: **Background Worker + SQLite**. An in-memory lock or a dedicated background thread pulling from SQLite ensures the printer is fed serially.
8. **Idempotency**: **Client-side UUIDs**. The client will generate an idempotency key (UUID) to prevent double-printing on retries.
9. **Print Confirmation**: **Queued**. The service will respond with "queued". We can use the paper-out sensor via USB in a later phase to confirm successful printing.
10. **Integration Scope**: **CLI + Web Form + Webhook**. Since we're building an HTTP service, a generic webhook endpoint (e.g., for Home Assistant) is trivial to include.

## Proposed Architecture & Changes

The v0 architecture will consist of:

1. **Backend Service (`tickertape/server/`)**: A Python HTTP server running on the Pi. It exposes:
   - `POST /api/print`: Accepts JSON payloads (title, style, items).
   - `GET /`: Serves the web UI.
   - A background thread that polls a local SQLite database and calls `unspooled`'s `receipt_print.py`.

2. **Web Frontend (`tickertape/web/`)**: Vanilla HTML/CSS/JS files served by the backend. It will feature a modern, dynamic, and responsive UI.

3. **CLI Client (`tickertape/cli/`)**: A simple Python wrapper around `curl`/`urllib` that reads from `~/.config/tickertape/config.json` and posts to the API.

### tickertape

#### [NEW] [server.py](file:///home/bryan/github/tickertape/tickertape/server/server.py)
The main entry point for the Pi service. Sets up the HTTP server and the SQLite database.

#### [NEW] [worker.py](file:///home/bryan/github/tickertape/tickertape/server/worker.py)
Background thread that pulls from the SQLite queue and interfaces with `unspooled`.

#### [NEW] [index.html](file:///home/bryan/github/tickertape/tickertape/web/index.html)
The mobile-friendly web UI.

#### [NEW] [styles.css](file:///home/bryan/github/tickertape/tickertape/web/styles.css)
Modern, premium vanilla CSS for the web UI.

#### [NEW] [app.js](file:///home/bryan/github/tickertape/tickertape/web/app.js)
Frontend logic to post requests to the `/api/print` endpoint.

#### [NEW] [cli.py](file:///home/bryan/github/tickertape/tickertape/cli/cli.py)
The CLI entry point for laptop-to-printer pushing.

## Verification Plan

### Automated Tests
- Create Python unit tests for the SQLite queueing logic and API payload validation.

### Manual Verification
- Start the server locally with a mock `unspooled` interface (dry-run mode).
- Verify the web UI looks premium and works correctly on desktop and simulated mobile viewports.
- Run the CLI tool and verify it successfully queues a job.
