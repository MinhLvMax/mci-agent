from dataclasses import dataclass
from src.pre.call_api.api_client import APIClient
from log import get_logger

logger = get_logger(__name__)

@dataclass
class Conversation:
    id: int
    user_id: int
    title: str


@dataclass
class DeleteConversationAPIResponse:
    delete_status: bool


@dataclass
class ListConversationAPIResponse:
    conversations: list[Conversation]


@dataclass
class NewConversationAPIResponse:
    title: str
    conversation_id: int


@dataclass
class UpdateConversationAPIResponse:
    id: int
    user_id: int
    title: str


class ConversationAPI:
    def __init__(self, client: APIClient):
        self.client = client

    def delete(
            self,
            conversation_id: str | int
    ):
        response = self.client.post(
            path='/delete_conversation/',
            json={
                "conversation_id": conversation_id,
            },
        )
        response.raise_for_status()
        data = response.json()
        return DeleteConversationAPIResponse(
            delete_status=data['status']
        )

    def list(self):
        response = self.client.post(
            path='/list_conversation/',  # Không gửi user_id, backend tự lấy từ token
        )
        response.raise_for_status()
        data = response.json()
        # logger.debug(data)
        return ListConversationAPIResponse(
            conversations=[
                Conversation(
                    id=conv['id'],
                    user_id=conv['user_id'],
                    title=conv['title']
                ) for conv in data['conversations']
            ]
        )

    def new(
            self,
            title: str | None = None,
    ):
        response = self.client.post(
            path='/new_conversation/',  # Thêm "/" cuối để khớp route, tránh FastAPI redirect 307
            # Không gửi user_id, backend tự lấy từ token.
            # Không có title thì backend dùng tên tạm, AI đặt tên sau tin nhắn đầu.
            json={'title': title} if title else {},
        )
        response.raise_for_status()
        data = response.json()
        return NewConversationAPIResponse(
            title=data['title'],
            conversation_id=data['conversation_id']
        )

    def update(
            self,
            conversation_id: int | str,
            title: str
    ):
        response = self.client.post(
            path='/update_conversation/',  # Thêm "/" cuối để khớp route, tránh FastAPI redirect 307
            json={
                'conversation_id': conversation_id,
                "title": title,
            },
        )
        response.raise_for_status()
        data = response.json()
        return UpdateConversationAPIResponse(
            id=data['id'],
            user_id=data['user_id'],
            title=data['title']
        )
