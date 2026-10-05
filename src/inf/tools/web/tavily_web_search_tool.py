from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.web.tavily_client import TAVILY_FATAL_ERRORS, create_tavily_client

TIME_RANGE_MAP = {'d': 'day', 'w': 'week', 'm': 'month', 'y': 'year'}


class WebSearchToolKwargs(ToolKwargs):
    query: str = Field(
        min_length=1,
        max_length=400,
        description="The search query, e.g. 'Tràng An lịch sử'."
    )

    kind: Literal['web', 'news', 'both'] = Field(
        default='web',
        description=(
            "'web' for regular pages (encyclopedias, blogs, travel guides), "
            "'news' for news articles with publish date, 'both' to combine them without duplicates. "
            "'both' costs two searches, use it only when really needed."
        )
    )

    max_results: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Maximum number of results from each kind."
    )

    timelimit: Literal['d', 'w', 'm', 'y'] | None = Field(
        default=None,
        description="Only results from the last day (d), week (w), month (m) or year (y). Omit for any time."
    )

    country: str | None = Field(
        default='vietnam',
        description=(
            "Boost results from this country (full English name in lowercase, e.g. 'vietnam', "
            "'united states'). Only applies to web results. Set to null for worldwide results."
        )
    )

    include_domains: list[str] | None = Field(
        default=None,
        description="Only return results from these domains, e.g. ['vnexpress.net', 'wikipedia.org']."
    )


@dataclass
class WebSearchToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class TavilyWebSearchTool(Tool):
    tool_name = 'web_search'
    tool_description = (
        "Search the web (Tavily) for pages and/or news articles. "
        "Returns title, date, snippet and URL of each result. "
        "Use open_url to read a result, with save_to to keep its full text in the workspace."
    )

    tool_kwargs = WebSearchToolKwargs

    # Cố định ở 'basic' (1 credit/lần) để agent không tự đẩy chi phí lên 'advanced'
    search_depth: Literal['basic', 'advanced'] = 'basic'

    def __init__(self, api_key: str | None):
        self.api_key = api_key
        self.client = create_tavily_client(api_key)

    def _search(self, args: WebSearchToolKwargs, topic: Literal['general', 'news']) -> list[dict]:
        params = {
            'query': args.query,
            'topic': topic,
            'search_depth': self.search_depth,
            'max_results': args.max_results,
            'include_answer': False,
            'include_raw_content': False,
        }
        if args.timelimit:
            params['time_range'] = TIME_RANGE_MAP[args.timelimit]
        if args.include_domains:
            params['include_domains'] = args.include_domains
        if topic == 'general' and args.country:
            params['country'] = args.country  # Tavily chỉ hỗ trợ country với topic general

        response = self.client.search(**params)
        kind = 'news' if topic == 'news' else 'web'

        return [
            {
                'kind': kind,
                'title': item.get('title') or '',
                'url': item.get('url') or '',
                'body': item.get('content') or '',
                'date': item.get('published_date') or '',
            }
            for item in response.get('results', [])
        ]

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        results: list[dict] = []
        errors: list[str] = []

        topics: list[Literal['general', 'news']] = []
        if args.kind in ('news', 'both'):
            topics.append('news')
        if args.kind in ('web', 'both'):
            topics.append('general')

        for topic in topics:
            try:
                results.extend(self._search(args, topic))
            except TAVILY_FATAL_ERRORS:
                # Lỗi cấu hình/hạn mức: agent thử lại cũng vô ích, báo rõ để nó dừng
                # (nên log chi tiết ở đây cho phía vận hành)
                return WebSearchToolResult(
                    content="Web search is currently unavailable. Do not retry; continue without it."
                )
            except Exception as e:  # lỗi mạng, timeout, request không hợp lệ...
                errors.append(f"{'news' if topic == 'news' else 'web'} search failed: {e}")

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
            meta = ' | '.join(x for x in (item['kind'], item['date'][:16]) if x)
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
    from src.config import Config

    tool = TavilyWebSearchTool(api_key=Config.TAVILY_API_KEY)
    print(tool.execute(query='Tràng An Ninh Bình', kind='both', max_results=3).to_text())
