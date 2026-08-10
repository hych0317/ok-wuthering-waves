import unittest

from src.task.DailyTask import DailyTask


class TestDailyTaskLogic(unittest.TestCase):

    def test_pending_daily_reward_clicks_topmost_ocr_button(self):
        class ClaimBox:
            def __init__(self, y):
                self.y = y

        top = ClaimBox(120)
        lower = ClaimBox(420)

        class FakeTask:
            def __init__(self):
                self.clicked = []

            def ocr(self, *args, **kwargs):
                return [lower, top]

            def log_info(self, *args):
                pass

            def click_box(self, box, after_sleep=0):
                self.clicked.append(box)

            def click(self, *args, **kwargs):
                raise AssertionError('fallback coordinate should not be used when OCR succeeds')

        task = FakeTask()

        found = DailyTask.click_pending_daily_quest_reward(task)

        self.assertTrue(found)
        self.assertEqual(task.clicked, [top])


if __name__ == '__main__':
    unittest.main()
