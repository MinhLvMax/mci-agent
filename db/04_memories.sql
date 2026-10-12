--
-- Bộ nhớ dài hạn của agent: bài học rút ra từ lượt chat và góp ý của người dùng.
-- scope = 'user': sở thích riêng của một người, áp dụng ngay.
-- scope = 'org' : quy định chung toàn công ty, phải được admin duyệt (pending -> active) mới vào prompt.
-- Viết dạng IF NOT EXISTS để chạy lại nhiều lần vẫn an toàn (server đã có dữ liệu thì chạy tay file này).
--

CREATE TABLE IF NOT EXISTS public.memories (
    id serial PRIMARY KEY,
    scope varchar(10) NOT NULL CHECK (scope IN ('user', 'org')),
    user_id integer REFERENCES public.users(id) ON DELETE CASCADE,  -- Chủ của memory user, NULL khi scope = 'org'
    content text NOT NULL,
    status varchar(10) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'pending', 'rejected', 'archived')),
    source varchar(20) NOT NULL,  -- 'tool' | 'extractor' | 'feedback' | 'admin'
    source_conversation_id integer REFERENCES public.conversations(id) ON DELETE SET NULL,
    source_feedback_id integer REFERENCES public.feedbacks(id) ON DELETE SET NULL,
    proposed_by integer REFERENCES public.users(id) ON DELETE SET NULL,  -- Người có lượt chat/góp ý sinh ra memory
    approved_by integer REFERENCES public.users(id) ON DELETE SET NULL,  -- Admin duyệt (chỉ dùng cho org)
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CHECK ((scope = 'user') = (user_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_memories_user_status ON public.memories USING btree (user_id, status);
CREATE INDEX IF NOT EXISTS idx_memories_scope_status ON public.memories USING btree (scope, status);

-- Góp ý có thêm đánh giá và loại để làm tín hiệu học
ALTER TABLE public.feedbacks ADD COLUMN IF NOT EXISTS rating smallint;  -- 1 = hài lòng, -1 = chưa hài lòng
ALTER TABLE public.feedbacks ADD COLUMN IF NOT EXISTS kind varchar(20);  -- 'correction' | 'preference' | 'bug' | 'other'
ALTER TABLE public.feedbacks ADD COLUMN IF NOT EXISTS processed_at timestamp without time zone;  -- Lúc extractor đã đọc
