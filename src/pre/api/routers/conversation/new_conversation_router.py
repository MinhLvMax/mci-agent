from fastapi import APIRouter
from pydantic import BaseModel
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.usecases.conversation_management_usecases.new_conversation_usecase import NewConversationUsecase, \
    NewConversationUseCaseCommand


class NewConversationRequest(BaseModel):
    title: str
    user_id: int


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
def new_conversation_controller(request: NewConversationRequest) -> NewConversationResponse:
    connection = create_postgres_connection()
    try:
        repository = PostgreConversationsRepository(connection)
        usecase = NewConversationUsecase(
            conversation_repository=repository
        )
        result = usecase.execute(
            NewConversationUseCaseCommand(
                title=request.title,
                user_id=request.user_id
            )
        )
        return NewConversationResponse(
            title=result.title,
            conversation_id=result.conversation_id
        )
    finally:
        connection.close()
