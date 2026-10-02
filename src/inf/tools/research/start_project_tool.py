from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.research.project_store import ResearchProjectStore


class StartResearchProjectToolKwargs(ToolKwargs):
    title: str = Field(
        min_length=1,
        description="Title of the content piece being researched, e.g. 'Những kỳ quan thiên nhiên miền Bắc'."
    )

    places: list[str] = Field(
        min_length=1,
        description="List of places (địa danh) covered by the content, e.g. ['Vịnh Hạ Long', 'Sa Pa']."
    )

    keywords: list[str] = Field(
        default_factory=list,
        description="Optional extra keywords that the content focuses on, e.g. ['kỳ quan', 'thiên nhiên']."
    )


@dataclass
class StartResearchProjectToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class StartResearchProjectTool(Tool):
    tool_name = 'start_research_project'
    tool_description = (
        "Create (or extend) a research project for a content title and its list of places. "
        "All research data (YouTube transcripts, articles, extracted insights, reports) is stored "
        "under research/<project>/ in the workspace. Returns the project slug that the other research "
        "tools take as the 'project' argument. Calling it again with the same title adds new places/keywords."
    )

    tool_kwargs = StartResearchProjectToolKwargs

    def __init__(self, workspace_dir: str | Path):
        self.store = ResearchProjectStore(workspace_dir)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        project, is_new = self.store.create_project(
            title=args.title,
            places=args.places,
            keywords=args.keywords,
        )

        status = 'Created' if is_new else 'Updated existing'
        sources = self.store.load_sources(project['slug'])

        return StartResearchProjectToolResult(
            content=(
                f"{status} research project.\n"
                f"project: {project['slug']}\n"
                f"title: {project['title']}\n"
                f"places: {', '.join(project['places'])}\n"
                f"keywords: {', '.join(project['keywords']) or '(none)'}\n"
                f"sources collected so far: {len(sources)}\n"
                f"folder: {self.store.relative(self.store.project_dir(project['slug']))}"
            )
        )


if __name__ == '__main__':
    import tempfile

    with tempfile.TemporaryDirectory() as workspace:
        tool = StartResearchProjectTool(workspace_dir=workspace)
        print(tool.execute(
            title='Những kỳ quan thiên nhiên miền Bắc',
            places=['Vịnh Hạ Long', 'Sa Pa', 'Tràng An'],
            keywords=['kỳ quan'],
        ).to_text())
