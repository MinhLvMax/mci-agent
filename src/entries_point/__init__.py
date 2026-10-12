'''
Các entrypoint của dự án: khởi chạy dự án chỉ cần quan tâm thư mục này.

- api.py    : backend FastAPI          -> uvicorn src.entries_point.api:app
- web_ui.py : giao diện Streamlit      -> streamlit run src/entries_point/web_ui.py

Entrypoint dùng bootstrap để lắp ráp phụ thuộc rồi truyền vào tầng pre,
tầng pre không tự import bootstrap.
'''
