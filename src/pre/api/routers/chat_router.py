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
from src.app.services.postgre_db.postgre_skills_repository import PostgreSkillsRepository
from src.app.services.postgre_db.postgre_memories_repository import PostgreMemoriesRepository
from src.app.services.memory_service import MemoryService
from src.app.services.system_prompt_builder import build_system_prompt
from src.app.services.workspace_sync_service import WorkspaceSyncService

from src.app.usecases.chat_usecase import ChatUseCase, ChatUseCaseCommand
from src.app.usecases.extract_lessons_usecase import ExtractLessonsUseCaseCommand
from src.app.usecases.conversation_management_usecases.generate_title_usecase import (
    DEFAULT_CONVERSATION_TITLE,
    GenerateTitleUsecase,
    GenerateTitleUseCaseCommand,
)
from src.dom.entities.message import Message
from src.dom.agent_event import AgentEvent
from src.bootstrap import build_agent_service, build_title_reasoner, build_workspace_service
from src.pre.api.lesson_runner import extract_lessons_in_background, last_content
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

        # Đọc skill và memory mỗi lượt chat để admin sửa/duyệt trong DB là có hiệu lực ngay
        skills = PostgreSkillsRepository(connection).list_active()
        memories_repository = PostgreMemoriesRepository(connection)
        memories = memories_repository.list_for_prompt(user_id)

        mess_repository = PostgreMessegesRepository(connection)
        history = mess_repository.get_messages(conversation_id=conversation.id)
        usecase = ChatUseCase(
            agent=build_agent_service(
                conversation_workspace_dir,
                skills,
                memory_service=MemoryService(memories_repository),
                user_id=user_id,
                conversation_id=conversation.id,
            ),
            conversation_repository=mess_repository,
            system_prompt=build_system_prompt(skills, memories),
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
        extract_lessons_in_background(ExtractLessonsUseCaseCommand(
            user_id=user_id,
            conversation_id=conversation.id,
            user_message=request.new_message,
            previous_assistant_reply=last_content(history, 'assistant'),
            assistant_reply=result.message.content,
        ))

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
            skills = PostgreSkillsRepository(connection).list_active()
            memories_repository = PostgreMemoriesRepository(connection)
            memories = memories_repository.list_for_prompt(user_id)
            messages_repository = PostgreMessegesRepository(connection)
            history = messages_repository.get_messages(conversation_id=conversation.id)

            # Lượt đầu của hội thoại còn mang tên tạm thì AI đặt tên sau khi trả lời xong.
            # User đã tự đổi tên thì không ghi đè.
            should_generate_title = (
                    conversation.title == DEFAULT_CONVERSATION_TITLE
                    and not history
            )

            usecase = ChatUseCase(
                agent=build_agent_service(
                    conversation_workspace_dir,
                    skills,
                    memory_service=MemoryService(memories_repository),
                    user_id=user_id,
                    conversation_id=conversation.id,
                ),
                conversation_repository=messages_repository,
                system_prompt=build_system_prompt(skills, memories),
            )
            try:
                assistant_reply = None
                for event in usecase.execute_stream(
                        ChatUseCaseCommand(
                            conversation_id=request.conversation_id,
                            messages=Message(
                                role='user',
                                content=request.new_message,
                            )
                        )
                ):
                    if event.type == 'done':
                        assistant_reply = event.data["content"]
                    yield json.dumps(event.to_dict(), ensure_ascii=False) + "\n"

                if assistant_reply is not None:
                    # Rút bài học ở thread riêng, model tự quyết lượt này có gì đáng nhớ không
                    extract_lessons_in_background(ExtractLessonsUseCaseCommand(
                        user_id=user_id,
                        conversation_id=conversation.id,
                        user_message=request.new_message,
                        previous_assistant_reply=last_content(history, 'assistant'),
                        assistant_reply=assistant_reply,
                    ))

                if should_generate_title and assistant_reply is not None:
                    title_event = _generate_title(connection, conversation.id, request.new_message, assistant_reply)
                    if title_event is not None:
                        yield json.dumps(title_event.to_dict(), ensure_ascii=False) + "\n"
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


def _generate_title(
        connection,
        conversation_id: int,
        user_message: str,
        assistant_reply: str,
) -> AgentEvent | None:
    '''
    Đặt tên hội thoại rồi trả về event "title" cho UI.
    Câu trả lời đã lưu xong nên đặt tên lỗi chỉ ghi log, không báo lỗi cho user.
    '''
    try:
        title = GenerateTitleUsecase(
            reasoner=build_title_reasoner(),
            conversation_repository=PostgreConversationsRepository(connection),
        ).execute(
            GenerateTitleUseCaseCommand(
                conversation_id=conversation_id,
                user_message=user_message,
                assistant_reply=assistant_reply,
            )
        )
    except Exception:
        Config.logger.exception('Save conversation title failed')
        connection.rollback()  # Transaction hỏng thì rollback để bước sync workspace phía sau còn dùng được
        return None

    return AgentEvent(type='title', data={"title": title})
