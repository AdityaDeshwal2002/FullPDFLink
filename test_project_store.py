"""Offline checks for saved projects. Run: python3 -m unittest."""

import tempfile
import unittest
from pathlib import Path

from project_store import ProjectStore


CSV = b'ID,Title\n1,My Test Paper\n'


class ProjectStoreTests(unittest.TestCase):
    def test_completed_project_survives_restart_and_stays_locked(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore(Path(temp))
            project_id = store.create('First project', '📚')
            other_id = store.create('Second project', '🔬')
            store.save_upload(project_id, CSV, 'papers.csv', 'CSV', 'Title')
            token = store.begin_run(project_id, 1)
            store.add_result(project_id, token, {'ID': '1', 'Result': 'No confident match'})
            store.finish_run(project_id, token)

            reopened = ProjectStore(Path(temp))
            project = reopened.get(project_id)
            self.assertEqual(project['status'], 'complete')
            self.assertEqual(project['results'][0]['ID'], '1')
            self.assertEqual(reopened.input_path(project).read_bytes(), CSV)
            with self.assertRaises(ValueError):
                reopened.save_upload(project_id, CSV, 'other.csv', 'CSV', 'Title')
            with self.assertRaises(ValueError):
                reopened.begin_run(project_id, 1)

            reopened.rename(project_id, 'Renamed', '🌱')
            self.assertEqual(reopened.get(project_id)['name'], 'Renamed')
            reopened.delete(project_id)
            self.assertFalse(reopened._folder(project_id).exists())
            self.assertEqual(reopened.list_projects()[0]['id'], other_id)

    def test_interrupted_run_can_retry_same_upload(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore(Path(temp))
            project_id = store.create('Draft', '📄')
            store.save_upload(project_id, CSV, 'papers.csv', 'CSV', 'Title')
            first_token = store.begin_run(project_id, 1)
            store.add_result(project_id, first_token, {'ID': '1'})
            store.recover_interrupted()
            self.assertEqual(store.get(project_id)['status'], 'interrupted')
            with self.assertRaises(ValueError):
                store.add_result(project_id, first_token, {'ID': '2'})
            second_token = store.begin_run(project_id, 1)
            self.assertEqual(store.get(project_id)['results'], [])
            store.add_result(project_id, second_token, {'ID': '1'})
            store.finish_run(project_id, second_token)
            self.assertEqual(store.get(project_id)['status'], 'complete')


if __name__ == '__main__':
    unittest.main()
