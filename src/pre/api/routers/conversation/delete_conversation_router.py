from fastapi import APIRouter
from pydantic import BaseModel
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.usecases.conversation_management_usecases.delete_conversation_usecase import \
    DeleteConversationUseCaseCommand, DeleteConversationUsecase
from src.bootstrap import build_workspace_service


class DeleteConversationRequest(BaseModel):
    conversation_id: int


class DeleteConversationResponse(BaseModel):
    status: bool


delete_conversation_router = APIRouter(
    prefix='/delete_conversation'
)


@delete_conversation_router.post(
    path='/',
    response_model=DeleteConversationResponse
)
def delete_conversation_controller(request: DeleteConversationRequest) -> DeleteConversationResponse:
    connection = create_postgres_connection()
    try:
        repository = PostgreConversationsRepository(connection)
        usecase = DeleteConversationUsecase(
            conversation_repository=repository,
            workspace_service=build_workspace_service(),
        )
        result = usecase.execute(
            DeleteConversationUseCaseCommand(
                conversation_id=request.conversation_id
            )
        )
        return DeleteConversationResponse(
            status=result.status
        )
    finally:
        connection.close()
