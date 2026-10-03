from typing import Literal
from dataclasses import dataclass
import streamlit as st


class StateManager:
    # ===
    @dataclass
    class User:
        user_id: str | int
        email: str

    @property
    def user(self) -> User:
        return st.session_state.get("user")

    @user.setter
    def user(self, value: User):
        st.session_state["user"] = value

    # ===

    # JWT backend cấp khi đăng nhập, gửi kèm mọi request sau đó.
    @property
    def access_token(self) -> str | None:
        return st.session_state.get("access_token")  # None nghĩa là chưa đăng nhập

    @access_token.setter
    def access_token(self, value: str | None):
        st.session_state["access_token"] = value  # Lưu token trong phiên của user hiện tại

    # Thông báo hiện ở màn hình đăng nhập, ví dụ khi phiên hết hạn.
    @property
    def auth_notice(self) -> str | None:
        return st.session_state.get("auth_notice")

    @auth_notice.setter
    def auth_notice(self, value: str | None):
        st.session_state["auth_notice"] = value

    def logout(self):
        st.session_state.clear()  # Xóa toàn bộ phiên: user, token, hội thoại, file đang mở

    # ===

    @dataclass
    class Conversation:
        title: str
        id: int | str

    @property
    def user_conversations(self) -> list[Conversation]:
        if "user_conversations" not in st.session_state:
            st.session_state["user_conversations"] = []
        return st.session_state.get("user_conversations", [])

    @user_conversations.setter
    def user_conversations(self, value: list):
        st.session_state["user_conversations"] = value

    @property
    def current_conversation_id(self) -> str | int | None:
        return st.session_state.get("current_conversation_id")

    @current_conversation_id.setter
    def current_conversation_id(self, value: str | int | None):
        st.session_state["current_conversation_id"] = value

    # ===

    @dataclass
    class Message:
        role: Literal['user', 'assistant']
        content: str
        reasoning: list[dict] | None = None  # Các bước suy luận/gọi tool, hiện trong expander

    @property
    def messages_in_current_conversation(self) -> list[Message]:
        if "messeages_in_current_conversation" not in st.session_state:
            st.session_state["messeages_in_current_conversation"] = []
        return st.session_state.get("messeages_in_current_conversation", [])

    @messages_in_current_conversation.setter
    def messages_in_current_conversation(self, value: list[Message]):
        st.session_state["messeages_in_current_conversation"] = value

    # Prompt user vừa gửi, đang chờ Agent trả lời.
    @property
    def pending_prompt(self) -> str | None:
        return st.session_state.get("pending_prompt")

    @pending_prompt.setter
    def pending_prompt(self, value: str | None):
        st.session_state["pending_prompt"] = value

    # Lỗi của lượt chat gần nhất, để hiện trong khung chat.
    @property
    def chat_error(self) -> str | None:
        return st.session_state.get("chat_error")

    @chat_error.setter
    def chat_error(self, value: str | None):
        st.session_state["chat_error"] = value

    # ===
    @dataclass
    class WorkSpaceItem:
        # ID metadata trong bảng files.
        file_id: int

        is_directory: bool

        # Tên hiển thị.
        name: str

        # Đường dẫn
        path: str

        # md/json/csv/txt...
        item_type: str

        # MIME type để sau này xử lý preview/download.
        mime_type: str | None

        # Kích thước file.
        size: int

        # Chỉ lưu metadata.
        # KHÔNG lưu content ở đây.
        collapsed: bool = True

    @property
    def work_space_items(self) -> list[WorkSpaceItem]:
        if "work_space_items" not in st.session_state:
            st.session_state["work_space_items"] = []
        return st.session_state.get("work_space_items", [])

    @work_space_items.setter
    def work_space_items(self, value: list[WorkSpaceItem]):
        st.session_state["work_space_items"] = value

    # Đường dẫn các thư mục đang mở trong cây Workspace, vd {"research", "research/abc"}.
    @property
    def expanded_folders(self) -> set[str]:
        if "expanded_folders" not in st.session_state:
            st.session_state["expanded_folders"] = set()
        return st.session_state["expanded_folders"]

    @expanded_folders.setter
    def expanded_folders(self, value: set[str]):
        st.session_state["expanded_folders"] = value

    # ===

    @dataclass
    class OpenedFile:
        file_id: int
        name: str
        item_type: str
        content: object

    @property
    def opened_file(self) -> OpenedFile | None:
        return st.session_state.get(
            "opened_file"
        )

    @opened_file.setter
    def opened_file(
            self,
            value: OpenedFile | None
    ):
        st.session_state["opened_file"] = value

    # ===

    # Panel đang phóng to toàn chiều ngang, None là hiện cả hai.
    @property
    def maximized_panel(self) -> Literal["chat", "workspace"] | None:
        return st.session_state.get("maximized_panel")

    @maximized_panel.setter
    def maximized_panel(self, value: Literal["chat", "workspace"] | None):
        st.session_state["maximized_panel"] = value

    # ===

    # Số đếm gắn vào key của st.file_uploader.
    # Đổi key sau mỗi lần upload thì Streamlit tạo widget mới, ô chọn file trống trở lại.
    @property
    def upload_nonce(self) -> int:
        return st.session_state.get("upload_nonce", 0)  # Mặc định 0 cho lần đầu

    @upload_nonce.setter
    def upload_nonce(self, value: int):
        st.session_state["upload_nonce"] = value

    # Lỗi của lần upload gần nhất, mỗi phần tử là một dòng thông báo.
    @property
    def upload_errors(self) -> list[str]:
        return st.session_state.get("upload_errors", [])  # Mặc định không có lỗi

    @upload_errors.setter
    def upload_errors(self, value: list[str]):
        st.session_state["upload_errors"] = value
