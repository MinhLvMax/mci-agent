import psycopg
from psycopg.types.json import Jsonb
from src.dom.entities.skill import Skill

_COLUMNS = """
    id,
    name,
    description,
    instructions,
    always_on,
    config_json,
    is_active,
    sort_order
"""


def _to_skill(row) -> Skill:
    return Skill(
        id=row[0],
        name=row[1],
        description=row[2] or '',
        instructions=row[3] or '',
        always_on=row[4],
        config=row[5] or {},  # psycopg tự đổi JSONB thành dict
        is_active=row[6],
        sort_order=row[7],
    )


class PostgreSkillsRepository:
    '''
    Đọc/ghi skill do admin quản lý trong bảng skills (trang Quản trị).
    Không xoá hẳn skill: muốn bỏ thì tắt is_active.
    '''

    def __init__(self, connection: psycopg.Connection):
        self.connection = connection

    def list_active(self) -> list[Skill]:
        '''Các skill đang bật, skill always_on đứng trước và theo sort_order'''
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    description,
                    instructions,
                    always_on,
                    config_json
                FROM skills
                WHERE is_active
                ORDER BY always_on DESC, sort_order ASC, name ASC
                """
            )

            rows = cursor.fetchall()

        return [
            Skill(
                id=row[0],
                name=row[1],
                description=row[2] or '',
                instructions=row[3] or '',
                always_on=row[4],
                config=row[5] or {},  # psycopg tự đổi JSONB thành dict
            )
            for row in rows
        ]

    def list_all(self) -> list[Skill]:
        '''Tất cả skill kể cả đang tắt, cho trang quản trị'''
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_COLUMNS} FROM skills
                ORDER BY is_active DESC, always_on DESC, sort_order ASC, name ASC
                """
            )
            rows = cursor.fetchall()

        return [_to_skill(row) for row in rows]

    def get_by_id(self, skill_id: int) -> Skill | None:
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT {_COLUMNS} FROM skills WHERE id = %s", (skill_id,))
            row = cursor.fetchone()

        return _to_skill(row) if row else None

    def create(self, skill: Skill) -> Skill:
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO skills(name, description, instructions, always_on, config_json, is_active, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING {_COLUMNS}
                """,
                (
                    skill.name,
                    skill.description,
                    skill.instructions,
                    skill.always_on,
                    Jsonb(skill.config) if skill.config else None,
                    skill.is_active,
                    skill.sort_order,
                )
            )
            row = cursor.fetchone()

        self.connection.commit()
        return _to_skill(row)

    def update(self, skill: Skill) -> Skill | None:
        '''Ghi đè toàn bộ các trường của skill có id tương ứng'''
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE skills
                SET name = %s,
                    description = %s,
                    instructions = %s,
                    always_on = %s,
                    config_json = %s,
                    is_active = %s,
                    sort_order = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING {_COLUMNS}
                """,
                (
                    skill.name,
                    skill.description,
                    skill.instructions,
                    skill.always_on,
                    Jsonb(skill.config) if skill.config else None,
                    skill.is_active,
                    skill.sort_order,
                    skill.id,
                )
            )
            row = cursor.fetchone()

        self.connection.commit()
        return _to_skill(row) if row else None


if __name__ == '__main__':
    from src.app.services.postgre_db import create_postgres_connection

    conn = create_postgres_connection()
    try:
        for skill in PostgreSkillsRepository(conn).list_active():
            print(skill.name, skill.always_on, skill.description[:80])
    finally:
        conn.close()
