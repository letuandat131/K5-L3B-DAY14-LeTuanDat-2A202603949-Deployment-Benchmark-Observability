# Benchmark & Observability Report — Day 14

**Họ tên:** Lê Tuấn Đạt  
**Mã sinh viên:** 2A202603949  
**Lớp:** K5-L3B  
**Ngày chạy:** 26/11/2026  
**Môi trường:** Windows 11, Python 3.12, Redis 3.0.504 Native, FastAPI, Locust 2.47.0

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

Dữ liệu thực nghiệm trích xuất trực tiếp từ các file report JSON trong thư mục `reports/`:

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

Dữ liệu đo đạc thực nghiệm với `concurrency = 20`, 300 requests (từ `reports/load_v2_slow_*.json`):

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 210.9 | 454.1 | 486.5 |
| 0.03 (mặc định) | 270.0 | 485.3 | 1724.8 |
| 0.1 | 352.6 | 1684.5 | 1739.8 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

1. **Chỉ số nhạy nhất:** `p95` và `p99` là các chỉ số nhạy cảm nhất với tail latency. Khi `MOCK_SLOW_RATE` tăng từ 0 lên 0.1, giá trị `avg` chỉ tăng từ 210.9ms lên 352.6ms (+67%), nhưng `p95` tăng vọt từ 454.1ms lên 1684.5ms (+271%) và `p99` tăng từ 486.5ms lên 1739.8ms (+257%).
2. **Vì sao SLO không nên đặt theo average (trung bình):**
   - Giá trị trung bình bị pha loãng bởi số đông các request nhanh (~190ms), che giấu các request bị nghẽn nghiêm trọng (>1.7s).
   - Nếu đặt SLO theo `avg < 500ms`, hệ thống ở mức `MOCK_SLOW_RATE = 0.1` (`avg = 352.6ms`) vẫn được coi là đạt chuẩn, trong khi thực tế có tới 10% người dùng phải chờ gần 2 giây. Percentiles (`p95`, `p99`) phản ánh trung thực trải nghiệm của nhóm người dùng chịu độ trễ cao nhất.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Dữ liệu thực nghiệm trích xuất chính xác từ các file `reports/eval_v1.json`, `reports/eval_v2.json`, và `reports/eval_v2_fixed.json`:

| Chỉ số | Agent v1 | Agent v2 (bản gốc của đề) | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.0 | 108.8 | 112.4 |
| Tổng cost (USD) | $0.000403 | $0.000758 | $0.000780 |
| Cost / câu đúng (USD) | $0.00040335 | $0.00003607 | $0.00003390 |
| Quality gate | FAIL (4.35% < 80%) | PASS (91.3% ≥ 80%) | PASS (100% ≥ 80%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung tri thức về JWT verification (`token`, thời hạn `hết hạn`, xác thực qua `chữ ký` số) vào `KNOWLEDGE_BASE` trong `mock_llm.py` |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung tri thức về Kubernetes HPA scale dựa trên `CPU`, `memory`, `custom metrics` vào `KNOWLEDGE_BASE` trong `mock_llm.py` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

1. **Chất lượng:** Agent v2 vượt trội hoàn toàn so với v1 (Accuracy từ 4.35% lên 91.3% ở bản gốc và 100.0% sau khi bổ sung KB). V1 không có retrieval ngữ cảnh nên trả lời sai 22/23 câu.
2. **Chi phí (Cost):** Tổng chi phí của v2 ($0.000758 → $0.000780) cao hơn ~1.9 lần so với v1 ($0.000403) do prompt kèm context làm avg tokens tăng từ 57 lên 108.8–112.4. Tuy nhiên, **Cost / câu đúng** của v2 rẻ hơn ~11–12 lần ($0.00003607 và $0.00003390 so với $0.00040335).
3. **Latency:** v2 có thêm bước retrieval `search_knowledge_base()` nên p50 tăng nhẹ từ 170.5ms (v1) lên 188.9ms–200.6ms (v2), là sự đánh đổi hợp lý cho chất lượng trả lời.

---

## 4. Observability stack (production)

> **Trạng thái môi trường:** Sau khi bật lại `hypervisorlaunchtype=auto` và restart máy lúc 23:43, Docker 29.5.3 đã khởi động và kéo/chạy được các container `prometheus`, `grafana`, `jaeger`, `nginx`, `locust`, tuy nhiên container `production-agent` gặp lỗi `ModuleNotFoundError: No module named 'uvicorn'` (do `production/Dockerfile` có sẵn dùng `useradd -d /app` khác với `/home/agent/.local`) sát giờ nộp bài 23:59 nên chưa kịp chạy đủ thí nghiệm chaos và chụp ảnh thật. Toàn bộ các mục chưa có dữ liệu chạy thật đều để trống trung thực theo đúng `RULES.md`.

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (chưa chạy được Docker stack)
- [ ] Một trace chậm trong Jaeger (chưa chạy được Docker stack)
- [ ] Một trace lỗi trong Jaeger (chưa chạy được Docker stack)
- [ ] Trang Alerts của Prometheus với ≥ 2 alert đang firing (chưa chạy được Docker stack)

### 4.2 Thí nghiệm "phá hệ thống"

*(Chưa chạy thực nghiệm do chưa khởi động được Docker Compose.)*

**Phân tích lý thuyết cho câu hỏi thí nghiệm E (`AGENT_VERSION=v1` không làm alert hạ tầng nào firing):**

- Hạ tầng kỹ thuật vẫn trả HTTP `200 OK` và latency thậm chí thấp hơn (vì bỏ qua bước retrieval), nên các alert hạ tầng (`AgentHighErrorRate`, `AgentHighLatencyP95`, `AgentInstanceDown`) sẽ không kích hoạt.
- Để phát hiện suy giảm chất lượng trên production cần: (1) chạy automated eval định kỳ với golden dataset (synthetic quality monitoring) và bắn alert khi accuracy dưới ngưỡng, (2) theo dõi metric nghiệp vụ như `retrieval_hits_total{result="miss"}` (tỷ lệ retrieval miss tăng đột biến), và (3) thu thập phản hồi người dùng (negative feedback / retry rate).

### 4.3 Debug bằng trace

*(Chưa thu thập được trace thật và log tương ứng từ Jaeger do chưa chạy được stack Docker.)*

---

## 5. Benchmark scaling (Locust headless)

| Số instance | Môi trường chạy | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|---|
| 1 | Local (`develop/app.py`, 100 users, 30s — `benchmark-results/scale_1_stats.csv`) | 58.30 | 190 ms | 230 ms | 1700 ms | 15 / 1584 (0.95%) |
| 3 | *(Chưa chạy được `docker compose up --scale agent=3` do lỗi Hyper-V/Docker)* | — | — | — | — | — |

**Phân tích lý thuyết về scaling:**

Khi scale ngang từ 1 lên 3 instance sau Nginx, tổng thông lượng (RPS) ở concurrency cao có thể tăng vì giảm nghẽn event loop/CPU trên mỗi worker, nhưng độ trễ từng request đơn lẻ (đặc biệt tail latency p95/p99 khi `MOCK_SLOW_RATE` kích hoạt) vẫn bị chặn dưới bởi độ trễ gọi downstream LLM (`chat mock-llm-small`).

---

## 6. Kết luận

- **3 điều học được về benchmark & observability:**
  1. **Không dùng average làm SLO:** Thực nghiệm `load_v2_slow_*.json` cho thấy khi tăng `MOCK_SLOW_RATE` từ 0 lên 0.1, `avg` chỉ tăng 67% nhưng `p95` tăng 271% (454ms → 1684ms).
  2. **Chất lượng AI phải đo bằng Eval tự động:** Agent v1 trả lời nhanh hơn v2 (~170ms vs ~190ms) nhưng accuracy chỉ đạt 4.35%. Chạy `eval/run_eval.py` giúp bắt đúng 2 lỗ hổng tri thức (`security-02`, `scaling-03`) và xác minh không có regression sau khi sửa.
  3. **Concurrency cao quá mức làm giảm RPS:** Với 1 process uvicorn, RPS đạt đỉnh 105.44 ở `c=50` nhưng tụt xuống 52.82 ở `c=100` trong khi p95 vọt lên 3425ms.
- **Nếu đưa agent lên production thật, cần thêm metric / alert nào:**
  - Alert theo tỷ lệ retrieval miss (`retrieval_hits_total{result="miss"}`) để phát hiện sớm lỗi chất lượng RAG.
  - Alert theo tốc độ tiêu thụ token bất thường và chi phí theo giờ (`LLMCostBurnRateHigh`) kết hợp cơ chế cost guard trả HTTP 402.
  - Synthetic eval định kỳ chạy trên tập câu hỏi vàng để phát hiện suy giảm chất lượng mà metric hạ tầng không thấy được.
