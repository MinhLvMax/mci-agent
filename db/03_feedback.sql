--
-- Bảng góp ý của người dùng.
-- Viết dạng IF NOT EXISTS để chạy lại nhiều lần vẫn an toàn (dùng cho server đã có dữ liệu).
--

CREATE TABLE IF NOT EXISTS public.feedbacks (
    id serial PRIMARY KEY,
    user_id integer NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    conversation_id integer REFERENCES public.conversations(id) ON DELETE SET NULL,  -- Hội thoại đang mở lúc gửi, có thể trống
    content text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedbacks_created_at ON public.feedbacks USING btree (created_at DESC);
