# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Phạm Hữu Hoàng Hiệp
- **Student ID**: 2A202600415
- **Date**: 6/4/2026

---

## I. Technical Contribution (15 Points)

*Describe your specific contribution to the codebase (e.g., implemented a specific tool, fixed the parser, etc.).*

- **Modules Implementated**: 
                            -Tool Design Evolution
                            -Trace Quality
- **Code Highlights**: 
https://github.com/hoanghiepbk/day03_2A202600415/commit/7c25f7997d4187eeb3cbca91d2c27b23be394be5
https://github.com/hoanghiepbk/day03_2A202600415/commit/e0de44e8afe4fddb702862c5890971d76f4208b1
- **Documentation**: 
Các thay đổi chính:

Thêm module mới src/telemetry/reporting.py

Thêm cơ chế ghi log có cấu trúc để dễ lấy trace:
Ghi logs/experiments.jsonl (mỗi run 1 record JSON)
Ghi logs/compare_summary.csv (bảng so sánh chatbot/agent để mở Excel)
Cập nhật run_lab.py

chatbot, agent, compare, dalat-compare, benchmark đều ghi snapshot vào experiments.jsonl
compare và dalat-compare tự động append dòng vào compare_summary.csv
Thêm hướng dẫn log tại logs/README.md

Chỉ rõ nguồn dữ liệu cho phần Tool Design Evolution và Trace Quality
Trỏ trực tiếp tới các file log mới để trích bằng chứng
Cập nhật README.md

Thêm mục “Comparison Logs” mô tả 3 file log phục vụ report
Đã cải thiện code để pipeline chạy ổn (không bị kẹt llama_cpp khi không dùng local model), nên việc thu trace cho chatbot/agent giờ ổn định hơn.


---

## II. Debugging Case Study (10 Points)

*Analyze a specific failure event you encountered during the lab using the logging system.*

- **Problem Description**: Agent lúc trả lời tiếng việt lúc trả lời tiếng anh
- **Log Source**: Hiển thị khi chạy lệnh test
- **Diagnosis**: 
    Vì prompt của đang không đồng nhất ngôn ngữ giữa các mode chạy.

    Cụ thể trong project này:

    chatbot dùng system prompt tiếng Anh (chatbot.py)
    → model thường trả lời tiếng Anh.
    agent mặc định (v1/v2 trong src/agent/agent.py) cũng là prompt tiếng Anh
    → thường ra tiếng Anh.
    dalat-compare dùng prompt v2 tiếng Việt (src/agent/dalat_prompts.py)
    → thường ra tiếng Việt.
    Ngoài ra model có thể “dao động” theo:

    ngôn ngữ câu hỏi user (Việt/Anh),
    lịch sử ngữ cảnh,
    temperature > 0 (có tính ngẫu nhiên).
- **Solution**: 
    Trong BASELINE_SYSTEM, thêm rule ngôn ngữ.

    BASELINE_SYSTEM = """You are a helpful assistant. Answer in one reply.
You do NOT have access to tools, databases, or live APIs.
If the user asks for stock, coupons, or shipping fees that require external data you do not have,
reason transparently and clearly state what you are guessing versus what you cannot verify.

Language policy:
- Detect the user's language from the latest user message.
- Reply in the same language as the user's latest message.
- If the user mixes languages, prioritize the language that dominates the latest message."""

Trong get_system_prompt(), thêm block Language policy cho cả v1/v2.
Giảm nhiệt độ ở run agent:

temperature=0.1 hoặc 0.0 (đặc biệt cho benchmark/report)

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Reflect on the reasoning capability difference.*

1.  **Reasoning**: How did the `Thought` block help the agent compared to a direct Chatbot answer?
        Thought block giúp agent tách bài toán đa bước thành các bước có kiểm chứng: chọn tool -> lấy dữ kiện -> cập nhật kết luận. Ở case commerce trong log, agent gọi tuần tự check_stock -> get_discount -> calc_shipping rồi mới ra Final Answer: $1806.60, nên câu trả lời có căn cứ rõ ràng hơn chatbot (chatbot chỉ nêu hướng dẫn chung khi thiếu dữ liệu thật).
2.  **Reliability**: In which cases did the Agent actually perform *worse* than the Chatbot?
        Agent có thể kém chatbot ở các câu hỏi đơn giản hoặc khi prompt/tool không khớp ngữ cảnh. Ví dụ trong log Đà Lạt, có lượt agent v2 gọi nhầm tool calc_shipping (tool của ecommerce) cho bài toán khách sạn, làm tăng token và chi phí mà chất lượng không tăng tương ứng. Ngoài ra, agent từng gặp PARSE_ERROR ở v1 do format output không đúng Action/Final Answer.
3.  **Observation**: How did the environment feedback (observations) influence the next steps?
        Observation là cơ chế “feedback từ môi trường” giúp agent tự sửa hướng đi ở bước sau. Khi tool trả dữ liệu cụ thể (ví dụ weather/hotel reviews), bước kế tiếp của agent chuyển từ phỏng đoán sang tổng hợp có căn cứ. Ngược lại, khi observation là parse error hoặc tool không liên quan, agent dễ bị lệch hướng hoặc kết thúc sớm với câu trả lời generic.

---

## IV. Future Improvements (5 Points)

*How would you scale this for a production-level AI agent system?*

- **Scalability**: Chuyển execution sang hàng đợi bất đồng bộ cho tool calls, thêm cache cho kết quả tool lặp lại, và tách telemetry thành pipeline riêng (ingest -> store -> dashboard) để xử lý nhiều phiên đồng thời.
- **Safety**: Thêm lớp validator schema cho mọi Action trước khi chạy tool; bổ sung policy check (tool allowlist theo task), guardrails chống loop/hallucination, và cơ chế fallback sang “safe final answer” khi vượt ngưỡng lỗi.
- **Performance**: Dùng dynamic model routing (task đơn giản -> model rẻ/nhanh, task đa bước -> model mạnh), nén context mỗi vòng lặp để giảm token, và tối ưu tool selection bằng retrieval theo mô tả tool thay vì luôn nhồi toàn bộ inventory vào prompt.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
