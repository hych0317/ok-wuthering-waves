import unittest

from ok import CannotFindException
from src.task.TacetTask import TacetTask


class TestTacetTaskLogic(unittest.TestCase):

    def test_transient_combat_exit_retries_before_reward_claim(self):
        class FakeTask:
            stamina_once = 60

            def __init__(self):
                self.combat_attempts = 0
                self.reward_claims = 0

            def info_incr(self, *args):
                pass

            def sleep(self, timeout):
                pass

            def openF2Book(self, feature):
                pass

            def get_stamina(self):
                return 160, 0, 160

            def open_boss_book(self, name):
                pass

            def teleport_to_tacet(self, index):
                return True

            def click_team_challenge(self):
                pass

            def wait_in_team_and_world(self, time_out):
                pass

            def combat_once(self, target):
                self.combat_attempts += 1
                if self.combat_attempts == 1:
                    raise RuntimeError('transient in_team detection failure')

            def walk_to_treasure(self):
                pass

            def pick_f(self, handle_claim):
                self.reward_claims += 1

            def log_error(self, *args):
                pass

            def use_tacet_stamina(self, must_use):
                return False, self.stamina_once

            def log_info(self, message):
                pass

            def click(self, *args, **kwargs):
                pass

        task = FakeTask()

        TacetTask.farm_tacet(
            task,
            daily=True,
            used_stamina=0,
            config={'Which Tacet Suppression to Farm': 1},
        )

        self.assertEqual(task.combat_attempts, 2)
        self.assertEqual(task.reward_claims, 1)

    def test_reward_stamina_read_retries_before_succeeding(self):
        class FakeTask:
            stamina_once = 60

            def __init__(self):
                self.attempts = 0
                self.sleeps = []

            def use_stamina(self, once, must_use):
                self.attempts += 1
                if self.attempts < 3:
                    raise CannotFindException('temporary OCR failure')
                return False, once

            def log_warning(self, message):
                pass

            def sleep(self, timeout):
                self.sleeps.append(timeout)

        task = FakeTask()

        result = TacetTask.use_tacet_stamina(task, must_use=180)

        self.assertEqual(result, (False, 60))
        self.assertEqual(task.attempts, 3)
        self.assertEqual(task.sleeps, [1, 1])


if __name__ == '__main__':
    unittest.main()
