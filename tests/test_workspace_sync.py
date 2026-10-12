'''
Chạy: python -m unittest discover tests

- WorkspaceSyncService: dùng scanner giả + repository giả, không đụng ổ đĩa hay CSDL.
- LocalWorkspaceScanner: quét một thư mục tạm thật.
'''
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.app.ports.storage import WorkspaceEntry
from src.app.services.workspace_sync_service import WorkspaceSyncService
from src.dom.entities.file import File
from src.inf.storage.local_workspace_scanner import LocalWorkspaceScanner


def entry(path, is_directory=False, size=0, file_type=None, mime_type=None):
    parent = path.rsplit('/', 1)[0] if '/' in path else None
    return WorkspaceEntry(
        path=path,
        name=path.rsplit('/', 1)[-1],
        parent_path=parent,
        is_directory=is_directory,
        file_type=file_type,
        mime_type=mime_type,
        size=size,
    )


class FakeScanner:
    def __init__(self, entries):
        self.entries = entries

    def scan(self, workspace_dir):
        return self.entries


class FakeFilesRepository:
    def __init__(self, files=()):
        self.files = {f.id: f for f in files}
        self.calls = []

    def get_by_conversation_id(self, conversation_id):
        return [f for f in self.files.values() if f.conversation_id == conversation_id]

    def create(self, conversation_id, name, path, parent_id=None, is_directory=False,
               file_type=None, mime_type=None, size=0, source='USER'):
        file = File(id=max(self.files, default=0) + 1, conversation_id=conversation_id, parent_id=parent_id,
                    name=name, path=path, is_directory=is_directory, file_type=file_type,
                    mime_type=mime_type, size=size, source=source, created_at=None, updated_at=None)
        self.files[file.id] = file
        self.calls.append(('create', path))
        return file

    def update(self, file_id, name, path, parent_id, is_directory, file_type, mime_type, size):
        self.files[file_id] = replace(self.files[file_id], name=name, path=path, parent_id=parent_id,
                                      is_directory=is_directory, file_type=file_type,
                                      mime_type=mime_type, size=size)
        self.calls.append(('update', path))
        return self.files[file_id]

    def delete(self, file_id):
        self.calls.append(('delete', self.files.pop(file_id).path))
        return True


def sync(repo, entries):
    WorkspaceSyncService(files_repository=repo, scanner=FakeScanner(entries)).sync(
        conversation_id=1, workspace_dir=Path('ws'))


class WorkspaceSyncServiceTest(unittest.TestCase):
    def test_new_items_are_created_with_parent_ids(self):
        repo = FakeFilesRepository()
        sync(repo, [
            entry('reports', is_directory=True),
            entry('reports/data', is_directory=True),
            entry('reports/data/result.json', size=10, file_type='json', mime_type='application/json'),
        ])

        by_path = {f.path: f for f in repo.files.values()}
        self.assertIsNone(by_path['reports'].parent_id)
        self.assertEqual(by_path['reports/data'].parent_id, by_path['reports'].id)
        self.assertEqual(by_path['reports/data/result.json'].parent_id, by_path['reports/data'].id)
        self.assertEqual(by_path['reports/data/result.json'].source, 'AGENT')

    def test_changed_file_is_updated_and_unchanged_is_untouched(self):
        repo = FakeFilesRepository()
        sync(repo, [entry('a.md', size=1, file_type='md'), entry('b.md', size=1, file_type='md')])
        repo.calls.clear()

        sync(repo, [entry('a.md', size=5, file_type='md'), entry('b.md', size=1, file_type='md')])
        self.assertEqual(repo.calls, [('update', 'a.md')])

    def test_missing_items_are_deleted_children_first(self):
        repo = FakeFilesRepository()
        sync(repo, [entry('reports', is_directory=True), entry('reports/data', is_directory=True),
                    entry('reports/data/x.md', file_type='md'), entry('keep.md', file_type='md')])
        repo.calls.clear()

        sync(repo, [entry('keep.md', file_type='md')])
        self.assertEqual(repo.calls, [('delete', 'reports/data/x.md'), ('delete', 'reports/data'),
                                      ('delete', 'reports')])

    def test_no_change_writes_nothing(self):
        repo = FakeFilesRepository()
        entries = [entry('a.md', size=3, file_type='md')]
        sync(repo, entries)
        repo.calls.clear()

        sync(repo, entries)
        self.assertEqual(repo.calls, [])


class LocalWorkspaceScannerTest(unittest.TestCase):
    def test_scan_returns_parents_first_with_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'reports' / 'data').mkdir(parents=True)
            (root / 'reports' / 'data' / 'Result.JSON').write_text('{"a": 1}', encoding='utf-8')
            (root / 'note.md').write_text('# hi', encoding='utf-8')

            entries = LocalWorkspaceScanner().scan(root)

        by_path = {e.path: e for e in entries}
        self.assertEqual(set(by_path), {'reports', 'reports/data', 'reports/data/Result.JSON', 'note.md'})

        depths = [e.path.count('/') for e in entries]
        self.assertEqual(depths, sorted(depths))  # Cha luôn đứng trước con

        self.assertEqual(by_path['reports'], WorkspaceEntry('reports', 'reports', None, True, None, None, 0))
        result = by_path['reports/data/Result.JSON']
        self.assertEqual((result.parent_path, result.file_type, result.size), ('reports/data', 'json', 8))
        self.assertEqual(by_path['note.md'].parent_path, None)

    def test_missing_workspace_raises(self):
        with self.assertRaises(FileNotFoundError):
            LocalWorkspaceScanner().scan(Path(tempfile.gettempdir()) / 'khong_ton_tai_zz')


if __name__ == '__main__':
    unittest.main()
