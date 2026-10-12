from fastapi import APIRouter, Depends
from typing import Annotated

from pydantic import BaseModel, StringConstraints
from src.app.usecases.conversation_management_usecases.update_conversation_usecase import UpdateConversationUsecase, \
    UpdateConversationUseCaseCommand
from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id, get_owned_conversation


class UpdateConversationRequest(BaseModel):
    conversation_id: int
    # Bỏ khoảng trắng hai đầu trước khi kiểm tra, tên toàn dấu cách bị từ chối (422)
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class UpdateConversationResponse(BaseModel):
    id: int
    user_id: int
    title: str


update_conversation_router = APIRouter(
    prefix='/update_conversation'
)


@update_conversation_router.post(
    path='/',
    response_model=UpdateConversationResponse
)
def new_conversation_controller(
        request: UpdateConversationRequest,
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token
        container: ApiContainer = Depends(get_container),
) -> UpdateConversationResponse:
    with container.unit_of_work() as uow:
        repository = uow.conversations

        get_owned_conversation(  # Chỉ cho đổi tên conversation của chính mình
            repository,
            conversation_id=request.conversation_id,
            user_id=user_id,
        )

        usecase = UpdateConversationUsecase(repository)
        result = usecase.execute(
            UpdateConversationUseCaseCommand(
                conversation_id=request.conversation_id,
                title=request.title
            )
        )
        return UpdateConversationResponse(
            id=result.id,
            user_id=result.user_id,
            title=result.title
        )
