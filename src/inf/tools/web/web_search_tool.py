from dataclasses import dataclass
from typing import Literal

from ddgs import DDGS
from ddgs.exceptions import DDGSException
from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult


class WebSearchToolKwargs(ToolKwargs):
    query: str = Field(
        min_length=1,
        description="The search query, e.g. 'Tràng An lịch sử'."
    )

    kind: Literal['web', 'news', 'both'] = Field(
        default='web',
        description=(
            "'web' for regular pages (encyclopedias, blogs, travel guides), "
            "'news' for news articles with source and date, 'both' to combine them without duplicates."
        )
    )

    max_results: int = Field(
        default=8,
        ge=1,
        le=30,
        description="Maximum number of results from each kind."
    )

    timelimit: Literal['d', 'w', 'm', 'y'] | None = Field(
        default=None,
        description="Only results from the last day (d), week (w), month (m) or year (y). Omit for any time."
    )

    region: str = Field(
        default='vn-vi',
        description="Search region, e.g. 'vn-vi' for Vietnamese results, 'wt-wt' for worldwide."
    )


@dataclass
class WebSearchToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class WebSearchTool(Tool):
    tool_name = 'web_search'
    tool_description = (
        "Search the web (DuckDuckGo) for pages and/or news articles. "
        "Returns title, source, date, snippet and URL of each result. "
        "Use open_url to read a result, with save_to to keep its full text in the workspace."
    )

    tool_kwargs = WebSearchToolKwargs

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        results: list[dict] = []
        errors: list[str] = []

        if args.kind in ('news', 'both'):
            try:
                for item in DDGS().news(
                        args.query,
                        region=args.region,
                        timelimit=args.timelimit,
                        max_results=args.max_results,
                ) or []:
                    results.append({
                        'kind': 'news',
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'body': item.get('body', ''),
                        'date': item.get('date', ''),
                        'source': item.get('source', ''),
                    })
            except DDGSException as e:
                errors.append(f"news search failed: {e}")

        if args.kind in ('web', 'both'):
            try:
                for item in DDGS().text(
                        args.query,
                        region=args.region,
                        timelimit=args.timelimit,
                        max_results=args.max_results,
                ) or []:
                    results.append({
                        'kind': 'web',
                        'title': item.get('title', ''),
                        'url': item.get('href', ''),
                        'body': item.get('body', ''),
                        'date': '',
                        'source': '',
                    })
            except DDGSException as e:
                errors.append(f"web search failed: {e}")

        # Cùng một trang có thể xuất hiện ở cả tin tức lẫn web
        seen: set[str] = set()
        unique = []
        for item in results:
            url = item['url'].rstrip('/')
            if url and url not in seen:
                seen.add(url)
                unique.append(item)

        if not unique:
            return WebSearchToolResult(
                content="No results found." + (f" ({'; '.join(errors)})" if errors else "")
            )

        output = []
        for i, item in enumerate(unique, 1):
            meta = ' | '.join(x for x in (item['kind'], item['source'], item['date'][:10]) if x)
            output.append(
                f"{i}. {item['title']}\n"
                f"[{meta}] {item['body']}\n"
                f"URL: {item['url']}"
            )

        if errors:
            output.append(f"Warnings: {'; '.join(errors)}")

        return WebSearchToolResult(
            content="\n\n".join(output)
        )


if __name__ == '__main__':
    tool = WebSearchTool()
    print(tool.execute(query='Tràng An Ninh Bình', kind='both', max_results=3).to_text())
