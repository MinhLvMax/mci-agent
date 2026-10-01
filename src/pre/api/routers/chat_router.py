import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
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
from src.dom.agent_event import AgentEvent
from src.bootstrap import build_agent_service, build_workspace_service
from src.config import Config


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


@chat_router.post(
    path='/stream'
)
def chat_stream(
        request: ChatRequest,
        user_id: int = Depends(get_current_user_id),
) -> StreamingResponse:
    '''
    Giống /chat/ nhưng trả về dần từng event của agent, mỗi dòng là một JSON (NDJSON).
    Dòng cuối là {"type": "done", ...} hoặc {"type": "error", ...}.
    '''
    connection = create_postgres_connection()
    try:
        # Kiểm tra quyền trước khi stream để lỗi 403/404 vẫn trả về đúng status code
        conversation = get_owned_conversation(
            PostgreConversationsRepository(connection),
            conversation_id=request.conversation_id,
            user_id=user_id,
        )
    except Exception:
        connection.close()
        raise

    conversation_workspace_dir = build_workspace_service().get_conversation_workspace(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
    )

    def event_lines():
        # Connection phải sống tới khi stream xong nên mọi thứ nằm trong generator
        try:
            usecase = ChatUseCase(
                agent=build_agent_service(conversation_workspace_dir),
                conversation_repository=PostgreMessegesRepository(connection)
            )
            try:
                for event in usecase.execute_stream(
                        ChatUseCaseCommand(
                            conversation_id=request.conversation_id,
                            messages=Message(
                                role='user',
                                content=request.new_message,
                            )
                        )
                ):
                    yield json.dumps(event.to_dict(), ensure_ascii=False) + "\n"
            except Exception as e:
                # Status 200 đã gửi đi rồi, chỉ còn cách báo lỗi bằng một event
                Config.logger.exception('Chat stream failed')
                yield json.dumps(
                    AgentEvent(type='error', data={"message": str(e)}).to_dict(),
                    ensure_ascii=False
                ) + "\n"
            finally:
                # Agent có thể đã đổi file trong workspace -> đồng bộ lại metadata như /chat/
                connection.rollback()
                WorkspaceSyncService(
                    files_repository=PostgreFilesRepository(connection=connection)
                ).sync(
                    conversation_id=conversation.id,
                    workspace_dir=conversation_workspace_dir,
                )
        finally:
            connection.close()

    return StreamingResponse(
        event_lines(),
        media_type="application/x-ndjson",
    )
