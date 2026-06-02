# tickertape — project handoff brief (rev. 2026-06-02)

This file is a current-state brief for the next session working on
tickertape. It's NOT a from-scratch design brief any more — v0 is
shipped, deployed-ready, and printing. The job now is to consume
new upstream features, ship to the dedicated printer host, and
harden the app for **actual daily use** (Bryan's phrasing,
2026-06-02).

The original "starting from scratch" brief is preserved as
`HANDOFF.md.v0-stale.bak` for archaeology.

The author of this rev is the Copilot CLI session that:
- shipped `unspooled` v0.3.0 (the upstream renderer + Rongta CLI),
- provisioned the new printer host (`tickerbox`) via Ansible,
- and wrote both committed code reviews in `docs/review-*-2026-06-01.md`.

---

## TL;DR — what changed in the last 24 hours

1. **Gemini addressed most of round-2.** Tests are green in CI
   (`36a6e17`), the Tests and Docker workflows have been **merged
   into one file with a `needs: test` gate** so the publish step
   no longer runs on red, the Node-20 actions have been bumped to
   current (`actions/checkout@v4`, `actions/setup-python@v5`, etc.),
   the accidentally-committed `.antigravitycli/` symlink was
   removed and added to `.gitignore`, the stray `resolving` file
   was deleted, and the round-1 review was renamed to a dated doc
   under `docs/`. The `db.py` per-call-connection issue that broke
   `:memory:` tests was fixed via a refactor + `DB_PATH` test patch.
   Solid pass. See `docs/review-2-2026-06-01.md` for the original
   triage list; most rows can be marked ✅ now.

2. **The deploy target moved.** Tickertape now runs on `tickerbox`
   (a dedicated Pi 3B+ provisioned with Pi OS Lite Bookworm), not
   `octoprint`. The Rongta RP332 is plugged into `tickerbox` via
   USB; the udev rule + group + persistent-journald + unspooled
   clone are all in place via the new `printer-host` Ansible role
   at `~/github/myconfigs/ansible/roles/printer-host/`. tickertape's
   `tickertape.service` / `tickertape-worker.service` need to land
   on `tickerbox` next.

3. **Upstream shipped two features that obsolete code in this repo.**
   `unspooled` v0.3.0 (2026-06-02, commit `f22020b`) added:
   - **`sanitize()` with a built-in NFKD + smart-quote / em-dash /
     ellipsis / arrow translation table**, default-on. `Receipt(...)`
     and the new `render_markdown(...)` both run input through it
     unless you pass `sanitize=False`. **This makes
     `worker.sanitize_text()` redundant** — drop it and let upstream
     handle it.
   - **`render_markdown(text, **kwargs) -> bytes`** plus
     `Receipt.from_markdown()`. Stdlib regex tokenizer for a
     constrained CommonMark subset (H1/H2/H3, `**bold**`, bullet /
     numbered / checkbox lists, `---` HR, paragraphs). This is the
     piece tickertape's web UI has been missing — users can now
     enter markdown and have it rendered with headings, bold, and
     mixed list styles on a single receipt.

4. **The vendored copy is stale.** `_vendored/receipt_print.py`
   header says `v0.2.0 (commit bc19427)`. Bump to **v0.3.0
   (commit f22020b)** and re-test. v0.2.0 byte-equality contract
   for ASCII-only input is preserved upstream, so existing
   byte-equality tests will still pass after the swap; the new
   capabilities just become available to call.

---

## Where things stand right now

### Code state

```
~/github/tickertape/
├── server.py            # HTTP server: web UI + /api/print endpoint
├── worker.py            # SQLite-queue poller; has sanitize_text() (now redundant)
├── db.py                # refactored for test isolation (round-2 ✅)
├── cli.py               # client wrapper around urllib
├── web/                 # mobile-friendly form
├── _vendored/
│   └── receipt_print.py # v0.2.0 (bc19427) ← BUMP to v0.3.0 (f22020b)
├── tests/               # GREEN as of 36a6e17
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.example.yml
├── Dockerfile
├── tickertape.service
├── tickertape-worker.service
├── .github/workflows/
│   └── docker-publish.yml   # merged test+build, needs: test gate (round-2 ✅)
└── docs/
    ├── HANDOFF.md                  ← this file
    ├── HANDOFF.md.v0-stale.bak     ← original from-scratch brief
    ├── implementation_plan.md
    ├── review-1-2026-06-01.md
    └── review-2-2026-06-01.md
```

### Hardware / network

- **Printer host:** `tickerbox` (Pi 3B+, Pi OS Lite Bookworm, 1 GB RAM).
- **Pi user:** `bryan`, in groups `plugdev`, `lp`, `dialout`.
- **Printer:** Rongta RP332 plugged into `tickerbox` USB; udev rule
  `99-rongta-receipt.rules` pins `/dev/rongta-receipt → /dev/usb/lp0`
  with mode `0660`, group `plugdev`.
- **Network:** LAN-only. Bryan reaches the host externally via the
  Wireguard endpoint on his OPNSense gateway — **no Tailscale on
  this host**, no inbound auth required at the app layer (yet).
- **unspooled clone:** `~/github/unspooled` on `tickerbox`, currently
  at v0.3.0 (`git pull` keeps it fresh).
- **Old `octoprint` host:** still alive but no longer the printer
  home. Don't put tickertape there.

---

## What the next session should do, in order

These are **concrete, sequenced, and small** — designed to be done
in one or two sittings.

### 1. Bump `_vendored/receipt_print.py` to v0.3.0

```bash
cp ~/github/unspooled/receipt_print.py _vendored/receipt_print.py
# Then update the vendor header (top of file) to read:
#   # Vendored from https://github.com/bryanwintermute/unspooled
#   # at v0.3.0 (commit f22020b). DO NOT EDIT locally; refresh by
#   # re-vendoring from upstream.
```

Run `pytest tests/` — should still pass. v0.3.0 preserves the v0.2.0
byte contract for ASCII-only input; existing byte-equality tests
won't see any difference.

### 2. Drop `worker.sanitize_text()`

Upstream's `Receipt(sanitize=True)` (default) replaces it entirely
**and** has a more complete map (arrows, NFKD-based accent stripping,
configurable extension). Delete the local function and remove the
wrapping `sanitize_text(...)` calls in `process_job()`. Receipt will
sanitize automatically.

If the local map has any entries that aren't in
`DEFAULT_SANITIZE_MAP` (check by importing it from the new vendored
copy), contribute them upstream as a one-line PR extending the map
(then re-vendor). Don't duplicate.

### 3. Expose markdown in the web UI

The biggest user-facing v0.3.0 win. Two paths:

**Path A (smaller):** add a request-type. The web form gets a
"Markdown" mode toggle; the API accepts
`POST /api/print` with `{ "type": "markdown", "markdown": "..." }`,
the worker calls `render_markdown(payload["markdown"], title=...)`.
Existing `type: list` and `type: echo` paths keep working unchanged.

**Path B (more ambitious):** make markdown the *default* parser.
A plain bullet list `- milk\n- eggs` already renders correctly under
`render_markdown` (CommonMark says so), so most existing UX still
works. Headings + bold + checkboxes "just work" without a mode
toggle. Plain text without markdown syntax wraps as a paragraph.

Recommend Path B for ergonomics, Path A if you want to keep the v0
API contract literally stable.

### 4. Deploy to `tickerbox`

The Ansible `printer-host` role gets the host ready; tickertape needs
its own minimal deploy step. Two paths:

- **Quick**: scp the systemd unit files + clone the repo + `systemctl daemon-reload`
  + `enable --now tickertape.service tickertape-worker.service`. Document in
  README.
- **Better (later)**: add a `tickertape` Ansible role under
  `~/github/myconfigs/ansible/roles/` that runs alongside
  `printer-host`. Sequence: `printer-host` (already done) →
  `tickertape` (clones repo, runs containers or systemd units, opens
  firewall on the right port).

Either way, **don't put tickertape on `octoprint` any more**.

### 5. Productionize for daily use (Bryan's stated 2026-06-02 goal)

Once 1–4 land, the things that make this "actually daily-usable"
rather than "demo-able":

- **Persistent web UI URL** Bryan can pin on his phone home screen.
  Easiest: serve a `manifest.json` + decent app icon so iOS / Android
  install it as a PWA. (Bonus: install prompt.)
- **Retry / backoff** on print failures (paper out, USB unplugged) —
  worker currently swallows the error and logs. Mark the job
  `failed_retriable`; surface state in the UI ("printer offline,
  queued"). Worker already has crashed-job recovery from round-2;
  this extends it.
- **Job history** view: see the last N prints, retry on demand.
  SQLite already retains them; just add a list view.
- **Templates / favorites**: "today's shopping list" preset, "morning
  routine" preset. Bryan's original use case was shopping lists;
  treat that path as the polished happy-case.

---

## Open design questions still worth Bryan's input

These were on the v0 brief but haven't been resolved:

1. **Auth**: tickertape is LAN-only behind Wireguard, so the app
   itself currently has no auth. Should we add a shared-secret /
   single-user login before adding a mobile bookmark, or trust the
   network boundary?
2. **Multi-printer**: schema has room for a `printer:` field but only
   one printer exists. Decide whether to model "printer" as
   first-class now or punt to when a second one shows up.
3. **Concurrent prints**: the worker is serial (one printer), so
   the queue model is already correct. But: do we want a "rush"
   priority lane? (Probably no — overengineering.)

---

## Repo conventions (carry-over from upstream)

Same as the original brief; restating because Antigravity/Gemini
sometimes ignores stored memory across sessions:

- **Commit voice:** never use "a reader found" / "a user reported"
  for things Bryan did. Use "we" / "Bryan" / "I noticed". This is
  in Copilot Memory but worth restating.
- **Test discipline:** byte-equality tests are the contract for
  anything that emits printer bytes. Don't lower this bar. (And
  good job keeping CI green — don't let it regress.)
- **No third-party deps unless absolutely necessary.** Stdlib-first
  is the upstream convention and the right one here too. The
  current Dockerfile is stdlib-only — keep it that way.
- **Issue references in commit messages:** if a commit closes a
  review item, cite it (`addresses round-2 #4` etc.) so future
  reviewers can verify coverage.

---

## What this brief deliberately doesn't decide

- Tickertape's UI polish (font, theme, color)
- Whether to publish tickertape as OSS (still private)
- Whether to migrate the stack to a different language

These remain Bryan's calls; nothing forces them now.

---

## Pointers for the next session

- **`~/github/tickertape/docs/review-2-2026-06-01.md`** — the
  triage list. Most rows are ✅ now after the last work block;
  worth reading the headers to verify nothing's been missed.
- **`~/github/tickertape/docs/review-1-2026-06-01.md`** — the prior
  round, for context.
- **`~/github/unspooled/README.md`** — v0.3.0 API surface, including
  the new `render_markdown()` and `sanitize=` argument shapes.
- **`~/github/unspooled/releases/tag/v0.3.0`** — release notes for
  the upstream features tickertape should now consume.
- **`~/github/myconfigs/ansible/roles/printer-host/README.md`** —
  what's already deployed on `tickerbox` (you don't need to
  reinstall any of this; just clone tickertape and run its
  service units).
- **`~/github/myconfigs/copilot/lessons/antigravity-gemini-as-coding-sidekick.md`**
  — Bryan's notes on how to work with you (Gemini/Antigravity)
  effectively; worth a skim if you're a fresh session.

Synced as of 2026-06-02 04:36 PT.
