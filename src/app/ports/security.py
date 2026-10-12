from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        '''Băm mật khẩu để lưu, không bao giờ lưu mật khẩu gốc'''

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenExpiredError(Exception):
    '''Token đúng chữ ký nhưng đã hết hạn'''


class InvalidTokenError(Exception):
    '''Token bị sửa, sai chữ ký hoặc sai định dạng'''


class TokenService(Protocol):
    '''Cấp và kiểm tra access token. Lỗi của thư viện token phải được đổi thành 2 lỗi ở trên'''

    def create_access_token(self, user_id: int) -> str: ...

    def decode_access_token(self, token: str) -> int:
        '''Trả về user_id. Raise TokenExpiredError hoặc InvalidTokenError'''
