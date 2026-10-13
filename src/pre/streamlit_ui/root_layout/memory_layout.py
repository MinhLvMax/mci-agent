import requests
import streamlit as st
from src.pre.streamlit_ui.actions import UIActions
from src.pre.call_api.api_client import UnauthorizedError
from src.pre.streamlit_ui.inline_edit import render_click_to_edit
from src.pre.streamlit_ui.root_layout.admin_widgets import confirm_delete_dialog, render_add_button, render_row

STATUS_LABELS = {
    "active": ":green-badge[Đang áp dụng]",
    "pending": ":orange-badge[Chờ duyệt]",
    "rejected": ":gray-badge[Đã từ chối]",
}

SCOPE_LABELS = {
    "user": ":blue-badge[Riêng tôi]",
    "org": ":violet-badge[Toàn công ty]",
}


@st.dialog("Ghi nhớ của Agent", icon=":material/psychology:", width="large")
def memories_dialog(
        action: UIActions,
):
    """
    Những gì agent đã học về người dùng này từ các lượt chat và góp ý.
    Duyệt/quản lý quy định chung của công ty nằm ở trang Quản trị (chỉ admin).
    Các nút dùng st.rerun(scope="fragment") để chỉ vẽ lại dialog, không đóng dialog.
    """

    try:
        render_my_memories(action)
    except requests.RequestException:
        st.error("Không tải được dữ liệu, vui lòng thử lại.", icon=":material/error:")


def render_my_memories(action: UIActions):
    st.caption(
        "Agent tự ghi nhớ khi bạn nêu sở thích hoặc sửa câu trả lời. "
        "Ghi nhớ riêng áp dụng ngay cho bạn; đề xuất chung cho cả công ty cần admin duyệt."
    )

    memories = action.list_my_memories()
    if not memories:
        st.info("Agent chưa ghi nhớ gì về bạn.", icon=":material/info:")
        return

    for memory in memories:
        with st.container(border=True):
            st.markdown(f"{SCOPE_LABELS[memory.scope]} {STATUS_LABELS.get(memory.status, '')} `#{memory.id}`")

            if memory.scope == "user":  # Quy định chung chỉ admin sửa/xoá được
                render_edit_controls(action, memory, key_prefix="mine")
            else:
                st.markdown(memory.content)


def render_pending_memories(action: UIActions):
    st.caption("Bài học agent rút ra cho toàn công ty. Chỉ có hiệu lực sau khi được duyệt.")

    pending = action.list_org_memories(status="pending")
    if not pending:
        st.info("Không có bài học nào chờ duyệt.", icon=":material/check_circle:")
        return

    for memory in pending:
        def review_buttons(memory=memory):
            if st.button("Duyệt", key=f"approve_{memory.id}", icon=":material/check:", type="primary"):
                action.approve_memory(memory.id)
                st.rerun(scope="fragment")

            if st.button("Từ chối", key=f"reject_{memory.id}", icon=":material/close:"):
                action.reject_memory(memory.id)
                st.rerun(scope="fragment")

        render_row(
            key=f"pending_memory_{memory.id}",
            title=f"`#{memory.id}` · đề xuất bởi user {memory.proposed_by or '?'}"
                  f"{f' · hội thoại {memory.source_conversation_id}' if memory.source_conversation_id else ''}",
            body=memory.content,
            on_edit=lambda memory=memory: memory_form_dialog(action, memory),  # Sửa câu chữ trước khi duyệt
            extra=review_buttons,
        )


def render_org_memories(action: UIActions):
    if render_add_button("Thêm quy định", key="add_org_memory"):
        memory_form_dialog(action, None)

    memories = [m for m in action.list_org_memories() if m.status != "pending"]
    for memory in memories:
        render_row(
            key=f"org_memory_{memory.id}",
            title=f"{STATUS_LABELS.get(memory.status, '')} `#{memory.id}`",
            body=memory.content,
            on_edit=lambda memory=memory: memory_form_dialog(action, memory),
            on_delete=lambda memory=memory: confirm_delete_dialog(
                f"quy định #{memory.id}",
                lambda: action.delete_memory(memory.id),
            ),
        )


@st.dialog("Quy định chung", icon=":material/rule:")
def memory_form_dialog(action: UIActions, memory):
    '''Thêm (memory=None) hoặc sửa một quy định chung / bài học chờ duyệt'''
    with st.form(f"memory_form_{memory.id if memory else 'new'}", border=False):
        content = st.text_area(
            "Nội dung",
            value=memory.content if memory else "",
            placeholder="VD: Giá luôn ghi bằng VNĐ, có dấu chấm phân cách hàng nghìn",
            max_chars=500,
            height=150,
        )

        if not st.form_submit_button("Lưu", icon=":material/save:", type="primary"):
            return

    content = content.strip()
    if not content:
        st.error("Nội dung không được để trống.", icon=":material/error:")
        return

    try:
        if memory is None:
            action.create_org_memory(content)
        elif content != memory.content:
            action.update_memory(memory.id, content)
    except requests.RequestException:
        st.error("Lưu không thành công, vui lòng thử lại.", icon=":material/error:")
        return

    st.toast("Đã lưu", icon=":material/check_circle:")
    st.rerun()  # Rerun cả trang để đóng dialog


def render_edit_controls(action: UIActions, memory, key_prefix: str):
    """
    Nội dung hiện dạng đọc, click vào là sửa. Click ra ngoài hoặc bấm lưu thì lưu và quay về đọc.
    Nút xoá (archived) luôn ở bên cạnh.
    """
    key = f"{key_prefix}_memory_{memory.id}"
    editing_key = f"{key}_editing"
    draft_key = f"{key}_draft"  # Chữ đang sửa mà lưu lỗi, giữ lại để không mất

    def set_editing(editing: bool):
        st.session_state[editing_key] = editing

    toast = st.session_state.pop(f"{key}_toast", None)  # Callback không được tự vẽ, báo kết quả lưu ở đây
    if toast:
        st.toast(toast[0], icon=toast[1])

    text_col, buttons_col = st.columns([12, 1], vertical_alignment="top")

    with text_col:
        render_click_to_edit(
            key=key,
            editing=st.session_state.get(editing_key, False),
            text=st.session_state.get(draft_key, memory.content),
            render_view=lambda: st.markdown(memory.content),
            on_save=lambda text: _save_memory(action, memory, text, key),
            set_editing=set_editing,
            max_chars=500,
        )

    with buttons_col:
        if st.session_state.get(editing_key):
            # Bấm lưu làm ô mất focus nên đã lưu và thoát sửa, nút này để user yên tâm
            if st.button(":material/save:", key=f"{key}_save", type="tertiary", help="Lưu"):
                st.rerun(scope="fragment")

        if st.button(":material/delete:", key=f"{key}_delete", type="tertiary", help="Xoá"):
            action.delete_memory(memory.id)
            st.rerun(scope="fragment")


def _save_memory(action: UIActions, memory, text: str, key: str) -> bool:
    '''Lưu khi nội dung đổi. Để trống thì bỏ qua, giữ nội dung cũ'''
    draft_key = f"{key}_draft"
    content = text.strip()

    if not content or content == memory.content:
        st.session_state.pop(draft_key, None)
        return True

    try:
        action.update_memory(memory.id, content)
    except UnauthorizedError as e:  # Callback chạy ngoài try của main.py nên phải tự xử lý hết phiên
        action.state.logout()
        action.state.auth_notice = str(e)
        return False
    except requests.RequestException:
        st.session_state[draft_key] = text
        st.session_state[f"{key}_toast"] = ("Lưu không thành công, vui lòng thử lại.", ":material/error:")
        return False

    memory.content = content  # Lần gọi sau trong cùng lượt không lưu lại lần nữa
    st.session_state.pop(draft_key, None)
    st.session_state[f"{key}_toast"] = ("Đã lưu", ":material/check_circle:")
    return True
