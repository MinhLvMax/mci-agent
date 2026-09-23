from dataclasses import dataclass, field


@dataclass
class User:
    email: str
    password_hash: str
    id: str | None = None

