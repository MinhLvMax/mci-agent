import json

import streamlit as st
from src.pre.call_api.admin_api import AdminAPIError
from src.pre.streamlit_ui.actions import UIActions
from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.root_layout.memory_layout import render_org_memories, render_pending_memories

ROLE_LABELS = {"user": "Người dùng", "admin": "Admin"}

# Cách nạp skill vào agent (cột always_on trong DB)
LOAD_MODES = {
    True: "Luôn nạp vào prompt",
    False: "Agent tự tải khi cần",
}


def render_admin(
        action: UIActions,
        state: StateManager,
):
    """
    Trang Quản trị, chỉ admin thấy nút vào.
    Mọi thao tác đều gọi API /admin/... nên kể cả có ai tự vào được trang này, backend vẫn chặn (403).
    """

    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown("#### :material/admin_panel_settings: Quản trị", anchors=False, width="content")
        if st.button("Về chat", icon=":material/arrow_back:", type="tertiary", key="admin_back_to_chat"):
            state.current_page = 'chat'
            st.rerun()

    users_tab, skills_tab, memory_tab = st.tabs(["Người dùng", "Skills", "Memory hệ thống"])

    with users_tab:
        render_users_tab(action, state)

    with skills_tab:
        render_skills_tab(action)

    with memory_tab:
        render_memory_tab(action)


def _show_error(e: AdminAPIError):
    st.error(str(e), icon=":material/error:")


# ======================================================================
# Người dùng
# ======================================================================

def render_users_tab(action: UIActions, state: StateManager):
    users = action.admin_list_users()

    pending_count = sum(1 for user in users if not user.is_active)
    st.caption(
        f"{len(users)} tài khoản · {pending_count} chờ duyệt / đã khoá. "
        "Tài khoản bị khoá sẽ bị đăng xuất ngay ở lần thao tác tiếp theo."
    )

    keyword = st.text_input(
        "Tìm theo email",
        placeholder="Tìm theo email...",
        label_visibility="collapsed",
        key="admin_user_search",
    ).strip().lower()

    for user in users:
        if keyword and keyword not in user.email.lower():
            continue
        render_user_row(action, user, is_me=user.id == state.user.user_id)


def render_user_row(action: UIActions, user, is_me: bool):
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            status = ":green-badge[Đang hoạt động]" if user.is_active else ":orange-badge[Chờ duyệt / đã khoá]"
            role = ":violet-badge[Admin]" if user.role == 'admin' else ":gray-badge[Người dùng]"
            st.markdown(
                f"**{user.email}**{' (bạn)' if is_me else ''} {role} {status}",
                width="content",
            )

            if not user.is_active:
                # Duyệt nhanh tài khoản mới ngay trên hàng
                if st.button("Kích hoạt", key=f"activate_{user.id}", icon=":material/check:", type="primary"):
                    _update_user(action, user.id, is_active=True)

        with st.expander("Sửa thông tin", icon=":material/edit:"):
            with st.form(f"user_form_{user.id}", border=False):
                email = st.text_input("Email", value=user.email)
                role = st.selectbox(
                    "Quyền",
                    options=list(ROLE_LABELS),
                    index=list(ROLE_LABELS).index(user.role) if user.role in ROLE_LABELS else 0,
                    format_func=ROLE_LABELS.get,
                    disabled=is_me,  # Không cho tự hạ quyền mình (backend cũng chặn)
                )
                is_active = st.toggle("Kích hoạt", value=user.is_active, disabled=is_me)

                if st.form_submit_button("Lưu", icon=":material/save:", type="primary"):
                    changes = {}
                    if email.strip().lower() != user.email:
                        changes["email"] = email.strip()
                    if role != user.role:
                        changes["role"] = role
                    if is_active != user.is_active:
                        changes["is_active"] = is_active

                    if changes:
                        _update_user(action, user.id, **changes)
                    else:
                        st.info("Không có gì thay đổi.", icon=":material/info:")

            with st.form(f"password_form_{user.id}", border=False, clear_on_submit=True):
                new_password = st.text_input("Đặt lại mật khẩu", type="password", placeholder="Mật khẩu mới (≥ 8 ký tự)")
                if st.form_submit_button("Đặt lại mật khẩu", icon=":material/key:"):
                    try:
                        action.admin_reset_password(user.id, new_password)
                        st.toast(f"Đã đặt lại mật khẩu cho {user.email}", icon=":material/check_circle:")
                    except AdminAPIError as e:
                        _show_error(e)


def _update_user(action: UIActions, user_id: int, **changes):
    try:
        user = action.admin_update_user(user_id, **changes)
    except AdminAPIError as e:
        _show_error(e)
        return

    st.toast(f"Đã cập nhật {user.email}", icon=":material/check_circle:")
    st.rerun()


# ======================================================================
# Skills
# ======================================================================

def render_skills_tab(action: UIActions):
    st.caption(
        "**Đang dùng**: công tắc chính, tắt thì agent không biết skill này tồn tại. "
        "Skill mới tạo mặc định tắt để kiểm tra nội dung trước.  \n"
        "**Cách nạp** (chỉ áp dụng khi đang dùng): *Luôn nạp vào prompt* — toàn bộ chỉ dẫn có sẵn ở mọi lượt chat, "
        "hợp với quy tắc nền như `core`. *Agent tự tải khi cần* — prompt chỉ có tên + mô tả, agent gọi `load_skill` "
        "khi yêu cầu khớp mô tả, hợp với quy trình dài cho một loại việc."
    )

    with st.expander("Thêm skill", icon=":material/add:"):
        render_skill_form(action, skill=None)

    for skill in action.admin_list_skills():
        active = ":green-badge[Đang dùng]" if skill.is_active else ":gray-badge[Đã tắt]"
        kind = ":violet-badge[Luôn nạp]" if skill.always_on else ":blue-badge[Tải khi cần]"

        with st.container(border=True):
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"**{skill.name}** {kind} {active}", width="content")

                # Bật/tắt nhanh (bật = duyệt cho agent dùng)
                if st.button(
                        "Tắt" if skill.is_active else "Dùng skill này",
                        key=f"toggle_skill_{skill.id}",
                        icon=":material/toggle_off:" if skill.is_active else ":material/toggle_on:",
                        type="secondary" if skill.is_active else "primary",
                ):
                    _save_skill(action, skill.id, is_active=not skill.is_active)

            if skill.description:
                st.caption(skill.description)

            with st.expander("Sửa", icon=":material/edit:"):
                render_skill_form(action, skill=skill)


def render_skill_form(action: UIActions, skill):
    '''Form dùng chung cho thêm (skill=None) và sửa skill'''
    key = f"skill_form_{skill.id if skill else 'new'}"

    with st.form(key, border=False, clear_on_submit=skill is None):
        name = st.text_input(
            "Tên (slug)",
            value=skill.name if skill else "",
            placeholder="vd: viet-kich-ban",
            help="Chữ thường không dấu, số và '-'. Agent gọi load_skill bằng đúng tên này.",
        )
        description = st.text_area(
            "Mô tả (khi nào dùng skill này)",
            value=skill.description if skill else "",
            height=80,
        )
        instructions = st.text_area(
            "Chỉ dẫn",
            value=skill.instructions if skill else "",
            height=300,
        )

        always_on = st.radio(
            "Cách nạp",
            options=list(LOAD_MODES),
            format_func=LOAD_MODES.get,
            index=0 if skill and skill.always_on else 1,
            horizontal=True,
        )

        with st.container(horizontal=True):
            is_active = st.toggle("Đang dùng", value=skill.is_active if skill else False)
            sort_order = st.number_input("Thứ tự", value=skill.sort_order if skill else 0, step=1)

        config_text = st.text_area(
            "config_json",
            value=json.dumps(skill.config_json, ensure_ascii=False, indent=2) if skill and skill.config_json else "{}",
            height=100,
            help='Ví dụ: {"tools": ["web_search", "open_url"]}',
        )

        if not st.form_submit_button("Tạo skill" if skill is None else "Lưu", icon=":material/save:", type="primary"):
            return

    try:
        config = json.loads(config_text or "{}")
    except json.JSONDecodeError as e:
        st.error(f"config_json không phải JSON hợp lệ: {e}", icon=":material/error:")
        return

    if not isinstance(config, dict):
        st.error("config_json phải là một object JSON, ví dụ {}.", icon=":material/error:")
        return

    fields = dict(
        name=name.strip(),
        description=description,
        instructions=instructions,
        always_on=always_on,
        is_active=is_active,
        sort_order=int(sort_order),
        config_json=config,
    )

    if skill is None:
        try:
            created = action.admin_create_skill(**fields)
        except AdminAPIError as e:
            _show_error(e)
            return
        st.toast(f"Đã tạo skill {created.name}", icon=":material/check_circle:")
        st.rerun()
    else:
        _save_skill(action, skill.id, **fields)


def _save_skill(action: UIActions, skill_id: int, **changes):
    try:
        skill = action.admin_update_skill(skill_id, **changes)
    except AdminAPIError as e:
        _show_error(e)
        return

    st.toast(f"Đã lưu skill {skill.name}", icon=":material/check_circle:")
    st.rerun()


# ======================================================================
# Memory hệ thống
# ======================================================================

@st.fragment
def render_memory_tab(action: UIActions):
    '''Fragment vì các nút duyệt dùng st.rerun(scope="fragment"), chỉ vẽ lại tab này'''
    st.markdown("##### Chờ duyệt", anchors=False)
    render_pending_memories(action)

    st.divider()

    st.markdown("##### Quy định chung", anchors=False)
    render_org_memories(action)
