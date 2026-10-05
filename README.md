# mci-agent
MCI Agent - an AI agent platform that supports content creation workflows through intelligent analysis, automation, and workflow assistance.


## Triển khai (VPS + Docker)

Gồm 4 container: `caddy` (cổng 80) → `ui` (Streamlit) → `api` (FastAPI) → `db` (PostgreSQL). Chỉ cổng 80 mở ra ngoài.

1. VPS Ubuntu, tối thiểu 2 vCPU / 2–4 GB RAM. Cài Docker: `curl -fsSL https://get.docker.com | sh`
2. Firewall: `ufw allow 22,80/tcp && ufw enable`
3. `git clone <repo> && cd <repo>`
4. `cp .env.example .env` và điền giá trị (mật khẩu DB mới, `JWT_SECRET_KEY` mới, các API key)
5. `docker compose up -d --build`, sau đó mở `http://<IP-VPS>`

- Bảng và dữ liệu `skills` tự tạo từ `db/*.sql` ở lần chạy đầu (khi volume `pgdata` còn trống).
- Cập nhật code: `git pull && docker compose up -d --build`
- Xem log: `docker compose logs -f api ui`
- Sao lưu DB: `docker compose exec db pg_dump -U <DB_USER> <DB_NAME> > backup.sql`
- Có tên miền: sửa `:80` trong `Caddyfile` thành tên miền, mở thêm cổng 443 trong `docker-compose.yml` và firewall để có HTTPS tự động.
