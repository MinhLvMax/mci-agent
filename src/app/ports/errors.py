class DuplicateRecordError(Exception):
    '''
    Ghi dữ liệu vi phạm ràng buộc duy nhất (email, tên skill...).
    Adapter lưu trữ đổi lỗi riêng của CSDL thành lỗi này để tầng app không phải biết CSDL là gì.
    '''
