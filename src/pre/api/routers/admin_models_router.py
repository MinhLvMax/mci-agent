from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.app.usecases.admin_models_usecase import (
    AdminModelsUsecase,
    ModelChanges,
    ModelExistsError,
    ModelNotFoundError,
    ModelValidationError,
)
from src.app.usecases.test_model_usecase import TestModelUsecase
from src.dom.entities.ai_model import AIModel
from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id, require_admin


class ProviderResponse(BaseModel):
    name: str  # Mã lưu ở cột models.provider
    label: str  # Tên hiển thị, do adapter khai báo


class ModelResponse(BaseModel):
    id: int
    display_name: str
    model_name: str
    provider: str
    provider_label: str
    reasoning_modes: list[str]
    is_active: bool
    is_default: bool
    sort_order: int


class ModelRequest(BaseModel):
    # Dùng chung cho tạo và sửa: khi sửa, trường nào không gửi (None) thì giữ nguyên
    display_name: str | None = Field(default=None, max_length=100)
    model_name: str | None = Field(default=None, max_length=200)
    provider: str | None = Field(default=None, max_length=30)
    reasoning_modes: list[str] | None = None
    is_active: bool | None = None
    is_default: bool | None = None
    sort_order: int | None = None


def _provider_labels(container: ApiContainer) -> dict[str, str]:
    return {provider.name: provider.label for provider in container.supported_providers()}


def _to_response(model: AIModel, labels: dict[str, str]) -> ModelResponse:
    return ModelResponse(
        id=model.id,
        display_name=model.display_name,
        model_name=model.model_name,
        provider=model.provider,
        # Mã trong CSDL không còn adapter nào khai báo thì hiện nguyên mã để admin thấy mà sửa
        provider_label=labels.get(model.provider, model.provider),
        reasoning_modes=model.reasoning_modes,
        is_active=model.is_active,
        is_default=model.is_default,
        sort_order=model.sort_order,
    )


class ModeTestResponse(BaseModel):
    mode: str | None
    ok: bool
    message: str
    seconds: float


def _to_changes(request: ModelRequest) -> ModelChanges:
    return ModelChanges(**request.model_dump())


# ===== Người dùng: danh sách model được chọn khi chat =====

models_router = APIRouter(
    prefix='/models'
)


@models_router.get(path='/', response_model=list[ModelResponse])
def list_active_models(
        _: int = Depends(get_current_user_id),
        container: ApiContainer = Depends(get_container),
) -> list[ModelResponse]:
    with container.unit_of_work() as uow:
        labels = _provider_labels(container)
        return [_to_response(m, labels) for m in uow.models.list_active()]


# ===== Admin: quản lý bảng models =====

admin_models_router = APIRouter(
    prefix='/admin/models'
)


@admin_models_router.get(path='/', response_model=list[ModelResponse])
def list_models(
        _: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> list[ModelResponse]:
    with container.unit_of_work() as uow:
        labels = _provider_labels(container)
        return [_to_response(m, labels) for m in _usecase(container, uow).list_models()]


@admin_models_router.get(path='/providers', response_model=list[ProviderResponse])
def list_providers(
        _: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> list[ProviderResponse]:
    '''Nhà cung cấp đã có adapter: admin chỉ chọn được trong danh sách này khi thêm/sửa model'''
    return [ProviderResponse(name=p.name, label=p.label) for p in container.supported_providers()]


@admin_models_router.post(path='/test', response_model=list[ModeTestResponse])
def test_model(
        request: ModelRequest,
        _: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> list[ModeTestResponse]:
    '''
    Chạy thử model với dữ liệu đang nhập trong form (chưa cần lưu): gọi model một lần cho mỗi chế độ suy luận.
    Không đụng CSDL. Mỗi lần gọi có thể mất vài giây tuỳ model và mức suy luận.
    '''
    model = AIModel(
        display_name=request.display_name or '',
        model_name=request.model_name or '',
        provider=request.provider or '',
        reasoning_modes=request.reasoning_modes or [],
    )

    try:
        results = TestModelUsecase(
            reasoner_factory=container.chat_reasoner,
            supported_providers=_provider_names(container),
        ).execute(model)
    except ModelValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return [ModeTestResponse(**vars(result)) for result in results]


@admin_models_router.post(path='/', response_model=ModelResponse)
def create_model(
        request: ModelRequest,
        _: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> ModelResponse:
    return _run(container, lambda usecase: _to_response(usecase.create_model(_to_changes(request)), _provider_labels(container)))


@admin_models_router.patch(path='/{model_id}', response_model=ModelResponse)
def update_model(
        model_id: int,
        request: ModelRequest,
        _: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> ModelResponse:
    return _run(container, lambda usecase: _to_response(usecase.update_model(model_id, _to_changes(request)), _provider_labels(container)))


@admin_models_router.delete(path='/{model_id}')
def delete_model(
        model_id: int,
        _: int = Depends(require_admin),
        container: ApiContainer = Depends(get_container),
) -> dict:
    _run(container, lambda usecase: usecase.delete_model(model_id))
    return {"success": True}


def _usecase(container: ApiContainer, uow) -> AdminModelsUsecase:
    return AdminModelsUsecase(uow.models, supported_providers=_provider_names(container))


def _provider_names(container: ApiContainer) -> list[str]:
    return [provider.name for provider in container.supported_providers()]


def _run(container: ApiContainer, action):
    '''Mở phiên CSDL, chạy nghiệp vụ, đổi lỗi nghiệp vụ thành mã HTTP'''
    try:
        with container.unit_of_work() as uow:
            return action(_usecase(container, uow))

    except ModelNotFoundError:
        raise HTTPException(status_code=404, detail="Model not found")
    except ModelExistsError:
        raise HTTPException(status_code=409, detail="Model already exists")
    except ModelValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
