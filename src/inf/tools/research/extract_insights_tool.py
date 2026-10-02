from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from src.app.ports.model_reasoner import ModelReasoner
from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.research.llm_extractor import LLMExtractor, LLMExtractorError
from src.inf.tools.research.project_store import CATEGORIES, ResearchProjectStore, ResearchProjectError
from src.inf.tools.research.prompts import INSIGHT_EXTRACTION_PROMPT
from src.inf.tools.research.text_utils import (
    TextUnit,
    chunk_units,
    format_timestamp,
    mentions,
    parse_transcript,
    place_terms,
    relevance_filter,
    split_sentences,
    strip_accents,
)


class ExtractInsightsToolKwargs(ToolKwargs):
    project: str | None = Field(
        default=None,
        description=(
            "Research project slug returned by start_research_project. "
            "Can be omitted when the workspace has only one research project."
        )
    )

    place: str = Field(
        description="The place (địa danh) to extract information for."
    )

    aliases: list[str] = Field(
        default_factory=list,
        description=(
            "Other names of the place used to find relevant passages, "
            "e.g. ['Ha Long Bay', 'vịnh Bái Tử Long'] for 'Vịnh Hạ Long'."
        )
    )

    source_ids: list[str] | None = Field(
        default=None,
        description="Only process these sources. If omitted, process every saved source of the place."
    )

    force: bool = Field(
        default=False,
        description="Re-process sources that were already extracted."
    )

    max_chunks: int = Field(
        default=15,
        ge=1,
        le=60,
        description=(
            "Maximum number of text chunks (about 6000 chars each, one LLM call per chunk) to process in this call. "
            "If work remains, call the tool again to continue."
        )
    )


@dataclass
class ExtractInsightsToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class ExtractInsightsTool(Tool):
    tool_name = 'extract_insights'
    tool_description = (
        "Filter the saved YouTube transcripts and articles of a place and classify useful sentences into 4 groups: "
        "data_history (numbers, dates, history), visual_description (descriptions of scenery and objects), "
        "comparison_metaphor (comparisons, metaphors) and fact_paradox (interesting facts, paradoxes). "
        "Results are stored in research/<project>/insights/<place>.jsonl. Returns counts per group and a few examples. "
        "Processing is incremental: already processed sources are skipped, and if the result says work remains, "
        "call it again."
    )

    tool_kwargs = ExtractInsightsToolKwargs

    CHUNK_CHARS = 6000
    EXAMPLES_PER_CATEGORY = 2

    def __init__(self, workspace_dir: str | Path, reasoner: ModelReasoner):
        self.store = ResearchProjectStore(workspace_dir)
        self.extractor = LLMExtractor(reasoner)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            project = self.store.load_project(args.project)
            place = self.store.find_place(project, args.place)
        except ResearchProjectError as e:
            return ExtractInsightsToolResult(content=str(e))

        slug = project['slug']
        terms = place_terms(place, args.aliases)
        all_sources = self.store.load_sources(slug)

        sources = [
            s for s in all_sources
            if strip_accents(s.get('place', '')) == strip_accents(place)
            and (args.source_ids is None or s['id'] in args.source_ids)
            and (args.force or not s.get('extracted'))
        ]

        if not sources:
            return ExtractInsightsToolResult(
                content=(
                    f"No unprocessed sources for '{place}'. "
                    f"Save sources with youtube_transcript / save_article first, or use force=true to re-process."
                )
            )

        system_prompt = INSIGHT_EXTRACTION_PROMPT.format(
            title=project['title'],
            place=place,
            keywords=', '.join(project.get('keywords', [])) or '(không có)',
        )

        added: list[dict] = []
        chunks_done = 0
        failed_chunks = 0
        remaining_chunks = 0

        for source in sources:
            units = self._relevant_units(source, terms)
            chunks = chunk_units(units, self.CHUNK_CHARS)
            # Lần trước có thể dừng giữa chừng vì hết max_chunks, chạy tiếp từ chunk đã dừng
            start_chunk = 0 if args.force else source.get('extracted_chunks', 0)

            for chunk_index in range(start_chunk, len(chunks)):
                if chunks_done >= args.max_chunks:
                    remaining_chunks += len(chunks) - chunk_index
                    break

                try:
                    items = self._extract_chunk(system_prompt, source, chunks[chunk_index])
                    added += self.store.append_insights(slug, place, items)
                except LLMExtractorError:
                    failed_chunks += 1

                chunks_done += 1
                source['extracted_chunks'] = chunk_index + 1

            source['extracted'] = source.get('extracted_chunks', 0) >= len(chunks)
            self.store.upsert_source(slug, source)

        return ExtractInsightsToolResult(
            content=self._summary(slug, place, sources, added, chunks_done, failed_chunks, remaining_chunks)
        )

    def _relevant_units(self, source: dict, terms: list[str]) -> list[TextUnit]:
        '''Đọc file nguồn và chỉ giữ phần liên quan đến địa danh'''
        raw = self.store.read_file(source['file'])
        body = raw.split('\n---\n', 1)[-1]
        title_matches = mentions(source.get('title', ''), terms)

        if source['type'] == 'youtube':
            units = parse_transcript(body)
            # Video có tên địa danh trong tiêu đề thì cả video nói về nó, phụ đề hay dùng "nơi đây" thay vì gọi tên
            return units if title_matches else relevance_filter(units, terms, window=1)

        units = split_sentences(body)
        return relevance_filter(units, terms, window=2 if title_matches else 1)

    def _extract_chunk(self, system_prompt: str, source: dict, chunk: list[TextUnit]) -> list[dict]:
        lines = [
            f"[u{i}]" + (f" ({format_timestamp(unit.start)})" if unit.start is not None else "") + f" {unit.text}"
            for i, unit in enumerate(chunk)
        ]
        user_content = (
            f"Nguồn: {source.get('title', '')} ({'phụ đề video YouTube' if source['type'] == 'youtube' else 'bài viết'})\n\n"
            + "\n".join(lines)
        )

        result = self.extractor.ask_json(system_prompt, user_content)

        if isinstance(result, dict):  # Có model bọc mảng trong một object
            result = next((v for v in result.values() if isinstance(v, list)), [])

        items = []
        for raw_item in result:
            if not isinstance(raw_item, dict):
                continue

            category = str(raw_item.get('category', '')).strip()
            text = str(raw_item.get('text', '')).strip()
            if category not in CATEGORIES or not text:
                continue

            unit = _unit_at(chunk, raw_item.get('unit'))
            item = {
                'category': category,
                'text': text,
                'note': str(raw_item.get('note', '')).strip(),
                'source_id': source['id'],
                'start': unit.start if unit else None,
            }
            if raw_item.get('translation_vi'):
                item['translation_vi'] = str(raw_item['translation_vi']).strip()

            items.append(item)

        return items

    def _summary(self, slug, place, sources, added, chunks_done, failed_chunks, remaining_chunks) -> str:
        total = self.store.read_insights(slug, place)
        added_counts = Counter(i['category'] for i in added)
        total_counts = Counter(i['category'] for i in total)

        output = [
            f"Processed {chunks_done} chunks from {len(sources)} sources of '{place}'.",
            f"New insights: {len(added)} | total for this place: {len(total)}",
            "",
        ]

        for category, label in CATEGORIES.items():
            output.append(f"- {category} ({label}): +{added_counts[category]} (total {total_counts[category]})")
            for item in [i for i in added if i['category'] == category][:self.EXAMPLES_PER_CATEGORY]:
                output.append(f"    [{item['id']}] {item['text'][:200]}")

        if failed_chunks:
            output.append(f"\n{failed_chunks} chunks failed because the model did not return valid JSON.")

        if remaining_chunks:
            output.append(f"\nWork remains: about {remaining_chunks} chunks left. Call extract_insights again to continue.")
        else:
            output.append("\nAll sources of this place are processed. Use query_insights to read the results.")

        output.append(f"file: {self.store.relative(self.store.insights_file(slug, place))}")
        return "\n".join(output)


def _unit_at(chunk: list[TextUnit], value) -> TextUnit | None:
    '''Model trả về "unit" dạng 3 hoặc "u3", đổi về đoạn tương ứng để lấy timestamp'''
    try:
        index = int(str(value).lstrip('[u').rstrip(']'))
    except (TypeError, ValueError):
        return None
    return chunk[index] if 0 <= index < len(chunk) else None
