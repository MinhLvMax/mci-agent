import json

import streamlit as st
from src.pre.call_api.admin_api import AdminAPIError
from src.pre.streamlit_ui.actions import UIActions
from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.root_layout.memory_layout import render_org_memories, render_pending_memories
from src.pre.streamlit_ui.root_layout.admin_widgets import confirm_delete_dialog, render_add_button, render_row

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

    users_tab, skills_tab, models_tab, memory_tab = st.tabs(["Người dùng", "Skills", "Models", "Memory hệ thống"])

    with users_tab:
        render_users_tab(action, state)

    with skills_tab:
        render_skills_tab(action)

    with models_tab:
        render_models_tab(action)

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
    status = ":green-badge[Đang hoạt động]" if user.is_active else ":orange-badge[Chờ duyệt / đã khoá]"
    role = ":violet-badge[Admin]" if user.role == 'admin' else ":gray-badge[Người dùng]"

    def activate_button():
        # Duyệt nhanh tài khoản mới ngay trên hàng
        if not user.is_active and st.button("Kích hoạt", key=f"activate_{user.id}", icon=":material/check:", type="primary"):
            _update_user(action, user.id, is_active=True)

    render_row(
        key=f"user_{user.id}",
        title=f"**{user.email}**{' (bạn)' if is_me else ''} {role} {status}",
        on_edit=lambda: edit_user_dialog(action, user, is_me),
        extra=activate_button,
    )


@st.dialog("Sửa người dùng", icon=":material/edit:")
def edit_user_dialog(action: UIActions, user, is_me: bool):
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
                _update_user(action, user.id, **changes)  # Lưu xong rerun nên dialog tự đóng
            else:
                st.info("Không có gì thay đổi.", icon=":material/info:")

    st.divider()

    with st.form(f"password_form_{user.id}", border=False, clear_on_submit=True):
        new_password = st.text_input("Đặt lại mật khẩu", type="password", placeholder="Mật khẩu mới (≥ 8 ký tự)")
        if st.form_submit_button("Đặt lại mật khẩu", icon=":material/key:"):
            try:
                action.admin_reset_password(user.id, new_password)
                st.success(f"Đã đặt lại mật khẩu cho {user.email}", icon=":material/check_circle:")
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

    if render_add_button("Thêm skill", key="add_skill"):
        skill_form_dialog(action, None)

    for skill in action.admin_list_skills():
        active = ":green-badge[Đang dùng]" if skill.is_active else ":gray-badge[Đã tắt]"
        kind = ":violet-badge[Luôn nạp]" if skill.always_on else ":blue-badge[Tải khi cần]"

        def toggle_button(skill=skill):
            # Bật/tắt nhanh (bật = duyệt cho agent dùng)
            if st.button(
                    "Tắt" if skill.is_active else "Dùng skill này",
                    key=f"toggle_skill_{skill.id}",
                    icon=":material/toggle_off:" if skill.is_active else ":material/toggle_on:",
                    type="secondary" if skill.is_active else "primary",
            ):
                _save_skill(action, skill.id, is_active=not skill.is_active)

        render_row(
            key=f"skill_{skill.id}",
            title=f"**{skill.name}** {kind} {active}",
            caption=skill.description or None,
            on_edit=lambda skill=skill: skill_form_dialog(action, skill),
            on_delete=lambda skill=skill: confirm_delete_dialog(
                f"skill {skill.name}",
                lambda: action.admin_delete_skill(skill.id),
            ),
            extra=toggle_button,
        )


@st.dialog("Skill", icon=":material/psychology:", width="large")
def skill_form_dialog(action: UIActions, skill):
    st.markdown("##### Thêm skill" if skill is None else f"##### Sửa skill {skill.name}", anchors=False)
    render_skill_form(action, skill)


def render_skill_form(action: UIActions, skill):
    '''Form dùng chung cho thêm (skill=None) và sửa skill'''
    key = f"skill_form_{skill.id if skill else 'new'}"

    with st.form(key, border=False):
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
# Models
# ======================================================================

def render_models_tab(action: UIActions):
    st.caption(
        "Model người dùng được chọn khi chat. **Tên chuẩn** là tên gửi lên API của nhà cung cấp, "
        "**chế độ suy luận** là các giá trị model đó nhận (vd OpenAI: `low, medium, high`; "
        "Ollama: `true, false` hoặc `low, medium, high`), chế độ đầu tiên là mặc định. "
        "Hãy tra kỹ tài liệu của nhà cung cấp và bấm **Chạy thử** trong form để kiểm tra trước khi bật: "
        "model sai mà vẫn bật thì người dùng sẽ gặp lỗi khi chat. Model mới thêm mặc định tắt."
    )

    if render_add_button("Thêm model", key="add_model"):
        model_form_dialog(action, None)

    for model in action.admin_list_models():
        active = ":green-badge[Đang bật]" if model.is_active else ":gray-badge[Đã tắt]"
        default = " :violet-badge[Mặc định]" if model.is_default else ""
        provider = model.provider_label
        modes = ", ".join(f"`{mode}`" for mode in model.reasoning_modes) or "không có"

        def quick_buttons(model=model):
            if model.is_active and not model.is_default and st.button(
                    "Đặt mặc định", key=f"default_model_{model.id}", icon=":material/star:"):
                _save_model(action, model.id, is_default=True)

            # Model mặc định không tắt được, phải đặt model khác làm mặc định trước
            if not model.is_default and st.button(
                    "Tắt" if model.is_active else "Bật",
                    key=f"toggle_model_{model.id}",
                    icon=":material/toggle_off:" if model.is_active else ":material/toggle_on:",
                    type="secondary" if model.is_active else "primary",
            ):
                _save_model(action, model.id, is_active=not model.is_active)

        render_row(
            key=f"model_{model.id}",
            title=f"**{model.display_name}** :blue-badge[{provider}] {active}{default}",
            caption=f"Tên chuẩn: {model.model_name} · Suy luận: {modes}",
            on_edit=lambda model=model: model_form_dialog(action, model),
            on_delete=lambda model=model: confirm_delete_dialog(
                f"model {model.display_name}",
                lambda: action.admin_delete_model(model.id),
            ),
            extra=quick_buttons,
        )


@st.dialog("Model", icon=":material/smart_toy:", width="large")
def model_form_dialog(action: UIActions, model):
    st.markdown("##### Thêm model" if model is None else f"##### Sửa model {model.display_name}", anchors=False)

    providers = action.admin_list_providers()  # Do adapter ở backend khai báo, admin chỉ chọn trong danh sách này
    labels = {provider["name"]: provider["label"] for provider in providers}
    names = list(labels)

    with st.form(f"model_form_{model.id if model else 'new'}", border=False):
        display_name = st.text_input(
            "Tên hiển thị",
            value=model.display_name if model else "",
            placeholder="vd: GPT-5.6 Luna",
            help="Tên người dùng thấy trong ô chọn model.",
        )
        provider = st.selectbox(
            "Nhà cung cấp",
            options=names,
            index=names.index(model.provider) if model and model.provider in names else 0,
            format_func=labels.get,
            help="Quyết định backend gọi API của nhà cung cấp nào. API key cấu hình trong file .env của server.",
        )
        model_name = st.text_input(
            "Tên chuẩn",
            value=model.model_name if model else "",
            placeholder="vd: gpt-5.6-luna, openai/gpt-oss-20b, qwen3:8b",
            help="Đúng tên model trong tài liệu API của nhà cung cấp, phân biệt hoa thường.",
        )
        reasoning_modes = st.text_input(
            "Chế độ suy luận",
            value=", ".join(model.reasoning_modes) if model else "",
            placeholder="vd: low, medium, high — để trống nếu model không có",
            help="Các giá trị cách nhau bằng dấu phẩy, đúng như nhà cung cấp quy định. Chế độ đầu tiên là mặc định.",
        )

        with st.container(horizontal=True):
            is_active = st.toggle("Đang bật", value=model.is_active if model else False)
            is_default = st.toggle("Mặc định", value=model.is_default if model else False)
            sort_order = st.number_input("Thứ tự", value=model.sort_order if model else 0, step=1)

        with st.container(horizontal=True):
            test_clicked = st.form_submit_button(
                "Chạy thử",
                icon=":material/play_arrow:",
                help="Gọi model với dữ liệu đang nhập (chưa lưu) để kiểm tra tên model, nhà cung cấp "
                     "và từng chế độ suy luận. Mỗi chế độ gọi một lần, có thể mất vài giây.",
            )
            save_clicked = st.form_submit_button(
                "Thêm model" if model is None else "Lưu",
                icon=":material/save:",
                type="primary",
            )

    fields = dict(
        display_name=display_name,
        provider=provider,
        model_name=model_name,
        reasoning_modes=[mode.strip() for mode in reasoning_modes.split(",") if mode.strip()],
        is_active=is_active,
        is_default=is_default,
        sort_order=int(sort_order),
    )

    if test_clicked:
        render_model_test(action, fields)  # Chỉ hiện kết quả, dialog vẫn mở để admin sửa và chạy thử lại
        return

    if not save_clicked:
        return

    if model is None:
        try:
            created = action.admin_create_model(**fields)
        except AdminAPIError as e:
            _show_error(e)
            return
        st.toast(f"Đã thêm model {created.display_name}", icon=":material/check_circle:")
        st.rerun()
    else:
        _save_model(action, model.id, **fields)


def render_model_test(action: UIActions, fields: dict):
    '''Chạy thử model với dữ liệu đang nhập rồi hiện kết quả từng chế độ suy luận'''
    with st.spinner("Đang gọi model..."):
        try:
            results = action.admin_test_model(
                display_name=fields["display_name"],
                provider=fields["provider"],
                model_name=fields["model_name"],
                reasoning_modes=fields["reasoning_modes"],
            )
        except AdminAPIError as e:  # Dữ liệu chưa đủ để gọi (thiếu tên chuẩn...)
            _show_error(e)
            return

    failed = sum(not result["ok"] for result in results)
    if failed:
        st.warning(
            f"{failed}/{len(results)} lần gọi không thành công. Hãy tra lại tài liệu của nhà cung cấp, "
            "sửa rồi chạy thử lại.",
            icon=":material/warning:",
        )
    else:
        st.success("Tất cả đều gọi được, có thể lưu và bật model.", icon=":material/check_circle:")

    for result in results:
        mode = result["mode"]
        label = f"Suy luận `{mode}`" if mode is not None else "Không suy luận"
        text = f"**{label}** · {result['seconds']} giây  \n{result['message']}"
        if result["ok"]:
            st.markdown(f":green[:material/check_circle:] {text}")
        else:
            st.markdown(f":red[:material/cancel:] {text}")


def _save_model(action: UIActions, model_id: int, **changes):
    try:
        model = action.admin_update_model(model_id, **changes)
    except AdminAPIError as e:
        _show_error(e)
        return

    st.toast(f"Đã lưu model {model.display_name}", icon=":material/check_circle:")
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
