from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ddgs import DDGS
from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.research.project_store import ResearchProjectStore, ResearchProjectError
from src.inf.tools.research.text_utils import place_terms, relevance_filter, split_sentences


class SaveArticleToolKwargs(ToolKwargs):
    project: str | None = Field(
        default=None,
        description=(
            "Research project slug returned by start_research_project. "
            "Can be omitted when the workspace has only one research project."
        )
    )

    place: str = Field(
        description="The place (địa danh) of the project that this article is about."
    )

    url: str = Field(
        description="Full URL of the article to save."
    )

    title: str | None = Field(
        default=None,
        description="Article title from the search results, used as the label of the source. Recommended."
    )


@dataclass
class SaveArticleToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class SaveArticleTool(Tool):
    tool_name = 'save_article'
    tool_description = (
        "Download an article (news, blog, encyclopedia page...) and save its readable text into the research "
        "project (research/<project>/raw/articles/) as a source of the given place. "
        "Returns only a short preview and how many sentences mention the place, not the full text. "
        "Run extract_insights afterwards to filter useful information from saved articles."
    )

    tool_kwargs = SaveArticleToolKwargs

    PREVIEW_CHARS = 300
    MIN_CONTENT_CHARS = 200  # Ít hơn mức này thường là trang lỗi, paywall hoặc chặn bot

    def __init__(self, workspace_dir: str | Path):
        self.store = ResearchProjectStore(workspace_dir)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            project = self.store.load_project(args.project)
            place = self.store.find_place(project, args.place)
        except ResearchProjectError as e:
            return SaveArticleToolResult(content=str(e))

        try:
            result = DDGS().extract(args.url, fmt="text_markdown") or {}
        except Exception as e:
            return SaveArticleToolResult(content=f"Failed to open URL: {e}")

        content = (result.get('content') or '').strip()

        if len(content) < self.MIN_CONTENT_CHARS:
            return SaveArticleToolResult(
                content="The page has no readable article content (maybe blocked or paywalled). Try another URL."
            )

        source_id = self.store.article_id(args.url)
        title = args.title or args.url

        file_path = self.store.write_raw(
            project['slug'],
            kind='articles',
            name=source_id,
            content=f"# {title}\nURL: {args.url}\n---\n{content}\n",
        )

        is_new = self.store.upsert_source(project['slug'], {
            'id': source_id,
            'type': 'article',
            'place': place,
            'url': args.url,
            'title': title,
            'saved_at': datetime.now().isoformat(timespec='seconds'),
            'file': file_path,
            'extracted': False,
        })

        sentences = split_sentences(content)
        relevant = relevance_filter(sentences, place_terms(place), window=0)
        # Preview lấy từ các câu thật, bỏ qua menu/điều hướng ở đầu trang
        prose = [s for s in (relevant or sentences) if len(s.text) >= 60 and s.text[-1] in '.!?…"”']
        preview = ' '.join(s.text for s in (prose or sentences)[:3])[:self.PREVIEW_CHARS]

        return SaveArticleToolResult(
            content=(
                f"{'Saved' if is_new else 'Updated'} article '{title}'.\n"
                f"source_id: {source_id}\n"
                f"file: {file_path}\n"
                f"length: {len(content):,} chars, sentences: {len(sentences)}, "
                f"sentences mentioning '{place}': {len(relevant)}\n"
                f"preview: {preview}..."
            )
        )


if __name__ == '__main__':
    import tempfile
    from src.inf.tools.research.start_project_tool import StartResearchProjectTool

    with tempfile.TemporaryDirectory() as workspace:
        StartResearchProjectTool(workspace).execute(title='Test', places=['Tràng An'])
        tool = SaveArticleTool(workspace_dir=workspace)
        print(tool.execute(
            project='test',
            place='Tràng An',
            url='https://vi.wikipedia.org/wiki/Qu%E1%BA%A7n_th%E1%BB%83_danh_th%E1%BA%AFng_Tr%C3%A0ng_An',
        ).to_text())
