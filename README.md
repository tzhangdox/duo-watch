# iPhone Duo watch

Checks [Duo Stock](https://duo-checker.on-forge.com/agents) every 20 minutes for
iPhone Duo online pickup availability and sends a push through [ntfy](https://ntfy.sh)
only when a store/variant newly shows as available. Runs on GitHub Actions, so no
computer needs to stay on.

| Watch | What | Where | Alerts go to |
|---|---|---|---|
| Sacramento | Night Sky 256GB | Any store within 50 mi of 95831 | `NTFY_TOPIC` secret |
| Oakland/SF | 256GB, either color | Union Square, Chestnut Street, Bay Street, 4th Street, Broadway Plaza, Stoneridge Mall | `NTFY_TOPIC_OAKLAND` secret |

Read-only: one request per watch per run to an unofficial tracker. It never touches
Apple's site and never buys anything. When an alert arrives, order on apple.com or
in the Apple Store app with in-store pickup, and confirm availability there.

## Setup

1. Install the ntfy app on each phone that should get alerts and subscribe to the
   right topic name. Anyone who knows a topic name can read it, so keep it random.
2. Add a repository secret for each watch's topic (`NTFY_TOPIC`, `NTFY_TOPIC_OAKLAND`).
3. Run **iPhone Duo watch** from the Actions tab with "Send a test push" checked.
   Each subscribed phone should buzz.

## Changing a watch

Edit the `env:` block of its step in `.github/workflows/duo-watch.yml`:
`WATCH_AREA`, `WATCH_ZIP`, `WATCH_RADIUS_MILES`, `WATCH_PART_NUMBERS` (comma-separated),
`WATCH_STORAGE_GB`, `WATCH_STORE_IDS` (comma-separated; empty means any store in the
radius), `STATE_FILE`. Part numbers are on the tracker's agents page; store IDs are
in its store links (for example `/stores/R075`).

## Stopping

Delete a watch's step to stop just that one. To stop everything, disable the
workflow in the Actions tab (or `gh workflow disable "iPhone Duo watch"`), or delete
the repo.
