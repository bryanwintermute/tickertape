# Re-vendor unspooled v0.3.1

**Date:** 2026-06-02
**Reason:** Upstream patch fix for the fraction-spacing bug in v0.3.0.
**Estimated work:** ~10 minutes including verification.

## What changed upstream

`unspooled` v0.3.1 ([release notes](https://github.com/bryanwintermute/unspooled/releases/tag/v0.3.1))
fixes `sanitize()` so the mixed-number convention works correctly:

| Input | v0.3.0 (current) | v0.3.1 (target) |
|---|---|---|
| `"1¼ cups"` | `"11/4 cups"` ❌ | `"1 1/4 cups"` ✅ |
| `"10½ oz"` | `"101/2 oz"` ❌ | `"10 1/2 oz"` ✅ |
| `"½ off"` | `"1/2 off"` ✅ | `"1/2 off"` ✅ (unchanged) |
| `"5×3"` | `"5x3"` ✅ | `"5x3"` ✅ (unchanged) |

This matters for the markdown-mode tickertape UI Bryan just deployed
to `tickerbox` — any user typing a recipe-style "1¼ cup flour"
currently prints as "11/4 cup flour".

The fix is a regex pre-pass that inserts a space between an ASCII
digit and an adjacent Unicode fraction character (Latin-1
`\u00BC-\u00BE` + the `\u2150-\u215E` Number Forms block).

The v0.3.0 byte-equality contract is preserved for any input that
doesn't contain digit-adjacent fractions — only the previously-broken
cases change.

## Re-vendor steps

```bash
cd ~/github/tickertape

# 1. Copy the new upstream file in.
cp ~/github/unspooled/receipt_print.py _vendored/receipt_print.py

# 2. Update the vendor header (the first 4 lines of the file).
#    Replace the v0.3.0 marker with:
#
#      #!/usr/bin/env python3
#      # Vendored from https://github.com/bryanwintermute/unspooled
#      # at v0.3.1 (commit 42db0ba). DO NOT EDIT locally; refresh by
#      # re-vendoring from upstream.
#
#    Then drop the upstream shebang line that follows so the file
#    keeps just one header block.

# 3. Verify the fix locally.
~/github/myconfigs/ansible/.venv/bin/python -c "
from _vendored.receipt_print import sanitize
assert sanitize('1\u00BC cups') == '1 1/4 cups', f'fix not applied: got {sanitize(chr(0x31)+chr(0xBC)+chr(0x20)+\"cups\")!r}'
assert sanitize('\u00BD off') == '1/2 off', 'standalone fraction regressed'
assert sanitize('5\u00D73') == '5x3', 'non-fraction case regressed'
print('OK: v0.3.1 fix is active in _vendored/')
"

# 4. Run tickertape's own test suite.
~/github/myconfigs/ansible/.venv/bin/python -m pytest tests/ -q

# 5. Commit.
git add _vendored/receipt_print.py
git commit -m "chore: re-vendor unspooled v0.3.1 (mixed-number spacing fix)

Bumps the vendored receipt_print.py from v0.3.0 (commit bc19427)
to v0.3.1 (commit 42db0ba). The only behavioral change is in
sanitize(): mixed-number forms like \"1¼ cups\" now render as
\"1 1/4 cups\" (correct) instead of \"11/4 cups\" (broken). All
other byte-equality contracts are preserved.

See https://github.com/bryanwintermute/unspooled/releases/tag/v0.3.1.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

# 6. Push and deploy.
git push

# 7. Re-deploy to tickerbox. IMPORTANT: exclude the SQLite DB
#    (lesson learned the hard way last night — see
#    ~/github/myconfigs/copilot/lessons/rsync-sqlite-deployment-footgun.md).
rsync -avz --exclude '.git' --exclude 'venv' --exclude '*.db' \
  ~/github/tickertape/ tickerbox:~/github/tickertape/
ssh tickerbox 'sudo systemctl restart tickertape-worker tickertape'
```

## Verification on tickerbox

Before declaring done, send a test print containing a mixed-number
fraction and confirm it renders with the space:

```bash
# From your dev box:
curl -X POST http://tickerbox/api/print \
  -H 'Content-Type: application/json' \
  -d '{"type":"echo","text":"# Recipe test\n\n- 1¼ cup flour\n- ½ tsp salt\n- 2¾ oz butter"}'
```

Expected on paper:
```
RECIPE TEST
-------------------------
- 1 1/4 cup flour
- 1/2 tsp salt
- 2 3/4 oz butter
-------------------------
```

If the digits and the `1/4` / `3/4` are still smashed together,
the vendor swap didn't actually land — check that `_vendored/receipt_print.py`
has `_RE_DIGIT_FRACTION` near the top of the sanitize section.

## Out of scope for this re-vendor

- **No changes to `worker.py`.** The v0.3.1 fix is purely upstream.
  `render_markdown()` and `Receipt(...)` automatically pick up the
  improved `sanitize()` behavior because they share the sanitizer.
- **No new tests in tickertape.** Upstream owns the sanitizer tests
  (109 of them as of v0.3.1). Tickertape's tests cover its own
  worker / queue logic, not the renderer.
- **No `worker.sanitize_text()`** to re-add. That was correctly
  removed in commit `8854b65`; the upstream fix is the right home
  for sanitization improvements.

## If anything goes sideways

- **Tests fail after the swap:** diff the new and old vendored files
  (`git diff HEAD _vendored/receipt_print.py`) and look for anything
  beyond the sanitize/regex changes. The only intentional changes
  between v0.3.0 and v0.3.1 are:
  - `_RE_DIGIT_FRACTION` constant added at the top of sanitize section
  - `sanitize()` calls it as the new step 0 in its pipeline
  - `import re as _re` moved to the top of the file (was later)
  - 4 new tests in `tests/test_receipt_print_library.py` (not vendored)
- **Print mangled on `tickerbox`:** confirm the service actually restarted
  (`systemctl status tickertape-worker`); if it's running the old code,
  it'll still produce the old output.
- **`sudo` denied on tickerbox:** the `bryan` user can restart services
  it owns without sudo if the unit files use `User=bryan` (they do —
  see commit `61a2eb3`). Try `systemctl --user restart` instead.
