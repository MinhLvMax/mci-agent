--
-- Các model AI người dùng được chọn khi chat, admin quản lý trên trang Quản trị.
-- provider     : nhà cung cấp, quyết định bootstrap gọi adapter nào ('openai' | 'groq' | 'ollama').
-- model_name   : tên chuẩn gửi lên API của nhà cung cấp, vd 'gpt-5.6-luna', 'openai/gpt-oss-20b'.
-- reasoning_modes: các chế độ suy luận model hỗ trợ, rỗng là model không có chế độ suy luận.
--                  OpenAI/Groq: 'low' | 'medium' | 'high'...; Ollama: 'true'/'false' hoặc 'low'/'medium'/'high'.
-- Tên / chế độ sai chỉ bị phát hiện lúc chat (nhà cung cấp báo lỗi), admin tự kiểm tra trước khi thêm.
-- Viết dạng IF NOT EXISTS để chạy lại nhiều lần vẫn an toàn (server đã có dữ liệu thì chạy tay file này).
--

CREATE TABLE IF NOT EXISTS public.models (
    id serial PRIMARY KEY,
    display_name varchar(100) NOT NULL,
    model_name varchar(200) NOT NULL,
    provider varchar(30) NOT NULL,
    reasoning_modes text[] NOT NULL DEFAULT '{}',
    is_active boolean NOT NULL DEFAULT false,  -- Model mới thêm mặc định tắt, admin bật khi đã sẵn sàng
    is_default boolean NOT NULL DEFAULT false,  -- Model chọn sẵn khi người dùng chưa chọn gì
    sort_order integer NOT NULL DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (provider, model_name)
);

-- Chỉ một model được là mặc định
CREATE UNIQUE INDEX IF NOT EXISTS idx_models_single_default ON public.models (is_default) WHERE is_default;

-- Model đang dùng trước khi có bảng này (trước đây ghi cứng trong bootstrap)
INSERT INTO public.models (display_name, model_name, provider, reasoning_modes, is_active, is_default)
VALUES ('GPT-5.6 Luna', 'gpt-5.6-luna', 'openai', '{low,medium,high}', true, true)
ON CONFLICT (provider, model_name) DO NOTHING;
