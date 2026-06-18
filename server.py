import http.server
import socketserver
import json
import logging
import uuid
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from db import init_db, enqueue_job, list_reminders, list_history, mark_job_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = 8000
WEB_DIR = Path(__file__).parent / "web"

class TickertapeHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_POST(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/print':
            self._handle_print_job()
        elif parsed_path.path == '/api/release_reminder':
            self._handle_release_reminder()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/inbox':
            self._handle_get_inbox()
        elif parsed_path.path == '/api/history':
            self._handle_get_history()
        elif parsed_path.path == '/' or parsed_path.path == '/index.html':
            self._serve_index()
        else:
            # Fall back to serving static files from web/
            super().do_GET()

    def _serve_index(self):
        index_path = WEB_DIR / "index.html"
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import datetime
            version_str = f"Server Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            content = content.replace("<!-- APP_VERSION -->", version_str)
            
            encoded = content.encode('utf-8')
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(encoded)
        except Exception as e:
            logger.error(f"Failed to serve index: {e}")
            self._send_error(500, "Internal Server Error")

    def _handle_print_job(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
            return

        # Validate required fields
        job_type = payload.get('type')
        if not job_type or job_type not in ('echo', 'list', 'reminder'):
            self._send_error(400, "Missing or invalid 'type'. Must be 'echo', 'list', or 'reminder'")
            return

        # Use client-provided idempotency key or generate one
        idem_key = payload.get('idempotency_key', str(uuid.uuid4()))
        
        # Enqueue the job
        try:
            job_id = enqueue_job(idem_key, job_type, payload)
            
            self.send_response(202) # Accepted
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "queued", "job_id": job_id}).encode())
            logger.info(f"Queued {job_type} job (ID: {job_id})")
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            self._send_error(500, "Internal Server Error")

    def _handle_release_reminder(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
            job_id = payload.get('id')
            if not job_id:
                self._send_error(400, "Missing job id")
                return
                
            mark_job_status(job_id, 'pending')
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "id": job_id}).encode())
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
        except Exception as e:
            logger.error(f"Failed to release reminder: {e}")
            self._send_error(500, "Internal Server Error")

    def _handle_get_inbox(self):
        try:
            reminders = list_reminders()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"reminders": reminders}).encode())
        except Exception as e:
            logger.error(f"Failed to fetch inbox: {e}")
            self._send_error(500, "Internal Server Error")

    def _handle_get_history(self):
        try:
            history = list_history()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"history": history}).encode())
        except Exception as e:
            logger.error(f"Failed to fetch history: {e}")
            self._send_error(500, "Internal Server Error")

    def _send_error(self, code: int, message: str):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

def run():
    init_db()
    logger.info("Database initialized.")
    
    with socketserver.TCPServer(("", PORT), TickertapeHandler) as httpd:
        logger.info(f"Serving UI and API at port {PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down server...")

if __name__ == '__main__':
    run()
