from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.research.project_store import (
    CATEGORIES,
    ResearchProjectStore,
    ResearchProjectError,
    youtube_link,
)
from src.inf.tools.research.text_utils import format_timestamp, strip_accents


class BuildResearchReportToolKwargs(ToolKwargs):
    project: str | None = Field(
        default=None,
        description=(
            "Research project slug returned by start_research_project. "
            "Can be omitted when the workspace has only one research project."
        )
    )

    max_per_category: int = Field(
        default=15,
        ge=1,
        le=200,
        description="Maximum number of insights listed per group for each place."
    )


@dataclass
class BuildResearchReportToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class BuildResearchReportTool(Tool):
    tool_name = 'build_research_report'
    tool_description = (
        "Compile everything collected in a research project into one Markdown brief for writers: "
        "for each place its sources and insights grouped into the 4 groups (with links to the source and "
        "video timestamp), followed by the unique stories if find_unique_stories has been run. "
        "Writes research/<project>/report.md and returns only a summary."
    )

    tool_kwargs = BuildResearchReportToolKwargs

    def __init__(self, workspace_dir: str | Path):
        self.store = ResearchProjectStore(workspace_dir)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            project = self.store.load_project(args.project)
        except ResearchProjectError as e:
            return BuildResearchReportToolResult(content=str(e))

        slug = project['slug']
        sources = self.store.load_sources(slug)
        source_map = {s['id']: s for s in sources}

        lines = [
            f"# Research brief — {project['title']}",
            "",
            f"- **Địa danh:** {', '.join(project['places'])}",
            f"- **Từ khoá:** {', '.join(project.get('keywords', [])) or '(không có)'}",
            f"- **Số nguồn:** {len(sources)} "
            f"({sum(s['type'] == 'youtube' for s in sources)} video, {sum(s['type'] == 'article' for s in sources)} bài viết)",
            f"- **Ngày tổng hợp:** {date.today().isoformat()}",
            "",
        ]
        summary = []

        for place in project['places']:
            insights = self.store.read_insights(slug, place)
            place_sources = [s for s in sources if strip_accents(s.get('place', '')) == strip_accents(place)]
            summary.append(f"- {place}: {len(place_sources)} sources, {len(insights)} insights")

            lines += [f"## {place}", "", "### Nguồn"]
            for source in place_sources:
                extra = f" — {source['views']:,} views" if source.get('views') else ""
                lines.append(f"- [{source['title']}]({source['url']}) ({source['type']}{extra})")
            if not place_sources:
                lines.append("- (chưa có nguồn)")

            for category, label in CATEGORIES.items():
                items = [i for i in insights if i['category'] == category]
                lines += ["", f"### {label} ({len(items)})"]

                for item in items[:args.max_per_category]:
                    source = source_map.get(item['source_id'], {})
                    when = f" @ {format_timestamp(item['start'])}" if item.get('start') is not None else ""
                    link = youtube_link(source, item.get('start'))
                    lines.append(f"- \"{item['text']}\"")
                    if item.get('translation_vi'):
                        lines.append(f"  - *Dịch:* {item['translation_vi']}")
                    if item.get('note'):
                        lines.append(f"  - *Ghi chú:* {item['note']}")
                    lines.append(f"  - *Nguồn:* [{source.get('title', item['source_id'])}{when}]({link})")

                if len(items) > args.max_per_category:
                    lines.append(f"- … còn {len(items) - args.max_per_category} câu, xem insights/ hoặc query_insights")

            lines.append("")

        unique_stories = self.store.read_output(slug, 'unique_stories.md')
        lines.append("# Câu chuyện độc đáo")
        if unique_stories:
            # Bỏ tiêu đề cấp 1 của file gốc, giữ nguyên phần thân
            lines.append(unique_stories.split('\n', 1)[-1].strip())
        else:
            lines.append("_Chưa chạy find_unique_stories._")

        file_path = self.store.write_output(slug, 'report.md', "\n".join(lines) + "\n")

        return BuildResearchReportToolResult(
            content=(
                f"Report written to {file_path}\n"
                + "\n".join(summary)
                + ("\nUnique stories included." if unique_stories else "\nUnique stories not included yet (run find_unique_stories).")
            )
        )
