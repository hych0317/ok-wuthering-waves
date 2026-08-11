import tempfile
import unittest
from pathlib import Path

from scripts.resolve_onetime_task_index import resolve_onetime_task_index


class TestDailyLauncher(unittest.TestCase):
    def _write_config(self, source):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        config_path = Path(temp_dir.name) / 'config.py'
        config_path.write_text(source, encoding='utf-8')
        return config_path

    def test_resolves_one_based_task_index_by_class_name(self):
        config_path = self._write_config(
            "config = {'onetime_tasks': ["
            "['src.task.DailyTask', 'DailyTask'], "
            "['src.task.MultiAccountDailyTask', 'MultiAccountDailyTask']]}"
        )

        index = resolve_onetime_task_index(config_path, 'MultiAccountDailyTask')

        self.assertEqual(2, index)

    def test_returns_zero_when_task_is_not_registered(self):
        config_path = self._write_config(
            "config = {'onetime_tasks': [['src.task.DailyTask', 'DailyTask']]}"
        )

        index = resolve_onetime_task_index(config_path, 'MultiAccountDailyTask')

        self.assertEqual(0, index)


if __name__ == '__main__':
    unittest.main()
