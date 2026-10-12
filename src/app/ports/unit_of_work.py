from typing import Protocol, Self

from src.app.ports.repositories import (
    ConversationsRepository,
    FeedbacksRepository,
    FilesRepository,
    MemoriesRepository,
    MessagesRepository,
    SkillsRepository,
    UsersRepository,
)


class UnitOfWork(Protocol):
    '''
    Một phiên làm việc với kho dữ liệu: các repository dùng chung một kết nối.

    Dùng với "with": vào thì mở kết nối, ra thì đóng.
        with unit_of_work_factory() as uow:
            uow.conversations.get_by_id(...)
    '''
    users: UsersRepository
    conversations: ConversationsRepository
    messages: MessagesRepository
    files: FilesRepository
    skills: SkillsRepository
    memories: MemoriesRepository
    feedbacks: FeedbacksRepository

    def rollback(self) -> None:
        '''Huỷ phần đang dở sau khi có lỗi để phiên còn dùng tiếp được'''

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type, exc, tb) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...
