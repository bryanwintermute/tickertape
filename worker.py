import os
import time
import logging
from db import init_db, get_next_pending_job, mark_job_status
from _vendored.receipt_print import Receipt
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

def print_to_device(raw_bytes: bytes, device_path: str):
    with open(device_path, 'wb') as f:
        f.write(raw_bytes)

def process_job(job: dict):
    logger.info(f"Processing job {job['id']} of type {job['type']}")
    payload = job['payload']
    
    try:
        save = payload.get('save_to_history', True)
        
        # Build the receipt
        title = sanitize_text(payload.get('title'))
        style = payload.get('style', 'checkbox')
        
        if job['type'] == 'echo':
            style = 'plain'
            
        receipt = Receipt(title=title, style=style, timestamp=True)
        
        items = payload.get('items', [])
        if job['type'] == 'echo':
            text = payload.get('text', '')
            if text:
                for line in text.split('\n'):
                    receipt.add_item(sanitize_text(line))
        else:
            for item in items:
                receipt.add_item(sanitize_text(item))
                
        raw_bytes = receipt.to_bytes()
        
        # In a real environment, send to PRINTER_DEVICE
        # For testing if the device doesn't exist, we fall back to logging
        if os.path.exists(PRINTER_DEVICE):
            print_to_device(raw_bytes, PRINTER_DEVICE)
            logger.info(f"Job {job['id']} printed successfully to {PRINTER_DEVICE}.")
            
            save = payload.get('save_to_history', True)
            if save:
                mark_job_status(job['id'], 'printed')
            else:
                mark_job_status(job['id'], 'forgotten')
        else:
            logger.warning(f"Device {PRINTER_DEVICE} not found! Dry-run mode.")
            logger.info(f"Payload generated ({len(raw_bytes)} bytes)")
            mark_job_status(job['id'], 'skipped-dry-run')
        
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
