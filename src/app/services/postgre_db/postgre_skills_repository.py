import psycopg
from src.dom.entities.skill import Skill


class PostgreSkillsRepository:
    '''
    Đọc skill do admin quản lý trong bảng skills.
    Hiện admin thêm/sửa/xoá trực tiếp trong CSDL nên repository chỉ cần đọc.
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


if __name__ == '__main__':
    from src.app.services.postgre_db import create_postgres_connection

    conn = create_postgres_connection()
    try:
        for skill in PostgreSkillsRepository(conn).list_active():
            print(skill.name, skill.always_on, skill.description[:80])
    finally:
        conn.close()
