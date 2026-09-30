import streamlit as st
from src.pre.streamlit_ui.root_layout.workspace_layout import render_workspace
from src.pre.streamlit_ui.root_layout.chat_layout import render_chat, AVATARS
from src.pre.streamlit_ui.root_layout.side_bar_layout import render_sidebar
from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.actions import UIActions
from src.pre.streamlit_ui.root_layout.login_layout import render_login
from src.pre.streamlit_ui.styles import inject_styles

CHAT_HEIGHT = 600

# Khung workspace cao hơn khung chat đúng bằng ô nhập tin nhắn
# để đáy hai cột bằng nhau.
WORKSPACE_HEIGHT = 670


def root_layout(
        state_manager: StateManager,
        actions: UIActions
):
    # State manager nên khai báo ở đây rồi truyền vào các layout theo những gì chúng cần

    st.set_page_config(
        page_title="MCI Agent",
        page_icon=":material/smart_toy:",
        layout="wide"
    )

    inject_styles()

    if not state_manager.user:
        render_login(actions, state_manager)
        return  # Đăng nhập xong thì mới chạy code phía dưới

    render_sidebar(
        actions,
        state_manager,
    )

    current_conversation = next(
        (
            conversation
            for conversation in state_manager.user_conversations
            if conversation.id == state_manager.current_conversation_id
        ),
        None,
    )

    has_conversation = state_manager.current_conversation_id is not None
    pending_prompt = state_manager.pending_prompt

    render_header(
        current_conversation,
        state_manager,
    )

    left, right = st.columns(
        [3, 2],
        gap="medium",
    )
    with left:
        thinking_slot = render_chat(
            state_manager.messages_in_current_conversation,
            has_conversation,
            state_manager.chat_error,
            CHAT_HEIGHT,
        )

        prompt = st.chat_input(
            "Nhập yêu cầu cho Agent..."
            if has_conversation
            else "Chọn hoặc tạo một hội thoại để bắt đầu",
            disabled=not has_conversation or pending_prompt is not None,
        )

    with right:
        render_workspace(
            work_space_items=state_manager.work_space_items,
            opened_file=state_manager.opened_file,
            action=actions,
            height=WORKSPACE_HEIGHT,
        )

    if prompt:
        # Hiện tin nhắn của user ngay, lượt chạy kế tiếp mới gọi Agent.
        state_manager.messages_in_current_conversation.append(
            StateManager.Message(
                role="user",
                content=str(prompt),
            )
        )
        state_manager.chat_error = None
        state_manager.pending_prompt = str(prompt)
        st.rerun()

    if pending_prompt is not None:
        # Xóa trước khi gọi: nếu lượt chạy này bị ngắt giữa chừng
        # (user bấm nút khác) thì không gửi lại prompt lần hai.
        state_manager.pending_prompt = None

        with thinking_slot.container():
            with st.chat_message(
                    "assistant",
                    avatar=AVATARS["assistant"],
            ):
                with st.spinner(
                        "Agent đang xử lý...",
                        show_time=True,
                ):
                    try:
                        actions.send_message(pending_prompt)
                    except Exception as e:
                        state_manager.chat_error = str(e)

        st.rerun()


def render_header(
        current_conversation: StateManager.Conversation | None,
        state_manager: StateManager,
):
    if current_conversation is None:
        st.markdown(
            "#### MCI Agent",
            anchors=False,
        )
        st.caption(
            "Trợ lý AI nghiên cứu và tạo nội dung"
        )
        return

    file_count = len([
        item
        for item in state_manager.work_space_items
        if not item.is_directory
    ])

    st.markdown(
        f"#### {current_conversation.title}",
        anchors=False,
    )
    st.caption(
        f"{len(state_manager.messages_in_current_conversation)} tin nhắn"
        f" · {file_count} file"
    )
