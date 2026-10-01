from dataclasses import dataclass
from src.pre.call_api.api_client import APIClient


@dataclass
class SigninResponse:
    id: int
    email: str
    access_token: str  # Token backend cấp sau khi đăng nhập đúng


@dataclass
class SignupResponse:
    id: int
    email: str
    is_active: bool  # False nghĩa là phải chờ quản trị viên duyệt


# Thông báo lỗi 400 của /signup/ -> câu tiếng Việt hiện cho người dùng
SIGNUP_ERRORS = {
    "Invalid email address": "Email không đúng định dạng.",
    "Password must be at least 8 characters": "Mật khẩu phải có ít nhất 8 ký tự.",
    "Password must be at most 72 bytes": "Mật khẩu quá dài (tối đa 72 byte, chữ có dấu tính 2–3 byte).",
}


class SigninAPI:
    def __init__(self, client: APIClient):
        self.client = client

    def signin(self,
               email: str,
               password: str):
        response = self.client.post(
            path='/signin/',
            json={
                "email": email,
                "password": password,
            },
        )
        if response.status_code == 401:
            raise ValueError("Email hoặc mật khẩu không chính xác.")

        if response.status_code == 403:  # Đúng mật khẩu nhưng tài khoản chưa được duyệt
            raise ValueError("Tài khoản đang chờ quản trị viên duyệt, vui lòng thử lại sau.")

        response.raise_for_status()
        data = response.json()
        return SigninResponse(
            id=data['id'],
            email=data['email'],
            access_token=data['access_token']  # Lấy token từ response đăng nhập
        )

    def signup(self,
               email: str,
               password: str) -> SignupResponse:
        response = self.client.post(
            path='/signup/',  # API công khai, không cần token
            json={
                "email": email,
                "password": password,
            },
        )

        if response.status_code == 409:  # Email đã có người đăng ký
            raise ValueError("Email này đã được đăng ký.")

        if response.status_code == 400:  # Backend từ chối email hoặc mật khẩu
            raise ValueError(SIGNUP_ERRORS.get(  # Dịch thông báo của backend sang tiếng Việt
                response.json().get("detail", ""),
                "Email hoặc mật khẩu không hợp lệ."  # Thông báo chung nếu không có trong bảng dịch
            ))

        response.raise_for_status()
        data = response.json()
        return SignupResponse(
            id=data['id'],
            email=data['email'],
            is_active=data['is_active'],
        )
