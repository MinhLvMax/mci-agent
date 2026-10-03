import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from src.app.ports.model_reasoner import ModelReasoner
from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError
from src.inf.tools.research.helper import ResearchHelper

H = ResearchHelper

OUTLINE_PROMPT = """Bạn dựng một văn bản có cấu trúc từ các thông tin nghiên cứu được cung cấp.

Chủ đề: "{topic}"

Yêu cầu về văn bản cần dựng:
{brief}

Quy tắc:
- Chỉ dùng thông tin được cung cấp. Mỗi khi dùng một thông tin, ghi mã của nó ngay sau ý đó theo dạng (#id).
- Không bịa thêm số liệu, tên người, năm tháng ngoài các thông tin đã cho.
- Thông tin có đánh dấu ⚠ là chưa được nguồn khác xác nhận: nếu dùng thì ghi rõ "(cần kiểm chứng)".
- Ưu tiên thông tin nhiều sao (★★★).
- Viết bằng tiếng Việt, định dạng Markdown, dùng heading cho các phần. Không viết phần danh sách nguồn ở cuối.
"""

_CITATION = re.compile(r'\(#([^)\s]+)\)')


class BuildOutlineToolKwargs(ToolKwargs):
    insight_paths: list[str] = Field(
        min_length=1,
        description="Insight files written by extract_insights to build from."
    )

    brief: str = Field(
        min_length=10,
        description=(
            "What to build: kind of document, length, sections and what each section must contain, e.g. "
            "'outline for a 50-minute video, 8-10 segments, each with timing, goal, facts, visuals, transition'."
        )
    )

    topic: str = Field(
        default='',
        description="Title or purpose of the work."
    )

    extra_paths: list[str] = Field(
        default_factory=list,
        description="Other workspace files to give as context (e.g. unique stories, research plan)."
    )

    output_path: str = Field(
        default='outline.md',
        description="Markdown file to write the result to (replaced if it exists)."
    )

    max_insights: int = Field(
        default=150,
        ge=10,
        le=400,
        description="Maximum number of insights sent to the model, highest scores first."
    )


@dataclass
class BuildOutlineToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class BuildOutlineTool(Tool):
    tool_name = 'build_outline'
    tool_description = (
        "Build a structured document (outline, script plan, report...) from insight files, following the brief you "
        "write. Insights are given to the model best-scored first, contradicted ones (✖) are left out. "
        "The model cites insights as (#id); the tool appends a source list for every cited id, so the result can be "
        "traced back. Writes a Markdown file."
    )

    tool_kwargs = BuildOutlineToolKwargs

    EXTRA_CHARS = 6000  # Mỗi file ngữ cảnh thêm chỉ gửi đoạn đầu

    def __init__(self, workspace_dir: str | Path, reasoner: ModelReasoner):
        self.path_guard = WorkspacePathGuard(workspace_dir)
        self.reasoner = reasoner

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        files = []
        extras: list[tuple[str, str]] = []
        problems: list[str] = []

        try:
            for path in args.insight_paths:
                data = H.read_insights(self.path_guard, path)
                if data is None or not data.insights:
                    problems.append(f"{path} ({'not found' if data is None else 'no insights'})")
                else:
                    files.append(data)

            for path in args.extra_paths:
                resolved = self.path_guard.resolve(path)
                if resolved.is_file():
                    extras.append((path, resolved.read_text(encoding='utf-8', errors='replace')[:self.EXTRA_CHARS]))
                else:
                    problems.append(f"{path} (not found)")
        except WorkspacePathError as e:
            return BuildOutlineToolResult(content=f"Access denied: {e}")

        if not files:
            return BuildOutlineToolResult(content="No insights to build from: " + "; ".join(problems))

        pool = _pick(files, args.max_insights)
        topic = args.topic or next((f.topic for f in files if f.topic), '')

        try:
            text = H.ask_text(
                self.reasoner,
                OUTLINE_PROMPT.format(topic=topic or '(không có)', brief=args.brief.strip()),
                _user_content(pool, files, extras),
            )
        except H.LLMError as e:
            return BuildOutlineToolResult(content=f"Failed to build: {e}")

        text = _strip_fence(text)
        by_id = {insight.id: insight for insight, _ in pool}
        cited = list(dict.fromkeys(_CITATION.findall(text)))
        valid = [i for i in cited if i in by_id]
        unknown = [i for i in cited if i not in by_id]

        content = text.rstrip() + "\n\n" + _appendix(valid, by_id)

        try:
            saved_path = H.save_generated(self.path_guard, args.output_path, content)
        except WorkspacePathError as e:
            return BuildOutlineToolResult(content=f"Cannot save to '{args.output_path}': {e}")

        output = [
            f"Built '{saved_path}' from {len(pool)} insights of {len(files)} files.",
            f"Cited {len(valid)} insights, sections: {len(re.findall(r'^#{1,3} ', text, flags=re.MULTILINE))}.",
        ]
        if unknown:
            output.append(f"Unknown ids cited by the model (not in the insight files, check those parts): {', '.join(unknown)}")
        if problems:
            output.append(f"Skipped: {'; '.join(problems)}")

        return BuildOutlineToolResult(content="\n".join(output))


def _pick(files: list, limit: int) -> list[tuple]:
    '''Bỏ câu bị đánh dấu mâu thuẫn, lấy điểm cao trước, giữ thứ tự gốc khi bằng điểm'''
    pool = [(i, f) for f in files for i in f.insights if not i.check.startswith('✖')]
    pool.sort(key=lambda pair: -pair[0].score)
    return pool[:limit]


def _user_content(pool: list[tuple], files: list, extras: list[tuple[str, str]]) -> str:
    lines = ["# Thông tin nghiên cứu"]

    for insight, data in pool:
        label = H.category_label(data.categories.get(insight.category, insight.category))
        stars = f" {'★' * insight.score}" if insight.score else ""
        warning = " ⚠" if insight.check.startswith('⚠') else ""
        lines.append(f"[{insight.id}] ({data.subject} · {label}{stars}{warning}) {insight.translation or insight.text}")

    for path, text in extras:
        lines += ["", f"# Tài liệu thêm: {path}", text]

    return "\n".join(lines)


def _appendix(ids: list[str], by_id: dict) -> str:
    '''Danh sách nguồn do code ghi từ file insight, không qua model nên không thể bị bịa'''
    lines = ["## Nguồn trích dẫn", ""]

    if not ids:
        return "\n".join(lines + ["_Không có thông tin nào được trích dẫn._"]) + "\n"

    for insight_id in ids:
        insight = by_id[insight_id]
        start = f" @ {H.format_timestamp(insight.start)}" if insight.start is not None else ""
        check = f" {{{insight.check}}}" if insight.check else ""
        lines.append(f'- (#{insight_id}) "{insight.text}" — nguồn: `{insight.source}`{start}{check}')

    return "\n".join(lines) + "\n"


def _strip_fence(text: str) -> str:
    '''Model hay bọc cả bài trong ```markdown ... ```'''
    match = re.fullmatch(r'\s*```(?:markdown|md)?\s*\n(.*?)\n```\s*', text, flags=re.DOTALL)
    return match.group(1) if match else text
