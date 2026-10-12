# src/inf/security/bcrypt_password_hasher.py

import bcrypt


class BcryptPasswordHasher:

    def hash(
            self,
            password: str
    ) -> str:
        """
        Mã hóa password thành password hash
        """

        # Chuyển password từ str sang bytes
        password_bytes = password.encode("utf-8")

        # Tạo salt và hash password
        hashed = bcrypt.hashpw(
            password_bytes,
            bcrypt.gensalt()
        )

        # Chuyển bytes về string để lưu database
        return hashed.decode("utf-8")

    def verify(
            self,
            password: str,
            password_hash: str,
    ) -> bool:
        """
        Kiểm tra password có khớp với hash không
        """

        # Chuyển password sang bytes
        password_bytes = password.encode("utf-8")

        # Hash trong database sang bytes
        hash_bytes = password_hash.encode("utf-8")

        # So sánh password với hash
        return bcrypt.checkpw(
            password_bytes,
            hash_bytes
        )
