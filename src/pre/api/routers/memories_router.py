from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints

from src.app.services.memory_service import MAX_MEMORY_CHARS
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_memories_repository import PostgreMemoriesRepository
from src.dom.entities.memory import Memory
from src.pre.api.dependencies import get_current_user_id, is_admin

MemoryContent = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MEMORY_CHARS)]


class MemoryResponse(BaseModel):
    id: int
    scope: str
    content: str
    status: str
    source: str
    user_id: int | None
    proposed_by: int | None
    approved_by: int | None
    source_conversation_id: int | None
    created_at: datetime | None
    updated_at: datetime | None


class CreateMemoryRequest(BaseModel):
    content: MemoryContent


class UpdateMemoryRequest(BaseModel):
    content: MemoryContent


class MeResponse(BaseModel):
    is_admin: bool


def _to_response(memory: Memory) -> MemoryResponse:
    return MemoryResponse(
        id=memory.id,
        scope=memory.scope,
        content=memory.content,
        status=memory.status,
        source=memory.source,
        user_id=memory.user_id,
        proposed_by=memory.proposed_by,
        approved_by=memory.approved_by,
        source_conversation_id=memory.source_conversation_id,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Memory not found")


def _require_admin(connection, user_id: int):
    if not is_admin(connection, user_id):
        raise HTTPException(status_code=403, detail="Admin only")


def _get_editable(repository: PostgreMemoriesRepository, connection, memory_id: int, user_id: int) -> Memory:
    '''User sửa/xoá được memory riêng của mình, admin sửa/xoá được memory org'''
    memory = repository.get_by_id(memory_id)
    if memory is None or memory.status == 'archived':
        raise _not_found()

    if memory.scope == 'user' and memory.user_id == user_id:
        return memory

    if memory.scope == 'org' and is_admin(connection, user_id):
        return memory

    raise _not_found()  # 404 thay vì 403 để không dò được id của người khác


memories_router = APIRouter(
    prefix='/memories'
)


@memories_router.get(path='/me', response_model=list[MemoryResponse])
def list_my_memories(user_id: int = Depends(get_current_user_id)) -> list[MemoryResponse]:
    '''Ghi nhớ riêng của user và các đề xuất quy định chung do user tạo ra'''
    connection = create_postgres_connection()
    try:
        return [_to_response(m) for m in PostgreMemoriesRepository(connection).list_for_user(user_id)]
    finally:
        connection.close()


@memories_router.get(path='/permissions', response_model=MeResponse)
def my_permissions(user_id: int = Depends(get_current_user_id)) -> MeResponse:
    '''UI dùng để biết có hiện trang duyệt bài học cho admin không'''
    connection = create_postgres_connection()
    try:
        return MeResponse(is_admin=is_admin(connection, user_id))
    finally:
        connection.close()


@memories_router.get(path='/org', response_model=list[MemoryResponse])
def list_org_memories(
        status: Literal['active', 'pending', 'rejected'] | None = None,
        user_id: int = Depends(get_current_user_id),
) -> list[MemoryResponse]:
    connection = create_postgres_connection()
    try:
        _require_admin(connection, user_id)
        return [_to_response(m) for m in PostgreMemoriesRepository(connection).list_org(status)]
    finally:
        connection.close()


@memories_router.post(path='/org', response_model=MemoryResponse)
def create_org_memory(
        request: CreateMemoryRequest,
        user_id: int = Depends(get_current_user_id),
) -> MemoryResponse:
    '''Admin tự thêm quy định chung, có hiệu lực ngay'''
    connection = create_postgres_connection()
    try:
        _require_admin(connection, user_id)
        memory = PostgreMemoriesRepository(connection).create(Memory(
            scope='org',
            content=request.content,
            status='active',
            source='admin',
            proposed_by=user_id,
            approved_by=user_id,
        ))
        return _to_response(memory)
    finally:
        connection.close()


@memories_router.post(path='/{memory_id}/approve', response_model=MemoryResponse)
def approve_memory(memory_id: int, user_id: int = Depends(get_current_user_id)) -> MemoryResponse:
    return _review(memory_id, user_id, 'active')


@memories_router.post(path='/{memory_id}/reject', response_model=MemoryResponse)
def reject_memory(memory_id: int, user_id: int = Depends(get_current_user_id)) -> MemoryResponse:
    return _review(memory_id, user_id, 'rejected')


def _review(memory_id: int, user_id: int, status: str) -> MemoryResponse:
    connection = create_postgres_connection()
    try:
        _require_admin(connection, user_id)
        repository = PostgreMemoriesRepository(connection)

        memory = repository.get_by_id(memory_id)
        if memory is None or memory.scope != 'org' or memory.status == 'archived':
            raise _not_found()

        return _to_response(repository.set_status(memory_id, status, approved_by=user_id))
    finally:
        connection.close()


@memories_router.patch(path='/{memory_id}', response_model=MemoryResponse)
def update_memory(
        memory_id: int,
        request: UpdateMemoryRequest,
        user_id: int = Depends(get_current_user_id),
) -> MemoryResponse:
    connection = create_postgres_connection()
    try:
        repository = PostgreMemoriesRepository(connection)
        memory = _get_editable(repository, connection, memory_id, user_id)
        return _to_response(repository.update_content(memory.id, request.content))
    finally:
        connection.close()


@memories_router.delete(path='/{memory_id}', response_model=MemoryResponse)
def delete_memory(memory_id: int, user_id: int = Depends(get_current_user_id)) -> MemoryResponse:
    '''Không xoá hẳn mà chuyển sang archived để còn truy vết'''
    connection = create_postgres_connection()
    try:
        repository = PostgreMemoriesRepository(connection)
        memory = _get_editable(repository, connection, memory_id, user_id)
        return _to_response(repository.set_status(memory.id, 'archived'))
    finally:
        connection.close()
