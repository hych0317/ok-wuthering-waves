import os
import tempfile
import unittest
from unittest.mock import patch

from src.task.MultiAccountDailyTask import MultiAccountDailyTask


class TestMultiAccountDailyTask(unittest.TestCase):

    def test_daily_launcher_marker_is_written_atomically_after_success(self):
        class FakeTask:
            def log_info(self, *args):
                pass

        with tempfile.TemporaryDirectory() as temp_dir:
            marker_path = os.path.join(temp_dir, '.okww_last_run')
            with patch.dict(os.environ, {
                'OKWW_DAILY_RUN_MARKER': marker_path,
                'OKWW_DAILY_RUN_DATE': '2026-08-09',
            }):
                MultiAccountDailyTask._mark_daily_launcher_success(FakeTask())

            with open(marker_path, 'r', encoding='utf-8') as marker:
                self.assertEqual(marker.read(), '2026-08-09\n')
            self.assertFalse(os.path.exists(f'{marker_path}.tmp'))

    @patch('src.task.MultiAccountDailyTask.threading.Timer')
    @patch('src.task.MultiAccountDailyTask.communicate')
    def test_failed_daily_launcher_schedules_app_exit(self, communicate, timer_class):
        class FakeTask:
            def log_info(self, *args):
                pass

        timer = timer_class.return_value
        with patch.dict(os.environ, {
            'OKWW_DAILY_RUN_MARKER': 'C:\\temp\\.okww_last_run',
            'OKWW_DAILY_RUN_DATE': '2026-08-10',
        }):
            MultiAccountDailyTask._quit_failed_daily_launcher_instance(FakeTask())

        timer_class.assert_called_once_with(1.0, communicate.quit.emit)
        self.assertTrue(timer.daemon)
        timer.start.assert_called_once_with()

    def test_account_selection_recovers_after_account_list_timeout(self):
        class FakeExecutor:
            def get_task_by_class(self, task_class):
                return None

        class FakeTask:
            def __init__(self):
                self.executor = FakeExecutor()
                self.overlay_checks = 0
                self.list_checks = 0
                self.login_clicked = False
                self.main_waited = False

            def log_info(self, *args):
                pass

            def sleep(self, *args):
                pass

            def _ensure_account_switch_overlay(self, time_out=30):
                self.overlay_checks += 1
                return True

            def _login_page_state(self):
                return 'account_switch_overlay'

            def _click_center_offset(self, *args, **kwargs):
                pass

            def _click_account_in_list(self, suffix):
                self.list_checks += 1
                return self.list_checks >= 2

            def _detect_login_page_state(self, time_out=2):
                return 'account_switch_overlay'

            def _selected_account_matches(self, suffix, selected_account):
                selected_account[0] = suffix
                return True

            def wait_until(self, condition, **kwargs):
                return condition()

            def _click_login_button(self):
                self.login_clicked = True

            def ensure_main(self, time_out=180):
                self.main_waited = True

        task = FakeTask()

        MultiAccountDailyTask._select_and_login_account(task, '1001')

        self.assertEqual(task.overlay_checks, 2)
        self.assertEqual(task.list_checks, 2)
        self.assertTrue(task.login_clicked)
        self.assertTrue(task.main_waited)
        self.assertFalse(task.logged_in)
        self.assertFalse(task._logged_in)

    def test_account_text_parsing_keeps_unique_four_digit_suffixes(self):
        parsed = MultiAccountDailyTask._parse_account_text(
            object(), '1001\ninvalid\n2002\n1001\n12345'
        )

        self.assertEqual(parsed, ['1001', '2002'])

    def test_account_queue_starts_with_detected_configured_account(self):
        class FakeTask:
            def log_info(self, *args):
                pass

        queue = MultiAccountDailyTask._account_run_queue(
            FakeTask(), ['1001', '2002'], '2002'
        )

        self.assertEqual(queue, ['2002', '1001'])

    def test_account_overlay_reopens_when_title_page_is_detected(self):
        class FakeTask:
            def __init__(self):
                self.advance_timeout = None

            def _detect_login_page_state(self, time_out=3):
                return 'connected_title_page'

            def log_info(self, *args):
                pass

            def _advance_login_page_to_account_switch(self, time_out=30):
                self.advance_timeout = time_out
                return True

        task = FakeTask()

        recovered = MultiAccountDailyTask._ensure_account_switch_overlay(task, time_out=25)

        self.assertTrue(recovered)
        self.assertEqual(task.advance_timeout, 25)


if __name__ == "__main__":
    unittest.main()
