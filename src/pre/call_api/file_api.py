from dataclasses import dataclass
from typing import Any

from src.pre.call_api.api_client import APIClient


# ============================================================
# FILE MODEL
# ============================================================

@dataclass
class File:
    """
    Đại diện metadata của một file được backend trả về.

    Class này thuộc presentation/call_api nên dùng để nhận
    dữ liệu JSON từ API.

    Không thao tác trực tiếp với database hoặc filesystem.
    """

    id: int
    conversation_id: int
    parent_id: int | None

    name: str
    path: str

    is_directory: bool

    file_type: str | None
    mime_type: str | None

    size: int
    source: str

    created_at: str
    updated_at: str


# ============================================================
# API RESPONSE
# ============================================================

@dataclass
class ListFilesAPIResponse:
    """
    Kết quả của API lấy danh sách file.
    """

    files: list[File]


@dataclass
class GetFileAPIResponse:
    """
    Kết quả của API đọc một file.

    content để Any vì tùy loại file:

        .md/.txt -> str
        .json    -> dict/list
        .csv     -> list[dict]
    """

    file: File
    content: Any


@dataclass
class DeleteFileAPIResponse:
    """
    Kết quả của API xóa file.
    """

    success: bool


# ============================================================
# FILE API
# ============================================================

class FileAPI:

    def __init__(
            self,
            client: APIClient
    ):
        self.client = client

    # ========================================================
    # LIST FILES
    # ========================================================

    def list(
            self,
            conversation_id: int | str
    ) -> ListFilesAPIResponse:
        """
        Lấy danh sách file thuộc một conversation.

        API:
            POST /list_files/

        Request:
            {
                "conversation_id": 10
            }
        """

        response = self.client.post(
            path="/list_files/",
            json={
                "conversation_id": conversation_id,
            },
        )

        # Nếu backend trả HTTP error thì requests
        # sẽ phát sinh exception tại đây.
        response.raise_for_status()

        data = response.json()

        # Chuyển từng dictionary backend trả về
        # thành File object.
        files = [
            self._parse_file(file_data)
            for file_data in data["files"]
        ]

        return ListFilesAPIResponse(
            files=files
        )

    # ========================================================
    # GET FILE
    # ========================================================

    def get(
            self,
            file_id: int | str
    ) -> GetFileAPIResponse:
        """
        Lấy metadata + nội dung của một file.

        API:
            POST /get_file/

        Request:
            {
                "file_id": 15
            }
        """

        response = self.client.post(
            path="/get_file/",
            json={
                "file_id": file_id,
            },
        )

        response.raise_for_status()

        data = response.json()

        return GetFileAPIResponse(
            file=self._parse_file(
                data["file"]
            ),
            content=data["content"],
        )

    # ========================================================
    # DELETE FILE
    # ========================================================

    def delete(
            self,
            file_id: int | str
    ) -> DeleteFileAPIResponse:
        """
        Xóa file vật lý + metadata của file.

        API:
            POST /delete_file/

        Request:
            {
                "file_id": 15
            }
        """

        response = self.client.post(
            path="/delete_file/",
            json={
                "file_id": file_id,
            },
        )

        response.raise_for_status()

        data = response.json()

        return DeleteFileAPIResponse(
            success=data["success"]
        )

    # ========================================================
    # HELPER
    # ========================================================

    @staticmethod
    def _parse_file(
            data: dict
    ) -> File:
        """
        Chuyển dictionary JSON backend trả về thành File.

        Việc map tập trung tại đây giúp tránh lặp lại code
        trong list() và get().
        """

        return File(
            id=data["id"],
            conversation_id=data["conversation_id"],
            parent_id=data["parent_id"],

            name=data["name"],
            path=data["path"],

            is_directory=data["is_directory"],

            file_type=data["file_type"],
            mime_type=data["mime_type"],

            size=data["size"],
            source=data["source"],

            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
