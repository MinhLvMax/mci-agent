from contextlib import contextmanager

import psycopg

from src.app.ports.errors import DuplicateRecordError


@contextmanager
def translate_unique_violation(connection: psycopg.Connection, message: str):
    '''
    Bọc lệnh ghi: vi phạm ràng buộc duy nhất thì rollback rồi raise DuplicateRecordError,
    để tầng app chỉ cần biết lỗi chung của port chứ không biết psycopg.
    '''
    try:
        yield
    except psycopg.errors.UniqueViolation as e:
        connection.rollback()
        raise DuplicateRecordError(message) from e
