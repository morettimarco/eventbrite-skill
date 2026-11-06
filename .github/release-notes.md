## Install

**Claude apps:** download `eventbrite-event-management.skill` below, then upload it under Settings → Capabilities → Skills (or drop it into a chat with Claude and click **Save skill**).

**Claude Code:** `unzip -o eventbrite-event-management.skill -d ~/.claude/skills/`

You'll need an Eventbrite private token: https://www.eventbrite.com/platform/api-keys

## What it does

- Create, update, copy, publish/unpublish, cancel and delete Eventbrite events via the REST API v3, with no MCP server needed
- Recurring series (RRULE schedules), venue reuse, structured-content descriptions, cover-image upload
- Free and paid ticket classes, early bird → regular, discount codes, checkout questions
- Attendee/order export, check-in status, sales reports, webhooks
- `scripts/eb.py`: tiny stdlib client handling auth, org ID, pagination and the read-after-write waypoint header

Notes tagged **(verified)** were run against the live API. Notes tagged **(spec)** come from the official spec and haven't been run live yet (series, copy, image upload, paid tickets, discounts, reports). Reports are welcome.
