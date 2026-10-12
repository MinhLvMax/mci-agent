from dataclasses import dataclass

from src.app.ports.repositories import FilesRepository
from src.app.ports.storage import FileStorage
from src.dom.entities.file import File


@dataclass
class GetFileContentCommand:
    file_id: int


@dataclass
class GetFileContentResult:
    file: File
    content: str


class GetFileContentUseCase:

    def __init__(
            self,
            files_repository: FilesRepository,
            file_storage: FileStorage,
    ):
        self.files_repository = files_repository
        self.file_storage = file_storage

    def execute(
            self,
            command: GetFileContentCommand
    ) -> GetFileContentResult:
        file = self.files_repository.get_by_id(
            file_id=command.file_id
        )

        if file is None:
            raise ValueError("File not found")

        content = self.file_storage.read(
            path=file.path
        )

        return GetFileContentResult(
            file=file,
            content=content,
        )
