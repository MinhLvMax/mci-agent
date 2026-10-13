# Tên hiển thị của các chế độ suy luận hay gặp, dùng chung giữa trang chat và trang quản trị.
# Giá trị thật nằm trong CSDL, chế độ chưa có nhãn thì hiện nguyên văn.
# Tên nhà cung cấp không đặt ở đây: do adapter ở backend khai báo và API gửi kèm (provider_label).

REASONING_LABELS = {
    "none": "Không suy luận",
    "minimal": "Tối thiểu",
    "low": "Thấp",
    "medium": "Vừa",
    "high": "Cao",
    "xhigh": "Rất cao",
    "max": "Tối đa",
    "true": "Bật",
    "false": "Tắt",
}


def reasoning_label(mode: str) -> str:
    return REASONING_LABELS.get(mode.lower(), mode)
