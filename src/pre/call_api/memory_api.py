from dataclasses import dataclass
from src.pre.call_api.api_client import APIClient


@dataclass
class MemoryItem:
    id: int
    scope: str  # 'user' | 'org'
    content: str
    status: str  # 'active' | 'pending' | 'rejected'
    source: str
    proposed_by: int | None
    source_conversation_id: int | None
    updated_at: str | None


def _parse(data: dict) -> MemoryItem:
    return MemoryItem(
        id=data['id'],
        scope=data['scope'],
        content=data['content'],
        status=data['status'],
        source=data['source'],
        proposed_by=data.get('proposed_by'),
        source_conversation_id=data.get('source_conversation_id'),
        updated_at=data.get('updated_at'),
    )


class MemoryAPI:
    '''Bộ nhớ dài hạn của agent: user xem/xoá ghi nhớ riêng, admin duyệt quy định chung'''

    def __init__(self, client: APIClient):
        self.client = client

    def list_mine(self) -> list[MemoryItem]:
        response = self.client.get(path='/memories/me')
        response.raise_for_status()
        return [_parse(item) for item in response.json()]

    def is_admin(self) -> bool:
        response = self.client.get(path='/memories/permissions')
        response.raise_for_status()
        return response.json()['is_admin']

    def list_org(self, status: str | None = None) -> list[MemoryItem]:
        response = self.client.get(path='/memories/org', params={'status': status} if status else None)
        response.raise_for_status()
        return [_parse(item) for item in response.json()]

    def create_org(self, content: str) -> MemoryItem:
        response = self.client.post(path='/memories/org', json={'content': content})
        response.raise_for_status()
        return _parse(response.json())

    def approve(self, memory_id: int) -> MemoryItem:
        response = self.client.post(path=f'/memories/{memory_id}/approve')
        response.raise_for_status()
        return _parse(response.json())

    def reject(self, memory_id: int) -> MemoryItem:
        response = self.client.post(path=f'/memories/{memory_id}/reject')
        response.raise_for_status()
        return _parse(response.json())

    def update(self, memory_id: int, content: str) -> MemoryItem:
        response = self.client.patch(path=f'/memories/{memory_id}', json={'content': content})
        response.raise_for_status()
        return _parse(response.json())

    def delete(self, memory_id: int):
        response = self.client.delete(path=f'/memories/{memory_id}')
        response.raise_for_status()
