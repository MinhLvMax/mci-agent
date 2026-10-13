from dataclasses import dataclass, field


@dataclass
class AIModel:
    '''
    Một model AI người dùng được chọn khi chat, admin quản lý trong bảng models.

    provider quyết định adapter nào được gọi, model_name là tên gửi lên API của nhà cung cấp.
    reasoning_modes rỗng nghĩa là model không có chế độ suy luận để chọn.
    '''
    display_name: str
    model_name: str
    provider: str
    reasoning_modes: list[str] = field(default_factory=list)
    id: int | None = None
    is_active: bool = False
    is_default: bool = False
    sort_order: int = 0
