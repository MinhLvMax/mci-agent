from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.composition import APIService
from src.pre.streamlit_ui.state_manager import StateManager
from log import get_logger

logger = get_logger(__name__)


class UIActions:
    '''Mỗi ui làm 3 việc, thực hiện hành động, nhận kết quả, set vào state'''

    def __init__(self, state: StateManager, api: APIService):
        self.state = state
        self.api = api

    def signin(self, email: str, password: str):
        response = self.api.signin_api.signin(email, password)
        self.state.user = StateManager.User(
            user_id=response.id,
            email=response.email
        )
        self.state.access_token = response.access_token  # Lưu token để các lần rerun sau dùng lại
        self.api.client.access_token = response.access_token  # Gắn ngay vào client cho các request còn lại của lượt chạy này
        self.state.auth_notice = None  # Đăng nhập lại thành công thì bỏ thông báo hết phiên

    def logout(self):
        """
        Đăng xuất ở phía UI.

        JWT không lưu ở server nên backend không cần gọi API nào:
        chỉ cần xóa token khỏi phiên là các request sau không còn được xác thực.
        """

        self.state.logout()  # Xóa user, token, hội thoại, file đang mở khỏi session
        self.api.client.access_token = None  # Gỡ token khỏi client phòng khi còn request trong lượt chạy này

    def list_conversations(self):
        response = self.api.conversations_api.list()  # Backend tự biết user nào nhờ token
        # logger.debug(response.conversations)
        conversations = response.conversations
        self.state.user_conversations = [
            StateManager.Conversation(
                id=conv.id,
                title=conv.title
            )
            for conv in conversations
        ]
        # logger.debug(self.state.user_conversations)

    def select_conversation(self, conversation_id: int, ):
        """
            Khi chuyển conversation:

            1. Set conversation hiện tại.
            2. Load messages.
            3. Load metadata file của workspace.
            4. Đóng file đang mở của conversation trước.
            """

        # Conversation hiện tại.
        self.state.current_conversation_id = conversation_id

        # Load msgs
        response = self.api.message_api.list(conversation_id)
        self.state.messages_in_current_conversation = [
            StateManager.Message(role=m.role, content=m.content)
            for m in response.messages
        ]
        # Load files meta
        self.list_files(
            conversation_id=conversation_id
        )
        # File đang mở thuộc conversation cũ
        # nên phải reset.
        self.state.opened_file = None
        self.state.chat_error = None

    def send_message(self, prompt: str):
        # self.state.messages_in_current_conversation.append(
        #     StateManager.Message(role="user", content=prompt)
        # )

        result = self.api.chat_api.chat(
            conversation_id=self.state.current_conversation_id,
            new_message=prompt,
        )

        self.state.messages_in_current_conversation.append(
            StateManager.Message(role="assistant", content=result.message)
        )

        # Agent có thể vừa tạo/xóa/sửa file.
        # Vì vậy sau mỗi lượt Agent chạy xong,
        # refresh lại metadata workspace.
        self.list_files(
            conversation_id=self.state.current_conversation_id
        )

    def create_new_conversation(self, title: str):
        response = self.api.conversations_api.new(
            title=title,  # Không cần user_id, backend lấy từ token
        )
        self.state.current_conversation_id = response.conversation_id
        self.select_conversation(conversation_id=response.conversation_id)

        # Để hội thoại mới hiện ngay ở sidebar.
        self.list_conversations()

    def delete_conversation(
            self,
            conversation_id: int | str
    ):
        """
        Xóa conversation thông qua backend.

        Sau khi xóa thành công:
        - nếu đang mở chính conversation vừa xóa thì dọn khung chat và workspace
        - refresh danh sách conversation ở sidebar
        """

        response = self.api.conversations_api.delete(
            conversation_id=conversation_id
        )

        if not response.delete_status:
            return False

        if self.state.current_conversation_id == conversation_id:
            self.state.current_conversation_id = None
            self.state.messages_in_current_conversation = []
            self.state.work_space_items = []
            self.state.opened_file = None

        self.list_conversations()

        return True

    def list_files(
            self,
            conversation_id: int | str
    ):
        """
        Load danh sách metadata file của conversation
        vào session state.

        Không load content tại đây.
        """

        response = self.api.file_api.list(
            conversation_id=conversation_id
        )

        self.state.work_space_items = [
            StateManager.WorkSpaceItem(
                file_id=file.id,
                name=file.name,
                is_directory=file.is_directory,
                path=file.path,
                item_type=file.file_type or "",
                mime_type=file.mime_type,
                size=file.size,
                collapsed=True,
            )
            for file in response.files
        ]

    def open_file(
            self,
            file_id: int
    ):
        """
        User click một file trong workspace.
        Lúc này mới gọi backend để lấy content.
        """

        response = self.api.file_api.get(
            file_id=file_id
        )

        self.state.opened_file = StateManager.OpenedFile(
            file_id=response.file.id,
            name=response.file.name,
            item_type=response.file.file_type or "",
            content=response.content,
        )

    def close_file(self):
        """
        Đóng file đang xem, quay lại danh sách file.
        """

        self.state.opened_file = None

    def download_file(
            self,
            file_id: int
    ) -> bytes:
        """
        Lấy bytes của file để st.download_button gửi về máy user.

        Hàm này được st.download_button gọi trên thread riêng,
        chỉ khi user bấm nút, nên không được đụng tới session state.
        """

        return self.api.file_api.download(
            file_id=file_id
        )

    def delete_file(
            self,
            file_id: int
    ):
        """
        Xóa file thông qua backend.

        Sau khi xóa thành công:
        - refresh danh sách file
        - đóng file nếu file đang mở chính là file vừa xóa
        """

        response = self.api.file_api.delete(
            file_id=file_id
        )

        if not response.success:
            return False

        # Nếu đang mở chính file vừa xóa
        # thì đóng preview.
        if (
                self.state.opened_file is not None
                and self.state.opened_file.file_id == file_id
        ):
            self.state.opened_file = None

        # Reload metadata workspace.
        self.list_files(
            conversation_id=self.state.current_conversation_id
        )

        return True
