from dataclasses import dataclass  # Import dataclass để tạo class kết quả tool gọn hơn
from datetime import datetime  # Import datetime để chuyển timestamp thành ngày giờ dễ đọc
from pathlib import Path  # Import Path để xử lý đường dẫn file và thư mục

from pydantic import Field  # Import Field để khai báo và mô tả tham số đầu vào của tool

from src.dom.tool import (  # Import các class nền tảng của hệ thống tool
    Tool,  # Class cha của tất cả các tool
    ToolKwargs,  # Class cha dùng để định nghĩa tham số đầu vào của tool
    ToolResult,  # Class cha dùng để định nghĩa kết quả trả về của tool
)
from src.inf.tools.file.helper import (  # Import các helper dùng để bảo vệ workspace
    WorkspacePathGuard,  # Class kiểm tra đường dẫn có nằm trong workspace hay không
    WorkspacePathError,  # Exception được ném ra khi đường dẫn cố thoát khỏi workspace
)


class GetFileInfoToolKwargs(ToolKwargs):  # Khai báo các tham số đầu vào mà src được phép truyền vào tool
    path: str = Field(  # Đường dẫn của file mà src muốn xem thông tin
        description=(  # Mô tả cách sử dụng path cho LLM
            "Path of the file to inspect, relative to the workspace root. "  # Path phải tính từ workspace
            "Examples: 'script.md', 'characters/cave_lion.json'. "  # Một số ví dụ hợp lệ
            "Absolute paths and paths outside the workspace are not allowed."  # Không cho phép truy cập ngoài workspace
        )
    )


@dataclass  # Tự động tạo __init__ và các method tiện ích cho class kết quả
class GetFileInfoToolResult(ToolResult):  # Class chứa kết quả trả về từ GetFileInfoTool
    content: str  # Nội dung kết quả hoặc thông báo lỗi
    path: str | None = None  # Đường dẫn file dạng relative path, None nếu xảy ra lỗi
    size_bytes: int | None = None  # Kích thước file tính bằng byte
    line_count: int | None = None  # Số dòng của file text, None nếu không đọc được dưới dạng UTF-8
    extension: str | None = None  # Phần mở rộng của file, ví dụ .md hoặc .json
    modified_at: str | None = None  # Thời gian file được chỉnh sửa gần nhất

    def to_text(self) -> str:  # Chuyển kết quả tool thành chuỗi để src đọc
        if self.path is None:  # Nếu không có path thì thường là trường hợp lỗi
            return self.content  # Trả thẳng nội dung lỗi

        output = [  # Tạo danh sách các dòng output
            f"File: {self.path}",  # Hiển thị đường dẫn file
            f"Size: {self.size_bytes} bytes",  # Hiển thị kích thước file
            f"Extension: {self.extension or '[none]'}",  # Hiển thị extension hoặc [none] nếu file không có extension
            f"Modified at: {self.modified_at}",  # Hiển thị thời gian sửa file gần nhất
        ]

        if self.line_count is not None:  # Nếu có thể đọc file dưới dạng UTF-8
            output.append(  # Thêm thông tin số dòng vào output
                f"Lines: {self.line_count}"  # Hiển thị tổng số dòng
            )

        else:  # Nếu file không đọc được dưới dạng UTF-8
            output.append(  # Thêm thông báo thay cho số dòng
                "Lines: unavailable (not a valid UTF-8 text file)"  # Báo rằng không thể đếm dòng text
            )

        return "\n".join(output)  # Ghép toàn bộ các dòng thành một chuỗi hoàn chỉnh


class GetFileInfoTool(Tool):  # Khai báo tool get_file_info và kế thừa từ Tool
    tool_name = "get_file_info"  # Tên mà src sẽ dùng để gọi tool

    tool_description = (  # Mô tả chức năng của tool cho LLM
        "Inspect metadata about a file inside the src workspace. "  # Tool dùng để xem metadata của file
        "Returns information such as file size, extension, line count, "  # Trả kích thước, extension và số dòng
        "and last modified time. "  # Trả thêm thời gian chỉnh sửa gần nhất
        "Use this tool before reading large file to decide whether the file "  # Hữu ích trước khi đọc file lớn
        "should be read completely or in smaller sections. "  # Giúp src quyết định cách đọc file
        "This tool cannot inspect file outside the workspace."  # Không được phép truy cập ngoài workspace
    )

    tool_kwargs = GetFileInfoToolKwargs  # Chỉ định schema tham số đầu vào của tool

    def __init__(  # Hàm khởi tạo GetFileInfoTool
            self,  # Instance hiện tại của tool
            workspace_dir: str | Path,  # Workspace mà tool được phép truy cập
    ):
        self.path_guard = WorkspacePathGuard(  # Tạo bộ bảo vệ đường dẫn
            workspace_dir  # Truyền workspace vào để giới hạn quyền truy cập
        )

    def execute(self, **kwargs) -> ToolResult:  # Hàm chính được gọi khi src sử dụng tool
        args = self.tool_kwargs(**kwargs)  # Validate kwargs và chuyển thành GetFileInfoToolKwargs

        try:  # Bắt đầu kiểm tra và resolve đường dẫn
            file_path = self.path_guard.resolve(  # Chuyển relative path thành absolute path an toàn
                args.path  # Path mà src truyền vào
            )

        except WorkspacePathError as e:  # Nếu path cố thoát khỏi workspace
            return GetFileInfoToolResult(  # Trả về kết quả lỗi
                content=f"Access denied: {e}"  # Báo rằng quyền truy cập bị từ chối
            )

        if not file_path.exists():  # Kiểm tra đường dẫn có tồn tại hay không
            return GetFileInfoToolResult(  # Nếu không tồn tại thì trả về lỗi
                content=(  # Tạo nội dung thông báo lỗi
                    f"File does not exist: "  # Báo file không tồn tại
                    f"{args.path}"  # Hiển thị path mà src đã truyền
                )
            )

        if not file_path.is_file():  # Kiểm tra path có thực sự là file hay không
            return GetFileInfoToolResult(  # Nếu path là directory thì trả lỗi
                content=(  # Tạo thông báo lỗi
                    f"Path is not a file: "  # Báo rằng path không phải file
                    f"{args.path}"  # Hiển thị path gây lỗi
                )
            )

        try:  # Bắt đầu lấy metadata của file
            file_stat = file_path.stat()  # Lấy thông tin metadata từ hệ điều hành

            size_bytes = file_stat.st_size  # Lấy kích thước file tính bằng byte

            modified_at = datetime.fromtimestamp(  # Chuyển timestamp thành đối tượng datetime
                file_stat.st_mtime  # Lấy timestamp của lần chỉnh sửa gần nhất
            ).isoformat(  # Chuyển datetime thành chuỗi ISO dễ đọc
                timespec="seconds"  # Chỉ hiển thị chính xác tới giây
            )

        except OSError as e:  # Nếu hệ điều hành không thể lấy metadata
            return GetFileInfoToolResult(  # Trả về lỗi thay vì làm chương trình crash
                content=f"Failed to inspect file: {e}"  # Hiển thị lỗi thực tế
            )

        line_count: int | None = None  # Mặc định chưa xác định được số dòng

        try:  # Thử đọc file dưới dạng text UTF-8 để đếm số dòng
            with file_path.open(  # Mở file
                    mode="r",  # Mở ở chế độ đọc
                    encoding="utf-8",  # Đọc bằng encoding UTF-8
            ) as file:  # Gán file đang mở vào biến file
                line_count = sum(  # Đếm tổng số dòng trong file
                    1 for _ in file  # Mỗi dòng đọc được sẽ cộng thêm 1
                )

        except UnicodeDecodeError:  # Nếu file không phải text UTF-8
            line_count = None  # Không thể xác định số dòng text

        except OSError:  # Nếu xảy ra lỗi khi đọc file
            line_count = None  # Không làm tool fail hoàn toàn, chỉ bỏ thông tin số dòng

        relative_path = self.path_guard.to_relative(  # Chuyển absolute path về relative path
            file_path  # File đang được inspect
        )

        return GetFileInfoToolResult(  # Trả kết quả thành công
            content="File information retrieved successfully.",  # Thông báo lấy thông tin thành công
            path=relative_path,  # Đường dẫn file relative với workspace
            size_bytes=size_bytes,  # Kích thước file tính bằng byte
            line_count=line_count,  # Tổng số dòng nếu file là UTF-8 text
            extension=file_path.suffix.lower(),  # Lấy extension của file và chuyển về chữ thường
            modified_at=modified_at,  # Thời gian file được sửa gần nhất
        )