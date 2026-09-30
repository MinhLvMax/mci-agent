from datetime import datetime

import streamlit as st
from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.actions import UIActions
from log import get_logger

logger = get_logger(__name__)


def render_sidebar(
        action: UIActions,
        state: StateManager,
):
    with st.sidebar:

        # =====================
        # Brand + user section
        # =====================
        user = state.user

        st.markdown(
            "### :material/smart_toy: MCI Agent",
            anchors=False,
        )

        if user:
            # Chèn ký tự zero-width trước @ để markdown
            # không tự biến email thành link.
            email = user.email.replace("@", "​@")

            st.caption(
                f":material/account_circle: {email}"
            )

        # =====================
        # New conversation
        # =====================
        if st.button(
                "Hội thoại mới",
                icon=":material/add:",
                width="stretch",
                type="primary"
        ):
            action.create_new_conversation(
                title=datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                user_id=user.user_id
            )

            st.rerun()

        st.divider()

        # =====================
        # Conversation list
        # =====================
        st.caption("HỘI THOẠI GẦN ĐÂY")

        conversations = state.user_conversations

        if not conversations:

            st.caption(
                "Chưa có hội thoại nào."
            )

        else:

            with st.container(
                    key="conversation_list",
                    gap=None,
            ):
                for conversation in conversations:

                    active = (
                            state.current_conversation_id
                            == conversation.id
                    )

                    # Một hàng gồm:
                    #
                    # [conversation title....] [delete]
                    #
                    title_col, delete_col = st.columns(
                        [6, 1],
                        vertical_alignment="center",
                    )

                    with title_col:

                        # Hội thoại đang mở được tô nền để phân biệt.
                        if st.button(
                                conversation.title,
                                key=f"conversation_{conversation.id}",
                                icon=":material/chat_bubble:",
                                type="secondary" if active else "tertiary",
                                width="stretch",
                                help=conversation.title,
                        ):
                            action.select_conversation(
                                conversation.id
                            )

                            st.rerun()

                    with delete_col:

                        if st.button(
                                ":material/delete:",
                                key=f"delete_conversation_{conversation.id}",
                                type="tertiary",
                                help="Xóa hội thoại",
                        ):
                            confirm_delete_conversation_dialog(
                                action,
                                conversation,
                            )


@st.dialog("Xóa hội thoại", icon=":material/delete:")
def confirm_delete_conversation_dialog(
        action: UIActions,
        conversation: StateManager.Conversation,
):
    st.write(
        f"Xóa hội thoại **{conversation.title}**? "
        "Toàn bộ tin nhắn và file trong workspace của hội thoại này sẽ bị xóa."
    )

    cancel_col, confirm_col = st.columns(2)

    with cancel_col:

        if st.button(
                "Hủy",
                width="stretch",
        ):
            st.rerun()

    with confirm_col:

        if st.button(
                "Xóa",
                type="primary",
                width="stretch",
        ):
            action.delete_conversation(
                conversation.id
            )

            st.rerun()

# def render_sidebar(
#         action: UIActions,
#         state: StateManager,
# ):
#     with st.sidebar:
#
#         # if not user:  # Nếu chưa có thông tin gì của user thì hiện nút đăng nhập
#         #     if st.button(
#         #             'Signin',
#         #             use_container_width=True
#         #     ):
#         #         st.toast('Cần thực hiện logic đăng nhập')
#         #         render_login(action)
#         #
#         # else:  # Nếu có thông tin của user tức là đăng nhập rồi, thì hiện email ra
#         #     st.write(user.email)
#
#         action.list_conversations(
#             state.user.user_id
#         )
#
#         # logger.debug(state.user_conversations)
#
#         if st.button("➕ New conversation", use_container_width=True):
#             # tạo conversation mới
#             action.create_new_conversation(
#                 title=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                 user_id=state.user.user_id
#             )
#
#         st.divider()
#         if not state.user_conversations:
#             st.caption("Chưa có cuộc hội thoại nào.")
#         else:
#             for conversation in state.user_conversations:
#                 if st.button(
#                         conversation.title,
#                         key=f"conversation_{conversation.id}",
#                         use_container_width=True,
#                 ):
#                     current_conversation_id = conversation.id  # Ấn vào hội thoại nào thì ván id hội thoại hiện tại vào phiên
#                     # st.toast(f'Cần thêm logic danh sách tin nhắn hiện ra ở đây')
#                     action.select_conversation(current_conversation_id)
#                     st.rerun()
