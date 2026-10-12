from pathlib import Path

from src.app.ports.repositories import FilesRepository
from src.app.ports.storage import WorkspaceScanner


class WorkspaceSyncService:
    """
    Đồng bộ trạng thái filesystem của một conversation
    với metadata trong bảng `files`.

    Nguyên tắc:

    - Filesystem là nguồn sự thật về việc file/thư mục
      hiện có tồn tại vật lý hay không.

    - CSDL chỉ lưu metadata của file/thư mục.

    - path lưu trong CSDL luôn là relative path
      tính từ conversation workspace.

    Ví dụ:

        workspace:
            D:/agent_workspace/user_1/conversation_10/

        file vật lý:
            D:/agent_workspace/user_1/conversation_10/reports/result.md

        path lưu DB:
            reports/result.md

    Service này không tự đọc ổ đĩa: việc quét workspace do port WorkspaceScanner đảm nhận,
    ở đây chỉ còn logic đối chiếu với CSDL.
    """

    def __init__(
            self,
            files_repository: FilesRepository,
            scanner: WorkspaceScanner,
    ):
        self.files_repository = files_repository
        self.scanner = scanner

    def sync(
            self,
            conversation_id: int,
            workspace_dir: str | Path,
    ) -> None:
        """
        Đồng bộ toàn bộ workspace của một conversation với database.

        Bao gồm:

        1. Phát hiện file/thư mục mới -> tạo metadata.
        2. File đã tồn tại -> cập nhật metadata nếu thay đổi.
        3. File/thư mục đã bị xóa vật lý -> xóa metadata DB.
        """

        # ============================================================
        # 1. Lấy toàn bộ metadata hiện có trong DB
        # ============================================================

        db_files = self.files_repository.get_by_conversation_id(
            conversation_id=conversation_id
        )

        # Tạo map:
        #
        # {
        #     "report.md": File(...),
        #     "reports": File(...),
        #     "reports/result.md": File(...)
        # }
        #
        # Giúp lookup nhanh theo path.
        db_files_by_path = {
            file.path: file
            for file in db_files
        }

        # ============================================================
        # 2. Quét workspace (thư mục cha đứng trước con)
        # ============================================================

        entries = self.scanner.scan(workspace_dir)

        # Lưu tất cả relative path thực sự tồn tại.
        physical_paths: set[str] = set()

        # Map path -> File entity trong DB.
        #
        # Map này bao gồm cả:
        # - record cũ
        # - record vừa được tạo trong lần sync hiện tại
        #
        # Nhờ vậy child có thể lấy ID của parent vừa được INSERT.
        synced_files_by_path = dict(db_files_by_path)

        # ============================================================
        # 3. Đồng bộ từng file/thư mục vật lý
        # ============================================================

        for entry in entries:

            physical_paths.add(entry.path)

            # --------------------------------------------------------
            # Xác định parent_id
            # --------------------------------------------------------

            # Item nằm trực tiếp trong workspace thì parent_id = NULL
            if entry.parent_path is None:
                parent_id = None

            else:
                parent_file = synced_files_by_path.get(
                    entry.parent_path
                )

                if parent_file is None:
                    raise RuntimeError(
                        "Parent directory metadata was not "
                        f"created: {entry.parent_path}"
                    )

                parent_id = parent_file.id

            # --------------------------------------------------------
            # Kiểm tra metadata đã tồn tại chưa
            # --------------------------------------------------------

            existing_file = db_files_by_path.get(
                entry.path
            )

            # ========================================================
            # 3A. Chưa có trong DB -> CREATE
            # ========================================================

            if existing_file is None:
                created_file = self.files_repository.create(
                    conversation_id=conversation_id,
                    name=entry.name,
                    path=entry.path,
                    parent_id=parent_id,
                    is_directory=entry.is_directory,
                    file_type=entry.file_type,
                    mime_type=entry.mime_type,
                    size=entry.size,

                    # File xuất hiện trên filesystem nhưng chưa có
                    # metadata DB.
                    #
                    # Trong luồng hiện tại trường hợp phổ biến nhất
                    # là Agent vừa tạo nó.
                    source="AGENT",
                )

                synced_files_by_path[
                    entry.path
                ] = created_file

                continue

            # ========================================================
            # 3B. Đã có trong DB -> kiểm tra UPDATE
            # ========================================================

            metadata_changed = (
                    existing_file.name != entry.name
                    or existing_file.parent_id != parent_id
                    or existing_file.is_directory != entry.is_directory
                    or existing_file.file_type != entry.file_type
                    or existing_file.mime_type != entry.mime_type
                    or existing_file.size != entry.size
            )

            if metadata_changed:

                updated_file = self.files_repository.update(
                    file_id=existing_file.id,
                    name=entry.name,
                    path=entry.path,
                    parent_id=parent_id,
                    is_directory=entry.is_directory,
                    file_type=entry.file_type,
                    mime_type=entry.mime_type,
                    size=entry.size,
                )

                if updated_file is not None:
                    synced_files_by_path[
                        entry.path
                    ] = updated_file

            else:
                synced_files_by_path[
                    entry.path
                ] = existing_file

        # ============================================================
        # 4. Xóa metadata không còn tồn tại trên filesystem
        # ============================================================

        stale_files = [
            file
            for file in db_files
            if file.path not in physical_paths
        ]

        # Child phải được xóa trước parent.
        #
        # Ví dụ:
        #
        # reports/
        # reports/data/
        # reports/data/result.json
        #
        # Mặc dù DB có ON DELETE CASCADE,
        # xử lý deepest-first giúp hành vi rõ ràng hơn.
        # path trong DB luôn dùng "/" nên đếm "/" là ra độ sâu.
        stale_files.sort(
            key=lambda file: file.path.count("/"),
            reverse=True,
        )

        for stale_file in stale_files:
            self.files_repository.delete(
                file_id=stale_file.id
            )
