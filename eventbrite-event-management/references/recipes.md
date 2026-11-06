# Eventbrite recipes

Payloads for flows that SKILL.md only summarizes. All are **(spec)** unless marked otherwise: built from the official API v3 spec (https://www.eventbrite.com/platform/api), not yet exercised against the live API. On first use, check the response and update the marker.

Examples use `eb.py` (`S=<skill>/scripts/eb.py`); the same paths work with curl + `Authorization: Bearer $TOKEN`.

Contents
- Description (structured content)
- Image upload (event cover)
- Recurring series
- Early bird → regular tickets
- Copy an existing event
- Discount / promo codes
- Custom checkout questions
- Buyer confirmation message and instructions
- Display settings and custom status texts
- Attendees export and check-in status
- Sales report
- Webhooks

---

## Description (structured content)

The long description is a "page" of modules. Two rules shape every call:

1. **Insert-only, versioned.** Each save is a new version, and you resend the *full* module list every time, not a diff.
2. **Publish in the same call.** Saving without `"publish": true` stores a working version only you can see. Sending `publish: true` without the modules publishes an empty page.

Find the current version, then post to the next one:

```bash
python3 $S GET /events/$EID/structured_content/edit/     # → page_version_number (absent/empty on a new event)
```

Next version = current + 1, or `1` if there's none. If you get `PAGE_VERSION_DISCONTINUITY`, re-read the version and retry with the right number.

```bash
python3 $S POST /events/$EID/structured_content/1/ --json desc.json
```

`desc.json`:

```json
{
  "modules": [
    {"type": "text", "data": {"body": {"alignment": "left",
      "text": "<p>Una serata di <strong>stand-up comedy</strong> in italiano.</p><ul><li>Ingresso libero</li><li>Prenotazione consigliata</li></ul>"}}},
    {"type": "image", "data": {"image": {"image_id": "<id from Image upload, type image-structured-content>"}}},
    {"type": "video", "data": {"video": {"url": "https://www.youtube.com/watch?v=...", "display_size": "large"}}}
  ],
  "publish": true,
  "purpose": "listing"
}
```

- Allowed HTML in text modules: links, `<strong>`, `<em>`, `<p>`, lists. Other tags get stripped.
- Video on the listing page: YouTube only.
- Limits: 100 modules per page, 5,000 versions.
- Widgets (`agenda`, `faqs`) exist on the page object; see the "Structured Content Agenda/FAQs Widget" data structures in the spec if needed.
- Read back: `GET /events/$EID/structured_content/` (latest *published*) or `GET /events/$EID/description/` (rendered HTML of summary + description).
- `purpose: "digital_content"` builds the separate attendee-only page for online events instead.

## Image upload (event cover)

The bundled spec only documents the `/media/upload/` endpoints; the sequence below follows Eventbrite's media-upload tutorial. Print each response and use the field names it actually returns.

1. **Ask for an upload slot**, saying what the image is for:
   ```bash
   python3 $S GET /media/upload/ type=image-event-logo
   ```
   Other types: `image-structured-content` (images inside the description), `image-organizer-logo`, `image-event-logo-preserve-quality`. The response carries an `upload_token`, an `upload_url` (S3), the form fields to send with it (`upload_data`) and the name of the file field (`file_parameter_name`).
2. **Push the file to S3** — multipart POST to `upload_url`, every `upload_data` field first, the file last, *no* Eventbrite auth header:
   ```bash
   curl -s -X POST "$UPLOAD_URL" -F key=... -F AWSAccessKeyId=... -F policy=... -F signature=... -F acl=... -F "file=@cover.jpg"
   ```
   Build the `-F` list from `upload_data` in code rather than by hand.
3. **Confirm the upload** (optionally with a crop):
   ```json
   {"upload_token": "<token from step 1>",
    "crop_mask": {"top_left": {"x": 0, "y": 0}, "width": 2160, "height": 1080}}
   ```
   `POST /media/upload/` → returns the image with its `id`. Errors: `BAD_UPLOAD_TOKEN`, `BAD_FORMAT`, `BAD_FILE`, `S3_ERROR`.
4. **Attach it:** `POST /events/$EID/` with `{"event": {"logo_id": "<image id>"}}`. Event covers display at 2:1; 2160×1080 is the safe size.

## Recurring series

For a show with the same title, venue, tickets and description on a regular cadence (e.g. every Thursday).

1. **Create the parent** — normal create body plus `"is_series": true`. The `start`/`end` you send are placeholders; the parent's dates are computed from its occurrences.
2. **Add occurrences** with an RRULE (RFC 5545). `DTSTART` (and `UNTIL`, if used) must be UTC, so compute the local→UTC offset per season:
   ```json
   {"schedule": {
     "occurrence_duration": 7200,
     "recurrence_rule": "DTSTART:20261112T200000Z\nRRULE:FREQ=WEEKLY;COUNT=8"
   }}
   ```
   `POST /events/$PARENT/schedules/` → `created_event_ids` lists the child events. Occurrences that collide with an existing date/time are silently skipped.
   - A weekly rule that crosses a DST change keeps the *UTC* time, so the local start shifts by an hour. Split it into two schedules (one per season) on the same parent.
   - Limits: 120 occurrences per series, `DTSTART` within 2 years, last occurrence within 4 years, each occurrence ≤ 7 days (`EXCEEDS_MAX_OCCURRENCES`, `DTSTART_OUTSIDE_PERMITTED_RANGE`, `RECURRENCE_RULE_DATES_NOT_IN_UTC`).
3. **Tickets on the parent.** `sales_end` can't be set on a series parent; use `"sales_end_relative": {"relative_to_event": "start_time", "offset": 0}` (offset = seconds before each date's start).
4. **Publish the parent** — it publishes every occurrence. Occurrences can't be unpublished individually; to drop one date, cancel or delete that child event.
5. **List dates:** `GET /series/$PARENT/events/?time_filter=current_future`. Editing `name`, `currency`, `capacity`, `show_remaining`, `password` or `hide_*_date` on the parent propagates to every occurrence.

A one-off event can't later become a series once it's published, has tickets or has occurrences (`IS_SERIES_UPDATE_NOT_ALLOWED_*`) — decide up front. Reserved-seating events can't be series.

## Early bird → regular tickets

Two ticket classes; the second opens when the first sells out:

```json
{"ticket_class": {"name": "Early bird", "cost": "EUR,800",  "capacity": 20, "sales_end": "2026-11-22T19:00:00Z"}}
{"ticket_class": {"name": "Intero",     "cost": "EUR,1200", "capacity": 60, "sales_start_after": "<early bird ticket_class id>", "sales_end": "2026-11-22T19:00:00Z"}}
```

Use `auto_hide: true` on the regular class if it shouldn't appear until it opens. A class referenced by `sales_start_after` can't be deleted while the reference exists (`IS_STARTED_AFTER`).

## Copy an existing event

```json
{"name": "Titolo nuovo", "start_date": "2026-12-20T19:00:00Z", "end_date": "2026-12-20T21:00:00Z",
 "timezone": "Europe/Rome", "summary": "Max 140 caratteri"}
```

`POST /events/$OLD/copy/` → full Event object of the new draft. Carries over payment options, payout, refund policy, tax. Then GET `/events/$NEW/ticket_classes/` and `/events/$NEW/structured_content/edit/` to see what else came along, and fix ticket `sales_end` dates — they won't move with the new date automatically. Errors: `INVALID_START_DATE`, `INVALID_END_DATE` (1 min–365 days after start), `INSUFFICIENT_PACKAGE`.

## Discount / promo codes

`POST /organizations/$ORG/discounts/`:

```json
{"discount": {
  "type": "coded", "code": "AMICI20", "percent_off": "20",
  "event_id": "<event id>", "ticket_class_ids": [],
  "quantity_available": 30,
  "end_date": "2026-11-20T23:59:00"
}}
```

- Types: `coded` (secret code gives a discount), `access` (secret code reveals hidden tickets; can also discount), `public` (shown to everyone; single event only), `hold`.
- `amount_off` *or* `percent_off`, never both (`AMOUNT_AND_PERCENT_OFF_PROVIDED`). Amounts are major units here ("5.00"), unlike ticket `cost`.
- `start_date`/`end_date` are **naive local time in the event's timezone** (no `Z`) — the opposite of event times. Or use `*_relative` (seconds before event start, multiple of 60).
- Scope: `event_id` (+ optional `ticket_class_ids`) = one event; `ticket_group_id` = a group; neither = all current and future events of the org.
- `quantity_available: 0` means unlimited. List: `GET /organizations/$ORG/discounts/?scope=event&event_id=...`. Only unused discounts can be deleted (`DELETE /discounts/{id}/`).

## Custom checkout questions

`POST /events/$EID/questions/`:

```json
{"question": {
  "question": {"html": "Come ci hai conosciuto?"},
  "type": "dropdown", "required": false, "respondent": "ticket_buyer",
  "choices": [{"answer": {"html": "Instagram"}}, {"answer": {"html": "Passaparola"}}, {"answer": {"html": "Altro"}}]
}}
```

Types: `text`, `paragraph`, `checkbox`, `dropdown`, `radio`, `waiver`. `respondent: "attendee"` asks per ticket instead of per order. Built-in fields (phone, company, …) are "canned questions": `POST /events/$EID/canned_questions/` with `canned_type` (e.g. `cell_phone`). Answers arrive on attendees as `answers` (or `?expand=survey_responses`). `INSUFFICIENT_PACKAGE` = the account plan doesn't allow custom questions.

## Buyer confirmation message and instructions

`POST /events/$EID/ticket_buyer_settings/`:

```json
{"ticket_buyer_settings": {
  "confirmation_message": {"html": "<p>Grazie! Ci vediamo alle 20:30, porte alle 20:00.</p>"},
  "instructions": {"html": "<p>Mostra il QR all'ingresso.</p>"},
  "refund_request_enabled": false
}}
```

`redirect_url` sends buyers to your own page after checkout instead (overrides the confirmation message).

## Display settings and custom status texts

- `POST /events/$EID/display_settings/` with `{"display_settings": {"show_remaining": true, "show_map": true, "show_end_date": false}}`.
- Custom banner texts (sold out, postponed, …):
  ```json
  {"event_id": "<id>", "locale": "it_IT",
   "strings": [{"text_code": "tickets_sold_out", "message": "Sold out! Scrivici per la lista d'attesa."}]}
  ```
  `POST /organizations/$ORG/text_overrides/`. Codes: `tickets_not_yet_on_sale`, `tickets_with_sales_ended`, `tickets_sold_out`, `tickets_unavailable`, `tickets_at_the_door`, `event_cancelled`, `event_postponed`, `checkout_title_*`.

## Attendees export and check-in status

```bash
python3 $S GET /events/$EID/attendees/ status=attending --all --quiet > attendees.json
python3 -c "
import json, csv, sys
a = json.load(open('attendees.json'))['attendees']
w = csv.writer(open('attendees.csv', 'w', newline=''))
w.writerow(['name', 'email', 'ticket', 'checked_in', 'order_id'])
for x in a:
    w.writerow([x['profile'].get('name'), x['profile'].get('email'), x['ticket_class_name'], x['checked_in'], x['order_id']])
print(len(a), 'attendees')
"
```

- `status`: `attending` (incl. checked in), `not_attending`, `unpaid`. One attendee per ticket, so a 3-ticket order is 3 rows; with order-level questions only, they share the buyer's data.
- Incremental sync: `changed_since=2026-11-20T00:00:00Z`.
- Across all events: `GET /organizations/$ORG/attendees/`.
- Treat the export as personal data: keep it local, don't paste the email list into chat unless asked.

## Sales report

```bash
python3 $S GET /reports/sales/ event_ids=$EID1,$EID2 group_by=ticket date_facet=none
python3 $S GET /reports/sales/ event_ids=$EID date_facet=day timezone=Europe/Rome
python3 $S GET /reports/attendees/ event_ids=$EID group_by=ticket
```

Totals: `gross`, `net` (without fees/taxes/royalties), `quantity`, `fees`. `group_by` options include `ticket`, `event`, `payment_method`, `sales_channel_lvl_1`, `city`, `country`. Mixing currencies across events gives `CURRENCY_MISMATCH`.

## Webhooks

`POST /organizations/$ORG/webhooks/`:

```json
{"endpoint_url": "https://example.com/hooks/eventbrite",
 "actions": "order.placed,order.refunded,attendee.checked_in",
 "event_id": ""}
```

Empty `event_id` = all events. Actions: `event.created|published|updated|unpublished`, `order.placed|refunded|updated`, `attendee.checked_in|checked_out|updated`, `ticket_class.created|updated|deleted`, `organizer.updated`, `venue.updated`. Check the first delivery's body to see what it carries (the spec doesn't document the payload). List: `GET /organizations/$ORG/webhooks/`; delete: `DELETE /webhooks/{id}/`. The org-less `POST /webhooks/` is dead.
