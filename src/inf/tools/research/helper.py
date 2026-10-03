import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from src.app.ports.model_reasoner import ModelReasoner
from src.dom.context import Context
from src.dom.decision.final_decision import FinalDecision
from src.dom.message.text_message import TextMessage
from src.inf.tools.file.helper import WorkspacePathGuard, save_text
from src.config import Config


class ResearchHelper:
    '''
    Phần dùng chung của nhóm tool research, chỉ chứa thứ có từ 2 tool trở lên cần:
    - định dạng file insight (đọc/ghi, trạng thái làm việc nằm ngay trong file)
    - gọi model một lượt không tool
    - đọc file nguồn thành các đoạn
    - nhận ra file kết quả của nhóm research để không đọc nhầm như nguồn

    Không chứa kiến thức nghiệp vụ: nhóm phân loại, tiêu chí... do skill truyền vào từng tool.
    '''

    # Dòng đầu mọi file kết quả của nhóm research (comment HTML, không hiện khi xem Markdown)
    GENERATED_MARKER = '<!-- research:generated -->'
    _LEGACY_HEADERS = ('# Insights:', '# Câu chuyện độc đáo')  # File tạo trước khi có marker

    class LLMError(RuntimeError):
        pass

    @dataclass
    class TextUnit:
        '''Một đơn vị văn bản: 1 câu bài viết hoặc 1 đoạn phụ đề'''
        text: str
        start: int | None = None  # Giây bắt đầu trong video, None với bài viết

    @dataclass
    class Insight:
        id: str
        category: str
        text: str
        source: str  # Đường dẫn file nguồn lúc trích
        note: str = ''
        start: int | None = None  # Giây trong video với nguồn phụ đề
        translation: str = ''
        score: int = 0  # 1-3 do model chấm, 0 là file cũ chưa chấm
        check: str = ''  # Nhãn đối chiếu nguồn do verify_claims ghi, vd "✔ 2 nguồn"

    @dataclass
    class InsightFile:
        """
        File insight dạng Markdown, người đọc được trên giao diện và agent grep được:

            <!-- research:generated -->
            # Insights: <đối tượng>
            > Chủ đề: ...
            ## <tên nhóm> (<khóa nhóm>)
            - (#id) [★★★] "câu trích" — ghi chú · nguồn: `sources/a.srt` @ 01:03 {✔ 2 nguồn}
              - Dịch: ...
            <!-- research:state {...} -->

        Dòng state cuối file lưu trạng thái làm việc (bộ nhóm, tiến độ từng nguồn)
        để các tool đọc lại và làm tiếp, không cần file phụ.
        """
        subject: str
        categories: dict[str, str] = field(default_factory=dict)  # khóa -> mô tả, theo thứ tự hiển thị
        insights: list = field(default_factory=list)  # list[ResearchHelper.Insight]
        state: dict = field(default_factory=dict)
        topic: str = ''

    _TITLE = re.compile(r'^# Insights:\s*(.+?)\s*$')
    _TOPIC = re.compile(r'^> Chủ đề:\s*(.+?)\s*$')
    _SECTION = re.compile(r'^## (?P<label>.*?)\s*\((?P<key>[a-z0-9_]+)\)\s*$')
    _ITEM = re.compile(
        r'^- \(#(?P<id>[^)]+)\)(?: \[(?P<stars>★{1,3})\])? "(?P<text>.*)"(?: — (?P<note>.*?))? · nguồn: `(?P<source>[^`]*)`'
        r'(?: @ (?P<start>\d+(?::\d+){1,2}))?(?: \{(?P<check>[^}]*)\})?\s*$'
    )
    _TRANSLATION = re.compile(r'^\s+- Dịch:\s*(.*)$')
    _STATE = re.compile(r'^<!-- (?:research|extract_insights):state (.*) -->\s*$')  # extract_insights: định dạng cũ

    # ------------------------------------------------------------------
    # Chuỗi
    # ------------------------------------------------------------------

    @staticmethod
    def strip_accents(text: str) -> str:
        '''Bỏ dấu tiếng Việt và viết thường để so khớp: "Vịnh Hạ Long" -> "vinh ha long"'''
        text = text.replace('đ', 'd').replace('Đ', 'D')
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        return re.sub(r'\s+', ' ', text).strip().lower()

    @staticmethod
    def format_timestamp(seconds: int) -> str:
        hours, rest = divmod(int(seconds), 3600)
        minutes, secs = divmod(rest, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def _parse_timestamp(value: str) -> int:
        seconds = 0
        for part in value.split(':'):
            seconds = seconds * 60 + int(part)
        return seconds

    @staticmethod
    def category_label(description: str) -> str:
        '''Tên nhóm hiển thị ở heading: phần trước dấu ":" của mô tả'''
        label = description.split(':', 1)[0].strip()
        return label[:60] or description[:60]

    # ------------------------------------------------------------------
    # File kết quả
    # ------------------------------------------------------------------

    @classmethod
    def is_generated(cls, path: Path) -> bool:
        '''File do nhóm research tạo ra, không phải là nguồn'''
        try:
            with path.open(encoding='utf-8', errors='replace') as file:
                first_line = file.readline().strip()
        except OSError:
            return False
        return first_line == cls.GENERATED_MARKER or first_line.startswith(cls._LEGACY_HEADERS)

    @classmethod
    def save_generated(cls, guard: WorkspacePathGuard, relative_path: str, content: str) -> str:
        '''Ghi file kết quả kèm marker ở dòng đầu'''
        return save_text(guard, relative_path, f"{cls.GENERATED_MARKER}\n{content}")

    # ------------------------------------------------------------------
    # File insight
    # ------------------------------------------------------------------

    @classmethod
    def read_insights(cls, guard: WorkspacePathGuard, relative_path: str, default_subject: str = ''):
        '''Đọc file insight, không tồn tại thì trả về None'''
        path = guard.resolve(relative_path)
        if not path.is_file():
            return None
        return cls.parse_insights(path.read_text(encoding='utf-8'), default_subject)

    @classmethod
    def write_insights(cls, guard: WorkspacePathGuard, relative_path: str, data: 'ResearchHelper.InsightFile') -> str:
        return cls.save_generated(guard, relative_path, cls.render_insights(data))

    @classmethod
    def parse_insights(cls, text: str, default_subject: str = '') -> 'ResearchHelper.InsightFile':
        result = cls.InsightFile(subject=default_subject)
        heading_categories: dict[str, str] = {}
        category = None

        for line in text.splitlines():
            if match := cls._TITLE.match(line):
                result.subject = match.group(1)
            elif match := cls._TOPIC.match(line):
                result.topic = match.group(1)
            elif match := cls._SECTION.match(line):
                category = match.group('key')
                heading_categories.setdefault(category, match.group('label'))
            elif (match := cls._ITEM.match(line)) and category:
                result.insights.append(cls.Insight(
                    id=match.group('id'),
                    category=category,
                    text=match.group('text'),
                    note=match.group('note') or '',
                    source=match.group('source'),
                    start=cls._parse_timestamp(match.group('start')) if match.group('start') else None,
                    score=len(match.group('stars') or ''),
                    check=match.group('check') or '',
                ))
            elif (match := cls._TRANSLATION.match(line)) and result.insights:
                result.insights[-1].translation = match.group(1)
            elif match := cls._STATE.match(line):
                try:
                    result.state = json.loads(match.group(1))
                except json.JSONDecodeError:
                    result.state = {}

        # Bộ nhóm lưu trong state là chuẩn, file cũ chưa có thì lấy từ heading
        saved = result.state.get('categories')
        result.categories = dict(saved) if isinstance(saved, dict) and saved else {}
        for key, label in heading_categories.items():
            result.categories.setdefault(key, label)

        return result

    @classmethod
    def render_insights(cls, data: 'ResearchHelper.InsightFile') -> str:
        lines = [f"# Insights: {data.subject}", ""]

        if data.topic:
            lines += [f"> Chủ đề: {data.topic}", ""]

        # Nhóm có câu nhưng không còn trong bộ nhóm (hiếm) vẫn được giữ lại ở cuối
        keys = list(data.categories) + sorted({i.category for i in data.insights} - set(data.categories))

        for key in keys:
            items = [i for i in data.insights if i.category == key]
            lines += [f"## {cls.category_label(data.categories.get(key, key))} ({key})", ""]

            if not items:
                lines += ["_Chưa có._", ""]
                continue

            for item in items:
                stars = f" [{'★' * item.score}]" if item.score else ""
                note = f" — {cls._one_line(item.note)}" if item.note else ""
                start = f" @ {cls.format_timestamp(item.start)}" if item.start is not None else ""
                check = f" {{{cls._one_line(item.check).replace('{', '(').replace('}', ')')}}}" if item.check else ""
                lines.append(
                    f'- (#{item.id}){stars} "{cls._one_line(item.text)}"{note} · nguồn: `{item.source}`{start}{check}'
                )
                if item.translation:
                    lines.append(f"  - Dịch: {cls._one_line(item.translation)}")

            lines.append("")

        state = {**data.state, 'categories': data.categories}
        lines.append(f"<!-- research:state {json.dumps(state, ensure_ascii=False)} -->")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _one_line(text: str) -> str:
        '''Mỗi insight nằm trên một dòng để parse lại được'''
        return ' '.join(text.split()).replace('`', "'")

    # ------------------------------------------------------------------
    # Đọc nguồn
    # ------------------------------------------------------------------

    _CUE_TIME = re.compile(r'^((?:\d+:)?\d{1,2}:\d{2})[.,]\d{1,3}\s*-->')  # 00:01:02,345 --> (srt) / 01:02.345 --> (vtt)
    _CUE_TAG = re.compile(r'<[^>]+>')  # Thẻ định dạng/timestamp từng chữ trong vtt
    _TRANSCRIPT_LINE = re.compile(r'^\[(\d+(?::\d+){1,2})\]\s*(.*)$')  # "[mm:ss] câu", định dạng phụ đề cũ
    _SENTENCE_END = re.compile(r'(?<=[.!?…])\s+(?=[\"“\'(\[]?[A-ZÀ-Ỹ0-9])')

    SUBTITLE_SUFFIXES = {'.srt', '.vtt'}
    TEXT_SUFFIXES = {'.txt', '.md', '.markdown', '.srt', '.vtt'}

    @classmethod
    def load_units(cls, path: Path) -> list['ResearchHelper.TextUnit']:
        '''Đọc file nguồn: phụ đề thành các đoạn có timestamp, còn lại tách câu'''
        text = path.read_text(encoding='utf-8', errors='replace')

        if path.suffix.lower() in cls.SUBTITLE_SUFFIXES:
            return cls._group_passages(cls._subtitle_lines(text))

        # File "[mm:ss] câu": phần lớn các dòng phải có timestamp, tránh nhận nhầm bài viết
        non_empty = [line for line in text.splitlines() if line.strip()]
        stamped = [cls._TRANSCRIPT_LINE.match(line.strip()) for line in non_empty]
        if non_empty and sum(1 for m in stamped if m) >= len(non_empty) / 2:
            return cls._group_passages([(cls._parse_timestamp(m.group(1)), m.group(2).strip()) for m in stamped if m])

        return cls._split_sentences(text)

    @classmethod
    def _subtitle_lines(cls, text: str) -> list[tuple[int, str]]:
        '''Bỏ số thứ tự, dòng thời gian, thẻ định dạng và dòng lặp liên tiếp (vtt tự động hay lặp)'''
        lines: list[tuple[int, str]] = []
        current_start: int | None = None
        previous = ''

        for raw in text.splitlines():
            line = raw.strip()

            if match := cls._CUE_TIME.match(line):
                current_start = cls._parse_timestamp(match.group(1))
                continue

            if current_start is None or not line or line.isdigit():
                continue

            cleaned = cls._CUE_TAG.sub('', line).strip()
            if cleaned and cleaned != previous:
                lines.append((current_start, cleaned))
                previous = cleaned

        return lines

    @classmethod
    def _group_passages(cls, lines: list[tuple[int, str]], passage_chars: int = 300) -> list['ResearchHelper.TextUnit']:
        '''Phụ đề tự động không có dấu câu nên gộp các dòng liền nhau theo độ dài, giữ timestamp dòng đầu'''
        units = []
        buffer: list[str] = []
        buffer_start: int | None = None

        for start, text in lines:
            if buffer_start is None:
                buffer_start = start
            buffer.append(text)

            if sum(len(part) + 1 for part in buffer) >= passage_chars:
                units.append(cls.TextUnit(text=' '.join(buffer), start=buffer_start))
                buffer, buffer_start = [], None

        if buffer:
            units.append(cls.TextUnit(text=' '.join(buffer), start=buffer_start))

        return units

    @classmethod
    def _split_sentences(cls, text: str) -> list['ResearchHelper.TextUnit']:
        '''Tách câu cho bài viết: bỏ link/ảnh markdown, tách theo dòng rồi theo dấu kết thúc câu'''
        text = re.sub(r'^\s*\[\d+\]:\s*\S+.*$', '', text, flags=re.MULTILINE)  # Dòng định nghĩa link [1]: http...
        text = re.sub(r'!\[[^\]]*\]\[\d+\]|!\[[^\]]*\]\([^)]*\)', '', text)  # Ảnh
        text = re.sub(r'\[\s*([^\]]*?)\s*\]\[\d+\]', r'\1', text)  # [chữ][12] -> chữ
        text = re.sub(r'\[\s*([^\]]*?)\s*\]\([^)]*\)', r'\1', text)  # [chữ](url) -> chữ
        text = re.sub(r'\[\d+\]', '', text)  # Chú thích kiểu Wikipedia [5]

        units = []
        for line in text.splitlines():
            line = line.strip().lstrip('#>*- ').strip()
            if len(line) < 20:  # Tiêu đề mục, menu, dòng rác
                continue

            for sentence in cls._SENTENCE_END.split(line):
                sentence = sentence.strip()
                if len(sentence) >= 20:
                    units.append(cls.TextUnit(text=sentence))

        return units

    # ------------------------------------------------------------------
    # Gọi model
    # ------------------------------------------------------------------

    @classmethod
    def ask_text(cls, reasoner: ModelReasoner, system_prompt: str, user_content: str) -> str:
        '''Gọi model một lượt không tool, trả về văn bản'''
        decision = reasoner.decide(
            context=Context(messages=[
                TextMessage(role='system', content=system_prompt),
                TextMessage(role='user', content=user_content),
            ]),
            tools=[],
        )

        if not isinstance(decision, FinalDecision) or not decision.final_content.strip():
            raise cls.LLMError('model returned no text')

        return decision.final_content

    @classmethod
    def ask_json(cls, reasoner: ModelReasoner, system_prompt: str, user_content: str, retries: int = 1) -> list | dict:
        '''Gọi model một lượt không tool và nhận về JSON, sai định dạng thì cho model sửa lại'''
        messages = [
            TextMessage(role='system', content=system_prompt),
            TextMessage(role='user', content=user_content),
        ]
        last_error = None

        for _ in range(retries + 1):
            decision = reasoner.decide(context=Context(messages=list(messages)), tools=[])

            if not isinstance(decision, FinalDecision):
                last_error = 'model tried to call a tool instead of answering'
                continue

            try:
                return cls._parse_json(decision.final_content)
            except ValueError as e:
                last_error = str(e)
                Config.logger.debug(f'LLM returned invalid JSON: {decision.final_content[:300]}')
                messages = messages[:2] + [
                    TextMessage(role='assistant', content=decision.final_content),
                    TextMessage(role='user', content='Câu trả lời không phải JSON hợp lệ. Chỉ trả về đúng JSON theo mẫu.'),
                ]

        raise cls.LLMError(f'LLM did not return valid JSON: {last_error}')

    @staticmethod
    def _parse_json(text: str) -> list | dict:
        '''Lấy JSON từ câu trả lời, chấp nhận cả khi bị bọc trong ```json ... ``` hoặc có chữ thừa'''
        text = text.strip()

        fenced = re.search(r'```(?:json)?\s*(.*?)```', text, flags=re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        for open_char, close_char in (('[', ']'), ('{', '}')):
            start, end = text.find(open_char), text.rfind(close_char)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    continue

        raise ValueError('response is not valid JSON')

    @staticmethod
    def as_list(result: list | dict) -> list:
        '''Có model bọc mảng trong một object, lấy mảng đầu tiên bên trong'''
        if isinstance(result, dict):
            return next((v for v in result.values() if isinstance(v, list)), [])
        return result if isinstance(result, list) else []
