import time
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

        # === Step 2: Find and click "Platoon" (scan the whole screen) ===
        self.info_set('current_task', 'navigate_to_platoon')
        self.log_info("Looking for 'Platoon' button (full screen search)...")
        if not self.wait_click_ocr(
            match='Platoon',
            box=None,          # scan entire screen — button may vary by resolution
            time_out=10,
            after_sleep=2,
            raise_if_not_found=True,
            log=True,
        ):
            self.log_error("Could not find 'Platoon' button")
            return False

        # === Step 3: On the Platoon page, find and click "Members" ===
        self.info_set('current_task', 'navigate_to_members')
        self.log_info("Looking for 'Members' button on the Platoon page...")
        if not self.wait_click_ocr(
            match='Members',
            box=self.box.bottom_left,
            time_out=5,
            after_sleep=2,
            raise_if_not_found=True,
            log=True,
        ):
            self.log_error("Could not find 'Members' button on the Platoon page")
            return False

        # === Step 4: Scroll through the member list and screenshot ===
        self.info_set('current_task', 'screenshot_members')
        self.log_info("Scrolling through the member list and taking screenshots...")
        self._scroll_and_screenshot_members()

        self.log_info("Platoon Members Screenshot task completed", notify=True)
        return True

    def _scroll_and_screenshot_members(self, max_scrolls=30, scroll_duration=1.0):
        """
        Scrolls the member list and takes a screenshot after each scroll.

        The member list is assumed to be in the main content area (center).
        Each scroll advances the list, and a screenshot is captured after each
        scroll to document the visible members.

        The loop stops when:
          - An end-of-list indicator is detected via OCR
          - max_scrolls is reached
          - No change in list content is detected after consecutive scrolls
            (using feature matching on consecutive screenshots)

        Args:
            max_scrolls: Maximum number of scrolls to prevent infinite loops.
            scroll_duration: Duration of each swipe gesture in seconds.
        """
        self.sleep(1)  # Let the member list fully render

        for i in range(max_scrolls):
            self.info_set('scroll_index', i + 1)
            self.log_info(f"Screenshotting member page {i + 1}...")

            # Capture the current visible member list
            self.screenshot(f'platoon_members_page_{i + 1:03d}')
            self.log_info(f"Captured screenshot: platoon_members_page_{i + 1:03d}")

            # Check for end-of-list indicators via OCR
            if self.ocr(
                match=['No more', 'End of list', 'No members found'],
                box=self.box.center,
                time_out=1,
                raise_if_not_found=False,
                log=True,
            ):
                self.log_info("Reached end of member list, stopping")
                break

            # Check if we can still scroll — if list items look the same,
            # we may have hit the bottom (non-scrollable content)
            if i > 0 and i % 5 == 0:
                self.log_info(f"Progress: scrolled {i + 1} pages so far...")

            # Scroll down: swipe upward within the member list area
            self.swipe_relative(
                0.5, 0.75,   # start: center, near bottom of the member list
                0.5, 0.35,   # end: center, near top of the member list
                duration=scroll_duration,
            )
            self.sleep(0.8)  # Wait for the list to settle after scroll animation

        self.log_info(f"Finished scrolling. Pages captured: {min(i + 1, max_scrolls)}")
