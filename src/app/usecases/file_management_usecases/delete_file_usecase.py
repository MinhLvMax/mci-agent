from dataclasses import dataclass

from src.app.ports.repositories import FilesRepository
from src.app.ports.storage import FileStorage


@dataclass
class DeleteFileCommand:
    """
    Command chứa dữ liệu đầu vào cần thiết
    để thực hiện thao tác xóa file.
    """

    file_id: int


@dataclass
class DeleteFileResult:
    """
    Kết quả trả về sau khi thực hiện xóa file.

    success = True:
        File đã được xóa thành công.

    success = False:
        Không tìm thấy file tương ứng trong database.
    """

    success: bool


class DeleteFileUseCase:

    def __init__(
            self,
            files_repository: FilesRepository,
            file_storage: FileStorage,
    ):
        # Repository chịu trách nhiệm thao tác metadata
        # của file trong PostgreSQL.
        self.files_repository = files_repository

        # FileStorage chịu trách nhiệm thao tác
        # với file vật lý trên ổ đĩa.
        self.file_storage = file_storage

    def execute(
            self,
            command: DeleteFileCommand
    ) -> DeleteFileResult:
        """
        Xóa một file gồm 2 phần:

        1. Xóa file vật lý khỏi storage.
        2. Xóa metadata của file khỏi PostgreSQL.
        """

        # Tìm metadata của file trong database.
        file = self.files_repository.get_by_id(
            file_id=command.file_id
        )

        # Không tồn tại record -> không có gì để xóa.
        if file is None:
            return DeleteFileResult(
                success=False
            )

        # Xóa file vật lý trước.
        #
        # file.path là đường dẫn tương đối đã được lưu
        # trong bảng files.
        self.file_storage.delete(
            path=file.path
        )

        # Sau khi file vật lý đã được xử lý,
        # xóa metadata khỏi PostgreSQL.
        deleted = self.files_repository.delete(
            file_id=command.file_id
        )

        return DeleteFileResult(
            success=deleted
        )
