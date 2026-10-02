'''
Prompt dùng bên trong các tool nghiên cứu (không phải system prompt của agent).
Tách riêng ở đây để sau này có thể chuyển sang cho admin quản lý.
'''

INSIGHT_EXTRACTION_PROMPT = """Bạn là biên tập viên nghiên cứu cho đội viết content về địa danh.
Nhiệm vụ: đọc các đoạn văn bản (phụ đề video hoặc bài báo) và lọc ra những câu có giá trị cho bài viết về chủ đề dưới đây.

Chủ đề / tiêu đề bài viết: "{topic}"
Địa danh đang nghiên cứu: "{place}"
Từ khoá trọng tâm: {keywords}

Phân loại mỗi câu hữu ích vào ĐÚNG MỘT nhóm:
- data_history: con số, số liệu đo lường (diện tích, độ cao, tuổi, số lượng...), năm/niên đại, sự kiện lịch sử, nhân vật lịch sử, truyền thuyết gốc tích.
- visual_description: câu miêu tả hình ảnh, màu sắc, hình dáng, ánh sáng, âm thanh, vật thể, cảnh quan cụ thể mà người đọc có thể hình dung được.
- comparison_metaphor: câu so sánh, ẩn dụ, nhân hoá, ví von (ví dụ: "như", "tựa như", "giống", "hơn cả", "được ví là").
- fact_paradox: sự thật thú vị, ít người biết, kỷ lục, điều bất ngờ hoặc nghịch lý (hai điều tưởng mâu thuẫn cùng tồn tại).

Quy tắc:
- Chỉ lấy câu nói về "{place}". Bỏ qua câu về địa điểm khác, lời chào, quảng cáo, kêu gọi đăng ký kênh, giá vé, lịch trình tour.
- "text" phải trích NGUYÊN VĂN từ đoạn nguồn (được sửa lỗi chính tả hiển nhiên của phụ đề tự động, thêm dấu câu), không bịa thêm.
- Nếu nguồn không phải tiếng Việt, thêm trường "translation_vi" là bản dịch tiếng Việt.
- "note": 1 câu ngắn bằng tiếng Việt nói vì sao câu này đáng dùng (ví dụ: "con số gây ấn tượng về quy mô").
- "unit": số thứ tự của đoạn chứa câu đó (số trong dấu [u..]).
- Ưu tiên chất lượng hơn số lượng. Không có gì đáng giá thì trả về [].

Chỉ trả lời bằng một mảng JSON, không giải thích gì thêm:
[{{"unit": 3, "category": "data_history", "text": "...", "note": "..."}}]
"""

UNIQUE_STORIES_PROMPT = """Bạn là biên tập viên trưởng của đội viết content về địa danh.

Chủ đề / tiêu đề bài viết: "{topic}"
Các địa danh trong bài: {places}

Dưới đây là các thông tin đã lọc được cho từng địa danh (mỗi dòng có mã [id]).
Nhiệm vụ: với MỖI địa danh, tìm 1-3 câu chuyện / chi tiết ĐỘC ĐÁO CHỈ địa danh đó có,
những điểm mà các địa danh còn lại trong bài KHÔNG có hoặc không nổi bật bằng.
Tránh những điểm chung chung mà địa danh nào cũng có (ví dụ: "cảnh đẹp", "được UNESCO công nhận" nếu nhiều nơi cùng có).
Có thể kết hợp nhiều thông tin thành một câu chuyện, nhưng chỉ dùng dữ liệu được cung cấp, không bịa thêm.

{insights}

Chỉ trả lời bằng một mảng JSON, không giải thích gì thêm:
[{{"place": "<tên địa danh>", "story": "<câu chuyện độc đáo, 2-4 câu tiếng Việt>",
   "why_unique": "<vì sao các địa danh khác trong bài không có>", "evidence": ["<id>", "<id>"]}}]
"""
