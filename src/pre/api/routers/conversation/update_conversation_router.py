from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.usecases.conversation_management_usecases.update_conversation_usecase import UpdateConversationUsecase, \
    UpdateConversationUseCaseCommand
from src.pre.api.dependencies import get_current_user_id, get_owned_conversation


class UpdateConversationRequest(BaseModel):
    conversation_id: int
    title: str


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
) -> UpdateConversationResponse:
    connection = create_postgres_connection()
    try:
        repository = PostgreConversationsRepository(connection)

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
    finally:
        connection.close()
