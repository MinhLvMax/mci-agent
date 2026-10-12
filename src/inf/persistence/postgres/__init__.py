'''
Adapter PostgreSQL: triển khai các port lưu trữ ở src/app/ports.
Bên ngoài chỉ nên dùng PostgresUnitOfWork (qua bootstrap), không import thẳng các repository.
'''
from src.inf.persistence.postgres.connection import create_postgres_connection
