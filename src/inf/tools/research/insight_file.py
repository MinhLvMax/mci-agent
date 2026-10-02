import json
import re
from dataclasses import dataclass, field

from src.inf.tools.file.helper import WorkspacePathGuard, save_text
from src.inf.tools.research.text_utils import format_timestamp, parse_timestamp

CATEGORIES = {
    'data_history': 'Số liệu & lịch sử',
    'visual_description': 'Miêu tả hình ảnh, vật thể',
    'comparison_metaphor': 'So sánh, ẩn dụ',
    'fact_paradox': 'Facts & nghịch lý',
}


@dataclass
class Insight:
    id: str
    category: str
    text: str
    source: str  # Đường dẫn file nguồn lúc trích
    note: str = ''
    start: int | None = None  # Giây trong video với nguồn phụ đề
    translation: str = ''


@dataclass
class InsightFile:
    """
    File insight dạng Markdown, người đọc được trên giao diện và agent grep được bằng search_files:

        # Insights: Vịnh Hạ Long
        ## Số liệu & lịch sử (data_history)
        - (#vinh-ha-long-1) "Năm 1994, ..." — ghi chú · nguồn: `transcripts/abc.srt` @ 01:03
          - Dịch: ...
        <!-- extract_insights:state {...} -->

    Dòng state cuối file là comment HTML (không hiện khi xem Markdown), lưu tiến độ xử lý từng nguồn
    để extract_insights chạy tiếp được mà không cần file phụ.
    """
    place: str
    insights: list[Insight] = field(default_factory=list)
    state: dict = field(default_factory=dict)
    topic: str = ''


_TITLE = re.compile(r'^# Insights:\s*(.+?)\s*$')
_TOPIC = re.compile(r'^> Chủ đề:\s*(.+?)\s*$')
_SECTION = re.compile(r'^## .*\((\w+)\)\s*$')
_ITEM = re.compile(
    r'^- \(#(?P<id>[^)]+)\) "(?P<text>.*)"(?: — (?P<note>.*))? · nguồn: `(?P<source>[^`]*)`'
    r'(?: @ (?P<start>\d+(?::\d+){1,2}))?\s*$'
)
_TRANSLATION = re.compile(r'^\s+- Dịch:\s*(.*)$')
_STATE = re.compile(r'^<!-- extract_insights:state (.*) -->\s*$')


def parse_insight_file(text: str, default_place: str = '') -> InsightFile:
    result = InsightFile(place=default_place)
    category = None

    for line in text.splitlines():
        if match := _TITLE.match(line):
            result.place = match.group(1)
        elif match := _TOPIC.match(line):
            result.topic = match.group(1)
        elif match := _SECTION.match(line):
            category = match.group(1) if match.group(1) in CATEGORIES else None
        elif (match := _ITEM.match(line)) and category:
            result.insights.append(Insight(
                id=match.group('id'),
                category=category,
                text=match.group('text'),
                note=match.group('note') or '',
                source=match.group('source'),
                start=parse_timestamp(match.group('start')) if match.group('start') else None,
            ))
        elif (match := _TRANSLATION.match(line)) and result.insights:
            result.insights[-1].translation = match.group(1)
        elif match := _STATE.match(line):
            try:
                result.state = json.loads(match.group(1))
            except json.JSONDecodeError:
                result.state = {}

    return result


def render_insight_file(data: InsightFile) -> str:
    lines = [f"# Insights: {data.place}", ""]

    if data.topic:
        lines += [f"> Chủ đề: {data.topic}", ""]

    for category, label in CATEGORIES.items():
        items = [i for i in data.insights if i.category == category]
        lines += [f"## {label} ({category})", ""]

        if not items:
            lines += ["_Chưa có._", ""]
            continue

        for item in items:
            note = f" — {_one_line(item.note)}" if item.note else ""
            start = f" @ {format_timestamp(item.start)}" if item.start is not None else ""
            lines.append(f'- (#{item.id}) "{_one_line(item.text)}"{note} · nguồn: `{item.source}`{start}')
            if item.translation:
                lines.append(f"  - Dịch: {_one_line(item.translation)}")

        lines.append("")

    lines.append(f"<!-- extract_insights:state {json.dumps(data.state, ensure_ascii=False)} -->")
    return "\n".join(lines) + "\n"


def read_insight_file(guard: WorkspacePathGuard, relative_path: str, default_place: str = '') -> InsightFile | None:
    path = guard.resolve(relative_path)
    if not path.is_file():
        return None
    return parse_insight_file(path.read_text(encoding='utf-8'), default_place)


def write_insight_file(guard: WorkspacePathGuard, relative_path: str, data: InsightFile) -> str:
    return save_text(guard, relative_path, render_insight_file(data))


def _one_line(text: str) -> str:
    '''Mỗi insight nằm trên một dòng để parse lại được'''
    return ' '.join(text.split()).replace('`', "'")
