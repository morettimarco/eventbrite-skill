#!/usr/bin/env python3
"""Tiny Eventbrite API v3 client for the eventbrite-event-management skill.

Standard library only. Handles the four things every raw-curl session ends up
re-implementing: auth, org-ID resolution, continuation pagination, and the
Eventbrite-API-Waypoint-Token header that makes reads see your own writes.

Usage:
  eb.py GET  /users/me/organizations/
  eb.py GET  /organizations/{org}/events/ status=all page_size=50 --all
  eb.py POST /organizations/{org}/events/ --json event.json
  eb.py POST /events/123/ --data '{"event": {"summary": "..."}}'
  eb.py DELETE /events/123/ticket_classes/456/
  eb.py org                      # print (and cache) the organization ID

Path placeholders: {org} is replaced with the resolved organization ID.
Query params: trailing key=value pairs.
--all     follow pagination and merge every page's list into one array.
--quiet   print only the JSON body (default also prints status to stderr).

Env:
  EVENTBRITE_TOKEN   personal OAuth token (required)
  EVENTBRITE_ORG_ID  optional; skips the /users/me/organizations/ lookup
  EB_BASE_URL        override the API base (only for testing against a mock)
  EB_STATE_DIR       where the waypoint token / org cache live (default ~/.cache/eb)

Exit code is 0 on 2xx, 1 otherwise; the error JSON (with its stable `error`
constant) is still printed so the caller can branch on it.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("EB_BASE_URL", "https://www.eventbriteapi.com/v3")
STATE_DIR = os.path.expanduser(os.environ.get("EB_STATE_DIR", "~/.cache/eb"))
WAYPOINT_FILE = os.path.join(STATE_DIR, "waypoint")
ORG_FILE = os.path.join(STATE_DIR, "org_id")
WAYPOINT_TTL = 300  # docs: a waypoint can be dropped ~5 min after the last request


def _token():
    tok = os.environ.get("EVENTBRITE_TOKEN")
    if not tok:
        sys.exit("EVENTBRITE_TOKEN is not set")
    return tok


def _read_waypoint():
    try:
        if time.time() - os.path.getmtime(WAYPOINT_FILE) > WAYPOINT_TTL:
            return None
        with open(WAYPOINT_FILE) as f:
            return f.read().strip() or None
    except OSError:
        return None


def _write_waypoint(value):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(WAYPOINT_FILE, "w") as f:
        f.write(value)


def request(method, path, params=None, body=None, retries=3):
    url = BASE + path if path.startswith("/") else path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = {"Authorization": "Bearer " + _token()}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    wp = _read_waypoint()
    if wp:
        headers["Eventbrite-API-Waypoint-Token"] = wp
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            status, raw, rh = resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as e:
        status, raw, rh = e.code, e.read(), e.headers
    new_wp = rh.get("Eventbrite-API-Waypoint-Token") if rh else None
    if new_wp:
        _write_waypoint(new_wp)
    if status == 429 and retries > 0:  # HIT_RATE_LIMIT (2,000 calls/hour/token)
        time.sleep(30)
        return request(method, path, params, body, retries - 1)
    try:
        payload = json.loads(raw) if raw else {}
    except ValueError:
        payload = {"raw": raw.decode(errors="replace")}
    return status, payload


def org_id():
    env = os.environ.get("EVENTBRITE_ORG_ID")
    if env:
        return env
    try:
        with open(ORG_FILE) as f:
            cached = f.read().strip()
            if cached:
                return cached
    except OSError:
        pass
    status, data = request("GET", "/users/me/organizations/")
    if status != 200 or not data.get("organizations"):
        sys.exit("Could not resolve organization: %s" % json.dumps(data))
    orgs = data["organizations"]
    if len(orgs) > 1:
        print("warning: %d organizations, using the first (%s). Set EVENTBRITE_ORG_ID to pick another."
              % (len(orgs), orgs[0]["name"]), file=sys.stderr)
    oid = orgs[0]["id"]
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(ORG_FILE, "w") as f:
        f.write(oid)
    return oid


def paginate(method, path, params):
    """Follow `continuation` and merge the single list key of each page."""
    params = dict(params or {})
    merged, list_key = [], None
    while True:
        status, data = request(method, path, params)
        if status != 200:
            return status, data
        if list_key is None:
            list_key = next((k for k, v in data.items() if isinstance(v, list)), None)
        if list_key:
            merged.extend(data.get(list_key, []))
        pag = data.get("pagination") or {}
        if not pag.get("has_more_items") or not pag.get("continuation"):
            break
        params["continuation"] = pag["continuation"]
    return 200, {list_key or "items": merged, "count": len(merged)}


def main(argv):
    quiet = "--quiet" in argv
    argv = [a for a in argv if a != "--quiet"]
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "org":
        print(org_id())
        return 0
    method, path, rest = argv[0].upper(), argv[1], argv[2:]
    if "{org}" in path:
        path = path.replace("{org}", org_id())
    body, params, follow = None, {}, False
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--all":
            follow = True
        elif a == "--json":
            with open(rest[i + 1]) as f:
                body = json.load(f)
            i += 1
        elif a == "--data":
            body = json.loads(rest[i + 1])
            i += 1
        elif "=" in a:
            k, v = a.split("=", 1)
            params[k] = v
        else:
            sys.exit("unrecognised argument: %s" % a)
        i += 1
    if follow:
        status, data = paginate(method, path, params)
    else:
        status, data = request(method, path, params, body)
    if not quiet:
        print("HTTP %s" % status, file=sys.stderr)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
