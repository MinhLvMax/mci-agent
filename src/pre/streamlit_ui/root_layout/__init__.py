import streamlit as st
from src.pre.streamlit_ui.styles import render_empty_state
from src.pre.streamlit_ui.root_layout.workspace_layout import render_workspace
from src.pre.streamlit_ui.root_layout.chat_layout import render_chat, render_tool_call, AVATARS
from src.pre.streamlit_ui.root_layout.side_bar_layout import render_sidebar, rename_conversation_dialog, feedback_dialog
from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.actions import ModelChoiceError, UIActions
from src.pre.streamlit_ui.root_layout.login_layout import render_login
from src.pre.streamlit_ui.styles import inject_styles
from src.pre.streamlit_ui.labels import reasoning_label
import requests

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

    if chat_toast := state_manager.chat_toast:  # Lỗi chọn model của lượt trước, hiện sau khi rerun
        state_manager.chat_toast = None
        st.toast(chat_toast, icon=":material/error:", duration="long")

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

            render_model_picker(
                actions,
                state_manager,
                disabled=pending_prompt is not None,
            )

            if (restore_prompt := state_manager.restore_prompt) is not None:
                # Chỉ gán được trước khi vẽ ô nhập, nên lượt có lỗi lưu tạm rồi lượt sau mới điền lại
                state_manager.restore_prompt = None
                st.session_state["chat_input"] = restore_prompt

            prompt = st.chat_input(
                "Nhập yêu cầu cho Agent..."
                if has_conversation
                else "Chọn hoặc tạo một hội thoại để bắt đầu",
                key="chat_input",  # Có key để trả lại tin nhắn vào ô nhập khi model chọn bị lỗi
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
                try:
                    render_agent_stream(
                        actions.send_message_stream(pending_prompt),
                        state_manager,
                    )
                except ModelChoiceError as e:
                    # Model / chế độ suy luận chọn sai: backend không lưu gì, bỏ tin nhắn vừa hiện
                    # và trả lại vào ô nhập để người dùng đổi model rồi gửi lại
                    messages = state_manager.messages_in_current_conversation
                    if messages and messages[-1].role == "user" and messages[-1].content == pending_prompt:
                        messages.pop()
                    state_manager.restore_prompt = pending_prompt
                    state_manager.chat_toast = str(e)

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

    except (UnauthorizedError, ModelChoiceError):  # Hết phiên / chọn sai model thì không hiện như lỗi chat
        raise  # Hết phiên: main.py đưa về màn hình đăng nhập; sai model: root_layout hiện toast
    except Exception as e:
        status.update(label="Agent gặp lỗi", state="error")
        state_manager.chat_error = str(e)


ALL_PROVIDERS = "__all__"  # Lựa chọn "Tất cả" trong ô nhà cung cấp


def render_model_picker(
        actions: UIActions,
        state_manager: StateManager,
        disabled: bool,
):
    """
    Hàng chọn [Nhà cung cấp] [Model] [Suy luận] ngay trên ô nhập tin nhắn.

    - Nhà cung cấp lấy từ các model đang bật trong CSDL, đứng đầu là "Tất cả" (mặc định).
    - "Tất cả" thì ô model có mọi model, tên kèm nhà cung cấp; chọn một nhà cung cấp thì chỉ còn model của nó.
    - Ô suy luận chỉ có các chế độ của riêng model đang chọn, model không có chế độ thì ẩn.
    Lựa chọn giữ trong phiên và gửi kèm mỗi lượt chat (chỉ model_id + chế độ, nhà cung cấp chỉ để lọc).

    Ba ô dùng key cố định và đặt giá trị qua session state (không truyền index):
    truyền index thay đổi theo lựa chọn thì Streamlit coi là ô mới và làm mất lựa chọn kế tiếp của người dùng.
    """

    try:
        models = actions.list_models()
    except UnauthorizedError:
        raise
    except requests.RequestException:
        st.caption(":material/error: Không tải được danh sách model.")
        return

    if not models:
        st.caption(":material/warning: Chưa có model nào được bật, hãy báo admin.")
        return

    default = next((model for model in models if model.is_default), models[0])
    providers = list(dict.fromkeys(model.provider for model in models))  # Giữ thứ tự, model mặc định đứng đầu
    provider_options = [ALL_PROVIDERS, *providers]
    provider_labels = {model.provider: model.provider_label for model in models}  # Tên do backend gửi kèm từng model

    # Giá trị đang chọn không còn hợp lệ (lần đầu, admin vừa tắt model...) thì chọn lại trước khi vẽ ô
    # Streamlit xoá giá trị của ô có key khi ô không được vẽ (vd sang trang Quản trị),
    # nên lựa chọn còn được lưu riêng trong state_manager để lấy lại
    if st.session_state.get("picker_provider") not in provider_options:
        saved = state_manager.selected_provider
        st.session_state["picker_provider"] = saved if saved in provider_options else ALL_PROVIDERS

    with st.container(horizontal=True, vertical_alignment="center", gap="small", key="model_picker"):
        provider = st.selectbox(
            "Nhà cung cấp",
            options=provider_options,
            format_func=lambda p: "Tất cả nhà cung cấp" if p == ALL_PROVIDERS else provider_labels[p],
            key="picker_provider",
            label_visibility="collapsed",
            disabled=disabled,
            width=190,
        )
        state_manager.selected_provider = provider

        shown = [model for model in models if provider == ALL_PROVIDERS or model.provider == provider]
        by_id = {model.id: model for model in shown}

        if st.session_state.get("picker_model") not in by_id:
            # Đổi sang nhà cung cấp khác: giữ model đang chọn nếu thuộc, không thì model mặc định, không nữa thì model đầu
            fallback = default.id if default.id in by_id else shown[0].id
            st.session_state["picker_model"] = (
                state_manager.selected_model_id if state_manager.selected_model_id in by_id else fallback
            )

        model_id = st.selectbox(
            "Model",
            options=list(by_id),
            format_func=lambda id: (
                f"{by_id[id].display_name} · {by_id[id].provider_label}"
                if provider == ALL_PROVIDERS else by_id[id].display_name
            ),
            key="picker_model",
            label_visibility="collapsed",
            disabled=disabled,
            width=260,
        )
        state_manager.selected_model_id = model_id

        modes = by_id[model_id].reasoning_modes
        if not modes:
            state_manager.selected_reasoning_mode = None
            return

        if st.session_state.get("picker_reasoning") not in modes:
            saved = state_manager.selected_reasoning_mode
            # Chế độ đầu tiên admin nhập là mặc định
            st.session_state["picker_reasoning"] = saved if saved in modes else modes[0]

        state_manager.selected_reasoning_mode = st.selectbox(
            "Suy luận",
            options=modes,
            format_func=lambda mode: f"Suy luận: {reasoning_label(mode)}",
            key="picker_reasoning",
            label_visibility="collapsed",
            disabled=disabled,
            width=180,
        )


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
