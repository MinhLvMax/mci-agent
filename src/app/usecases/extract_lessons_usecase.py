import json
import re
from dataclasses import dataclass

from src.app.ports.model_reasoner import ModelReasoner
from src.app.services.memory_service import MemoryService
from src.app.services.postgre_db.postgre_memories_repository import PostgreMemoriesRepository
from src.dom.context import Context
from src.dom.decision.final_decision import FinalDecision
from src.dom.entities.memory import Memory
from src.dom.message.text_message import TextMessage
from src.config import Config

LESSON_PROMPT = """Bạn là bộ phận "rút kinh nghiệm" của một trợ lý AI dùng trong doanh nghiệp.
Bạn đọc một lượt trao đổi (và góp ý nếu có) rồi quyết định có bài học nào đáng ghi nhớ LÂU DÀI cho các lần sau không.

Có bài học khi người dùng:
- sửa lỗi hoặc chê câu trả lời trước, và cách sửa đó nên áp dụng cho các lần sau;
- nêu sở thích về cách trả lời (độ dài, định dạng, giọng văn, ngôn ngữ...);
- mô tả quy trình, thuật ngữ, quy định hoặc sự thật về công ty/công việc mà trợ lý cần nhớ.

KHÔNG có bài học khi: chỉ là yêu cầu công việc bình thường, chi tiết chỉ dùng cho riêng việc đang làm,
lời chào/cảm ơn, thông tin nhạy cảm (mật khẩu, khoá API...), hoặc điều đã có trong danh sách ghi nhớ hiện có.
Phần lớn các lượt KHÔNG có bài học. Khi nghi ngờ, trả danh sách rỗng.

Phạm vi:
- "user": sở thích/cách làm riêng của người này.
- "org": quy định, thuật ngữ, quy trình, sự thật áp dụng cho cả công ty (sẽ được admin duyệt).

Mỗi bài học viết thành MỘT câu chỉ dẫn ngắn, tự hiểu được khi không có hội thoại, cùng ngôn ngữ với người dùng.
Nếu bài học sửa/thay một ghi nhớ hiện có thì điền replace_memory_id là id của ghi nhớ đó.

Chỉ trả về JSON đúng dạng, không giải thích:
{"lessons": [{"scope": "user" | "org", "content": "...", "replace_memory_id": null}]}"""


@dataclass
class ExtractLessonsUseCaseCommand:
    user_id: int
    conversation_id: int | None
    user_message: str = ""
    previous_assistant_reply: str = ""  # Câu trả lời mà tin nhắn user đang phản hồi/sửa
    assistant_reply: str = ""
    feedback_content: str = ""
    feedback_rating: int | None = None
    feedback_kind: str | None = None
    feedback_id: int | None = None


class ExtractLessonsUsecase:
    '''
    Gọi LLM xem lượt chat/góp ý vừa rồi có bài học lâu dài nào không, có thì lưu vào memories.
    Không dùng từ khoá cố định: model tự quyết, phần lớn lượt sẽ trả danh sách rỗng.
    '''
    INPUT_CHARS = 2000  # Mỗi phần chỉ gửi đoạn đầu cho rẻ, bài học thường nằm ở tin nhắn user
    MAX_LESSONS = 3  # Chặn model trả quá nhiều bài học từ một lượt

    def __init__(
            self,
            reasoner: ModelReasoner,
            memory_service: MemoryService,
            memories_repository: PostgreMemoriesRepository,
    ):
        self.reasoner = reasoner
        self.memory_service = memory_service
        self.memories_repository = memories_repository

    def execute(self, command: ExtractLessonsUseCaseCommand) -> list[Memory]:
        existing = self.memories_repository.list_for_extractor(command.user_id)
        lessons = self._ask_model(command, existing)

        saved = []
        for lesson in lessons[:self.MAX_LESSONS]:
            try:
                saved.append(self.memory_service.remember(
                    user_id=command.user_id,
                    scope=lesson["scope"],
                    content=lesson["content"],
                    source='feedback' if command.feedback_id is not None else 'extractor',
                    conversation_id=command.conversation_id,
                    feedback_id=command.feedback_id,
                    replace_memory_id=lesson.get("replace_memory_id"),
                ))
            except Exception:
                # Một bài học lỗi (vd replace_memory_id sai) thì bỏ qua, các bài khác vẫn lưu
                Config.logger.exception('Save extracted lesson failed: %s', lesson)
                self.memories_repository.connection.rollback()

        return saved

    def _ask_model(self, command: ExtractLessonsUseCaseCommand, existing: list[Memory]) -> list[dict]:
        context = Context(messages=[
            TextMessage(role='system', content=LESSON_PROMPT),
            TextMessage(role='user', content=self._build_input(command, existing)),
        ])

        decision = self.reasoner.decide(context=context, tools=[])
        if not isinstance(decision, FinalDecision):
            return []

        return parse_lessons(decision.final_content)

    def _build_input(self, command: ExtractLessonsUseCaseCommand, existing: list[Memory]) -> str:
        n = self.INPUT_CHARS
        parts = []

        if existing:
            listing = "\n".join(
                f"- #{m.id} [{m.scope}{', chờ duyệt' if m.status == 'pending' else ''}] {m.content}"
                for m in existing
            )
            parts.append(f"Ghi nhớ hiện có:\n{listing}")
        else:
            parts.append("Ghi nhớ hiện có: (chưa có)")

        if command.previous_assistant_reply:
            parts.append(f"Câu trả lời trước đó của trợ lý:\n{command.previous_assistant_reply[:n]}")
        if command.user_message:
            parts.append(f"Tin nhắn người dùng:\n{command.user_message[:n]}")
        if command.assistant_reply:
            parts.append(f"Câu trả lời mới của trợ lý:\n{command.assistant_reply[:n]}")

        if command.feedback_content or command.feedback_rating is not None:
            rating = {1: "hài lòng", -1: "chưa hài lòng"}.get(command.feedback_rating, "không đánh giá")
            parts.append(
                f"Góp ý của người dùng (đánh giá: {rating}, loại: {command.feedback_kind or 'không rõ'}):\n"
                f"{command.feedback_content[:n]}"
            )

        return "\n\n".join(parts)


def parse_lessons(text: str) -> list[dict]:
    '''Lấy danh sách bài học hợp lệ từ output của model, sai định dạng thì coi như không có'''
    match = re.search(r'\{.*\}', text or "", flags=re.DOTALL)  # Model đôi khi bọc JSON trong ```json
    if not match:
        return []

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    lessons = data.get("lessons") if isinstance(data, dict) else None
    if not isinstance(lessons, list):
        return []

    valid = []
    for lesson in lessons:
        if not isinstance(lesson, dict):
            continue
        content = lesson.get("content")
        if lesson.get("scope") not in ('user', 'org') or not isinstance(content, str) or not content.strip():
            continue

        replace_id = lesson.get("replace_memory_id")
        valid.append({
            "scope": lesson["scope"],
            "content": content.strip(),
            "replace_memory_id": replace_id if isinstance(replace_id, int) else None,
        })

    return valid
