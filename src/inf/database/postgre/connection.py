import psycopg
from src.config import Config


class DatabaseConnection:

    def __init__(self):
        self.connection = None

    def connect(self):
        self.connection = psycopg.connect(
            Config.DATABASE_URL
        )

        return self.connection

    def close(self):
        if self.connection:
            self.connection.close()
