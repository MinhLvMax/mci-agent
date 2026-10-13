from dataclasses import dataclass

from src.pre.call_api.api_client import APIClient


@dataclass
class AIModelItem:
    id: int
    display_name: str
    model_name: str
    provider: str  # Mã lưu ở cột models.provider
    provider_label: str  # Tên hiển thị do adapter của nhà cung cấp khai báo, backend gửi kèm
    reasoning_modes: list[str]
    is_active: bool
    is_default: bool
    sort_order: int


class ModelsAPI:
    '''Danh sách model người dùng được chọn khi chat. Quản lý model (admin) nằm ở AdminAPI'''

    def __init__(self, client: APIClient):
        self.client = client

    def list(self) -> list[AIModelItem]:
        response = self.client.get(path='/models/')
        response.raise_for_status()
        return [AIModelItem(**item) for item in response.json()]
