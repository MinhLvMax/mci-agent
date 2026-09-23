from dataclasses import dataclass  # Import dataclass để tạo class kết quả tool gọn hơn
from pathlib import Path  # Import Path để xử lý đường dẫn file và thư mục

from pydantic import Field  # Import Field để khai báo và validate tham số đầu vào

from src.dom.tool import (  # Import các class nền tảng của hệ thống tool
    Tool,  # Class cha của tất cả các tool
    ToolKwargs,  # Class cha dùng để định nghĩa tham số đầu vào
    ToolResult,  # Class cha dùng để định nghĩa kết quả trả về
)
from src.inf.tools.file.helper import (  # Import các helper bảo vệ workspace
    WorkspacePathGuard,  # Class đảm bảo tool chỉ truy cập bên trong workspace
    WorkspacePathError,  # Exception xảy ra khi đường dẫn cố thoát khỏi workspace
)


class ReadFileToolKwargs(ToolKwargs):  # Khai báo các tham số src được phép truyền vào read_file
    path: str = Field(  # Đường dẫn file cần đọc
        description=(  # Mô tả cách sử dụng path cho LLM
            "Path of the text file to read, relative to the workspace root. "  # Path phải tính từ workspace
            "Examples: 'script.md', 'characters/cave_lion.json'. "  # Ví dụ path hợp lệ
            "Absolute paths and paths outside the workspace are not allowed."  # Không cho phép truy cập ngoài workspace
        )
    )

    start_line: int | None = Field(  # Dòng bắt đầu muốn đọc
        default=None,  # None nghĩa là bắt đầu từ dòng đầu tiên
        ge=1,  # Nếu truyền thì dòng phải từ 1 trở lên
        description=(  # Mô tả chức năng cho LLM
            "First line to read, using 1-based line numbering. "  # Số dòng bắt đầu từ 1 chứ không phải 0
            "If omitted, reading starts from the first line."  # Không truyền thì đọc từ dòng đầu tiên
        )
    )

    end_line: int | None = Field(  # Dòng cuối cùng muốn đọc
        default=None,  # None nghĩa là đọc tới cuối file
        ge=1,  # Nếu truyền thì dòng phải từ 1 trở lên
        description=(  # Mô tả chức năng cho LLM
            "Last line to read, using 1-based line numbering. "  # Số dòng cuối muốn lấy
            "If omitted, reading continues to the end of the file."  # Không truyền thì đọc đến cuối file
        )
    )

    max_chars: int = Field(  # Giới hạn số ký tự tối đa được trả về
        default=20_000,  # Mặc định tối đa 20.000 ký tự
        ge=1,  # Không cho phép nhỏ hơn 1
        le=100_000,  # Không cho phép lớn hơn 100.000
        description=(  # Mô tả chức năng cho LLM
            "Maximum number of characters to return. "  # Giới hạn output của tool
            "The content is truncated if this limit is reached."  # Nội dung sẽ bị cắt nếu vượt giới hạn
        )
    )


@dataclass  # Tự động tạo __init__ và các method tiện ích
class ReadFileToolResult(ToolResult):  # Class chứa kết quả trả về từ read_file
    content: str  # Nội dung file hoặc thông báo lỗi
    path: str | None = None  # Relative path của file, None nếu xảy ra lỗi
    total_lines: int | None = None  # Tổng số dòng của toàn bộ file
    start_line: int | None = None  # Dòng đầu tiên thực tế đã đọc
    end_line: int | None = None  # Dòng cuối cùng thực tế đã đọc
    has_more: bool = False  # Cho biết phía sau vẫn còn nội dung chưa đọc hay không
    truncated: bool = False  # Cho biết nội dung có bị cắt vì max_chars hay không

    def to_text(self) -> str:  # Chuyển kết quả thành chuỗi để src đọc
        if self.path is None:  # Nếu không có path thì thường là lỗi
            return self.content  # Trả thẳng thông báo lỗi

        output = [  # Tạo danh sách các dòng output
            f"File: {self.path}",  # Hiển thị file đang đọc
            f"Total lines: {self.total_lines}",  # Hiển thị tổng số dòng của file
        ]

        if self.start_line is not None and self.end_line is not None:  # Nếu có dữ liệu về range đã đọc
            output.append(  # Thêm thông tin range vào output
                f"Read lines: {self.start_line}-{self.end_line}"  # Ví dụ: Read lines: 100-200
            )

        output.extend([  # Thêm nội dung file vào output
            "",  # Một dòng trống
            self.content,  # Nội dung thực tế đã đọc
        ])

        if self.truncated:  # Nếu nội dung bị cắt vì max_chars
            output.extend([  # Thêm cảnh báo vào cuối output
                "",  # Một dòng trống
                "[Content truncated because max_chars was reached.]"  # Báo cho src biết nội dung đã bị cắt
            ])

        if self.has_more:  # Nếu phía sau file vẫn còn nội dung
            output.extend([  # Thêm thông báo cho src
                "",  # Một dòng trống
                "[More content is available after this section.]"  # Báo rằng src có thể đọc tiếp
            ])

        return "\n".join(output)  # Ghép toàn bộ output thành một chuỗi


class ReadFileTool(Tool):  # Khai báo ReadFileTool và kế thừa từ Tool
    tool_name = "read_file"  # Tên mà src sử dụng để gọi tool

    tool_description = (  # Mô tả chức năng của tool cho LLM
        "Read a UTF-8 text file from the src workspace. "  # Tool dùng để đọc file UTF-8
        "The path must be relative to the workspace root. "  # Path phải tính từ workspace
        "Large file can be read in sections using start_line and end_line. "  # Cho phép đọc từng đoạn của file lớn
        "The result includes total line count and whether more content is available. "  # Trả thêm metadata giúp src đọc tiếp
        "This tool cannot access file outside the workspace."  # Không được phép truy cập ngoài workspace
    )

    tool_kwargs = ReadFileToolKwargs  # Chỉ định schema tham số đầu vào

    def __init__(  # Hàm khởi tạo tool
            self,  # Instance hiện tại
            workspace_dir: str | Path,  # Workspace mà tool được phép truy cập
    ):
        self.path_guard = WorkspacePathGuard(  # Tạo bộ kiểm soát đường dẫn
            workspace_dir  # Truyền workspace vào guard
        )

    def execute(self, **kwargs) -> ToolResult:  # Hàm chính được gọi khi src sử dụng tool
        args = self.tool_kwargs(**kwargs)  # Validate kwargs và chuyển thành ReadFileToolKwargs

        if (  # Kiểm tra trường hợp end_line nhỏ hơn start_line
                args.start_line is not None  # Phải có start_line
                and args.end_line is not None  # Đồng thời phải có end_line
                and args.end_line < args.start_line  # Kiểm tra end_line có nhỏ hơn start_line không
        ):
            return ReadFileToolResult(  # Nếu range không hợp lệ thì trả lỗi
                content="end_line must be greater than or equal to start_line."  # Thông báo lỗi rõ ràng
            )

        try:  # Bắt đầu resolve đường dẫn
            file_path = self.path_guard.resolve(  # Chuyển relative path thành absolute path an toàn
                args.path  # Path src truyền vào
            )

        except WorkspacePathError as e:  # Nếu path cố thoát ra ngoài workspace
            return ReadFileToolResult(  # Trả lỗi
                content=f"Access denied: {e}"  # Báo quyền truy cập bị từ chối
            )

        if not file_path.exists():  # Kiểm tra file có tồn tại hay không
            return ReadFileToolResult(  # Nếu không tồn tại thì trả lỗi
                content=f"File does not exist: {args.path}"  # Hiển thị path không tồn tại
            )

        if not file_path.is_file():  # Kiểm tra path có thực sự là file không
            return ReadFileToolResult(  # Nếu là directory thì trả lỗi
                content=f"Path is not a file: {args.path}"  # Hiển thị path gây lỗi
            )

        try:  # Bắt đầu đếm tổng số dòng của file
            with file_path.open(  # Mở file
                    mode="r",  # Mở ở chế độ đọc
                    encoding="utf-8",  # Đọc file dưới dạng UTF-8
            ) as file:  # Gán file đang mở vào biến file
                total_lines = sum(  # Đếm tổng số dòng
                    1 for _ in file  # Mỗi dòng đọc được cộng thêm 1
                )

        except UnicodeDecodeError:  # Nếu file không phải UTF-8 hợp lệ
            return ReadFileToolResult(  # Trả lỗi
                content=(  # Nội dung lỗi
                    "Failed to read file because it is not "  # Phần đầu thông báo
                    "a valid UTF-8 text file."  # Báo file không phải UTF-8
                )
            )

        except OSError as e:  # Nếu hệ điều hành gặp lỗi khi đọc file
            return ReadFileToolResult(  # Trả lỗi
                content=f"Failed to read file: {e}"  # Hiển thị lỗi thực tế
            )

        relative_path = self.path_guard.to_relative(  # Chuyển absolute path về relative path
            file_path  # File đang được đọc
        )

        if total_lines == 0:  # Nếu file không có dòng nào
            return ReadFileToolResult(  # Trả kết quả file rỗng
                content="[File is empty.]",  # Báo file rỗng
                path=relative_path,  # Relative path của file
                total_lines=0,  # Tổng số dòng bằng 0
                has_more=False,  # Không còn nội dung phía sau
                truncated=False,  # Không bị truncate
            )

        requested_start = args.start_line or 1  # Nếu không có start_line thì bắt đầu từ dòng 1

        if requested_start > total_lines:  # Nếu src yêu cầu bắt đầu sau cả cuối file
            return ReadFileToolResult(  # Trả lỗi
                content=(  # Nội dung thông báo
                    f"start_line {requested_start} exceeds "  # Hiển thị dòng src yêu cầu
                    f"the total number of lines ({total_lines})."  # Hiển thị tổng số dòng thực tế
                )
            )

        requested_end = args.end_line or total_lines  # Nếu không có end_line thì đọc tới cuối file
        requested_end = min(  # Không cho requested_end vượt quá số dòng thực tế
            requested_end,  # Dòng cuối src yêu cầu
            total_lines,  # Dòng cuối thực tế của file
        )

        chunks: list[str] = []  # Danh sách dùng để chứa các đoạn text đã đọc
        chars_read = 0  # Đếm tổng số ký tự đã lấy
        actual_end_line: int | None = None  # Lưu dòng cuối thực tế đã đọc
        truncated = False  # Ban đầu nội dung chưa bị cắt

        try:  # Bắt đầu đọc range được yêu cầu
            with file_path.open(  # Mở file lần thứ hai để đọc nội dung
                    mode="r",  # Chế độ đọc
                    encoding="utf-8",  # Encoding UTF-8
            ) as file:  # Gán file vào biến file
                for line_number, line in enumerate(  # Duyệt từng dòng cùng số dòng
                        file,  # File đang đọc
                        start=1,  # Số dòng bắt đầu từ 1
                ):
                    if line_number < requested_start:  # Nếu chưa tới dòng bắt đầu
                        continue  # Bỏ qua dòng hiện tại

                    if line_number > requested_end:  # Nếu đã vượt quá dòng cuối cần đọc
                        break  # Dừng vòng lặp

                    remaining_chars = (  # Tính số ký tự vẫn còn được phép trả về
                            args.max_chars - chars_read  # Lấy giới hạn trừ số ký tự đã đọc
                    )

                    if remaining_chars <= 0:  # Nếu đã hết quota ký tự
                        truncated = True  # Đánh dấu nội dung bị cắt
                        break  # Dừng đọc

                    if len(line) <= remaining_chars:  # Nếu toàn bộ dòng vẫn nằm trong giới hạn
                        chunks.append(line)  # Thêm toàn bộ dòng vào kết quả
                        chars_read += len(line)  # Cộng số ký tự đã đọc
                        actual_end_line = line_number  # Cập nhật dòng cuối đã đọc

                    else:  # Nếu dòng hiện tại dài hơn số ký tự còn được phép lấy
                        chunks.append(  # Thêm một phần của dòng
                            line[:remaining_chars]  # Chỉ lấy số ký tự còn lại
                        )
                        chars_read += remaining_chars  # Cập nhật số ký tự đã đọc
                        actual_end_line = line_number  # Ghi nhận đã đọc tới dòng này
                        truncated = True  # Đánh dấu nội dung bị truncate
                        break  # Dừng đọc vì đã chạm max_chars

        except UnicodeDecodeError:  # Nếu xảy ra lỗi UTF-8 trong lúc đọc
            return ReadFileToolResult(  # Trả lỗi
                content=(  # Nội dung lỗi
                    "Failed to read file because it is not "  # Phần đầu
                    "a valid UTF-8 text file."  # Báo encoding không hợp lệ
                )
            )

        except OSError as e:  # Nếu hệ điều hành gặp lỗi khi đọc
            return ReadFileToolResult(  # Trả lỗi
                content=f"Failed to read file: {e}"  # Hiển thị lỗi thực tế
            )

        content = "".join(chunks)  # Ghép các dòng đã đọc thành một chuỗi hoàn chỉnh

        has_more = (  # Xác định phía sau còn nội dung chưa đọc hay không
                actual_end_line is not None  # Phải đọc được ít nhất một dòng
                and actual_end_line < total_lines  # Dòng cuối vừa đọc chưa phải dòng cuối file
        )

        return ReadFileToolResult(  # Trả kết quả đọc file thành công
            content=content,  # Nội dung đã đọc
            path=relative_path,  # Relative path của file
            total_lines=total_lines,  # Tổng số dòng của toàn bộ file
            start_line=requested_start,  # Dòng bắt đầu đã đọc
            end_line=actual_end_line,  # Dòng cuối thực tế đã đọc
            has_more=has_more,  # Báo phía sau có còn nội dung hay không
            truncated=truncated,  # Báo nội dung có bị cắt bởi max_chars hay không
        )
