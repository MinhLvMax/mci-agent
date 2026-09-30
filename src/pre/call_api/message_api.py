from dataclasses import dataclass
from src.pre.call_api.api_client import APIClient


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ListMessageAPIResponse:
    messages: list[Message]


class MessageAPI:
    def __init__(self, client: APIClient):
        self.client = client

    def list(self, conversation_id: str | int):
        response = self.client.post(
            path='/list_message/',
            json={
                "conversation_id": conversation_id,
            },
        )

        response.raise_for_status()
        data = response.json()

        return ListMessageAPIResponse(
            messages=[
                Message(
                    role=m['role'],
                    content=m['content']
                )
                for m in data['messages']
            ]
        )
