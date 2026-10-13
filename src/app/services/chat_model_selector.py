from src.app.ports.model_reasoner import ModelUnavailableError
from src.app.ports.repositories import ModelsRepository
from src.dom.entities.ai_model import AIModel


def select_chat_model(
        models_repository: ModelsRepository,
        model_id: int | None,
        reasoning_mode: str | None,
) -> tuple[AIModel, str | None]:
    '''
    Chọn model và chế độ suy luận cho lượt chat từ lựa chọn của người dùng.

    - Không gửi model_id: dùng model mặc định admin đặt.
    - Model phải đang bật (admin có thể vừa tắt trong lúc người dùng đang mở trang).
    - Model không có chế độ suy luận thì bỏ qua reasoning_mode; có thì phải nằm trong danh sách,
      không gửi thì lấy chế độ đầu tiên admin nhập.

    Sai thì raise ModelUnavailableError với câu tiếng Việt để hiện cho người dùng.
    '''
    if model_id is None:
        model = models_repository.get_default()
        if model is None:
            raise ModelUnavailableError("Chưa có model mặc định nào được bật. Hãy chọn model hoặc báo admin.")
    else:
        model = models_repository.get_by_id(model_id)
        if model is None or not model.is_active:
            raise ModelUnavailableError("Model bạn chọn không còn được bật. Hãy tải lại trang và chọn model khác.")

    if not model.reasoning_modes:
        return model, None

    if reasoning_mode is None:
        return model, model.reasoning_modes[0]

    if reasoning_mode not in model.reasoning_modes:
        raise ModelUnavailableError(
            f"Model {model.display_name} không có chế độ suy luận '{reasoning_mode}'. Hãy chọn chế độ khác."
        )

    return model, reasoning_mode
