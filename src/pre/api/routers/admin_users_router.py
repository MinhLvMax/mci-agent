from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.app.usecases.admin_users_usecase import (
    AdminRuleError,
    AdminUsersUsecase,
    UpdateUserCommand,
    UserNotFoundError,
)
from src.app.usecases.signup_usecase import EmailAlreadyExistsError, SignupValidationError
from src.dom.entities.user import User
from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import require_admin


class AdminUserResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime | None


class UpdateUserRequest(BaseModel):
    # Trường nào không gửi (None) thì giữ nguyên
    email: str | None = None
    role: Literal['user', 'admin'] | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str


def _to_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


admin_users_router = APIRouter(
    prefix='/admin/users'
)


@admin_users_router.get(path='/', response_model=list[AdminUserResponse])
def list_users(
        _: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> list[AdminUserResponse]:
    with container.unit_of_work() as uow:
        users = AdminUsersUsecase(uow.users, container.password_hasher()).list_users()
        return [_to_response(user) for user in users]


@admin_users_router.patch(path='/{user_id}', response_model=AdminUserResponse)
def update_user(
        user_id: int,
        request: UpdateUserRequest,
        admin_id: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> AdminUserResponse:
    try:
        with container.unit_of_work() as uow:
            user = AdminUsersUsecase(uow.users, container.password_hasher()).update_user(
                UpdateUserCommand(
                    actor_id=admin_id,
                    user_id=user_id,
                    email=request.email,
                    role=request.role,
                    is_active=request.is_active,
                )
            )
            return _to_response(user)

    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except EmailAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (AdminRuleError, SignupValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@admin_users_router.post(path='/{user_id}/reset_password')
def reset_password(
        user_id: int,
        request: ResetPasswordRequest,
        _: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> dict:
    try:
        with container.unit_of_work() as uow:
            AdminUsersUsecase(uow.users, container.password_hasher()).reset_password(user_id, request.new_password)
            return {"ok": True}

    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except SignupValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
