from dataclasses import dataclass
from pathlib import Path

from src.dom.entities.file import File


@dataclass
class DownloadFileCommand:
    file_id: int


@dataclass
class DownloadFileResult:
    file: File

    # Absolute path của file vật lý trên server.
    # Router dùng path này để stream nguyên bytes của file về client.
    physical_path: Path

    # Tên file client nhận được, thư mục thì là <tên>.zip
    download_name: str

    media_type: str

    # True khi physical_path là file zip tạm, router phải xóa sau khi gửi xong
    is_temporary: bool = False


class DownloadFileUseCase:

    def __init__(
            self,
            files_repository,
            file_storage,
    ):
        self.files_repository = files_repository
        self.file_storage = file_storage

    def execute(
            self,
            command: DownloadFileCommand
    ) -> DownloadFileResult:
        file = self.files_repository.get_by_id(
            file_id=command.file_id
        )

        if file is None:
            raise FileNotFoundError("File not found")

        if file.is_directory:
            # Thư mục thì nén thành zip tạm để tải về một lần
            return DownloadFileResult(
                file=file,
                physical_path=self.file_storage.zip_directory(
                    path=file.path
                ),
                download_name=f"{file.name}.zip",
                media_type="application/zip",
                is_temporary=True,
            )

        # Không đọc nội dung ở đây, chỉ lấy path đã được
        # kiểm tra nằm trong workspace.
        physical_path = self.file_storage.get_path(
            path=file.path
        )

        return DownloadFileResult(
            file=file,
            physical_path=physical_path,
            download_name=file.name,
            media_type=file.mime_type or "application/octet-stream",
        )
