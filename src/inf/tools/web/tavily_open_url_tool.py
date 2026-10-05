import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field

from src.dom.tool import ToolKwargs, ToolResult, Tool
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError, save_text
from src.inf.tools.web.tavily_client import TAVILY_FATAL_ERRORS, create_tavily_client

# Các trang mà điều khoản dịch vụ không cho phép lấy nội dung tự động.
# YouTube: dùng YouTube Data API (tool riêng) thay vì trích trang.
BLOCKED_DOMAINS: dict[str, str] = {
    'youtube.com': "YouTube pages cannot be opened. Use the youtube_transcript tool for video content.",
    'youtu.be': "YouTube pages cannot be opened. Use the youtube_transcript tool for video content.",
}

# Hậu tố tên miền nội bộ, không bao giờ là trang công khai
INTERNAL_SUFFIXES = ('.local', '.localhost', '.internal', '.lan', '.home', '.corp')


class URLNotAllowed(ValueError):
    pass


def validate_url(url: str) -> str:
    '''Chỉ cho phép URL http(s) công khai; trả về URL đã chuẩn hóa hoặc ném URLNotAllowed'''
    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme not in ('http', 'https'):
        raise URLNotAllowed("Only http and https URLs are supported.")

    if parsed.username or parsed.password:
        raise URLNotAllowed("URLs containing login credentials are not allowed.")

    host = (parsed.hostname or '').lower().rstrip('.')
    if not host:
        raise URLNotAllowed("The URL has no host name.")

    if host == 'localhost' or host.endswith(INTERNAL_SUFFIXES) or '.' not in host:
        raise URLNotAllowed("Internal or local addresses cannot be opened.")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None  # Không phải IP, là tên miền

    # Raise ngoài try vì URLNotAllowed là con của ValueError, để trong try sẽ bị nuốt mất
    if ip is not None and not ip.is_global:
        raise URLNotAllowed("Private or reserved IP addresses cannot be opened.")

    for domain, message in BLOCKED_DOMAINS.items():
        if host == domain or host.endswith('.' + domain):
            raise URLNotAllowed(message)

    return url


class OpenURLToolKwargs(ToolKwargs):
    url: str = Field(
        max_length=2048,
        description="The full URL (http or https) of the webpage to open and extract content from."
    )

    max_chars: int = Field(
        default=15_000,
        ge=1,
        le=50_000,
        description="Maximum number of characters to return. Long pages are cut at this limit."
    )

    offset: int = Field(
        default=0,
        ge=0,
        description=(
            "Character offset to start reading from. "
            "Use it to read the next part of a long page."
        )
    )

    save_to: str | None = Field(
        default=None,
        description=(
            "Optional workspace path to save the full page text instead of returning it, "
            "e.g. 'ha-long/sources/wikipedia.md'. Missing folders are created, an existing file is replaced. "
            "Only a short summary is returned, so long articles do not fill the conversation."
        )
    )

    title: str | None = Field(
        default=None,
        max_length=300,
        description="Page title (from the search results), written at the top of the saved file."
    )


@dataclass
class OpenURLToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class TavilyOpenURLTool(Tool):
    tool_name = "open_url"

    tool_description = (
        "Open a public webpage from a URL and extract its readable text content. "
        "Use this tool when you already have a URL, usually from search results. "
        "Without save_to it returns the text (long pages in parts, use offset to read further). "
        "With save_to it saves the full text into a workspace file for later use (read_file, search_files, "
        "extract_insights) and returns only a short summary. "
        "Some sites (e.g. YouTube) are not supported."
    )

    tool_kwargs = OpenURLToolKwargs

    PREVIEW_CHARS = 300
    MIN_SAVE_CHARS = 200  # Ít hơn mức này thường là trang lỗi, paywall hoặc chặn bot
    MAX_SAVE_CHARS = 500_000  # Giới hạn dung lượng một file nguồn trong workspace

    # 'basic' rẻ hơn; 'advanced' tốn gấp đôi credit, chỉ bật nếu cần bảng/nội dung nhúng
    extract_depth: Literal['basic', 'advanced'] = 'basic'

    def __init__(self, workspace_dir: str | Path, api_key: str | None):
        self.path_guard = WorkspacePathGuard(workspace_dir)
        self.api_key = api_key

    def _extract(self, url: str) -> str:
        '''Gọi Tavily Extract, trả về markdown của trang hoặc ném RuntimeError'''
        response = create_tavily_client(self.api_key).extract(
            urls=[url],
            extract_depth=self.extract_depth,
            format='markdown',
            include_images=False,
            timeout=30,
        )

        results = response.get('results') or []
        if results:
            return results[0].get('raw_content') or ''

        failed = response.get('failed_results') or []
        reason = failed[0].get('error') if failed else None
        raise RuntimeError(reason or "the page could not be extracted")

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            url = validate_url(args.url)
        except URLNotAllowed as e:
            return OpenURLToolResult(content=f"Cannot open this URL: {e}")

        try:
            content = self._extract(url)
        except TAVILY_FATAL_ERRORS:
            # Nên log chi tiết ở đây cho phía vận hành
            return OpenURLToolResult(
                content="Opening webpages is currently unavailable. Do not retry; continue without it."
            )
        except Exception as e:  # trang lỗi, timeout, bị chặn...
            return OpenURLToolResult(content=f"Failed to open URL: {e}")

        if not content.strip():
            return OpenURLToolResult(
                content="Webpage opened, but no readable content was found."
            )

        if args.save_to:
            return self._save(args, url, content)

        total = len(content)

        if args.offset >= total:
            return OpenURLToolResult(
                content=f"Offset {args.offset} exceeds content length ({total} chars)."
            )

        end = min(args.offset + args.max_chars, total)
        part = content[args.offset:end]

        if args.offset == 0 and end == total:
            return OpenURLToolResult(content=part)

        # Trang dài: báo rõ đang đọc đoạn nào và còn tiếp hay không
        footer = (
            f"\n\n[Showing chars {args.offset}-{end} of {total}. "
            f"Call again with offset={end} to read more.]"
            if end < total
            else f"\n\n[Showing chars {args.offset}-{end} of {total}. End of page.]"
        )

        return OpenURLToolResult(content=part + footer)

    def _save(self, args: OpenURLToolKwargs, url: str, content: str) -> ToolResult:
        '''Lưu toàn văn (đã bỏ link, ảnh, chú thích) vào workspace, chỉ trả tóm tắt'''
        text = re.sub(r'\n{3,}', '\n\n', _clean_markdown(content)).strip()

        if len(text) < self.MIN_SAVE_CHARS:
            return OpenURLToolResult(
                content="The page has no readable article content (maybe blocked or paywalled). Try another URL."
            )

        truncated = len(text) > self.MAX_SAVE_CHARS
        if truncated:
            text = text[:self.MAX_SAVE_CHARS]

        title = (args.title or url).replace('\n', ' ').strip()

        try:
            saved_path = save_text(
                self.path_guard,
                args.save_to,
                f"# {title}\nURL: {url}\n\n{text}\n",
            )
        except WorkspacePathError as e:
            return OpenURLToolResult(content=f"Cannot save to '{args.save_to}': {e}")

        # Preview lấy từ các câu văn thật, bỏ qua menu/điều hướng ở đầu trang
        sentences = _split_sentences(text)
        prose = [s for s in sentences if len(s) >= 60 and s[-1] in '.!?…"”']
        preview = ' '.join((prose or sentences)[:3])[:self.PREVIEW_CHARS]

        return OpenURLToolResult(
            content=(
                f"Saved '{title}' to {saved_path}\n"
                f"length: {len(text):,} chars, sentences: {len(sentences)}"
                + (f" (truncated at {self.MAX_SAVE_CHARS:,} chars)" if truncated else "")
                + f"\npreview: {preview}..."
            )
        )


_SENTENCE_END = re.compile(r'(?<=[.!?…])\s+(?=[\"“\'(\[]?[A-ZÀ-Ỹ0-9])')


def _clean_markdown(text: str) -> str:
    '''Bỏ link, ảnh, chú thích [1] của markdown trích từ web, chỉ giữ chữ'''
    text = re.sub(r'^\s*\[\d+\]:\s*\S+.*$', '', text, flags=re.MULTILINE)  # Dòng định nghĩa link [1]: http...
    text = re.sub(r'!\[[^\]]*\]\[\d+\]|!\[[^\]]*\]\([^)]*\)', '', text)  # Ảnh
    text = re.sub(r'\[\s*([^\]]*?)\s*\]\[\d+\]', r'\1', text)  # [chữ][12] -> chữ
    text = re.sub(r'\[\s*([^\]]*?)\s*\]\([^)]*\)', r'\1', text)  # [chữ](url) -> chữ
    text = re.sub(r'\[\d+\]', '', text)  # Chú thích kiểu Wikipedia [5]
    return text


def _split_sentences(text: str) -> list[str]:
    '''Tách câu để làm preview: bỏ dòng quá ngắn (menu, tiêu đề mục), tách theo dấu kết thúc câu'''
    sentences = []

    for line in text.splitlines():
        line = line.strip().lstrip('#>*- ').strip()
        if len(line) < 20:
            continue
        sentences += [s.strip() for s in _SENTENCE_END.split(line) if len(s.strip()) >= 20]

    return sentences


if __name__ == "__main__":
    import tempfile
    from src.config import Config

    with tempfile.TemporaryDirectory() as workspace:
        tool = TavilyOpenURLTool(workspace_dir=workspace, api_key=Config.TAVILY_API_KEY)
        print(tool.execute(
            url="https://vi.wikipedia.org/wiki/V%E1%BB%8Bnh_H%E1%BA%A1_Long",
            save_to="ha-long/sources/wikipedia.md",
            title="Vịnh Hạ Long – Wikipedia",
        ).to_text())
        print(tool.execute(url="http://127.0.0.1:8000/admin").to_text())
        print(tool.execute(url="https://www.youtube.com/watch?v=abc").to_text())
