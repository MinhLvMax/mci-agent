"""
User sửa file trên giao diện Workspace: ghi nguyên văn text và cập nhật size trong DB.
"""

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from src.app.usecases.file_management_usecases.save_file_content_usecase import (
    SaveFileContentCommand,
    SaveFileContentUseCase,
)
from src.dom.entities.file import File
from src.inf.storage.local_file_storage import LocalFileStorage


def make_file(file_id, path, is_directory=False):
    return File(
        id=file_id,
        conversation_id=1,
        parent_id=None,
        name=Path(path).name,
        path=path,
        is_directory=is_directory,
        file_type=Path(path).suffix.removeprefix(".") or None,
        mime_type=None,
        size=0,
        source="agent",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


class FakeFilesRepository:
    def __init__(self, files):
        self.files = {file.id: file for file in files}

    def get_by_id(self, file_id):
        return self.files.get(file_id)

    def update_size(self, file_id, size):
        self.files[file_id] = replace(self.files[file_id], size=size)
        return self.files[file_id]


class SaveFileContentUseCaseTest(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.storage = LocalFileStorage(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def save(self, files, file_id, content):
        repo = FakeFilesRepository(files)
        usecase = SaveFileContentUseCase(files_repository=repo, file_storage=self.storage)
        return usecase.execute(SaveFileContentCommand(file_id=file_id, content=content)), repo

    def test_saves_text_verbatim_and_updates_size(self):
        (self.root / "note.md").write_text("cũ", encoding="utf-8")
        content = "# Tiêu đề\nnội dung mới\n"

        result, repo = self.save([make_file(1, "note.md")], 1, content)

        self.assertEqual((self.root / "note.md").read_bytes(), content.encode("utf-8"))  # Không đổi \n thành \r\n
        self.assertEqual(result.file.size, len(content.encode("utf-8")))
        self.assertEqual(repo.files[1].size, result.file.size)

    def test_json_and_csv_saved_as_raw_text(self):
        (self.root / "data.json").write_text("{}", encoding="utf-8")
        (self.root / "data.csv").write_text("a\n", encoding="utf-8")
        files = [make_file(1, "data.json"), make_file(2, "data.csv")]

        self.save(files, 1, '{"a": 1,\n  "b": [1, 2]}')
        self.save(files, 2, "name,age\nMinh,25\n")

        self.assertEqual((self.root / "data.json").read_text(encoding="utf-8"), '{"a": 1,\n  "b": [1, 2]}')
        self.assertEqual(self.storage.read("data.csv"), [{"name": "Minh", "age": "25"}])

    def test_rejects_directory_binary_and_missing(self):
        (self.root / "folder").mkdir()
        (self.root / "image.png").write_bytes(b"\x89PNG")
        files = [make_file(1, "folder", is_directory=True), make_file(2, "image.png"), make_file(3, "gone.md")]

        with self.assertRaises(ValueError):
            self.save(files, 1, "x")
        with self.assertRaises(ValueError):
            self.save(files, 2, "x")
        with self.assertRaises(FileNotFoundError):
            self.save(files, 3, "x")
        with self.assertRaises(ValueError):
            self.save(files, 99, "x")

        self.assertEqual((self.root / "image.png").read_bytes(), b"\x89PNG")


if __name__ == "__main__":
    unittest.main()
