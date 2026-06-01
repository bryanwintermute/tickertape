# tickertape

Tickertape is the user-facing web app and CLI for pushing short, time-ordered messages (to-dos, shopping lists, reminders) to a home-network thermal receipt printer.

Built on top of [`unspooled`](https://github.com/bryanwintermute/unspooled).

## Architecture
- **Server (`server.py`)**: Serves the mobile-friendly web UI and a simple `/api/print` endpoint.
- **Worker (`worker.py`)**: A background process that polls a local SQLite queue and interfaces with `unspooled` to print.
- **CLI (`cli.py`)**: A simple Python wrapper around curl/urllib to push jobs to the server from a laptop or cron job.

## Setup
### Dependencies
- Python 3.9+
- A thermal printer available as a character device (e.g. `/dev/usb/lp0` or `/dev/rongta-receipt`)

### Configuration
You can configure the path to the printer by setting the `PRINTER_DEVICE` environment variable. It defaults to `/dev/rongta-receipt`.

### Running Locally
```bash
# Start the web server (listens on port 8000)
python3 server.py

# In another terminal, start the worker
python3 worker.py
```

Open `http://localhost:8000` to access the mobile UI.

### Docker & Portainer
A `docker-compose.yml` is provided for easy deployment via Portainer (it pulls the latest image from GHCR). 

If you are developing locally and want to build the Docker image from your local code, use the dev compose file:
```bash
docker compose -f docker-compose.dev.yml up --build
```

When running in Docker, ensure you map the printer device (e.g. `/dev/usb/lp0`) correctly in the compose file under the `devices:` block.

### Systemd Deployment
Example `.service` files for Raspberry Pi deployments are included:
- `tickertape.service`
- `tickertape-worker.service`

Copy these to `/etc/systemd/system/` and enable them.