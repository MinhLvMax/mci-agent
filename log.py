import logging
from logging.handlers import RotatingFileHandler
from functools import wraps
from pprint import pformat

def get_logger(name: str, path=None, enable_console=True) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(pathname)s:%(funcName)s:%(lineno)d\n"
        "   %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if enable_console:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    if path:
        file = logging.handlers.RotatingFileHandler(
            path,
            maxBytes=1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file.setFormatter(formatter)

        logger.addHandler(file)

    return logger


def log_call(logger):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__=}, {args=}, {kwargs=}\n"
                         f"   return={pformat(result)}")
            return result

        return wrapper

    return decorator


if __name__ == '__main__':
    logger = get_logger(name=__name__)


    @log_call(logger)
    def add(a, b):
        return a + b


    add(1, 2)
