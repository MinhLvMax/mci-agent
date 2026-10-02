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


def parse_transcript(text: str, passage_chars: int = 300) -> list[TextUnit]:
    '''
    Đọc phụ đề dạng "[mm:ss] câu" và gộp các dòng liền nhau thành đoạn khoảng passage_chars ký tự.
    Phụ đề tự động không có dấu câu nên gộp theo độ dài, giữ timestamp của dòng đầu đoạn.
    '''
    units: list[TextUnit] = []
    buffer: list[str] = []
    buffer_start: int | None = None

    for line in text.splitlines():
        match = _TRANSCRIPT_LINE.match(line.strip())
        if not match:
            continue

        if buffer_start is None:
            buffer_start = parse_timestamp(match.group(1))

        buffer.append(match.group(2).strip())

        if sum(len(part) + 1 for part in buffer) >= passage_chars:
            units.append(TextUnit(text=' '.join(buffer), start=buffer_start))
            buffer, buffer_start = [], None

    if buffer:
        units.append(TextUnit(text=' '.join(buffer), start=buffer_start))

    return units


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
