# iPhone Duo watch

Checks [Duo Stock](https://duo-checker.on-forge.com/agents) every 20 minutes for an
**iPhone Duo, Night Sky, 256GB** (part `MK1F4LL/A`) available for pickup within
**50 miles of 95831**, and sends a push through [ntfy](https://ntfy.sh) only when a
store newly shows as available. Runs on GitHub Actions, so no computer needs to stay on.

Read-only: one request per run to an unofficial tracker. It never touches Apple's
site and never buys anything. Always confirm on apple.com before heading over.

## Setup

1. Install the ntfy app (iOS or Android) on each phone that should get alerts and
   subscribe to your topic name. Anyone who knows the topic name can read it, so
   keep it random.
2. Push this folder to a new GitHub repo.
3. Add a repository secret named `NTFY_TOPIC` set to the topic name.
4. In the Actions tab, run **iPhone Duo watch** with "Send a test push" checked.
   Every subscribed phone should buzz. Run it once more unchecked for a real check.

## Changing what it watches

Set these as `env:` on the "Check availability" step in
`.github/workflows/duo-watch.yml`: `WATCH_ZIP`, `WATCH_RADIUS_MILES`,
`WATCH_PART_NUMBER`, `WATCH_VARIANT_LABEL`. Part numbers are listed on the
tracker's agents page.

## Stopping

Disable the workflow in the Actions tab (or `gh workflow disable "iPhone Duo watch"`),
or delete the repo.
