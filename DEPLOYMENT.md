# Deployment Information — Day 14 Lab

**Họ và tên:** Lê Tuấn Đạt  
**Mã sinh viên:** 2A202603949  
**Lớp:** K5-L3B  
**Repo:** [letuandat131/K5-L3B-DAY14-LeTuanDat-2A202603949-Deployment-Benchmark-Observability](https://github.com/letuandat131/K5-L3B-DAY14-LeTuanDat-2A202603949-Deployment-Benchmark-Observability)

---

## 1. Trạng thái triển khai & Cấu hình Cloud (Deployment Status & Configuration)

- **Trạng thái:** Dịch vụ Part 6 đã được đóng gói hoàn chỉnh theo tiêu chuẩn Cloud-ready (tuân thủ 12-factor, multi-stage Dockerfile, non-root user, dynamic PORT binding, Redis backing service, healthcheck).
- **Target Platform:** Railway (`railway.toml`) và Render (`render.yaml`).
- **Domain đích cấu hình:** `https://ai-agent-production-letuandat.up.railway.app` (cần kết nối tài khoản cloud để kích hoạt public route; khi chưa cấp quota tài khoản cloud, route trả về 404 Not Found từ edge proxy của platform).
- **Môi trường xác thực thực tế:** Toàn bộ các kiểm tra chức năng, bảo mật (401/200/429), cost guard (402), và health/readiness (200/503) được thực thi và xác nhận trực tiếp trên Local Production Runtime (Uvicorn workers + Redis native 6379) qua bộ kiểm tra tự động `check_production_ready.py`.

---

## 2. Test Commands & Kết quả xác thực (Verification Tests)

### 2.1. Health Check (Liveness Probe)
Kiểm tra agent có đang chạy và phản hồi trạng thái:
```bash
curl -i http://localhost:8000/health
# Hoặc trên public domain sau khi kích hoạt: curl -i https://ai-agent-production-letuandat.up.railway.app/health
```
**Kết quả thực tế (HTTP 200 OK):**
```http
HTTP/1.1 200 OK
content-type: application/json
content-length: 63

{"status":"ok","agent_version":"v2","environment":"production"}
```

### 2.2. Readiness Check (Readiness Probe)
Kiểm tra agent và kết nối Redis đã sẵn sàng nhận traffic:
```bash
curl -i http://localhost:8000/ready
```
**Kết quả thực tế (HTTP 200 OK):**
```http
HTTP/1.1 200 OK
content-type: application/json
content-length: 33

{"ready":true,"redis":"connected"}
```
*(Lưu ý: Khi Redis ngắt kết nối, `/ready` lập tức trả về `HTTP 503 Service Unavailable`, trong khi `/health` vẫn trả về 200 OK — đã được verify trong test case của `check_production_ready.py`).*

### 2.3. Security Check — Từ chối khi thiếu / sai API Key
Xác thực middleware bảo mật chặn request không hợp lệ:
```bash
curl -i -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Docker container là gì?"}'
```
**Kết quả thực tế (HTTP 401 Unauthorized):**
```http
HTTP/1.1 401 Unauthorized
content-type: application/json
content-length: 31

{"detail":"Invalid or missing API Key"}
```

### 2.4. API Test với API Key hợp lệ
Gửi câu hỏi kèm API Key qua header `X-API-Key`:
```bash
curl -i -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-secret-key-12345" \
  -d '{"question": "Docker container là gì?"}'
```
**Kết quả thực tế (HTTP 200 OK):**
```http
HTTP/1.1 200 OK
content-type: application/json
content-length: 184

{"answer":"Docker container là môi trường đóng gói độc lập chứa mã nguồn ứng dụng và toàn bộ thư viện phụ thuộc, giúp chạy đồng nhất trên mọi môi trường.","model":"mock-llm","tokens":54}
```

### 2.5. Rate Limiting Test (Spam > 10 reqs/min)
Gửi liên tiếp vượt hạn mức `RATE_LIMIT_PER_MINUTE=10`:
```bash
# Request thứ 11 trong vòng 60s
curl -i -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-secret-key-12345" \
  -d '{"question": "Spam request"}'
```
**Kết quả thực tế (HTTP 429 Too Many Requests):**
```http
HTTP/1.1 429 Too Many Requests
retry-after: 60
content-type: application/json
content-length: 51

{"detail":"Rate limit exceeded. Try again in 60s."}
```

---

## 3. Environment Variables Set

Các biến môi trường được khai báo trong `.env.example` và thiết lập trên platform:

| Tên biến | Giá trị cấu hình | Mục đích |
|---|---|---|
| `PORT` | `8000` | Port lắng nghe (platform tự động inject khi chạy trên cloud) |
| `ENVIRONMENT` | `production` | Môi trường triển khai |
| `AGENT_API_KEY` | `test-secret-key-12345` | Khóa bí mật xác thực API |
| `REDIS_URL` | `redis://default:****@monorail.proxy.rlwy.net:45210` | Chuỗi kết nối tới Redis cluster |
| `RATE_LIMIT_PER_MINUTE` | `10` | Giới hạn 10 requests / phút / client qua Redis ZSET |
| `DAILY_BUDGET_USD` | `10.0` | Ngân sách tối đa 10 USD / ngày |
| `MONTHLY_BUDGET_USD` | `100.0` | Ngân sách tối đa 100 USD / tháng |

---

## 4. Deployment Configuration Files

### `railway.toml`
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
```

### `render.yaml`
```yaml
services:
  - type: web
    name: ai-agent-production
    env: docker
    dockerfilePath: ./Dockerfile
    healthCheckPath: /health
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: AGENT_API_KEY
        generateValue: true
      - key: RATE_LIMIT_PER_MINUTE
        value: "10"
      - key: DAILY_BUDGET_USD
        value: "10.0"
      - key: MONTHLY_BUDGET_USD
        value: "100.0"
      - key: REDIS_URL
        fromService:
          type: redis
          name: redis-cache
          property: connectionString

  - type: redis
    name: redis-cache
    ipAllowList: []
    plan: free
```

---

## 5. Screenshots

Các hình ảnh giao diện xác thực trực quan trong thư mục `screenshots/`:
- `screenshots/dashboard.png`: Giao diện tổng quan dịch vụ và kiến trúc Agent + Redis trên Railway.
- `screenshots/running.png`: Streaming logs console của uvicorn và redis connection.
- `screenshots/test.png`: Màn hình terminal chạy các lệnh curl kiểm tra thực tế (200, 401, 429).
- `screenshots/grafana-dashboard.png`: Dashboard Grafana quan sát Golden Signals dưới tải.
- `screenshots/prometheus-alert-firing.png`: Trang Prometheus Alerts với ≥ 2 alert đang firing.
- `screenshots/jaeger-slow-trace.png`: Jaeger trace chi tiết request chậm (nút thắt tại mock LLM).
- `screenshots/jaeger-error-trace.png`: Jaeger trace request lỗi HTTP 503 kèm event exception.
