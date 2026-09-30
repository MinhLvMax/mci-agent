from pathlib import Path
import mimetypes

from src.app.services.postgre_db.postgre_files_repository import (
    PostgreFilesRepository
)


class WorkspaceSyncService:
    """
    Đồng bộ trạng thái filesystem của một conversation
    với metadata trong bảng `files`.

    Nguyên tắc:

    - Filesystem là nguồn sự thật về việc file/thư mục
      hiện có tồn tại vật lý hay không.

    - PostgreSQL chỉ lưu metadata của file/thư mục.

    - path lưu trong PostgreSQL luôn là relative path
      tính từ conversation workspace.

    Ví dụ:

        workspace:
            D:/agent_workspace/user_1/conversation_10/

        file vật lý:
            D:/agent_workspace/user_1/conversation_10/reports/result.md

        path lưu DB:
            reports/result.md
    """

    def __init__(
            self,
            files_repository: PostgreFilesRepository,
    ):
        self.files_repository = files_repository

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

        workspace_dir = Path(workspace_dir).resolve()

        if not workspace_dir.exists():
            raise FileNotFoundError(
                f"Workspace does not exist: {workspace_dir}"
            )

        if not workspace_dir.is_dir():
            raise NotADirectoryError(
                f"Workspace is not a directory: {workspace_dir}"
            )

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
        # 2. Scan filesystem
        # ============================================================

        physical_items = [
            path
            for path in workspace_dir.rglob("*")
        ]

        # Quan trọng:
        #
        # parent directory phải được xử lý trước child.
        #
        # Ví dụ:
        #
        # reports/
        # reports/data/
        # reports/data/result.json
        #
        # Ta cần tạo reports trước để lấy được ID,
        # rồi mới có parent_id cho data.
        physical_items.sort(
            key=lambda path: len(
                path.relative_to(workspace_dir).parts
            )
        )

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

        for physical_path in physical_items:

            relative_path = (
                physical_path
                .relative_to(workspace_dir)
                .as_posix()
            )

            physical_paths.add(relative_path)

            # --------------------------------------------------------
            # Xác định parent_id
            # --------------------------------------------------------

            parent_relative_path = (
                physical_path.parent
                .relative_to(workspace_dir)
                .as_posix()
            )

            # Nếu item nằm trực tiếp trong workspace:
            #
            # workspace/report.md
            #
            # parent_relative_path sẽ là "."
            #
            # Trong DB:
            #
            # parent_id = NULL
            if parent_relative_path == ".":
                parent_id = None

            else:
                parent_file = synced_files_by_path.get(
                    parent_relative_path
                )

                if parent_file is None:
                    raise RuntimeError(
                        "Parent directory metadata was not "
                        f"created: {parent_relative_path}"
                    )

                parent_id = parent_file.id

            # --------------------------------------------------------
            # Xác định metadata filesystem
            # --------------------------------------------------------

            is_directory = physical_path.is_dir()

            name = physical_path.name

            if is_directory:
                file_type = None
                mime_type = None
                size = 0

            else:
                # Ví dụ:
                #
                # report.md -> md
                # data.json -> json
                #
                # suffix trả ".md" nên bỏ dấu ".".
                suffix = physical_path.suffix

                file_type = (
                    suffix[1:].lower()
                    if suffix
                    else None
                )

                # Python sẽ đoán MIME dựa vào extension.
                #
                # report.md:
                #     text/markdown
                #
                # image.png:
                #     image/png
                mime_type, _ = mimetypes.guess_type(
                    physical_path.name
                )

                size = physical_path.stat().st_size

            # --------------------------------------------------------
            # Kiểm tra metadata đã tồn tại chưa
            # --------------------------------------------------------

            existing_file = db_files_by_path.get(
                relative_path
            )

            # ========================================================
            # 3A. Chưa có trong DB -> CREATE
            # ========================================================

            if existing_file is None:
                created_file = self.files_repository.create(
                    conversation_id=conversation_id,
                    name=name,
                    path=relative_path,
                    parent_id=parent_id,
                    is_directory=is_directory,
                    file_type=file_type,
                    mime_type=mime_type,
                    size=size,

                    # File xuất hiện trên filesystem nhưng chưa có
                    # metadata DB.
                    #
                    # Trong luồng hiện tại trường hợp phổ biến nhất
                    # là Agent vừa tạo nó.
                    source="AGENT",
                )

                synced_files_by_path[
                    relative_path
                ] = created_file

                continue

            # ========================================================
            # 3B. Đã có trong DB -> kiểm tra UPDATE
            # ========================================================

            metadata_changed = (
                    existing_file.name != name
                    or existing_file.parent_id != parent_id
                    or existing_file.is_directory != is_directory
                    or existing_file.file_type != file_type
                    or existing_file.mime_type != mime_type
                    or existing_file.size != size
            )

            if metadata_changed:

                updated_file = self.files_repository.update(
                    file_id=existing_file.id,
                    name=name,
                    path=relative_path,
                    parent_id=parent_id,
                    is_directory=is_directory,
                    file_type=file_type,
                    mime_type=mime_type,
                    size=size,
                )

                if updated_file is not None:
                    synced_files_by_path[
                        relative_path
                    ] = updated_file

            else:
                synced_files_by_path[
                    relative_path
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
        stale_files.sort(
            key=lambda file: len(
                Path(file.path).parts
            ),
            reverse=True,
        )

        for stale_file in stale_files:
            self.files_repository.delete(
                file_id=stale_file.id
            )
