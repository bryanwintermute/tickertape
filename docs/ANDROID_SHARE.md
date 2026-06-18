# Android Share Sheet Support

Send content from Android straight to Tickertape. Which method works
depends on your **browser**, because the "appears in the Android share
sheet" feature is a browser capability, not something Tickertape can
force on its own.

## Why Tickertape shows up from Chrome but not Firefox

The share-sheet entry comes from the **Web Share Target API** (the
`share_target` block in `manifest.json`). Support is split:

| Browser (Android) | Installs as PWA | Appears in share sheet |
|---|---|---|
| Chrome / Edge / Samsung Internet (Chromium) | ✅ | ✅ |
| **Firefox / Firefox Beta (GeckoView)** | ✅ | ❌ **not supported** |

As of 2026, Firefox for Android / GeckoView **do not implement
`share_target`** — they silently ignore it. (This is different from the
*outgoing* Web Share API, `navigator.share()`, which Firefox does
support.) There is no manifest change that fixes this; it requires
Firefox to ship the feature. So:

- **Want the share sheet to "just work"?** Install the PWA with **Chrome**
  (Method 1). You can keep Firefox as your daily browser and install this
  one app via Chrome.
- **Want it independent of which browser you use?** Use **Method 2** — an
  automation app that POSTs to the API directly. No PWA, no browser
  involved.

---

## Method 1: Web Share Target (PWA, Chromium browsers)

1. Open the site in **Chrome** and choose **Install app / Add to Home
   screen**.
2. Highlight text (or use any app's **Share** button).
3. Tap **Share**, then tap **Tickertape**.
4. Tickertape opens with the content pre-filled in the Markdown tab,
   ready to adjust and **Print**.

This relies on the `share_target` manifest entry (GET to `/` with
`title` / `text` / `url` params, which the UI reads to pre-fill).

---

## Method 2: Automation app → direct API (any browser, one tap)

This is the Android analog of the iOS "Apple Shortcuts (Direct Print)"
method. It registers a share-sheet entry backed by an HTTP request, so it
works regardless of your browser and prints instantly without opening the
UI. Two good apps: **HTTP Shortcuts** (free, open-source) or **Tasker**.

### Using HTTP Shortcuts

1. Install **HTTP Shortcuts** from the Play Store / F-Droid.
2. Create a new shortcut:
   - **Method:** `POST`
   - **URL:** `http://<tickertape-host>:8000/api/print`
     (your LAN IP/hostname, or the Wireguard-reachable address, e.g.
     `http://tickerbox:8000/api/print`).
   - **Request body / Content type:** `application/json`
   - **Body:**
     ```json
     {"type": "echo", "title": "Shared", "text": "{shared_text}"}
     ```
     Insert the **shared text** variable where `{shared_text}` is. In
     HTTP Shortcuts, enable the shortcut as a **share target** and use the
     built-in shared-text variable.
3. In the shortcut's settings, turn on **"Show in share sheet"** (accept
   Text / URLs).
4. Save as **"Print to Tickertape"**.

> **JSON-escaping caveat.** The shared text must be valid JSON (quotes,
> newlines, and backslashes escaped). HTTP Shortcuts inserts variables
> *literally*, so a shared snippet containing `"` will break the body.
> Mitigations:
> - Use HTTP Shortcuts' JSON-body editor (it can escape inserted
>   variables), or its `{{"variable" | jsonencode}}`-style formatting if
>   your version supports it.
> - In **Tasker**, run the text through a `Variable Convert → JSON
>   Encode` (or a small JavaScriptlet `JSON.stringify(text)`) before
>   building the body.
> - See the "Optional server-side simplification" note below for a way to
>   avoid JSON entirely.

### API contract (for any client)

```
POST /api/print
Content-Type: application/json

{
  "type": "echo",          // "echo" (markdown/plain text), "list", or "reminder"
  "title": "Shared",       // optional header on the receipt
  "text": "<your text>",   // for type "echo": the body, rendered as markdown
  "idempotency_key": "..." // optional; auto-generated if omitted
}
```
For `type: "list"`, send `items: [...]` and optional `style`
(`checkbox` / `bullet` / `numbered`) instead of `text`.

A successful enqueue returns JSON with the job id; the worker prints it
on the next poll.

> **Optional server-side simplification (future enhancement).** Adding a
> `GET /api/share?text=...&title=...` endpoint that enqueues an `echo`
> job would let any share integration be a plain URL-encoded GET — no
> JSON escaping at all. Not implemented yet; noted here for when share
> automation gets heavier.

---

## Method 3: TWA wrapper (true native share target)

For a *real*, browser-independent share-sheet entry — one that behaves
like a native app and doesn't depend on Chrome being the installer —
wrap Tickertape in a **Trusted Web Activity (TWA)**:

1. Use **Bubblewrap** (`@bubblewrap/cli`) to generate a TWA project from
   the `manifest.json`.
2. Add a native **`ACTION_SEND` intent filter** to the Android manifest
   so the app registers as a share target, and forward the shared
   `EXTRA_TEXT` to Tickertape (either open the PWA with the text, or POST
   to `/api/print`).
3. Set up **Digital Asset Links** (`assetlinks.json`) so the TWA opens
   without a browser chrome bar.
4. Build, sign, and sideload (or publish) the APK.

This is a genuine mini-project (APK signing, asset links, a release
pipeline). Only worth it if you want a polished, browser-agnostic native
share target. For personal use, **Method 1 (Chrome) or Method 2
(automation app)** are far less effort.

---

## See also

- [`IOS_SHORTCUTS.md`](./IOS_SHORTCUTS.md) — the iOS equivalents (Web
  Share Target + Apple Shortcuts direct-print).
