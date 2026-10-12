from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.app.usecases.conversation_management_usecases.list_conversation_usecase import \
    ListConversationUseCaseCommand, ListConversationUsecase
from src.dom.entities.conversation import Conversation
from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id


# Không còn request body: trước đây client gửi user_id lên nên ai cũng xem được
# hội thoại của người khác, giờ user_id chỉ lấy từ token.


class ListConversationResponse(BaseModel):
    conversations: list[Conversation]


list_conversation_router = APIRouter(
    prefix='/list_conversation'
)


@list_conversation_router.post(
    path='/',
    response_model=ListConversationResponse
)
def list_conversation_controller(
        user_id: int = Depends(get_current_user_id),  # Chỉ liệt kê hội thoại của user trong token
        container: ApiContainer = Depends(get_container),
) -> ListConversationResponse:
    with container.unit_of_work() as uow:
        repository = uow.conversations
        usecase = ListConversationUsecase(
            conversation_repository=repository
        )
        result = usecase.execute(
            ListConversationUseCaseCommand(
                user_id=user_id  # Dùng user id đã xác thực
            )
        )
        return ListConversationResponse(
            conversations=result.conversations
        )
