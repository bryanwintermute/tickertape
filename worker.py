import os
import time
import logging
from db import init_db, get_next_pending_job, mark_job_status, requeue_job, recover_crashed_jobs
from _vendored.receipt_print import render_markdown
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 2.0
PRINTER_DEVICE = os.environ.get("PRINTER_DEVICE", "/dev/rongta-receipt")

def print_to_device(raw_bytes: bytes, device_path: str):
    with open(device_path, 'wb') as f:
        f.write(raw_bytes)

def process_job(job: dict):
    logger.info(f"Processing job {job['id']} of type {job['type']}")
    payload = job['payload']
    
    try:
        # Build the receipt
        title = payload.get('title')
        
        if job['type'] == 'echo':
            text = payload.get('text', '')
        else:
            style = payload.get('style', 'checkbox')
            items = payload.get('items', [])
            lines = []
            for item in items:
                if style == 'checkbox':
                    lines.append(f"- [ ] {item}")
                elif style == 'bullet':
                    lines.append(f"- {item}")
                elif style == 'numbered':
                    lines.append(f"1. {item}")
                else:
                    lines.append(item)
            text = '\n'.join(lines)
                
        raw_bytes = render_markdown(text, title=title)
        
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
        attempts = job.get('attempts', 0) + 1
        if attempts < 3:
            logger.info(f"Requeueing job {job['id']} (attempt {attempts} of 3)")
            requeue_job(job['id'], attempts)
            time.sleep(1) # Small backoff
        else:
            logger.error(f"Job {job['id']} failed after 3 attempts. Giving up.")
            mark_job_status(job['id'], 'failed')

def run_worker():
    init_db()
    recover_crashed_jobs()
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
