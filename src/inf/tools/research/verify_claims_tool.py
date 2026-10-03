import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from src.app.ports.model_reasoner import ModelReasoner
from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError
from src.inf.tools.research.helper import ResearchHelper

H = ResearchHelper

VERIFY_PROMPT = """Bạn là người kiểm chứng thông tin. Với mỗi nhận định dưới đây, đọc các đoạn trích từ NGUỒN KHÁC
(mỗi đoạn có mã [P..]) và cho biết các đoạn đó xác nhận, mâu thuẫn hay không nói tới nhận định.

- "supported": có đoạn nói cùng một sự việc với cùng con số/chi tiết (cách diễn đạt có thể khác, ngôn ngữ có thể khác).
- "contradicted": có đoạn nói cùng một sự việc nhưng con số/chi tiết khác.
- "not_found": các đoạn không nói tới sự việc đó.

Yêu cầu riêng:
{instructions}

Chỉ dựa vào các đoạn được cung cấp, không dùng hiểu biết riêng.
Chỉ trả lời bằng một mảng JSON, mỗi nhận định một phần tử, không giải thích gì thêm:
[{{"id": "<id nhận định>", "verdict": "supported", "passages": ["P1"], "note": "<1 câu, nêu chi tiết khác nhau nếu mâu thuẫn>"}}]
"""

_NUMBER = re.compile(r'\d+(?:[.,]\d+)*')
_WORD = re.compile(r'[a-z0-9]{4,}')


class VerifyClaimsToolKwargs(ToolKwargs):
    insight_path: str = Field(
        description="Insight file written by extract_insights whose sentences should be checked."
    )

    source_paths: list[str] = Field(
        default_factory=list,
        description=(
            "Extra source files or folders to check against. The sources already recorded in the insight file "
            "are always used."
        )
    )

    ids: list[str] = Field(
        default_factory=list,
        description="Only check these insight ids."
    )

    categories: list[str] = Field(
        default_factory=list,
        description="Only check insights in these groups (keys as in the insight file)."
    )

    min_score: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Only check insights scored at least this much."
    )

    only_with_numbers: bool = Field(
        default=False,
        description="Only check insights that contain a number (figures, dates, measurements)."
    )

    max_claims: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Maximum number of insights checked in this call. Call again to continue."
    )

    instructions: str = Field(
        default='',
        description="Extra rules for judging, e.g. how strict to be with rounded numbers."
    )

    force: bool = Field(
        default=False,
        description="Check again insights that already have a label."
    )


@dataclass
class VerifyClaimsToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class VerifyClaimsTool(Tool):
    tool_name = 'verify_claims'
    tool_description = (
        "Cross-check sentences of an insight file against the OTHER sources (each sentence is compared with sources "
        "different from the one it came from). Writes a label next to each checked sentence in the insight file: "
        "'✔ N nguồn' (confirmed by N sources in total), '⚠ 1 nguồn' (only its own source) or "
        "'✖ mâu thuẫn: <source>' (another source says otherwise). Select which sentences to check with "
        "ids / categories / min_score / only_with_numbers."
    )

    tool_kwargs = VerifyClaimsToolKwargs

    PASSAGES_PER_SOURCE = 3
    PASSAGES_PER_CLAIM = 8
    CLAIMS_PER_CALL = 5

    def __init__(self, workspace_dir: str | Path, reasoner: ModelReasoner):
        self.path_guard = WorkspacePathGuard(workspace_dir)
        self.reasoner = reasoner

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            data = H.read_insights(self.path_guard, args.insight_path)
            if data is None:
                return VerifyClaimsToolResult(content=f"Insight file not found: {args.insight_path}")

            sources = self._load_sources(data, args.source_paths)
        except WorkspacePathError as e:
            return VerifyClaimsToolResult(content=f"Access denied: {e}")

        candidates = [i for i in data.insights if self._wanted(i, args)]
        claims = candidates[:args.max_claims]

        if not claims:
            return VerifyClaimsToolResult(content="No insight matches the selection (or all are already checked).")

        if len(sources) < 2:
            return VerifyClaimsToolResult(
                content="Need at least 2 readable sources to cross-check. Add more with source_paths."
            )

        # Phần máy: tìm đoạn có thể nói cùng sự việc ở các nguồn khác
        passages_by_claim = {claim.id: self._find_passages(claim, sources) for claim in claims}

        verdicts: dict[str, tuple[str, list[str], str]] = {}
        failed = 0

        to_ask = [c for c in claims if passages_by_claim[c.id]]
        for claim in claims:
            if not passages_by_claim[claim.id]:
                verdicts[claim.id] = ('not_found', [], '')

        # Phần model: mỗi lượt vài nhận định cùng các đoạn tìm được
        for start in range(0, len(to_ask), self.CLAIMS_PER_CALL):
            batch = to_ask[start:start + self.CLAIMS_PER_CALL]
            try:
                verdicts.update(self._judge(batch, passages_by_claim, args.instructions))
            except H.LLMError:
                failed += len(batch)

        for claim in claims:
            if claim.id in verdicts:
                claim.check = _label(*verdicts[claim.id][:2])

        try:
            H.write_insights(self.path_guard, args.insight_path, data)
        except WorkspacePathError as e:
            return VerifyClaimsToolResult(content=f"Cannot save '{args.insight_path}': {e}")

        return VerifyClaimsToolResult(
            content=self._summary(args.insight_path, claims, verdicts, failed, len(candidates) - len(claims))
        )

    @staticmethod
    def _wanted(insight, args: VerifyClaimsToolKwargs) -> bool:
        if insight.check and not args.force:
            return False
        if args.ids and insight.id not in args.ids:
            return False
        if args.categories and insight.category not in args.categories:
            return False
        if insight.score < args.min_score:
            return False
        if args.only_with_numbers and not _NUMBER.search(insight.text + ' ' + insight.translation):
            return False
        return True

    def _load_sources(self, data, extra_paths: list[str]) -> dict[str, list]:
        '''Nguồn ghi trong file insight + nguồn thêm, mỗi nguồn đọc thành các đoạn'''
        paths: dict[str, Path] = {}

        for source in dict.fromkeys(i.source for i in data.insights):
            try:
                path = self.path_guard.resolve(source)
            except WorkspacePathError:
                continue  # Nguồn là link hoặc đường dẫn lạ thì bỏ qua
            if path.is_file():
                paths[source] = path

        for raw in extra_paths:
            path = self.path_guard.resolve(raw)
            candidates = (
                sorted(p for p in path.rglob('*') if p.is_file() and p.suffix.lower() in H.TEXT_SUFFIXES)
                if path.is_dir() else [path] if path.is_file() else []
            )
            for candidate in candidates:
                if not H.is_generated(candidate):
                    paths.setdefault(self.path_guard.to_relative(candidate).replace('\\', '/'), candidate)

        return {source: H.load_units(path) for source, path in paths.items()}

    def _find_passages(self, claim, sources: dict[str, list]) -> list[tuple[str, object]]:
        '''Chấm điểm từng đoạn của các nguồn khác theo số và từ chung với nhận định, lấy các đoạn cao nhất'''
        claim_text = claim.text + ' ' + claim.translation
        numbers = _numbers(claim_text)
        words = set(_WORD.findall(H.strip_accents(claim_text)))
        found = []

        for source, units in sources.items():
            if source == claim.source:
                continue

            scored = []
            for unit in units:
                unit_numbers = _numbers(unit.text)
                unit_words = set(_WORD.findall(H.strip_accents(unit.text)))
                same = numbers & unit_numbers
                # Số mâu thuẫn thì khác nhau, nên số cùng độ lớn (cùng số chữ số) cũng đáng đưa cho model xét
                similar = {len(n) for n in numbers - same} & {len(n) for n in unit_numbers - same}
                shared_words = words & unit_words
                score = 3 * len(same) + len(similar) + len(shared_words)

                # Có số trong nhận định thì đoạn phải có số chung / số cùng độ lớn, hoặc nhiều từ chung
                if score > 0 and (not numbers or same or similar or len(shared_words) >= 3):
                    scored.append((score, unit))

            scored.sort(key=lambda pair: -pair[0])
            found += [(score, source, unit) for score, unit in scored[:self.PASSAGES_PER_SOURCE]]

        found.sort(key=lambda item: -item[0])
        return [(source, unit) for _, source, unit in found[:self.PASSAGES_PER_CLAIM]]

    def _judge(self, batch: list, passages_by_claim: dict, instructions: str) -> dict:
        blocks = []
        passage_sources: dict[str, str] = {}
        number = 0

        for claim in batch:
            lines = [f'Nhận định [{claim.id}]: "{claim.text}"' + (f' (dịch: {claim.translation})' if claim.translation else '')]
            for source, unit in passages_by_claim[claim.id]:
                number += 1
                passage_id = f"P{number}"
                passage_sources[passage_id] = source
                lines.append(f"  [{passage_id}] ({source}) {unit.text}")
            blocks.append("\n".join(lines))

        result = H.as_list(H.ask_json(
            self.reasoner,
            VERIFY_PROMPT.format(instructions=instructions.strip() or '(không có)'),
            "\n\n".join(blocks),
        ))

        ids = {claim.id for claim in batch}
        verdicts = {}

        for raw in result:
            if not isinstance(raw, dict) or raw.get('id') not in ids:
                continue

            verdict = str(raw.get('verdict', '')).strip()
            if verdict not in ('supported', 'contradicted', 'not_found'):
                continue

            sources = list(dict.fromkeys(
                passage_sources[p] for p in raw.get('passages') or [] if p in passage_sources
            ))
            verdicts[raw['id']] = (verdict, sources, str(raw.get('note', '')).strip())

        # Model bỏ sót nhận định nào thì coi như chưa tìm thấy
        for claim in batch:
            verdicts.setdefault(claim.id, ('not_found', [], ''))

        return verdicts

    @staticmethod
    def _summary(insight_path: str, claims: list, verdicts: dict, failed: int, remaining: int) -> str:
        counts = Counter(verdicts[c.id][0] for c in claims if c.id in verdicts)

        output = [
            f"Checked {len(claims) - failed}/{len(claims)} insights in {insight_path}.",
            f"- confirmed by other sources (✔): {counts['supported']}",
            f"- only one source (⚠): {counts['not_found']}",
            f"- contradicted (✖): {counts['contradicted']}",
        ]

        contradicted = [c for c in claims if verdicts.get(c.id, ('',))[0] == 'contradicted']
        if contradicted:
            output.append("\nContradicted:")
            for claim in contradicted:
                note = verdicts[claim.id][2]
                output.append(f"  (#{claim.id}) {claim.text[:150]}" + (f" → {note}" if note else ""))

        if failed:
            output.append(f"\n{failed} insights not checked because the model did not return valid JSON. Call again.")

        if remaining:
            output.append(f"\n{remaining} more insights match the selection. Call verify_claims again to continue.")

        return "\n".join(output)


def _numbers(text: str) -> set[str]:
    '''Các con số trong câu, bỏ dấu phân cách để "1,553" và "1.553" và "1553" khớp nhau'''
    return {re.sub(r'[.,]', '', n) for n in _NUMBER.findall(text)}


def _label(verdict: str, sources: list[str]) -> str:
    if verdict == 'contradicted':
        return f"✖ mâu thuẫn: {', '.join(_short(s) for s in sources) or 'nguồn khác'}"
    if verdict == 'supported':
        # +1 là nguồn gốc của chính câu đó; model quên ghi mã đoạn thì tính ít nhất 1 nguồn khác
        return f"✔ {max(len(sources), 1) + 1} nguồn"
    return "⚠ 1 nguồn"


def _short(source: str) -> str:
    return source.rsplit('/', 1)[-1]
