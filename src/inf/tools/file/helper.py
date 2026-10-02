import shutil  # Dùng để di chuyển file/thư mục
from pathlib import Path  # Import Path để xử lý đường dẫn file và thư mục


class WorkspacePathError(ValueError):  # Tạo exception riêng cho các lỗi liên quan đến đường dẫn workspace
    pass  # Không cần thêm logic, chỉ dùng để phân biệt loại lỗi


class WorkspacePathGuard:  # Class chịu trách nhiệm kiểm soát và giới hạn đường dẫn trong workspace
    """
    Resolve và kiểm tra đường dẫn để đảm bảo tool chỉ có thể
    thao tác bên trong workspace được cấp.
    """

    def __init__(self, workspace_dir: str | Path):  # Hàm khởi tạo, nhận vào đường dẫn workspace
        self.workspace_dir = Path(
            workspace_dir).expanduser().resolve()  # Chuyển workspace thành Path, xử lý ~ và chuẩn hóa thành absolute path

        if not self.workspace_dir.exists():  # Kiểm tra workspace có thực sự tồn tại trên hệ thống không
            raise ValueError(  # Nếu không tồn tại thì báo lỗi ngay khi khởi tạo class
                f"Workspace does not exist: {self.workspace_dir}"  # Hiển thị workspace không tồn tại
            )

        if not self.workspace_dir.is_dir():  # Kiểm tra workspace có phải là thư mục hay không
            raise ValueError(  # Nếu workspace là file hoặc loại khác thì báo lỗi
                f"Workspace is not a directory: {self.workspace_dir}"  # Hiển thị đường dẫn không phải thư mục
            )

    def resolve(self, relative_path: str) -> Path:  # Nhận relative path và trả về absolute path an toàn
        """
        Chuyển relative path thành absolute path an toàn.

        Ví dụ hợp lệ:
            characters/cave_lion.json
            shots/shot_001.json

        Ví dụ bị chặn:
            ../config.py
            ../../secret.txt
            C:/Users/...
            /etc/passwd
        """  # Docstring mô tả chức năng và ví dụ đường dẫn hợp lệ / không hợp lệ

        if not isinstance(relative_path, str):  # Kiểm tra xem có phải dạng chuỗi không, nếu không phải thì ném lỗi
            raise WorkspacePathError(
                "Path must be string"
            )

        path = Path(relative_path)  # Chuyển chuỗi relative_path thành đối tượng Path để dễ xử lý

        if path.is_absolute():  # Kiểm tra xem src có truyền vào absolute path hay không
            raise WorkspacePathError(  # Nếu là absolute path thì chặn ngay
                "Absolute paths are not allowed. "  # Thông báo không được sử dụng absolute path
                "Use a path relative to the workspace."  # Yêu cầu sử dụng relative path tính từ workspace
            )

        resolved_path = (  # Bắt đầu tạo đường dẫn tuyệt đối của file cần truy cập
                self.workspace_dir / path  # Ghép workspace với relative path mà src truyền vào
        ).resolve()  # Chuẩn hóa đường dẫn và xử lý các thành phần như . hoặc ..

        try:  # Thử kiểm tra xem resolved_path có thực sự nằm trong workspace hay không
            resolved_path.relative_to(  # Thử biểu diễn resolved_path dưới dạng đường dẫn tương đối so với workspace
                self.workspace_dir  # Workspace là thư mục gốc mà đường dẫn bắt buộc phải nằm bên trong
            )

        except ValueError:  # Nếu relative_to thất bại thì resolved_path không nằm trong workspace
            raise WorkspacePathError(  # Báo lỗi và chặn truy cập
                f"Path escapes workspace: {relative_path}"  # Hiển thị path đang cố thoát ra ngoài workspace
            )

        return resolved_path  # Nếu vượt qua mọi kiểm tra thì trả về absolute path an toàn

    def to_relative(self, path: Path) -> str:  # Chuyển một absolute path trong workspace về relative path
        try:
            return str(
                path.resolve().relative_to(
                    self.workspace_dir
                )
            )

        except ValueError:
            raise WorkspacePathError(
                "Path is outside workspace"
            )


def save_text(guard: WorkspacePathGuard, relative_path: str, content: str) -> str:
    """
    Ghi nội dung text UTF-8 vào file trong workspace, tự tạo thư mục cha.
    Dùng chung cho các tool có tham số save_to (open_url, youtube_transcript...).
    Trả về relative path dạng "a/b.md".
    """

    path = guard.resolve(relative_path)

    if path.exists() and path.is_dir():
        raise WorkspacePathError(f"Path is a directory: {relative_path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    return guard.to_relative(path).replace("\\", "/")


def safe_move(guard: WorkspacePathGuard, source: str, destination: str) -> tuple[str, str]:
    """
    Chuyển file hoặc thư mục trong workspace, dùng chung cho move_path và rename_path.

    Không bao giờ ghi đè hay xóa dữ liệu: đích đã tồn tại thì từ chối.
    Trả về (relative path nguồn, relative path đích).
    """

    source_path = guard.resolve(source)
    destination_path = guard.resolve(destination)

    if source_path == guard.workspace_dir:
        raise WorkspacePathError("Cannot move the workspace root.")

    if not source_path.exists():
        raise WorkspacePathError(f"Source does not exist: {source}")

    if destination_path.exists():
        raise WorkspacePathError(
            f"Destination already exists: {destination}. Choose another path (existing files are never overwritten)."
        )

    if source_path.is_dir() and destination_path.is_relative_to(source_path):
        raise WorkspacePathError("Cannot move a directory into itself.")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(destination_path))

    return (
        guard.to_relative(source_path).replace("\\", "/"),
        guard.to_relative(destination_path).replace("\\", "/"),
    )
