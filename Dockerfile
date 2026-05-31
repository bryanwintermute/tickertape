FROM python:3.9-slim

WORKDIR /app
COPY . /app/

# Since there are no external pip dependencies, we don't need a requirements.txt!
# We just need a simple wrapper to run both the server and worker in the same container.
# This avoids needing to share a volume for the SQLite DB between two separate containers.
RUN echo '#!/bin/bash\npython3 server.py &\npython3 worker.py &\nwait -n\nexit $?' > /app/start.sh
RUN chmod +x /app/start.sh

# Environment variables that can be overridden
ENV TICKERTAPE_DB=/data/tickertape.db
ENV PRINTER_DEVICE=/dev/rongta-receipt
ENV TZ=UTC

# We expose 8000 for the web UI
EXPOSE 8000

# Create the data directory for the SQLite database
RUN mkdir -p /data

CMD ["/app/start.sh"]
