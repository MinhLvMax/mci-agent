from datetime import datetime, timedelta, timezone

import jwt


class JWTService:

    def __init__(
            self,
            secret_key: str,
            algorithm: str,
            expire_minutes: int
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes

    def create_access_token(self, user_id: int) -> str:
        expire = (
                datetime.now(timezone.utc)
                + timedelta(minutes=self.expire_minutes)
        )

        payload = {
            "sub": str(user_id),
            "exp": expire
        }

        return jwt.encode(
            payload,
            self.secret_key,
            algorithm=self.algorithm
        )

    def decode_access_token(self, token: str) -> int:
        payload = jwt.decode(
            token,
            self.secret_key,
            algorithms=[self.algorithm]
        )

        return int(payload["sub"])
