import psycopg
from src.config import Config


def create_postgres_connection() -> psycopg.Connection:
    '''Hàm khởi tạo kết nối, chỉ làm nhiệm vụ tạo connection'''
    return psycopg.connect(
        Config.DATABASE_URL
    )
