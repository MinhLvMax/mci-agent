import requests


class UnauthorizedError(Exception):
    """Token hết hạn hoặc không hợp lệ, UI cần đưa user về màn hình đăng nhập."""


class APIClient:

    def __init__(self, base_url: str, access_token: str | None = None):
        self.base_url = base_url
        self.access_token = access_token  # Token hiện tại, None nghĩa là chưa đăng nhập

    def _request(self, method: str, path: str, **kwargs):
        headers = kwargs.pop("headers", {})  # Lấy header caller truyền vào nếu có

        if self.access_token:  # Đã đăng nhập thì gắn token vào request
            headers["Authorization"] = f"Bearer {self.access_token}"  # Định dạng chuẩn backend đọc được

        response = requests.request(  # Gửi request với method tương ứng
            method,
            f"{self.base_url}{path}",
            headers=headers,
            **kwargs,
        )

        # Chỉ coi là hết phiên khi đã gửi token mà vẫn bị 401,
        # còn 401 lúc đăng nhập sai mật khẩu để SigninAPI tự xử lý.
        if response.status_code == 401 and self.access_token:  # Token bị backend từ chối
            raise UnauthorizedError(  # Báo lên UI để đăng xuất
                "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại."
            )

        return response  # Trả response cho các API class xử lý tiếp

    def post(self, path: str, **kwargs):
        return self._request("POST", path, **kwargs)  # Đi qua _request để luôn có token

    def get(self, path: str, **kwargs):
        return self._request("GET", path, **kwargs)  # Đi qua _request để luôn có token

    def delete(self, path: str, **kwargs):
        return self._request("DELETE", path, **kwargs)  # Đi qua _request để luôn có token

    def patch(self, path: str, **kwargs):
        return self._request("PATCH", path, **kwargs)  # Đi qua _request để luôn có token
