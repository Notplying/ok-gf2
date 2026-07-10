# Platoon Discord Webhook Integration

**Date:** 2026-07-10
**Status:** Approved

## Overview

Extend PlatoonTask to send captured platoon member screenshots to a Discord
channel via a Discord webhook URL configured as an environment variable.

## Configuration

- `DISCORD_WEBHOOK_URL` environment variable holds the webhook URL.
- If not set, Discord sending is silently skipped — the task works as before.
- No changes to `config.py` or any existing config files.

## New file: `src/tasks/DiscordNotifier.py`

A stateless helper with one static method:

```
DiscordNotifier.send_screenshots(paths: list[str], task_name: str) -> bool
```

### Behavior

1. Read `DISCORD_WEBHOOK_URL` from `os.environ`.
2. If missing or empty, log info and return `False` — no-op.
3. Split `paths` into batches of 10.
4. For each batch, POST a multipart/form-data request via `requests`:
   - **First batch:** Includes a Discord embed with:
     - Title: `{task_name} Screenshots`
     - Timestamp (ISO 8601)
     - Page count: `"Pages 1–N of M"`
   - **Subsequent batches:** Simple `"Pages X–Y of M"` payload text.
   - Attach up to 10 image files as multipart uploads.
5. On failure: log the error, return `False`. Does NOT raise — the task
   continues regardless.
6. On success: log info with count, return `True`.

### Dependencies

Only `requests` and `os` — both already available (requests is in
`requirements.txt`).

## Modified file: `src/tasks/PlatoonTask.py`

### Changes to `_scroll_and_screenshot_members()`

Instead of just calling `self.screenshot()`, collect paths:

```python
captured_paths = []

for i in range(max_scrolls):
    path = self.screenshot(f'platoon_members_page_{i + 1:03d}')
    captured_paths.append(path)

    # Frame comparison to detect end-of-list...
    if mean_diff < 2.0:
        # Remove the duplicate (last screenshot) before breaking
        # Actually, the duplicate IS this screenshot — the current frame
        # matches the previous one. So we pop the last path since this
        # screenshot is identical to the previous page.
        captured_paths.pop()
        break
```

Wait — let's look at this more carefully. In the current code:

1. `screenshot()` is called (captures current frame)
2. Then the frame is compared to `prev_frame`
3. If diff < 2.0, break

So when we detect a duplicate, the screenshot we just took IS the duplicate.
We should NOT append it if we're about to detect its duplicate; or we append
and then pop if it's a duplicate.

Simpler approach: screenshot first, append, compare, if duplicate, pop the
last entry and break.

### After the loop

```python
from src.tasks.DiscordNotifier import DiscordNotifier

DiscordNotifier.send_screenshots(captured_paths, "Platoon Members")
```

### Screenshot path

The `self.screenshot(name)` method (from BaseTask/ok-script) saves to
`{screenshots_folder}/{name}.png` and is assumed to return the full path.
If it doesn't return a path, construct it from the known naming convention
and `screenshots_folder` config.

## Edge Cases

| Case | Behavior |
|------|----------|
| `DISCORD_WEBHOOK_URL` not set | Skipped silently |
| Webhook HTTP error | Logged, task continues |
| 0 screenshots captured | `send_screenshots` returns early (no-op) |
| 1–10 screenshots | Single Discord message with embed |
| 11–20 screenshots | Two messages: embed + 10, then 1–10 more |
| Duplicate end-of-list frame | Popped from list, never sent |
| Webhook URL invalid (timeout, DNS) | Logged, task continues |
