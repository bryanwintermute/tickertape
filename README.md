# tickertape

Tickertape is the user-facing web app and CLI for pushing short, time-ordered messages (to-dos, shopping lists, reminders) to a home-network thermal receipt printer.

Built on top of [`unspooled`](https://github.com/bryanwintermute/unspooled).

## Architecture
- **Server (`server.py`)**: Serves the mobile-friendly web UI and a simple `/api/print` endpoint.
- **Worker (`worker.py`)**: A background process that polls a local SQLite queue and interfaces with `unspooled` to print.
- **CLI (`cli.py`)**: A simple Python wrapper around curl/urllib to push jobs to the server from a laptop or cron job.

## Setup

The easiest way to run the project (both the web UI/API and the print worker) is using Docker Compose.

### Running Locally with Docker (Recommended)

To run the application locally for development or testing:

1. Connect your Rongta RP332 printer via USB. Ensure it appears as `/dev/usb/lp0`.
2. Build and start the services using the development compose file:
   ```bash
   docker compose -f docker-compose.dev.yml up --build
   ```
3. Open `http://localhost:8000` in your browser.

If you don't have a printer connected, the worker will safely swallow the `PermissionError` or `FileNotFoundError` and you can still test the UI.

### Manual Setup (Without Docker)

If you prefer to run it manually with Python 3.11+:

1. Create a virtual environment and install dependencies (though there are no external dependencies right now!):
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Start the API & Web Server (runs on port 8000):
   ```bash
   python server.py
   ```

3. In a separate terminal, start the Worker process:
   ```bash
   python worker.py
   ```

### Configuration
You can configure the path to the printer by setting the `PRINTER_DEVICE` environment variable. It defaults to `/dev/rongta-receipt`. When running in Docker, ensure you map the printer device (e.g. `/dev/usb/lp0`) correctly in the compose file under the `devices:` block.

### Systemd Deployment
Example `.service` files for Raspberry Pi deployments are included:
- `tickertape.service`
- `tickertape-worker.service`

Copy these to `/etc/systemd/system/` and enable them.