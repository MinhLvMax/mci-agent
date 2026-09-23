from dataclasses import dataclass  # Import dataclass để tạo class kết quả gọn hơn
from pathlib import Path  # Import Path để xử lý đường dẫn file và thư mục

from pydantic import Field  # Import Field để khai báo và mô tả tham số đầu vào của tool

from src.dom.tool import (  # Import các class nền tảng của hệ thống tool
    Tool,  # Class cha của tất cả các tool
    ToolKwargs,  # Class cha dùng để định nghĩa tham số đầu vào của tool
    ToolResult,  # Class cha dùng để định nghĩa kết quả trả về của tool
)
from src.inf.tools.file.helper import (  # Import helper dùng để bảo vệ workspace
    WorkspacePathGuard,  # Class kiểm tra đường dẫn có nằm trong workspace hay không
    WorkspacePathError,  # Exception được ném ra khi đường dẫn cố thoát khỏi workspace
)


class SearchFilesToolKwargs(ToolKwargs):  # Khai báo các tham số đầu vào mà src được phép truyền vào tool
    query: str = Field(  # Chuỗi nội dung mà src muốn tìm kiếm
        min_length=1,  # Không cho phép query rỗng
        description=(  # Mô tả cho LLM biết query dùng để làm gì
            "Text to search for inside file in the workspace. "  # Nội dung cần tìm trong các file
            "The search is case-insensitive by default."  # Mặc định không phân biệt chữ hoa chữ thường
        )
    )

    path: str = Field(  # Thư mục bắt đầu tìm kiếm
        default="",  # Mặc định tìm từ thư mục gốc workspace
        description=(  # Mô tả cách sử dụng path
            "Directory to search inside, relative to the workspace root. "  # Path phải tính từ workspace
            "Use an empty string to search the entire workspace. "  # Chuỗi rỗng nghĩa là tìm toàn bộ workspace
            "Examples: '', 'characters', 'research'."  # Một số ví dụ hợp lệ
        )
    )

    extensions: list[str] | None = Field(  # Danh sách phần mở rộng file được phép tìm
        default=None,  # None nghĩa là tìm trong tất cả file text có thể đọc được
        description=(  # Mô tả cho LLM cách lọc extension
            "Optional list of file extensions to search. "  # Có thể giới hạn loại file cần tìm
            "Examples: ['.txt', '.md', '.json']. "  # Ví dụ các extension hợp lệ
            "If omitted, all readable UTF-8 text file are searched."  # Nếu không truyền thì thử đọc tất cả file text UTF-8
        )
    )

    case_sensitive: bool = Field(  # Xác định có phân biệt chữ hoa chữ thường hay không
        default=False,  # Mặc định không phân biệt hoa thường
        description=(  # Mô tả ý nghĩa của case_sensitive
            "If true, search is case-sensitive. "  # True thì 'Lion' khác 'lion'
            "If false, uppercase and lowercase letters are treated as equal."  # False thì coi chúng giống nhau
        )
    )

    max_results: int = Field(  # Giới hạn số lượng kết quả trả về
        default=50,  # Mặc định tối đa 50 kết quả
        ge=1,  # Không cho phép nhỏ hơn 1
        le=500,  # Không cho phép lớn hơn 500 để tránh output quá dài
        description=(  # Mô tả mục đích của max_results
            "Maximum number of matching lines to return."  # Số dòng match tối đa được trả về
        )
    )

    max_line_chars: int = Field(  # Giới hạn độ dài mỗi dòng kết quả
        default=500,  # Mặc định mỗi dòng chỉ hiển thị tối đa 500 ký tự
        ge=50,  # Tối thiểu 50 ký tự
        le=2000,  # Tối đa 2000 ký tự
        description=(  # Mô tả mục đích của max_line_chars
            "Maximum number of characters to include from each matching line."  # Giới hạn chiều dài snippet của dòng match
        )
    )


@dataclass  # Tự động tạo __init__ và các method tiện ích cho class
class SearchFilesToolResult(ToolResult):  # Class chứa kết quả của SearchFilesTool
    content: str  # Nội dung kết quả tìm kiếm hoặc thông báo lỗi
    query: str | None = None  # Query đã được tìm, None nếu xảy ra lỗi trước khi search
    truncated: bool = False  # Cho biết kết quả có bị cắt vì đạt max_results hay không

    def to_text(self) -> str:  # Chuyển kết quả thành chuỗi để src đọc
        if self.query is None:  # Nếu không có query thì thường là trường hợp lỗi
            return self.content  # Trả thẳng nội dung lỗi

        output = [  # Tạo danh sách các dòng output
            f"Search query: {self.query}",  # Hiển thị query vừa được tìm
            "",  # Thêm một dòng trống
            self.content,  # Thêm danh sách kết quả tìm được
        ]

        if self.truncated:  # Nếu số lượng kết quả vượt quá max_results
            output.extend([  # Thêm cảnh báo vào cuối output
                "",  # Thêm một dòng trống
                "[Results truncated because max_results was reached.]"  # Báo src rằng vẫn còn kết quả chưa được hiển thị
            ])

        return "\n".join(output)  # Ghép toàn bộ danh sách thành một chuỗi nhiều dòng


class SearchFilesTool(Tool):  # Khai báo tool search_files và kế thừa từ Tool
    tool_name = "search_files"  # Tên mà src sẽ dùng để gọi tool

    tool_description = (  # Mô tả chức năng của tool cho LLM
        "Search for text inside UTF-8 file in the src workspace. "  # Tool dùng để tìm nội dung trong file text
        "The search can be limited to a directory or specific file extensions. "  # Có thể giới hạn folder hoặc extension
        "Results include the relative file path, line number, and matching line. "  # Kết quả có path, số dòng và nội dung match
        "This tool cannot search file outside the workspace."  # Không được phép tìm bên ngoài workspace
    )

    tool_kwargs = SearchFilesToolKwargs  # Chỉ định schema tham số đầu vào của tool

    def __init__(  # Hàm khởi tạo SearchFilesTool
            self,  # Instance hiện tại của tool
            workspace_dir: str | Path,  # Workspace mà tool được phép truy cập
    ):
        self.path_guard = WorkspacePathGuard(  # Tạo bộ bảo vệ đường dẫn
            workspace_dir  # Truyền workspace vào guard
        )

    def execute(self, **kwargs) -> ToolResult:  # Hàm chính được gọi khi src sử dụng tool
        args = self.tool_kwargs(**kwargs)  # Validate kwargs và chuyển thành SearchFilesToolKwargs

        try:  # Thử resolve thư mục bắt đầu tìm kiếm
            search_path = self.path_guard.resolve(  # Chuyển relative path thành absolute path an toàn
                args.path  # Path mà src truyền vào
            )

        except WorkspacePathError as e:  # Nếu path cố thoát khỏi workspace
            return SearchFilesToolResult(  # Trả về kết quả lỗi
                content=f"Access denied: {e}"  # Báo rằng quyền truy cập bị từ chối
            )

        if not search_path.exists():  # Kiểm tra đường dẫn tìm kiếm có tồn tại hay không
            return SearchFilesToolResult(  # Nếu không tồn tại thì trả lỗi
                content=(  # Tạo nội dung lỗi
                    f"Search path does not exist: "  # Phần đầu thông báo
                    f"{args.path}"  # Hiển thị path mà src đã truyền
                )
            )

        if not search_path.is_dir():  # Kiểm tra path có phải thư mục hay không
            return SearchFilesToolResult(  # Nếu là file thì trả lỗi
                content=(  # Tạo thông báo lỗi
                    f"Search path is not a directory: "  # Báo rằng path không phải folder
                    f"{args.path}"  # Hiển thị path gây lỗi
                )
            )

        normalized_extensions: set[str] | None = None  # Ban đầu chưa có bộ lọc extension

        if args.extensions is not None:  # Nếu src có truyền danh sách extension
            normalized_extensions = set()  # Tạo set để lưu extension đã chuẩn hóa

            for extension in args.extensions:  # Duyệt từng extension được truyền vào
                extension = extension.strip().lower()  # Xóa khoảng trắng và chuyển về chữ thường

                if not extension.startswith("."):  # Nếu extension chưa có dấu chấm ở đầu
                    extension = f".{extension}"  # Tự động thêm dấu chấm, ví dụ json thành .json

                normalized_extensions.add(extension)  # Thêm extension đã chuẩn hóa vào set

        if args.case_sensitive:  # Nếu yêu cầu phân biệt chữ hoa chữ thường
            search_query = args.query  # Giữ nguyên query
        else:  # Nếu không phân biệt chữ hoa chữ thường
            search_query = args.query.lower()  # Chuyển query về chữ thường để so sánh

        results: list[str] = []  # Tạo danh sách chứa các kết quả tìm được
        truncated = False  # Ban đầu mặc định kết quả chưa bị cắt

        try:  # Bắt đầu quá trình duyệt file trong workspace
            entries = search_path.rglob("*")  # Duyệt đệ quy tất cả item bên trong thư mục search

            for entry in entries:  # Duyệt từng item tìm được
                if not entry.is_file():  # Nếu item không phải file
                    continue  # Bỏ qua và chuyển sang item tiếp theo

                try:  # Kiểm tra file có thực sự an toàn hay không
                    relative_entry = entry.relative_to(  # Chuyển file thành relative path
                        self.path_guard.workspace_dir  # Relative so với workspace root
                    )

                    safe_entry = self.path_guard.resolve(  # Resolve lại file qua WorkspacePathGuard
                        str(relative_entry)  # Chuyển Path thành string để truyền vào guard
                    )

                except (  # Bắt các lỗi nếu file không nằm an toàn trong workspace
                    ValueError,  # Có thể xảy ra nếu path không relative được với workspace
                    WorkspacePathError,  # Xảy ra nếu resolve ra ngoài workspace
                ):
                    continue  # Bỏ qua file không an toàn

                if normalized_extensions is not None:  # Nếu có bộ lọc extension
                    if safe_entry.suffix.lower() not in normalized_extensions:  # Nếu extension file không nằm trong danh sách cho phép
                        continue  # Bỏ qua file này

                try:  # Thử đọc nội dung file
                    content = safe_entry.read_text(  # Đọc toàn bộ file thành string
                        encoding="utf-8"  # Chỉ đọc file theo encoding UTF-8
                    )

                except UnicodeDecodeError:  # Nếu file không phải text UTF-8
                    continue  # Bỏ qua file nhị phân hoặc encoding khác

                except OSError:  # Nếu xảy ra lỗi hệ điều hành khi đọc file
                    continue  # Bỏ qua file lỗi và tiếp tục tìm trong file khác

                lines = content.splitlines()  # Tách nội dung file thành danh sách từng dòng

                for line_number, line in enumerate(  # Duyệt từng dòng của file kèm số thứ tự
                        lines,  # Danh sách các dòng trong file
                        start=1,  # Số dòng bắt đầu từ 1 thay vì 0
                ):
                    if args.case_sensitive:  # Nếu tìm kiếm phân biệt hoa thường
                        line_to_search = line  # Giữ nguyên nội dung dòng
                    else:  # Nếu không phân biệt hoa thường
                        line_to_search = line.lower()  # Chuyển dòng về chữ thường để so sánh

                    if search_query not in line_to_search:  # Nếu query không xuất hiện trong dòng này
                        continue  # Bỏ qua và kiểm tra dòng tiếp theo

                    display_line = line.strip()  # Xóa khoảng trắng thừa ở đầu và cuối dòng

                    if len(display_line) > args.max_line_chars:  # Nếu dòng quá dài
                        display_line = (  # Cắt bớt nội dung hiển thị
                            display_line[:args.max_line_chars]  # Chỉ giữ số ký tự tối đa được cho phép
                            + "..."  # Thêm dấu ... để báo rằng dòng đã bị cắt
                        )

                    results.append(  # Thêm kết quả match vào danh sách
                        f"{relative_entry}:{line_number}: {display_line}"  # Ví dụ characters/lion.json:12: cave lion...
                    )

                    if len(results) >= args.max_results:  # Nếu đã đạt số lượng kết quả tối đa
                        truncated = True  # Đánh dấu rằng kết quả đã bị cắt
                        break  # Dừng duyệt các dòng của file hiện tại

                if truncated:  # Nếu đã đạt max_results
                    break  # Dừng luôn việc duyệt các file còn lại

        except OSError as e:  # Bắt lỗi nếu không thể duyệt thư mục
            return SearchFilesToolResult(  # Trả về kết quả lỗi
                content=f"Failed to search file: {e}"  # Hiển thị lỗi thực tế
            )

        if not results:  # Nếu không tìm thấy bất kỳ kết quả nào
            content = "[No matches found.]"  # Trả thông báo không có kết quả

        else:  # Nếu có kết quả
            content = "\n".join(results)  # Ghép toàn bộ kết quả thành chuỗi nhiều dòng

        return SearchFilesToolResult(  # Trả kết quả tìm kiếm thành công
            query=args.query,  # Trả lại query đã tìm
            content=content,  # Danh sách kết quả tìm được
            truncated=truncated,  # Cho biết kết quả có bị cắt hay không
        )