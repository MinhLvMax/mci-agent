from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    email: str
    password_hash: str
    id: int | None = None
    is_active: bool = False  # Tài khoản mới mặc định chờ quản trị viên duyệt, khớp mặc định của DB
    role: str = 'user'  # 'user' | 'admin', admin đầu tiên đặt trong DB, các admin sau cấp trên trang Quản trị
    created_at: datetime | None = None
