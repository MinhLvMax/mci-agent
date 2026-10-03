import re
from dataclasses import dataclass
from pathlib import Path

from ddgs import DDGS
from pydantic import Field

from src.dom.tool import ToolKwargs, ToolResult, Tool
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError, save_text


class OpenURLToolKwargs(ToolKwargs):
    url: str = Field(
        description="The full URL of the webpage to open and extract content from."
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
        description="Page title (from the search results), written at the top of the saved file."
    )


@dataclass
class OpenURLToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class OpenURLTool(Tool):
    tool_name = "open_url"

    tool_description = (
        "Open a webpage from a URL and extract its readable text content. "
        "Use this tool when you already have a URL, usually from search results. "
        "Without save_to it returns the text (long pages in parts, use offset to read further). "
        "With save_to it saves the full text into a workspace file for later use (read_file, search_files, "
        "extract_insights) and returns only a short summary."
    )

    tool_kwargs = OpenURLToolKwargs

    PREVIEW_CHARS = 300
    MIN_SAVE_CHARS = 200  # Ít hơn mức này thường là trang lỗi, paywall hoặc chặn bot

    def __init__(self, workspace_dir: str | Path):
        self.path_guard = WorkspacePathGuard(workspace_dir)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            result = DDGS().extract(
                args.url,
                fmt="text_markdown",
            )
        except Exception as e:
            return OpenURLToolResult(
                content=f"Failed to open URL: {e}"
            )

        content = (result or {}).get("content", "")

        if not content:
            return OpenURLToolResult(
                content="Webpage opened, but no readable content was found."
            )

        if args.save_to:
            return self._save(args, content)

        total = len(content)

        if args.offset >= total:
            return OpenURLToolResult(
                content=f"Offset {args.offset} exceeds content length ({total} chars)."
            )

        end = min(args.offset + args.max_chars, total)
        part = content[args.offset:end]

        if args.offset == 0 and end == total:
            return OpenURLToolResult(
                content=part
            )

        # Trang dài: báo rõ đang đọc đoạn nào và còn tiếp hay không
        footer = (
            f"\n\n[Showing chars {args.offset}-{end} of {total}. "
            f"Call again with offset={end} to read more.]"
            if end < total
            else f"\n\n[Showing chars {args.offset}-{end} of {total}. End of page.]"
        )

        return OpenURLToolResult(
            content=part + footer
        )

    def _save(self, args: OpenURLToolKwargs, content: str) -> ToolResult:
        '''Lưu toàn văn (đã bỏ link, ảnh, chú thích) vào workspace, chỉ trả tóm tắt'''
        text = re.sub(r'\n{3,}', '\n\n', _clean_markdown(content)).strip()

        if len(text) < self.MIN_SAVE_CHARS:
            return OpenURLToolResult(
                content="The page has no readable article content (maybe blocked or paywalled). Try another URL."
            )

        title = args.title or args.url

        try:
            saved_path = save_text(
                self.path_guard,
                args.save_to,
                f"# {title}\nURL: {args.url}\n\n{text}\n",
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
                f"length: {len(text):,} chars, sentences: {len(sentences)}\n"
                f"preview: {preview}..."
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

    with tempfile.TemporaryDirectory() as workspace:
        tool = OpenURLTool(workspace_dir=workspace)
        print(tool.execute(
            url="https://vi.wikipedia.org/wiki/V%E1%BB%8Bnh_H%E1%BA%A1_Long",
            save_to="ha-long/sources/wikipedia.md",
            title="Vịnh Hạ Long – Wikipedia",
        ).to_text())
