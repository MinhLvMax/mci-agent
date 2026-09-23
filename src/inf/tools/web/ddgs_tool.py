from dataclasses import dataclass
from pydantic import Field
from ddgs import DDGS
from ddgs.exceptions import DDGSException
from src.dom.tool import ToolKwargs, ToolResult, Tool


class DDGSToolKwargs(ToolKwargs):
    query: str = Field(
        description="The search query to search on the web."
    )

@dataclass
class DDGSToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class DDGSTool(Tool):
    tool_name = 'ddgs'
    tool_description = (
        "Search the web using DuckDuckGo and return "
        "relevant search results."
    )

    tool_kwargs = DDGSToolKwargs

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            results = DDGS().text(
                args.query,
                region="vn-vi",
                max_results=5,
            )

        except DDGSException as e:
            return DDGSToolResult(
                content=f"Search failed: {e}"
            )

        if not results:
            return DDGSToolResult(
                content="No search results found."
            )

        output = []

        for i, result in enumerate(results, 1):
            output.append(
                f"{i}. {result.get('title', '')}\n"
                f"{result.get('body', '')}\n"
                f"URL: {result.get('href', '')}"
            )

        return DDGSToolResult(
            content="\n\n".join(output)
        )

if __name__ == '__main__':
    tool = DDGSTool()
    result = tool.execute(query='Thời tiết Hà Nội hôm nay')
    print(result.to_text())