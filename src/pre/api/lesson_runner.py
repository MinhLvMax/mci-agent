import threading

from src.app.services.memory_service import MemoryService
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_feedbacks_repository import PostgreFeedbacksRepository
from src.app.services.postgre_db.postgre_memories_repository import PostgreMemoriesRepository
from src.app.usecases.extract_lessons_usecase import ExtractLessonsUsecase, ExtractLessonsUseCaseCommand
from src.bootstrap import build_lesson_reasoner
from src.dom.entities.message import Message
from src.config import Config


def last_content(messages: list[Message], role: str) -> str:
    '''Nội dung tin nhắn gần nhất của role, không có thì ""'''
    for message in reversed(messages):
        if message.role == role and not message.interrupted:
            return message.content or ""
    return ""


def extract_lessons_in_background(command: ExtractLessonsUseCaseCommand):
    '''
    Chạy bộ trích bài học ở thread riêng với connection riêng,
    để user nhận câu trả lời / phản hồi góp ý ngay mà không phải chờ thêm một lần gọi model.
    Lỗi chỉ ghi log, không ảnh hưởng lượt chat.
    '''
    threading.Thread(
        target=_run,
        args=(command,),
        daemon=True,
        name=f"extract-lessons-{command.conversation_id}",
    ).start()


def _run(command: ExtractLessonsUseCaseCommand):
    try:
        connection = create_postgres_connection()
    except Exception:
        Config.logger.exception('Extract lessons: cannot connect to DB')
        return

    try:
        memories_repository = PostgreMemoriesRepository(connection)
        saved = ExtractLessonsUsecase(
            reasoner=build_lesson_reasoner(),
            memory_service=MemoryService(memories_repository),
            memories_repository=memories_repository,
        ).execute(command)

        if command.feedback_id is not None:
            PostgreFeedbacksRepository(connection).mark_processed(command.feedback_id)

        for memory in saved:
            Config.logger.info(
                'Learned memory #%s [%s/%s] from user %s: %s',
                memory.id, memory.scope, memory.status, command.user_id, memory.content
            )
    except Exception:
        Config.logger.exception('Extract lessons failed')
    finally:
        connection.close()
