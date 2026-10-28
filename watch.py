#!/usr/bin/env python3
"""Watch Duo Stock for iPhone Duo pickup availability and push to ntfy when it changes.

Read-only: one GET to the Duo Stock API per run. It never touches Apple's site
and never buys or reserves anything. Standard library only, no installs needed.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

API_URL = "https://duo-checker.on-forge.com/api/v1/nearby"
ZIP = os.environ.get("WATCH_ZIP", "95831")
PART_NUMBER = os.environ.get("WATCH_PART_NUMBER", "MK1F4LL/A")  # iPhone Duo, Night Sky, 256GB
VARIANT = os.environ.get("WATCH_VARIANT_LABEL", "iPhone Duo Night Sky 256GB")
RADIUS_MILES = os.environ.get("WATCH_RADIUS_MILES", "50")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
PACIFIC = ZoneInfo("America/Los_Angeles")

# Errors worth shrugging off: the next run 20 minutes later will try again.
TRANSIENT_HTTP = {429, 500, 502, 503, 504}


def fetch_nearby():
    """Return the tracker's /nearby response, or None if it's temporarily unavailable."""
    query = urllib.parse.urlencode({
        "zip": ZIP,
        "part_number": PART_NUMBER,
        "radius_miles": RADIUS_MILES,
        "available_only": 1,
    })
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": "duo-watch/1.0 (personal watcher, one request per 20 min)",
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


def available_stores(data):
    """Map store_id -> details for every store showing the watched part as available."""
    found = {}
    for store in data.get("stores") or []:
        for product in store.get("products") or []:
            if product.get("part_number") == PART_NUMBER and product.get("pickup_status") == "available":
                found[store["store_id"]] = {
                    "name": store.get("name") or store["store_id"],
                    "city": store.get("city") or "",
                    "distance_miles": store.get("distance_miles"),
                    "message": product.get("pickup_message") or "Available",
                    "url": store.get("url") or store.get("page_url") or "",
                }
    return found


def load_state():
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f).get("available_store_ids", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_state(store_ids):
    with open(STATE_FILE, "w") as f:
        json.dump({"available_store_ids": sorted(store_ids)}, f, indent=2)
        f.write("\n")


def pacific_time(iso_timestamp):
    if not iso_timestamp:
        return "an unknown time"
    moment = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00")).astimezone(PACIFIC)
    return moment.strftime("%-I:%M %p %Z, %a %b %-d")


def notify(title, body, click_url=""):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        sys.exit("NTFY_TOPIC is not set. Add it as a repository secret.")
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
            "Duo watch test",
            f"Test from the {VARIANT} watcher for {ZIP}. If you can read this, alerts will reach this phone.",
        )
        print("Sent a test notification.")
        return

    data = fetch_nearby()
    if data is None:
        return

    checked = pacific_time(data.get("run_finished_at"))
    now_available = available_stores(data)
    previous = load_state()
    newly_available = {sid: s for sid, s in now_available.items() if sid not in previous}

    if newly_available:
        stores = sorted(
            newly_available.values(),
            key=lambda s: s["distance_miles"] if isinstance(s["distance_miles"], (int, float)) else float("inf"),
        )
        lines = [
            f"• Apple {s['name']} ({s['city']}) — {distance_label(s['distance_miles'])} — {s['message']}"
            for s in stores
        ]
        body = (
            f"{VARIANT} is showing available for pickup:\n"
            + "\n".join(lines)
            + f"\n\nTracker checked at {checked}. Confirm on apple.com before heading over; "
            "this is an unofficial tracker, not a stock count."
        )
        if data.get("is_stale"):
            body += "\nHeads up: the tracker marked this data as stale."
        # Alert first, save state after, so a failed push gets retried next run.
        notify(f"{VARIANT} available near {ZIP}", body, click_url=stores[0]["url"])
        print(f"ALERT SENT: {len(newly_available)} newly available store(s).\n{body}")
    elif now_available:
        print(f"Still available at {len(now_available)} store(s) already alerted on (checked {checked}).")
    else:
        print(f"Nothing available within {RADIUS_MILES} mi of {ZIP} (checked {checked}).")

    if set(now_available) != previous:
        save_state(now_available.keys())


if __name__ == "__main__":
    main()
