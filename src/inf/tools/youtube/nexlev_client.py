import requests

NEXLEV_BASE_URL = 'https://prod.dashboard.nexlev.io/api/external'


class NexlevError(RuntimeError):
    '''Lỗi từng request (video không có phụ đề, upstream lỗi...), agent bỏ qua video đó rồi đi tiếp'''


class NexlevFatalError(NexlevError):
    '''Lỗi cấu hình/hạn mức (thiếu key, sai key, hết quota): agent thử lại cũng vô ích'''


class NexlevClient:
    TIMEOUT = 60  # Transcript video dài trả về chậm

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def get(self, path: str, **params) -> dict:
        return self._request('GET', path, params={k: v for k, v in params.items() if v is not None})

    def post(self, path: str, json: dict) -> dict:
        return self._request('POST', path, json=json)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        if not self.api_key:
            raise NexlevFatalError("NEXLEV_API_KEY is not configured")

        try:
            response = requests.request(
                method,
                f"{NEXLEV_BASE_URL}{path}",
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=self.TIMEOUT,
                **kwargs,
            )
        except requests.RequestException as e:
            raise NexlevError(f"network error: {type(e).__name__}") from e

        if response.status_code in (401, 403):
            raise NexlevFatalError("invalid NexLev API key")

        if response.status_code == 429:
            raise NexlevFatalError("NexLev quota or rate limit exceeded")

        if not response.ok:
            raise NexlevError(f"HTTP {response.status_code}: {_error_message(response)}")

        return response.json()


def _error_message(response: requests.Response) -> str:
    try:
        return str(response.json().get('message') or response.text[:200])
    except ValueError:
        return response.text[:200]
