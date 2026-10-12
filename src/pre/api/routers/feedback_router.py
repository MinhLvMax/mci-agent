from fastapi import APIRouter, Depends
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, model_validator
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.services.postgre_db.postgre_feedbacks_repository import PostgreFeedbacksRepository
from src.app.services.postgre_db.postgre_messages_repository import PostgreMessegesRepository
from src.app.usecases.extract_lessons_usecase import ExtractLessonsUseCaseCommand
from src.app.usecases.send_feedback_usecase import SendFeedbackUsecase, SendFeedbackUseCaseCommand
from src.pre.api.dependencies import get_current_user_id, get_owned_conversation
from src.pre.api.lesson_runner import extract_lessons_in_background, last_content


class SendFeedbackRequest(BaseModel):
    # Bỏ khoảng trắng hai đầu trước khi kiểm tra
    content: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    conversation_id: int | None = None  # Hội thoại đang mở lúc gửi, không có thì để trống
    rating: Literal[1, -1] | None = None  # 👍 = 1, 👎 = -1
    kind: Literal['correction', 'preference', 'bug', 'other'] | None = None

    @model_validator(mode='after')
    def check_not_empty(self):
        # Chỉ bấm 👍/👎 thì được để trống nội dung, còn lại phải có nội dung (422)
        if not self.content and self.rating is None:
            raise ValueError("content or rating is required")
        return self


class SendFeedbackResponse(BaseModel):
    id: int


feedback_router = APIRouter(
    prefix='/send_feedback'
)


@feedback_router.post(
    path='/',
    response_model=SendFeedbackResponse
)
def send_feedback_controller(
        request: SendFeedbackRequest,
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token
) -> SendFeedbackResponse:
    connection = create_postgres_connection()
    try:
        history = []
        if request.conversation_id is not None:
            get_owned_conversation(  # Chỉ cho gắn góp ý vào hội thoại của chính mình
                PostgreConversationsRepository(connection),
                conversation_id=request.conversation_id,
                user_id=user_id,
            )
            history = PostgreMessegesRepository(connection).get_messages(conversation_id=request.conversation_id)

        usecase = SendFeedbackUsecase(PostgreFeedbacksRepository(connection))
        result = usecase.execute(
            SendFeedbackUseCaseCommand(
                user_id=user_id,
                conversation_id=request.conversation_id,
                content=request.content,
                rating=request.rating,
                kind=request.kind
            )
        )

        # Góp ý nào cũng đưa cho model xem có bài học không (kèm lượt chat gần nhất làm ngữ cảnh)
        extract_lessons_in_background(ExtractLessonsUseCaseCommand(
            user_id=user_id,
            conversation_id=request.conversation_id,
            user_message=last_content(history, 'user'),
            assistant_reply=last_content(history, 'assistant'),
            feedback_content=request.content,
            feedback_rating=request.rating,
            feedback_kind=request.kind,
            feedback_id=result.id,
        ))

        return SendFeedbackResponse(
            id=result.id
        )
    finally:
        connection.close()
