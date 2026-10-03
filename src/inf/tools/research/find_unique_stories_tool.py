from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from src.app.ports.model_reasoner import ModelReasoner
from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError
from src.inf.tools.research.helper import ResearchHelper

H = ResearchHelper

COMPARE_PROMPT = """Bạn là trợ lý nghiên cứu. Bạn so sánh nhiều đối tượng với nhau.

Chủ đề / mục đích sử dụng: "{topic}"
Các đối tượng: {subjects}

Dưới đây là các thông tin đã lọc được cho từng đối tượng (mỗi dòng có mã [id], nhóm và điểm sao).
Nhiệm vụ: với MỖI đối tượng, tìm 1-3 câu chuyện / chi tiết CHỈ đối tượng đó có,
những điểm mà các đối tượng còn lại KHÔNG có hoặc không nổi bật bằng.
Tránh điểm chung chung mà đối tượng nào cũng có.
Có thể kết hợp nhiều thông tin thành một câu chuyện, nhưng chỉ dùng dữ liệu được cung cấp, không bịa thêm.

Yêu cầu riêng:
{instructions}

{insights}

Chỉ trả lời bằng một mảng JSON, không giải thích gì thêm:
[{{"subject": "<tên đối tượng>", "story": "<câu chuyện, 2-4 câu tiếng Việt>",
   "why_unique": "<vì sao các đối tượng khác không có>", "evidence": ["<id>", "<id>"]}}]
"""


class FindUniqueStoriesToolKwargs(ToolKwargs):
    insight_paths: list[str] = Field(
        min_length=2,
        description=(
            "Insight files written by extract_insights, one per subject (at least 2), e.g. "
            "['insights/vinh-ha-long.md', 'insights/trang-an.md']. The subject name is read from each file."
        )
    )

    topic: str = Field(
        default='',
        description="Title or purpose of the work."
    )

    instructions: str = Field(
        default='',
        description="Extra rules for choosing stories, e.g. what kind of details to prefer."
    )

    output_path: str = Field(
        default='unique_stories.md',
        description="Markdown file to write the result to (replaced if it exists)."
    )

    max_insights_per_subject: int = Field(
        default=30,
        ge=5,
        le=80,
        description="Maximum number of insights of each subject sent to the model, highest scores first."
    )


@dataclass
class FindUniqueStoriesToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class FindUniqueStoriesTool(Tool):
    tool_name = 'find_unique_stories'
    tool_description = (
        "Compare the insight files of several subjects (written by extract_insights) and find, for each subject, "
        "the stories and details that only it has compared to the others. "
        "Run it after the insights of every subject are extracted. Writes a Markdown file with evidence ids and sources."
    )

    tool_kwargs = FindUniqueStoriesToolKwargs

    def __init__(self, workspace_dir: str | Path, reasoner: ModelReasoner):
        self.path_guard = WorkspacePathGuard(workspace_dir)
        self.reasoner = reasoner

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        files = []
        problems: list[str] = []

        try:
            for path in args.insight_paths:
                data = H.read_insights(self.path_guard, path, default_subject=Path(path).stem)
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

        if len({H.strip_accents(f.subject) for f in files}) < 2:
            return FindUniqueStoriesToolResult(content="Need insight files of at least 2 different subjects.")

        subjects = [f.subject for f in files]
        topic = args.topic or next((f.topic for f in files if f.topic), '')

        sections = []
        for data in files:
            lines = [
                f"[{i.id}] ({H.category_label(data.categories.get(i.category, i.category))}"
                f"{', ' + '★' * i.score if i.score else ''}) {i.translation or i.text}"
                for i in _select(data.insights, args.max_insights_per_subject)
            ]
            sections.append(f"## {data.subject}\n" + "\n".join(lines))

        system_prompt = COMPARE_PROMPT.format(
            topic=topic or '(không có)',
            subjects=', '.join(subjects),
            instructions=args.instructions.strip() or '(không có)',
            insights="\n\n".join(sections),
        )

        try:
            result = H.as_list(H.ask_json(
                self.reasoner,
                system_prompt,
                "Hãy tìm câu chuyện độc đáo cho từng đối tượng và trả về mảng JSON.",
            ))
        except H.LLMError as e:
            return FindUniqueStoriesToolResult(content=f"Failed to find unique stories: {e}")

        all_insights = {i.id: i for data in files for i in data.insights}
        subject_by_key = {H.strip_accents(s): s for s in subjects}
        stories = []

        for raw in result:
            if not isinstance(raw, dict) or not raw.get('story'):
                continue

            subject = subject_by_key.get(H.strip_accents(str(raw.get('subject') or raw.get('place') or '')))
            if subject is None:
                continue

            stories.append({
                'subject': subject,
                'story': str(raw['story']).strip(),
                'why_unique': str(raw.get('why_unique', '')).strip(),
                'evidence': [e for e in raw.get('evidence') or [] if e in all_insights],
            })

        if not stories:
            return FindUniqueStoriesToolResult(content="The model did not return any usable story. Try again.")

        try:
            saved_path = H.save_generated(
                self.path_guard, args.output_path, _to_markdown(topic, subjects, stories, all_insights)
            )
        except WorkspacePathError as e:
            return FindUniqueStoriesToolResult(content=f"Cannot save to '{args.output_path}': {e}")

        output = [f"Found {len(stories)} unique stories. file: {saved_path}", ""]
        for story in stories:
            output.append(f"- {story['subject']}: {story['story']}")

        without = [s for s in subjects if not any(story['subject'] == s for story in stories)]
        if without:
            output.append(f"\nNo unique story found for: {', '.join(without)}")

        return FindUniqueStoriesToolResult(content="\n".join(output))


def _select(insights: list, limit: int) -> list:
    '''
    Chọn tối đa limit câu: bỏ câu bị đánh dấu mâu thuẫn, mỗi nhóm xếp điểm cao trước,
    rồi lấy xen kẽ giữa các nhóm để đủ đa dạng.
    '''
    usable = [i for i in insights if not i.check.startswith('✖')]
    categories = list(dict.fromkeys(i.category for i in usable))
    groups = [sorted((i for i in usable if i.category == c), key=lambda i: -i.score) for c in categories]
    groups.sort(key=lambda group: -group[0].score)  # Nhóm có câu điểm cao nhất được lấy trước mỗi vòng

    selected = []
    while len(selected) < limit and any(groups):
        for group in groups:
            if group and len(selected) < limit:
                selected.append(group.pop(0))

    return selected


def _to_markdown(topic: str, subjects: list[str], stories: list[dict], all_insights: dict) -> str:
    lines = [f"# Câu chuyện độc đáo{f' — {topic}' if topic else ''}", ""]

    for subject in subjects:
        subject_stories = [s for s in stories if s['subject'] == subject]
        if not subject_stories:
            continue

        lines.append(f"## {subject}")
        for number, story in enumerate(subject_stories, 1):
            lines += ["", f"### {number}. {story['story']}"]
            if story['why_unique']:
                lines.append(f"- **Vì sao độc đáo:** {story['why_unique']}")
            for insight_id in story['evidence']:
                insight = all_insights[insight_id]
                start = f" @ {H.format_timestamp(insight.start)}" if insight.start is not None else ""
                lines.append(f"- (#{insight_id}) \"{insight.text}\" — nguồn: `{insight.source}`{start}")
        lines.append("")

    return "\n".join(lines)
