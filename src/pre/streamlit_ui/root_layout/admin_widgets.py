from typing import Callable

import requests
import streamlit as st

from src.pre.call_api.admin_api import AdminAPIError


def render_add_button(label: str, key: str) -> bool:
    '''Nút "Thêm ..." nằm bên phải, đầu mỗi danh sách. Trả True khi được bấm'''
    with st.container(horizontal=True, horizontal_alignment="right"):
        return st.button(label, key=key, icon=":material/add:", type="primary")


def render_row(
        key: str,
        title: str,
        body: str | None = None,
        caption: str | None = None,
        on_edit: Callable[[], None] | None = None,
        on_delete: Callable[[], None] | None = None,
        extra: Callable[[], None] | None = None,
):
    """
    Một bản ghi trên trang quản trị: nội dung bên trái, các nút bên phải.

    [tiêu đề + badge / nội dung / chú thích ...........] [extra] [sửa] [xoá]

    on_edit / on_delete thường mở dialog; không truyền thì không hiện nút đó.
    """

    with st.container(border=True, horizontal=True, vertical_alignment="center", key=f"row_{key}"):
        with st.container(gap="small"):
            st.markdown(title)
            if body:
                st.markdown(body)
            if caption:
                st.caption(caption)

        if extra:
            extra()

        if on_edit and st.button(":material/edit:", key=f"edit_{key}", type="tertiary", help="Sửa"):
            on_edit()

        if on_delete and st.button(":material/delete:", key=f"delete_{key}", type="tertiary", help="Xoá"):
            on_delete()


@st.dialog("Xác nhận xoá", icon=":material/delete:")
def confirm_delete_dialog(
        label: str,
        on_confirm: Callable[[], None],
):
    '''Hỏi lại trước khi xoá. Xoá xong rerun cả trang để đóng dialog và tải lại danh sách'''
    st.markdown(f"Xoá **{label}**?  \nThao tác này không hoàn tác được.")

    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Huỷ", key="confirm_delete_cancel"):
            st.rerun()

        if st.button("Xoá", key="confirm_delete_ok", type="primary", icon=":material/delete:"):
            try:
                on_confirm()
            except AdminAPIError as e:
                st.error(str(e), icon=":material/error:")
                return
            except requests.RequestException:
                st.error("Xoá không thành công, vui lòng thử lại.", icon=":material/error:")
                return

            st.toast(f"Đã xoá {label}", icon=":material/check_circle:")
            st.rerun()
