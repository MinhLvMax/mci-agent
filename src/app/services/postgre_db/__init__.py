import psycopg
from src.config import Config

'''Cùng lắm sau này muốn thay csdl thì chỉ trừu tượng các repository thôi, không cần trựu tượng hóa cả kết nối'''


def create_postgres_connection():
    '''Hàm khởi tạo kết nối, chỉ làm nhiệm vụ tạo connection'''
    return psycopg.connect(
        Config.DATABASE_URL
    )
