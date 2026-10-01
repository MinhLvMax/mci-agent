from dataclasses import dataclass
from src.pre.call_api.api_client import APIClient


@dataclass
class SigninResponse:
    id: int
    email: str
    access_token: str  # Token backend cấp sau khi đăng nhập đúng


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

        response.raise_for_status()
        data = response.json()
        return SigninResponse(
            id=data['id'],
            email=data['email'],
            access_token=data['access_token']  # Lấy token từ response đăng nhập
        )
