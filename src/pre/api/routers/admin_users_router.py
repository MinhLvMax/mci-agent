from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_users_repository import PostgresUsersRepository
from src.app.usecases.admin_users_usecase import (
    AdminRuleError,
    AdminUsersUsecase,
    UpdateUserCommand,
    UserNotFoundError,
)
from src.app.usecases.signup_usecase import EmailAlreadyExistsError, SignupValidationError
from src.dom.entities.user import User
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
def list_users(_: int = Depends(require_admin)) -> list[AdminUserResponse]:
    connection = create_postgres_connection()
    try:
        users = AdminUsersUsecase(PostgresUsersRepository(connection)).list_users()
        return [_to_response(user) for user in users]
    finally:
        connection.close()


@admin_users_router.patch(path='/{user_id}', response_model=AdminUserResponse)
def update_user(
        user_id: int,
        request: UpdateUserRequest,
        admin_id: int = Depends(require_admin),
) -> AdminUserResponse:
    connection = create_postgres_connection()
    try:
        user = AdminUsersUsecase(PostgresUsersRepository(connection)).update_user(
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
    finally:
        connection.close()


@admin_users_router.post(path='/{user_id}/reset_password')
def reset_password(
        user_id: int,
        request: ResetPasswordRequest,
        _: int = Depends(require_admin),
) -> dict:
    connection = create_postgres_connection()
    try:
        AdminUsersUsecase(PostgresUsersRepository(connection)).reset_password(user_id, request.new_password)
        return {"ok": True}

    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except SignupValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        connection.close()
