import pytest
import os
from db import init_db, enqueue_job, get_next_pending_job, list_reminders, mark_job_status, get_connection

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    monkeypatch.setenv("TICKERTAPE_DB", ":memory:")
    init_db()
    
def test_idempotency_returns_same_id():
    payload = {"title": "Test"}
    id1 = enqueue_job("test-key-1", "echo", payload)
    id2 = enqueue_job("test-key-1", "echo", payload)
    assert id1 == id2
    
def test_reminders_default_to_inbox():
    id1 = enqueue_job("key-rem", "reminder", {"title": "rem"})
    with get_connection() as conn:
        row = conn.execute("SELECT status FROM queue WHERE id = ?", (id1,)).fetchone()
        assert row["status"] == "inbox"
        
    reminders = list_reminders()
    assert len(reminders) == 1
    
    # Next pending job shouldn't pick it up yet
    assert get_next_pending_job() is None
    
    # Mark it as pending
    mark_job_status(id1, 'pending')
    
    # Now it should be picked up
    job = get_next_pending_job()
    assert job is not None
    assert job['id'] == id1
