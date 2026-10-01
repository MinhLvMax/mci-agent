import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
import os

from dotenv import load_dotenv


def get_logger(name: str, path, enable_console=True) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)-8s - %(pathname)s:%(funcName)s:%(lineno)d %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if enable_console:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    file = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file.setFormatter(formatter)

    logger.addHandler(file)

    return logger


class Config:
    PROJECT_PATH = Path(__file__).resolve().parents[1]

    PATH_FOLDER_LOG = PROJECT_PATH / 'logs'
    PATH_FOLDER_LOG.mkdir(parents=True, exist_ok=True)

    logger = get_logger(
        name='agent_logger',
        path=PATH_FOLDER_LOG / 'app.log'
    )

    DATA = PROJECT_PATH / 'data'
    DATA.mkdir(exist_ok=True, parents=True)

    load_dotenv()  # Load file biến môi trường
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    OPEN_API_KEY = os.getenv('OPEN_API_KEY')
    OLLAMA_API_KEY = os.getenv('OLLAMA_API_KEY')
    OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    AGENT_ROOT_WORKSPACE = Path(os.getenv('AGENT_ROOT_WORKSPACE'))
    AGENT_ROOT_WORKSPACE.mkdir(exist_ok=True, parents=True)

    # Database
    DATABASE_URL = (
        f"postgresql://"
        f"{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:"
        f"{os.getenv('DB_PORT')}/"
        f"{os.getenv('DB_NAME')}"
    )

    # Authenticate

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM')
    JWT_EXPIRE_MINUTES = int(os.getenv('JWT_EXPIRE_MINUTES', '480'))  # Ép sang int vì timedelta không nhận chuỗi, mặc định 8 tiếng


if __name__ == '__main__':
    # print(Config.JWT_SECRET_KEY)
    # print(Config.JWT_ALGORITHM)
    # print(Config.JWT_EXPIRE_MINUTES)
    # import secrets
    #
    # print(secrets.token_urlsafe(64))
    ...