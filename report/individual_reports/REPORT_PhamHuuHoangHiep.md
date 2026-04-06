# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Đặng Tiến Dũng
- **Student ID**: 2A202600024
- **Date**: 06-04-2026

---

## I. Technical Contribution (15 Points)

*Describe your specific contribution to the codebase (e.g., implemented a specific tool, fixed the parser, etc.).*

- **Modules Implementated**: `run_lab_tests.sh`, `run_test_promts.py` add tests cases show case fail tolorant
- **Code Highlights**: Conducted comprehensive architectural reviews of both the baseline Chatbot and ReAct Agent implementations. Validated the system's stateless execution and evaluated prompt resilience without historical context memory.
- **Documentation**: Developed automated test suites (`run_test_prompts.py` and shell scripts) that iterate through realistic Da Lat queries, calling `cmd_dalat_compare` programmatically to stress-test prompt resilience. Ensured the framework safely navigates LLM API throttling mechanisms.

---

## II. Debugging Case Study (10 Points)

*Analyze a specific failure event you encountered during the lab using the logging system.*

- **Problem Description**: The agent execution process crashed entirely when evaluating multiple conversational scenarios consecutively, halting all subsequent steps.
- **Log Source**: Terminal Exception `google.api_core.exceptions.ResourceExhausted: 429 You exceeded your current quota... limit: 20, model: gemini-2.5-flash`
- **Diagnosis**: The Gemini provider enforces a strict Requests-Per-Minute (RPM) rate limit on Free Tier usage. Because our automation script immediately dispatched the next question once a test ended, we triggered rate ceilings and broke the ReAct execution pipeline.
- **Solution**: Refactored the testing infrastructure (`run_test_prompts.py`) to systematically intercept these exceptions and orchestrate a `time.sleep(60)` cooldown phase between requests to safely respect the Free Tier thresholds.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Reflect on the reasoning capability difference.*

1.  **Reasoning**: The `Thought` block forces the agent to use a chain-of-thought scratchpad, which is essential for multi-hop constraints (e.g., finding available hotels -> pulling their IDs -> checking reviews to fulfill user intent). A direct chatbot simply guesses or hallucinates answers to these complex dependencies.
2.  **Reliability**: The Agent performs *worse* when strict latency is required, or when the LLM struggles to consistently output the `Action:` formatting (breaking the regex parser). A simple chatbot is far more robust and faster for basic Q&A.
3.  **Observation**: Real-time environmental feedback guarantees grounding. For example, if a tool returns "vượt ngân sách" (over budget), the agent is forced to process this failure observation and pivot to an affordable lodging choice rather than fabricating data.

---

## IV. Future Improvements (5 Points)

*How would you scale this for a production-level AI agent system?*

- **Scalability**: Deploy an asynchronous message queue (e.g., RabbitMQ or Kafka) to distribute complex agent workflows and tool executions to background workers instead of blocking the main thread.
- **Safety**: Implement a secondary "Supervisor" LLM evaluator that audits tool parameters for destructive actions (like financial transactions) before they are passed to the executable functions.
- **Performance**: Use semantic search and Vector Databases to dynamically filter and retrieve only the most relevant subset of tools per query, rather than packing all tool descriptions into the system prompt context window.

