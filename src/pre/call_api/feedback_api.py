from dataclasses import dataclass
from src.pre.call_api.api_client import APIClient


@dataclass
class SendFeedbackAPIResponse:
    id: int


class FeedbackAPI:
    def __init__(self, client: APIClient):
        self.client = client

    def send(
            self,
            content: str,
            conversation_id: int | str | None = None,
            rating: int | None = None,  # 1 = 👍, -1 = 👎
            kind: str | None = None,  # 'correction' | 'preference' | 'bug' | 'other'
    ):
        response = self.client.post(
            path='/send_feedback/',  # Thêm "/" cuối để khớp route, tránh FastAPI redirect 307
            # Không gửi user_id, backend tự lấy từ token
            json={
                'content': content,
                'conversation_id': conversation_id,
                'rating': rating,
                'kind': kind,
            },
        )
        response.raise_for_status()
        data = response.json()
        return SendFeedbackAPIResponse(
            id=data['id']
        )
