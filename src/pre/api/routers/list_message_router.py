from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.app.usecases.list_messege_usecase import ListMessegeUsecase, ListMessegeUseCaseCommand
from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id, get_owned_conversation

from src.dom.entities.message import Message


class ListMessageRequest(BaseModel):
    conversation_id: int


class ListMessageResponse(BaseModel):
    messages: list[Message]


list_message_router = APIRouter(
    prefix='/list_message'
)


@list_message_router.post(
    path='/',
    response_model=ListMessageResponse
)
def list_messages(
        request: ListMessageRequest,
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token
        container: ApiContainer = Depends(get_container),
) -> ListMessageResponse:
    with container.unit_of_work() as uow:
        get_owned_conversation(  # Chặn đọc tin nhắn của conversation người khác
            uow.conversations,
            conversation_id=request.conversation_id,
            user_id=user_id,
        )

        repository = uow.messages
        usecase = ListMessegeUsecase(
            message_repository=repository
        )
        result = usecase.execute(
            ListMessegeUseCaseCommand(
                conversation_id=request.conversation_id,
            )
        )
        return ListMessageResponse(
            messages=result.messages
        )
