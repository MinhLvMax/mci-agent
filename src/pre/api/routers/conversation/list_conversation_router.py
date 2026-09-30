from fastapi import APIRouter
from pydantic import BaseModel
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.usecases.conversation_management_usecases.list_conversation_usecase import \
    ListConversationUseCaseCommand, ListConversationUsecase
from src.dom.entities.conversation import Conversation


class ListConversationRequest(BaseModel):
    user_id: int


class ListConversationResponse(BaseModel):
    conversations: list[Conversation]


list_conversation_router = APIRouter(
    prefix='/list_conversation'
)


@list_conversation_router.post(
    path='/',
    response_model=ListConversationResponse
)
def list_conversation_controller(request: ListConversationRequest) -> ListConversationResponse:
    connection = create_postgres_connection()
    try:
        repository = PostgreConversationsRepository(connection)
        usecase = ListConversationUsecase(
            conversation_repository=repository
        )
        result = usecase.execute(
            ListConversationUseCaseCommand(
                user_id=request.user_id
            )
        )
        return ListConversationResponse(
            conversations=result.conversations
        )
    finally:
        connection.close()
