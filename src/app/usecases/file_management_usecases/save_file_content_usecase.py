from dataclasses import dataclass

from src.app.ports.repositories import FilesRepository
from src.app.ports.storage import FileStorage
from src.dom.entities.file import File


@dataclass
class SaveFileContentCommand:
    file_id: int
    content: str


@dataclass
class SaveFileContentResult:
    file: File


class SaveFileContentUseCase:
    '''User sửa file trên giao diện: ghi nguyên văn nội dung rồi cập nhật size trong DB'''

    def __init__(
            self,
            files_repository: FilesRepository,
            file_storage: FileStorage,
    ):
        self.files_repository = files_repository
        self.file_storage = file_storage

    def execute(
            self,
            command: SaveFileContentCommand
    ) -> SaveFileContentResult:
        file = self.files_repository.get_by_id(
            file_id=command.file_id
        )

        if file is None:
            raise ValueError("File not found")

        if file.is_directory:
            raise ValueError("Cannot edit a directory")

        if not self.file_storage.is_supported(file.path):  # pdf, ảnh... không sửa dạng text được
            raise ValueError("Unsupported file type")

        self.file_storage.write_text(
            path=file.path,
            content=command.content,
        )

        updated = self.files_repository.update_size(
            file_id=file.id,
            size=self.file_storage.get_size(file.path),
        )

        return SaveFileContentResult(
            file=updated or file,
        )
