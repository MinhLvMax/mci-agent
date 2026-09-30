import streamlit as st
from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.styles import render_empty_state

AVATARS = {
    "user": ":material/person:",
    "assistant": ":material/smart_toy:",
}


def render_chat(
        messeages_in_current_conversation: list[StateManager.Message],
        has_conversation: bool,
        error: str | None,
        height,
):
    """
    Render khung chat.

    Trả về một placeholder nằm cuối danh sách tin nhắn,
    dùng để hiện trạng thái "Agent đang xử lý" trong lúc chờ backend.
    """

    with st.container(
            height=height,
            border=True,
            autoscroll=True,
    ):
        if not has_conversation:
            render_empty_state(
                icon=":material/forum:",
                title="Chưa chọn hội thoại",
                hint="Chọn một hội thoại ở thanh bên hoặc bấm “Hội thoại mới” để bắt đầu.",
            )

        elif not messeages_in_current_conversation:
            render_empty_state(
                icon=":material/waving_hand:",
                title="Bạn cần Agent giúp gì?",
                hint="Agent có thể tìm kiếm web, đọc trang và tạo file trong workspace.",
            )

        # Messages
        for message in messeages_in_current_conversation:
            with st.chat_message(
                    message.role,
                    avatar=AVATARS.get(message.role),
            ):
                st.markdown(message.content)

        if error:
            st.error(
                f"Agent gặp lỗi: {error}",
                icon=":material/error:",
            )

        return st.empty()
