from dataclasses import dataclass
from ddgs import DDGS
from pydantic import Field
from src.dom.tool import ToolKwargs, ToolResult, Tool


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


@dataclass
class OpenURLToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class OpenURLTool(Tool):
    tool_name = "open_url"

    tool_description = (
        "Open a webpage from a URL and extract its readable text content. "
        "Use this tool when you already have a URL, usually from search results, "
        "and need to read the actual webpage content. "
        "Long pages are returned in parts, use offset to read further. "
        "To keep an article for research, use save_article instead."
    )

    tool_kwargs = OpenURLToolKwargs

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            result = DDGS().extract(
                args.url,
                fmt="text_markdown",
            )

            if not result:
                return OpenURLToolResult(
                    content="Failed to extract webpage content."
                )

            content = result.get("content", "")

            if not content:
                return OpenURLToolResult(
                    content="Webpage opened, but no readable content was found."
                )

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

        except Exception as e:
            return OpenURLToolResult(
                content=f"Failed to open URL: {e}"
            )


if __name__ == "__main__":
    tool = OpenURLTool()

    result = tool.execute(
        url="https://www.accuweather.com/vi/vn/hanoi/353412/hourly-weather-forecast/353412"
    )

    print(result.to_text())
