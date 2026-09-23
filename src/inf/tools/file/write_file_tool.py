from dataclasses import dataclass  # Import dataclass để tạo class kết quả tool gọn hơn
from pathlib import Path  # Import Path để xử lý đường dẫn file và thư mục

from pydantic import Field  # Import Field để khai báo và validate tham số đầu vào

from src.dom.tool import (  # Import các class nền tảng của hệ thống tool
    Tool,  # Class cha của tất cả các tool
    ToolKwargs,  # Class cha dùng để định nghĩa tham số đầu vào
    ToolResult,  # Class cha dùng để định nghĩa kết quả trả về
)
from src.inf.tools.file.helper import (  # Import helper bảo vệ workspace
    WorkspacePathGuard,  # Class giới hạn tool trong workspace
    WorkspacePathError,  # Exception khi đường dẫn cố thoát khỏi workspace
)


class WriteFileToolKwargs(ToolKwargs):  # Khai báo các tham số src được phép truyền vào write_file
    path: str = Field(  # Đường dẫn file muốn ghi
        description=(  # Mô tả cách sử dụng path
            "Path of the file to write, relative to the workspace root. "  # Path phải relative với workspace
            "Examples: 'characters/cave_lion.json', "  # Ví dụ path hợp lệ
            "'prompts/shot_001.txt'. "  # Ví dụ path hợp lệ khác
            "Absolute paths and paths outside the workspace are not allowed."  # Không cho phép truy cập ngoài workspace
        )
    )

    content: str = Field(  # Nội dung cần ghi vào file
        description=(  # Mô tả cho LLM
            "The complete text content to write to the file."  # Nội dung text cần ghi
        )
    )

    append: bool = Field(  # Xác định có ghi nối vào file hay không
        default=False,  # Mặc định không append
        description=(  # Mô tả hành vi append
            "If true, append content to the end of the file. "  # True thì nối vào cuối file
            "Use this only when existing content should be preserved."  # Chỉ dùng khi muốn giữ nội dung cũ
        )
    )

    overwrite: bool = Field(  # Xác định có được phép ghi đè file đang tồn tại không
        default=False,  # Mặc định không cho phép ghi đè
        description=(  # Mô tả hành vi overwrite
            "If true, an existing file may be completely replaced. "  # True thì có thể xóa nội dung cũ và ghi lại
            "If false, writing to an existing file is rejected unless append is true."
            # False thì file đã tồn tại sẽ bị từ chối
        )
    )


@dataclass  # Tự động tạo __init__ và các method tiện ích
class WriteFileToolResult(ToolResult):  # Class chứa kết quả trả về từ write_file
    content: str  # Thông báo kết quả hoặc lỗi
    path: str | None = None  # Relative path của file, None nếu lỗi
    chars_written: int = 0  # Số ký tự đã được ghi

    def to_text(self) -> str:  # Chuyển kết quả thành chuỗi để src đọc
        if self.path is None:  # Nếu không có path thì thường là lỗi
            return self.content  # Trả thẳng thông báo lỗi

        return (  # Tạo output khi ghi thành công
            f"{self.content}\n"  # Hiển thị hành động vừa thực hiện
            f"File: {self.path}\n"  # Hiển thị file vừa ghi
            f"Characters written: {self.chars_written}"  # Hiển thị số ký tự đã ghi
        )


class WriteFileTool(Tool):  # Khai báo WriteFileTool và kế thừa từ Tool
    tool_name = "write_file"  # Tên src dùng để gọi tool

    tool_description = (  # Mô tả chức năng của tool cho LLM
        "Create or write a UTF-8 text file inside the src workspace. "  # Tool dùng để tạo hoặc ghi file UTF-8
        "The path must be relative to the workspace root. "  # Path phải relative với workspace
        "Existing file are protected from accidental overwriting by default. "  # Mặc định bảo vệ file đang tồn tại
        "Use append=true to add content to an existing file. "  # append dùng để nối nội dung
        "Use overwrite=true only when the entire existing file should be replaced. "  # overwrite dùng khi thực sự muốn ghi đè
        "Parent directories are created automatically when necessary. "  # Tự động tạo thư mục cha
        "This tool cannot modify file outside the workspace."  # Không được ghi ngoài workspace
    )

    tool_kwargs = WriteFileToolKwargs  # Chỉ định schema tham số đầu vào

    def __init__(  # Hàm khởi tạo tool
            self,  # Instance hiện tại
            workspace_dir: str | Path,  # Workspace mà tool được phép thao tác
    ):
        self.path_guard = WorkspacePathGuard(  # Tạo bộ bảo vệ đường dẫn
            workspace_dir  # Truyền workspace vào guard
        )

    def execute(self, **kwargs) -> ToolResult:  # Hàm chính được gọi khi src sử dụng tool
        args = self.tool_kwargs(**kwargs)  # Validate kwargs và chuyển thành WriteFileToolKwargs

        if args.append and args.overwrite:  # Kiểm tra src có bật đồng thời append và overwrite không
            return WriteFileToolResult(  # Nếu có thì trả lỗi vì hai hành vi mâu thuẫn nhau
                content=(  # Tạo thông báo lỗi
                    "append and overwrite cannot both be true. "  # Báo hai option không được bật cùng lúc
                    "Choose either append or overwrite."  # Yêu cầu src chọn một hành vi
                )
            )

        try:  # Bắt đầu resolve đường dẫn file
            file_path = self.path_guard.resolve(  # Chuyển relative path thành absolute path an toàn
                args.path  # Path mà src muốn ghi
            )

        except WorkspacePathError as e:  # Nếu src cố ghi ra ngoài workspace
            return WriteFileToolResult(  # Trả lỗi
                content=f"Access denied: {e}"  # Báo quyền truy cập bị từ chối
            )

        if file_path.exists() and file_path.is_dir():  # Nếu path đang trỏ tới một directory
            return WriteFileToolResult(  # Không cho phép ghi text vào directory
                content=(  # Tạo thông báo lỗi
                    f"Cannot write because the path "  # Phần đầu thông báo
                    f"is a directory: {args.path}"  # Hiển thị directory gây lỗi
                )
            )

        file_exists = file_path.exists()  # Ghi nhớ file đã tồn tại từ trước hay chưa

        if (  # Kiểm tra trường hợp file đã tồn tại nhưng src không chỉ định cách xử lý
                file_exists  # File đã tồn tại
                and not args.append  # Không yêu cầu append
                and not args.overwrite  # Cũng không cho phép overwrite
        ):
            return WriteFileToolResult(  # Từ chối ghi để bảo vệ file cũ
                content=(  # Tạo thông báo lỗi
                    f"File already exists: {args.path}. "  # Báo file đã tồn tại
                    "Use append=true to add content, "  # Hướng dẫn dùng append
                    "overwrite=true to replace the file, "  # Hướng dẫn dùng overwrite
                    "or patch_file to modify only part of the file."  # Gợi ý patch_file nếu chỉ muốn sửa một phần
                )
            )

        try:  # Bắt đầu chuẩn bị ghi file
            file_path.parent.mkdir(  # Tạo thư mục cha nếu chưa tồn tại
                parents=True,  # Tạo luôn toàn bộ các folder cha còn thiếu
                exist_ok=True,  # Nếu folder đã tồn tại thì không báo lỗi
            )

            if args.append:  # Nếu src yêu cầu ghi nối
                with file_path.open(  # Mở file
                        mode="a",  # Chế độ append
                        encoding="utf-8",  # Ghi dưới dạng UTF-8
                ) as file:  # Gán file đang mở vào biến file
                    file.write(  # Ghi nội dung
                        args.content  # Nội dung src truyền vào
                    )

                if file_exists:  # Nếu file đã tồn tại trước đó
                    action = "Content appended successfully."  # Báo đã nối nội dung thành công

                else:  # Nếu file chưa tồn tại thì mode=a vừa tạo file mới
                    action = "File created successfully."  # Báo file mới đã được tạo

            else:  # Nếu không phải append
                file_path.write_text(  # Ghi toàn bộ content vào file
                    args.content,  # Nội dung cần ghi
                    encoding="utf-8",  # Sử dụng UTF-8
                )

                if file_exists:  # Nếu file đã tồn tại và overwrite=True
                    action = "File overwritten successfully."  # Báo file đã được ghi đè

                else:  # Nếu file chưa tồn tại
                    action = "File created successfully."  # Báo file mới đã được tạo

        except OSError as e:  # Nếu hệ điều hành gặp lỗi khi ghi file
            return WriteFileToolResult(  # Trả lỗi thay vì crash chương trình
                content=f"Failed to write file: {e}"  # Hiển thị lỗi thực tế
            )

        return WriteFileToolResult(  # Trả kết quả ghi file thành công
            content=action,  # Hành động vừa thực hiện
            path=self.path_guard.to_relative(  # Chuyển absolute path về relative path
                file_path  # File vừa được ghi
            ),
            chars_written=len(args.content),  # Trả số ký tự đã được ghi
        )
