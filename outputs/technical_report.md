# Báo Cáo Kỹ Thuật FinOps: Tối Ưu Hóa Chi Phí Hạ Tầng GPU
**Dự án:** NimbusAI — LLM Infrastructure Cost Optimization  
**Tác giả:** Kỹ sư FinOps (Trần Gia Khánh)  
**Thời gian đánh giá:** Tháng 6/2026  
**Mục tiêu:** Cắt giảm chi phí GPU 40–95%, chuẩn hoá đơn vị đo lường theo `$/1M-token`

---

## 1. Tổng Quan Baseline vs. Optimized

NimbusAI đang đối mặt với bài toán chi phí hạ tầng GPU tăng phi mã do mở rộng dịch vụ LLM. Qua quá trình kiểm toán toàn diện telemetry và mô hình sử dụng token, chiến lược FinOps đã mang lại kết quả tối ưu vượt bậc:

| Chỉ số đo lường | Baseline (Trước tối ưu) | Optimized (Sau tối ưu) | Mức cắt giảm | Nhận xét |
|---|:---:|:---:|:---:|---|
| **Tổng chi phí hàng tháng** | **$27,133** | **$14,626** | **-46.1% (-$12,507)** | Giảm gần một nửa chi phí vận hành |
| **Chi phí Inference theo token** | **$6.488 / 1M-token** | **$1.126 / 1M-token** | **-82.6% (-$5.362)** | Hiệu quả phục vụ token tăng gấp ~5.8 lần |
| **Chi phí Inference hàng ngày** | $48.87 / ngày | $8.48 / ngày | -82.6% | Lưu lượng 2,400 queries (7.53M tokens) |
| **Chi phí hạ tầng máy chủ** | $25,667 / tháng | $15,627 / tháng | -39.1% | Tối ưu hóa 8 workloads đào tạo và suy luận |

> **Điểm cốt lõi:** Việc chuyển đổi hệ quy chiếu từ `$/GPU-giờ` sang `$/1M-token` đã phản ánh chính xác hiệu suất kinh tế của hạ tầng: cùng một mức chi phí, hệ thống sau tối ưu phục vụ được lượng người dùng lớn hơn gần 6 lần.

---

## 2. Phân Tích Đóng Góp Của Từng Đòn Bẩy Tiết Kiệm (Savings Levers)

Khoản tiết kiệm **$12,507/tháng** được cấu thành từ 4 đòn bẩy chiến lược với mức đóng góp cụ thể:

```
Tổng tiết kiệm: $12,507/tháng
├── [80.3%] Chiến lược mua sắm (Spot / Reserved): $10,040
├── [ 9.7%] Đòn bẩy Inference (Cascade / Cache / Batch): $1,212
├── [ 5.2%] Right-sizing GPU "nói dối" (Util-lies): $655
└── [ 4.8%] Tắt GPU chạy không tải (Kill idle GPUs): $600
```

| Thứ hạng | Đòn bẩy tối ưu | Tiết kiệm (USD/tháng) | Tỷ trọng | Đánh giá ROI & Cơ chế tác động |
|:---:|---|:---:|:---:|---|
| **1** | **Purchasing Strategy (Spot / Reserved)** | **$10,040** | **80.3%** | **ROI cao nhất:** Chuyển đổi 5 workloads ngắt quãng sang Spot (chiết khấu ~60–70%) kết hợp checkpointing; cam kết Reserved 3 năm (chiết khấu 45%) cho 3 cụm inference 24/7 có duty cycle $\ge 55\%$. |
| **2** | **Inference Levers (Cascade / Cache / Batch)** | **$1,212** | **9.7%** | **Tác động trực tiếp đến unit economics:** Giảm 82.6% chi phí token nhờ: (1) Cascade routing chuyển request đơn giản sang model nhỏ rẻ hơn 15x; (2) Prompt caching giảm 90% chi phí input token lặp lại; (3) Batch API giảm 50% chi phí cho các tác vụ nền. |
| **3** | **Right-sizing Util-lies** | **$655** | **5.2%** | Hạ cấp cấu hình GPU bị lãng phí năng lực tính toán (`gpu-h100-4` hạ xuống A100, `gpu-a10g-1` hạ xuống L4) do workload bị memory-bound. |
| **4** | **Kill Idle GPUs** | **$600** | **4.8%** | Tắt `gpu-h100-5` lãng phí 8 giờ idle mỗi ngày ($20/ngày), thiết lập chính sách tự động thu hồi tài nguyên sau 15 phút không có tải. |

---

## 3. Bản Chất Kỹ Thuật Của Hiện Tượng "GPU-Util Lie"

### 3.1 Thực trạng phát hiện tại NimbusAI
Trong 11 GPU được giám sát telemetry suốt 24 giờ, hệ thống phát hiện 2 GPU rơi vào nhóm **GPU-Util Lie** (`gpu_util_pct >= 90%` nhưng `MFU < 30%`):
1. **`gpu-h100-4` (H100):** `GPU-Util = 98.2%` nhưng `MFU = 0.194` (MBU = 0.207).
2. **`gpu-a10g-1` (A10G):** `GPU-Util = 96.9%` nhưng `MFU = 0.268` (MBU = 0.302).

### 3.2 Cơ chế kỹ thuật gốc rễ (Root Cause Analysis)
* **`nvidia-smi` chỉ đo thời gian xung nhịp (Time-active Clock):** Chỉ số GPU-Util % thể hiện tỷ lệ phần trăm thời gian trong 1 giây mà ít nhất một kernel đang hoạt động trên GPU. Nó **hoàn toàn không đo lường số lượng phép tính dấu phẩy động (FLOPs)** thực sự được thực thi.
* **Tắc nghẽn bộ nhớ (Memory Stall) & Giai đoạn Decode:** Trong giai đoạn sinh từ (LLM autoregressive decode), tỷ số cường độ số học (Arithmetic Intensity) cực kỳ thấp ($\approx 1\text{--}2\text{ FLOP/byte}$), nằm sâu bên dưới điểm gờ (ridge point $\approx 295\text{ FLOP/byte}$) của mô hình Roofline. Các nhân tính toán Tensor Core phải liên tục dừng chờ nạp trọng số từ bộ nhớ HBM, dẫn đến GPU luôn báo 100% bận rộn nhưng MFU chỉ đạt $\sim 20\%$.
* **Chi phí khởi chạy kernel (Kernel Launch Overhead) & Batch size nhỏ:** Việc chạy batch size = 1 hoặc không gom batch khiến GPU mất nhiều chu kỳ đồng bộ và chờ CPU dispatch kernel thay vì thực hiện tính toán hữu ích.

### 3.3 Tác động tài chính
NimbusAI đang trả trọn vẹn **$3.50/giờ** cho một node H100 để nhận lại năng lực tính toán chỉ tương đương một GPU dòng trung cấp (như A10G hay L4). Bằng cách tách biệt giai đoạn Prefill (compute-bound) sang H100 và chuyển giai đoạn Decode (memory-bound) sang các GPU tối ưu băng thông/chi phí bộ nhớ như A100/L4, công ty tiết kiệm ngay **$655/tháng** cho mỗi GPU mà không làm suy giảm SLA độ trễ.

---

## 4. Quản Trị Chi Phí (FinOps Governance) & Chuẩn FOCUS

* **Độ phủ gắn thẻ (Tag Coverage):** Đạt mức **92%**, vượt xa ngưỡng tiêu chuẩn tối thiểu (80%).
* **Chuyển đổi từ Showback sang Chargeback:** Vì độ phủ tag đạt 92%, hệ thống đã kích hoạt thành công cổng **Chargeback**, cho phép hạch toán chi phí thực tế tới từng phòng ban thay vì chỉ gửi báo cáo nhận thức (Showback):
  - Team `assistant`: $2.59 / ngày (30.5%)
  - Team `search`: $2.49 / ngày (29.4%)
  - Team `eval`: $1.79 / ngày (21.1%)
  - Team `rag`: $1.60 / ngày (18.9%)
* **Xuất khẩu dữ liệu chuẩn FOCUS:** Toàn bộ 50 dòng chi phí đã được chuẩn hoá theo schema **FinOps Open Cost and Usage Specification (FOCUS)** (`ServiceCategory`, `BilledCost`, `Tags`, `ResourceId`), sẵn sàng tích hợp vào nền tảng quản trị tài chính đa đám mây nội bộ.

---

## 5. Chiến Lược Bền Vững (Green FinOps & Sustainability)

* **Tiêu thụ năng lượng:** $0.24\text{ Wh}$ trên mỗi câu truy vấn LLM trung bình (800 tokens).
* **Phát thải Carbon:** Đạt $0.091\text{ gCO2e}$ mỗi truy vấn khi triển khai tại vùng `us-east-1` (lưới điện có cường độ phát thải trung bình $379\text{ gCO2e/kWh}$).
* **Lựa chọn vùng tối ưu (Carbon-aware Routing):**
  - Vùng **`europe-north1` (Na Uy)** được xác định là vùng **rẻ nhất và sạch nhất** nhờ tận dụng 100% nguồn thủy điện tái tạo (cường độ phát thải chỉ $28\text{ gCO2e/kWh}$).
  - Việc chuyển dịch các tác vụ huấn luyện gián đoạn (`job-train-llm`, `job-train-embed`) sang `europe-north1` giúp **giảm hơn 92.6% lượng phát thải carbon** của workload huấn luyện mà không làm gia tăng chi phí thuê GPU.

## 6. Kết Quả Triển Khai Phần Mở Rộng ("Your Turn" Extensions)

Chúng tôi đã triển khai, đo lường và kiểm thử đơn vị thành công **3 phần mở rộng nâng cao** (vượt yêu cầu tối thiểu 2 extensions theo Rubric):

### 6.1 Extension 3 — Kinh tế học Prompt Cache (`cache_is_worth_it()`)
* **Mã nguồn thực hiện:** Đã viết hàm `cache_break_even_reads()` và `cache_is_worth_it()` trong [finops/pricing.py](file:///d:/GitHub/LAB/K4-L3-DAY25-TranGiaKhanh-2A202602689-GpuFinOps/finops/pricing.py), tích hợp kiểm thử tự động tại [tests/test_extensions.py](file:///d:/GitHub/LAB/K4-L3-DAY25-TranGiaKhanh-2A202602689-GpuFinOps/tests/test_extensions.py).
* **Kết quả đo lường định lượng:**
  - Mô hình Small (write $0.25/1M, base read $0.20/1M, chiết khấu 90%): Điểm hòa vốn là **1.39 lượt đọc**.
  - Mô hình Large (write $3.75/1M, base read $3.00/1M, chiết khấu 90%): Điểm hòa vốn cũng là **1.39 lượt đọc**.
  - Trong hệ thống production RAG, prefix trung bình được tái sử dụng **3.5 lần** (>1.39) $\implies$ Khẳng định **Cache là hoàn toàn có lợi (True)**, giúp tiết kiệm **$18.18 / ngày** riêng tiền input tokens.

### 6.2 Extension 4 — Ngân sách & Năng lượng Suy Luận (`Reasoning Budget`)
* **Mã nguồn thực hiện:** Tích hợp bộ đo lường chi phí và tiêu thụ năng lượng theo cờ `is_reasoning` trong [missions/m2_inference_levers.py](file:///d:/GitHub/LAB/K4-L3-DAY25-TranGiaKhanh-2A202602689-GpuFinOps/missions/m2_inference_levers.py).
* **Kết quả đo lường định lượng:**
  - Lượng truy vấn reasoning chiếm **8.4% tổng lưu lượng** (201 / 2,400 requests).
  - Tuy nhiên, reasoning chiếm **16.5% tổng chi phí** ($1.40 / $8.48/ngày) với chi phí bình quân $0.0069/query (**gấp 2.2 lần** non-reasoning).
  - Về năng lượng: Reasoning tiêu thụ **29,787.7 Wh — chiếm tới 94.0% tổng năng lượng inference**! Mỗi query reasoning ngốn $148.2\text{ Wh}$, **gấp 172.6 lần** so với query thông thường ($0.86\text{ Wh}$).
* **Đề xuất quy tắc định tuyến:** Áp dụng Semantic Router: chỉ kích hoạt reasoning khi điểm độ tin cậy (confidence score) $< 0.75$ hoặc câu hỏi thuộc nhóm lập trình/toán học phức tạp. Cắt giảm 50% reasoning không cần thiết sẽ tiết kiệm thêm **$21/tháng** và **$446.8\text{ kWh/tháng}$ điện năng**.

### 6.3 Extension 5 — Lập Lịch Nhận Thức Carbon (`Carbon-Aware Scheduling`)
* **Mã nguồn thực hiện:** Bổ sung thuật toán phân bổ vị trí địa lý cho 5 tác vụ huấn luyện gián đoạn trong [missions/m3_purchasing.py](file:///d:/GitHub/LAB/K4-L3-DAY25-TranGiaKhanh-2A202602689-GpuFinOps/missions/m3_purchasing.py).
* **Kết quả đo lường định lượng:**
  - Tổng điện năng tiêu thụ của 5 tác vụ gián đoạn là **$1,841.8\text{ kWh}$**.
  - Nếu chạy mặc định tại `us-east-1` (380 gCO2e/kWh): Phát thải **$699.9\text{ kg CO2e}$**.
  - Nếu chuyển sang `europe-north1` (28–30 gCO2e/kWh): Phát thải chỉ còn **$55.3\text{ kg CO2e}$**.
  - Mức cắt giảm đạt **$644.6\text{ kg CO2e}$ (giảm 92.1% lượng phát thải)**, đồng thời giá điện ở Na Uy rẻ hơn ($0.09 vs $0.12/kWh), tiết kiệm thêm **$55.26** tiền điện.

---

## 7. Lộ Trình Hành Động Đề Xuất Cho Ban Giám Đốc NimbusAI

Nếu đảm nhiệm vai trò FinOps Lead tại NimbusAI, đây là 3 hành động ưu tiên cao nhất trong 30–60–90 ngày tới:

1. **Hành động 1 (Tuần 1–2): Tái cấu trúc hợp đồng mua sắm hạ tầng (Immediate ROI - Tiết kiệm $10,040/tháng)**
   - Ký kết hợp đồng Reserved Instance 3 năm cho 3 cụm máy chủ phục vụ inference 24/7 (`job-infer-chat`, `job-infer-rag`, `job-infer-search`).
   - Cấu hình hạ tầng điều phối (Orchestrator) hỗ trợ Spot Instances có gắn cơ chế checkpoint định kỳ cho 5 tác vụ huấn luyện và sandbox.
2. **Hành động 2 (Tháng 1): Tích hợp Inference Proxy thông minh (Tiết kiệm $1,212/tháng)**
   - Triển khai LiteLLM / Semantic Router để tự động phân luồng (Cascade): 70% câu hỏi hội thoại đơn giản được chuyển sang mô hình cỡ nhỏ (Small Tier).
   - Kích hoạt cơ chế Prompt Caching trên toàn bộ hệ thống RAG và Chatbot nội bộ để tận dụng chiết khấu 90% cho system prompt và tài liệu tra cứu lặp lại.
3. **Hành động 3 (Tháng 2): Triển khai Giám sát MFU/MBU thời gian thực & Thực thi Chargeback**
   - Thay thế biểu đồ theo dõi `GPU-Util %` truyền thống bằng dashboard theo dõi **MFU và MBU thời gian thực** trên Prometheus/Grafana.
   - Áp dụng chính sách phạt ngân sách đối với các tác vụ chạy không tải quá 30 phút hoặc có MFU $<25\%$.
   - Chính thức phân bổ hóa đơn thực tế (Chargeback) hàng tháng về các nhóm sản phẩm dựa trên file xuất FOCUS.
