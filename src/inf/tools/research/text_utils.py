import re
import unicodedata
from dataclasses import dataclass


@dataclass
class TextUnit:
    '''Một đơn vị văn bản để lọc/phân loại: 1 câu bài báo hoặc 1 đoạn phụ đề'''
    text: str
    start: int | None = None  # Giây bắt đầu trong video, None với bài báo


def strip_accents(text: str) -> str:
    '''Bỏ dấu tiếng Việt và viết thường để so khớp: "Vịnh Hạ Long" -> "vinh ha long"'''
    text = text.replace('đ', 'd').replace('Đ', 'D')
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', text).strip().lower()


def slugify(text: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', strip_accents(text)).strip('-')
    return slug[:60] or 'untitled'


def format_timestamp(seconds: int) -> str:
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def parse_timestamp(value: str) -> int:
    seconds = 0
    for part in value.split(':'):
        seconds = seconds * 60 + int(part)
    return seconds


_SENTENCE_END = re.compile(r'(?<=[.!?…])\s+(?=[\"“\'(\[]?[A-ZÀ-Ỹ0-9])')


def clean_markdown(text: str) -> str:
    '''Bỏ link, ảnh, chú thích [1] của markdown trích từ web, chỉ giữ chữ'''
    text = re.sub(r'^\s*\[\d+\]:\s*\S+.*$', '', text, flags=re.MULTILINE)  # Dòng định nghĩa link [1]: http...
    text = re.sub(r'!\[[^\]]*\]\[\d+\]|!\[[^\]]*\]\([^)]*\)', '', text)  # Ảnh
    text = re.sub(r'\[\s*([^\]]*?)\s*\]\[\d+\]', r'\1', text)  # [chữ][12] -> chữ
    text = re.sub(r'\[\s*([^\]]*?)\s*\]\([^)]*\)', r'\1', text)  # [chữ](url) -> chữ
    text = re.sub(r'\[\d+\]', '', text)  # Chú thích kiểu Wikipedia [5]
    return text


def split_sentences(text: str) -> list[TextUnit]:
    '''Tách câu cho bài báo: tách theo dòng rồi theo dấu kết thúc câu'''
    units = []

    for line in clean_markdown(text).splitlines():
        line = line.strip().lstrip('#>*- ').strip()

        if len(line) < 20:  # Bỏ tiêu đề mục, menu, dòng rác quá ngắn
            continue

        for sentence in _SENTENCE_END.split(line):
            sentence = sentence.strip()
            if len(sentence) >= 20:
                units.append(TextUnit(text=sentence))

    return units


_TRANSCRIPT_LINE = re.compile(r'^\[(\d+(?::\d+){1,2})\]\s*(.*)$')


def group_passages(lines: list[tuple[int, str]], passage_chars: int = 300) -> list[TextUnit]:
    '''
    Gộp các dòng phụ đề (giây bắt đầu, chữ) liền nhau thành đoạn khoảng passage_chars ký tự.
    Phụ đề tự động không có dấu câu nên gộp theo độ dài, giữ timestamp của dòng đầu đoạn.
    '''
    units: list[TextUnit] = []
    buffer: list[str] = []
    buffer_start: int | None = None

    for start, text in lines:
        if buffer_start is None:
            buffer_start = start

        buffer.append(text)

        if sum(len(part) + 1 for part in buffer) >= passage_chars:
            units.append(TextUnit(text=' '.join(buffer), start=buffer_start))
            buffer, buffer_start = [], None

    if buffer:
        units.append(TextUnit(text=' '.join(buffer), start=buffer_start))

    return units


def parse_transcript(text: str, passage_chars: int = 300) -> list[TextUnit]:
    '''Đọc phụ đề dạng "[mm:ss] câu" (định dạng cũ của youtube_transcript)'''
    lines = []

    for line in text.splitlines():
        match = _TRANSCRIPT_LINE.match(line.strip())
        if match:
            lines.append((parse_timestamp(match.group(1)), match.group(2).strip()))

    return group_passages(lines, passage_chars)


# 00:01:02,345 --> 00:01:04,000 (srt) hoặc 01:02.345 --> ... (vtt, giờ có thể bỏ)
_CUE_TIME = re.compile(r'^((?:\d+:)?\d{1,2}:\d{2})[.,]\d{1,3}\s*-->')
_CUE_TAG = re.compile(r'<[^>]+>')  # Thẻ định dạng/timestamp từng chữ trong vtt: <c>, <00:00:01.000>


def parse_subtitles(text: str, passage_chars: int = 300) -> list[TextUnit]:
    '''
    Đọc phụ đề .srt hoặc .vtt (kể cả phụ đề tự động của YouTube).
    Bỏ số thứ tự, dòng thời gian, thẻ định dạng và các dòng lặp lại liên tiếp
    (vtt tự động hay lặp lại dòng trước khi chữ chạy).
    '''
    lines: list[tuple[int, str]] = []
    current_start: int | None = None
    previous_text = ''

    for raw_line in text.splitlines():
        line = raw_line.strip()

        match = _CUE_TIME.match(line)
        if match:
            current_start = parse_timestamp(match.group(1))
            continue

        if current_start is None or not line or line.isdigit():
            continue  # Header WEBVTT, ghi chú, số thứ tự cue

        cleaned = _CUE_TAG.sub('', line).strip()
        if cleaned and cleaned != previous_text:
            lines.append((current_start, cleaned))
            previous_text = cleaned

    return group_passages(lines, passage_chars)


def to_srt(lines: list[tuple[float, float, str]]) -> str:
    '''Ghi phụ đề chuẩn .srt từ danh sách (giây bắt đầu, thời lượng, chữ)'''

    def stamp(seconds: float) -> str:
        millis = int(round(seconds * 1000))
        hours, rest = divmod(millis, 3_600_000)
        minutes, rest = divmod(rest, 60_000)
        secs, millis = divmod(rest, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    blocks = [
        f"{number}\n{stamp(start)} --> {stamp(start + duration)}\n{text}\n"
        for number, (start, duration, text) in enumerate(lines, 1)
    ]
    return "\n".join(blocks)


def load_units(text: str, suffix: str) -> list[TextUnit]:
    '''Chọn cách đọc theo loại file: phụ đề giữ timestamp, còn lại tách câu'''
    suffix = suffix.lower()

    if suffix in ('.srt', '.vtt'):
        return parse_subtitles(text)

    # File .md cũ dạng "[mm:ss] câu": phần lớn các dòng phải có timestamp, tránh nhận nhầm bài báo
    non_empty = [line for line in text.splitlines() if line.strip()]
    stamped = sum(1 for line in non_empty if _TRANSCRIPT_LINE.match(line.strip()))
    if non_empty and stamped >= len(non_empty) / 2:
        return parse_transcript(text)

    return split_sentences(text)


# Các từ chỉ loại địa danh, bỏ đi để có thêm tên gọi ngắn: "Vịnh Hạ Long" -> "Hạ Long"
_PLACE_PREFIXES = (
    'vinh', 'nui', 'ho', 'dao', 'chua', 'den', 'dinh', 'thac', 'hang', 'dong', 'song', 'bien',
    'pho co', 'thanh pho', 'tp', 'tinh', 'huyen', 'thi xa', 'khu du lich', 'khu', 'quan the',
    'vuon quoc gia', 'cao nguyen', 'deo', 'ban', 'lang', 'cu lao', 'quan dao', 'bai', 'mui',
)


def place_terms(place: str, aliases: list[str] | None = None) -> list[str]:
    '''Danh sách cụm từ (đã bỏ dấu) dùng để nhận ra địa danh trong văn bản'''
    terms = {strip_accents(place)}

    for alias in aliases or []:
        if alias.strip():
            terms.add(strip_accents(alias))

    for term in list(terms):
        for prefix in _PLACE_PREFIXES:
            if term.startswith(prefix + ' ') and len(term) > len(prefix) + 3:
                terms.add(term[len(prefix) + 1:])

    return sorted(terms, key=len, reverse=True)


def mentions(text: str, terms: list[str]) -> bool:
    normalized = strip_accents(text)
    return any(
        re.search(rf'(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])', normalized)
        for term in terms
    )


def relevance_filter(units: list[TextUnit], terms: list[str], window: int = 1) -> list[TextUnit]:
    '''Giữ các đơn vị nhắc tới địa danh/từ khoá, kèm window đơn vị lân cận để không mất ngữ cảnh'''
    keep: set[int] = set()

    for index, unit in enumerate(units):
        if mentions(unit.text, terms):
            keep.update(range(max(0, index - window), min(len(units), index + window + 1)))

    return [units[i] for i in sorted(keep)]


def chunk_units(units: list[TextUnit], max_chars: int = 6000) -> list[list[TextUnit]]:
    chunks: list[list[TextUnit]] = []
    current: list[TextUnit] = []
    size = 0

    for unit in units:
        if current and size + len(unit.text) > max_chars:
            chunks.append(current)
            current, size = [], 0

        current.append(unit)
        size += len(unit.text) + 1

    if current:
        chunks.append(current)

    return chunks
