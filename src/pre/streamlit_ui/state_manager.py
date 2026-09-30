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
