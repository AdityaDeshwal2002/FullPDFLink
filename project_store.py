"""Local project metadata and files for the single-user Streamlit app."""

import json
import re
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from paper_finder import load_sheets


class ProjectStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / 'projects.db'
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                emoji TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                filename TEXT,
                input_file TEXT,
                sheet TEXT,
                title_column TEXT,
                results TEXT NOT NULL DEFAULT '[]',
                completed_count INTEGER NOT NULL DEFAULT 0,
                total_count INTEGER NOT NULL DEFAULT 0,
                run_token TEXT,
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )''')

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _folder(self, project_id: str) -> Path:
        if not re.fullmatch(r'[0-9a-f]{32}', project_id):
            raise ValueError('Invalid project ID')
        return self.root / 'projects' / project_id

    def list_projects(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute('SELECT id, name, emoji, status FROM projects '
                              'ORDER BY created_at DESC, rowid DESC').fetchall()
        return [dict(row) for row in rows]

    def get(self, project_id: str) -> dict:
        with self._connect() as db:
            row = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        if row is None:
            raise KeyError('Project not found')
        project = dict(row)
        project['results'] = json.loads(project['results'])
        return project

    def create(self, name: str, emoji: str) -> str:
        name = name.strip()
        if not name or len(name) > 100:
            raise ValueError('Project name must be 1–100 characters')
        if not emoji or len(emoji) > 16:
            raise ValueError('Choose one emoji')
        project_id = uuid.uuid4().hex
        with self._connect() as db:
            db.execute('INSERT INTO projects (id, name, emoji) VALUES (?, ?, ?)',
                       (project_id, name, emoji))
        return project_id

    def rename(self, project_id: str, name: str, emoji: str) -> None:
        name = name.strip()
        if not name or len(name) > 100:
            raise ValueError('Project name must be 1–100 characters')
        if not emoji or len(emoji) > 16:
            raise ValueError('Choose one emoji')
        with self._connect() as db:
            cursor = db.execute('UPDATE projects SET name = ?, emoji = ? WHERE id = ?',
                                (name, emoji, project_id))
            if cursor.rowcount != 1:
                raise KeyError('Project not found')

    def save_upload(self, project_id: str, data: bytes, filename: str,
                    sheet: str, title_column: str) -> None:
        suffix = Path(filename).suffix.lower()
        if suffix not in ('.csv', '.xlsx'):
            raise ValueError('Upload a CSV or XLSX file')
        sheets = load_sheets(data, filename)
        if sheet not in sheets or not sheets[sheet] or title_column not in sheets[sheet][0]:
            raise ValueError('Choose a nonempty sheet and a valid title column')
        project = self.get(project_id)
        if project['status'] != 'draft':
            raise ValueError('The upload is locked after a run starts')
        folder = self._folder(project_id)
        folder.mkdir(parents=True, exist_ok=True)
        input_file = uuid.uuid4().hex + suffix
        path = folder / input_file
        path.write_bytes(data)
        try:
            with self._connect() as db:
                cursor = db.execute('''UPDATE projects SET filename = ?, input_file = ?,
                    sheet = ?, title_column = ? WHERE id = ? AND status = 'draft' ''',
                    (Path(filename).name, input_file, sheet, title_column, project_id))
                if cursor.rowcount != 1:
                    raise ValueError('The upload is locked after a run starts')
        except Exception:
            path.unlink(missing_ok=True)
            raise
        if project['input_file']:
            (folder / project['input_file']).unlink(missing_ok=True)

    def input_path(self, project: dict) -> Path:
        if not project['input_file']:
            raise ValueError('Upload a spreadsheet first')
        return self._folder(project['id']) / project['input_file']

    def pdf_folder(self, project_id: str) -> Path:
        return self._folder(project_id) / 'pdfs'

    def zip_path(self, project_id: str) -> Path:
        return self._folder(project_id) / 'downloaded_pdfs.zip'

    def begin_run(self, project_id: str, total_count: int) -> str:
        project = self.get(project_id)
        if project['status'] not in ('draft', 'interrupted') or not project['input_file']:
            raise ValueError('This project cannot be run')
        if total_count < 1:
            raise ValueError('There are no titles to search')
        if self.pdf_folder(project_id).exists():
            shutil.rmtree(self.pdf_folder(project_id))
        self.zip_path(project_id).unlink(missing_ok=True)
        self.pdf_folder(project_id).mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        with self._connect() as db:
            cursor = db.execute('''UPDATE projects SET status = 'running', results = '[]',
                completed_count = 0, total_count = ?, run_token = ?, error = ''
                WHERE id = ? AND status IN ('draft', 'interrupted')''',
                (total_count, token, project_id))
            if cursor.rowcount != 1:
                raise ValueError('This project is already running or complete')
        return token

    def add_result(self, project_id: str, token: str, result: dict) -> None:
        project = self.get(project_id)
        if project['status'] != 'running' or project['run_token'] != token:
            raise ValueError('This run is no longer active')
        results = project['results']
        results.append(result)
        with self._connect() as db:
            cursor = db.execute('''UPDATE projects SET results = ?, completed_count = ?
                WHERE id = ? AND status = 'running' AND run_token = ?''',
                (json.dumps(results), len(results), project_id, token))
            if cursor.rowcount != 1:
                raise ValueError('This run is no longer active')

    def finish_run(self, project_id: str, token: str) -> None:
        with self._connect() as db:
            cursor = db.execute('''UPDATE projects SET status = 'complete', run_token = NULL
                WHERE id = ? AND status = 'running' AND run_token = ?
                AND completed_count = total_count''', (project_id, token))
            if cursor.rowcount != 1:
                raise ValueError('This run is incomplete or no longer active')

    def interrupt_run(self, project_id: str, token: str, error: str = '') -> None:
        with self._connect() as db:
            db.execute('''UPDATE projects SET status = 'interrupted', run_token = NULL,
                error = ? WHERE id = ? AND status = 'running' AND run_token = ?''',
                (error[:500], project_id, token))

    def recover_interrupted(self) -> None:
        with self._connect() as db:
            db.execute("UPDATE projects SET status = 'interrupted', run_token = NULL "
                       "WHERE status = 'running'")

    def delete(self, project_id: str) -> None:
        self.get(project_id)
        if self._folder(project_id).exists():
            shutil.rmtree(self._folder(project_id))
        with self._connect() as db:
            db.execute('DELETE FROM projects WHERE id = ?', (project_id,))
