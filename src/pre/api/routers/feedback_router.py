from fastapi import APIRouter, Depends
from typing import Annotated

from pydantic import BaseModel, StringConstraints
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.services.postgre_db.postgre_feedbacks_repository import PostgreFeedbacksRepository
from src.app.usecases.send_feedback_usecase import SendFeedbackUsecase, SendFeedbackUseCaseCommand
from src.pre.api.dependencies import get_current_user_id, get_owned_conversation


class SendFeedbackRequest(BaseModel):
    # Bỏ khoảng trắng hai đầu trước khi kiểm tra, góp ý toàn dấu cách bị từ chối (422)
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    conversation_id: int | None = None  # Hội thoại đang mở lúc gửi, không có thì để trống


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
        if request.conversation_id is not None:
            get_owned_conversation(  # Chỉ cho gắn góp ý vào hội thoại của chính mình
                PostgreConversationsRepository(connection),
                conversation_id=request.conversation_id,
                user_id=user_id,
            )

        usecase = SendFeedbackUsecase(PostgreFeedbacksRepository(connection))
        result = usecase.execute(
            SendFeedbackUseCaseCommand(
                user_id=user_id,
                conversation_id=request.conversation_id,
                content=request.content
            )
        )
        return SendFeedbackResponse(
            id=result.id
        )
    finally:
        connection.close()
