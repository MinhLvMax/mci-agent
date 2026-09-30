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

    def list(
            self,
            user_id: str | int
    ):
        response = self.client.post(
            path='/list_conversation/',
            json={
                "user_id": user_id,
            },
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
            title: str,
            user_id: int | str
    ):
        response = self.client.post(
            path='/new_conversation',
            json={
                'title': title,
                "user_id": user_id,
            },
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
            path='/update_conversation',
            json={
                'conversation_id': conversation_id,
                "title": title,
            },
        )
        response.raise_for_status()
        return response.json()
