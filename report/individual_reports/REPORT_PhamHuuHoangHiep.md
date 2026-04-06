# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Phạm Hữu Hoàng Hiệp
- **Student ID**: 2A202600415
- **Date**: 6/4/2026

---

## I. Technical Contribution (15 Points)

*Describe your specific contribution to the codebase (e.g., implemented a specific tool, fixed the parser, etc.).*

- **Modules Implementated**:
  - Create web demo
  - Tool Design Evolution
  - Trace Quality
  - Failure Handling
  - Sửa agent thay đổi ngôn ngữ dựa theo input

- **Code Highlights**:
  - Link demo PNG : https://docs.google.com/document/d/1DuX_CcaLGKkvT_pANiCQuJly-h672MlIweQIgxM51lQ/edit?tab=t.0
  - [Commit 1](https://github.com/hoanghiepbk/day03_2A202600415/commit/7636ca23f42b4caa6eb9f4cee4c69768b362e85c)
  - [Commit 2](https://github.com/hoanghiepbk/day03_2A202600415/commit/7c25f7997d4187eeb3cbca91d2c27b23be394be5)
  - [Commit 3](https://github.com/hoanghiepbk/day03_2A202600415/commit/8a7ce72dbf901f910b11f967f34e1e91098f4609)
  - [Commit 4](https://github.com/hoanghiepbk/day03_2A202600415/commit/e0de44e8afe4fddb702862c5890971d76f4208b1)

- **Documentation**:
  Các thay đổi chính:
  - Create web demo với các chức năng :
    - 🔀 3 chế độ: Đơn lẻ / So sánh 2 / So sánh cả 3
    - 📡 Broadcast: Gửi đồng thời 1 câu hỏi đến tất cả panels
    - 📊 Metrics real-time: Tokens, cost, latency, requests per panel
    - 🎯 Chuyển đổi linh hoạt: Dropdown chọn mode trong mỗi panel
  - Retry có điều kiện khi parse lỗi
  - Guardrail chống gọi sai tool
  - Guardrail cho tham số tool
  - Loop protection thông minh hơn
  - Fallback an toàn
  - Thêm module mới `src/telemetry/reporting.py`
  - Thêm cơ chế ghi log có cấu trúc để dễ lấy trace:
    - Ghi `logs/experiments.jsonl` (mỗi run 1 record JSON)
    - Ghi `logs/compare_summary.csv` (bảng so sánh chatbot/agent để mở Excel)
  - Cập nhật `run_lab.py`
    - `chatbot`, `agent`, `compare`, `dalat-compare`, `benchmark` đều ghi snapshot vào `experiments.jsonl`
    - `compare` và `dalat-compare` tự động append dòng vào `compare_summary.csv`
  - Chỉ rõ nguồn dữ liệu cho phần Tool Design Evolution và Trace Quality
  - Thêm mục "Comparison Logs" mô tả 3 file log phục vụ report
  - Cải thiện pipeline chạy ổn định (không bị kẹt `llama_cpp` khi không dùng local model), nên việc thu trace cho chatbot/agent ổn định hơn


---

## II. Debugging Case Study (10 Points)

*Analyze a specific failure event you encountered during the lab using the logging system.*

- **Problem Description**: Agent lúc trả lời tiếng việt lúc trả lời tiếng anh
- **Log Source**: Hiển thị khi chạy lệnh test
- **Diagnosis**:
  - Prompt không đồng nhất ngôn ngữ giữa các mode chạy
  - `chatbot` dùng system prompt tiếng Anh (`chatbot.py`) -> model thường trả lời tiếng Anh
  - Agent mặc định (`v1/v2` trong `src/agent/agent.py`) cũng là prompt tiếng Anh -> thường ra tiếng Anh
  - `dalat-compare` dùng prompt v2 tiếng Việt (`src/agent/dalat_prompts.py`) -> thường ra tiếng Việt
  - Model còn dao động theo:
    - ngôn ngữ câu hỏi user (Việt/Anh)
    - lịch sử ngữ cảnh
    - `temperature > 0` (có tính ngẫu nhiên)

- **Solution**:
  - Trong `BASELINE_SYSTEM`, thêm rule ngôn ngữ:
    - Detect the user's language from the latest user message.
    - Reply in the same language as the user's latest message.
    - If mixed, prioritize the dominant language in the latest message.
  - Trong `get_system_prompt()`, thêm block `Language policy` cho cả `v1/v2`
  - Giảm nhiệt độ khi benchmark/report: `temperature=0.1` hoặc `0.0`

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Reflect on the reasoning capability difference.*

1. **Reasoning**: How did the `Thought` block help the agent compared to a direct Chatbot answer?  
   Thought block giúp agent tách bài toán đa bước thành các bước có kiểm chứng: chọn tool -> lấy dữ kiện -> cập nhật kết luận. Ở case commerce trong log, agent gọi tuần tự `check_stock` -> `get_discount` -> `calc_shipping` rồi mới ra `Final Answer: $1806.60`, nên câu trả lời có căn cứ rõ ràng hơn chatbot (chatbot chỉ nêu hướng dẫn chung khi thiếu dữ liệu thật).

2. **Reliability**: In which cases did the Agent actually perform *worse* than the Chatbot?  
   Agent có thể kém chatbot ở các câu hỏi đơn giản hoặc khi prompt/tool không khớp ngữ cảnh. Ví dụ trong log Đà Lạt, có lượt agent v2 gọi nhầm tool `calc_shipping` (tool của ecommerce) cho bài toán khách sạn, làm tăng token và chi phí mà chất lượng không tăng tương ứng. Ngoài ra, agent từng gặp `PARSE_ERROR` ở v1 do format output không đúng `Action/Final Answer`.

3. **Observation**: How did the environment feedback (observations) influence the next steps?  
   Observation là cơ chế "feedback từ môi trường" giúp agent tự sửa hướng đi ở bước sau. Khi tool trả dữ liệu cụ thể (ví dụ weather/hotel reviews), bước kế tiếp của agent chuyển từ phỏng đoán sang tổng hợp có căn cứ. Ngược lại, khi observation là parse error hoặc tool không liên quan, agent dễ bị lệch hướng hoặc kết thúc sớm với câu trả lời generic.

---

## IV. Future Improvements (5 Points)

*How would you scale this for a production-level AI agent system?*

- **Scalability**: Chuyển execution sang hàng đợi bất đồng bộ cho tool calls, thêm cache cho kết quả tool lặp lại, và tách telemetry thành pipeline riêng (ingest -> store -> dashboard) để xử lý nhiều phiên đồng thời.
- **Safety**: Thêm lớp validator schema cho mọi Action trước khi chạy tool; bổ sung policy check (tool allowlist theo task), guardrails chống loop/hallucination, và cơ chế fallback sang “safe final answer” khi vượt ngưỡng lỗi.
- **Performance**: Dùng dynamic model routing (task đơn giản -> model rẻ/nhanh, task đa bước -> model mạnh), nén context mỗi vòng lặp để giảm token, và tối ưu tool selection bằng retrieval theo mô tả tool thay vì luôn nhồi toàn bộ inventory vào prompt.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
