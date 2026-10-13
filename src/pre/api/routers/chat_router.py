import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id, get_owned_conversation

from src.app.ports.model_reasoner import ModelUnavailableError
from src.app.ports.unit_of_work import UnitOfWork
from src.app.services.chat_model_selector import select_chat_model
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
from src.pre.api.lesson_runner import extract_lessons_in_background, last_content
from src.config import Config


class ChatRequest(BaseModel):
    conversation_id: int
    new_message: str
    model_id: int | None = None  # None thì dùng model mặc định admin đặt
    reasoning_mode: str | None = None  # None thì dùng chế độ đầu tiên của model (nếu model có)


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
        container: ApiContainer = Depends(get_container),
) -> ChatResponse:
    with container.unit_of_work() as uow:
        conversation = get_owned_conversation(  # Chỉ cho chat trong conversation của chính mình
            uow.conversations,
            conversation_id=request.conversation_id,
            user_id=user_id,
        )

        conversation_workspace_dir = container.workspace_service().get_conversation_workspace(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
        )

        # Đọc skill và memory mỗi lượt chat để admin sửa/duyệt trong DB là có hiệu lực ngay
        skills = uow.skills.list_active()
        memories = uow.memories.list_for_prompt(user_id)

        history = uow.messages.get_messages(conversation_id=conversation.id)
        try:
            ai_model, reasoning_mode = select_chat_model(uow.models, request.model_id, request.reasoning_mode)
            agent = container.agent_service(
                conversation_workspace_dir,
                skills,
                memory_service=MemoryService(uow.memories),
                user_id=user_id,
                conversation_id=conversation.id,
                ai_model=ai_model,
                reasoning_mode=reasoning_mode,
            )
        except ModelUnavailableError as e:
            raise HTTPException(status_code=400, detail=str(e))

        usecase = ChatUseCase(
            agent=agent,
            conversation_repository=uow.messages,
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
        except ModelUnavailableError as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            # ============================================================
            # Agent đã chạy xong (kể cả khi chạy lỗi giữa chừng)
            #    -> filesystem có thể đã thay đổi
            #    -> đồng bộ lại metadata vào DB
            # ============================================================

            # Nếu usecase lỗi ở bước ghi DB thì transaction đang hỏng,
            # phải rollback trước khi dùng tiếp phiên.
            uow.rollback()

            WorkspaceSyncService(
                files_repository=uow.files,
                scanner=container.workspace_scanner(),
            ).sync(
                conversation_id=conversation.id,
                workspace_dir=conversation_workspace_dir,
            )

    extract_lessons_in_background(container, ExtractLessonsUseCaseCommand(
        user_id=user_id,
        conversation_id=conversation.id,
        user_message=request.new_message,
        previous_assistant_reply=last_content(history, 'assistant'),
        assistant_reply=result.message.content,
    ))

    return ChatResponse(
        message=result.message.content
    )


@chat_router.post(
    path='/stream'
)
def chat_stream(
        request: ChatRequest,
        user_id: int = Depends(get_current_user_id),
        container: ApiContainer = Depends(get_container),
) -> StreamingResponse:
    '''
    Giống /chat/ nhưng trả về dần từng event của agent, mỗi dòng là một JSON (NDJSON).
    Dòng cuối là {"type": "done", ...} hoặc {"type": "error", ...}.
    '''
    # Kiểm tra quyền trước khi stream để lỗi 403/404 vẫn trả về đúng status code
    with container.unit_of_work() as uow:
        conversation = get_owned_conversation(
            uow.conversations,
            conversation_id=request.conversation_id,
            user_id=user_id,
        )

    conversation_workspace_dir = container.workspace_service().get_conversation_workspace(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
    )

    def event_lines():
        # Phiên CSDL phải sống tới khi stream xong nên mở trong generator
        with container.unit_of_work() as uow:
            skills = uow.skills.list_active()
            memories = uow.memories.list_for_prompt(user_id)
            history = uow.messages.get_messages(conversation_id=conversation.id)

            # Lượt đầu của hội thoại còn mang tên tạm thì AI đặt tên sau khi trả lời xong.
            # User đã tự đổi tên thì không ghi đè.
            should_generate_title = (
                    conversation.title == DEFAULT_CONVERSATION_TITLE
                    and not history
            )

            try:
                ai_model, reasoning_mode = select_chat_model(uow.models, request.model_id, request.reasoning_mode)
                usecase = ChatUseCase(
                    agent=container.agent_service(
                        conversation_workspace_dir,
                        skills,
                        memory_service=MemoryService(uow.memories),
                        user_id=user_id,
                        conversation_id=conversation.id,
                        ai_model=ai_model,
                        reasoning_mode=reasoning_mode,
                    ),
                    conversation_repository=uow.messages,
                    system_prompt=build_system_prompt(skills, memories),
                )

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
                    extract_lessons_in_background(container, ExtractLessonsUseCaseCommand(
                        user_id=user_id,
                        conversation_id=conversation.id,
                        user_message=request.new_message,
                        previous_assistant_reply=last_content(history, 'assistant'),
                        assistant_reply=assistant_reply,
                    ))

                if should_generate_title and assistant_reply is not None:
                    title_event = _generate_title(container, uow, conversation.id, request.new_message, assistant_reply)
                    if title_event is not None:
                        yield json.dumps(title_event.to_dict(), ensure_ascii=False) + "\n"
            except ModelUnavailableError as e:
                # Chọn sai model / chế độ suy luận: kind = "model" để UI hiện toast thay vì khung lỗi agent
                yield json.dumps(
                    AgentEvent(type='error', data={"message": str(e), "kind": "model"}).to_dict(),
                    ensure_ascii=False
                ) + "\n"
            except Exception as e:
                # Status 200 đã gửi đi rồi, chỉ còn cách báo lỗi bằng một event
                Config.logger.exception('Chat stream failed')
                yield json.dumps(
                    AgentEvent(type='error', data={"message": str(e)}).to_dict(),
                    ensure_ascii=False
                ) + "\n"
            finally:
                # Agent có thể đã đổi file trong workspace -> đồng bộ lại metadata như /chat/
                uow.rollback()
                WorkspaceSyncService(
                    files_repository=uow.files,
                    scanner=container.workspace_scanner(),
                ).sync(
                    conversation_id=conversation.id,
                    workspace_dir=conversation_workspace_dir,
                )

    return StreamingResponse(
        event_lines(),
        media_type="application/x-ndjson",
    )


def _generate_title(
        container: ApiContainer,
        uow: UnitOfWork,
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
            reasoner=container.title_reasoner(),
            conversation_repository=uow.conversations,
        ).execute(
            GenerateTitleUseCaseCommand(
                conversation_id=conversation_id,
                user_message=user_message,
                assistant_reply=assistant_reply,
            )
        )
    except Exception:
        Config.logger.exception('Save conversation title failed')
        uow.rollback()  # Transaction hỏng thì rollback để bước sync workspace phía sau còn dùng được
        return None

    return AgentEvent(type='title', data={"title": title})
