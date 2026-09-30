from dataclasses import dataclass
from src.dom.entities.file import File

@dataclass
class ListFilesCommand:
    conversation_id: int


@dataclass
class ListFilesResult:
    files: list[File]


class ListFilesUseCase:

    def __init__(self, files_repository):
        self.files_repository = files_repository

    def execute(
            self,
            command: ListFilesCommand
    ) -> ListFilesResult:

        files = self.files_repository.get_by_conversation_id(
            conversation_id=command.conversation_id
        )

        return ListFilesResult(
            files=files
        )