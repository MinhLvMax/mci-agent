-- Cập nhật skill nghiên cứu địa danh theo bộ tool mới:
-- bỏ start_research_project / save_article / news_search / query_insights / build_research_report,
-- đọc ghi tài nguyên bằng tool file, agent tự chọn cấu trúc thư mục, có move_path / rename_path, không có tool xóa.

UPDATE skills
SET instructions = $$# Quy trình nghiên cứu địa danh

Đầu vào: tiêu đề/chủ đề bài viết + danh sách địa danh (có thể kèm từ khoá). Thiếu chủ đề hoặc địa danh thì hỏi lại người dùng trước khi làm.

## Tổ chức file
- Tự chọn cách sắp xếp thư mục cho gọn và dễ tìm. Gợi ý (không bắt buộc): một thư mục cho chủ đề, bên trong mỗi địa danh một thư mục nguồn, một thư mục insights, file kết quả để ở thư mục chủ đề.
- Trước khi bắt đầu, dùng list_files xem workspace đã có gì (người dùng có thể đã tải phụ đề, bài viết, ghi chú lên). Dùng lại tài liệu sẵn có, không tải trùng.
- Có thể dùng move_path / rename_path để sắp xếp lại file của người dùng hoặc của chính bạn. Nên sắp xếp TRƯỚC khi chạy extract_insights vì file insight ghi lại đường dẫn nguồn lúc trích.
- KHÔNG có tool xóa. Nếu thấy file thừa hoặc trùng, liệt kê trong câu trả lời để người dùng tự xóa.

## Bước 1. Thu thập nguồn cho TỪNG địa danh
1. Phụ đề video:
   - Ưu tiên phụ đề người dùng đã tải lên (.srt, .vtt, .txt).
   - Nếu chưa có: youtube_search tìm video tư liệu/khám phá nhiều view về địa danh (bỏ qua vlog giải trí, review giá tour, video dưới 2 phút), rồi youtube_transcript(video_id, save_to=...) cho 2-3 video.
   - Nếu youtube_transcript báo lỗi (máy chủ bị YouTube chặn) thì bỏ qua, ghi lại link các video phù hợp và đề nghị người dùng tự tải phụ đề lên.
2. Bài viết: web_search(kind="both") với tên địa danh (+ từ khoá); chọn 3-5 nguồn uy tín (báo chính thống, Wikipedia, trang di sản/du lịch chính thức); lưu từng bài bằng open_url(url, save_to=..., title=...).

## Bước 2. Lọc thông tin
Với từng địa danh gọi extract_insights(paths=[thư mục hoặc các file nguồn của địa danh đó], place, aliases, topic, output_path).
- paths PHẢI gồm cả file phụ đề / tài liệu người dùng đã tải lên cho địa danh đó (hoặc move_path chúng vào thư mục nguồn của địa danh trước). Kiểm tra dòng "Processed ... source files" trong kết quả: số file phải khớp với số nguồn bạn định dùng.
- Chỉ ghi vào báo cáo những nguồn đã thực sự được đưa vào extract_insights.
- aliases là các tên gọi khác của địa danh (tên tiếng Anh, tên ngắn).
- Kết quả có dòng "Work remains" thì gọi lại đúng các tham số đó cho tới khi hết.
- Nhóm nào dưới 3 thông tin thì thu thập thêm 1-2 nguồn cho địa danh đó rồi chạy lại extract_insights (nguồn đã xử lý sẽ tự bỏ qua).

## Bước 3. Câu chuyện độc đáo
CHỈ khi tất cả địa danh đã có file insight: gọi find_unique_stories(insight_paths=[các file insight], topic, output_path).

## Bước 4. Tổng hợp
- Dùng read_file đọc các file insight và file câu chuyện độc đáo.
- Dùng write_file viết một báo cáo tổng hợp ngắn (Markdown): mỗi địa danh 2-3 thông tin nổi bật nhất của mỗi nhóm kèm nguồn, câu chuyện độc đáo, danh sách file chi tiết.
- Trả lời người dùng: số nguồn và số thông tin theo từng địa danh, các điểm nổi bật, đường dẫn các file kết quả, những việc người dùng cần làm thêm (tải phụ đề còn thiếu, xóa file thừa).$$,
    config_json = '{"tools": ["list_files", "read_file", "search_files", "write_file", "move_path", "rename_path", "youtube_search", "youtube_transcript", "web_search", "open_url", "extract_insights", "find_unique_stories"]}'::jsonb,
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'nghien-cuu-dia-danh';


-- Skill core còn nhắc tới query_insights (đã bỏ)
UPDATE skills
SET instructions = replace(
        instructions,
        'dùng query_insights hoặc read_file theo từng đoạn.',
        'dùng search_files để tìm, read_file để đọc theo từng đoạn (start_line, end_line).'
    ),
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'core'
  AND instructions LIKE '%query_insights%';
