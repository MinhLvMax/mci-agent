import streamlit as st
from src.pre.streamlit_ui.root_layout.workspace_layout import render_workspace
from src.pre.streamlit_ui.root_layout.chat_layout import render_chat
from src.pre.streamlit_ui import UIState


def init_state():
    if 'ui_state' not in st.session_state:
        st.session_state.ui_state = UIState()

    if "workspace_items" not in st.session_state:
        st.session_state.workspace_items = []

    if "messages" not in st.session_state:
        st.session_state.messages = []


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
