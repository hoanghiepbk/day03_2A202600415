# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Trần Gia Khánh
- **Student ID**: 2A202600293
- **Date**: 06-04-2026

---

## I. Technical Contribution (15 Points)

- **Modules Implementated**:
  - `src/agent/agent.py`: Implemented complete ReAct loop (Thought -> Action -> Observation -> Final Answer), action parsing, final-answer parsing, tool execution, and error logging.
  - `src/tools/dalat_travel_tools.py`: Implemented 3 tools for the Da Lat scenario:
    - `get_weather(city, date)`
    - `search_hotels(city, check_in, check_out, max_price)`
    - `get_hotel_reviews(hotel_id)`
  - `src/agent/dalat_prompts.py`: Designed separate prompt versions for Agent v1 (minimal) and Agent v2 (strict JSON action format + guardrails).
  - `run_lab.py`: Added `dalat-compare` pipeline to run baseline chatbot + Agent v1 + Agent v2 and output telemetry summary.
  - `chatbot.py`: Baseline chatbot flow with no tools for comparison.
  - `src/telemetry/metrics.py`: Added request-level metrics tracking and session summary (requests, tokens, latency, cost estimate).
  - `tests/test_parse.py`: Added tests for parser/action handling utilities.

- **Code Highlights**:
  - ReAct loop with observation feedback:
    - Model output is parsed for `Action:` or `Final Answer:`.
    - When action is valid, tool output is appended as `Observation:` to the next prompt iteration.
  - Robust parsing helpers:
    - `parse_action`, `parse_final_answer`
    - CSV and key-value argument parsing
    - JSON argument parsing path for stricter v2 prompt format
  - Telemetry events used:
    - `AGENT_START`, `AGENT_END`
    - `TOOL_CALL`
    - `AGENT_ERROR` (e.g., `PARSE_ERROR`, `TOOL_ARG_MISMATCH`)
    - `LLM_METRIC`

- **Documentation**:
  - The baseline chatbot intentionally does not call tools and is used to demonstrate single-shot limitations.
  - Agent v1/v2 both use the same tools, but different prompt strictness:
    - v1: minimal instructions (more flexible, easier to drift/hallucinate)
    - v2: stricter format constraints (reduced ambiguity, but still model-dependent)
  - The comparison command `python run_lab.py dalat-compare` generates evidence for scoring categories: functionality, trace quality, and evaluation metrics.

---

## II. Debugging Case Study (10 Points)

- **Problem Description**:
  - In the Da Lat scenario, Agent v2 produced a parser failure at step 0, then returned an irrelevant hallucinated story ("In the fog-laden streets of London...") instead of tool-grounded recommendations.
  - Agent v1 also hallucinated a non-existent hotel ("Green Valley Inn") despite tool inventory containing different entries.

- **Log Source**:
  - Run command: `python run_lab.py dalat-compare`
  - Key events observed:
    - `AGENT_ERROR` with `code: "PARSE_ERROR"` at step 0 (Agent v2).
    - `AGENT_END` with final answer unrelated to query (Agent v2).
    - `AGENT_END` with final answer containing hallucinated hotel name not present in tool outputs (Agent v1).
  - Same run also contains valid telemetry:
    - `LLM_METRIC` for each request
    - `TOOL_CALL` for `get_weather` in v1

- **Diagnosis**:
  - Root causes:
    1. **Model-format mismatch**: Phi-3 is weaker at strictly obeying structured ReAct output and may ignore action schema under long prompts.
    2. **Prompt compliance instability**: even with strict v2 instruction, the model sometimes outputs narrative text not matching `Action:` parser regex.
    3. **Grounding gap**: model can still hallucinate details not present in observations unless constrained harder.

- **Solution**:
  - Implemented and refined parser + guardrails:
    - Strict parsing for `Action: tool_name(...)` and `Final Answer:`.
    - Parse error recovery: append correction observation asking model to return valid headers.
  - Added prompt hardening:
    - v2 prompt requires JSON-style action arguments and explicit workflow order.
  - Added structured telemetry:
    - Logged parser/tool errors and metrics to make failures diagnosable instead of anecdotal.
  - Practical next step for higher reliability:
    - Add deterministic post-validation so final answer must reference only tool-returned entities; otherwise force retry.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**:
   - The baseline chatbot produced a safe but generic response and explicitly could not provide verifiable hotel/weather data.
   - ReAct agent architecture is better for multi-step tasks because it can decompose intent into tool calls and use external observations before answering.
   - In theory, this is exactly what the Da Lat use case needs: weather -> hotels under budget -> reviews -> recommendation + clothing advice.

2. **Reliability**:
   - In this run, both agents were less reliable than expected due to local model limitations:
     - v1 hallucinated an unlisted hotel.
     - v2 produced parse error then irrelevant narrative output.
   - The baseline chatbot was "less useful" but more behaviorally stable (it admitted limitations instead of fabricating structured results).
   - Conclusion: agent architecture is more capable, but only when prompt adherence + parser robustness + model quality are sufficient.

3. **Observation**:
   - Observation feedback is critical: once tool output is appended, the model has grounding context for the next step.
   - However, observation injection alone is not enough; model may still ignore observations without hard constraints or output validation.
   - This lab confirmed the instructor point: logs/traces are essential to verify whether observations actually influenced subsequent actions.

---

## IV. Future Improvements (5 Points)

- **Scalability**:
  - Move tool execution to async workers with queue-based orchestration (e.g., Celery/RQ) so multiple user requests and tool calls can run concurrently.
  - Add provider failover policy (OpenAI primary, local fallback) and request-level circuit breakers.
  - Add persistent state store for traces and replay (for RCA and regression testing).

- **Safety**:
  - Add output validator/guardrail layer:
    - Validate that recommended hotels exist in latest `search_hotels` observation.
    - Reject final answers with entities absent from tool outputs.
  - Add max-step, retry budget, and tool allowlist per scenario.
  - Add PII/secret redaction in logs before writing telemetry.

- **Performance**:
  - Introduce caching for deterministic tool results (weather/hotel lookup snapshots).
  - Use retrieval over tool docs/examples to reduce prompt length and parser failure risk.
  - Track additional metrics: token ratio (`completion/prompt`), tool-call success rate, parse-error rate, and end-to-end task success rate.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
