from tavily import (
    TavilyClient,
    InvalidAPIKeyError,
    MissingAPIKeyError,
    UsageLimitExceededError,
    KeylessUnsupportedEndpointError,
)
from tavily.errors import ForbiddenError

# Lỗi cấu hình/hạn mức: agent thử lại cũng vô ích, tool nên báo dừng hẳn
TAVILY_FATAL_ERRORS = (
    MissingAPIKeyError,
    InvalidAPIKeyError,
    UsageLimitExceededError,  # Gồm cả TavilyKeylessLimitError
    ForbiddenError,
    KeylessUnsupportedEndpointError,
)


def create_tavily_client(api_key: str | None) -> TavilyClient:
    '''Tạo client Tavily; không có key thì ném lỗi thay vì để SDK tự chạy chế độ keyless'''
    if not api_key:
        raise MissingAPIKeyError()

    return TavilyClient(api_key=api_key)
