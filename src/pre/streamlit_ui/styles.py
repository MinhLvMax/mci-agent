import streamlit as st

# Màu sắc, font, bo góc nằm trong .streamlit/config.toml.
# CSS ở đây chỉ xử lý những thứ theme không chỉnh được.
#
# Các class .st-key-* sinh ra từ tham số key của st.container.
_CSS = """
<style>
.block-container {
    padding-top: 3rem;
    padding-bottom: 1rem;
}

/* Danh sách hội thoại và danh sách file: chữ căn trái, quá dài thì cắt bằng ... */
.st-key-conversation_list button,
.st-key-file_list button,
.st-key-conversation_list button > div,
.st-key-file_list button > div {
    justify-content: flex-start;
}

.st-key-conversation_list button [data-testid="stMarkdownContainer"],
.st-key-file_list button [data-testid="stMarkdownContainer"] {
    min-width: 0;
}

.st-key-conversation_list button p,
.st-key-file_list button p {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Khung xem file hẹp nên thu nhỏ heading của nội dung markdown. */
.st-key-file_preview h1 { font-size: 1.5rem; padding-top: 0.25rem; }
.st-key-file_preview h2 { font-size: 1.25rem; }
.st-key-file_preview h3 { font-size: 1.1rem; }
""" + "".join(
    # Cây thư mục Workspace: hàng ở cấp d có key "tree_d{d}_..." (xem workspace_layout.py), thụt lề theo cấp
    f'[class*="st-key-tree_d{depth}_"] {{ padding-left: {depth * 1.1:.1f}rem; }}\n'
    for depth in range(1, 11)
) + """</style>
"""


def inject_styles():
    st.html(_CSS)


def render_empty_state(
        icon: str,
        title: str,
        hint: str,
):
    """
    Khối thông báo căn giữa dùng khi chưa có dữ liệu để hiển thị.
    """

    st.space("large")

    st.markdown(
        f"## {icon}",
        text_alignment="center",
        anchors=False,
    )

    st.markdown(
        f"**{title}**",
        text_alignment="center",
    )

    st.caption(
        hint,
        text_alignment="center",
    )
