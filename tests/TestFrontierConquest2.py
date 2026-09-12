# Test case
import unittest
from unittest.mock import Mock, PropertyMock, patch

import numpy as np

from ok.test.TaskTestCase import TaskTestCase
from src.config import config
from src.tasks.FrontierConquestTask import FrontierConquestTask
from src.tasks.FrontierConquestTask2 import FrontierConquestTask2

BASE_NAME = 'Frontier Conquest Ranking Screenshot'
SECOND_NAME = 'Frontier Conquest Ranking Screenshot 2'

EXPECTED_FEATURE_ORDER = [
    'platoon_button_main',
    'fc_platoon_button',
    'fc_close_update',
    'fc_score_button',
    'fc_platoon_ranking',
]


class TestFrontierConquestTask2(TaskTestCase):
    """FrontierConquestTask2 is a scheduling duplicate of FrontierConquestTask.

    It must behave identically apart from its display name, so these tests
    pin the flow it shares with the base task as much as the name it changes.
    """

    task_class = FrontierConquestTask2

    config = config

    def _run_task(self, close_update_found):
        features = []
        sleeps = []

        def fake_wait_click_feature(feature, **kwargs):
            features.append(feature)
            return close_update_found if feature == 'fc_close_update' else True

        with patch.object(FrontierConquestTask2, 'hwnd', new_callable=PropertyMock,
                          return_value=Mock()), \
                patch.object(self.task, 'ensure_main'), \
                patch.object(self.task, 'sleep', side_effect=sleeps.append), \
                patch.object(self.task, 'wait_click_feature',
                             side_effect=fake_wait_click_feature), \
                patch.object(self.task, '_scroll_and_screenshot_ranking') as scroll:
            result = self.task.run()

        return features, sleeps, result, scroll

    def test_is_a_distinct_task(self):
        """The copy must be separately schedulable, not a name collision."""
        self.assertEqual(self.task.name, SECOND_NAME)
        self.assertNotEqual(self.task.name, BASE_NAME)
        self.assertIsNot(FrontierConquestTask2, FrontierConquestTask)
        # Both must be registered, or the duplicate never appears in the UI.
        registered = [name for _, name in config['onetime_tasks']]
        self.assertIn('FrontierConquestTask', registered)
        self.assertIn('FrontierConquestTask2', registered)

    def test_missing_close_update_continues_gracefully(self):
        features, sleeps, result, scroll = self._run_task(close_update_found=False)

        self.assertEqual(features, EXPECTED_FEATURE_ORDER)
        self.assertIn(25, sleeps, 'expected a 25s wait for the FC page to settle')
        self.assertTrue(result)
        scroll.assert_called_once()

    def test_upload_uses_frontier_conquest_content(self):
        """Both FC instances post under the same frontier_conquest tag."""
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(FrontierConquestTask2, 'hwnd', new_callable=PropertyMock,
                          return_value=Mock()), \
                patch.object(FrontierConquestTask2, 'frame',
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
