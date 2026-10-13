import psycopg

from src.dom.entities.ai_model import AIModel
from src.inf.persistence.postgres.errors import translate_unique_violation

_COLUMNS = """
    id,
    display_name,
    model_name,
    provider,
    reasoning_modes,
    is_active,
    is_default,
    sort_order
"""

_ORDER = "ORDER BY is_default DESC, sort_order ASC, display_name ASC"


def _to_model(row) -> AIModel:
    return AIModel(
        id=row[0],
        display_name=row[1],
        model_name=row[2],
        provider=row[3],
        reasoning_modes=list(row[4] or []),  # psycopg tự đổi text[] thành list
        is_active=row[5],
        is_default=row[6],
        sort_order=row[7],
    )


class PostgreModelsRepository:
    '''
    Đọc/ghi các model AI trong bảng models (trang Quản trị).
    Bảng chỉ cho một model mặc định: ghi model mặc định mới thì bỏ cờ ở model cũ trong cùng transaction.
    '''

    def __init__(self, connection: psycopg.Connection):
        self.connection = connection

    def list_all(self) -> list[AIModel]:
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT {_COLUMNS} FROM models {_ORDER}")
            rows = cursor.fetchall()

        return [_to_model(row) for row in rows]

    def list_active(self) -> list[AIModel]:
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT {_COLUMNS} FROM models WHERE is_active {_ORDER}")
            rows = cursor.fetchall()

        return [_to_model(row) for row in rows]

    def get_by_id(self, model_id: int) -> AIModel | None:
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT {_COLUMNS} FROM models WHERE id = %s", (model_id,))
            row = cursor.fetchone()

        return _to_model(row) if row else None

    def get_default(self) -> AIModel | None:
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT {_COLUMNS} FROM models WHERE is_default AND is_active")
            row = cursor.fetchone()

        return _to_model(row) if row else None

    def create(self, model: AIModel) -> AIModel:
        with (
                translate_unique_violation(self.connection, "Model already exists"),
                self.connection.cursor() as cursor,
        ):
            if model.is_default:
                cursor.execute("UPDATE models SET is_default = false WHERE is_default")

            cursor.execute(
                f"""
                INSERT INTO models(display_name, model_name, provider, reasoning_modes, is_active, is_default, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING {_COLUMNS}
                """,
                (
                    model.display_name,
                    model.model_name,
                    model.provider,
                    model.reasoning_modes,
                    model.is_active,
                    model.is_default,
                    model.sort_order,
                )
            )
            row = cursor.fetchone()

        self.connection.commit()
        return _to_model(row)

    def update(self, model: AIModel) -> AIModel | None:
        with (
                translate_unique_violation(self.connection, "Model already exists"),
                self.connection.cursor() as cursor,
        ):
            if model.is_default:
                cursor.execute("UPDATE models SET is_default = false WHERE is_default AND id <> %s", (model.id,))

            cursor.execute(
                f"""
                UPDATE models
                SET display_name = %s,
                    model_name = %s,
                    provider = %s,
                    reasoning_modes = %s,
                    is_active = %s,
                    is_default = %s,
                    sort_order = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING {_COLUMNS}
                """,
                (
                    model.display_name,
                    model.model_name,
                    model.provider,
                    model.reasoning_modes,
                    model.is_active,
                    model.is_default,
                    model.sort_order,
                    model.id,
                )
            )
            row = cursor.fetchone()

        self.connection.commit()
        return _to_model(row) if row else None

    def delete(self, model_id: int) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM models WHERE id = %s RETURNING id", (model_id,))
            row = cursor.fetchone()

        self.connection.commit()
        return row is not None
