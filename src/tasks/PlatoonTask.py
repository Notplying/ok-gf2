import os
import time

import cv2
import numpy as np
from ok import Logger, TaskDisabledException
from src.tasks.BaseGfTask import BaseGfTask

logger = Logger.get_logger(__name__)


class PlatoonTask(BaseGfTask):
    """
    Task that navigates to Platoon → Members, scrolls through the member list,
    and takes screenshots of all members.

    Prerequisites:
        - The game must have been logged into at least once so credentials are
          remembered. GF2 PC client auto-authenticates on subsequent launches.
        - ensure_main() handles clicking "点击开始" (Tap to Start) and
          dismissing announcement pop-ups to reach the main screen.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Platoon Members Screenshot"
        self.description = (
            "Navigates to Platoon → Members, scrolls the member list, "
            "and screenshots all members. Game must be running (logged in)."
        )
        self.support_schedule_task = True

    def run(self):
        """
        Main entry point. Steps:
          1. Ensure we are on the main screen (auto-login via ensure_main).
          2. Find and click "Platoon" in the bottom-right area.
          3. On the Platoon page, find and click "Members".
          4. Scroll through the member list, screenshotting each batch.
        """
        self.log_info("Starting Platoon Members Screenshot task")

        # === Step 1: Auto-login / ensure main screen ===
        # ensure_main handles the full login flow:
        #   1. Waits for game window to be ready
        #   2. Clicks "点击开始" (Tap to Start) at the title screen
        #   3. Dismisses announcement pop-ups and event notices
        #   4. Presses ESC to backtrack if on a sub-screen
        #   5. Verifies main screen UI elements are visible
        # Timeout of 120s accounts for game startup, title screen, and
        # any post-update shader compilation.
        self.info_set('current_task', 'auto_login_and_ensure_main')
        self.hwnd.bring_to_front()
        self.sleep(0.1)
        self.log_info("Auto-logging in: waiting for game to reach main screen (timeout=120s)...")
        try:
            self.ensure_main(recheck_time=2, time_out=120)
        except TaskDisabledException:
            raise
        except Exception:
            self.log_error("Could not reach main screen. Is the game running?")
            self.kill_all_related_processes()
            raise Exception(
                "Failed to reach main screen. Make sure the game is running "
                "and you have logged in at least once before."
            )

        # Let the main screen fully settle before searching
        self.sleep(5)

        # === Step 2: Find and click "Platoon" via template matching ===
        self.info_set('current_task', 'navigate_to_platoon')
        self.log_info("Looking for 'Platoon' button via template matching (full screen search)...")
        if not self.wait_click_feature(
            feature='platoon_button_main',
            time_out=10,
            after_sleep=2,
            raise_if_not_found=True,
        ):
            self.log_error("Could not find 'Platoon' button")
            return False

        # === Step 3: On the Platoon page, find and click "Members" via template matching ===
        self.info_set('current_task', 'navigate_to_members')
        self.log_info("Looking for 'Members' button via template matching...")
        if not self.wait_click_feature(
            feature='member_button_platoon',
            time_out=5,
            after_sleep=2,
            raise_if_not_found=True,
        ):
            self.log_error("Could not find 'Members' button on the Platoon page")
            return False

        # === Step 4: Scroll through the member list and screenshot ===
        self.info_set('current_task', 'screenshot_members')
        self.log_info("Scrolling through the member list and taking screenshots...")
        self._scroll_and_screenshot_members()

        self.log_info("Platoon Members Screenshot task completed", notify=True)
        return True

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

        if not captured_paths:
            try:
                os.rmdir(screenshots_dir)
            except OSError:
                pass

        # --- Send to Discord ---
        try:
            from src.tasks.DiscordNotifier import DiscordNotifier
            if captured_paths:
                self.log_info(
                    f"Sending {len(captured_paths)} screenshots to Discord..."
                )
                DiscordNotifier.send_screenshots(captured_paths, "Platoon Members")
        except Exception as e:
            self.log_info(f"Discord notification failed: {e} — continuing")
        finally:
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
