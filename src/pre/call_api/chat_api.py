import json
from dataclasses import dataclass
from typing import Iterator
from src.pre.call_api.api_client import APIClient

from src.log import get_logger

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

    def chat_stream(self,
                    conversation_id: str | int,
                    new_message: str) -> Iterator[dict]:
        '''Đọc dần từng dòng NDJSON backend gửi về, mỗi dòng là một event của agent'''
        response = self.client.post(
            path='/chat/stream',
            json={
                "conversation_id": conversation_id,
                "new_message": new_message,
            },
            stream=True,  # Không chờ tải hết body, có dòng nào đọc dòng đó
        )
        response.raise_for_status()
        try:
            for line in response.iter_lines(decode_unicode=False):
                if line:
                    yield json.loads(line)
        finally:
            response.close()
