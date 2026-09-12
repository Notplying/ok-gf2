# Test case
import unittest
from unittest.mock import Mock, PropertyMock, patch

import numpy as np

from ok.test.TaskTestCase import TaskTestCase
from src.config import config
from src.tasks.FrontierConquestTask import FrontierConquestTask

# The screenshot the fc_* templates were annotated against.
FC_SCREENSHOT = 'assets/images/2.png'

FC_FEATURES = [
    'fc_platoon_button',
    'fc_close_update',
    'fc_score_button',
    'fc_platoon_ranking',
]

# The order the task must visit these features in.
EXPECTED_FEATURE_ORDER = [
    'platoon_button_main',
    'fc_platoon_button',
    'fc_close_update',
    'fc_score_button',
    'fc_platoon_ranking',
]


class TestFrontierConquestTask(TaskTestCase):
    """Covers the Frontier Conquest ranking task without a live game."""

    task_class = FrontierConquestTask

    config = config

    def _run_task(self, close_update_found):
        """Runs the task with the game, sleeps and scrolling stubbed out.

        Returns the features passed to wait_click_feature in order, the sleep
        durations requested, and the run() return value.
        """
        features = []
        sleeps = []

        def fake_wait_click_feature(feature, **kwargs):
            features.append(feature)
            return close_update_found if feature == 'fc_close_update' else True

        with patch.object(FrontierConquestTask, 'hwnd', new_callable=PropertyMock,
                          return_value=Mock()), \
                patch.object(self.task, 'ensure_main'), \
                patch.object(self.task, 'sleep', side_effect=sleeps.append), \
                patch.object(self.task, 'wait_click_feature',
                             side_effect=fake_wait_click_feature), \
                patch.object(self.task, '_scroll_and_screenshot_ranking') as scroll:
            result = self.task.run()

        return features, sleeps, result, scroll

    def test_fc_templates_are_found(self):
        """The fc_* templates must resolve against the screenshot they were labelled on."""
        self.set_image(FC_SCREENSHOT)
        for feature in FC_FEATURES:
            with self.subTest(feature=feature):
                self.assertIsNotNone(
                    self.task.find_one(feature), f'{feature} matched nothing'
                )

    def test_missing_close_update_continues_gracefully(self):
        features, sleeps, result, scroll = self._run_task(close_update_found=False)

        # The probe still runs and is recorded, but its miss must not divert
        # the flow: the remaining screens are still visited in order.
        self.assertEqual(features, EXPECTED_FEATURE_ORDER)
        self.assertIn(25, sleeps, 'expected a 25s wait for the FC page to settle')
        self.assertTrue(result)
        scroll.assert_called_once()

    def test_upload_uses_frontier_conquest_content(self):
        """Captures are uploaded to Discord tagged as frontier_conquest."""
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(FrontierConquestTask, 'hwnd', new_callable=PropertyMock,
                          return_value=Mock()), \
                patch.object(FrontierConquestTask, 'frame',
                             new_callable=PropertyMock, return_value=frame), \
                patch.object(self.task, 'sleep'), \
                patch.object(self.task, 'screenshot'), \
                patch.object(self.task, 'scroll_relative'), \
                patch('src.tasks.DiscordNotifier.DiscordNotifier.send_screenshots') \
                as send_screenshots:
            self.task._scroll_and_screenshot_ranking()

        send_screenshots.assert_called_once()
        self.assertEqual(send_screenshots.call_args.kwargs.get('content'),
                         'frontier_conquest')

    def test_visits_fc_screens_in_order(self):
        features, sleeps, result, scroll = self._run_task(close_update_found=True)

        self.assertEqual(features, EXPECTED_FEATURE_ORDER)
        self.assertIn(25, sleeps, 'expected a 25s wait for the FC page to settle')
        self.assertTrue(result)
        scroll.assert_called_once()


if __name__ == '__main__':
    unittest.main()
