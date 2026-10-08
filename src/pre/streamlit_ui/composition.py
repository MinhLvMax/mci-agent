from src.pre.call_api.api_client import APIClient
from src.pre.call_api.chat_api import ChatAPI
from src.pre.call_api.signin_api import SigninAPI
from src.pre.call_api.conversations_api import ConversationAPI
from src.pre.call_api.message_api import MessageAPI
from src.pre.call_api.file_api import FileAPI
from src.pre.call_api.feedback_api import FeedbackAPI


class APIService:
    def __init__(
            self,
            client: APIClient,
            chat_api: ChatAPI,
            signin_api: SigninAPI,
            conversations_api: ConversationAPI,
            message_api: MessageAPI,
            file_api: FileAPI,
            feedback_api: FeedbackAPI,
    ):
        self.client = client  # Giữ client để cập nhật token ngay sau khi đăng nhập
        self.chat_api = chat_api
        self.signin_api = signin_api
        self.conversations_api = conversations_api
        self.message_api = message_api
        self.file_api = file_api
        self.feedback_api = feedback_api


def build_api_service(
        base_url: str,
        access_token: str | None = None):
    api_client = APIClient(
        base_url=base_url,
        access_token=access_token  # Token đã lưu trong session, None nếu chưa đăng nhập
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
    feedback_api = FeedbackAPI(
        client=api_client
    )

    return APIService(
        api_client,
        chat_api,
        signin_api,
        conversations_api,
        message_api,
        file_api,
        feedback_api
    )


def build_app():
    ...


if __name__ == '__main__':
    ...
