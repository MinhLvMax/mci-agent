from dataclasses import dataclass
from typing import Literal

from ddgs import DDGS
from ddgs.exceptions import DDGSException
from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult


class NewsSearchToolKwargs(ToolKwargs):
    query: str = Field(
        min_length=1,
        description="Search query, usually the place name plus a topic, e.g. 'Tràng An lịch sử'."
    )

    max_results: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Maximum number of results from each source (news and web)."
    )

    timelimit: Literal['d', 'w', 'm', 'y'] | None = Field(
        default=None,
        description="Only return results from the last day (d), week (w), month (m) or year (y). Omit for any time."
    )

    region: str = Field(
        default='vn-vi',
        description="Search region, e.g. 'vn-vi' for Vietnamese results, 'wt-wt' for worldwide."
    )

    include_web: bool = Field(
        default=True,
        description="Also include regular web results (blogs, encyclopedias, travel guides), not only news."
    )


@dataclass
class NewsSearchToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class NewsSearchTool(Tool):
    tool_name = 'news_search'
    tool_description = (
        "Search news articles (and optionally web pages) about a place or topic. "
        "Returns title, source, date, snippet and URL of each article, without duplicates. "
        "Use save_article with a URL to store a relevant article into the research project."
    )

    tool_kwargs = NewsSearchToolKwargs

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        results: list[dict] = []
        errors: list[str] = []

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

        if args.include_web:
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

        seen: set[str] = set()
        unique = []
        for item in results:
            url = item['url'].rstrip('/')
            if url and url not in seen:
                seen.add(url)
                unique.append(item)

        if not unique:
            return NewsSearchToolResult(
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

        return NewsSearchToolResult(
            content="\n\n".join(output)
        )


if __name__ == '__main__':
    tool = NewsSearchTool()
    print(tool.execute(query='Tràng An Ninh Bình', max_results=5).to_text())
