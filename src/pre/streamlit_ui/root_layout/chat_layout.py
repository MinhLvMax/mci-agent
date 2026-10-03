import streamlit as st
from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.styles import render_empty_state, render_panel_header

AVATARS = {
    "user": ":material/person:",
    "assistant": ":material/smart_toy:",
}


def render_tool_call(step: dict):
    """Một dòng gọi tool, kèm kết quả nếu đã có."""
    kwargs = ", ".join(f"{k}={v!r}" for k, v in (step.get("kwargs") or {}).items())
    done = step.get("result") is not None
    st.markdown(
        f"{':material/check_circle:' if done else ':material/build:'} "
        f"`{step['name']}({kwargs})`"
    )
    if done:
        st.code(step["result"], language=None, wrap_lines=True)


def render_reasoning(steps: list[dict]):
    """
    Vẽ lại các bước suy luận đã lưu (thinking + tool call).
    Dùng cho tin nhắn cũ, sau khi agent chạy xong.
    """
    for step in steps:
        if step["type"] == "thinking":
            st.caption(step["text"])
        elif step["type"] == "tool_call":
            render_tool_call(step)


def render_chat(
        messeages_in_current_conversation: list[StateManager.Message],
        has_conversation: bool,
        error: str | None,
        height,
        state: StateManager,
):
    """
    Render khung chat.

    Trả về một placeholder nằm cuối danh sách tin nhắn,
    dùng để hiện trạng thái "Agent đang xử lý" trong lúc chờ backend.
    """

    render_panel_header(
        title="Hội thoại",
        icon=":material/forum:",
        panel="chat",
        state=state,
    )

    with st.container(
            key="chat_panel",  # CSS đặt chiều cao theo màn hình (xem styles.py)
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
        for index, message in enumerate(messeages_in_current_conversation):
            with st.chat_message(
                    message.role,
                    avatar=AVATARS.get(message.role),
            ):
                if message.reasoning:
                    with st.expander(
                            "Suy luận",
                            icon=":material/psychology:",
                            expanded=False,
                    ):
                        render_reasoning(message.reasoning)

                if message.role == "user":
                    # Avatar tùy chỉnh nên DOM không phân biệt được user/assistant,
                    # key này là dấu hiệu để CSS tô nền tin nhắn user.
                    with st.container(key=f"user_msg_{index}"):
                        st.markdown(message.content)
                else:
                    st.markdown(message.content)

        if error:
            st.error(
                f"Agent gặp lỗi: {error}",
                icon=":material/error:",
            )

        return st.empty()
