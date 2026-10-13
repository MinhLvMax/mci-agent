from dataclasses import dataclass, fields, replace

from src.app.ports.errors import DuplicateRecordError
from src.app.ports.repositories import ModelsRepository
from src.dom.entities.ai_model import AIModel


class ModelValidationError(ValueError):
    """Dữ liệu model không hợp lệ."""


class ModelExistsError(Exception):
    """Đã có model cùng nhà cung cấp + tên chuẩn."""


class ModelNotFoundError(Exception):
    """Model không tồn tại."""


@dataclass
class ModelChanges:
    '''Các trường muốn sửa, None thì giữ nguyên'''
    display_name: str | None = None
    model_name: str | None = None
    provider: str | None = None
    reasoning_modes: list[str] | None = None
    is_active: bool | None = None
    is_default: bool | None = None
    sort_order: int | None = None


class AdminModelsUsecase:
    '''
    Nghiệp vụ trang quản trị model: thêm, sửa, bật/tắt, đặt mặc định, xoá.

    Chỉ kiểm tra dữ liệu có đủ và đúng dạng. Tên chuẩn và chế độ suy luận có đúng với
    nhà cung cấp hay không thì chỉ biết lúc chat (nhà cung cấp báo lỗi), admin tự tìm hiểu trước khi thêm.
    '''

    def __init__(self, models_repository: ModelsRepository, supported_providers: list[str]):
        self.models_repository = models_repository
        self.supported_providers = supported_providers  # Nhà cung cấp đã có adapter, do bootstrap cho biết

    def list_models(self) -> list[AIModel]:
        return self.models_repository.list_all()

    def create_model(self, changes: ModelChanges) -> AIModel:
        model = AIModel(
            display_name=changes.display_name or '',
            model_name=changes.model_name or '',
            provider=changes.provider or '',
            reasoning_modes=changes.reasoning_modes or [],
            is_active=bool(changes.is_active),  # Mặc định tắt để admin kiểm tra trước khi cho mọi người dùng
            is_default=bool(changes.is_default),
            sort_order=changes.sort_order or 0,
        )
        validate_model(model, self.supported_providers)
        return self._save(self.models_repository.create, model)

    def update_model(self, model_id: int, changes: ModelChanges) -> AIModel:
        model = self.models_repository.get_by_id(model_id)
        if model is None:
            raise ModelNotFoundError(f"Model {model_id} not found")

        updated = replace(model, **{
            f.name: getattr(changes, f.name)
            for f in fields(changes)
            if getattr(changes, f.name) is not None
        })
        validate_model(updated, self.supported_providers)
        return self._save(self.models_repository.update, updated)

    def delete_model(self, model_id: int):
        if not self.models_repository.delete(model_id):
            raise ModelNotFoundError(f"Model {model_id} not found")

    def _save(self, save, model: AIModel) -> AIModel:
        try:
            return save(model)
        except DuplicateRecordError:
            raise ModelExistsError(f"Model '{model.provider}/{model.model_name}' already exists")


def validate_model(model: AIModel, supported_providers: list[str]):
    '''Làm sạch và kiểm tra dữ liệu admin nhập, dùng cho cả lưu model lẫn chạy thử'''
    model.display_name = model.display_name.strip()
    model.model_name = model.model_name.strip()
    model.provider = model.provider.strip().lower()

    # Bỏ khoảng trắng, dòng trống và chế độ trùng, giữ nguyên thứ tự admin nhập (chế độ đầu là mặc định)
    modes = [mode.strip() for mode in model.reasoning_modes if mode.strip()]
    model.reasoning_modes = list(dict.fromkeys(modes))

    if not model.display_name:
        raise ModelValidationError("Display name is required")

    if not model.model_name:
        raise ModelValidationError("Model name is required")

    if model.provider not in supported_providers:
        raise ModelValidationError("Unsupported provider")

    if model.is_default and not model.is_active:
        raise ModelValidationError("Default model must be active")  # Mặc định mà tắt thì người dùng không chat được
