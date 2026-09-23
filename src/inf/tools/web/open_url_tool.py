from dataclasses import dataclass
from ddgs import DDGS
from pydantic import Field
from src.dom.tool import ToolKwargs, ToolResult, Tool


class OpenURLToolKwargs(ToolKwargs):
    url: str = Field(
        description="The full URL of the webpage to open and extract content from."
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
        "and need to read the actual webpage content."
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

            return OpenURLToolResult(
                content=content
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
