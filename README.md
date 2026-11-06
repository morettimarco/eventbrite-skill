# Eventbrite skill for Claude

An [Agent Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) that lets Claude create and manage Eventbrite events directly through the [Eventbrite REST API v3](https://www.eventbrite.com/platform/api). No MCP server is needed: Claude calls the API with `curl` or the small bundled Python client.

Ask Claude things like:

- "Put my show on Eventbrite: Friday 20 March, 21:00, Teatro X, 80 free seats, max 4 per booking."
- "Create a weekly series every Thursday for the next 8 weeks."
- "Copy last month's event to 20 December, with 20 early-bird tickets at €7 and then regular ones at €10."
- "Export the attendees of event 1234567890 to CSV and create a 20% promo code for friends."

## What it covers

- **Events:** create, update, copy, publish/unpublish, cancel, delete, plus recurring series (RRULE schedules)
- **Content:** summary, structured-content description, cover-image upload
- **Venues:** reuse an existing venue instead of creating duplicates
- **Tickets:** free and paid ticket classes, early bird → regular, capacity, per-order limits, sales windows
- **Checkout:** discount and access codes, custom checkout questions, confirmation messages, custom status texts
- **After the sale:** attendees, orders, check-in status, sales and attendee reports, webhooks

It also records the API's traps that cost hours the first time, for example:

- legacy endpoints that return 403 without an organization prefix
- the `summary`/`description` conflict
- start and end times that must be sent in UTC
- venues that can't be deleted
- the waypoint header that fixes "just-created event not found"
- discount dates in naive local time

## Status: what's tested

Every note in the skill is tagged:

- **(verified)** — exercised against the live Eventbrite API: org-scoped endpoints, venues, categories, single events, summary handling, free ticket classes, batch creation.
- **(spec)** — taken from the official API spec but not yet run live: series, structured content, event copy, image upload, paid tickets, discounts, questions, reports, webhooks.

If you use a **(spec)** flow and it works (or doesn't), please open an issue or PR so the tag can be updated.

## Install

**Claude apps (claude.ai / desktop):**

1. Download **[eventbrite-event-management.skill](https://github.com/morettimarco/eventbrite-skill/releases/latest/download/eventbrite-event-management.skill)** (latest release).
2. Upload it under Settings → Capabilities → Skills, or drop it into a chat with Claude and click **Save skill**.

**Claude Code:**

```bash
curl -L -o /tmp/eb.skill https://github.com/morettimarco/eventbrite-skill/releases/latest/download/eventbrite-event-management.skill
unzip -o /tmp/eb.skill -d ~/.claude/skills/
```

Or, from a clone: `cp -r eventbrite-skill/eventbrite-event-management ~/.claude/skills/`.

Then give Claude your token. Create a private token at <https://www.eventbrite.com/platform/api-keys>, and either export it as `EVENTBRITE_TOKEN` or paste it when Claude asks. Treat it like a password: it has full access to your Eventbrite account.

## Layout

```
eventbrite-event-management/
├── SKILL.md                    # main workflow and rules (what Claude reads first)
├── references/
│   ├── recipes.md              # full payloads: series, description, images, discounts, …
│   └── api-reference.md        # every endpoint with params and error codes
├── scripts/eb.py               # tiny stdlib client: auth, org ID, pagination, waypoint header
└── evals/                      # test prompts with graders (skill-creator / `claude plugin eval` format)
```

The full official API Blueprint spec isn't included, because it has no published license. If you have a copy, drop it in `references/eventbrite-api-v3.apib` and the skill will search it for anything the reference doesn't cover.

### Using `eb.py` on its own

```bash
export EVENTBRITE_TOKEN=...
python3 scripts/eb.py org                                           # your organization ID
python3 scripts/eb.py GET /organizations/{org}/events/ status=all --all
python3 scripts/eb.py POST /organizations/{org}/events/ --json event.json
```

## Contributing

Issues and PRs are welcome, especially ones that confirm or correct **(spec)** notes with real API responses. Please don't include tokens, attendee data or real event IDs in issues.

### Releasing

Releases are built by `.github/workflows/release.yml`. Push an annotated tag and the Action zips the skill (without `evals/`) and attaches the `.skill` file to a new GitHub release, using the tag message as the release notes:

```bash
git tag -a v2.0.1 -m "What changed"
git push origin v2.0.1
```

## License

MIT, see [LICENSE](LICENSE). Not affiliated with or endorsed by Eventbrite.
