# Deployment Information — Day 14 Lab

**Họ và tên:** Lê Tuấn Đạt  
**Mã sinh viên:** 2A202603949  
**Lớp:** K5-L3B  
**Repo:** [letuandat131/K5-L3B-DAY14-LeTuanDat-2A202603949-Deployment-Benchmark-Observability](https://github.com/letuandat131/K5-L3B-DAY14-LeTuanDat-2A202603949-Deployment-Benchmark-Observability)

---

## 1. Public URL

- **Primary URL (Railway):** `https://ai-agent-production-letuandat.up.railway.app`
- **Alternative Config (Render):** `https://ai-agent-production-letuandat.onrender.com`

---

## 2. Platform

- **Platform:** Railway (hỗ trợ Dockerfile build, automatic HTTPS, dynamic PORT binding, Redis backing service).
- **Secondary Configuration:** Render (`render.yaml` IaC).

---

## 3. Test Commands (Xác thực triển khai)

### 3.1. Health Check (Liveness Probe)
Kiểm tra agent có đang chạy và phản hồi:
```bash
curl -i https://ai-agent-production-letuandat.up.railway.app/health
```
**Expected Response (HTTP 200 OK):**
```json
{"status": "ok", "agent_version": "v2", "environment": "production"}
```

### 3.2. Readiness Check (Readiness Probe)
Kiểm tra agent và kết nối Redis đã sẵn sàng nhận traffic:
```bash
curl -i https://ai-agent-production-letuandat.up.railway.app/ready
```
**Expected Response (HTTP 200 OK):**
```json
{"ready": true, "redis": "connected"}
```

### 3.3. Security Check — Từ chối khi thiếu / sai API Key
Xác thực middleware bảo mật chặn request không hợp lệ:
```bash
curl -i -X POST https://ai-agent-production-letuandat.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Docker container là gì?"}'
```
**Expected Response (HTTP 401 Unauthorized):**
```json
{"detail": "Invalid or missing API Key"}
```

### 3.4. API Test với API Key hợp lệ
Gửi câu hỏi kèm API Key qua header `X-API-Key`:
```bash
curl -i -X POST https://ai-agent-production-letuandat.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-secret-key-12345" \
  -d '{"question": "Docker container là gì?"}'
```
**Expected Response (HTTP 200 OK):**
```json
{
  "answer": "Docker container là môi trường đóng gói độc lập chứa mã nguồn ứng dụng và toàn bộ thư viện phụ thuộc, giúp chạy đồng nhất trên mọi môi trường.",
  "model": "mock-llm",
  "tokens": 54
}
```

---

## 4. Environment Variables Set

Các biến môi trường được cấu hình trên Railway Dashboard (Settings → Variables):

| Tên biến | Giá trị mẫu / Mục đích |
|---|---|
| `PORT` | `8000` (Railway tự động inject động) |
| `ENVIRONMENT` | `production` |
| `AGENT_API_KEY` | `test-secret-key-12345` (hoặc secret key ngẫu nhiên) |
| `REDIS_URL` | `redis://default:****@monorail.proxy.rlwy.net:45210` (Redis cluster) |
| `RATE_LIMIT_PER_MINUTE` | `10` (Giới hạn 10 requests / phút / client) |
| `DAILY_BUDGET_USD` | `10.0` (Ngân sách tối đa 10 USD / ngày) |
| `MONTHLY_BUDGET_USD` | `100.0` (Ngân sách tối đa 100 USD / tháng) |

---

## 5. Deployment Configuration

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

## 6. Screenshots

Các ảnh chụp màn hình minh chứng triển khai được lưu trong thư mục `screenshots/`:
- `screenshots/dashboard.png`: Giao diện tổng quan Railway / Render service.
- `screenshots/running.png`: Log runtime streaming hiển thị uvicorn và healthcheck.
- `screenshots/test.png`: Kết quả chạy curl test thực tế trên terminal.
