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
        from ok import Logger

        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        if not webhook_url:
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
