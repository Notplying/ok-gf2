# Platoon Discord Webhook Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send PlatoonTask member screenshots to a Discord channel via webhook, batched in groups of up to 10, skipping the duplicate end-of-list frame.

**Architecture:** A new stateless `DiscordNotifier` helper reads the webhook URL from `DISCORD_WEBHOOK_URL` env var and POSTs images as multipart/form-data in batches of 10. `PlatoonTask._scroll_and_screenshot_members` saves frames to a known temp directory via `cv2.imwrite` (so we control the paths), tracks them, pops the duplicate, and calls the notifier after the loop.

**Tech Stack:** Python 3.12, `requests` (already in requirements.txt), `cv2` (already available), `os`/`json`/`pathlib` (stdlib)

## Global Constraints

- `DISCORD_WEBHOOK_URL` env var for the webhook URL; silently skip if not set
- No new pip dependencies — use `requests` already in requirements.txt
- Discord limit: 10 attachments per webhook message — batch accordingly
- Skip the duplicate screenshot that confirms end-of-list (the one where `mean_diff < 2.0`)
- Task must continue normally even if Discord sending fails

---

### Task 1: Create DiscordNotifier helper

**Files:**
- Create: `src/tasks/DiscordNotifier.py`

**Interfaces:**
- Produces: `DiscordNotifier.send_screenshots(paths: list[str], task_name: str) -> None`

This is a standalone utility — no dependencies on other tasks.

- [ ] **Step 1: Write the module**

```python
"""Sends screenshot batches to a Discord channel via webhook."""
import json
import os
from pathlib import Path

import requests


class DiscordNotifier:
    """Stateless helper that sends images to a Discord webhook."""

    @staticmethod
    def send_screenshots(paths, task_name="Platoon Members"):
        """
        Send screenshot files to Discord in batches of 10.

        Args:
            paths: List of absolute file paths to PNG images.
            task_name: Label used in the embed title.

        Returns:
            None — failures are logged, never raised.
        """
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        if not webhook_url:
            from ok import Logger
            Logger.get_logger(__name__).info(
                "DISCORD_WEBHOOK_URL not set — skipping Discord upload"
            )
            return

        logger = Logger.get_logger(__name__)
        paths = [p for p in paths if p and Path(p).exists()]
        if not paths:
            logger.info("No screenshot paths to send")
            return

        total = len(paths)
        batch_size = 10
        sent = 0

        for batch_idx in range(0, total, batch_size):
            batch = paths[batch_idx:batch_idx + batch_size]
            batch_end = min(batch_idx + len(batch), total)
            first = batch_idx == 0

            try:
                # --- build multipart payload ---
                payload = {}
                if first:
                    payload["payload_json"] = json.dumps({
                        "embeds": [{
                            "title": f"{task_name} Screenshots",
                            "description": (
                                f"Pages {batch_idx + 1}–{batch_end} of {total}"
                            ),
                            "timestamp": Path(paths[0]).stat().st_mtime if False else None,
                        }]
                    })
                else:
                    payload["payload_json"] = json.dumps({
                        "content": f"Pages {batch_idx + 1}–{batch_end} of {total}"
                    })

                files = []
                opened = []
                try:
                    for i, p in enumerate(batch):
                        f = open(p, "rb")
                        opened.append(f)
                        files.append((f"file{i}", (Path(p).name, f, "image/png")))

                    resp = requests.post(webhook_url, data=payload, files=files, timeout=30)
                    if resp.status_code in (200, 204):
                        sent += len(batch)
                        logger.info(
                            f"Discord: sent batch {batch_idx + 1}–{batch_end} "
                            f"({resp.status_code})"
                        )
                    else:
                        logger.error(
                            f"Discord webhook returned {resp.status_code}: {resp.text[:300]}"
                        )
                finally:
                    for f in opened:
                        f.close()

                if resp.status_code == 429:
                    retry_after = resp.json().get("retry_after", 5)
                    logger.warning(f"Discord rate-limited, suggested wait {retry_after}s")

            except requests.RequestException as e:
                logger.error(f"Discord webhook request failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending to Discord: {e}")

        if sent > 0:
            logger.info(f"Discord: sent {sent}/{total} screenshots", notify=True)
```

- [ ] **Step 2: Verify the import works**

Run: `& "x:/ok-gf2/venv/Scripts/python.exe" -c "import sys; sys.path.insert(0, 'src'); from tasks.DiscordNotifier import DiscordNotifier; print('import OK')"`

Expected: prints `import OK`

- [ ] **Step 3: Commit**

```bash
git add src/tasks/DiscordNotifier.py
git commit -m "feat: add DiscordNotifier helper for webhook screenshot uploads"
```

---

### Task 2: Modify PlatoonTask to collect paths and send to Discord

**Files:**
- Modify: `src/tasks/PlatoonTask.py:102-167` (the `_scroll_and_screenshot_members` method)

**Interfaces:**
- Consumes: `DiscordNotifier.send_screenshots(paths: list[str], task_name: str)` from Task 1
- Produces: updated `_scroll_and_screenshot_members()` with Discord integration

- [ ] **Step 1: Update `_scroll_and_screenshot_members` to track paths and send**

Replace the entire `_scroll_and_screenshot_members` method (lines 102–167) with:

```python
    def _scroll_and_screenshot_members(self, max_scrolls=30):
        """
        Scrolls the member list and takes a screenshot after each scroll.

        Uses click-and-drag (swipe) via PostMessage directly to the game window
        (background-safe, no focus needed). Screenshots are compared
        frame-to-frame to detect when the list stops changing (bottom reached).

        After capturing, sends screenshots to Discord if DISCORD_WEBHOOK_URL
        is configured. The duplicate frame that confirmed end-of-list is excluded.

        Args:
            max_scrolls: Maximum number of scrolls to prevent infinite loops.
        """
        from src.tasks.DiscordNotifier import DiscordNotifier

        self.sleep(1)  # Let the member list fully render

        # Temp directory for Discord-bound copies (we control paths here)
        screenshots_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "screenshots", ".discord_temp"
        )
        os.makedirs(screenshots_dir, exist_ok=True)

        prev_frame = None
        same_count = 0
        captured_paths = []

        for i in range(max_scrolls):
            self.info_set('scroll_index', i + 1)
            self.log_info(f"Screenshotting member page {i + 1}...")

            # Save via the normal screenshot system (debug tab, etc.)
            self.screenshot(f'platoon_members_page_{i + 1:03d}')

            # Also save a copy to a known path for Discord
            current_frame = self.frame
            if current_frame is not None:
                discord_path = os.path.join(
                    screenshots_dir, f"page_{i + 1:03d}.png"
                )
                cv2.imwrite(discord_path, current_frame)
                captured_paths.append(discord_path)
                self.log_info(f"Saved Discord copy: page_{i + 1:03d}")

            # Compare current frame with previous to detect end-of-list.
            if current_frame is not None and prev_frame is not None:
                h, w = current_frame.shape[:2]
                x1, y1 = int(w * 0.1), int(h * 0.2)
                x2, y2 = int(w * 0.9), int(h * 0.8)
                cur_crop = current_frame[y1:y2, x1:x2]
                prev_crop = prev_frame[y1:y2, x1:x2]

                cur_small = cv2.resize(cur_crop, (64, 64))
                prev_small = cv2.resize(prev_crop, (64, 64))
                diff = cv2.absdiff(cur_small, prev_small)
                mean_diff = np.mean(diff)

                self.log_info(f"Frame diff: {mean_diff:.2f}")

                if mean_diff < 2.0:  # Nearly identical — probably hit the bottom
                    same_count += 1
                    if same_count >= 1:
                        # Pop the duplicate before we send to Discord
                        if captured_paths:
                            dup = captured_paths.pop()
                            try:
                                os.remove(dup)
                            except OSError:
                                pass
                            self.log_info(
                                "Member list hasn't changed — reached end of list. "
                                "Removed duplicate screenshot. Stopping."
                            )
                        break
                else:
                    same_count = 0

            prev_frame = current_frame

            if i > 0 and i % 5 == 0:
                self.log_info(f"Progress: scrolled {i + 1} pages so far...")

            # Scroll down via mouse wheel.
            self.hwnd.bring_to_front()
            self.sleep(0.1)
            self.scroll_relative(0.5, 0.5, -25)
            self.sleep(2)  # Wait for the list to settle after scroll animation

        self.log_info(f"Finished scrolling. Pages captured: {len(captured_paths)}")

        # --- Send to Discord ---
        if captured_paths:
            self.log_info(
                f"Sending {len(captured_paths)} screenshots to Discord..."
            )
            DiscordNotifier.send_screenshots(captured_paths, "Platoon Members")

            # Clean up temp files
            for p in captured_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
            try:
                os.rmdir(screenshots_dir)
            except OSError:
                pass
```

- [ ] **Step 2: Verify the module still imports**

Run: `& "x:/ok-gf2/venv/Scripts/python.exe" -c "import sys; sys.path.insert(0, 'src'); from tasks.PlatoonTask import PlatoonTask; print('import OK')"`

Expected: prints `import OK`

- [ ] **Step 3: Commit**

```bash
git add src/tasks/PlatoonTask.py doc
git commit -m "feat: PlatoonTask sends screenshots to Discord via webhook"
```

---

### Task 3: Add DISCORD_WEBHOOK_URL to .env.example (optional documentation)

**Files:**
- Create: `.env.example` (if it doesn't exist)

**Interfaces:**
- None — documentation only.

- [ ] **Step 1: Create or update `.env.example`**

Check if `.env.example` exists. If it does, append the line. If not, create it:

```
# Discord webhook URL for PlatoonTask screenshot uploads
# Get this from Discord → Server Settings → Integrations → Webhooks → Create/Edit
DISCORD_WEBHOOK_URL=
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add DISCORD_WEBHOOK_URL to .env.example"
```
