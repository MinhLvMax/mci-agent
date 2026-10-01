from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.pre.api.dependencies import get_current_user_id, get_owned_conversation

from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_messages_repository import PostgreMessegesRepository
from src.app.services.postgre_db.postgre_conversations_repository import (
    PostgreConversationsRepository
)
from src.app.services.postgre_db.postgre_files_repository import (
    PostgreFilesRepository
)
from src.app.services.workspace_sync_service import WorkspaceSyncService

from src.app.usecases.chat_usecase import ChatUseCase, ChatUseCaseCommand
from src.dom.entities.message import Message
from src.bootstrap import build_agent_service, build_workspace_service


class ChatRequest(BaseModel):
    conversation_id: int
    new_message: str


class ChatResponse(BaseModel):
    message: str


chat_router = APIRouter(
    prefix='/chat'
)


@chat_router.post(
    path='/',
    response_model=ChatResponse
)
def chat(
        request: ChatRequest,
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token, không phải client tự khai
) -> ChatResponse:
    connection = create_postgres_connection()
    try:
        conversation = get_owned_conversation(  # Chỉ cho chat trong conversation của chính mình
            PostgreConversationsRepository(connection),
            conversation_id=request.conversation_id,
            user_id=user_id,
        )

        workspace_service = build_workspace_service()

        conversation_workspace_dir = workspace_service.get_conversation_workspace(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
        )

        mess_repository = PostgreMessegesRepository(connection)
        usecase = ChatUseCase(
            agent=build_agent_service(conversation_workspace_dir),
            conversation_repository=mess_repository
        )
        try:
            result = usecase.execute(
                ChatUseCaseCommand(
                    conversation_id=request.conversation_id,
                    messages=Message(
                        role='user',
                        content=request.new_message,
                    )
                )
            )
        finally:
            # ============================================================
            # 5. Agent đã chạy xong (kể cả khi chạy lỗi giữa chừng)
            #    -> filesystem có thể đã thay đổi
            #    -> đồng bộ lại metadata vào DB
            # ============================================================

            # Nếu usecase lỗi ở bước ghi DB thì transaction đang hỏng,
            # phải rollback trước khi dùng tiếp connection.
            connection.rollback()

            files_repository = PostgreFilesRepository(
                connection=connection
            )

            workspace_sync_service = WorkspaceSyncService(
                files_repository=files_repository
            )

            workspace_sync_service.sync(
                conversation_id=conversation.id,
                workspace_dir=conversation_workspace_dir,
            )
        return ChatResponse(
            message=result.message.content
        )
    finally:
        connection.close()
