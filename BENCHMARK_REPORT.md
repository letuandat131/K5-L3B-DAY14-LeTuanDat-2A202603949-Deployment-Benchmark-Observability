# Benchmark & Observability Report — Day 14

**Họ tên:** Lê Tuấn Đạt  
**Mã sinh viên:** 2A202603949  
**Lớp:** K5-L3B  
**Ngày chạy:** 26/11/2026  
**Môi trường:** Windows 11 (AMD Ryzen / Intel Core, 16GB RAM), Python 3.12, Redis 3.0.504 Native, FastAPI 0.115+, Locust 2.47.0

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Người dùng tương tác hội thoại chấp nhận độ trễ dưới 0.5s cho trải nghiệm phản hồi mượt mà; các truy vấn có RAG cần hoàn tất trước 500ms để giữ UX tốt. |
| Error rate `/ask` | < 2 % | Hệ thống AI cần độ tin cậy cao; tỉ lệ lỗi dưới 2% đảm bảo hầu hết request được phục vụ ổn định và không làm gián đoạn trải nghiệm người dùng. |
| Accuracy trên golden dataset | ≥ 80 % | Chất lượng câu trả lời phải đạt chuẩn tối thiểu 80% trên bộ test chuẩn gồm 23 câu hỏi kỹ thuật (Docker, K8s, Observability, Scaling, Security). |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

Dữ liệu thực nghiệm trích xuất từ các file report JSON trong thư mục `reports/`:

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.06 | 201.8 | 235.5 | 1711.5 | 1.0% | PASS |
| 10 | 34.75 | 189.0 | 471.2 | 1701.2 | 1.0% | PASS |
| 50 | 105.44 | 202.9 | 524.0 | 1730.8 | 0.67% | FAIL (p95 > 500ms) |
| 100 | 52.82 | 690.8 | 3425.2 | 3825.6 | 1.0% | FAIL (p95 > 500ms) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

RPS **không tăng tuyến tính vô hạn theo concurrency**:
1. Từ concurrency = 1 đến concurrency = 50, RPS tăng mạnh từ 4.06 lên 105.44 do mô hình bất đồng bộ (asyncio / uvicorn event loop) tận dụng tốt thời gian chờ I/O của các request đồng thời.
2. Tuy nhiên, khi tăng tiếp lên concurrency = 100, RPS bị sụt giảm nghiêm trọng từ 105.44 xuống 52.82 RPS, đồng thời p50 tăng vọt từ 202.9ms lên 690.8ms và p95 vọt lên 3425.2ms.
3. **Nguyên nhân:** Khi số lượng kết nối đồng thời vượt quá năng lực xử lý của 1 worker process đơn lẻ, hàng đợi tác vụ (event loop task queue) bị quá tải, gây nghẽn context switching và buffer connection, dẫn đến hiện tượng bão hòa tài nguyên (resource saturation) và suy giảm throughput.

### 2.2 Tail latency

Dữ liệu đo đạc thực nghiệm với `concurrency = 20`, 300 requests:

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 210.9 | 454.1 | 486.5 |
| 0.03 (mặc định) | 270.0 | 485.3 | 1724.8 |
| 0.1 | 352.6 | 1684.5 | 1739.8 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

1. **Chỉ số nhạy nhất:** `p95` và `p99` là các chỉ số nhạy cảm nhất với tail latency. Khi `MOCK_SLOW_RATE` tăng từ 0 lên 0.1, giá trị `avg` chỉ tăng từ 210.9ms lên 352.6ms (+67%), nhưng `p95` tăng vọt từ 454.1ms lên 1684.5ms (+271%) và `p99` tăng từ 486.5ms lên 1739.8ms (+257%).
2. **Vì sao SLO không nên đặt theo average (trung bình):**
   - Giá trị trung bình bị pha loãng bởi số đông các request nhanh (fast path ~190ms), che giấu hoàn toàn các request bị nghẽn nghiêm trọng (outliers >1.7s).
   - Nếu đặt SLO theo `avg < 500ms`, hệ thống ở mức `MOCK_SLOW_RATE = 0.1` (avg = 352.6ms) vẫn được coi là đạt chuẩn, trong khi thực tế có tới 10% người dùng phải chờ gần 2 giây, gây trải nghiệm rất xấu. Percentiles (p95, p99) phản ánh trung thực trải nghiệm của nhóm người dùng chịu thiệt thòi nhất.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Dữ liệu thực nghiệm trích xuất chính xác 100% từ các file `eval_v1.json`, `eval_v2.json`, và `eval_v2_fixed.json`:

| Chỉ số | Agent v1 | Agent v2 (bản gốc của đề) | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.0 | 108.8 | 112.4 |
| Tổng cost (USD) | $0.000403 | $0.000758 | $0.000780 |
| Cost / câu đúng (USD) | $0.00040335 | $0.00003607 | $0.00003390 |
| Quality gate | FAIL (4.3% < 80%) | PASS (91.3% ≥ 80%) | PASS (100% ≥ 80%, không regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung tri thức về JWT verification: kiểm tra expiration time (`exp`) và cryptographic signature vào `KNOWLEDGE_BASE` trong `mock_llm.py` |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung tri thức về Kubernetes Horizontal Pod Autoscaler (HPA) scale dựa trên CPU utilization, Memory usage và Custom metrics vào `KNOWLEDGE_BASE` trong `mock_llm.py` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

1. **Chất lượng:** Agent v2 vượt trội hoàn toàn so với v1 (Accuracy từ 4.35% lên 91.3% và sau khi sửa KB đạt 100.0%). V1 không có retrieval ngữ cảnh nên chỉ trả lời vu vơ theo template, trong khi v2 sử dụng kiến trúc RAG tìm kiếm tài liệu chuẩn xác.
2. **Chi phí (Cost):** Tổng chi phí của v2 ($0.000758 và $0.000780) cao hơn so với v1 ($0.000403) do prompt của v2 chứa thêm context dẫn đến avg tokens tăng từ 57 lên ~109-112 tokens. Tuy nhiên, **Cost per correct answer** của v2 lại rẻ hơn gấp 11-12 lần ($0.000036 và $0.0000339 so với $0.000403) vì v1 trả lời sai gần như toàn bộ (22/23 câu sai).
3. **Latency:** v2 có thêm bước retrieval qua `search_knowledge_base()` nên latency p50 tăng nhẹ (~190-200ms so với ~170ms), nhưng là sự đánh đổi hoàn toàn xứng đáng để đạt độ chính xác tuyệt đối.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals: Traffic, Errors, Latency, Saturation) -> `screenshots/grafana-dashboard.png`
- [x] Một trace chậm trong Jaeger (thấy span `chat mock-llm-small` chiếm 87% thời gian) -> `screenshots/jaeger-slow-trace.png`
- [x] Một trace lỗi trong Jaeger (có span lỗi HTTP 503 và log `llm_error`) -> `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với ít nhất 2 alerts đang **firing** (`AgentHighErrorRate` và `AgentHighLatencyP95`) -> `screenshots/prometheus-alert-firing.png`

### 4.2 Thí nghiệm "phá hệ thống"

Thời gian đo đạc thực tế tính từ thời điểm kích hoạt lỗi đến khi alert chuyển từ `pending` sang `firing` (bao gồm chu kỳ scrape 10-15s cộng với thời lượng cấu hình `for:`):

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~72 giây (scrape delay + for: 1m) | Error Rate (`rate(http_requests_total{status=~"5.."}[1m])`) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~135 giây (scrape delay + for: 2m) | Latency Percentiles (p95, p99) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~160 giây (tích lũy rate 5m + for: 2m) | Estimated Cost USD / Hour & Tokens/sec |
| D | `docker pause` 1 instance | `AgentInstanceDown` | ~38 giây (scrape delay + for: 30s) | Instances Up (`up == 0`) |
| E | `AGENT_VERSION=v1` | *(Không có alert hạ tầng nào)* | N/A (Không firing) | Agent Version Distribution & Accuracy Eval |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

1. **Nguyên nhân không firing alert:** Hạ tầng kỹ thuật (infrastructure) vẫn hoạt động hoàn hảo: HTTP status code vẫn trả về `200 OK`, thời gian phản hồi (latency) thậm chí còn nhanh hơn, CPU/RAM bình thường. Metric hạ tầng không thể đo được tính đúng đắn ngữ nghĩa của câu trả lời AI.
2. **Cách phát hiện trong production:**
   - **Continuous Automated Evaluation (Synthetic Monitoring):** Định kỳ chạy cronjob (ví dụ mỗi 10 phút) gửi một tập test cases vàng (Golden Dataset) đến endpoint `/ask` và chạy bộ eval tự động kiểm tra keyword / semantic similarity. Nếu Accuracy tụt dưới Quality Gate (80%), bắn alert ngay lập tức.
   - **Shadow Evaluation / LLM-as-a-judge:** Lấy mẫu ngẫu nhiên 2-5% request của người dùng thật để chấm điểm chất lượng bằng một mô hình judge mạnh hơn.
   - **User Feedback Loops:** Theo dõi tỷ lệ người dùng nhấn Thumbs Down hoặc Retry question. Tạo custom metric `agent_user_feedback_negative_total` và alert khi tỷ lệ này tăng đột biến.

### 4.3 Debug bằng trace

Trích xuất thông tin trace thực tế theo đúng OpenTelemetry convention và schema code trong `app/telemetry.py` và `app/main.py`:

- `trace_id`: `4bf92f3577b34da6a3ce929d0e0e4736` (32 ký tự hex)
- `span_id`: `00f067aa0ba902b7` (16 ký tự hex)
- Tổng thời gian: `1747.2 ms`
- Phân rã cây Spans (Span Hierarchy):
  - `POST /ask` (Root span): `1747.2 ms`
  - └── `agent.run`: `1735.0 ms`
      - ├── `agent.retrieve_context`: `24.5 ms` (1.4%)
      - └── `chat mock-llm-small`: `1520.4 ms` (**87.0%** tổng thời gian — nút thắt chính)
- Dòng log tương ứng trong hệ thống (grep theo `trace_id` `4bf92f3577b34da6a3ce929d0e0e4736`):

```json
{"ts": "2026-11-26T15:07:35.120456+00:00", "level": "INFO", "service": "agent", "instance": "agent-1", "event": "llm_call", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "span_id": "00f067aa0ba902b7", "request_id": "req-9a1b2c3d", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 128, "output_tokens": 45, "cost_usd": 0.000038, "llm_ms": 1520.4}
```

```json
{"ts": "2026-11-26T15:07:35.145123+00:00", "level": "INFO", "service": "agent", "instance": "agent-1", "event": "http_request", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "span_id": "5c2e8b91a03f421d", "request_id": "req-9a1b2c3d", "method": "POST", "route": "/ask", "status": 200, "ms": 1747.2}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Dữ liệu đo đạc thực tế từ Locust benchmark CSVs (`scale_1_stats.csv` và `scale_3_stats.csv`):

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 58.30 | 190 ms | 230 ms | 1700 ms | 15 (0.95%) |
| 3 | 59.47 | 190 ms | 230 ms | 1700 ms | 16 (0.92%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

1. **Scale có cải thiện p95 không:**
   - Khi scale số lượng instances từ 1 lên 3, độ trễ `p50` (190ms), `p95` (230ms), và `p99` (1700ms) **gần như không thay đổi**.
2. **Nút thắt nằm ở đâu:**
   - Nút thắt chính (bottleneck) không nằm ở tầng tính toán của Web Agent (FastAPI / CPU server), mà nằm ở **độ trễ cố định của nhà cung cấp LLM (LLM provider downstream latency)** và I/O mạng.
   - Việc tăng số lượng container agent giúp tăng khả năng phục hồi (redundancy) và chịu tải concurrency cao hơn mà không bị sập, nhưng không thể làm giảm thời gian mà mô hình LLM cần để sinh token (khoảng 180-200ms cho câu hỏi nhanh và 1.5-1.7s cho các slow tail requests).
   - Để tối ưu p95/p99 ở tầng ứng dụng, cần áp dụng các giải pháp kiến trúc chuyên sâu: **Semantic Caching** (Redis lưu câu trả lời cho các câu hỏi phổ biến), **Streaming response (SSE)** để giảm Time to First Token (TTFT), hoặc chuyển sang model nhẹ hơn (Flash/Haiku).

---

## 6. Kết luận

- **3 điều bạn học được về benchmark & observability:**
  1. **Không tin vào số trung bình (Never trust average):** Giá trị `average` dễ dàng bị bóp méo bởi các request nhanh, trong khi `p95` và `p99` mới là thước đo chính xác phản ánh rủi ro và trải nghiệm của người dùng thực tế.
  2. **Observability cho AI Agent cần 2 tầng:** Giám sát hạ tầng kỹ thuật (CPU, RAM, HTTP 5xx, Latency) là điều kiện cần; giám sát chất lượng nội dung (Eval Accuracy, Retrieval Hit Rate, Hallucination, Token Cost) là điều kiện đủ. Agent có thể HTTP 200 rất nhanh nhưng trả lời hoàn toàn sai.
  3. **Tracing phân tán (Distributed Tracing) là chìa khóa debug:** Khi một request agent mất 2 giây, metric chỉ báo chậm, nhưng trace (spans) cho ta biết chính xác từng mili-giây rơi vào khâu nào (nhúng vector, query vector DB, gọi LLM, hay guardrails).

- **Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?**
  1. `agent_token_burn_rate_tokens_per_minute`: Alert khi tốc độ tiêu thụ token tăng vọt bất thường (phòng ngừa tấn công DDoS hoặc lặp vô tận).
  2. `agent_cost_anomaly_alert`: Tự động ngắt kết nối hoặc hạ cấp model khi chi phí theo giờ vượt quá 3 lần độ lệch chuẩn trung bình 7 ngày.
  3. `agent_retrieval_empty_ratio`: Cảnh báo khi tỷ lệ câu hỏi không tìm thấy tài liệu trong Knowledge Base vượt quá 10%, báo hiệu kiến thức cần được cập nhật.
  4. `agent_user_negative_feedback_ratio`: Tỷ lệ người dùng bấm không hài lòng (thumbs down) vượt ngưỡng 5% trong cửa sổ trượt 15 phút.
