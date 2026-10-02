from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from src.app.ports.model_reasoner import ModelReasoner
from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError
from src.inf.tools.research.insight_file import (
    CATEGORIES,
    Insight,
    InsightFile,
    read_insight_file,
    write_insight_file,
)
from src.inf.tools.research.llm_extractor import LLMExtractor, LLMExtractorError
from src.inf.tools.research.prompts import INSIGHT_EXTRACTION_PROMPT
from src.inf.tools.research.text_utils import (
    TextUnit,
    chunk_units,
    format_timestamp,
    load_units,
    mentions,
    place_terms,
    relevance_filter,
    slugify,
    strip_accents,
)

# Các loại file được đọc khi truyền vào một thư mục
TEXT_SUFFIXES = {'.txt', '.md', '.markdown', '.srt', '.vtt'}
SUBTITLE_SUFFIXES = {'.srt', '.vtt'}


class ExtractInsightsToolKwargs(ToolKwargs):
    paths: list[str] = Field(
        min_length=1,
        description=(
            "Source files or folders in the workspace to analyse (articles saved with open_url, subtitles "
            "uploaded by the user or saved by youtube_transcript, notes...). A folder means every text file "
            "inside it (.txt, .md, .srt, .vtt). Example: ['ha-long/sources', 'subs/ha-long.srt']."
        )
    )

    place: str = Field(
        description="The place (địa danh) to extract information about, e.g. 'Vịnh Hạ Long'."
    )

    aliases: list[str] = Field(
        default_factory=list,
        description="Other names of the place used to find relevant passages, e.g. ['Ha Long Bay']."
    )

    topic: str = Field(
        default='',
        description="Title or topic of the content being written, used to judge what is relevant."
    )

    keywords: list[str] = Field(
        default_factory=list,
        description="Optional keywords the content focuses on."
    )

    output_path: str | None = Field(
        default=None,
        description=(
            "Markdown file to write the insights to. Defaults to 'insights/<place>.md'. "
            "If the file exists, new insights are merged into it without duplicates."
        )
    )

    max_chunks: int = Field(
        default=15,
        ge=1,
        le=60,
        description=(
            "Maximum number of text chunks (about 6000 chars each, one LLM call per chunk) in this call. "
            "If work remains, call the tool again with the same arguments to continue."
        )
    )

    force: bool = Field(
        default=False,
        description="Re-process sources that were already processed into this output file."
    )


@dataclass
class ExtractInsightsToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class ExtractInsightsTool(Tool):
    tool_name = 'extract_insights'
    tool_description = (
        "Read source files about a place and classify useful sentences into 4 groups: "
        "data_history (numbers, dates, history), visual_description (descriptions of scenery and objects), "
        "comparison_metaphor (comparisons, metaphors) and fact_paradox (interesting facts, paradoxes). "
        "Writes a Markdown file grouped by these 4 groups, each insight with an id, its source file and the "
        "video timestamp for subtitles. Read it later with read_file or search_files. "
        "Work is incremental: sources already processed into the output file are skipped, and if the result "
        "says work remains, call it again. Source paths are recorded as they are now, so organise files before extracting."
    )

    tool_kwargs = ExtractInsightsToolKwargs

    CHUNK_CHARS = 6000
    EXAMPLES_PER_CATEGORY = 2

    def __init__(self, workspace_dir: str | Path, reasoner: ModelReasoner):
        self.path_guard = WorkspacePathGuard(workspace_dir)
        self.extractor = LLMExtractor(reasoner)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        output_path = args.output_path or f"insights/{slugify(args.place)}.md"

        try:
            sources, skipped = self._collect_sources(args.paths, output_path)
            existing = read_insight_file(self.path_guard, output_path, default_place=args.place)
        except WorkspacePathError as e:
            return ExtractInsightsToolResult(content=f"Access denied: {e}")

        if not sources:
            return ExtractInsightsToolResult(
                content="No readable text files found in: " + ", ".join(args.paths)
                        + (f"\nSkipped: {', '.join(skipped)}" if skipped else "")
            )

        data = existing or InsightFile(place=args.place, topic=args.topic)
        data.topic = data.topic or args.topic
        progress: dict = data.state.setdefault('sources', {})

        terms = place_terms(args.place, args.aliases)
        system_prompt = INSIGHT_EXTRACTION_PROMPT.format(
            topic=args.topic or data.topic or '(không có)',
            place=args.place,
            keywords=', '.join(args.keywords) or '(không có)',
        )

        added: list[Insight] = []
        chunks_done = failed_chunks = remaining_chunks = 0
        processed_sources = 0

        for relative, path in sources:
            mtime = int(path.stat().st_mtime)
            record = progress.get(relative)

            # File nguồn bị sửa sau lần xử lý trước thì làm lại từ đầu (insight trùng sẽ tự bị bỏ)
            start_chunk = 0 if args.force or not record or record.get('mtime') != mtime else record.get('chunks_done', 0)

            chunks = chunk_units(self._relevant_units(path, terms), self.CHUNK_CHARS)
            progress[relative] = {'chunks_done': start_chunk, 'of': len(chunks), 'mtime': mtime}

            if start_chunk >= len(chunks):
                continue

            processed_sources += 1

            for chunk_index in range(start_chunk, len(chunks)):
                if chunks_done >= args.max_chunks:
                    remaining_chunks += len(chunks) - chunk_index
                    break

                try:
                    added += self._merge(data, self._extract_chunk(system_prompt, relative, chunks[chunk_index]))
                except LLMExtractorError:
                    failed_chunks += 1

                chunks_done += 1
                progress[relative]['chunks_done'] = chunk_index + 1

                # Ghi sau mỗi chunk để lỡ bị ngắt giữa chừng vẫn giữ được phần đã làm
                write_insight_file(self.path_guard, output_path, data)

        write_insight_file(self.path_guard, output_path, data)

        return ExtractInsightsToolResult(
            content=self._summary(args.place, output_path, data, added, len(sources), processed_sources,
                                  chunks_done, failed_chunks, remaining_chunks, skipped)
        )

    def _collect_sources(self, paths: list[str], output_path: str) -> tuple[list[tuple[str, Path]], list[str]]:
        '''Mở rộng thư mục thành danh sách file text, bỏ chính file output và các file insight khác'''
        output = self.path_guard.resolve(output_path)
        found: dict[str, Path] = {}
        skipped: list[str] = []

        for raw in paths:
            path = self.path_guard.resolve(raw)

            if path.is_dir():
                candidates = sorted(p for p in path.rglob('*') if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES)
            elif path.is_file():
                candidates = [path]
            else:
                skipped.append(f"{raw} (not found)")
                continue

            for candidate in candidates:
                relative = self.path_guard.to_relative(candidate).replace('\\', '/')

                if candidate == output or _is_generated(candidate):
                    continue

                found.setdefault(relative, candidate)

        return list(found.items()), skipped

    def _relevant_units(self, path: Path, terms: list[str]) -> list[TextUnit]:
        '''Đọc file và chỉ giữ phần liên quan đến địa danh'''
        text = path.read_text(encoding='utf-8', errors='replace')
        units = load_units(text, path.suffix)

        # Phụ đề được agent chọn đúng cho địa danh nên giữ hết: lời thoại hay dùng "nơi đây" thay vì gọi tên
        if path.suffix.lower() in SUBTITLE_SUFFIXES:
            return units

        # Bài viết có tên địa danh ở tiêu đề/đầu bài thì nói chủ yếu về nó, lấy rộng ngữ cảnh hơn
        about_place = mentions(path.stem.replace('-', ' ') + ' ' + text[:300], terms)
        return relevance_filter(units, terms, window=2 if about_place else 1)

    def _extract_chunk(self, system_prompt: str, source: str, chunk: list[TextUnit]) -> list[Insight]:
        lines = [
            f"[u{i}]" + (f" ({format_timestamp(unit.start)})" if unit.start is not None else "") + f" {unit.text}"
            for i, unit in enumerate(chunk)
        ]
        result = self.extractor.ask_json(system_prompt, f"Nguồn: {source}\n\n" + "\n".join(lines))

        if isinstance(result, dict):  # Có model bọc mảng trong một object
            result = next((v for v in result.values() if isinstance(v, list)), [])

        items = []
        for raw in result:
            if not isinstance(raw, dict):
                continue

            category = str(raw.get('category', '')).strip()
            text = str(raw.get('text', '')).strip()
            if category not in CATEGORIES or not text:
                continue

            unit = _unit_at(chunk, raw.get('unit'))
            items.append(Insight(
                id='',  # Gán khi gộp vào file
                category=category,
                text=text,
                note=str(raw.get('note', '')).strip(),
                source=source,
                start=unit.start if unit else None,
                translation=str(raw.get('translation_vi') or '').strip(),
            ))

        return items

    @staticmethod
    def _merge(data: InsightFile, items: list[Insight]) -> list[Insight]:
        '''Thêm insight mới vào file, bỏ câu trùng (so khớp không dấu), đánh id tăng dần'''
        seen = {(strip_accents(i.text), i.category) for i in data.insights}
        prefix = slugify(data.place)
        numbers = [int(i.id.rsplit('-', 1)[-1]) for i in data.insights if i.id.rsplit('-', 1)[-1].isdigit()]
        next_number = max(numbers, default=0) + 1
        added = []

        for item in items:
            key = (strip_accents(item.text), item.category)
            if key in seen:
                continue

            seen.add(key)
            item.id = f"{prefix}-{next_number}"
            next_number += 1
            data.insights.append(item)
            added.append(item)

        return added

    def _summary(self, place, output_path, data, added, source_count, processed_sources,
                 chunks_done, failed_chunks, remaining_chunks, skipped) -> str:
        added_counts = Counter(i.category for i in added)
        total_counts = Counter(i.category for i in data.insights)

        output = [
            f"Processed {chunks_done} chunks from {processed_sources}/{source_count} source files for '{place}'.",
            f"New insights: {len(added)} | total in file: {len(data.insights)}",
            "",
        ]

        for category, label in CATEGORIES.items():
            output.append(f"- {category} ({label}): +{added_counts[category]} (total {total_counts[category]})")
            for item in [i for i in added if i.category == category][:self.EXAMPLES_PER_CATEGORY]:
                output.append(f"    (#{item.id}) {item.text[:200]}")

        if failed_chunks:
            output.append(f"\n{failed_chunks} chunks failed because the model did not return valid JSON.")

        if skipped:
            output.append(f"\nSkipped: {', '.join(skipped)}")

        if remaining_chunks:
            output.append(f"\nWork remains: about {remaining_chunks} chunks left. Call extract_insights again with the same arguments.")
        elif not chunks_done:
            output.append("\nAll sources were already processed into this file (use force=true to redo).")
        else:
            output.append("\nAll sources are processed.")

        output.append(f"file: {output_path}")
        return "\n".join(output)


def _is_generated(path: Path) -> bool:
    '''File do chính các tool phân tích tạo ra (insight, câu chuyện độc đáo) không phải là nguồn'''
    try:
        with path.open(encoding='utf-8', errors='replace') as file:
            first_line = file.readline()
    except OSError:
        return False
    return first_line.startswith(('# Insights:', '# Câu chuyện độc đáo'))


def _unit_at(chunk: list[TextUnit], value) -> TextUnit | None:
    '''Model trả về "unit" dạng 3 hoặc "u3", đổi về đoạn tương ứng để lấy timestamp'''
    try:
        index = int(str(value).lstrip('[u').rstrip(']'))
    except (TypeError, ValueError):
        return None
    return chunk[index] if 0 <= index < len(chunk) else None
