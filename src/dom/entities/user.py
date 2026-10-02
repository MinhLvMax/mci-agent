from dataclasses import dataclass, field


@dataclass
class User:
    email: str
    password_hash: str
    id: int | None = None
    is_active: bool = False  # Tài khoản mới mặc định chờ quản trị viên duyệt, khớp mặc định của DB
    role: str = 'user'  # 'user' | 'admin', hiện admin được đặt trực tiếp trong DB
