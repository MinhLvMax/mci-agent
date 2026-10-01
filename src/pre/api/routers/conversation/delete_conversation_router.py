from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.usecases.conversation_management_usecases.delete_conversation_usecase import \
    DeleteConversationUseCaseCommand, DeleteConversationUsecase
from src.bootstrap import build_workspace_service
from src.pre.api.dependencies import get_current_user_id, get_owned_conversation


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
def delete_conversation_controller(
        request: DeleteConversationRequest,
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token
) -> DeleteConversationResponse:
    connection = create_postgres_connection()
    try:
        repository = PostgreConversationsRepository(connection)

        get_owned_conversation(  # Chỉ cho xóa conversation của chính mình
            repository,
            conversation_id=request.conversation_id,
            user_id=user_id,
        )

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
