---
name: eventbrite-event-management
description: "Create, publish and manage Eventbrite events directly through the Eventbrite REST API v3 (curl or the bundled scripts/eb.py), with no MCP server. Use this whenever the user wants to put a show, gig or event on Eventbrite, batch-create several dates or a weekly recurring series, add free or paid ticket classes, reuse a venue, set the summary/description or cover image, copy last month's event, publish/unpublish/cancel, create discount codes or custom checkout questions, or pull attendees, orders, check-ins and sales reports for an event. Trigger even if the user only says 'mettilo su Eventbrite', pastes an eventbrite.com link, or mentions an Eventbrite token, org ID or event ID."
license: MIT
metadata:
  version: '2.0.0'
  author: Marco Moretti
  homepage: https://github.com/morettimarco/eventbrite-skill
  platforms:
  - linux
  - macos
  tags:
  - eventbrite
  - events
  - api
  - curl
---

# Eventbrite Event Management

Drive Eventbrite through its REST API v3 directly. No MCP server is needed: the community Eventbrite MCP servers we tried covered only part of the API (no ticket classes, image upload or event copy at the time), while direct calls give full control over every field.

**How much to trust each note.** Lines marked **(verified)** come from real runs against the live API. Lines marked **(spec)** come from the official API v3 spec (summarized in `references/api-reference.md`) and haven't been exercised here yet — follow them, but check the response the first time and promote the note to (verified) once it works. When the two disagree, live behaviour wins; record what you saw.

## Where to look

| Need | Go to |
|---|---|
| The everyday flow: venue → event → description → tickets → publish | this file |
| Exact payloads for series, structured-content description, image upload, discounts, questions, webhooks, attendees/reports | `references/recipes.md` |
| Every endpoint, its params and its named error codes, grouped by object | `references/api-reference.md` |
| Something neither covers | If `references/eventbrite-api-v3.apib` exists (the full official spec, not shipped in the public repo), `grep -n` it — 7k lines, search it, don't read it whole. Otherwise the official docs: https://www.eventbrite.com/platform/api |

## Setup

Personal OAuth token from https://www.eventbrite.com/platform/api-keys (Account Settings → API Keys). Send it as `Authorization: Bearer $TOKEN`. Base URL `https://www.eventbriteapi.com/v3`. Rate limit is 2,000 calls/hour per token (`429 HIT_RATE_LIMIT`).

Prefer the bundled client over hand-rolled curl — it handles auth, org resolution, pagination and the waypoint header described below:

```bash
export EVENTBRITE_TOKEN=...            # never echo it back into chat or files
S=<this skill's dir>/scripts/eb.py
python3 $S org                                            # resolve + cache org ID
python3 $S GET /organizations/{org}/events/ status=all --all
python3 $S POST /organizations/{org}/events/ --json event.json
```

`{org}` in a path is substituted automatically. Exit code is non-zero on 4xx/5xx and the error JSON is still printed. Branch on the `error` constant (e.g. `SUMMARY_DESCRIPTION_CONFLICT`), not on `error_description`, which is localized and changes.

## Rules that save the most pain

**Use organization-scoped endpoints. (verified)** Modern accounts get `403 NOT_AUTHORIZED: ...legacy user endpoints...` on `/events/`, `/venues/`, `/webhooks/` without an org prefix. Resolve the org once with `GET /users/me/organizations/` and use `/organizations/{org_id}/...` for create/list. The org ID is not the number in your public organizer-profile URL.

**Read-after-write can 404 — use the waypoint token. (spec)** Eventbrite is eventually consistent: a `GET` right after a `POST` may 404 or return stale data for up to a few seconds (rarely minutes). Every successful POST/DELETE returns an `Eventbrite-API-Waypoint-Token` response header; send it back as a request header on the next call and the read is guaranteed to see your write (costs up to a few seconds). `eb.py` does this automatically. With raw curl, capture it with `-D headers.txt`. This is the likely cause of any "event I just created is not found" during batch runs.

**Times are UTC on the way in. (verified)** `start`/`end` take `{"timezone": "Europe/Rome", "utc": "2026-11-22T19:00:00Z"}`; `local` is ignored on input. Compute the offset yourself (Europe/Rome is +1 in CET, +2 in CEST; the switch is the last Sunday of March/October) and check the `start.local` Eventbrite echoes back. Both ends must use the same timezone (`DIFFERENT_TIMEZONES`), and you can't create in the past (`INVALID_DATE`).

**Everything is created as a draft. (verified)** Nothing is public until `POST /events/{id}/publish/`. Ask the user before publishing — it's the one step with outside visibility, and unpublishing gets blocked once anyone has an order.

**Updates are POST, not PATCH/PUT. (verified)** `POST /events/{id}/` with only the fields you want to change.

**Count character limits in code. (verified)** `summary` is max 140 chars. Use `len(s)` per generated string — named substitutions change the length per instance — and keep a shorter fallback phrasing ready.

## Creating an event, step by step

### 1. Reuse the venue (don't create duplicates)

`GET /organizations/{org}/venues/` and match by name + address in code — there's no server-side name filter. Only `POST /organizations/{org}/venues/` when nothing matches. **Venues cannot be deleted (verified: `405 METHOD_NOT_ALLOWED`)**, only updated with `POST /venues/{id}/`, so a duplicate is permanent clutter. Create payload: `{"venue": {"name": ..., "address": {"address_1": ..., "city": "Milano", "postal_code": ..., "country": "IT"}, "capacity": 80}}` (`google_place_id` is also accepted). For online events skip the venue and set `"online_event": true` — setting both gives `VENUE_AND_ONLINE`.

### 2. Category and subcategory

`GET /categories/` lists top-level categories (Performing & Visual Arts = `105`). **Subcategories are a separate, unfiltered endpoint (verified)** — `category_id` as a query param is rejected. Page through `GET /subcategories/` (`--all` with eb.py) and filter by `parent_category.id`. Comedy under Performing & Visual Arts = `5010`. Formats (`format_id`, e.g. performance/show) come from `GET /formats/`.

### 3. Create the event

`POST /organizations/{org}/events/`:

```json
{"event": {
  "name": {"html": "Title"},
  "summary": "Max 140 chars, plain text",
  "start": {"timezone": "Europe/Rome", "utc": "2026-11-22T19:00:00Z"},
  "end":   {"timezone": "Europe/Rome", "utc": "2026-11-22T21:00:00Z"},
  "currency": "EUR", "online_event": false, "listed": true,
  "shareable": true, "invite_only": false, "show_remaining": true,
  "category_id": "105", "subcategory_id": "5010",
  "venue_id": "<existing venue id>",
  "locale": "it_IT"
}}
```

- `locale` sets the listing language — `it_IT` for an Italian show, otherwise the page defaults to `en_US`. (spec)
- `listed: false` makes it reachable only by link; `password` and `invite_only` are mutually exclusive with `listed` (`PASSWORD_CONFLICT`, `INVITE_CONFLICT`). (spec)
- `capacity` caps the whole event; if omitted it's the sum of ticket capacities. (spec)
- `NO_DEFAULT_ORGANIZER` means the account has no organizer profile yet; profiles are created in the web UI only. (verified)

### 4. Summary and long description

`summary` and the old `description` field are **mutually exclusive in one call (verified: `400 SUMMARY_DESCRIPTION_CONFLICT`)**, and if you send only `description`, Eventbrite auto-truncates it into a 140-char summary you didn't write.

- **Preferred (spec):** create with `summary` as above, then set the long description as *structured content*: `POST /events/{id}/structured_content/{version}/` with text/image/video modules and `"publish": true`. The spec marks `event.description` as deprecated; structured content is what the new event editor uses. Version handling and payload are in `references/recipes.md` § Description. The rendered HTML can be read back with `GET /events/{id}/description/`.
- **Fallback (verified):** create with `description: {"html": ...}` only, then a second `POST /events/{id}/` carrying just `{"event": {"summary": "..."}}`.

### 5. Ticket classes

`POST /events/{id}/ticket_classes/`:

```json
{"ticket_class": {
  "name": "Posto a sedere",
  "capacity": 80,
  "free": true,
  "minimum_quantity": 1,
  "maximum_quantity": 4,
  "sales_start": "2026-11-05T13:00:00Z",
  "sales_end": "2026-11-22T19:00:00Z"
}}
```

- **`capacity` replaces `quantity_total` (spec).** `quantity_total` still worked in earlier runs (verified) but the spec marks it deprecated — prefer `capacity`, fall back if it's rejected.
- **The per-order cap is `maximum_quantity` (verified).** `maximum_quantity_per_order` appears in GET responses but is rejected on write (`ARGUMENTS_ERROR: Unknown parameter`).
- `sales_end` should normally be that event's own `start.utc` — don't reuse one cutoff across a batch with different start times. (verified)
- **Paid tickets (spec):** drop `free`, add `"cost": "EUR,1500"` (minor units: 1500 = €15.00). `include_fee: true` absorbs Eventbrite's fee into the shown price. Fee preview before committing: `POST /pricing/calculate_price_for_item/`. A paid event won't publish until payouts are configured in the web UI (`NO_PAYMENT_OPTIONS`, `PAYMENT_OPTIONS_NO_COUNTRY`). Price can't change once tickets are sold (`CANNOT_UPDATE_COST`).
- Other useful fields (spec): `hidden`, `auto_hide`, `sales_start_after` (open this class when another sells out — early bird → regular), `sales_channels: ["online","atd"]` (at the door), `description` + `hide_description`, `donation: true`.
- Ticket classes ARE deletable: `DELETE /events/{id}/ticket_classes/{tc_id}/`. List with `GET /events/{id}/ticket_classes/` before adding, especially after a partial or retried batch. (verified)

### 6. Cover image (optional)

Four steps — get an upload slot, push the file to S3, confirm, attach as `logo_id`. Full sequence in `references/recipes.md` § Image upload. (spec)

### 7. Verify, then publish

Re-`GET /events/{id}/?expand=venue,ticket_availability` (with the waypoint token) and check: `start.local`/`end.local` match intent, `venue_id` is the shared one, `summary` is exactly your string, and the ticket class exists with the right capacity. Report the draft URL to the user and publish only on their go-ahead: `POST /events/{id}/publish/` → `{"published": true}`. Publish needs name, description, organizer, at least one ticket and (if paid) payment options; failures come back as named errors (`ALREADY_PUBLISHED_OR_DELETED`, `NO_PAYMENT_OPTIONS`, …).

## Several dates

**Same show every week/month → a series (spec).** Create one event with `"is_series": true` (the series parent), then `POST /events/{parent_id}/schedules/` with an iCalendar RRULE (`DTSTART` in UTC) and `occurrence_duration` in seconds. Each occurrence is a child event; ticket classes go on the parent and use `sales_end_relative` instead of `sales_end`. Publishing the parent publishes every date. Limits: ≤120 occurrences per series, first date within 2 years. Full recipe in `references/recipes.md` § Series. Pick this when the dates share title, venue, tickets and description.

**Different titles/line-ups per date → batch of independent events (verified).** Build the per-event deltas (title, times, names) as a Python list, template the shared description, then loop create → description → ticket class, collecting `{id, url, status}` into a results file. Re-GET every event afterwards. If a run dies halfway, list the org's events (`status=all`) and each event's ticket classes before retrying, so you don't double-create.

**Re-running last month's show → copy (spec).** `POST /events/{id}/copy/` with `{"name": ..., "start_date": "2026-12-20T19:00:00Z", "end_date": "...", "timezone": "Europe/Rome", "summary": ...}` returns a new draft event carrying over payment options, payout method, refund policy and tax settings. The spec doesn't say whether ticket classes and structured-content description come along — GET both on the copy and fill the gaps. (Older notes said there was no copy endpoint; that was wrong.)

## Before creating: check what already exists (verified)

`GET /organizations/{org}/events/?status=all` (paginate) — without `status=all` drafts can be hidden. Useful filters (spec): `name_filter`, `time_filter=current_future`, `venue_filter`, `order_by=start_asc`. Filter by date client-side before concluding a day is free.

## Changing or ending an event (spec)

| Goal | Call | Blocked when |
|---|---|---|
| Edit any field | `POST /events/{id}/` | currency once paid sales exist; dates on a series parent (edit occurrences) |
| Take offline but keep | `POST /events/{id}/unpublish/` | any pending/completed order (free or paid, unless paid out & over) |
| Cancel | `POST /events/{id}/cancel/` | orders exist — refund them first |
| Remove a draft | `DELETE /events/{id}/` | orders exist |

Cancel and delete are irreversible and visible to buyers — confirm with the user each time. Custom texts for "sold out"/"postponed"/"cancelled" banners: `POST /organizations/{org}/text_overrides/`.

## After tickets go out (spec)

- **Attendees:** `GET /events/{id}/attendees/?status=attending` (paginated; `changed_since` for incremental syncs). Each has `profile.name/email`, `ticket_class_name`, `checked_in`, `answers`.
- **Orders:** `GET /events/{id}/orders/` or org-wide `GET /organizations/{org}/orders/`.
- **Numbers:** `GET /reports/sales/?event_ids=...&date_facet=day` and `/reports/attendees/`.
- **Promo codes:** `POST /organizations/{org}/discounts/` (coded/access/public). Codes allow only letters, digits and `-_()/`, no spaces.
- **Extra checkout questions:** `POST /events/{id}/questions/`.
- **Push notifications to your own endpoint:** `POST /organizations/{org}/webhooks/`.
- **Refunds:** the refund endpoint is limited-availability and returns a permission error for most apps — do refunds in the web UI.

Payloads for each are in `references/recipes.md`. Attendee data is personal data: keep exports local, don't paste email lists into chat unless the user asks.

## Not available through the API

- Searching other organizers' public events — `/events/search/` was shut down in December 2019. (spec)
- Creating organizations or organizer profiles — web UI only. (verified)
- Deleting venues. (verified)
- Configuring payouts/bank details — web UI only. (spec, implied by publish errors)
