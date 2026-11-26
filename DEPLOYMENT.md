# Deployment Information — Day 14 Lab

**Họ và tên:** Lê Tuấn Đạt  
**Mã sinh viên:** 2A202603949  
**Lớp:** K5-L3B  
**Repo:** [letuandat131/K5-L3B-DAY14-LeTuanDat-2A202603949-Deployment-Benchmark-Observability](https://github.com/letuandat131/K5-L3B-DAY14-LeTuanDat-2A202603949-Deployment-Benchmark-Observability)

---

## 1. Trạng thái triển khai

- **Public URL:** *(Chưa deploy lên Railway/Render — sẽ cập nhật sau khi hoàn tất triển khai cloud).*
- **Cấu hình sẵn sàng deploy:** Đã cấu hình đầy đủ `06-lab-complete/Dockerfile` (multi-stage, non-root user, HEALTHCHECK, đọc biến `PORT`), `06-lab-complete/railway.toml`, `06-lab-complete/render.yaml`, và `06-lab-complete/docker-compose.yml`. Tất cả các kiểm tra cấu hình deploy (Tiêu chí 12 trong `check_production_ready.py`) đều đạt PASS.

---

## 2. Lệnh kiểm tra (Local Runtime)

Trong thời gian chưa có URL public, ứng dụng Part 6 đã được kiểm tra đầy đủ runtime trên local với Redis native (`redis://127.0.0.1:6379/0`) qua `python check_production_ready.py --skip-docker --redis-url redis://127.0.0.1:6379/0`:

```bash
# 1. Health check (200 OK)
curl -i http://127.0.0.1:8000/health

# 2. Readiness check (200 OK khi Redis sống, 503 khi Redis ngắt kết nối)
curl -i http://127.0.0.1:8000/ready

# 3. Từ chối khi thiếu/sai API key (401 Unauthorized)
curl -i -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Docker container là gì?"}'

# 4. Gọi hợp lệ với X-API-Key (200 OK; vượt giới hạn -> 429; vượt ngân sách -> 402)
curl -i -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <AGENT_API_KEY>" \
  -d '{"question": "Docker container là gì?"}'
```

---

## 3. Biến môi trường cấu hình (`.env.example`)

| Tên biến | Mục đích |
|---|---|
| `PORT` | Port lắng nghe (platform cloud tự inject động, mặc định `8000`) |
| `ENVIRONMENT` | Môi trường chạy (`development` / `production`) |
| `AGENT_API_KEY` | Khóa bí mật xác thực qua header `X-API-Key` |
| `REDIS_URL` | Kết nối Redis cho rate limiter, cost guard và readiness check |
| `RATE_LIMIT_PER_MINUTE` | Giới hạn request/phút mỗi client (Redis sliding window ZSET) |
| `DAILY_BUDGET_USD` | Giới hạn chi phí LLM theo ngày |
| `MONTHLY_BUDGET_USD` | Giới hạn chi phí LLM theo tháng |

---

## 4. File cấu hình nền tảng

- `06-lab-complete/railway.toml`: `builder = "DOCKERFILE"`, `healthcheckPath = "/health"`.
- `06-lab-complete/render.yaml`: `type: web`, `healthCheckPath: /health`, `AGENT_API_KEY` dùng `generateValue: true` (không hardcode secret).
