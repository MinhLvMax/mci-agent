import streamlit as st
from src.pre.streamlit_ui.styles import render_empty_state
from src.pre.streamlit_ui.root_layout.workspace_layout import render_workspace
from src.pre.streamlit_ui.root_layout.chat_layout import render_chat, render_tool_call, AVATARS
from src.pre.streamlit_ui.root_layout.side_bar_layout import render_sidebar, rename_conversation_dialog, feedback_dialog
from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.actions import UIActions
from src.pre.streamlit_ui.root_layout.login_layout import render_login
from src.pre.streamlit_ui.styles import inject_styles
from src.pre.call_api.api_client import UnauthorizedError
from src.pre.streamlit_ui.root_layout.admin_layout import render_admin

# Chiều cao dự phòng, chiều cao thật do CSS tính theo màn hình (xem styles.py).
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

    render_feedback_button(actions)

    if state_manager.current_page == 'admin' and state_manager.user.role == 'admin':
        render_admin(actions, state_manager)
        return  # Trang quản trị không vẽ khung chat và workspace

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
        actions,
    )

    if not has_conversation:  # Chưa chọn hoặc tạo hội thoại
        render_welcome(actions)  # Chỉ hiện màn hình chào, không vẽ khung chat và workspace
        return  # Không có hội thoại thì không có gì để chat hay upload

    maximized = state_manager.maximized_panel

    # Panel nào phóng to thì chiếm cả chiều ngang, panel kia không vẽ.
    if maximized == "chat":
        chat_area, workspace_area = st.container(), None
    elif maximized == "workspace":
        chat_area, workspace_area = None, st.container()
    else:
        # Tỉ lệ ban đầu 3:2, user kéo ranh giới giữa hai cột để đổi (xem styles.py)
        chat_area, workspace_area = st.columns(
            [3, 2],
            gap="medium",
        )

    thinking_slot = None
    prompt = None

    if chat_area is not None:
        with chat_area:
            thinking_slot = render_chat(
                state_manager.messages_in_current_conversation,
                has_conversation,
                state_manager.chat_error,
                CHAT_HEIGHT,
                state_manager,
                on_rate=lambda rating: on_rate(actions, rating),
            )

            prompt = st.chat_input(
                "Nhập yêu cầu cho Agent..."
                if has_conversation
                else "Chọn hoặc tạo một hội thoại để bắt đầu",
                disabled=not has_conversation or pending_prompt is not None,
            )

    if workspace_area is not None:
        with workspace_area:
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

    if pending_prompt is not None and thinking_slot is None:
        # Đang phóng to Workspace thì không có chỗ hiện câu trả lời,
        # mở lại khung chat rồi mới chạy Agent ở lượt sau.
        state_manager.maximized_panel = None
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
                render_agent_stream(
                    actions.send_message_stream(pending_prompt),
                    state_manager,
                )

        st.rerun()


def render_agent_stream(
        events,
        state_manager: StateManager,
):
    """
    Vẽ dần suy luận và câu trả lời trong lúc agent đang chạy.

    Thinking và tool call nằm trong khung status, câu trả lời nằm bên dưới.
    Xong thì thu gọn status, sau rerun tin nhắn được vẽ lại từ state.
    """

    status = st.status("Đang suy nghĩ...", expanded=True)
    answer_slot = st.empty()

    thinking_slot = None  # Ô đang hiện đoạn thinking hiện tại
    thinking_text = ""
    answer_text = ""
    tool_slots = {}  # id tool call -> (ô hiển thị, dữ liệu tool call) để cập nhật khi có kết quả

    try:
        for event in events:
            data = event["data"]

            if event["type"] == "thinking":
                if thinking_slot is None:
                    thinking_slot = status.empty()
                    thinking_text = ""
                thinking_text += data["text"]
                thinking_slot.caption(thinking_text)

            elif event["type"] == "tool_call":
                thinking_slot = None  # Sau tool call thì thinking mới là một đoạn mới
                status.update(label=f"Đang chạy {data['name']}...")
                slot = status.empty()
                tool_slots[data["id"]] = (slot, data)
                with slot.container():
                    render_tool_call(data)

            elif event["type"] == "tool_result":
                status.update(label="Đang suy nghĩ...")
                slot, call = tool_slots[data["id"]]
                with slot.container():
                    render_tool_call({**call, "result": data["result"]})

                if call["name"] == "remember" and data["result"].startswith(("Saved", "Proposed")):
                    st.toast("Agent đã ghi nhớ điều này cho các lần sau", icon=":material/psychology:")

            elif event["type"] == "content":
                answer_text += data["text"]
                answer_slot.markdown(answer_text)

            elif event["type"] == "done":
                status.update(label="Đã suy nghĩ xong", state="complete", expanded=False)

    except UnauthorizedError:  # Hết phiên thì không hiện như lỗi chat
        raise  # Đẩy lên main.py để đưa user về màn hình đăng nhập
    except Exception as e:
        status.update(label="Agent gặp lỗi", state="error")
        state_manager.chat_error = str(e)


def on_rate(
        actions: UIActions,
        rating: int,
):
    """👍 gửi ngay; 👎 mở dialog để user nói rõ sai ở đâu (không nhập gì vẫn gửi được)"""
    if rating == -1:
        feedback_dialog(actions, rating=-1)
        return

    try:
        actions.send_feedback("", rating=1)
        st.toast("Cảm ơn bạn đã đánh giá!", icon=":material/thumb_up:")
    except UnauthorizedError:
        raise
    except Exception:
        st.toast("Gửi đánh giá thất bại.", icon=":material/error:")


def render_feedback_button(
        actions: UIActions,
):
    """
    Nút Góp ý luôn nằm ở góc trên bên phải, màn hình nào cũng bấm được ngay.
    """

    with st.container(key="feedback_corner"):  # CSS ghim khối này lên góc trên bên phải (xem styles.py)
        if st.button(
                "Góp ý",
                key="feedback",
                icon=":material/feedback:",
                type="secondary",
        ):
            feedback_dialog(actions)


def render_welcome(
        actions: UIActions,
):
    """
    Màn hình khi chưa có hội thoại nào được chọn.
    """

    _, center, _ = st.columns([1, 2, 1])  # Hai cột ngoài để căn giữa nội dung

    with center:
        render_empty_state(  # Dùng lại khối thông báo căn giữa sẵn có
            icon=":material/forum:",
            title="Chưa chọn hội thoại",
            hint="Chọn một hội thoại ở thanh bên hoặc bắt đầu hội thoại mới để chat với Agent và dùng workspace.",
        )

        if st.button(
                "Bắt đầu hội thoại mới",
                icon=":material/add:",
                type="primary",
                width="stretch",
                key="welcome_new_conversation",  # Key riêng để không trùng nút trên sidebar
        ):
            actions.create_new_conversation()  # Cùng logic với nút "Hội thoại mới" ở sidebar

            st.rerun()  # Vẽ lại để hiện khung chat và workspace của hội thoại vừa tạo


def render_header(
        current_conversation: StateManager.Conversation | None,
        state_manager: StateManager,
        actions: UIActions,
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

    # Một hàng gồm: [tiêu đề hội thoại] [đổi tên]
    with st.container(
            horizontal=True,
            vertical_alignment="center",
            gap="xsmall",
    ):
        st.markdown(
            f"#### {current_conversation.title}",
            anchors=False,
            width="content",
        )

        if st.button(
                ":material/edit:",
                key="rename_current_conversation",  # Key riêng để không trùng mục đổi tên trên sidebar
                type="tertiary",
                help="Đổi tên hội thoại",
        ):
            rename_conversation_dialog(  # Dùng chung dialog với sidebar
                actions,
                current_conversation,
            )

    st.caption(
        f"{len(state_manager.messages_in_current_conversation)} tin nhắn"
        f" · {file_count} file"
    )
