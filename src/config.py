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

    AGENT_WORKSPACE = DATA / 'agent_workspace'
    AGENT_WORKSPACE.mkdir(exist_ok=True, parents=True)

    load_dotenv()  # Load file biến môi trường
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    # OPEN_API_KEY = os.getenv('OPEN_API_KEY')

    OPEN_API_KEY = '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'
