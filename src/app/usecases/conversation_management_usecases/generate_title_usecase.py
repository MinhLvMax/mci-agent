import re
from dataclasses import dataclass

from src.app.ports.model_reasoner import ModelReasoner
from src.app.ports.repositories import ConversationsRepository
from src.dom.context import Context
from src.dom.decision.final_decision import FinalDecision
from src.dom.message.text_message import TextMessage
from src.config import Config

# Tên tạm khi vừa tạo hội thoại. Còn giữ tên này thì AI được đặt tên lại,
# user đã đổi sang tên khác thì không ghi đè.
DEFAULT_CONVERSATION_TITLE = "Hội thoại mới"

TITLE_PROMPT = (
    "Bạn đặt tiêu đề cho một cuộc hội thoại dựa trên tin nhắn đầu tiên của người dùng và câu trả lời.\n"
    "- Tiêu đề 3-8 từ, cùng ngôn ngữ với người dùng, nêu đúng chủ đề chính.\n"
    "- Không dùng dấu ngoặc kép, không markdown, không dấu chấm cuối câu.\n"
    "- Chỉ trả về đúng tiêu đề, không giải thích."
)


@dataclass
class GenerateTitleUseCaseCommand:
    conversation_id: int
    user_message: str
    assistant_reply: str


class GenerateTitleUsecase:
    INPUT_CHARS = 1000  # Mỗi phần chỉ gửi đoạn đầu, đủ để nhận ra chủ đề
    MAX_TITLE_CHARS = 80
    FALLBACK_CHARS = 50  # Model lỗi thì lấy đoạn đầu tin nhắn user làm tên

    def __init__(
            self,
            reasoner: ModelReasoner,
            conversation_repository: ConversationsRepository,
    ):
        self.reasoner = reasoner
        self.conversation_repository = conversation_repository

    def execute(self, command: GenerateTitleUseCaseCommand) -> str:
        title = self._ask_model(command) or _shorten(command.user_message, self.FALLBACK_CHARS)

        self.conversation_repository.update_title(
            conversation_id=command.conversation_id,
            title=title,
        )

        return title

    def _ask_model(self, command: GenerateTitleUseCaseCommand) -> str:
        '''Gọi model một lượt không tool, lỗi hoặc kết quả rỗng thì trả về ""'''
        context = Context(messages=[
            TextMessage(role='system', content=TITLE_PROMPT),
            TextMessage(
                role='user',
                content=(
                    f"Tin nhắn người dùng:\n{command.user_message[:self.INPUT_CHARS]}\n\n"
                    f"Câu trả lời:\n{command.assistant_reply[:self.INPUT_CHARS]}"
                ),
            ),
        ])

        try:
            decision = self.reasoner.decide(context=context, tools=[])
        except Exception:
            Config.logger.exception('Generate conversation title failed')
            return ""

        if not isinstance(decision, FinalDecision):
            return ""

        return clean_title(decision.final_content, self.MAX_TITLE_CHARS)


def clean_title(text: str, limit: int) -> str:
    '''Lấy dòng đầu, bỏ ngoặc/markdown/dấu chấm cuối mà model hay thêm vào'''
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return ""

    title = re.sub(r'^(tiêu đề|title)\s*:\s*', '', lines[0].strip(), flags=re.IGNORECASE)
    title = title.strip(' "\'“”‘’`#*_.。')  # Gồm cả dấu chấm để xử lý được dạng "Tiêu đề".
    return _shorten(title, limit)


def _shorten(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"
