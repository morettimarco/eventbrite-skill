# Eventbrite API v3 — endpoint reference

Condensed from the official Eventbrite API v3 spec (https://www.eventbrite.com/platform/api). Base `https://www.eventbriteapi.com/v3`. All writes are `POST` (no PUT/PATCH), with a JSON body wrapped in the object name (`{"event": {...}}`, `{"ticket_class": {...}}`, …) unless noted. Paths end with `/`.

When this table lacks a detail and the full spec `eventbrite-api-v3.apib` is in this folder, search it: `grep -n "### Create a Discount" eventbrite-api-v3.apib`, then read ~60 lines from there (data structures are under `## Data Structures`). Without it, use the official docs: https://www.eventbrite.com/platform/api

Contents: Conventions · User & Organization · Event · Series & schedules · Description / structured content · Ticket classes · Inventory tiers & capacity · Venue · Categories & formats · Media · Questions · Discounts & ticket groups · Orders · Attendees · Reports · Pricing · Settings & texts · Webhooks · Seat maps · Teams · Deprecated / dead

## Conventions

| Topic | Detail |
|---|---|
| Auth | `Authorization: Bearer TOKEN` (or `?token=` — avoid; it leaks into logs) |
| Errors | JSON `{"error": CONSTANT, "error_description": text, "status_code": n}`. Branch on `error`. Common: `ARGUMENTS_ERROR`, `INVALID_AUTH`, `NO_AUTH`, `NOT_AUTHORIZED` (403), `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `HIT_RATE_LIMIT` (429, 2,000/h), `EXPANSION_FAILED` (retry without `expand`) |
| Pagination | Response has `pagination.{has_more_items, continuation, page_count, object_count}`. Repeat the request with `continuation=<token>` until `has_more_items` is false. `page_size` works on many list endpoints |
| Consistency | Send back the `Eventbrite-API-Waypoint-Token` header from the last write to make the next read consistent (adds ≤5 s). Safe to drop after ~5 min |
| Expansions | v1: `?expand=venue,organizer,ticket_availability` (nest with `.`, 4 levels). v2 (when the object has `_type`): `?expand.event=venue,organizer` |
| Money | Read: `{"currency","value" (minor units),"major_value","display"}`. Write: `"EUR,1500"` string, or `{"currency":"EUR","value":1500}` in JSON bodies |
| Times | Event `start`/`end`: `{"timezone","utc"}` (UTC with `Z`; `local` ignored on input). Discount dates and `Event Copy` use their own formats — see those rows |
| Switches | Opt in/out of API behaviour via `Eb-Api-Switches-Enabled` / `-Disabled` headers, e.g. `OMIT_DESCRIPTION_FROM_EVENT_CONTAINER` |

## User & Organization

| Call | Notes |
|---|---|
| `GET /users/me/` | Current user; `?expand=assortment` for the plan |
| `GET /users/me/organizations/` | → `organizations[].id` — the ID all org-scoped calls need |
| `GET /organizations/{org}/members/` · `/roles/` | Team members and roles |

## Event

| Call | Notes |
|---|---|
| `GET /events/{id}/` | Expansions: `venue`, `organizer`, `logo`, `category`, `subcategory`, `format`, `ticket_availability`, `event_sales_status`, `refund_policy`, `basic_inventory_info`, `checkout_settings`, `listing_properties`, `music_properties`, `has_digital_content` |
| `GET /organizations/{org}/events/` | Filters: `status` (`draft,live,started,ended,completed,canceled,all`), `name_filter`, `time_filter` (`all/past/current_future`), `order_by` (`start_asc`…`name_desc`), `venue_filter`, `organizer_filter`, `series_filter`, `show_series_parent`, `event_ids`, `page_size` |
| `GET /venues/{venue_id}/events/` | Same idea per venue; `only_public` |
| `POST /organizations/{org}/events/` | Create (draft). Required: `name.html`, `start`, `end`, `currency`. Key optional: `summary` (≤140, plain), `venue_id` / `online_event`, `organizer_id`, `category_id`, `subcategory_id`, `format_id`, `logo_id`, `listed`, `shareable`, `invite_only`, `password`, `show_remaining`, `capacity`, `hide_start_date`, `hide_end_date`, `is_series`, `is_reserved_seating`, `locale` (`it_IT`, `en_GB`, `es_ES`, `de_DE`, `fr_FR`, …). Errors: `DATE_CONFLICT`, `DIFFERENT_TIMEZONES`, `INVALID_DATE`, `INVITE_CONFLICT`, `PASSWORD_CONFLICT`, `SHARE_INVITE_CONFLICT`, `NO_DEFAULT_ORGANIZER`, `NO_PACKAGE_SELECTED`, `NO_VENUE`, `VENUE_AND_ONLINE`, `UNSUPPORTED_TIMEZONE`, `SUMMARY_DESCRIPTION_CONFLICT` |
| `POST /events/{id}/` | Partial update, same fields. Extra errors: `CANNOT_UPDATE_CURRENCY`, `CANNOT_UPDATE_SOURCE`, `SERIES_PARENT_START_END_DATE_EDIT`, `OCCURRENCE_TIMEZONE_UPDATE_NOT_ALLOWED`, `OCCURRENCE_DURATION_TOO_LONG`, `IS_SERIES_UPDATE_NOT_ALLOWED_*`, `NO_PAYMENT_OPTIONS`, `PAYMENT_OPTIONS_*` |
| `POST /events/{id}/publish/` | → `{"published": true}`. Needs name, description, organizer, ≥1 ticket, payment options if paid. Errors: `ALREADY_PUBLISHED_OR_DELETED`, `NO_PAYMENT_OPTIONS`, `PAYMENT_OPTIONS_NO_COUNTRY`, `PAYMENT_OPTIONS_NO_PAYMENT_TYPE`, `PAYMENT_OPTIONS_PAYPAL_NO_EMAIL`, `PUBLISH_FREE_EVENT_FEATURE_DENIED`, `ERROR_CANNOT_PUBLISH_SERIES_WITH_NO_DATES` |
| `POST /events/{id}/unpublish/` | Blocked by pending/completed orders (`CANNOT_UNPUBLISH`); series occurrences can't be unpublished alone (`NOT_PUBLISHED` if not live) |
| `POST /events/{id}/copy/` | Body (not wrapped): `name`, `start_date`, `end_date` (UTC `Z`), `timezone`, `summary`. Returns new draft Event. Copies payment, payout, refund, tax settings. Errors: `INVALID_START_DATE`, `INVALID_END_DATE`, `INSUFFICIENT_PACKAGE`, `UNABLE_TO_COPY_EVENT` |
| `POST /events/{id}/cancel/` | Only with no pending/completed orders (`CANNOT_CANCEL`, `ALREADY_CANCELED`). Cascades to series occurrences |
| `DELETE /events/{id}/` | Only with no orders (`CANNOT_DELETE`). Irreversible |

## Series & schedules

| Call | Notes |
|---|---|
| `POST /organizations/{org}/events/` with `is_series: true` | Creates the series parent |
| `POST /events/{parent}/schedules/` | `{"schedule": {"occurrence_duration": seconds, "recurrence_rule": "DTSTART:...Z\nRRULE:..."}}` → `created_event_ids`. Errors: `DTSTART_MISSING`, `RECURRENCE_RULE_DATES_NOT_IN_UTC`, `DTSTART_OUTSIDE_PERMITTED_RANGE` (2 y), `LAST_OCCURRENCE_START_EXCEEDS_LIMIT` (4 y), `EXCEEDS_MAX_OCCURRENCES` (120) |
| `GET /series/{parent}/` | `?expand=series_dates` for the date list |
| `GET /series/{parent}/events/` | `time_filter`, `order_by`, `start_date.range_start/end` |

## Description / structured content

| Call | Notes |
|---|---|
| `GET /events/{id}/description/` | Rendered HTML of summary + description |
| `GET /events/{id}/structured_content/` | Latest *published* page. `?purpose=listing` (default) or `digital_content` |
| `GET /events/{id}/structured_content/edit/` | Latest *working* page → `page_version_number` |
| `POST /events/{id}/structured_content/{version}/` | Body: `modules[]` (`text`/`image`/`video`), `publish`, `purpose`, `access_type`. Full module list every time. Errors: `PAGE_VERSION_DISCONTINUITY`, `MODULES_LIMIT_REACHED` (100), `PAGE_VERSION_LIMIT_REACHED` (5000) |

## Ticket classes

| Call | Notes |
|---|---|
| `GET /events/{id}/ticket_classes/` | `category` (`admission`, `add_on`, `donation`, `all`), `pos` (`online`, `at_the_door`), `include_holds` |
| `GET /events/{id}/ticket_classes/for_sale/` | Buyer view with `variants`, `on_sale_status`; `code=` to see a promo's effect |
| `GET /events/{id}/ticket_classes/{tc}/` | One class |
| `POST /events/{id}/ticket_classes/` | Fields: `name`, `description`, `capacity` (`quantity_total` deprecated), `free` / `donation` / `cost` (`"EUR,1500"`), `minimum_quantity`, `maximum_quantity`, `sales_start`, `sales_end` (or `sales_end_relative` on series parents), `sales_start_after`, `hidden`, `auto_hide`, `auto_hide_before/after`, `hide_description`, `hide_sale_dates`, `include_fee`, `sales_channels` (`online`, `atd`), `delivery_methods`, `has_pdf_ticket`, `order_confirmation_message`, `sorting`, `inventory_tier_id` (required on tiered events), `image_id`. Errors: `BAD_QUANTITIES`, `COST_GREATER_THAN_FEE`, `CURRENCY_MISMATCH`, `DONATION_AND_COST`, `DONATION_AND_FREE`, `FREE_AND_COST`, `NO_COST`, `NO_QUANTITY_TOTAL`, `INSUFFICIENT_PACKAGE` (plan allows one ticket only), `SPLIT_FEES_DEPRECATED`, `AUTO_HIDE_NOT_SET` |
| `POST /events/{id}/ticket_classes/{tc}/` | Update. `CANNOT_UPDATE_COST` after sales, `CIRCULAR_SALES_START_AFTER`, `INVALID_TICKET` (series child — edit the parent) |
| `DELETE /events/{id}/ticket_classes/{tc}/` | Works when unsold (verified in use) |

## Inventory tiers & capacity

Rarely needed for simple GA shows. A tier is shared stock (e.g. "Admission 100") sold through several ticket classes (Adult, Student…); add-ons use a tier with `count_against_event_capacity: false`.

| Call | Notes |
|---|---|
| `GET/POST /events/{id}/inventory_tiers/` | Body `inventory_tier` or `inventory_tiers[]` (bulk). Fields: `name`, `quantity_total`, `count_against_event_capacity`, `sort_order`, `color`, `holds[]`. Max 100 tiers |
| `GET/POST/DELETE /events/{id}/inventory_tiers/{tier}/` | Update supports `holds` create/update/delete (`is_deleted: true`) with `capacity_total` |
| `GET/POST /events/{id}/capacity_tier/` | Event-level capacity and GA holds (e.g. hold 10 seats for guests): `{"capacity_tier": {"capacity_total": 100, "holds": [{"name": "Ospiti", "quantity_total": 10}]}}` |

## Venue

| Call | Notes |
|---|---|
| `GET /organizations/{org}/venues/` | All venues, paginated; no name filter |
| `GET /venues/{id}/` | One venue |
| `POST /organizations/{org}/venues/` | `{"venue": {"name", "address": {address_1, address_2, city, region, postal_code, country, latitude, longitude}, "capacity", "age_restriction", "google_place_id", "organizer_id"}}` |
| `POST /venues/{id}/` | Update. There is no DELETE |

## Categories & formats

| Call | Notes |
|---|---|
| `GET /categories/` · `/categories/{id}/` | Top level (105 = Performing & Visual Arts) |
| `GET /subcategories/` · `/subcategories/{id}/` | Unfiltered, paginated; filter by `parent_category.id` (5010 = Comedy) |
| `GET /formats/` · `/formats/{id}/` | Event types (conference, performance, party…) |

## Media

| Call | Notes |
|---|---|
| `GET /media/upload/?type=...` | Get upload slot. Types: `image-event-logo`, `image-event-logo-preserve-quality`, `image-event-view-from-seat`, `image-organizer-logo`, `image-user-photo`, `image-structured-content` |
| `POST /media/upload/` | `{"upload_token", "crop_mask": {"top_left": {"x","y"}, "width", "height"}}` → image `id`. Errors: `BAD_FILE`, `BAD_FORMAT`, `BAD_UPLOAD_TOKEN`, `S3_ERROR` |
| `GET /media/{id}/` | `width`, `height` for thumbnails |

## Questions

| Call | Notes |
|---|---|
| `GET/POST /events/{id}/questions/` | Custom: `question.html`, `type` (`text`, `paragraph`, `checkbox`, `dropdown`, `radio`, `waiver`), `required`, `respondent` (`ticket_buyer`/`attendee`), `choices[]`, `ticket_classes[]`, `parent_id`/`parent_choice_id` (sub-questions), `display_answer_on_order` |
| `GET/DELETE /events/{id}/questions/{qid}/` | |
| `GET/POST /events/{id}/canned_questions/` | Built-ins via `canned_type` (`first_name`, `email`, `cell_phone`, `company`, `job_title`, `home`, `ship`, `website`, `birth_date`, `age`, `sex`, …) |
| `GET/POST/DELETE /event/{id}/canned_questions/{qid}` | Note the singular `/event/` in the spec for these three |

## Discounts & ticket groups

| Call | Notes |
|---|---|
| `POST /organizations/{org}/discounts/` | `{"discount": {type, code, amount_off \| percent_off, event_id, ticket_class_ids, ticket_group_id, quantity_available (0 = ∞), start_date/end_date (naive local), start_date_relative/end_date_relative (s), hold_ids}}`. Errors: `AMOUNT_AND_PERCENT_OFF_PROVIDED`, `END_DATE_AND_END_DATE_RELATIVE_PROVIDED`, `MULTI_EVENT_DISCOUNT_NOT_SUPPORTED` (public cross-event) |
| `GET /organizations/{org}/discounts/` | Required `scope` (`event`, `multi_events`, `user`); `event_id` required with `event`; `code`, `code_filter`, `type`, `order_by` |
| `GET/POST /discounts/{id}/` · `DELETE` | Delete only if never used (`DISCOUNT_CANNOT_BE_DELETED`) |
| `POST /organizations/{org}/ticket_groups/` | `{"ticket_group": {"name" (≤20), "event_ticket_ids": {"<event>": ["<tc>"]}}}` — for cross-event discounts. Max 300 live groups |
| `GET /organizations/{org}/ticket_groups/` · `GET/POST/DELETE /ticket_groups/{id}/` | |
| `POST /organizations/{org}/events/{e}/ticket_classes/{tc}/ticket_groups/` | `{"ticket_group_ids": [...]}`; empty list removes from all groups |

## Orders

| Call | Notes |
|---|---|
| `GET /orders/{id}/` | Expansions: `event`, `attendees`, `survey_responses`, `answers`, `refund_requests`, `ticket_buyer_settings`, `contact_list_preferences` |
| `GET /events/{id}/orders/` | `status` (`active`, `inactive`, `both`, `all_not_deleted`), `changed_since`, `only_emails`, `exclude_emails`, `refund_request_statuses` |
| `GET /organizations/{org}/orders/` | Org-wide, same filters |
| `GET /users/{id}/orders/` | Orders *placed by* a user (buyer side) |
| `POST /orders/{id}/refunds/` | **Limited availability** — permission error unless Eventbrite enabled it for the app. Body: `reason`, `notes`, `send_refund_email`, `refund_method`. Check `GET /orders/{id}/get_retention_policy_information/` first |

## Attendees

| Call | Notes |
|---|---|
| `GET /events/{id}/attendees/` | `status` (`attending`, `not_attending`, `unpaid`), `changed_since`, `last_item_seen`, `attendee_ids`. Fields: `profile`, `ticket_class_name`, `checked_in`, `cancelled`, `refunded`, `barcodes[].status`, `answers`, `order_id`. Expansions: `event`, `order`, `survey_responses`, `assigned_unit`, `contact_list_preferences` |
| `GET /events/{id}/attendees/{aid}/` | One attendee |
| `GET /organizations/{org}/attendees/` | Org-wide |

## Reports

| Call | Notes |
|---|---|
| `GET /reports/sales/` | `event_ids` (required), `event_status`, `start_date`, `end_date`, `filter_by` (JSON), `group_by` (`ticket`, `event`, `payment_method`, `currency`, `city`, `country`, `source`, `sales_channel_lvl_1..3`, `delivery_method`, …), `date_facet` (`fifteen`, `hour`, `day`, `event_day`, `week`, `month`, `year`, `none`), `period`, `timezone`. Totals: `gross`, `net`, `quantity`, `fees`, `royalty` |
| `GET /reports/attendees/` | Same params; totals `num_attendees`, `num_orders` |

## Pricing

| Call | Notes |
|---|---|
| `POST /pricing/calculate_price_for_item/` | `{"base_price": "EUR,1500", "country": "IT", "scope": {"type": "event", "identifier": "<event id>"}, "absorb_fees": false}` → `organizer_share`, `total_fees`, `total_taxes`, `total_price` |
| `GET /pricing/fee_rates/` | `country`, `currency` required; `plan`, `payment_type`, `channel`, `item_type` |

## Settings & texts

| Call | Notes |
|---|---|
| `GET/POST /events/{id}/display_settings/` | `show_start_date`, `show_end_date`, `show_start_end_time`, `show_timezone`, `show_map`, `show_remaining`, `show_organizer_facebook/twitter`, `terminology` |
| `GET/POST /events/{id}/ticket_buyer_settings/` | `confirmation_message.html`, `instructions.html`, `sales_ended_message.html`, `refund_request_enabled`, `redirect_url`, `allow_attendee_update`, `survey_name`, `survey_info`, `survey_time_limit`, `survey_respondent`, `survey_ticket_classes` |
| `GET/POST /organizations/{org}/text_overrides/` | GET needs `text_codes` (+ `locale`, `event_id`, `venue_id`); POST `{event_id, venue_id, locale, strings: [{text_code, message \| message_code}]}` |

## Webhooks

| Call | Notes |
|---|---|
| `POST /organizations/{org}/webhooks/` | Body (not wrapped): `endpoint_url`, `actions` (comma string), `event_id` (blank = all) |
| `GET /organizations/{org}/webhooks/` | |
| `DELETE /webhooks/{id}/` | |

## Seat maps

| Call | Notes |
|---|---|
| `GET /organizations/{org}/seatmaps/` | `venue_id`, `venue_name_filter`; not paginated yet |
| `POST /events/{id}/seatmaps/` | `{"source_seatmap_id": "..."}` — copy a seat map onto a new reserved-seating event; seat maps themselves are drawn in the web UI |

## Teams

Groups of attendees (races, tournaments): `GET /events/{id}/teams/`, `/teams/{tid}/`, `/teams/{tid}/attendees/`, `POST /events/{id}/teams/create/`, `/teams/{tid}/check_password/`, `GET /events/{id}/teams/search/?term=`.

## Deprecated / dead

| Endpoint | Status |
|---|---|
| `GET /events/search/` | Shut down Dec 2019 — no public event search |
| `POST/GET /webhooks/` (no org) | Dead since June 2020 |
| Org-less `/events/`, `/venues/` create/list | 403 on modern accounts — use `/organizations/{org}/...` |
| `event.description` field | Deprecated → structured content |
| `ticket_class.quantity_total` (write) | Deprecated → `capacity` |
| `split_fee` | Deprecated (`SPLIT_FEES_DEPRECATED`) |
| `GET /balance/...` | Internal (SOA token, Eventbrite hosts) — not usable with a personal token |
