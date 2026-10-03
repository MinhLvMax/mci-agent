import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, field_validator

from src.app.ports.model_reasoner import ModelReasoner
from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError
from src.inf.tools.research.helper import ResearchHelper

H = ResearchHelper

EXTRACT_PROMPT = """Bạn là trợ lý nghiên cứu. Đọc các đoạn văn bản (phụ đề video hoặc bài viết) và lọc ra những câu hữu ích về đối tượng dưới đây.

Đối tượng: "{subject}"
Chủ đề / mục đích sử dụng: "{topic}"
Từ khoá trọng tâm: {keywords}

Các nhóm phân loại. Mỗi câu thuộc ĐÚNG MỘT nhóm, chỉ dùng các khoá dưới đây:
{categories}

Yêu cầu riêng:
{instructions}

Chấm "score" từ 1 đến 3:
{score_guide}

Quy tắc chung:
- Chỉ lấy câu nói về "{subject}". Bỏ qua câu về đối tượng khác, lời chào, quảng cáo, kêu gọi đăng ký kênh.
- "text" phải trích NGUYÊN VĂN từ đoạn nguồn (được sửa lỗi chính tả hiển nhiên của phụ đề tự động, thêm dấu câu), không bịa thêm.
- Nếu nguồn không phải tiếng Việt, thêm trường "translation_vi" là bản dịch tiếng Việt.
- "note": 1 câu ngắn bằng tiếng Việt nói vì sao câu này đáng dùng.
- "unit": số thứ tự của đoạn chứa câu đó (số trong dấu [u..]).
- Không có câu nào phù hợp thì trả về [].

Chỉ trả lời bằng một mảng JSON, không giải thích gì thêm:
[{{"unit": 3, "category": "<khoá nhóm>", "score": 2, "text": "...", "note": "..."}}]
"""

DEFAULT_SCORE_GUIDE = "3 = nổi bật, đáng dùng nhất; 2 = dùng được; 1 = bình thường."

_CATEGORY_KEY = re.compile(r'^[a-z][a-z0-9_]*$')


class ExtractInsightsToolKwargs(ToolKwargs):
    paths: list[str] = Field(
        min_length=1,
        description=(
            "Source files or folders in the workspace (articles saved with open_url, subtitles, notes...). "
            "A folder means every text file inside it (.txt, .md, .srt, .vtt)."
        )
    )

    subject: str = Field(
        description="What to extract information about: a place, event, person, phenomenon..."
    )

    aliases: list[str] = Field(
        default_factory=list,
        description="Other names of the subject (English name, short name, old name...), used to find relevant passages."
    )

    topic: str = Field(
        default='',
        description="Title or purpose of the work, used to judge what is relevant."
    )

    keywords: list[str] = Field(
        default_factory=list,
        description="Optional keywords to focus on."
    )

    categories: dict[str, str] | None = Field(
        default=None,
        description=(
            "Groups to classify sentences into: {key: description}, keys in snake_case, e.g. "
            "{'numbers': 'Numbers: dates, measurements, counts', 'quotes': 'Memorable quotes'}. "
            "Required the first time for an output file; "
            "later calls may omit it to reuse the groups saved in the file."
        )
    )

    instructions: str = Field(
        default='',
        description="Extra rules for this extraction, e.g. what to skip or what to prefer."
    )

    score_guide: str = Field(
        default='',
        description="How to score each sentence from 1 to 3. Empty uses a generic guide."
    )

    output_path: str | None = Field(
        default=None,
        description=(
            "Markdown file to write the insights to. Defaults to 'insights/<subject>.md'. "
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

    @field_validator('categories')
    @classmethod
    def _check_keys(cls, value):
        if value is not None:
            if not value:
                raise ValueError('categories must not be empty')
            bad = [key for key in value if not _CATEGORY_KEY.match(key)]
            if bad:
                raise ValueError(f'category keys must be snake_case: {bad}')
        return value


@dataclass
class ExtractInsightsToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class ExtractInsightsTool(Tool):
    tool_name = 'extract_insights'
    tool_description = (
        "Read source files and pick out useful sentences about a subject, classified into the groups you pass "
        "in `categories` and scored 1-3. Writes a Markdown file grouped by those groups, each sentence with an id, "
        "score, source file and video timestamp for subtitles. Read it later with read_file or search_files. "
        "Work is incremental: sources already processed are skipped, and if the result says work remains, call it again. "
        "Source paths are recorded as they are now, so organise files before extracting."
    )

    tool_kwargs = ExtractInsightsToolKwargs

    CHUNK_CHARS = 6000
    EXAMPLES_PER_CATEGORY = 2

    def __init__(self, workspace_dir: str | Path, reasoner: ModelReasoner):
        self.path_guard = WorkspacePathGuard(workspace_dir)
        self.reasoner = reasoner

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        output_path = args.output_path or f"insights/{_slugify(args.subject)}.md"

        try:
            sources, skipped = self._collect_sources(args.paths, output_path)
            existing = H.read_insights(self.path_guard, output_path, default_subject=args.subject)
        except WorkspacePathError as e:
            return ExtractInsightsToolResult(content=f"Access denied: {e}")

        data = existing or H.InsightFile(subject=args.subject, topic=args.topic)

        categories, problem = _resolve_categories(args.categories, data.categories, output_path)
        if problem:
            return ExtractInsightsToolResult(content=problem)

        if not sources:
            return ExtractInsightsToolResult(
                content="No readable text files found in: " + ", ".join(args.paths)
                        + (f"\nSkipped: {', '.join(skipped)}" if skipped else "")
            )

        data.categories = categories
        data.topic = data.topic or args.topic
        progress: dict = data.state.setdefault('sources', {})

        terms = _subject_terms(args.subject, args.aliases)
        system_prompt = EXTRACT_PROMPT.format(
            subject=args.subject,
            topic=args.topic or data.topic or '(không có)',
            keywords=', '.join(args.keywords) or '(không có)',
            categories="\n".join(f"- {key}: {description}" for key, description in categories.items()),
            instructions=args.instructions.strip() or '(không có)',
            score_guide=args.score_guide.strip() or DEFAULT_SCORE_GUIDE,
        )

        added = []
        unmatched: list[str] = []
        chunks_done = failed_chunks = remaining_chunks = 0
        processed_sources = 0

        for relative, path in sources:
            mtime = int(path.stat().st_mtime)
            record = progress.get(relative)

            # File nguồn bị sửa sau lần xử lý trước thì làm lại từ đầu (câu trùng sẽ tự bị bỏ)
            start_chunk = 0 if args.force or not record or record.get('mtime') != mtime else record.get('chunks_done', 0)

            units, matched = self._relevant_units(path, terms)
            if not matched:
                unmatched.append(relative)

            chunks = _chunk_units(units, self.CHUNK_CHARS)
            progress[relative] = {'chunks_done': start_chunk, 'of': len(chunks), 'mtime': mtime}

            if start_chunk >= len(chunks):
                continue

            processed_sources += 1

            for chunk_index in range(start_chunk, len(chunks)):
                if chunks_done >= args.max_chunks:
                    remaining_chunks += len(chunks) - chunk_index
                    break

                try:
                    added += _merge(data, self._extract_chunk(system_prompt, relative, chunks[chunk_index], categories))
                except H.LLMError:
                    failed_chunks += 1

                chunks_done += 1
                progress[relative]['chunks_done'] = chunk_index + 1

                # Ghi sau mỗi chunk để lỡ bị ngắt giữa chừng vẫn giữ được phần đã làm
                H.write_insights(self.path_guard, output_path, data)

        H.write_insights(self.path_guard, output_path, data)

        return ExtractInsightsToolResult(
            content=self._summary(args.subject, output_path, data, added, len(sources), processed_sources,
                                  chunks_done, failed_chunks, remaining_chunks, skipped, unmatched)
        )

    def _collect_sources(self, paths: list[str], output_path: str) -> tuple[list[tuple[str, Path]], list[str]]:
        '''Mở rộng thư mục thành danh sách file text, bỏ chính file output và các file kết quả khác'''
        output = self.path_guard.resolve(output_path)
        found: dict[str, Path] = {}
        skipped: list[str] = []

        for raw in paths:
            path = self.path_guard.resolve(raw)

            if path.is_dir():
                candidates = sorted(p for p in path.rglob('*') if p.is_file() and p.suffix.lower() in H.TEXT_SUFFIXES)
            elif path.is_file():
                candidates = [path]
            else:
                skipped.append(f"{raw} (not found)")
                continue

            for candidate in candidates:
                if candidate == output or H.is_generated(candidate):
                    continue
                found.setdefault(self.path_guard.to_relative(candidate).replace('\\', '/'), candidate)

        return list(found.items()), skipped

    @staticmethod
    def _relevant_units(path: Path, terms: list[str]) -> tuple[list, bool]:
        '''
        Chỉ giữ phần nhắc tới đối tượng để đỡ tốn lượt gọi model.
        Trả về (các đoạn, có khớp tên hay không). Không khớp đoạn nào thì giữ cả nguồn:
        nguồn được chọn có chủ đích, không khớp thường là do tên viết khác, model sẽ tự lọc.
        '''
        units = H.load_units(path)

        # Phụ đề được chọn đúng cho đối tượng nên giữ hết: lời thoại hay dùng "nơi đây" thay vì gọi tên
        if path.suffix.lower() in H.SUBTITLE_SUFFIXES:
            return units, True

        # Tên đối tượng có ở tên file/đầu bài thì bài nói chủ yếu về nó, lấy rộng ngữ cảnh hơn
        about_subject = _mentions(path.stem.replace('-', ' ') + ' ' + ' '.join(u.text for u in units[:3]), terms)
        relevant = _relevance_filter(units, terms, window=2 if about_subject else 1)

        if not relevant and units:
            return units, False

        return relevant, True

    def _extract_chunk(self, system_prompt: str, source: str, chunk: list, categories: dict[str, str]) -> list:
        lines = [
            f"[u{i}]" + (f" ({H.format_timestamp(unit.start)})" if unit.start is not None else "") + f" {unit.text}"
            for i, unit in enumerate(chunk)
        ]
        result = H.as_list(H.ask_json(self.reasoner, system_prompt, f"Nguồn: {source}\n\n" + "\n".join(lines)))

        items = []
        for raw in result:
            if not isinstance(raw, dict):
                continue

            category = str(raw.get('category', '')).strip()
            text = str(raw.get('text', '')).strip()
            if category not in categories or not text:  # Model tự đặt nhóm lạ thì bỏ
                continue

            unit = _unit_at(chunk, raw.get('unit'))
            items.append(H.Insight(
                id='',  # Gán khi gộp vào file
                category=category,
                text=text,
                note=str(raw.get('note', '')).strip(),
                source=source,
                start=unit.start if unit else None,
                translation=str(raw.get('translation_vi') or '').strip(),
                score=_score(raw.get('score')),
            ))

        return items

    def _summary(self, subject, output_path, data, added, source_count, processed_sources,
                 chunks_done, failed_chunks, remaining_chunks, skipped, unmatched) -> str:
        added_counts = Counter(i.category for i in added)
        total_counts = Counter(i.category for i in data.insights)
        top_counts = Counter(i.category for i in data.insights if i.score >= 3)

        output = [
            f"Processed {chunks_done} chunks from {processed_sources}/{source_count} source files for '{subject}'.",
            f"New insights: {len(added)} | total in file: {len(data.insights)}",
            "",
        ]

        for key, description in data.categories.items():
            output.append(
                f"- {key} ({H.category_label(description)}): +{added_counts[key]} "
                f"(total {total_counts[key]}, ★★★ {top_counts[key]})"
            )
            for item in [i for i in added if i.category == key][:self.EXAMPLES_PER_CATEGORY]:
                output.append(f"    (#{item.id}) {item.text[:200]}")

        if unmatched:
            output.append(
                f"\nSubject name not found in: {', '.join(unmatched)} → the whole file was sent to the model. "
                f"If a file is off-topic, leave it out next time; if it is on-topic, add the names it uses to aliases."
            )

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


def _resolve_categories(requested: dict[str, str] | None, saved: dict[str, str], output_path: str):
    '''Chọn bộ nhóm: lần đầu phải truyền, lần sau dùng lại bộ đã lưu; đổi khoá nhóm giữa chừng thì báo lỗi'''
    if requested is None:
        if not saved:
            return None, (
                "categories is required for a new output file: pass {key: description} for the groups to classify into."
            )
        return saved, None

    if saved and set(requested) != set(saved):
        return None, (
            f"'{output_path}' already uses the groups {sorted(saved)}, which differ from {sorted(requested)}. "
            f"Pass the same keys (descriptions may change), omit categories to reuse them, or use another output_path."
        )

    return dict(requested), None


def _subject_terms(subject: str, aliases: list[str]) -> list[str]:
    '''Các tên của đối tượng (đã bỏ dấu) dùng để nhận ra nó trong văn bản'''
    terms = {H.strip_accents(name) for name in [subject, *aliases] if name.strip()}
    return sorted(terms, key=len, reverse=True)


def _mentions(text: str, terms: list[str]) -> bool:
    '''
    Văn bản có nhắc tới một trong các tên không. So theo từng chữ, ghép k chữ liền nhau rồi so
    với tên đã bỏ khoảng trắng, nên khớp được cả dạng viết liền/viết rời ("Halong" / "Ha Long").
    '''
    tokens = re.findall(r'[a-z0-9]+', H.strip_accents(text))

    for term in terms:
        target = term.replace(' ', '')
        if not target:
            continue

        for k in range(1, len(term.split()) + 4):
            for i in range(len(tokens) - k + 1):
                if ''.join(tokens[i:i + k]) == target:
                    return True

    return False


def _relevance_filter(units: list, terms: list[str], window: int = 1) -> list:
    '''Giữ các đoạn nhắc tới đối tượng, kèm window đoạn lân cận để không mất ngữ cảnh'''
    keep: set[int] = set()

    for index, unit in enumerate(units):
        if _mentions(unit.text, terms):
            keep.update(range(max(0, index - window), min(len(units), index + window + 1)))

    return [units[i] for i in sorted(keep)]


def _chunk_units(units: list, max_chars: int) -> list[list]:
    chunks, current, size = [], [], 0

    for unit in units:
        if current and size + len(unit.text) > max_chars:
            chunks.append(current)
            current, size = [], 0

        current.append(unit)
        size += len(unit.text) + 1

    if current:
        chunks.append(current)

    return chunks


def _merge(data, items: list) -> list:
    '''Thêm câu mới vào file, bỏ câu trùng (so khớp không dấu), đánh id tăng dần'''
    seen = {(H.strip_accents(i.text), i.category) for i in data.insights}
    prefix = _slugify(data.subject)
    numbers = [int(i.id.rsplit('-', 1)[-1]) for i in data.insights if i.id.rsplit('-', 1)[-1].isdigit()]
    next_number = max(numbers, default=0) + 1
    added = []

    for item in items:
        key = (H.strip_accents(item.text), item.category)
        if key in seen:
            continue

        seen.add(key)
        item.id = f"{prefix}-{next_number}"
        next_number += 1
        data.insights.append(item)
        added.append(item)

    return added


def _score(value) -> int:
    try:
        return min(3, max(1, int(value)))
    except (TypeError, ValueError):
        return 1


def _unit_at(chunk: list, value):
    '''Model trả về "unit" dạng 3 hoặc "u3", đổi về đoạn tương ứng để lấy timestamp'''
    try:
        index = int(str(value).lstrip('[u').rstrip(']'))
    except (TypeError, ValueError):
        return None
    return chunk[index] if 0 <= index < len(chunk) else None


def _slugify(text: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', H.strip_accents(text)).strip('-')
    return slug[:60] or 'untitled'
