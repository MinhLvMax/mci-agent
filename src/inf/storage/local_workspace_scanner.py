import mimetypes
from pathlib import Path

from src.app.ports.storage import WorkspaceEntry


class LocalWorkspaceScanner:
    '''
    Triển khai port WorkspaceScanner (src/app/ports/storage.py) bằng filesystem cục bộ:
    đọc toàn bộ file/thư mục trong workspace kèm metadata để WorkspaceSyncService đối chiếu với CSDL.
    '''

    def scan(self, workspace_dir: Path) -> list[WorkspaceEntry]:
        workspace_dir = Path(workspace_dir).resolve()

        if not workspace_dir.exists():
            raise FileNotFoundError(
                f"Workspace does not exist: {workspace_dir}"
            )

        if not workspace_dir.is_dir():
            raise NotADirectoryError(
                f"Workspace is not a directory: {workspace_dir}"
            )

        physical_items = list(workspace_dir.rglob("*"))

        # Quan trọng: parent directory phải đứng trước child.
        #
        # reports/
        # reports/data/
        # reports/data/result.json
        #
        # Bên đồng bộ cần tạo reports trước để lấy được ID làm parent_id cho data.
        physical_items.sort(
            key=lambda path: len(path.relative_to(workspace_dir).parts)
        )

        return [self._to_entry(workspace_dir, path) for path in physical_items]

    @staticmethod
    def _to_entry(workspace_dir: Path, physical_path: Path) -> WorkspaceEntry:
        parent_relative_path = physical_path.parent.relative_to(workspace_dir).as_posix()
        is_directory = physical_path.is_dir()

        if is_directory:
            file_type = None
            mime_type = None
            size = 0
        else:
            # report.md -> md, data.json -> json (suffix trả ".md" nên bỏ dấu ".")
            suffix = physical_path.suffix
            file_type = suffix[1:].lower() if suffix else None

            # Đoán MIME theo đuôi file: report.md -> text/markdown, image.png -> image/png
            mime_type, _ = mimetypes.guess_type(physical_path.name)

            size = physical_path.stat().st_size

        return WorkspaceEntry(
            path=physical_path.relative_to(workspace_dir).as_posix(),
            name=physical_path.name,
            # Item nằm ngay trong workspace thì parent là "." -> parent_id = NULL trong DB
            parent_path=None if parent_relative_path == "." else parent_relative_path,
            is_directory=is_directory,
            file_type=file_type,
            mime_type=mime_type,
            size=size,
        )
