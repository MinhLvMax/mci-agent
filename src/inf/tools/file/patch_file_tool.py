from dataclasses import dataclass  # Import dataclass để tạo class kết quả tool gọn hơn
from pathlib import Path  # Import Path để xử lý đường dẫn file và thư mục

from pydantic import Field  # Import Field để khai báo và mô tả tham số đầu vào của tool

from src.dom.tool import (  # Import các class nền tảng của hệ thống tool
    Tool,  # Class cha của tất cả các tool
    ToolKwargs,  # Class cha dùng để định nghĩa tham số đầu vào của tool
    ToolResult,  # Class cha dùng để định nghĩa kết quả trả về của tool
)
from src.inf.tools.file.helper import (  # Import các helper dùng để bảo vệ workspace
    WorkspacePathGuard,  # Class kiểm tra đường dẫn có nằm an toàn trong workspace hay không
    WorkspacePathError,  # Exception được ném ra khi đường dẫn cố thoát khỏi workspace
)


class PatchFileToolKwargs(ToolKwargs):  # Khai báo các tham số đầu vào mà src được phép truyền vào patch_file
    path: str = Field(  # Đường dẫn file mà src muốn sửa
        description=(  # Mô tả cách sử dụng path cho LLM
            "Path of the text file to patch, relative to the workspace root. "  # Path phải tính từ workspace
            "Examples: 'script.md', 'characters/cave_lion.json'. "  # Một số ví dụ đường dẫn hợp lệ
            "Absolute paths and paths outside the workspace are not allowed."  # Không cho phép truy cập ngoài workspace
        )
    )

    old_text: str = Field(  # Đoạn text cũ cần tìm trong file
        min_length=1,  # Không cho phép old_text là chuỗi rỗng
        description=(  # Mô tả mục đích của old_text
            "Exact existing text to find in the file. "  # Tool sẽ tìm chính xác đoạn text này
            "The text must match the current file content exactly."
        # Nội dung phải giống chính xác với nội dung đang có trong file
        )
    )

    new_text: str = Field(  # Đoạn text mới sẽ thay thế cho old_text
        description=(  # Mô tả mục đích của new_text
            "New text that will replace old_text."  # Nội dung mới được dùng để thay thế đoạn cũ
        )
    )

    replace_all: bool = Field(  # Xác định có thay tất cả các vị trí giống nhau hay không
        default=False,  # Mặc định chỉ cho phép sửa khi old_text xuất hiện đúng một lần
        description=(  # Mô tả hành vi của replace_all
            "If false, old_text must appear exactly once in the file. "  # False thì old_text phải xuất hiện đúng một lần
            "If true, all occurrences of old_text will be replaced."  # True thì thay toàn bộ các vị trí tìm thấy
        )
    )


@dataclass  # Tự động tạo __init__ và các method tiện ích cho class kết quả
class PatchFileToolResult(ToolResult):  # Class chứa kết quả trả về từ PatchFileTool
    content: str  # Nội dung thông báo thành công hoặc lỗi
    path: str | None = None  # Đường dẫn file đã sửa, None nếu xảy ra lỗi
    replacements: int = 0  # Số lần old_text đã được thay thế

    def to_text(self) -> str:  # Chuyển kết quả tool thành chuỗi để src đọc
        if self.path is None:  # Nếu không có path thì thường là trường hợp lỗi
            return self.content  # Trả thẳng nội dung lỗi

        return (  # Tạo chuỗi kết quả thành công
            f"{self.content}\n"  # Hiển thị thông báo kết quả
            f"File: {self.path}\n"  # Hiển thị file vừa được sửa
            f"Replacements: {self.replacements}"  # Hiển thị số lần đã thay thế
        )


class PatchFileTool(Tool):  # Khai báo tool patch_file và kế thừa từ Tool
    tool_name = "patch_file"  # Tên mà src sẽ sử dụng để gọi tool

    tool_description = (  # Mô tả chức năng của tool cho LLM
        "Replace exact text inside an existing UTF-8 text file in the src workspace. "  # Tool dùng để thay một đoạn text trong file hiện có
        "Use this tool when only part of a file needs to be changed instead of rewriting the entire file. "  # Dùng khi chỉ muốn sửa một phần file
        "By default, the target text must appear exactly once to avoid accidental edits. "  # Mặc định chỉ sửa nếu đoạn cần tìm xuất hiện đúng một lần
        "Set replace_all to true only when every occurrence should be replaced. "  # Chỉ bật replace_all khi thực sự muốn thay tất cả
        "This tool cannot modify file outside the workspace."  # Không được phép sửa file ngoài workspace
    )

    tool_kwargs = PatchFileToolKwargs  # Chỉ định schema tham số đầu vào của tool

    def __init__(  # Hàm khởi tạo PatchFileTool
            self,  # Instance hiện tại của tool
            workspace_dir: str | Path,  # Workspace mà tool được phép thao tác
    ):
        self.path_guard = WorkspacePathGuard(  # Tạo bộ kiểm soát đường dẫn
            workspace_dir  # Truyền workspace vào để giới hạn quyền truy cập
        )

    def execute(self, **kwargs) -> ToolResult:  # Hàm chính được gọi khi src sử dụng tool
        args = self.tool_kwargs(**kwargs)  # Validate kwargs và chuyển thành PatchFileToolKwargs

        try:  # Bắt đầu kiểm tra đường dẫn file
            file_path = self.path_guard.resolve(  # Chuyển relative path thành absolute path an toàn
                args.path  # Path mà src yêu cầu sửa
            )

        except WorkspacePathError as e:  # Nếu path cố thoát khỏi workspace
            return PatchFileToolResult(  # Trả về kết quả lỗi
                content=f"Access denied: {e}"  # Báo rằng quyền truy cập bị từ chối
            )

        if not file_path.exists():  # Kiểm tra file có tồn tại hay không
            return PatchFileToolResult(  # Nếu không tồn tại thì trả về lỗi
                content=(  # Tạo nội dung thông báo lỗi
                    f"File does not exist: "  # Báo file không tồn tại
                    f"{args.path}"  # Hiển thị path mà src đã truyền
                )
            )

        if not file_path.is_file():  # Kiểm tra path có thực sự là file hay không
            return PatchFileToolResult(  # Nếu path là folder thì trả về lỗi
                content=(  # Tạo nội dung thông báo lỗi
                    f"Path is not a file: "  # Báo rằng path không phải file
                    f"{args.path}"  # Hiển thị path gây lỗi
                )
            )

        try:  # Bắt đầu đọc nội dung hiện tại của file
            content = file_path.read_text(  # Đọc toàn bộ file thành string
                encoding="utf-8"  # Chỉ đọc file bằng encoding UTF-8
            )

        except UnicodeDecodeError:  # Nếu file không phải UTF-8 hợp lệ
            return PatchFileToolResult(  # Trả về lỗi
                content=(  # Tạo nội dung thông báo
                    "Failed to patch file because it is not "  # Phần đầu thông báo lỗi
                    "a valid UTF-8 text file."  # Báo file không phải text UTF-8 hợp lệ
                )
            )

        except OSError as e:  # Nếu hệ điều hành không cho phép đọc file hoặc xảy ra lỗi I/O
            return PatchFileToolResult(  # Trả về lỗi thay vì làm chương trình crash
                content=f"Failed to read file: {e}"  # Hiển thị lỗi thực tế
            )

        occurrences = content.count(args.old_text)  # Đếm xem old_text xuất hiện bao nhiêu lần trong file

        if occurrences == 0:  # Nếu không tìm thấy old_text
            return PatchFileToolResult(  # Trả về lỗi để src biết nội dung hiện tại không khớp
                content=(  # Tạo nội dung thông báo lỗi
                    "Patch failed because old_text was not found "  # Báo rằng không tìm thấy đoạn cần sửa
                    f"in file: {args.path}"  # Hiển thị file đang được patch
                )
            )

        if not args.replace_all and occurrences > 1:  # Nếu old_text xuất hiện nhiều lần nhưng src không yêu cầu replace_all
            return PatchFileToolResult(  # Không tự ý sửa vì không biết src muốn sửa vị trí nào
                content=(  # Tạo thông báo lỗi
                    f"Patch is ambiguous because old_text appears "  # Báo rằng đoạn cần sửa không duy nhất
                    f"{occurrences} times in file: {args.path}. "  # Hiển thị số lần xuất hiện
                    "Provide a more specific old_text or set replace_all=true."
                # Yêu cầu src cung cấp đoạn cụ thể hơn hoặc bật replace_all
                )
            )

        if args.replace_all:  # Nếu src yêu cầu thay tất cả các vị trí
            patched_content = content.replace(  # Thực hiện thay thế text
                args.old_text,  # Đoạn text cũ cần tìm
                args.new_text,  # Đoạn text mới dùng để thay thế
            )
            replacements = occurrences  # Số lần thay thế bằng tổng số occurrence đã tìm thấy

        else:  # Nếu replace_all=False và old_text chỉ xuất hiện đúng một lần
            patched_content = content.replace(  # Thực hiện thay thế text
                args.old_text,  # Đoạn text cũ
                args.new_text,  # Đoạn text mới
                1,  # Chỉ thay thế đúng một lần
            )
            replacements = 1  # Ghi nhận có một lần thay thế

        if patched_content == content:  # Kiểm tra sau khi patch nội dung có thực sự thay đổi hay không
            return PatchFileToolResult(  # Nếu không thay đổi thì không cần ghi lại file
                content=(  # Tạo thông báo
                    "No changes were made because the replacement "  # Báo không có thay đổi
                    "produced the same file content."  # Nội dung sau khi thay giống nội dung ban đầu
                )
            )

        try:  # Bắt đầu ghi nội dung mới trở lại file
            file_path.write_text(  # Ghi toàn bộ nội dung đã patch vào file
                patched_content,  # Nội dung mới sau khi thay thế
                encoding="utf-8",  # Ghi file bằng UTF-8
            )

        except OSError as e:  # Nếu xảy ra lỗi khi ghi file
            return PatchFileToolResult(  # Trả về lỗi thay vì làm chương trình crash
                content=f"Failed to patch file: {e}"  # Hiển thị lỗi thực tế từ hệ điều hành
            )

        return PatchFileToolResult(  # Trả về kết quả khi patch thành công
            content="File patched successfully.",  # Thông báo sửa file thành công
            path=self.path_guard.to_relative(  # Chuyển absolute path thành relative path để trả về
                file_path  # File vừa được sửa
            ),
            replacements=replacements,  # Trả về số lần đã thay thế
        )
