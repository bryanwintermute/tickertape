# tickertape — project handoff brief

This file is a starting-point brief for a fresh session. It captures
what `tickertape` is meant to be, why, what's already in place
(elsewhere), what the rough architecture should be, and open
questions to resolve before writing code.

The author of this brief is the same Copilot CLI session that just
spent ~3 days reverse-engineering the Rongta RP332 thermal receipt
printer's vendor protocol into a public Python CLI called
[unspooled](https://github.com/bryanwintermute/unspooled). That
context spilled into the naming of `tickertape` (a tickertape was
the analog ancestor of every thermal receipt printer; the name
came out of brainstorming session names for `unspooled`, where
Bryan reserved `tickertape` specifically for the user-facing app).

Delete this file once the project takes shape.

## What it is

**Tickertape is the user-facing app for sending short, time-ordered
messages (to-dos, shopping lists, reminders, ad-hoc notes) to a
home-network thermal receipt printer.** Currently targeting
Bryan's Rongta RP332, plugged into the Pi at the maintainer's home,
but the architecture should be printer-agnostic where possible.

It is NOT:
- A printer driver
- An ESC/POS renderer (that's
  [`unspooled`'s `receipt_print.py`](https://github.com/bryanwintermute/unspooled/blob/main/receipt_print.py))
- A printer-config tool (that's
  [`unspooled`'s `rongta_config.py`](https://github.com/bryanwintermute/unspooled/blob/main/rongta_config.py))

It IS:
- A way to push a list / a note / a checkbox-set to the printer
  from a phone, from a laptop, from voice-assistant integration,
  from a chat client, from a cron job, …

## What's already in place

### upstream (no work needed)

- **`unspooled`** at `~/github/unspooled/` and
  https://github.com/bryanwintermute/unspooled (public, v0.1.2,
  Apache-2.0). Provides:
    - `receipt_print.py` — the stdlib ESC/POS renderer (importable
      as a module, exposes a `Receipt` class). Already supports
      `--title`, `--style {checkbox,numbered,bullet,plain}`,
      `--no-timestamp`, `--no-cut`, `--dry-run`. CP437 encoding
      with safe fallback for unsupported chars.
    - `nv_config.py`, `ethernet_config.py`, etc. — printer NV
      config. Tickertape probably shouldn't touch these directly
      but might link to the docs for setup.
- **The printer rig itself**:
    - Rongta RP332 plugged into a Pi (host = "octoprint", IP
      10.20.0.148 on Bryan's LAN). Cutter enabled, DHCP on,
      everything in known-good state.
    - udev rule pins `/dev/rongta-receipt` (mode 0660, plugdev).
    - The Pi has Python 3.9+ and `unspooled` cloned at
      `~/github/myconfigs/homelab/receipt-printer/` (or you can
      clone it fresh from GitHub on the Pi).
- **Deferred work this brief subsumes**, from the early-sessions
  plan:
    - "Phase 3 — `print-receipt` dev-box wrapper to pipe shopping
      lists from laptop → ssh → octoprint → /dev/rongta-receipt"
    - "Phase 4 — HTTP / web-share portal for send-to-printer from
      phone"
  Both of those are now properly tickertape's scope.

### downstream

- Nothing yet. `~/github/tickertape/` is empty except for an empty
  README.md. The GitHub repo is private and unused.

## High-level shape (Bryan should refine)

A reasonable v0 architecture has three layers:

1. **A printer service running on the Pi.** Wraps `unspooled` or
   imports `receipt_print` directly. Exposes:
    - A local Unix socket OR a localhost HTTP port OR (more likely)
      both via systemd socket activation.
    - Endpoints: `POST /print` with a JSON body specifying title,
      style, items, options. Maybe also `GET /status` for paper
      state.
2. **A LAN-facing API on the Pi.** Same service, additional bind
   address; authenticated (token / basic auth / Tailscale / etc).
   Stateless aside from optional spooling (queue requests if
   printer is offline; print on reconnect).
3. **Clients.** At minimum:
    - A laptop CLI `tickertape print` that posts to the service
      (Phase 3 of the old plan).
    - A mobile-friendly web UI (Phase 4 of the old plan) — a single
      page that lets you type a list and hit "send to printer".
    - Stretch: integrations with whatever Bryan already uses (Home
      Assistant for voice via Alexa? Discord webhook? cron-driven
      morning-list?).

The renderer remains `unspooled`'s `receipt_print.py`. Tickertape
adds the **transport + queuing + UI** layers; it does NOT
re-implement ESC/POS.

## Open design questions

These are the ones that should drive a brainstorm-and-decide
conversation before writing code. Ranked roughly by impact.

1. **Is the service architecture really 'a service on the Pi', or
   should the Pi just `ssh receive-and-print`?** SSH-based push is
   simpler, no auth to design, but less friendly for mobile + web
   integrations.
2. **What's the minimum interesting feature set for v0?**
    - "echo text > tickertape" — a printf for the printer
    - Shopping lists (Bryan's stated original use case)
    - Persistent reminder list ("inbox" that drains on print)
    - All of the above
3. **Phone UX**: native app? PWA? plain HTML form? The Pi's web
   service could just serve a `<form>` POSTing to `/print`. Lowest
   friction wins.
4. **Authn**: shared password / token? Tailscale tailnet-only?
   IP allowlist on the LAN? (This depends partly on how Bryan
   exposes the service.)
5. **Persistence + queueing**: if the printer is offline / out of
   paper, do requests fail, queue, or block? Where does the queue
   live? (SQLite is probably fine.)
6. **Multi-printer future-proofing**: tickertape v0 talks to
   the one Rongta RP332. Does the schema leave room for "send to
   printer X" if Bryan ever adds a second printer? (Easy yes;
   just include a `printer:` field in the request.)
7. **Concurrent prints**: what happens if two requests arrive
   simultaneously? The printer is fundamentally serial. Locking
   strategy?
8. **Idempotency**: if a request times out client-side, retrying
   could double-print. Idempotency keys? Server-side dedupe
   window?
9. **Print receipt confirmation**: does the service tell the client
   "printed successfully" or just "queued"? The Rongta has no
   reliable "I printed it" signal.
10. **Integration scope for v0**: just the CLI + web form, or also
    a webhook endpoint for Home Assistant / IFTTT-style use?

## Suggested first-session plan

1. **Brainstorm the design questions above** with Bryan (or pick
   defaults and propose them for sign-off).
2. **Sketch the data model** for a print request and any
   queue/inbox table.
3. **Decide the transport**: HTTP on the Pi seems most flexible;
   start there unless Bryan has a strong preference.
4. **Stand up a skeleton** (Pi-side HTTP service that accepts JSON
   + shells out to `unspooled`'s `receipt_print.py`, dry-run
   first, then real). Stdlib `http.server` is fine for v0; no need
   for Flask/FastAPI on day 1.
5. **Add a minimal HTML form** as the first client (single page,
   POST to `/print`, mobile-viewport). This is the "send a list
   from my phone" core use case.
6. **CLI client** (`tickertape print`) — wraps `curl -X POST`,
   reads config from `~/.config/tickertape/config.json`.

## What this brief deliberately doesn't decide

- Tickertape's UI/UX design (font, theme, color, layout)
- Hosting model (Pi-only? cloud sync? CF Tunnel? mDNS-only?)
- Whether to publish tickertape itself as OSS (currently the repo
  is private, like unspooled was at the start)
- Whether tickertape should be Python (consistent with unspooled),
  Go (single static binary on the Pi), or a JS/TS stack (better
  for the web UI half). All three have merits — pick deliberately,
  not by default.

## Carry-over context the next session won't have

A few things from the unspooled session that the next session
should know:

- **Bryan's repo conventions**: Apache-2.0 LICENSE matching
  `chimebox`. Stdlib-first / minimal-dependency Python. Each script
  has a substantial module docstring explaining wire format /
  decisions. Tests are byte-equality-ish where it makes sense.
  Issue templates + PR templates worth setting up before flipping
  public.
- **Bryan's voice in commit messages**: prefer "we"/"I"/"Bryan",
  never "a user reported" or "a reader found" (this is now in
  Copilot Memory as a convention, but worth restating in case a
  fresh session ignores memory).
- **The Rongta printer's firmware quirks** (worth knowing because
  tickertape will eventually surface error states):
    - The printer has no reliable "I printed it" feedback channel
      over USB — most "responses" come back as paper, not bytes.
    - Cutter is gated by an NV flag; if it's off, no ESC/POS
      command will cut. tickertape shouldn't assume cutting works
      until verified.
    - The printer DOES have a paper-out sensor (DLE EOT 4 query
      via ESC/POS), readable via BULK-IN on USB. If tickertape
      wants to gracefully handle "out of paper", it should use
      that.

## Where to find Bryan's running notes from this project

- `~/.copilot/session-state/fcb8743e-4bb9-454f-8a10-119111fe4545/plan.md`
  is the unspooled session's plan file; has the full RE arc, the
  state-of-the-rig snapshot, the wishlist, cleanup checklist.
- `~/github/myconfigs/copilot/lessons/rongta-rp332-vendor-tool-replacement-recap.md`
  is the same content as a committed lesson (project-recap
  flavour, less ephemeral).
- `~/github/unspooled/docs/` is the same content again, for the
  unspooled public repo's `docs/` folder.

Pick any one; they're synced as of 2026-05-27.
