import streamlit as st
from src.pre.streamlit_ui.actions import UIActions
from src.pre.streamlit_ui.state_manager import StateManager


def render_login(
        action: UIActions,
        state: StateManager,
):
    # Cột giữa chứa thẻ đăng nhập, hai cột ngoài để căn giữa.
    _, center, _ = st.columns(
        [1, 1, 1]
    )

    with center:

        st.space("large")

        with st.container(
                border=True,
        ):
            st.markdown(
                "## :material/smart_toy: MCI Agent",
                text_alignment="center",
                anchors=False,
            )

            if state.auth_notice:  # Có lý do bị đăng xuất, ví dụ phiên hết hạn
                st.info(state.auth_notice, icon=":material/schedule:")  # Báo cho user biết vì sao phải đăng nhập lại

            signin_tab, signup_tab = st.tabs(  # Hai tab dùng chung một thẻ
                ["Đăng nhập", "Đăng ký"]
            )

            with signin_tab:
                render_signin_form(action, state)

            with signup_tab:
                render_signup_form(action)


def render_signin_form(
        action: UIActions,
        state: StateManager,
):
    with st.form(
            "login_form",
            border=False,
    ):
        email = st.text_input(
            "Email",
            placeholder="ban@congty.com",
            icon=":material/mail:",
        )

        password = st.text_input(
            "Mật khẩu",
            type="password",
            icon=":material/lock:",
        )

        submitted = st.form_submit_button(
            "Đăng nhập",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    if not email or not password:
        st.error("Vui lòng nhập email và mật khẩu.")
        return

    try:
        action.signin(str(email), str(password))
        action.list_conversations()  # Backend lấy user từ token vừa nhận
    except Exception as e:
        # Không rerun ở đây, nếu không thông báo lỗi sẽ biến mất ngay.
        st.error(str(e))
        return

    st.rerun()


def render_signup_form(
        action: UIActions,
):
    with st.form(
            "signup_form",
            border=False,
    ):
        email = st.text_input(
            "Email",
            placeholder="ban@congty.com",
            icon=":material/mail:",
            key="signup_email",  # Key riêng để không đụng ô email của form đăng nhập
        )

        password = st.text_input(
            "Mật khẩu",
            type="password",
            icon=":material/lock:",
            help="Ít nhất 8 ký tự.",  # Gợi ý yêu cầu mật khẩu
            key="signup_password",
        )

        confirm_password = st.text_input(
            "Nhập lại mật khẩu",
            type="password",
            icon=":material/lock:",
            key="signup_confirm_password",
        )

        submitted = st.form_submit_button(
            "Đăng ký",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    if not email or not password:  # Kiểm tra sớm trên giao diện, đỡ một lần gọi API
        st.error("Vui lòng nhập email và mật khẩu.")
        return

    if password != confirm_password:  # Hai ô mật khẩu phải giống nhau
        st.error("Mật khẩu nhập lại không khớp.")
        return

    try:
        is_active = action.signup(str(email), str(password))  # Gọi backend tạo tài khoản
    except Exception as e:
        st.error(str(e))  # Hiện lỗi đã được dịch sang tiếng Việt ở SigninAPI
        return

    if is_active:  # Phòng khi sau này đổi sang kích hoạt ngay
        st.success("Đăng ký thành công. Bạn có thể đăng nhập ngay.")
    else:
        st.success(
            "Đăng ký thành công. Tài khoản đang chờ quản trị viên duyệt, "
            "bạn sẽ đăng nhập được sau khi được kích hoạt."
        )
