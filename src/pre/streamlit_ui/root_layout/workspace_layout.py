import streamlit as st

from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.actions import UIActions
from src.pre.streamlit_ui.styles import render_empty_state

FILE_ICONS = {
    "md": ":material/article:",
    "markdown": ":material/article:",
    "txt": ":material/notes:",
    "log": ":material/notes:",
    "json": ":material/data_object:",
    "csv": ":material/table_chart:",
    "py": ":material/code:",
    "sql": ":material/code:",
    "yaml": ":material/settings:",
    "yml": ":material/settings:",
}

DEFAULT_FILE_ICON = ":material/draft:"


def render_workspace(
        work_space_items: list[StateManager.WorkSpaceItem],
        opened_file: StateManager.OpenedFile | None,
        action: UIActions,
        height: int,
):
    with st.container(
            height=height,
            border=True,
    ):
        # Đang mở file thì hiện nội dung file,
        # không thì hiện danh sách file.
        if opened_file is not None:
            render_file_preview(
                opened_file,
                action,
            )

        else:
            render_file_list(
                work_space_items,
                action,
            )


def render_file_list(
        work_space_items: list[StateManager.WorkSpaceItem],
        action: UIActions,
):
    # Không hiện folder ra giao diện, chỉ hiện file với đường dẫn tương đối
    files = [
        item
        for item in work_space_items
        if not item.is_directory
    ]

    with st.container(
            horizontal=True,
            vertical_alignment="center",
    ):
        st.markdown(
            "#### :material/folder_open: Workspace",
            anchors=False,
        )

        if files:
            st.badge(
                f"{len(files)} file",
                color="gray",
            )

    if not files:
        render_empty_state(
            icon=":material/folder_off:",
            title="Chưa có file",
            hint="File do Agent tạo trong hội thoại này sẽ xuất hiện ở đây.",
        )
        return

    with st.container(
            key="file_list",
            gap=None,
    ):
        for item in files:

            # Một hàng gồm:
            #
            # [file name........] [size] [delete]
            #
            file_col, size_col, delete_col = st.columns(
                [7, 2, 1],
                vertical_alignment="center",
            )

            # -------------------------
            # OPEN FILE
            # -------------------------

            with file_col:

                if st.button(
                        item.path,
                        key=f"open_file_{item.file_id}",
                        icon=FILE_ICONS.get(
                            item.item_type.lower(),
                            DEFAULT_FILE_ICON,
                        ),
                        type="tertiary",
                        width="stretch",
                        help=item.path,
                ):
                    action.open_file(
                        file_id=item.file_id
                    )

                    st.rerun()

            with size_col:

                st.caption(
                    format_size(item.size),
                    text_alignment="right",
                )

            # -------------------------
            # DELETE FILE
            # -------------------------

            with delete_col:

                if st.button(
                        ":material/delete:",
                        key=f"delete_file_{item.file_id}",
                        type="tertiary",
                        help="Xóa file",
                ):
                    action.delete_file(
                        file_id=item.file_id
                    )

                    st.rerun()


def render_file_preview(
        file: StateManager.OpenedFile,
        action: UIActions,
):
    back_col, name_col = st.columns(
        [1, 9],
        vertical_alignment="center",
    )

    with back_col:

        if st.button(
                ":material/arrow_back:",
                key="close_file",
                type="tertiary",
                help="Quay lại danh sách file",
        ):
            action.close_file()

            st.rerun()

    with name_col:

        icon = FILE_ICONS.get(
            file.item_type.lower(),
            DEFAULT_FILE_ICON,
        )

        st.markdown(
            f"**{icon} {file.name}**"
        )

    st.divider()

    with st.container(
            key="file_preview",
    ):
        render_file_content(
            file
        )


def render_file_content(
        file: StateManager.OpenedFile
):
    """
    Render content tương ứng với từng loại file.
    """

    file_type = file.item_type.lower()

    # Markdown
    if file_type in {
        "md",
        "markdown",
    }:
        st.markdown(
            file.content
        )

    # JSON
    elif file_type == "json":
        st.json(
            file.content
        )

    # CSV
    elif file_type == "csv":
        st.dataframe(
            file.content,
            width="stretch",
        )

    # Text
    elif file_type in {
        "txt",
        "log",
        "py",
        "sql",
        "yaml",
        "yml",
    }:
        st.code(
            str(file.content),
            language=file_type if file_type in {"py", "sql", "yaml"} else None,
            wrap_lines=True,
        )

    # Fallback
    else:
        st.write(
            file.content
        )


def format_size(
        size: int
) -> str:
    if size < 1024:
        return f"{size} B"

    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"

    return f"{size / (1024 * 1024):.1f} MB"
