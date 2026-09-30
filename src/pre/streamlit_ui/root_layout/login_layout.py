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

            st.caption(
                "Đăng nhập để tiếp tục",
                text_alignment="center",
            )

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
                action.list_conversations(
                    state.user.user_id
                )
            except Exception as e:
                # Không rerun ở đây, nếu không thông báo lỗi sẽ biến mất ngay.
                st.error(str(e))
                return

            st.rerun()
