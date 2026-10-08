from dataclasses import dataclass
from src.app.services.postgre_db.postgre_feedbacks_repository import PostgreFeedbacksRepository


@dataclass
class SendFeedbackUseCaseCommand:
    user_id: int
    conversation_id: int | None
    content: str


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
            content=command.content
        )

        return SendFeedbackUseCaseResult(
            id=feedback.id
        )
