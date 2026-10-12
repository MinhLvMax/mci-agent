import requests
import streamlit as st
from src.pre.streamlit_ui.actions import UIActions

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
            st.markdown(memory.content)

            if memory.scope == "user":  # Quy định chung chỉ admin sửa/xoá được
                render_edit_controls(action, memory, key_prefix="mine")


def render_pending_memories(action: UIActions):
    st.caption("Bài học agent rút ra cho toàn công ty. Chỉ có hiệu lực sau khi được duyệt.")

    pending = action.list_org_memories(status="pending")
    if not pending:
        st.info("Không có bài học nào chờ duyệt.", icon=":material/check_circle:")
        return

    for memory in pending:
        with st.container(border=True):
            st.markdown(f"`#{memory.id}` · đề xuất bởi user {memory.proposed_by or '?'}"
                        f"{f' · hội thoại {memory.source_conversation_id}' if memory.source_conversation_id else ''}")

            content = st.text_area(
                "Nội dung",
                value=memory.content,
                key=f"pending_content_{memory.id}",
                label_visibility="collapsed",
                max_chars=500,
            )

            with st.container(horizontal=True, gap="small"):
                if st.button("Duyệt", key=f"approve_{memory.id}", icon=":material/check:", type="primary"):
                    if content.strip() and content.strip() != memory.content:
                        action.update_memory(memory.id, content.strip())  # Admin sửa câu chữ trước khi duyệt
                    action.approve_memory(memory.id)
                    st.rerun(scope="fragment")

                if st.button("Từ chối", key=f"reject_{memory.id}", icon=":material/close:"):
                    action.reject_memory(memory.id)
                    st.rerun(scope="fragment")


def render_org_memories(action: UIActions):
    with st.form("new_org_memory", border=False, clear_on_submit=True):
        content = st.text_input(
            "Thêm quy định chung",
            placeholder="VD: Giá luôn ghi bằng VNĐ, có dấu chấm phân cách hàng nghìn",
            max_chars=500,
        )
        if st.form_submit_button("Thêm", icon=":material/add:") and content.strip():
            action.create_org_memory(content.strip())
            st.rerun(scope="fragment")

    memories = [m for m in action.list_org_memories() if m.status != "pending"]
    for memory in memories:
        with st.container(border=True):
            st.markdown(f"{STATUS_LABELS.get(memory.status, '')} `#{memory.id}`")
            st.markdown(memory.content)
            render_edit_controls(action, memory, key_prefix="org")


def render_edit_controls(action: UIActions, memory, key_prefix: str):
    """Sửa nội dung hoặc xoá (archived) một ghi nhớ"""
    with st.expander("Sửa / xoá", icon=":material/edit:"):
        content = st.text_area(
            "Nội dung",
            value=memory.content,
            key=f"{key_prefix}_content_{memory.id}",
            label_visibility="collapsed",
            max_chars=500,
        )

        with st.container(horizontal=True, gap="small"):
            if st.button("Lưu", key=f"{key_prefix}_save_{memory.id}", icon=":material/save:"):
                if content.strip():
                    action.update_memory(memory.id, content.strip())
                    st.rerun(scope="fragment")

            if st.button("Xoá", key=f"{key_prefix}_delete_{memory.id}", icon=":material/delete:"):
                action.delete_memory(memory.id)
                st.rerun(scope="fragment")
