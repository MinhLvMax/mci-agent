from pathlib import Path
import csv
import json
import mimetypes
import re
import shutil
import tempfile
import zipfile
from typing import Any


class FileStorage:
    """
    Service chịu trách nhiệm thao tác với file vật lý trong workspace.

    Nhiệm vụ chính:
    - Đọc file.
    - Ghi file.
    - Xóa file/thư mục.
    - Kiểm tra file tồn tại.
    - Tự nhận diện loại file dựa trên extension.
    - Không cho phép truy cập ra ngoài workspace_root.

    Lưu ý:
    Service này thao tác với FILE VẬT LÝ.
    Nó không thao tác với metadata trong PostgreSQL.
    """

    # Các extension được coi là file text thông thường.
    TEXT_EXTENSIONS = {
        ".txt",
        ".md",
        ".markdown",
        ".py",
        ".js",
        ".ts",
        ".html",
        ".css",
        ".xml",
        ".yaml",
        ".yml",
        ".sql",
        ".log",
        ".ini",
        ".cfg",
    }

    # Các loại file hiện tại service biết cách đọc/ghi trực tiếp.
    SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {
        ".json",
        ".csv",
    }

    def __init__(
            self,
            workspace_root: str | Path
    ):
        """
        workspace_root:
            Thư mục gốc mà FileStorage được phép thao tác.

        Ví dụ:
            data/agent_workspace

        Mọi path truyền vào read/write/delete đều phải nằm
        bên trong workspace_root này.
        """

        self.workspace_root = Path(
            workspace_root
        ).resolve()

        # Đảm bảo workspace tồn tại.
        self.workspace_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    # =========================================================
    # PUBLIC METHODS
    # =========================================================

    def read(
            self,
            path: str
    ) -> Any:
        """
        Đọc file và tự lựa chọn cách đọc dựa trên extension.

        Ví dụ:

            storage.read("report.md")
                -> str

            storage.read("data.json")
                -> dict | list

            storage.read("data.csv")
                -> list[dict]

        Nếu loại file chưa được hỗ trợ thì báo lỗi rõ ràng.
        """

        file_path = self._resolve_path(path)

        # File phải tồn tại trước khi đọc.
        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {path}"
            )

        # Không cho đọc directory bằng read().
        if not file_path.is_file():
            raise ValueError(
                f"Path is not a file: {path}"
            )

        extension = self._get_extension(file_path)

        # -------------------------
        # JSON
        # -------------------------

        if extension == ".json":
            return self._read_json(file_path)

        # -------------------------
        # CSV
        # -------------------------

        if extension == ".csv":
            return self._read_csv(file_path)

        # -------------------------
        # TEXT
        # -------------------------

        if extension in self.TEXT_EXTENSIONS:
            return self._read_text(file_path)

        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    def write(
            self,
            path: str,
            content: Any,
            overwrite: bool = True,
    ) -> Path:
        """
        Ghi file và tự lựa chọn cách ghi dựa trên extension.

        Ví dụ:

            storage.write(
                "report.md",
                "# Báo cáo"
            )

            storage.write(
                "data.json",
                {"name": "Phong Nha"}
            )

            storage.write(
                "data.csv",
                [
                    {"name": "A", "age": 20},
                    {"name": "B", "age": 30},
                ]
            )

        overwrite=False:
            Nếu file đã tồn tại thì báo FileExistsError.
        """

        file_path = self._resolve_path(path)

        if file_path.exists() and not overwrite:
            raise FileExistsError(
                f"File already exists: {path}"
            )

        # Nếu user ghi:
        #
        # reports/2026/report.md
        #
        # mà reports/2026 chưa tồn tại thì tự tạo.
        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        extension = self._get_extension(file_path)

        # -------------------------
        # JSON
        # -------------------------

        if extension == ".json":
            self._write_json(
                file_path=file_path,
                content=content,
            )

        # -------------------------
        # CSV
        # -------------------------

        elif extension == ".csv":
            self._write_csv(
                file_path=file_path,
                content=content,
            )

        # -------------------------
        # TEXT
        # -------------------------

        elif extension in self.TEXT_EXTENSIONS:
            self._write_text(
                file_path=file_path,
                content=content,
            )

        else:
            raise ValueError(
                f"Unsupported file type: {extension}"
            )

        return file_path

    def write_bytes_unique(
            self,
            filename: str,
            data: bytes,
    ) -> str:
        """
        Ghi nguyên bytes vào thư mục gốc workspace, không bao giờ ghi đè.

        Dùng cho file người dùng upload, hỗ trợ mọi loại file.
        Nếu tên đã tồn tại thì tự đổi thành "ten (1).ext", "ten (2).ext"...

        Trả về relative path của file đã lưu.
        """

        safe_name = self._sanitize_filename(filename)  # Làm sạch tên trước khi dùng làm đường dẫn

        stem = Path(safe_name).stem  # Phần tên không gồm đuôi, ví dụ "bao_cao"
        suffix = Path(safe_name).suffix  # Phần đuôi, ví dụ ".md", có thể rỗng

        candidate = safe_name  # Lần đầu thử đúng tên gốc
        counter = 0  # Số thứ tự thêm vào tên khi bị trùng

        while True:
            file_path = self._resolve_path(candidate)  # Vẫn đi qua kiểm tra không thoát khỏi workspace

            try:
                with file_path.open("xb") as file:  # "x" = chỉ tạo mới, báo lỗi nếu file đã tồn tại
                    file.write(data)  # Ghi nguyên bytes, không chuyển đổi nội dung
                return candidate  # Ghi thành công thì trả tên đã dùng

            except FileExistsError:  # Tên này đã có file, kể cả do request khác vừa tạo
                counter += 1  # Tăng số thứ tự
                candidate = f"{stem} ({counter}){suffix}"  # Thử tên mới, ví dụ "bao_cao (1).md"

    @staticmethod
    def _sanitize_filename(
            filename: str
    ) -> str:
        """
        Biến tên file client gửi lên thành tên an toàn trên Windows.

        "../../evil.txt"  -> "evil.txt"
        "a:b?.txt"        -> "a_b_.txt"
        """

        name = Path(filename.replace("\\", "/")).name  # Bỏ mọi phần thư mục, chặn "../" và "C:\..."
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)  # Thay ký tự Windows không cho phép bằng "_"
        name = name.strip().rstrip(".")  # Windows không cho tên kết thúc bằng dấu chấm hoặc khoảng trắng

        if name in {"", ".", ".."}:  # Không còn gì hợp lệ sau khi làm sạch
            raise ValueError(
                f"Invalid file name: {filename}"
            )

        return name[:200]  # Cắt bớt để còn chỗ cho hậu tố " (n)" và giới hạn đường dẫn Windows

    def delete(
            self,
            path: str
    ) -> bool:
        """
        Xóa file hoặc directory.

        Trả về:
            True  -> đã xóa thành công.
            False -> path không tồn tại.

        Nếu là directory:
            xóa toàn bộ directory và nội dung bên trong.
        """

        target_path = self._resolve_path(path)

        if not target_path.exists():
            return False

        # Nếu là directory thì xóa toàn bộ cây directory.
        if target_path.is_dir():
            shutil.rmtree(target_path)

        else:
            target_path.unlink()

        return True

    def exists(
            self,
            path: str
    ) -> bool:
        """
        Kiểm tra file hoặc directory có tồn tại hay không.
        """

        return self._resolve_path(path).exists()

    def get_path(
            self,
            path: str
    ) -> Path:
        """
        Trả về absolute path an toàn của một file trong workspace.

        Khác với read():
        - không parse nội dung theo extension;
        - dùng được cho mọi loại file (pdf, png, xlsx...).

        Dùng khi cần trả nguyên file gốc, ví dụ API tải file.
        """

        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {path}"
            )

        if not file_path.is_file():
            raise ValueError(
                f"Path is not a file: {path}"
            )

        return file_path

    def zip_directory(
            self,
            path: str
    ) -> Path:
        """
        Nén một thư mục trong workspace thành file zip tạm.

        Giải nén ra được thư mục <tên thư mục>/... giữ nguyên cấu trúc bên trong.
        File zip nằm ngoài workspace (thư mục tạm của hệ thống),
        bên gọi chịu trách nhiệm xóa sau khi dùng xong.
        """

        dir_path = self._resolve_path(path)

        if not dir_path.exists():
            raise FileNotFoundError(
                f"Directory not found: {path}"
            )

        if not dir_path.is_dir():
            raise ValueError(
                f"Path is not a directory: {path}"
            )

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp:
            zip_path = Path(temp.name)

        try:
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for item in sorted(dir_path.rglob("*")):
                    # Tên trong zip tính từ thư mục cha để giải nén ra đúng <tên thư mục>/...
                    archive.write(item, arcname=item.relative_to(dir_path.parent))

        except Exception:
            zip_path.unlink(missing_ok=True)  # Nén lỗi thì không để lại file tạm
            raise

        return zip_path

    def get_size(
            self,
            path: str
    ) -> int:
        """
        Lấy kích thước file theo byte.

        Giá trị này có thể dùng để cập nhật:
            files.size
        trong PostgreSQL.
        """

        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {path}"
            )

        if not file_path.is_file():
            raise ValueError(
                f"Path is not a file: {path}"
            )

        return file_path.stat().st_size

    def get_mime_type(
            self,
            path: str
    ) -> str | None:
        """
        Tự nhận diện MIME type dựa trên tên/extension.

        Ví dụ:

            report.md
                -> text/markdown

            data.json
                -> application/json

            image.png
                -> image/png
        """

        mime_type, _ = mimetypes.guess_type(path)

        return mime_type

    def get_file_type(
            self,
            path: str
    ) -> str:
        """
        Trả về extension không có dấu chấm.

        Ví dụ:

            report.md -> md
            data.json -> json
            image.png -> png
        """

        extension = Path(path).suffix.lower()

        if not extension:
            return ""

        return extension.removeprefix(".")

    # =========================================================
    # TEXT
    # =========================================================

    @staticmethod
    def _read_text(
            file_path: Path
    ) -> str:
        """
        Đọc các file text UTF-8.
        """

        return file_path.read_text(
            encoding="utf-8"
        )

    @staticmethod
    def _write_text(
            file_path: Path,
            content: Any,
    ) -> None:
        """
        Ghi file text.

        Ép content thành str để caller có thể truyền
        các kiểu dữ liệu đơn giản.
        """

        file_path.write_text(
            str(content),
            encoding="utf-8",
        )

    # =========================================================
    # JSON
    # =========================================================

    @staticmethod
    def _read_json(
            file_path: Path
    ) -> Any:
        """
        Đọc JSON và deserialize thành Python object.

        JSON object -> dict
        JSON array  -> list
        """

        with file_path.open(
                "r",
                encoding="utf-8",
        ) as file:
            return json.load(file)

    @staticmethod
    def _write_json(
            file_path: Path,
            content: Any,
    ) -> None:
        """
        Serialize Python object thành JSON.

        ensure_ascii=False:
            giữ nguyên tiếng Việt.

        indent=4:
            giúp file JSON dễ đọc khi mở trực tiếp.
        """

        with file_path.open(
                "w",
                encoding="utf-8",
        ) as file:
            json.dump(
                content,
                file,
                ensure_ascii=False,
                indent=4,
            )

    # =========================================================
    # CSV
    # =========================================================

    @staticmethod
    def _read_csv(
            file_path: Path
    ) -> list[dict]:
        """
        Đọc CSV thành list[dict].

        Ví dụ file:

            name,age
            Minh,25
            An,30

        sẽ thành:

            [
                {"name": "Minh", "age": "25"},
                {"name": "An", "age": "30"}
            ]

        CSV mặc định trả các giá trị về dạng string.
        """

        with file_path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
        ) as file:
            reader = csv.DictReader(file)

            return list(reader)

    @staticmethod
    def _write_csv(
            file_path: Path,
            content: Any,
    ) -> None:
        """
        Ghi CSV từ list[dict].

        Ví dụ:

            [
                {
                    "name": "Minh",
                    "age": 25
                },
                {
                    "name": "An",
                    "age": 30
                }
            ]

        Nếu muốn hỗ trợ DataFrame sau này,
        có thể mở rộng method này.
        """

        if not isinstance(content, list):
            raise TypeError(
                "CSV content must be list[dict]"
            )

        # Cho phép ghi CSV rỗng.
        if not content:
            file_path.write_text(
                "",
                encoding="utf-8",
            )
            return

        # Mỗi row phải là dictionary.
        if not all(
                isinstance(row, dict)
                for row in content
        ):
            raise TypeError(
                "CSV content must be list[dict]"
            )

        # Dùng keys của row đầu tiên làm header.
        fieldnames = list(
            content[0].keys()
        )

        with file_path.open(
                "w",
                encoding="utf-8-sig",
                newline="",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )

            writer.writeheader()

            writer.writerows(content)

    # =========================================================
    # PATH / SECURITY
    # =========================================================

    def _resolve_path(
            self,
            path: str
    ) -> Path:
        """
        Chuyển relative path thành absolute path an toàn.

        Đây là phần rất quan trọng.

        Ví dụ workspace_root:

            D:/mci-agent/data/agent_workspace

        path:

            user_5/conversation_20/report.md

        kết quả:

            D:/mci-agent/data/agent_workspace/
                user_5/
                conversation_20/
                report.md

        Đồng thời ngăn path traversal như:

            ../../password.txt
        """

        relative_path = Path(path)

        # Không cho caller truyền absolute path.
        #
        # Ví dụ:
        # C:/Windows/system.ini
        # /etc/passwd
        if relative_path.is_absolute():
            raise ValueError(
                "Absolute paths are not allowed"
            )

        resolved_path = (
                self.workspace_root / relative_path
        ).resolve()

        # Sau khi resolve ../,
        # path cuối cùng bắt buộc phải nằm trong workspace.
        if not resolved_path.is_relative_to(
                self.workspace_root
        ):
            raise ValueError(
                "Path is outside workspace"
            )

        return resolved_path

    @staticmethod
    def _get_extension(
            file_path: Path
    ) -> str:
        """
        Lấy extension và chuẩn hóa thành lowercase.

        REPORT.MD -> .md
        Data.JSON -> .json
        """

        extension = file_path.suffix.lower()

        if not extension:
            raise ValueError(
                f"File has no extension: {file_path.name}"
            )

        return extension
