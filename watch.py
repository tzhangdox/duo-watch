#!/usr/bin/env python3
"""Watch Duo Stock for iPhone Duo pickup availability and push to ntfy when it changes.

Read-only: one GET to the Duo Stock API per run. It never touches Apple's site
and never buys or reserves anything. Standard library only, no installs needed.

Configured with environment variables (see the workflow file):
  WATCH_AREA           Name used in alerts, e.g. "Sacramento"
  WATCH_ZIP            ZIP code to search around
  WATCH_RADIUS_MILES   Straight-line radius from the ZIP's center
  WATCH_PART_NUMBERS   Comma-separated Apple part numbers to watch
  WATCH_STORAGE_GB     Optional size filter sent to the tracker (e.g. 256)
  WATCH_STORE_IDS      Optional comma-separated store IDs; empty = any store in the radius
  NTFY_TOPIC           ntfy topic that receives the alerts
  STATE_FILE           Where this watch remembers what it has already alerted on
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


API_URL = "https://duo-checker.on-forge.com/api/v1/nearby"
ZIP = os.environ.get("WATCH_ZIP", "95831")
AREA = os.environ.get("WATCH_AREA", ZIP)
RADIUS_MILES = os.environ.get("WATCH_RADIUS_MILES", "50")
PART_NUMBERS = set(env_list("WATCH_PART_NUMBERS", "MK1F4LL/A"))  # default: Night Sky 256GB
STORAGE_GB = os.environ.get("WATCH_STORAGE_GB", "").strip()
STORE_IDS = set(env_list("WATCH_STORE_IDS"))
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
PACIFIC = ZoneInfo("America/Los_Angeles")

# Errors worth shrugging off: the next run 20 minutes later will try again.
TRANSIENT_HTTP = {429, 500, 502, 503, 504}


def fetch_nearby():
    """Return the tracker's /nearby response, or None if it's temporarily unavailable."""
    params = {"zip": ZIP, "radius_miles": RADIUS_MILES, "available_only": 1, "limit": 50}
    if len(PART_NUMBERS) == 1:
        params["part_number"] = next(iter(PART_NUMBERS))
    elif STORAGE_GB:
        params["storage_gb"] = STORAGE_GB
    request = urllib.request.Request(
        f"{API_URL}?{urllib.parse.urlencode(params)}",
        headers={
            "Accept": "application/json",
            "User-Agent": "duo-watch/1.1 (personal watcher, one request per 20 min)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in TRANSIENT_HTTP:
            print(f"Tracker returned HTTP {error.code}; skipping this run.")
            return None
        detail = error.read().decode("utf-8", "replace")[:500]
        sys.exit(f"Tracker returned HTTP {error.code}: {detail}")
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"Could not reach the tracker ({error}); skipping this run.")
        return None


def variant_label(product):
    color, storage = product.get("color"), product.get("storage_label")
    if color and storage:
        return f"{color} {storage}"
    return product.get("part_number", "unknown variant")


def available_listings(data):
    """Map "store_id:part_number" -> details for every watched store/variant showing available."""
    found = {}
    for store in data.get("stores") or []:
        store_id = store.get("store_id")
        if not store_id or (STORE_IDS and store_id not in STORE_IDS):
            continue
        for product in store.get("products") or []:
            part = product.get("part_number")
            if part in PART_NUMBERS and product.get("pickup_status") == "available":
                found[f"{store_id}:{part}"] = {
                    "name": store.get("name") or store_id,
                    "city": store.get("city") or "",
                    "distance_miles": store.get("distance_miles"),
                    "variant": variant_label(product),
                    "message": product.get("pickup_message") or "Available",
                    "url": store.get("url") or store.get("page_url") or "",
                }
    return found


def load_state():
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f).get("available", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_state(keys):
    with open(STATE_FILE, "w") as f:
        json.dump({"available": sorted(keys)}, f, indent=2)
        f.write("\n")


def pacific_time(iso_timestamp):
    if not iso_timestamp:
        return "an unknown time"
    moment = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00")).astimezone(PACIFIC)
    return moment.strftime("%-I:%M %p %Z, %a %b %-d")


def notify(title, body, click_url=""):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        sys.exit("NTFY_TOPIC is not set for this watch. Add the repository secret it uses.")
    headers = {"Title": title, "Priority": "high", "Tags": "iphone"}
    if click_url:
        headers["Click"] = click_url
    request = urllib.request.Request(
        f"{NTFY_SERVER}/{urllib.parse.quote(topic, safe='')}",
        data=body.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def distance_label(miles):
    return f"{miles:.0f} mi" if isinstance(miles, (int, float)) else "distance unknown"


def main():
    if os.environ.get("SEND_TEST", "").lower() == "true":
        notify(
            f"Duo watch test ({AREA})",
            f"Test from the iPhone Duo watcher for {AREA}. If you can read this, alerts will reach this phone.",
        )
        print(f"Sent a test notification for {AREA}.")
        return

    data = fetch_nearby()
    if data is None:
        return

    checked = pacific_time(data.get("run_finished_at"))
    now_available = available_listings(data)
    previous = load_state()
    newly_available = {key: item for key, item in now_available.items() if key not in previous}

    if newly_available:
        items = sorted(
            newly_available.values(),
            key=lambda s: s["distance_miles"] if isinstance(s["distance_miles"], (int, float)) else float("inf"),
        )
        variants = sorted({item["variant"] for item in items})
        lines = [
            f"• Apple {s['name']} ({s['city']}) — {s['variant']} — {distance_label(s['distance_miles'])} — {s['message']}"
            for s in items
        ]
        body = (
            "iPhone Duo is showing available for pickup:\n"
            + "\n".join(lines)
            + f"\n\nTracker checked at {checked}. Order on apple.com or in the Apple Store app and "
            "choose in-store pickup. This is an unofficial tracker, not a stock count."
        )
        if data.get("is_stale"):
            body += "\nHeads up: the tracker marked this data as stale."
        # Alert first, save state after, so a failed push gets retried next run.
        notify(f"iPhone Duo {' / '.join(variants)} available near {AREA}", body, click_url=items[0]["url"])
        print(f"ALERT SENT ({AREA}): {len(newly_available)} newly available listing(s).\n{body}")
    elif now_available:
        print(f"{AREA}: still available at {len(now_available)} listing(s) already alerted on (checked {checked}).")
    else:
        where = f"at the {len(STORE_IDS)} watched stores" if STORE_IDS else f"within {RADIUS_MILES} mi of {ZIP}"
        print(f"{AREA}: nothing available {where} (checked {checked}).")

    if set(now_available) != previous:
        save_state(now_available.keys())


if __name__ == "__main__":
    main()
