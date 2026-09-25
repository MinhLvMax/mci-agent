from fastapi import APIRouter
from pydantic import BaseModel
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.usecases.conversation_management_usecases.update_conversation_usecase import UpdateConversationUsecase, \
    UpdateConversationUseCaseCommand


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
def new_conversation_controller(request: UpdateConversationRequest) -> UpdateConversationResponse:
    connection = create_postgres_connection()
    try:
        repository = PostgreConversationsRepository(connection)
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
