# tickertape v0 review — feedback for the next iteration

**Reviewer:** Copilot CLI (Claude) session running adjacent to
Bryan, dated 2026-06-01.
**Reviewed:** repository state at commit `d690a85` (after the
8 commits scaffolding tickertape v0).
**Purpose:** structured review handed to the next session (likely
Gemini via Antigravity CLI) to triage + address.

This file is not committed yet. It captures my findings, the
priority order Bryan and I agreed on, and the upstream decisions
in `unspooled` (the dependency it should consume) that were made
specifically to make this integration clean. None of these are
hard requirements — push back where you disagree, and ask Bryan
to arbitrate.

---

## tl;dr

Tickertape v0 is a **structurally sound implementation that
works end-to-end** (server starts, queues, idempotency works,
history & inbox endpoints respond — all verified live). The
architecture matches what the HANDOFF brief proposed: HTTP
service + SQLite queue + background worker + web UI + CLI.

There's **one architectural divergence** worth correcting (it
reimplements ESC/POS instead of using upstream `unspooled`), and a
handful of real but small bugs (UI/data-model coherence, worker
status semantics, CI gaps, etc.). All addressable in a focused
follow-up pass.

## What's there + what works

| Component | File | Status |
|---|---|---|
| HTTP service | `server.py` | Works. stdlib `http.server`. POST `/api/print`, GET `/api/inbox`, GET `/api/history`. |
| Worker | `worker.py` | Works. Polls SQLite, generates ESC/POS, writes to `/dev/rongta-receipt`. |
| SQLite queue | `db.py` | Works. `idempotency_key UNIQUE` constraint. Status column. |
| Web UI | `web/index.html`, `app.js`, `styles.css` | Dark theme, mobile viewport, 4 tabs (Echo/List/Inbox/History), 275 lines of CSS. Loads Outfit from Google Fonts CDN. |
| CLI | `cli.py` | Works. `tickertape echo` + `tickertape list` subcommands. |
| Docker | `Dockerfile` + `docker-compose.yml` | Single container running both server + worker, SQLite on a named volume, printer device mapped. |
| systemd | `tickertape.service` + `tickertape-worker.service` | Pi-deployment alternative. |
| CI | `.github/workflows/docker-publish.yml` | Builds + pushes multi-arch (amd64 + arm64) to GHCR on every push to main. |
| Docs | `README.md`, `docs/HANDOFF.md`, `docs/implementation_plan.md` | OK, with caveats below. |

Things tickertape v0 does **well** that I want to call out
explicitly (so they're preserved, not refactored away):

* **Idempotency works correctly.** Verified live: same key,
  same job_id returned.
* **The schema is sensible** for a single-printer v0 (idempotency
  unique, status enum-shaped column, JSON payload column).
* **Architecture is the right shape** (server + worker + SQLite
  matches HANDOFF q5/q7).
* **Web UI is genuinely nice** — clean dark mode, good mobile
  layout. The "Reprint" button on History is a delightful touch
  we didn't even discuss in the HANDOFF.
* **Stdlib only on the backend.** Sticks to Bryan's convention.
* **Multi-arch Docker** for amd64 + arm64 — accommodates the Pi.
* **All design-question answers in `docs/implementation_plan.md`
  match the HANDOFF defaults.**

## The big architectural finding

**Tickertape does NOT actually use `unspooled`.** It reimplements
ESC/POS from scratch in a 95-line `EscPosReceipt` class inside
`worker.py`.

The HANDOFF explicitly said the opposite:

> The renderer remains unspooled's receipt_print.py. Tickertape
> adds the transport + queuing + UI layers; it does NOT
> re-implement ESC/POS.

Concrete evidence:

* No `import receipt_print` or `import unspooled` anywhere in
  `*.py`, `web/*.js`, `Dockerfile`, or `docker-compose*.yml`.
* No git submodule, no pip dep, no clone path in the Dockerfile,
  no PYTHONPATH magic.
* The README claims "Built on top of `unspooled`" but it's
  name-checking only — there's zero code coupling.
* The two implementations have **already diverged**: tickertape
  adds simple `**bold**` markdown parsing, swaps smart-quotes via
  a `sanitize_text()` function, uses a different timestamp format
  ("YYYY-MM-DD HH:MM:SS" with seconds, vs unspooled's "YYYY-MM-DD
  HH:MM"), and feeds 4 lines pre-cut vs unspooled's 5.

### Why this matters

* Future bug fixes / new code pages / new font support in
  `unspooled` won't reach tickertape.
* The two byte-level outputs drift over time even though they're
  notionally rendering the same thing.
* Bryan has to maintain two ESC/POS implementations.
* The 68-test wire-protocol suite in `unspooled` (51 CLI
  dispatcher tests + 17 renderer library tests as of v0.2.0)
  protects neither implementation here.

### Background

Bryan's original instinct when creating tickertape was that
unspooled was a printer-management tool (Rongta-specific) and
shouldn't be a dependency for a printer-agnostic app. That
instinct wasn't wrong — but it turned out to be a framing problem,
not a code problem. The byte-emitting surface of
`unspooled/receipt_print.py` was **already 100% standard Epson
ESC/POS** (no Rongta-vendor commands at all). Only the docstrings,
defaults, and README made it feel Rongta-coupled.

We just shipped **[unspooled v0.2.0](https://github.com/bryanwintermute/unspooled/releases/tag/v0.2.0)**
specifically to make this integration clean:

* `receipt_print.py` reframed as brand-agnostic. New module
  docstring leads with "Stdlib-only ESC/POS renderer for 80mm
  and 58mm thermal receipt printers".
* `DEFAULT_DEVICE` is now `/dev/usb/lp0` (kernel-generic).
* New `print_width` constructor kwarg (and `--print-width` CLI
  flag) for 58mm support (`=32`), 80mm Font B (`=56`), etc.
* New README section "Use as a library" with `from receipt_print
  import Receipt` example.
* 17 new tests in `tests/test_receipt_print_library.py` lock the
  public `Receipt` API.
* CLI byte output for any input that doesn't use `--print-width`
  is **byte-identical to v0.1.2** (verified by sha256), so
  there's no risk of breaking existing callers.

### Recommended action: vendor a snapshot

After weighing options (submodule / pip / vendor / leave-it-as-is)
with Bryan, the chosen approach is **vendor a snapshot**:

1. `cp ~/github/unspooled/receipt_print.py
   ~/github/tickertape/_vendored/receipt_print.py`
2. Add a header to the vendored copy:

   ```python
   # Vendored from https://github.com/bryanwintermute/unspooled
   # at v0.2.0 (commit bc19427). DO NOT EDIT locally; refresh by
   # re-vendoring from upstream.
   ```
3. Update `worker.py` to:

   ```python
   from _vendored.receipt_print import Receipt
   ```

   …and delete the 95-line `EscPosReceipt` class.
4. Re-route `process_job()`'s logic: build a `Receipt(title=…,
   style=…, print_width=…)`, call `.add_items(items)`, write
   `.to_bytes()` to the printer.
5. Update tickertape's README to make the "Built on top of
   `unspooled`" claim literally true, pointing at the v0.2.0 tag.

Why vendor (instead of submodule or pip):

* Matches stdlib-first / minimal-deps style on both projects.
* Tickertape stays runnable from a fresh `git clone` with zero
  submodule dance.
* Docker COPY doesn't need to handle submodules.
* Drift risk is manageable: the header comment documents the
  source, and `unspooled`'s test suite gives a clear contract
  to verify against on refresh.
* Doesn't force any packaging decisions in `unspooled` (which
  explicitly has PyPI packaging in its CONTRIBUTING "out of
  scope" list for now).

### Functional differences to handle in the swap

The current `EscPosReceipt` in tickertape has a few features
upstream `Receipt` doesn't:

1. **`**bold**` / `*bold*` markdown parsing** in `_add_markdown_text`.
   Upstream doesn't. Two options:
   (a) Drop the markdown feature (simpler; users get
       what-you-type-is-what-you-get).
   (b) Add a thin pre-processing layer in tickertape that emits
       the bold-on/bold-off ESC/POS bytes inline — but then
       `Receipt` becomes harder to use as a contract. Discuss
       with Bryan; I'd lean (a).
2. **`sanitize_text()` for smart-quotes / em-dashes**. Upstream's
   `_encode()` uses `errors="replace"` which produces `?`.
   Tickertape's `sanitize_text()` is friendlier (turns `"` into
   `"`, `—` into `--`). This is a genuine improvement — propose
   it upstream as a PR to `unspooled`, possibly as an opt-in
   `sanitize=True` kwarg on `Receipt`. Until then, tickertape can
   pre-process strings before passing to `Receipt`.
3. **Timestamp format**: tickertape includes seconds; upstream
   doesn't. Cosmetic, pick one and stick to it.
4. **Pre-cut line feeds**: tickertape uses 4, upstream uses 5.
   The 5 in upstream is empirically tuned to advance paper above
   the cutter bar on the Rongta RP332; 4 is probably fine on
   other printers. Use upstream's default; users with different
   printers can call `Receipt(cut=False)` and emit the cut
   themselves.

## Other real bugs / concerns (in priority order)

These are unrelated to the integration question above. Some are
low-effort fixes; others are coherence-of-design issues that
deserve a short discussion before code.

### High priority

1. **UI/data-model coherence bug on the Inbox tab.**
   The UI calls it "Pending Reminders" but `list_reminders()` in
   `db.py` returns ALL jobs of type `'reminder'` regardless of
   status — including `'printed'`. The current data model has no
   `scheduled_for` field and no "drain on print" mechanism.
   Reminders are printed immediately on enqueue, then linger in
   the inbox tab forever as "printed".

   Either:
   * Rename the tab to "Recent Reminders" + filter the list to
     only show recent (last N) or non-failed entries; OR
   * Make reminders genuinely persistent (don't print on
     enqueue; show in inbox; user-action triggers a "print now"
     that flips them to history).

   The second option matches the HANDOFF brief's "persistent
   reminder list (inbox that drains on print)" framing better.

2. **Worker's misleading success log on dry-run.**
   In `worker.py:process_job()`, when `PRINTER_DEVICE` doesn't
   exist, the worker logs a warning then **still calls
   `mark_job_status('printed')`**. That's a lie — nothing
   printed. It should mark the job `'skipped-dry-run'` (new
   status) or `'failed'`, so the history view doesn't claim a
   non-existent print succeeded.

3. **`docker-compose.yml` specifies both `image:` and `build:`.**
   `docker compose up` will rebuild locally instead of pulling
   the GHCR image. Pick one:
   * Production compose: `image:` only (pulls from GHCR).
   * Dev compose (`docker-compose.dev.yml`?): `build:` only.

   Or: leave `build:` as a fallback but document the
   `--no-build` flag in the README.

4. **No tests at all.**
   `docs/implementation_plan.md` promised "Create Python unit
   tests for the SQLite queueing logic and API payload
   validation" but none exist. CI publishes a Docker image but
   never runs `pytest`. After the vendor swap, the tests should
   cover:
   * Idempotency: same key returns same id (already verified live
     — turn into a pytest).
   * Payload validation: `type` must be `echo`/`list`/`reminder`.
   * The worker's output bytes for a known payload (snapshot
     test against the vendored `Receipt`).

   Add a `pytest` job to the existing workflow OR add a
   second workflow that runs on every PR.

### Medium priority

5. **Worker job grab is non-atomic.**
   `db.get_next_pending_job()` does `SELECT … LIMIT 1` then
   later `mark_job_status()` UPDATEs. Fine for the single-worker
   case but no concurrency guard against accidentally running
   two workers. SQLite + `UPDATE … WHERE id = ? AND status =
   'pending' RETURNING *` would be atomic; or claim with a
   `worker_id` column.

6. **No retry logic in the worker.**
   A transient failure (printer unplugged briefly, USB reset)
   marks the job `'failed'` forever. Suggest: bounded retries
   (3 attempts with backoff), then `'failed'`. New `attempts`
   column on `queue`.

7. **CI uses Node-20-deprecated actions.**
   `actions/checkout@v4`, `docker/setup-buildx-action@v3`,
   `docker/login-action@v3`, `docker/metadata-action@v5`,
   `docker/build-push-action@v5`, `docker/setup-qemu-action@v3`.
   Same warning we fixed in `unspooled` by bumping to `@v6`
   (where available). Easy follow-up: bump each to the latest
   major.

8. **CLI doesn't have `--save / --no-save`.**
   The web UI exposes `save_to_history`; the CLI's `echo`/`list`
   subcommands don't. Add the flag; default `True` to match the
   web UI. Also consider `--no-cut` / `--no-timestamp` for
   parity with `unspooled`'s flags.

### Low priority / nits

9. **`docs/HANDOFF.md` is committed even though HANDOFF.md says
   "delete this file once the project takes shape".** Delete it
   (its content is captured in this review + the
   implementation_plan.md anyway).

10. **`__pycache__/db.cpython-311.pyc` is in the working tree**
    but correctly gitignored. Not in git; harmless. Could `git
    clean -fdX` periodically.

11. **`tickertape.db` exists locally** (28KB) but correctly
    gitignored. Same harmless state.

12. **`.env` is a copy of `.env.example`** with the same default
    values. Fine. Maybe add a comment in the example reminding
    users to actually customize it for non-Rongta setups.

13. **README's "Setup → Running Locally" runs `python3 server.py`
    + `python3 worker.py` in separate terminals.** Mention the
    Docker compose path as the primary recommendation since
    that's what the systemd unit + GHCR image are pointing at.

14. **The web UI loads Outfit from Google Fonts CDN** at
    runtime. That's a third-party dependency the rest of the
    project doesn't have. Consider self-hosting the font (one
    `.woff2` file) so tickertape works offline.

15. **Multi-printer support and webhook endpoint** were marked
    "deferred" in `implementation_plan.md` and are absent from
    v0. Not a regression. Could be a v0.2 follow-up.

## Repository hygiene findings (info, not action items)

* `.env` is correctly gitignored ✓
* `tickertape.db` is correctly gitignored ✓
* `__pycache__/` is correctly gitignored ✓
* `.antigravitycli/` symlinks to `~/.gemini/config/projects/...`
  — keeps Gemini's session state outside the repo. The `.agy/`
  gitignore entry (added in commit `01bb1fc`) defensively
  excludes any agent-tooling overflow.

## Tickertape's place in the broader project (Bryan's framing)

This is context for the next session, not action items.

* `unspooled` is the printer-management library + Rongta-RP332
  config tool (public, https://github.com/bryanwintermute/unspooled).
* `tickertape` is the user-facing app that lives on top.
* Bryan's actual end-user need: print to-do lists, shopping
  lists, and quick notes to the receipt printer from his phone
  and laptop.
* The Pi at "octoprint" (10.20.0.148 on Bryan's LAN) is the
  printer host; tickertape will run there.
* The web UI is intended to be reachable from a phone on the
  same LAN.

## Suggested workflow for the next session

1. Read this review end-to-end.
2. Triage: which items do you accept? push back on? defer?
3. Apply the High-priority items (1-4) first; bundle into 2-3
   focused commits.
4. Then Medium-priority (5-8) as a second pass.
5. Low-priority (9-15) opportunistically.
6. **Ping Bryan when ready** so he can have me re-review.

## A note on commit-message voice

Bryan caught me writing "a reader found …" in an `unspooled`
commit when in fact he was the one who found the thing. The
convention going forward across his repos:

* Use **"we"** for joint discoveries / decisions.
* Use **"Bryan"** when crediting his specific contribution.
* Use **"I noticed"** / **"I changed"** for the agent's own
  observations and edits.
* **Never** use phrasing that implies a third-party reporter
  ("a user reported", "a reader found", "an external
  contributor noted") unless it's literally true.

This applies to commit messages, doc updates, release notes,
README narratives, and anything else committed to a Bryan-owned
repo.
