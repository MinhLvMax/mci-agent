import threading

from src.app.services.memory_service import MemoryService
from src.app.usecases.extract_lessons_usecase import ExtractLessonsUsecase, ExtractLessonsUseCaseCommand
from src.dom.entities.message import Message
from src.pre.api.container import ApiContainer
from src.config import Config


def last_content(messages: list[Message], role: str) -> str:
    '''Nội dung tin nhắn gần nhất của role, không có thì ""'''
    for message in reversed(messages):
        if message.role == role and not message.interrupted:
            return message.content or ""
    return ""


def extract_lessons_in_background(container: ApiContainer, command: ExtractLessonsUseCaseCommand):
    '''
    Chạy bộ trích bài học ở thread riêng với phiên CSDL riêng,
    để user nhận câu trả lời / phản hồi góp ý ngay mà không phải chờ thêm một lần gọi model.
    Lỗi chỉ ghi log, không ảnh hưởng lượt chat.
    '''
    threading.Thread(
        target=_run,
        args=(container, command),
        daemon=True,
        name=f"extract-lessons-{command.conversation_id}",
    ).start()


def _run(container: ApiContainer, command: ExtractLessonsUseCaseCommand):
    try:
        with container.unit_of_work() as uow:
            saved = ExtractLessonsUsecase(
                reasoner=container.lesson_reasoner(),
                memory_service=MemoryService(uow.memories),
                memories_repository=uow.memories,
            ).execute(command)

            if command.feedback_id is not None:
                uow.feedbacks.mark_processed(command.feedback_id)

        for memory in saved:
            Config.logger.info(
                'Learned memory #%s [%s/%s] from user %s: %s',
                memory.id, memory.scope, memory.status, command.user_id, memory.content
            )
    except Exception:
        Config.logger.exception('Extract lessons failed')
