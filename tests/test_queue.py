import pytest
import os
import db
from db import init_db, enqueue_job, get_next_pending_job, list_reminders, mark_job_status, get_connection, list_history, recover_crashed_jobs, delete_job, clear_history

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test.db"
    db.DB_PATH = db_file
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

def test_list_history_roundtrip():
    id_echo = enqueue_job("key-echo", "echo", {"title": "Note", "text": "hello"})
    id_list = enqueue_job("key-list", "list", {"title": "Groceries", "items": ["milk", "bread"], "style": "checkbox"})
    mark_job_status(id_echo, "printed")
    mark_job_status(id_list, "printed")

    history = list_history()
    assert len(history) == 2
    # Both jobs present (newest-first ordering is second-resolution and ties
    # to rowid for fast inserts, so we don't assert strict order here)
    ids = {h["id"] for h in history}
    assert ids == {id_echo, id_list}
    # payload round-trips through JSON intact
    by_id = {h["id"]: h for h in history}
    assert by_id[id_echo]["payload"]["text"] == "hello"
    assert by_id[id_list]["payload"]["items"] == ["milk", "bread"]
    assert by_id[id_list]["payload"]["style"] == "checkbox"
    for h in history:
        assert h["status"] == "printed"

def test_list_history_limits_to_50():
    ids = [enqueue_job(f"key-limit-{i}", "echo", {"title": f"n{i}"}) for i in range(55)]
    for jid in ids:
        mark_job_status(jid, "printed")
    history = list_history()
    assert len(history) == 50

def test_recover_crashed_jobs():
    id1 = enqueue_job("key-reco-1", "echo", {"title": "a"})
    id2 = enqueue_job("key-reco-2", "echo", {"title": "b"})
    mark_job_status(id1, "processing")
    mark_job_status(id2, "failed_retriable")

    recover_crashed_jobs()

    with get_connection() as conn:
        statuses = [r["status"] for r in conn.execute("SELECT status FROM queue ORDER BY id").fetchall()]
    assert statuses == ["pending", "pending"]

def test_delete_job_removes_only_that_row():
    id1 = enqueue_job("key-del-1", "echo", {"title": "a"})
    id2 = enqueue_job("key-del-2", "echo", {"title": "b"})
    assert delete_job(id1) is True
    assert delete_job(999_999) is False  # missing id → False

    with get_connection() as conn:
        rows = conn.execute("SELECT id FROM queue ORDER BY id").fetchall()
    assert [r["id"] for r in rows] == [id2]

def test_clear_history_leaves_inbox_and_pending():
    printed  = enqueue_job("key-clr-printed",  "echo", {"title": "p"})
    failed   = enqueue_job("key-clr-failed",   "list", {"title": "f", "items": ["x"]})
    inbox_id = enqueue_job("key-clr-inbox",    "reminder", {"title": "i"})
    pending  = enqueue_job("key-clr-pending",  "echo", {"title": "q"})
    mark_job_status(printed, "printed")
    mark_job_status(failed,  "failed")

    count = clear_history()
    assert count == 2

    with get_connection() as conn:
        remaining_ids = {r["id"] for r in conn.execute("SELECT id FROM queue").fetchall()}
    assert remaining_ids == {inbox_id, pending}

    # A second clear is a no-op
    assert clear_history() == 0
