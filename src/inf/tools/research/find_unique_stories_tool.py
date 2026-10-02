from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from src.app.ports.model_reasoner import ModelReasoner
from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError, save_text
from src.inf.tools.research.insight_file import Insight, InsightFile, read_insight_file
from src.inf.tools.research.llm_extractor import LLMExtractor, LLMExtractorError
from src.inf.tools.research.prompts import UNIQUE_STORIES_PROMPT
from src.inf.tools.research.text_utils import format_timestamp, strip_accents

# Thứ tự ưu tiên khi phải chọn bớt insight gửi cho model: facts/nghịch lý và lịch sử dễ tạo nét riêng nhất
_PRIORITY = ('fact_paradox', 'data_history', 'comparison_metaphor', 'visual_description')


class FindUniqueStoriesToolKwargs(ToolKwargs):
    insight_paths: list[str] = Field(
        min_length=2,
        description=(
            "Insight files written by extract_insights, one per place (at least 2), e.g. "
            "['insights/vinh-ha-long.md', 'insights/trang-an.md']. The place name is read from each file."
        )
    )

    topic: str = Field(
        default='',
        description="Title or topic of the content being written."
    )

    output_path: str = Field(
        default='unique_stories.md',
        description="Markdown file to write the result to (replaced if it exists)."
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
        "Compare the insight files of several places (written by extract_insights) and find, for each place, "
        "the stories and details that only that place has compared to the others. "
        "Run it after the insights of every place are extracted. Writes a Markdown file with evidence ids and sources."
    )

    tool_kwargs = FindUniqueStoriesToolKwargs

    def __init__(self, workspace_dir: str | Path, reasoner: ModelReasoner):
        self.path_guard = WorkspacePathGuard(workspace_dir)
        self.extractor = LLMExtractor(reasoner)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        files: list[InsightFile] = []
        problems: list[str] = []

        try:
            for path in args.insight_paths:
                data = read_insight_file(self.path_guard, path, default_place=Path(path).stem)
                if data is None:
                    problems.append(f"{path} (not found)")
                elif not data.insights:
                    problems.append(f"{path} (no insights yet, run extract_insights first)")
                else:
                    files.append(data)
        except WorkspacePathError as e:
            return FindUniqueStoriesToolResult(content=f"Access denied: {e}")

        if problems:
            return FindUniqueStoriesToolResult(content="Cannot compare yet: " + "; ".join(problems))

        if len({strip_accents(f.place) for f in files}) < 2:
            return FindUniqueStoriesToolResult(content="Need insight files of at least 2 different places.")

        places = [f.place for f in files]
        topic = args.topic or next((f.topic for f in files if f.topic), '')

        sections = []
        for data in files:
            selected = _select(data.insights, args.max_insights_per_place)
            lines = [f"[{i.id}] ({i.category}) {i.translation or i.text}" for i in selected]
            sections.append(f"## {data.place}\n" + "\n".join(lines))

        system_prompt = UNIQUE_STORIES_PROMPT.format(
            topic=topic or '(không có)',
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

        all_insights = {i.id: i for data in files for i in data.insights}
        place_by_key = {strip_accents(p): p for p in places}
        stories = []

        for raw in result:
            if not isinstance(raw, dict) or not raw.get('story'):
                continue

            place = place_by_key.get(strip_accents(str(raw.get('place', ''))))
            if place is None:
                continue

            stories.append({
                'place': place,
                'story': str(raw['story']).strip(),
                'why_unique': str(raw.get('why_unique', '')).strip(),
                'evidence': [e for e in raw.get('evidence') or [] if e in all_insights],
            })

        if not stories:
            return FindUniqueStoriesToolResult(content="The model did not return any usable story. Try again.")

        try:
            saved_path = save_text(
                self.path_guard, args.output_path, _to_markdown(topic, places, stories, all_insights)
            )
        except WorkspacePathError as e:
            return FindUniqueStoriesToolResult(content=f"Cannot save to '{args.output_path}': {e}")

        output = [f"Found {len(stories)} unique stories. file: {saved_path}", ""]
        for story in stories:
            output.append(f"- {story['place']}: {story['story']}")

        without = [p for p in places if not any(s['place'] == p for s in stories)]
        if without:
            output.append(f"\nNo unique story found for: {', '.join(without)}")

        return FindUniqueStoriesToolResult(content="\n".join(output))


def _to_markdown(topic: str, places: list[str], stories: list[dict], all_insights: dict[str, Insight]) -> str:
    lines = [f"# Câu chuyện độc đáo{f' — {topic}' if topic else ''}", ""]

    for place in places:
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
                start = f" @ {format_timestamp(insight.start)}" if insight.start is not None else ""
                lines.append(f"- (#{insight_id}) \"{insight.text}\" — nguồn: `{insight.source}`{start}")
        lines.append("")

    return "\n".join(lines)


def _select(insights: list[Insight], limit: int) -> list[Insight]:
    '''Chọn tối đa limit insight, lấy xen kẽ giữa các nhóm theo thứ tự ưu tiên để đủ đa dạng'''
    groups = [[i for i in insights if i.category == c] for c in _PRIORITY]
    selected = []

    while len(selected) < limit and any(groups):
        for group in groups:
            if group and len(selected) < limit:
                selected.append(group.pop(0))

    return selected
