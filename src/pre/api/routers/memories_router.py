from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints

from src.app.services.memory_service import MAX_MEMORY_CHARS
from src.dom.entities.memory import Memory
from src.pre.api.container import ApiContainer, get_container
from src.app.ports.unit_of_work import UnitOfWork
from src.pre.api.dependencies import get_current_user_id, is_admin, require_admin

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


def _get_editable(uow: UnitOfWork, memory_id: int, user_id: int) -> Memory:
    '''User sửa/xoá được memory riêng của mình, admin sửa/xoá được memory org'''
    memory = uow.memories.get_by_id(memory_id)
    if memory is None or memory.status == 'archived':
        raise _not_found()

    if memory.scope == 'user' and memory.user_id == user_id:
        return memory

    if memory.scope == 'org' and is_admin(uow.users, user_id):
        return memory

    raise _not_found()  # 404 thay vì 403 để không dò được id của người khác


memories_router = APIRouter(
    prefix='/memories'
)


@memories_router.get(path='/me', response_model=list[MemoryResponse])
def list_my_memories(
        user_id: int = Depends(get_current_user_id),
        container: ApiContainer = Depends(get_container),
) -> list[MemoryResponse]:
    '''Ghi nhớ riêng của user và các đề xuất quy định chung do user tạo ra'''
    with container.unit_of_work() as uow:
        return [_to_response(m) for m in uow.memories.list_for_user(user_id)]


@memories_router.get(path='/permissions', response_model=MeResponse)
def my_permissions(
        user_id: int = Depends(get_current_user_id),
        container: ApiContainer = Depends(get_container),
) -> MeResponse:
    '''UI dùng để biết user có quyền admin không'''
    with container.unit_of_work() as uow:
        return MeResponse(is_admin=is_admin(uow.users, user_id))


@memories_router.get(path='/org', response_model=list[MemoryResponse])
def list_org_memories(
        status: Literal['active', 'pending', 'rejected'] | None = None,
        _: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> list[MemoryResponse]:
    with container.unit_of_work() as uow:
        return [_to_response(m) for m in uow.memories.list_org(status)]


@memories_router.post(path='/org', response_model=MemoryResponse)
def create_org_memory(
        request: CreateMemoryRequest,
        admin_id: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> MemoryResponse:
    '''Admin tự thêm quy định chung, có hiệu lực ngay'''
    with container.unit_of_work() as uow:
        memory = uow.memories.create(Memory(
            scope='org',
            content=request.content,
            status='active',
            source='admin',
            proposed_by=admin_id,
            approved_by=admin_id,
        ))
        return _to_response(memory)


@memories_router.post(path='/{memory_id}/approve', response_model=MemoryResponse)
def approve_memory(
        memory_id: int,
        admin_id: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> MemoryResponse:
    return _review(container, memory_id, admin_id, 'active')


@memories_router.post(path='/{memory_id}/reject', response_model=MemoryResponse)
def reject_memory(
        memory_id: int,
        admin_id: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> MemoryResponse:
    return _review(container, memory_id, admin_id, 'rejected')


def _review(container: ApiContainer, memory_id: int, admin_id: int, status: str) -> MemoryResponse:
    with container.unit_of_work() as uow:
        memory = uow.memories.get_by_id(memory_id)
        if memory is None or memory.scope != 'org' or memory.status == 'archived':
            raise _not_found()

        return _to_response(uow.memories.set_status(memory_id, status, approved_by=admin_id))


@memories_router.patch(path='/{memory_id}', response_model=MemoryResponse)
def update_memory(
        memory_id: int,
        request: UpdateMemoryRequest,
        user_id: int = Depends(get_current_user_id),
        container: ApiContainer = Depends(get_container),
) -> MemoryResponse:
    with container.unit_of_work() as uow:
        memory = _get_editable(uow, memory_id, user_id)
        return _to_response(uow.memories.update_content(memory.id, request.content))


@memories_router.delete(path='/{memory_id}', response_model=MemoryResponse)
def delete_memory(
        memory_id: int,
        user_id: int = Depends(get_current_user_id),
        container: ApiContainer = Depends(get_container),
) -> MemoryResponse:
    '''Không xoá hẳn mà chuyển sang archived để còn truy vết'''
    with container.unit_of_work() as uow:
        memory = _get_editable(uow, memory_id, user_id)
        return _to_response(uow.memories.set_status(memory.id, 'archived'))
