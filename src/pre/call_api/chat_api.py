from dataclasses import dataclass
from src.pre.call_api.api_client import APIClient

from log import get_logger

logger = get_logger(__name__)


@dataclass
class ChatAPIResponse:
    message: str


class ChatAPI:
    def __init__(self, client: APIClient):
        self.client = client

    def chat(self,
             conversation_id: str | int,
             new_message: str):
        response = self.client.post(
            path='/chat/',
            json={
                "conversation_id": conversation_id,
                "new_message": new_message,
            },
        )
        response.raise_for_status()
        data = response.json()
        return ChatAPIResponse(
            message=data['message']
        )
