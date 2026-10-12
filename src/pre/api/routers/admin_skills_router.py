from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_skills_repository import PostgreSkillsRepository
from src.app.usecases.admin_skills_usecase import (
    AdminSkillsUsecase,
    SkillChanges,
    SkillNameExistsError,
    SkillNotFoundError,
    SkillValidationError,
)
from src.dom.entities.skill import Skill
from src.pre.api.dependencies import require_admin


class SkillResponse(BaseModel):
    id: int
    name: str
    description: str
    instructions: str
    always_on: bool
    is_active: bool
    sort_order: int
    config_json: dict


class SkillRequest(BaseModel):
    # Dùng chung cho tạo và sửa: khi sửa, trường nào không gửi (None) thì giữ nguyên
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    instructions: str | None = None
    always_on: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    config_json: dict | None = None


def _to_response(skill: Skill) -> SkillResponse:
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        instructions=skill.instructions,
        always_on=skill.always_on,
        is_active=skill.is_active,
        sort_order=skill.sort_order,
        config_json=skill.config or {},
    )


def _to_changes(request: SkillRequest) -> SkillChanges:
    return SkillChanges(
        name=request.name,
        description=request.description,
        instructions=request.instructions,
        always_on=request.always_on,
        is_active=request.is_active,
        sort_order=request.sort_order,
        config=request.config_json,
    )


admin_skills_router = APIRouter(
    prefix='/admin/skills'
)


@admin_skills_router.get(path='/', response_model=list[SkillResponse])
def list_skills(_: int = Depends(require_admin)) -> list[SkillResponse]:
    connection = create_postgres_connection()
    try:
        return [_to_response(s) for s in AdminSkillsUsecase(PostgreSkillsRepository(connection)).list_skills()]
    finally:
        connection.close()


@admin_skills_router.post(path='/', response_model=SkillResponse)
def create_skill(request: SkillRequest, _: int = Depends(require_admin)) -> SkillResponse:
    return _run(lambda usecase: usecase.create_skill(_to_changes(request)))


@admin_skills_router.patch(path='/{skill_id}', response_model=SkillResponse)
def update_skill(skill_id: int, request: SkillRequest, _: int = Depends(require_admin)) -> SkillResponse:
    return _run(lambda usecase: usecase.update_skill(skill_id, _to_changes(request)))


def _run(action) -> SkillResponse:
    '''Mở connection, chạy nghiệp vụ, đổi lỗi nghiệp vụ thành mã HTTP'''
    connection = create_postgres_connection()
    try:
        return _to_response(action(AdminSkillsUsecase(PostgreSkillsRepository(connection))))

    except SkillNotFoundError:
        raise HTTPException(status_code=404, detail="Skill not found")
    except SkillNameExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except SkillValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        connection.close()
