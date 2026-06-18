# API Contract

The real dashboard can stay simple and call these endpoints.

## `GET /api/overview`

Returns mission text, impact totals, and the highest-priority action cards.

Use this for the dashboard home page.

## `GET /api/energy`

Returns energy waste estimate and the top energy anomaly rows/cards.

Use this for ScheduleGhost / energy module views.

## `GET /api/water`

Returns unresolved or needs-verification water alerts.

Use this for Aqualert / LeakListener cards.

The response now also includes:

- `live_sensor` for the newest Arduino ultrasonic reading
- `live_history` for recent USB-serial readings shown on the dashboard

## `GET /api/water/live`

Returns only the live Arduino feed summary and recent readings.

## `POST /api/water/live`

Accepts one Arduino reading from the local serial bridge and stores it for the dashboard. If `SUPABASE_SYNC_URL` and `SUPABASE_SECRET_KEY` are configured, the backend also forwards the reading into Supabase as a water operations log.

## `GET /api/waste`

Returns low-confidence or contaminated waste decisions.

Use this for Compost AI / BinGuard human review.

## `GET /api/events`

Returns event outcome summaries and event-planning action cards.

Use this for event footprint planning.

## `GET /api/event-plan`

Query params:

- `event_type`
- `expected_attendance`
- `duration_hr`

Returns recommended food servings, energy scheduling note, and human-check note.

Example:

```text
/api/event-plan?event_type=sports&expected_attendance=250&duration_hr=3
```

## `POST /api/agent/query`

Request:

```json
{
  "query": "What should we fix first before Friday's volleyball game?",
  "voice_mode": false
}
```

Response:

```json
{
  "answer": "Concise agent answer",
  "action_cards": [],
  "citations": [],
  "used_llm": false
}
```

The dashboard can send either typed text or a voice transcript.

## `POST /api/rag/search`

Request:

```json
{
  "query": "judging rubric responsible AI",
  "top_k": 5
}
```

Returns the retrieved chunks used by the agent.
