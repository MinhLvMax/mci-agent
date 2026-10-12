from dataclasses import dataclass
from src.pre.call_api.api_client import APIClient

# Thông báo lỗi của backend -> câu tiếng Việt hiện trên trang quản trị
ADMIN_ERRORS = {
    "You cannot remove your own admin access": "Bạn không thể tự gỡ quyền admin hoặc tự khoá tài khoản của mình.",
    "The system must keep at least one active admin": "Hệ thống phải còn ít nhất một admin đang hoạt động.",
    "Email already registered": "Email này đã có tài khoản khác dùng.",
    "Invalid email address": "Email không đúng định dạng.",
    "Password must be at least 8 characters": "Mật khẩu phải có ít nhất 8 ký tự.",
    "Password must be at most 72 bytes": "Mật khẩu quá dài (tối đa 72 byte, chữ có dấu tính 2–3 byte).",
    "Always-on skill needs instructions": "Skill \"Luôn nạp vào prompt\" phải có nội dung chỉ dẫn.",
    "On-demand skill needs a description": "Skill \"Agent tự tải khi cần\" phải có mô tả để agent biết khi nào dùng.",
    "config_json must be a JSON object": "config_json phải là một object JSON.",
    "config_json.tools must be a list of tool names": "config_json.tools phải là danh sách tên tool.",
    "Admin only": "Chỉ admin mới làm được việc này.",
}


class AdminAPIError(Exception):
    """Lỗi nghiệp vụ trả về từ API quản trị, message đã là câu tiếng Việt để hiện cho admin."""


@dataclass
class AdminUser:
    id: int
    email: str
    role: str
    is_active: bool
    created_at: str | None


@dataclass
class AdminSkill:
    id: int
    name: str
    description: str
    instructions: str
    always_on: bool
    is_active: bool
    sort_order: int
    config_json: dict


def _check(response):
    if 400 <= response.status_code < 500:
        detail = response.json().get('detail') if 'application/json' in response.headers.get('content-type', '') else None
        if isinstance(detail, str):
            if detail.startswith("Skill name"):
                raise AdminAPIError(
                    "Tên skill đã tồn tại." if "already exists" in detail
                    else "Tên skill chỉ gồm chữ thường không dấu, số và '-', ví dụ: nghien-cuu-dia-danh."
                )
            raise AdminAPIError(ADMIN_ERRORS.get(detail, detail))
        raise AdminAPIError("Dữ liệu không hợp lệ.")

    response.raise_for_status()
    return response.json()


class AdminAPI:
    '''API trang quản trị: người dùng và skill. Memory hệ thống dùng MemoryAPI'''

    def __init__(self, client: APIClient):
        self.client = client

    # ===== Người dùng =====
    def list_users(self) -> list[AdminUser]:
        return [AdminUser(**item) for item in _check(self.client.get(path='/admin/users/'))]

    def update_user(self, user_id: int, **changes) -> AdminUser:
        '''changes: email, role, is_active; trường nào không truyền thì giữ nguyên'''
        return AdminUser(**_check(self.client.patch(path=f'/admin/users/{user_id}', json=changes)))

    def reset_password(self, user_id: int, new_password: str):
        _check(self.client.post(path=f'/admin/users/{user_id}/reset_password', json={'new_password': new_password}))

    # ===== Skill =====
    def list_skills(self) -> list[AdminSkill]:
        return [AdminSkill(**item) for item in _check(self.client.get(path='/admin/skills/'))]

    def create_skill(self, **fields) -> AdminSkill:
        return AdminSkill(**_check(self.client.post(path='/admin/skills/', json=fields)))

    def update_skill(self, skill_id: int, **changes) -> AdminSkill:
        return AdminSkill(**_check(self.client.patch(path=f'/admin/skills/{skill_id}', json=changes)))
