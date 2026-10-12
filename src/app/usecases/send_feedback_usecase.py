from dataclasses import dataclass
from src.app.services.postgre_db.postgre_feedbacks_repository import PostgreFeedbacksRepository


@dataclass
class SendFeedbackUseCaseCommand:
    user_id: int
    conversation_id: int | None
    content: str
    rating: int | None = None  # 1 = hài lòng, -1 = chưa hài lòng
    kind: str | None = None  # 'correction' | 'preference' | 'bug' | 'other'


@dataclass
class SendFeedbackUseCaseResult:
    id: int


class SendFeedbackUsecase:
    def __init__(self, feedback_repository: PostgreFeedbacksRepository):
        self.feedback_repository = feedback_repository

    def execute(self, command: SendFeedbackUseCaseCommand) -> SendFeedbackUseCaseResult:
        feedback = self.feedback_repository.create(
            user_id=command.user_id,
            conversation_id=command.conversation_id,
            content=command.content,
            rating=command.rating,
            kind=command.kind
        )

        return SendFeedbackUseCaseResult(
            id=feedback.id
        )
