import streamlit as st


def render_chat():
    st.subheader("🤖 Agent")

    # vùng chat nhỏ hơn viewport
    with st.container(
            height=520,
            border=True
    ):

        for message in st.session_state.messages:
            with st.chat_message(
                    message["role"]
            ):
                st.markdown(
                    message["content"]
                )

    # nằm ngoài container
    prompt = st.chat_input(
        "Nhập yêu cầu..."
    )

    if prompt:
        st.session_state.messages.append(
            {
                "role": "user",
                "content": prompt
            }
        )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"Đã nhận: {prompt}"
            }
        )

        st.rerun()
