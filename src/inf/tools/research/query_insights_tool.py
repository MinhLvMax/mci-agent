from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.research.project_store import CATEGORIES, ResearchProjectStore, ResearchProjectError
from src.inf.tools.research.text_utils import format_timestamp, strip_accents


class QueryInsightsToolKwargs(ToolKwargs):
    project: str | None = Field(
        default=None,
        description=(
            "Research project slug returned by start_research_project. "
            "Can be omitted when the workspace has only one research project."
        )
    )

    place: str | None = Field(
        default=None,
        description="Only return insights of this place. If omitted, return insights of all places."
    )

    category: Literal['data_history', 'visual_description', 'comparison_metaphor', 'fact_paradox'] | None = Field(
        default=None,
        description="Only return insights of this group."
    )

    contains: str | None = Field(
        default=None,
        description="Only return insights containing this text (accent-insensitive)."
    )

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of insights to return."
    )

    offset: int = Field(
        default=0,
        ge=0,
        description="Number of matching insights to skip, used for paging."
    )


@dataclass
class QueryInsightsToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class QueryInsightsTool(Tool):
    tool_name = 'query_insights'
    tool_description = (
        "Read the insights extracted by extract_insights, filtered by place, group or text, with paging. "
        "Each insight shows its id, group, quoted sentence, note and source (with video timestamp). "
        "Without filters it also shows how many insights each place has per group."
    )

    tool_kwargs = QueryInsightsToolKwargs

    def __init__(self, workspace_dir: str | Path):
        self.store = ResearchProjectStore(workspace_dir)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            project = self.store.load_project(args.project)
            places = [self.store.find_place(project, args.place)] if args.place else project['places']
        except ResearchProjectError as e:
            return QueryInsightsToolResult(content=str(e))

        slug = project['slug']
        sources = {s['id']: s for s in self.store.load_sources(slug)}
        insights = [i for place in places for i in self.store.read_insights(slug, place)]

        output = []

        if args.place is None and args.category is None and args.contains is None:
            output.append("Overview (insights per place):")
            for place in places:
                counts = Counter(i['category'] for i in insights if i['place'] == place)
                detail = ', '.join(f"{c}: {counts[c]}" for c in CATEGORIES)
                output.append(f"- {place}: {sum(counts.values())} ({detail})")
            output.append("")

        if args.category:
            insights = [i for i in insights if i['category'] == args.category]

        if args.contains:
            needle = strip_accents(args.contains)
            insights = [i for i in insights if needle in strip_accents(i['text'])]

        page = insights[args.offset:args.offset + args.limit]

        if not page:
            output.append("No matching insights.")
            return QueryInsightsToolResult(content="\n".join(output))

        output.append(f"Showing {args.offset + 1}-{args.offset + len(page)} of {len(insights)} matching insights:")

        for item in page:
            source = sources.get(item['source_id'], {})
            where = source.get('title', item['source_id'])
            if item.get('start') is not None:
                where += f" @ {format_timestamp(item['start'])}"

            output.append(f"\n[{item['id']}] ({item['category']}) {item['text']}")
            if item.get('translation_vi'):
                output.append(f"  dịch: {item['translation_vi']}")
            if item.get('note'):
                output.append(f"  note: {item['note']}")
            output.append(f"  source: {where}")

        if args.offset + len(page) < len(insights):
            output.append(f"\nMore available, call again with offset={args.offset + len(page)}.")

        return QueryInsightsToolResult(content="\n".join(output))
