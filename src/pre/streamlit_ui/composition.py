from src.pre.call_api.api_client import APIClient
from src.pre.call_api.chat_api import ChatAPI
from src.pre.call_api.signin_api import SigninAPI
from src.pre.call_api.conversations_api import ConversationAPI
from src.pre.call_api.message_api import MessageAPI
from src.pre.call_api.file_api import FileAPI


class APIService:
    def __init__(
            self,
            chat_api: ChatAPI,
            signin_api: SigninAPI,
            conversations_api: ConversationAPI,
            message_api: MessageAPI,
            file_api: FileAPI,
    ):
        self.chat_api = chat_api
        self.signin_api = signin_api
        self.conversations_api = conversations_api
        self.message_api = message_api
        self.file_api = file_api


def build_api_service():
    api_client = APIClient(
        base_url='http://127.0.0.1:8000'
    )
    chat_api = ChatAPI(
        client=api_client
    )
    signin_api = SigninAPI(
        client=api_client
    )
    conversations_api = ConversationAPI(
        client=api_client
    )
    message_api = MessageAPI(
        client=api_client
    )
    file_api = FileAPI(
        client=api_client
    )

    return APIService(
        chat_api,
        signin_api,
        conversations_api,
        message_api,
        file_api
    )


def build_app():
    ...


if __name__ == '__main__':
    ...
