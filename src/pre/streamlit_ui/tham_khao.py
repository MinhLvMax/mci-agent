import streamlit as st
import pandas as pd


def init_state():
    if "workspace_items" not in st.session_state:
        st.session_state.workspace_items = []

    if "messages" not in st.session_state:
        st.session_state.messages = []


def render_workspace():
    st.subheader("📁 Workspace")

    with st.container(
            height=350,
            border=True
    ):

        if not st.session_state.workspace_items:
            st.info(
                "Workspace trống"
            )

        for index, item in enumerate(
                st.session_state.workspace_items
        ):

            st.markdown(
                f"### {item['name']}"
            )

            if item["type"] == "markdown":

                st.markdown(
                    item["content"]
                )


            elif item["type"] == "table":

                st.dataframe(
                    item["content"],
                    use_container_width=True
                )


            else:

                st.text(
                    item["content"]
                )

            st.download_button(
                "⬇ Download",
                data=str(item["content"]),
                file_name=item["name"],
                key=f"download_{index}"
            )

            st.divider()


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


def main():
    st.set_page_config(
        page_title="MCI Agent",
        layout="wide"
    )

    init_state()

    left, right = st.columns(
        [1, 2]
    )

    with left:
        render_workspace()

    with right:
        render_chat()


if __name__ == "__main__":
    main()
