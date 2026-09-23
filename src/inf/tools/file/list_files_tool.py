from dataclasses import dataclass  # Import dataclass để tạo class chứa kết quả tool gọn hơn
from pathlib import Path  # Import Path để xử lý đường dẫn file và thư mục

from pydantic import Field  # Import Field để khai báo và mô tả tham số đầu vào của tool

from src.dom.tool import (  # Import các class nền tảng của hệ thống tool
    Tool,  # Class cha của tất cả các tool
    ToolKwargs,  # Class cha dùng để định nghĩa tham số đầu vào của tool
    ToolResult,  # Class cha dùng để định nghĩa kết quả trả về của tool
)
from src.inf.tools.file.helper import (  # Import các helper liên quan đến bảo vệ workspace
    WorkspacePathGuard,  # Class dùng để kiểm tra đường dẫn có nằm trong workspace hay không
    WorkspacePathError,  # Exception được ném ra khi đường dẫn cố thoát khỏi workspace
)


class ListFilesToolKwargs(ToolKwargs):  # Khai báo các tham số mà src được phép truyền vào list_files
    path: str = Field(  # Đường dẫn thư mục mà src muốn xem
        default="",  # Mặc định chuỗi rỗng nghĩa là xem thư mục gốc của workspace
        description=(  # Mô tả tham số cho LLM biết cách sử dụng
            "Directory to list, relative to the workspace root. "  # Path phải tính từ workspace
            "Use an empty string to list the workspace root. "  # Chuỗi rỗng nghĩa là workspace root
            "Examples: '', 'characters', 'research/animals'. "  # Một số ví dụ hợp lệ
            "Absolute paths and paths outside the workspace are not allowed."  # Không được truy cập ngoài workspace
        )
    )

    recursive: bool = Field(  # Xác định có duyệt sâu xuống các thư mục con hay không
        default=False,  # Mặc định chỉ xem trực tiếp thư mục hiện tại
        description=(  # Mô tả cho LLM hiểu recursive
            "If true, recursively list file and directories "  # True thì duyệt cả thư mục con
            "inside all subdirectories. "  # Tiếp tục duyệt xuống các cấp bên dưới
            "If false, only list direct children of the directory."  # False thì chỉ lấy một cấp hiện tại
        )
    )

    max_results: int = Field(  # Giới hạn số lượng kết quả trả về
        default=200,  # Mặc định tối đa 200 file hoặc thư mục
        ge=1,  # Không cho phép nhỏ hơn 1
        le=2000,  # Không cho phép lớn hơn 2000 để tránh output quá lớn
        description=(  # Mô tả mục đích của max_results
            "Maximum number of file and directories to return."  # Số lượng item tối đa được trả về
        )
    )


@dataclass  # Tự động tạo __init__ và các method tiện ích cho class kết quả
class ListFilesToolResult(ToolResult):  # Class chứa kết quả mà ListFilesTool trả về
    content: str  # Nội dung danh sách file hoặc thông báo lỗi
    path: str | None = None  # Thư mục đang được list, có thể None nếu xảy ra lỗi
    truncated: bool = False  # Cho biết kết quả có bị cắt do vượt max_results hay không

    def to_text(self) -> str:  # Chuyển kết quả thành chuỗi để src đọc
        if self.path is None:  # Nếu không có path thì thường là trường hợp xảy ra lỗi
            return self.content  # Trả thẳng nội dung lỗi

        output = [  # Tạo danh sách các dòng output
            f"Directory: {self.path}",  # Hiển thị thư mục đang được xem
            "",  # Thêm một dòng trống cho dễ đọc
            self.content,  # Thêm danh sách file và thư mục
        ]

        if self.truncated:  # Nếu kết quả đã bị cắt vì vượt max_results
            output.extend([  # Thêm thông báo cảnh báo vào cuối kết quả
                "",  # Thêm một dòng trống
                "[Results truncated because max_results was reached.]"  # Báo rằng vẫn còn kết quả chưa được hiển thị
            ])

        return "\n".join(output)  # Ghép tất cả các dòng thành một chuỗi hoàn chỉnh


class ListFilesTool(Tool):  # Khai báo tool list_files và kế thừa từ Tool
    tool_name = "list_files"  # Tên mà src sẽ dùng để gọi tool

    tool_description = (  # Mô tả chức năng của tool cho LLM
        "List file and directories inside the src workspace. "  # Tool dùng để xem file và thư mục trong workspace
        "The path must be relative to the workspace root. "  # Đường dẫn phải là relative path
        "Use this tool to discover available scripts, prompts, research, "  # Có thể dùng để tìm script, prompt, research
        "character file, metadata, and other project resources. "  # Và các tài nguyên khác trong project
        "This tool cannot inspect directories outside the workspace."  # Không được phép xem ngoài workspace
    )

    tool_kwargs = ListFilesToolKwargs  # Chỉ định schema tham số đầu vào của tool

    def __init__(  # Hàm khởi tạo ListFilesTool
            self,  # Instance hiện tại của tool
            workspace_dir: str | Path,  # Workspace mà tool được phép truy cập
    ):
        self.path_guard = WorkspacePathGuard(  # Tạo bộ bảo vệ đường dẫn
            workspace_dir  # Truyền workspace vào path guard
        )

    def execute(self, **kwargs) -> ToolResult:  # Hàm chính được gọi khi src sử dụng tool
        args = self.tool_kwargs(**kwargs)  # Validate kwargs và chuyển thành ListFilesToolKwargs

        try:  # Thử resolve đường dẫn thư mục mà src yêu cầu
            directory_path = self.path_guard.resolve(  # Chuyển relative path thành absolute path an toàn
                args.path  # Path mà src truyền vào
            )

        except WorkspacePathError as e:  # Nếu src cố truy cập ra ngoài workspace
            return ListFilesToolResult(  # Trả về kết quả lỗi
                content=f"Access denied: {e}"  # Báo rằng quyền truy cập bị từ chối
            )

        if not directory_path.exists():  # Kiểm tra thư mục có tồn tại hay không
            return ListFilesToolResult(  # Nếu không tồn tại thì trả về lỗi
                content=(  # Tạo nội dung lỗi
                    f"Directory does not exist: "  # Phần đầu thông báo
                    f"{args.path}"  # Hiển thị path mà src đã truyền
                )
            )

        if not directory_path.is_dir():  # Kiểm tra path có thực sự là thư mục hay không
            return ListFilesToolResult(  # Nếu là file thì không thể list bên trong
                content=(  # Tạo thông báo lỗi
                    f"Path is not a directory: "  # Báo rằng path không phải directory
                    f"{args.path}"  # Hiển thị path gây lỗi
                )
            )

        try:  # Bắt đầu đọc danh sách file trong thư mục
            if args.recursive:  # Nếu src muốn duyệt toàn bộ thư mục con
                entries = directory_path.rglob("*")  # Lấy tất cả file và thư mục ở tất cả các cấp bên dưới

            else:  # Nếu src chỉ muốn xem một cấp hiện tại
                entries = directory_path.iterdir()  # Chỉ lấy các item trực tiếp bên trong thư mục

            results: list[str] = []  # Tạo danh sách để chứa kết quả
            truncated = False  # Ban đầu mặc định kết quả chưa bị cắt

            for entry in entries:  # Duyệt lần lượt từng file hoặc thư mục tìm được
                try:  # Kiểm tra từng entry để tránh symlink hoặc path thoát khỏi workspace
                    relative_entry = entry.relative_to(  # Chuyển entry thành đường dẫn tương đối
                        self.path_guard.workspace_dir  # Tính relative path dựa trên workspace root
                    )

                    safe_entry = self.path_guard.resolve(  # Resolve lại entry thông qua WorkspacePathGuard
                        str(relative_entry)  # Chuyển Path thành string rồi gửi vào guard
                    )

                except (  # Bắt các lỗi xảy ra khi entry không an toàn
                    ValueError,  # Có thể xảy ra nếu entry không nằm trong workspace
                    WorkspacePathError,  # Xảy ra nếu entry resolve ra ngoài workspace
                ):
                    continue  # Bỏ qua entry không an toàn và chuyển sang entry tiếp theo

                if safe_entry.is_dir():  # Kiểm tra entry có phải thư mục hay không
                    entry_type = "DIR"  # Gắn nhãn DIR nếu là thư mục

                elif safe_entry.is_file():  # Nếu không phải thư mục thì kiểm tra có phải file không
                    entry_type = "FILE"  # Gắn nhãn FILE nếu là file

                else:  # Nếu không phải file cũng không phải directory
                    entry_type = "OTHER"  # Gắn nhãn OTHER cho các loại đặc biệt khác

                results.append(  # Thêm entry vào danh sách kết quả
                    f"[{entry_type}] {relative_entry}"  # Ví dụ: [FILE] characters/lion.json
                )

                if len(results) >= args.max_results:  # Kiểm tra đã đạt số lượng tối đa chưa
                    truncated = True  # Đánh dấu rằng kết quả đã bị cắt
                    break  # Dừng vòng lặp để không lấy thêm item nữa

        except OSError as e:  # Bắt lỗi hệ điều hành như permission denied hoặc lỗi đọc folder
            return ListFilesToolResult(  # Trả về lỗi thay vì làm chương trình crash
                content=f"Failed to list directory: {e}"  # Hiển thị lỗi thực tế
            )

        if not results:  # Nếu danh sách kết quả rỗng
            content = "[Directory is empty.]"  # Thông báo thư mục không có gì bên trong

        else:  # Nếu có file hoặc thư mục
            results.sort()  # Sắp xếp kết quả theo alphabet để src dễ đọc
            content = "\n".join(results)  # Ghép danh sách thành một chuỗi nhiều dòng

        relative_directory = self.path_guard.to_relative(  # Chuyển absolute path của directory về relative path
            directory_path  # Directory mà src vừa yêu cầu list
        )

        if relative_directory == ".":  # Nếu đang list chính workspace root
            relative_directory = "."  # Hiển thị workspace root đơn giản là dấu chấm

        return ListFilesToolResult(  # Trả kết quả thành công cho src
            path=relative_directory,  # Đường dẫn thư mục vừa được xem
            content=content,  # Danh sách file và thư mục
            truncated=truncated,  # Cho biết danh sách có bị cắt hay không
        )