from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.usecases.conversation_management_usecases.new_conversation_usecase import NewConversationUsecase, \
    NewConversationUseCaseCommand
from src.app.usecases.conversation_management_usecases.generate_title_usecase import DEFAULT_CONVERSATION_TITLE
from src.pre.api.dependencies import get_current_user_id


class NewConversationRequest(BaseModel):
    # Bỏ user_id để client không tạo hội thoại dưới tên người khác.
    # Không gửi title thì dùng tên tạm, AI đặt tên thật sau lượt chat đầu tiên.
    title: str = DEFAULT_CONVERSATION_TITLE


class NewConversationResponse(BaseModel):
    title: str
    conversation_id: int


new_conversation_router = APIRouter(
    prefix='/new_conversation'
)


@new_conversation_router.post(
    path='/',
    response_model=NewConversationResponse
)
def new_conversation_controller(
        request: NewConversationRequest,
        user_id: int = Depends(get_current_user_id),  # Chủ sở hữu hội thoại lấy từ token
) -> NewConversationResponse:
    connection = create_postgres_connection()
    try:
        repository = PostgreConversationsRepository(connection)
        usecase = NewConversationUsecase(
            conversation_repository=repository
        )
        result = usecase.execute(
            NewConversationUseCaseCommand(
                title=request.title,
                user_id=user_id  # Gắn hội thoại cho user đã xác thực
            )
        )
        return NewConversationResponse(
            title=result.title,
            conversation_id=result.conversation_id
        )
    finally:
        connection.close()
