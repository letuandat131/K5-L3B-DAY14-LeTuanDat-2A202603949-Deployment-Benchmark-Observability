# Day 14 Lab - Mission Answers

**Họ và tên:** Lê Tuấn Đạt  
**Mã sinh viên:** 2A202603949  
**Lớp:** K5-L3B  
**Repo cá nhân:** [letuandat131/K5-L3B-DAY14-LeTuanDat-2A202603949-Deployment-Benchmark-Observability](https://github.com/letuandat131/K5-L3B-DAY14-LeTuanDat-2A202603949-Deployment-Benchmark-Observability)  
**Ngày hoàn thành:** 26/11/2026  

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in "Localhost-style" Agent (`01-localhost-vs-production/develop/app.py`)
1. **Hardcoded Secrets:** API key được gán cứng trực tiếp trong code, dễ bị lộ khi đẩy lên GitHub.
2. **Hardcoded Port & Host:** Port `8000` gắn cứng trong mã nguồn, không đọc từ biến môi trường `PORT` do cloud platform cấp.
3. **Thiếu Health & Readiness Check:** Không có endpoint `/health` và `/ready` cho container orchestrator/load balancer giám sát.
4. **Debug Mode bật cứng:** Làm rò rỉ stack trace chi tiết khi gặp lỗi và tốn tài nguyên.
5. **Không có Graceful Shutdown:** Không xử lý tín hiệu `SIGTERM` / `SIGINT`, khiến các request đang xử lý bị cắt ngang khi tắt server.
6. **Unstructured Logging:** Dùng `print()` thay vì structured JSON logging.

### Exercise 1.3: Comparison table (Develop vs Production)

| Tiêu chí / Feature | Develop (❌ Anti-pattern) | Production (✅ 12-Factor Compliant) | Tại sao quan trọng? (Why Important?) |
|---|---|---|---|
| **Config & Secrets** | Hardcode trong mã nguồn | Đọc từ biến môi trường (`os.getenv`), dùng `.env.example` làm mẫu | Ngăn lộ secret trên Git, tách biệt config khỏi code (12-Factor Factor III). |
| **Port Binding** | Cố định `8000` | Đọc từ biến `PORT` | Cloud platforms (Railway, Render, Cloud Run) cấp port động qua `PORT`. |
| **Health Checks** | Không có | `/health` (Liveness) và `/ready` (Readiness) | Giúp platform tự restart khi treo và ngắt traffic khi dependency (Redis) lỗi. |
| **Shutdown** | Tắt đột ngột | Graceful shutdown: bắt `SIGTERM`, ngừng nhận request mới, chờ in-flight xong | Tránh mất dữ liệu và lỗi 502/504 khi rolling deploy. |
| **Logging** | `print()` | Structured JSON logging | Dễ thu thập, parse và tìm kiếm trên hệ thống log tập trung. |
| **State** | Lưu trong RAM local | Stateless — lưu ra Redis | Cho phép scale ngang nhiều instance sau load balancer. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile Questions
1. **Base image:** Dùng `python:3.11-slim` ở stage runtime (loại bỏ gcc, headers và các gói thừa) để giảm dung lượng và bề mặt tấn công.
2. **Working directory:** `WORKDIR /app` tách biệt mã nguồn ứng dụng khỏi thư mục gốc `/`.
3. **User Non-root:** Tạo user `appuser` và dùng `USER appuser` theo nguyên tắc đặc quyền tối thiểu (Least Privilege).
4. **Healthcheck:** Dùng `HEALTHCHECK` gọi endpoint `/health` định kỳ để Docker phát hiện container bị treo.

### Exercise 2.2: Layer Order Caching
- Luôn `COPY requirements.txt .` và `RUN pip install --no-cache-dir -r requirements.txt` **trước** `COPY . .`.
- **Lý do:** `requirements.txt` ít thay đổi hơn mã nguồn. Khi sửa code Python, Docker tái sử dụng cache layer của bước cài thư viện thay vì cài lại từ đầu.

### Exercise 2.3: Image Size Comparison
Kết quả đo thực tế bằng `docker build` và `docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"` trên Docker 29.5.3:

```text
REPOSITORY             TAG           SIZE
agent-production       latest        240MB
agent-develop          latest        1.67GB
```

- **Develop (`02-docker/develop/Dockerfile`, single-stage `python:3.11`):** `1.67 GB` (~1670 MB)
- **Production (`02-docker/production/Dockerfile`, multi-stage `python:3.11-slim`):** `240 MB`
- **Chênh lệch:** Giảm `~1.43 GB` (**giảm 85.6%** dung lượng). Ngoài ra image Part 6 (`06-lab-complete`) được `check_production_ready.py` đo qua Docker API đạt `56 MB` (< 500 MB).

### Exercise 2.4: Multi-Service Stack (Docker Compose)
- Sơ đồ kiến trúc stack trong `02-docker/production/docker-compose.yml`:
  ```text
  Client → Nginx (Reverse Proxy / Load Balancer) → Agent Container(s) ↔ Redis (Shared State)
  ```

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway / Render Deployment
- *(Chưa có URL public hoạt động; xem chi tiết trạng thái tại `DEPLOYMENT.md`. Cấu hình `06-lab-complete/railway.toml` và `06-lab-complete/render.yaml` đã hoàn thiện và pass kiểm tra tự động.)*

### Exercise 3.2: So sánh `railway.toml` và `render.yaml`

| Tiêu chí | Railway (`railway.toml`) | Render (`render.yaml`) | Giải thích sự khác biệt |
|---|---|---|---|
| **Cơ chế cấu hình** | Tập trung cấu hình build & deploy cho service hiện tại (`[build]`, `[deploy]`) | Infrastructure as Code (IaC) khai báo nhiều service + database trong cùng 1 file YAML (`services: [...]`) | Render cho phép định nghĩa cả web service và Redis cùng mối liên kết `fromService` trong 1 blueprint duy nhất. |
| **Quản lý Secrets** | Khai báo qua Railway Dashboard / CLI | Hỗ trợ `generateValue: true` hoặc `sync: false` ngay trong `render.yaml` | `generateValue: true` tự sinh secret an toàn khi deploy mà không cần hardcode trong repo. |
| **Health Check** | `healthcheckPath = "/health"` trong `[deploy]` | `healthCheckPath: /health` ở cấu hình web service | Cả hai dùng HTTP GET `/health` để xác nhận bản deploy mới khỏe trước khi chuyển traffic. |
| **Port Binding** | Tự inject biến `PORT` động | Tự inject biến `PORT` | Container cần đọc `${PORT:-8000}` và bind `0.0.0.0`. |

### Exercise 3.3: Phân tích CI/CD Pipeline Cloud Run (`03-cloud-deployment/production-cloud-run/`)
Đọc `cloudbuild.yaml` và `service.yaml`, pipeline CI/CD trên Google Cloud đi qua 4 bước tuần tự (`waitFor`):
1. **Test (`test`):** Dùng container `python:3.11-slim` cài dependencies và chạy `pytest tests/ -v --tb=short`; fail thì dừng pipeline.
2. **Build (`build`):** Build Docker image gắn 2 tag (`$COMMIT_SHA` và `latest`), tận dụng `--cache-from` từ image `latest` trên GCR để tăng tốc.
3. **Push (`push`):** Đẩy tất cả tag image lên Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **Deploy (`deploy`):** Gọi `gcloud run deploy` triển khai image `$COMMIT_SHA` lên Cloud Run (`asia-southeast1`), giữ `--min-instances=1` để tránh cold start, giới hạn `--max-instances=10`, cấu hình 512Mi RAM / 1 CPU và nạp `OPENAI_API_KEY` từ Secret Manager.

---

## Part 4: API Security

### Exercise 4.1–4.3: Kiểm tra thực tế bằng `check_production_ready.py` (Local Runtime + Redis Native)
Các cơ chế bảo mật trong `06-lab-complete/` đã được xác minh trực tiếp qua runtime test của `check_production_ready.py`:
- **API Key Auth (`app/auth.py`):** Đọc header `X-API-Key`. Thiếu hoặc sai key → trả `HTTP 401 Unauthorized`; đúng key → trả `HTTP 200 OK`.
- **Rate Limiting (`app/rate_limiter.py`):** Dùng Redis Sorted Set (`ZSET`) theo thuật toán sliding window 60 giây. Khi vượt `RATE_LIMIT_PER_MINUTE` (test với `= 5`, sau 5 request thành công) → trả `HTTP 429 Too Many Requests` kèm header `Retry-After: 60`. Khi restart uvicorn process, state vẫn được giữ trong Redis nên vẫn trả 429 (chứng minh stateless).

### Exercise 4.4: Cost Guard Implementation (`app/cost_guard.py`)
1. Lưu tổng chi phí USD vào Redis (key `cost:total`) bằng thao tác nguyên tử `INCRBYFLOAT` để nhiều worker chia sẻ cùng một bộ đếm ngân sách.
2. Trước khi xử lý `/ask`, gọi `check_budget()`: nếu chi phí tích lũy vượt quá giới hạn (`DAILY_BUDGET_USD`), lập tức raise `HTTPException(status_code=402)` (Payment Required).
3. Sau khi gọi LLM thành công, gọi `record_cost()` để cộng dồn chi phí ước tính vào Redis. Đã kiểm chứng thực tế bằng `check_production_ready.py` (khi đặt budget ≈ 0, trả HTTP 402 ngay ở request đầu tiên).

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health vs Readiness Probes
- **`GET /health` (Liveness Probe):** Kiểm tra tiến trình ứng dụng còn sống hay không. Nếu fail, orchestrator sẽ restart container. Khi Redis mất kết nối, `/health` vẫn trả `200 OK` (vì tiến trình app không bị treo).
- **`GET /ready` (Readiness Probe):** Kiểm tra ứng dụng sẵn sàng nhận traffic (kiểm tra cờ `_is_ready` và gọi `redis_healthy()`). Khi Redis ngắt kết nối hoặc app đang shutdown, `/ready` trả `503 Service Unavailable` để load balancer ngừng gửi traffic mới tới instance đó mà không kill container.

### Exercise 5.2: Graceful Shutdown
- Khi nhận `SIGTERM`, handler lifespan đặt `_is_ready = False` (khiến `/ready` trả 503 để load balancer ngắt traffic mới), chờ các request in-flight hoàn thành rồi mới đóng kết nối và thoát êm.
- *(Lưu ý: trên Windows không gửi được `SIGTERM` chuẩn như Linux container nên kiểm tra runtime SIGTERM trong `check_production_ready.py` hiện ở trạng thái ⚠️ chờ chạy trong Docker).*

### Exercise 5.3: Stateless Architecture với Redis
- Toàn bộ trạng thái cần chia sẻ giữa các worker (rate limit window, cost accumulator) được lưu trên Redis ngoài tiến trình Python. Trong bài kiểm tra `check_production_ready.py` với `uvicorn --workers 2` và restart server giữa chừng, trạng thái rate limit vẫn được bảo toàn xuyên suốt các worker và sau khi restart.

---

## Part 6: Production Ready Output

Kết quả chạy thực tế `python check_production_ready.py` đầy đủ (với Docker 29.5.3 trên Windows) trong `06-lab-complete/`:

```text
================================================================
  Production Readiness Check — Day 14 Lab
================================================================

✅ 1. Dockerfile (multi-stage, < 500 MB)
     ✅ Dockerfile tồn tại
     ✅ requirements.txt tồn tại
     ✅ Multi-stage build (≥ 2 lệnh FROM)
     ✅ Base image gọn (slim / alpine / distroless) — stage cuối dùng python:3.11-slim
     ✅ Chạy bằng user non-root
     ✅ Có HEALTHCHECK
     ✅ Docker: build image thành công — 404s
     ✅ Docker: image < 500 MB — 56 MB
     ✅ Docker: container chạy được, GET /health → 200

✅ 2. docker-compose.yml (agent + redis)
✅ 3. .dockerignore
✅ 4. Health check endpoint (GET /health)
✅ 5. Readiness endpoint (GET /ready)
✅ 6. API Key authentication
✅ 7. Rate limiting
✅ 8. Cost guard
✅ 9. Config từ environment variables
✅ 10. Structured logging
⚠️  11. Graceful shutdown
     ✅ Code xử lý SIGTERM / lifespan shutdown
     ⚠️  Khi chạy: SIGTERM lúc đang có request → request vẫn 200, process tự thoát — chưa kiểm tra được — Windows không gửi được SIGTERM (phần Docker sẽ kiểm tra)
     ✅ Docker: `docker stop` tắt êm (exit code 0, < 10s) — exit code 0, 2.5s
✅ 12. Public URL ready (Railway / Render config)

================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ⚠️  Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 11/12 tiêu chí đạt · 42/42 checks passed
  ⚠️  Chưa kiểm tra được: Graceful shutdown
  ❌ CHƯA ĐẠT — còn tiêu chí chưa kiểm tra được (⚠️). Chạy đầy đủ trên máy có Docker.
================================================================
```

*(Ghi chú: 42/42 checks thực thi đều PASS; 1 dấu ⚠️ duy nhất ở mục 11 là do script chạy trên Windows nên bước test SIGTERM ngoài container bỏ qua với ghi chú "Windows không gửi được SIGTERM (phần Docker sẽ kiểm tra)", còn bước kiểm tra thật trong Docker `docker stop` đã PASS với `exit code 0, 2.5s`.)*

---

## AI Usage Log

| Thời gian | Mục đích / Prompt hỏi AI | Kết quả AI phản hồi | Tự kiểm tra & chỉnh sửa |
|---|---|---|---|
| 26/11 21:00 | Hỏi cách hoàn thiện các TODO trong `06-lab-complete/` (`config.py`, `redis_client.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`, `main.py`, `Dockerfile`, `docker-compose.yml`, `railway.toml`, `render.yaml`) | AI viết mã nguồn cho các module tuân thủ hợp đồng trong `06-lab-complete/README.md` | Cài Redis native trên Windows, chạy `python check_production_ready.py --skip-docker --redis-url redis://127.0.0.1:6379/0`, xác nhận 38/38 checks passed (10/12 tiêu chí đạt, 2 tiêu chí cần Docker đang báo ⚠️) |
| 26/11 21:55 | Hỏi chạy benchmark `load_test.py` và `eval/run_eval.py` trên bản develop | AI chạy load test (`c=1,10,50,100` và `MOCK_SLOW_RATE=0,0.03,0.1`) và eval v1, v2 | Kiểm tra từng file JSON trong `reports/`; phát hiện lần đầu `eval_v2.json` bị ghi đè bởi bản đã sửa KB (23/23) nên đã revert `mock_llm.py` về bản gốc để chạy lại `eval_v2.json` thật (21/23, sai `security-02` và `scaling-03`), sau đó mới sửa KB để tạo `eval_v2_fixed.json` (23/23) |
| 26/11 23:05 | Rà soát lại tính trung thực của toàn bộ bài nộp trước khi nộp theo `RULES.md` | Phát hiện lỗi `HCS_E_HYPERV_NOT_INSTALLED` là do `hypervisorlaunchtype` đang tắt trong Windows BCD | Gỡ bỏ toàn bộ 7 ảnh vẽ bằng script PIL, gỡ phần trace mẫu W3C, URL 404 và số đo chưa chạy thật; sau đó bật `bcdedit /set hypervisorlaunchtype auto`, restart máy, chạy thật `python check_production_ready.py` (có Docker 29.5.3, đạt 42/42 checks passed, image 56 MB, `docker stop` exit code 0 trong 2.5s) và đo `docker images` thật (`agent-develop` 1.67GB vs multi-stage 261MB) |
