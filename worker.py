import os
import time
import logging
import re
from datetime import datetime
from db import init_db, get_next_pending_job, mark_job_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 2.0
PRINTER_DEVICE = os.environ.get("PRINTER_DEVICE", "/dev/rongta-receipt")

def sanitize_text(text: str) -> str:
    """Replaces common non-CP437 characters with ASCII approximations."""
    if not text:
        return text
    replacements = {
        '“': '"', '”': '"', "‘": "'", "’": "'",
        '—': '--', '–': '-', '…': '...',
        '¼': '1/4', '½': '1/2', '¾': '3/4',
        '°': ' deg', '©': '(c)', '®': '(r)'
    }
    for search, replace in replacements.items():
        text = text.replace(search, replace)
    return text

class EscPosReceipt:
    """A lightweight ESC/POS generator for thermal receipt printers."""
    def __init__(self):
        self.buffer = bytearray()
        self.buffer.extend(b'\x1b\x40') # Initialize printer
    
    def add_title(self, text: str):
        text = sanitize_text(text)
        self.buffer.extend(b'\x1b\x61\x01') # Center align
        self.buffer.extend(b'\x1b\x21\x20') # Double width & height
        self.buffer.extend(text.encode('cp437', errors='replace') + b'\n')
        self.buffer.extend(b'\x1b\x21\x00') # Normal text
        self.buffer.extend(b'\x1b\x61\x00') # Left align
        self.buffer.extend(b'\n')

    def _add_markdown_text(self, text: str):
        """Parses simple **bold** and *bold* markdown."""
        parts = re.split(r'(\*\*.*?\*\*|\*.*?\*)', text)
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                self.buffer.extend(b'\x1b\x45\x01') # Bold on
                self.buffer.extend(part[2:-2].encode('cp437', errors='replace'))
                self.buffer.extend(b'\x1b\x45\x00') # Bold off
            elif part.startswith('*') and part.endswith('*'):
                self.buffer.extend(b'\x1b\x45\x01') # Bold on
                self.buffer.extend(part[1:-1].encode('cp437', errors='replace'))
                self.buffer.extend(b'\x1b\x45\x00') # Bold off
            else:
                self.buffer.extend(part.encode('cp437', errors='replace'))
                
    def add_text(self, text: str):
        text = sanitize_text(text)
        self._add_markdown_text(text)
        self.buffer.extend(b'\n')

    def add_checkbox_item(self, text: str):
        text = sanitize_text(text)
        self.buffer.extend(b'[ ] ')
        self._add_markdown_text(text)
        self.buffer.extend(b'\n')

    def add_bullet_item(self, text: str):
        text = sanitize_text(text)
        self.buffer.extend(b'- ')
        self._add_markdown_text(text)
        self.buffer.extend(b'\n')
        
    def add_numbered_item(self, index: int, text: str):
        text = sanitize_text(text)
        self.buffer.extend(f"{index}. ".encode('cp437'))
        self._add_markdown_text(text)
        self.buffer.extend(b'\n')

    def add_timestamp(self):
        # We use local time explicitly
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.buffer.extend(b'\n\x1b\x61\x02') # Right align
        self.buffer.extend(b'\x1b\x21\x01') # Small text
        self.buffer.extend(ts.encode('cp437') + b'\n')
        self.buffer.extend(b'\x1b\x21\x00') # Normal text
        self.buffer.extend(b'\x1b\x61\x00') # Left align

    def add_cut(self):
        self.buffer.extend(b'\n\n\n\n') # Feed some lines before cutting
        self.buffer.extend(b'\x1d\x56\x00') # Full cut

    def get_bytes(self) -> bytes:
        return bytes(self.buffer)

def print_to_device(data: bytes, device_path: str):
    """Writes the raw bytes to the printer device file."""
    with open(device_path, "wb") as f:
        f.write(data)

def process_job(job: dict):
    logger.info(f"Processing job {job['id']} (type: {job['type']})")
    payload = job['payload']
    
    try:
        receipt = EscPosReceipt()
        
        title = payload.get('title')
        if title:
            receipt.add_title(title)
            
        job_type = job['type']
        if job_type == 'echo':
            text = payload.get('text', '')
            receipt.add_text(text)
        elif job_type in ('list', 'reminder'):
            items = payload.get('items', [])
            style = payload.get('style', 'bullet')
            
            for i, item in enumerate(items, 1):
                if style == 'checkbox':
                    receipt.add_checkbox_item(item)
                elif style == 'numbered':
                    receipt.add_numbered_item(i, item)
                else:
                    receipt.add_bullet_item(item)
                    
        if not payload.get('no_timestamp', False):
            receipt.add_timestamp()
            
        if not payload.get('no_cut', False):
            receipt.add_cut()
            
        raw_bytes = receipt.get_bytes()
        
        # In a real environment, send to PRINTER_DEVICE
        # For testing if the device doesn't exist, we fall back to logging
        if os.path.exists(PRINTER_DEVICE):
            print_to_device(raw_bytes, PRINTER_DEVICE)
            logger.info(f"Job {job['id']} printed successfully to {PRINTER_DEVICE}.")
        else:
            logger.warning(f"Device {PRINTER_DEVICE} not found! Dry-run mode.")
            logger.info(f"Payload generated ({len(raw_bytes)} bytes)")
            
        save = payload.get('save_to_history', True)
        if save:
            mark_job_status(job['id'], 'printed')
        else:
            mark_job_status(job['id'], 'forgotten')
        
    except PermissionError:
        logger.error(f"Permission denied to write to {PRINTER_DEVICE}. Check udev rules.")
        mark_job_status(job['id'], 'failed')
    except Exception as e:
        logger.error(f"Failed to print job {job['id']}: {e}")
        mark_job_status(job['id'], 'failed')

def run_worker():
    init_db()
    logger.info(f"Worker started. Polling for jobs. Printer set to {PRINTER_DEVICE}")

    while True:
        try:
            job = get_next_pending_job()
            if job:
                process_job(job)
            else:
                time.sleep(POLL_INTERVAL_SEC)
        except KeyboardInterrupt:
            logger.info("Worker shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in worker loop: {e}")
            time.sleep(POLL_INTERVAL_SEC)

if __name__ == '__main__':
    run_worker()
