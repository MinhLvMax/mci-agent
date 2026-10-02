import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from src.app.ports.model_reasoner import ModelReasoner
from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.research.llm_extractor import LLMExtractor, LLMExtractorError
from src.inf.tools.research.project_store import (
    ResearchProjectStore,
    ResearchProjectError,
    youtube_link,
)
from src.inf.tools.research.prompts import UNIQUE_STORIES_PROMPT

# Thứ tự ưu tiên khi phải chọn bớt insight gửi cho model: facts/nghịch lý và lịch sử dễ tạo nét riêng nhất
_PRIORITY = ('fact_paradox', 'data_history', 'comparison_metaphor', 'visual_description')


class FindUniqueStoriesToolKwargs(ToolKwargs):
    project: str | None = Field(
        default=None,
        description=(
            "Research project slug returned by start_research_project. "
            "Can be omitted when the workspace has only one research project."
        )
    )

    max_insights_per_place: int = Field(
        default=30,
        ge=5,
        le=80,
        description="Maximum number of insights of each place sent to the model for comparison."
    )


@dataclass
class FindUniqueStoriesToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class FindUniqueStoriesTool(Tool):
    tool_name = 'find_unique_stories'
    tool_description = (
        "Compare the extracted insights of ALL places in the project and find, for each place, the stories and "
        "details that only that place has compared to the others in the same article. "
        "Only works after every place of the project has insights (run extract_insights for each place first). "
        "Writes research/<project>/unique_stories.md."
    )

    tool_kwargs = FindUniqueStoriesToolKwargs

    def __init__(self, workspace_dir: str | Path, reasoner: ModelReasoner):
        self.store = ResearchProjectStore(workspace_dir)
        self.extractor = LLMExtractor(reasoner)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            project = self.store.load_project(args.project)
        except ResearchProjectError as e:
            return FindUniqueStoriesToolResult(content=str(e))

        slug = project['slug']
        places = project['places']

        if len(places) < 2:
            return FindUniqueStoriesToolResult(
                content="The project needs at least 2 places to compare. Add places with start_research_project."
            )

        insights_by_place = {place: self.store.read_insights(slug, place) for place in places}
        missing = [place for place, items in insights_by_place.items() if not items]

        if missing:
            return FindUniqueStoriesToolResult(
                content=(
                    f"Not every place has insights yet. Missing: {', '.join(missing)}. "
                    f"Collect sources and run extract_insights for these places first."
                )
            )

        sections = []
        for place in places:
            selected = _select(insights_by_place[place], args.max_insights_per_place)
            lines = [f"[{i['id']}] ({i['category']}) {i.get('translation_vi') or i['text']}" for i in selected]
            sections.append(f"## {place}\n" + "\n".join(lines))

        system_prompt = UNIQUE_STORIES_PROMPT.format(
            title=project['title'],
            places=', '.join(places),
            insights="\n\n".join(sections),
        )

        try:
            result = self.extractor.ask_json(
                system_prompt,
                "Hãy tìm câu chuyện độc đáo cho từng địa danh và trả về mảng JSON.",
            )
        except LLMExtractorError as e:
            return FindUniqueStoriesToolResult(content=f"Failed to find unique stories: {e}")

        if isinstance(result, dict):
            result = next((v for v in result.values() if isinstance(v, list)), [])

        all_insights = {i['id']: i for items in insights_by_place.values() for i in items}
        stories = []

        for raw in result:
            if not isinstance(raw, dict) or not raw.get('story'):
                continue
            try:
                place = self.store.find_place(project, str(raw.get('place', '')))
            except ResearchProjectError:
                continue

            stories.append({
                'place': place,
                'story': str(raw['story']).strip(),
                'why_unique': str(raw.get('why_unique', '')).strip(),
                'evidence': [e for e in raw.get('evidence') or [] if e in all_insights],
            })

        if not stories:
            return FindUniqueStoriesToolResult(content="The model did not return any usable story. Try again.")

        self.store.write_output(slug, 'unique_stories.json', json.dumps(stories, ensure_ascii=False, indent=2))
        file_path = self.store.write_output(
            slug, 'unique_stories.md', self._to_markdown(slug, project, stories, all_insights)
        )

        output = [f"Found {len(stories)} unique stories. file: {file_path}", ""]
        for place in places:
            for story in [s for s in stories if s['place'] == place]:
                output.append(f"- {place}: {story['story']}")
        without = [p for p in places if not any(s['place'] == p for s in stories)]
        if without:
            output.append(f"\nNo unique story found for: {', '.join(without)}")

        # Vẫn cho chạy khi còn nguồn chưa lọc xong, nhưng báo để agent biết kết quả có thể chưa đầy đủ
        unfinished = sorted({s['place'] for s in self.store.load_sources(slug) if not s.get('extracted')})
        if unfinished:
            output.append(
                f"\nWarning: some sources are not fully extracted yet for: {', '.join(unfinished)}. "
                f"Run extract_insights for them and call this tool again for a complete comparison."
            )

        return FindUniqueStoriesToolResult(content="\n".join(output))

    def _to_markdown(self, slug: str, project: dict, stories: list[dict], all_insights: dict) -> str:
        sources = {s['id']: s for s in self.store.load_sources(slug)}
        lines = [f"# Câu chuyện độc đáo — {project['title']}", ""]

        for place in project['places']:
            place_stories = [s for s in stories if s['place'] == place]
            if not place_stories:
                continue

            lines.append(f"## {place}")
            for number, story in enumerate(place_stories, 1):
                lines += ["", f"### {number}. {story['story']}"]
                if story['why_unique']:
                    lines.append(f"- **Vì sao độc đáo:** {story['why_unique']}")
                for insight_id in story['evidence']:
                    insight = all_insights[insight_id]
                    source = sources.get(insight['source_id'], {})
                    link = youtube_link(source, insight.get('start'))
                    lines.append(
                        f"- [{insight_id}] \"{insight['text']}\" — [{source.get('title', insight['source_id'])}]({link})"
                    )
            lines.append("")

        return "\n".join(lines)


def _select(insights: list[dict], limit: int) -> list[dict]:
    '''Chọn tối đa limit insight, lấy xen kẽ giữa các nhóm theo thứ tự ưu tiên để đủ đa dạng'''
    groups = [[i for i in insights if i['category'] == c] for c in _PRIORITY]
    selected = []

    while len(selected) < limit and any(groups):
        for group in groups:
            if group and len(selected) < limit:
                selected.append(group.pop(0))

    return selected
