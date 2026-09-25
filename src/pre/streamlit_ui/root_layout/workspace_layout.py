import streamlit as st

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
