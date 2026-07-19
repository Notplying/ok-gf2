"""Sends screenshot batches to a Discord channel via webhook."""
import json
import os
from pathlib import Path

import requests


def _load_dotenv():
    """Load .env file from the project root into os.environ.

    Only sets vars that are not already present in the environment.
    Supports simple KEY=VALUE lines, blank lines, and # comments.
    """
    # Walk up from this file to find the project root (where .git is)
    project_dir = Path(__file__).resolve().parent
    while project_dir != project_dir.parent:
        if (project_dir / ".env").exists():
            env_file = project_dir / ".env"
            break
        if (project_dir / ".git").exists():
            env_file = project_dir / ".env"
            break
        project_dir = project_dir.parent
    else:
        return  # No project root found

    if not env_file.is_file():
        return

    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Only set if not already present (env vars take precedence)
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


class DiscordNotifier:
    """Stateless helper that sends images to a Discord webhook."""

    @staticmethod
    def send_screenshots(paths, task_name="Platoon Members", content=None):
        """
        Send screenshot files to Discord in batches of 10.

        Args:
            paths: List of absolute file paths to PNG images.
            task_name: Label used in the embed title.
            content: Optional plain-text string sent alongside the first batch's
                images in the same Discord message (e.g. "gunsmoke").

        Returns:
            None — failures are logged, never raised.
        """
        from ok import Logger

        _load_dotenv()
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
                    first_payload = {
                        "embeds": [{
                            "title": f"{task_name} Screenshots",
                            "description": (
                                f"Pages {batch_idx + 1}–{batch_end} of {total}"
                            ),
                            "timestamp": Path(paths[0]).stat().st_mtime if False else None,
                        }]
                    }
                    if content:
                        first_payload["content"] = content
                    payload["payload_json"] = json.dumps(first_payload)
                else:
                    batch_payload = {
                        "content": f"Pages {batch_idx + 1}–{batch_end} of {total}"
                    }
                    if content:
                        batch_payload["content"] = f"{content}\nPages {batch_idx + 1}–{batch_end} of {total}"
                    payload["payload_json"] = json.dumps(batch_payload)

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
            logger.info(f"Discord: sent {sent}/{total} screenshots")
