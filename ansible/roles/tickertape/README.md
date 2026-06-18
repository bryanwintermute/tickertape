# tickertape role

Deploys the [tickertape](https://github.com/bryanwintermute/tickertape)
web UI + print worker to a Debian / Raspberry Pi OS host as two
systemd services.

This role lives **in the tickertape repo** (co-located with the app it
deploys) and is intended to be consumed from elsewhere (e.g. a homelab
`myconfigs` Ansible tree) via `roles_path` — not copied or symlinked.
See [Consuming this role](#consuming-this-role).

## What it does

| Task | Notes |
|---|---|
| Installs `python3`, `rsync` (apt) | tickertape is stdlib-only; no pip step. |
| rsyncs the repo working copy to `{{ tickertape_dest }}` | Excludes `.git`, `venv`, `*.db`, `ansible`, `__pycache__`. |
| Renders `tickertape.service` + `tickertape-worker.service` | Parameterized units (user, paths, python, printer device). |
| Enables + starts both services | Toggle with `tickertape_manage_services`. |

## Deploy model — and why it's rsync, not git clone

`printer-host` (the sibling role that provisions the printer) deploys
`unspooled` by **git-cloning it on the target**, because unspooled is
public. tickertape is **private**, so a target-side clone would need a
deploy key or token on every host.

Instead, this role **pushes the working copy of the repo it lives in**
to the target with `rsync` (`ansible.posix.synchronize`). The source is
discovered relative to the role's own location (`role_path`), so there's
no hardcoded path and no dependency on a specific `$HOME` — whoever has
the repo checked out can deploy it.

Trade-off: rsync ships your **working tree**, including uncommitted
changes. For a clean committed deploy, commit + push first, or point
`tickertape_src_dir` at a fresh clone.

> **The live SQLite queue is protected.** `*.db` is in the rsync
> excludes, and rsync `--delete` does not remove excluded files on the
> target — so a deploy never clobbers the production queue. This is the
> fix for a real incident; see
> `myconfigs/copilot/lessons/rsync-sqlite-deployment-footgun.md`.

## Requirements

- **Target:** Debian-family (Raspberry Pi OS Bookworm/Trixie tested).
- **Controller:** `rsync` installed (for `synchronize`).
- **Collection:** `ansible.posix` (for `synchronize`). Add it to the
  consuming project's `requirements.yml`:
  ```yaml
  collections:
    - name: ansible.posix
  ```
- **Printer wiring:** run the `printer-host` role first (or otherwise
  provide `/dev/rongta-receipt` + a user in `plugdev`). The worker
  writes ESC/POS bytes to `{{ tickertape_printer_device }}`.

## Variables

See [`defaults/main.yml`](defaults/main.yml) for the annotated list. The
common ones:

| Variable | Default | Purpose |
|---|---|---|
| `tickertape_user` | `{{ ansible_user_id }}` | Service `User=` + deploy owner. |
| `tickertape_dest` | `/home/{{ tickertape_user }}/github/tickertape` | Where the app lands on the target. |
| `tickertape_src_dir` | repo root via `role_path` | Source checkout to deploy. |
| `tickertape_python` | `/usr/bin/python3` | Interpreter for the services. |
| `tickertape_printer_device` | `/dev/rongta-receipt` | `PRINTER_DEVICE` for the worker. |
| `tickertape_manage_services` | `true` | Enable/start (false = deploy only). |
| `tickertape_rsync_excludes` | `.git`, `venv`, `*.db`, … | Protects the live DB + trims payload. |

## Consuming this role

The role lives in this repo at `ansible/roles/tickertape`. To use it from
another Ansible project (e.g. `myconfigs`) **without copying or
symlinking**, add the path to that project's `ansible.cfg` `roles_path`
(relative, assuming sibling checkouts):

```ini
# myconfigs/ansible/ansible.cfg
[defaults]
roles_path = ./roles:../../tickertape/ansible/roles
```

Then reference it from a play:

```yaml
- name: Configure tickertape hosts
  hosts: tickertape_hosts
  roles:
    - role: printer-host    # provides /dev/rongta-receipt + plugdev
    - role: tickertape      # deploys the app + services
```

If the repos are **not** sibling-checked-out, either adjust the relative
path, use a git submodule, or set `tickertape_src_dir` explicitly.

## Usage

```bash
# From the consuming project (e.g. myconfigs/ansible):
ansible-playbook -i inventory.local.yml site.yml --tags tickertape -K

# Deploy code + units but don't touch services:
ansible-playbook ... --tags tickertape -e tickertape_manage_services=false -K
```

## What this role deliberately does NOT do

- **Provision the printer.** That's `printer-host` (udev rule, plugdev,
  persistent journald). Run it first.
- **Install Python dependencies.** tickertape is stdlib-only by design.
- **Manage a reverse proxy / TLS.** The service binds a plain HTTP port;
  front it with your own proxy if you expose it beyond the LAN.
- **Clone from GitHub on the target.** See the deploy-model section.
