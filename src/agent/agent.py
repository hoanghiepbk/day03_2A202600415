import json
import re
from typing import Any, Dict, List, Optional, Tuple

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


def _strip_markdown_fences(text: str) -> str:
    t = text.strip()
    if not t.startswith("```"):
        return t
    lines = t.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def split_csv_args(blob: str) -> List[str]:
    """Split on commas at depth 0, respecting quoted strings."""
    blob = blob.strip()
    if not blob:
        return []
    parts: List[str] = []
    cur: List[str] = []
    in_quote: Optional[str] = None
    i = 0
    while i < len(blob):
        ch = blob[i]
        if in_quote:
            cur.append(ch)
            if ch == in_quote and (i == 0 or blob[i - 1] != "\\"):
                in_quote = None
            i += 1
            continue
        if ch in "\"'":
            in_quote = ch
            cur.append(ch)
            i += 1
            continue
        if ch == ",":
            parts.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    if cur:
        parts.append("".join(cur).strip())
    return parts


def strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _coerce_scalar(v: Any) -> Any:
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    if not isinstance(v, str):
        return v
    s = v.strip()
    if re.fullmatch(r"-?\d+", s):
        try:
            return int(s)
        except ValueError:
            return v
    if re.fullmatch(r"-?\d+\.\d+", s):
        try:
            return float(s)
        except ValueError:
            return v
    return v


def kwargs_from_blob(inner: str) -> Dict[str, Any]:
    """Parse tool args as JSON object or key=value,... for kwargs tools."""
    inner = inner.strip()
    if inner.startswith("{") and inner.endswith("}"):
        obj = json.loads(inner)
        if not isinstance(obj, dict):
            raise ValueError("JSON tool arguments must be a JSON object {{...}}")
        return {str(k): _coerce_scalar(v) for k, v in obj.items()}
    out: Dict[str, Any] = {}
    for part in split_csv_args(inner):
        if "=" not in part:
            raise ValueError(f"Expected key=value inside Action(...), got: {part!r}")
        k, v = part.split("=", 1)
        out[k.strip()] = _coerce_scalar(strip_quotes(v.strip()))
    return out


def normalize_arg_tokens(raw_parts: List[str]) -> List[Any]:
    out: List[Any] = []
    for p in raw_parts:
        p = p.strip()
        if not p:
            continue
        p = strip_quotes(p)
        try:
            if "." in p:
                out.append(float(p))
            else:
                out.append(int(p))
            continue
        except ValueError:
            out.append(p)
    return out


def parse_final_answer(text: str) -> Optional[str]:
    # First line only avoids greedy capture of trailing Thought/Action noise from small models.
    m = re.search(r"Final\s*Answer\s*:\s*([^\n]+)", text, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip()


def parse_action(text: str) -> Optional[Tuple[str, str]]:
    """
    Returns (tool_name, inner_args_string) from first Action: tool(args)
    """
    m = re.search(r"Action\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)", text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


class ReActAgent:
    """
    ReAct agent: Thought -> Action -> Observation loop with structured telemetry.
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: List[Dict[str, Any]],
        max_steps: int = 8,
        prompt_version: str = "v2",
        temperature: Optional[float] = 0.2,
        system_prompt_override: Optional[str] = None,
    ):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.prompt_version = prompt_version
        self.temperature = temperature
        self.system_prompt_override = system_prompt_override
        self.history: List[Dict[str, Any]] = []
        self._tool_index = {t["name"]: t for t in tools}

    def get_system_prompt(self) -> str:
        if self.system_prompt_override is not None:
            return self.system_prompt_override
        lines = [f"- {t['name']}: {t['description']}" for t in self.tools]
        tool_block = "\n".join(lines)
        base = f"""You are a ReAct assistant. You may call tools to retrieve facts, then reason with those facts.

Available tools:
{tool_block}

Strict output rules:
- Use the exact headers: Thought:, then either Action: or Final Answer:.
- Do NOT write "Observation:" yourself; the system will append real observations after your Action.
- Action format: tool_name(arg1, arg2) with comma-separated arguments. Use quotes for strings.
  Examples:
  Action: check_stock("iPhone")
  Action: get_discount("WINNER")
  Action: calc_shipping(0.8, "Hanoi")
- When you have enough information, output:
  Final Answer: <concise answer for the user>

Language policy:
- Detect the language of the latest user message.
- Keep Thought/Action/Final Answer in that same language.
- If the latest user message mixes languages, follow the dominant language in that message."""

        if self.prompt_version == "v1":
            return f"""You are an intelligent assistant. Tools:
{tool_block}
Use: Thought / Action / Final Answer as in the lab template.

Language policy:
- Detect the language of the latest user message.
- Keep Thought/Action/Final Answer in that same language.
- If the latest user message mixes languages, follow the dominant language in that message."""
        return base

    def _generate_kwargs(self) -> Dict[str, Any]:
        kw: Dict[str, Any] = {}
        # Avoid importing LocalProvider eagerly (which requires llama-cpp-python).
        if self.llm.__class__.__name__ == "LocalProvider":
            kw["stop"] = ["<|end|>"]
        if self.temperature is not None:
            kw["temperature"] = self.temperature
        return kw

    def _execute_tool(self, tool_name: str, args_blob: str) -> str:
        spec = self._tool_index.get(tool_name)
        if not spec:
            logger.log_event(
                "AGENT_ERROR",
                {
                    "code": "HALLUCINATION_TOOL",
                    "tool": tool_name,
                    "known": list(self._tool_index.keys()),
                },
            )
            return (
                f"Error: unknown tool '{tool_name}'. "
                f"Valid tools: {', '.join(self._tool_index.keys())}."
            )

        inner = args_blob.strip()
        run_fn = spec["run"]
        try:
            if spec.get("uses_kwargs"):
                try:
                    kwargs_dict = kwargs_from_blob(inner)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.log_event(
                        "AGENT_ERROR",
                        {"code": "JSON_PARSER_ERROR", "detail": str(e), "args": inner[:500]},
                    )
                    return f"Error: could not parse tool arguments: {e}"
                out = run_fn(**kwargs_dict)
            else:
                parts: List[Any] = []
                if inner.startswith("{") and inner.endswith("}"):
                    try:
                        obj = json.loads(inner)
                        if isinstance(obj, dict):
                            parts = list(obj.values())
                        else:
                            parts = [obj]
                    except json.JSONDecodeError as e:
                        logger.log_event(
                            "AGENT_ERROR",
                            {"code": "JSON_PARSER_ERROR", "detail": str(e), "args": inner[:500]},
                        )
                        return f"Error: could not parse JSON tool arguments: {e}"
                else:
                    parts = normalize_arg_tokens(split_csv_args(inner))
                out = run_fn(parts)
        except TypeError as e:
            logger.log_event(
                "AGENT_ERROR",
                {"code": "TOOL_ARG_MISMATCH", "tool": tool_name, "detail": str(e), "args": inner[:500]},
            )
            return f"Error: wrong arguments for {tool_name}: {e}"
        except json.JSONDecodeError as e:
            logger.log_event(
                "AGENT_ERROR",
                {"code": "JSON_PARSER_ERROR", "detail": str(e), "args": inner[:500]},
            )
            return f"Error: could not parse tool arguments as JSON: {e}"
        except Exception as e:
            logger.log_event(
                "AGENT_ERROR",
                {"code": "TOOL_RUNTIME_ERROR", "tool": tool_name, "detail": str(e)},
            )
            return f"Error executing {tool_name}: {e}"

        logger.log_event(
            "TOOL_CALL",
            {"tool": tool_name, "args": inner[:500], "result_preview": str(out)[:300]},
        )
        return str(out)

    def _safe_fallback_answer(self, user_input: str) -> str:
        """
        Deterministic fallback when the loop cannot recover from repeated formatting/loop errors.
        """
        return (
            "I cannot complete this request reliably due to repeated tool/format errors. "
            "Please rephrase your request with explicit details, then try again.\n"
            f"(Original request: {user_input[:240]})"
        )

    def run(self, user_input: str) -> str:
        logger.log_event(
            "AGENT_START",
            {
                "input": user_input[:2000],
                "model": self.llm.model_name,
                "prompt_version": self.prompt_version,
                "system_prompt_override": bool(self.system_prompt_override),
            },
        )

        scratch = (
            f"Question: {user_input}\n\n"
            "Work step by step. After each Action, wait for the next message which will contain Observation.\n"
        )
        steps = 0
        gen_kw = self._generate_kwargs()
        parse_error_streak = 0
        max_parse_retries = 2
        last_action_sig: Optional[Tuple[str, str]] = None
        repeated_action_count = 0

        while steps < self.max_steps:
            result = self.llm.generate(scratch, system_prompt=self.get_system_prompt(), **gen_kw)
            content = (result.get("content") or "").strip()
            tracker.track_request(
                result.get("provider", "unknown"),
                self.llm.model_name,
                result.get("usage") or {},
                int(result.get("latency_ms") or 0),
            )

            cleaned = _strip_markdown_fences(content)
            scratch += cleaned + "\n"
            self.history.append({"step": steps, "raw": content})

            fa = parse_final_answer(cleaned)
            if fa:
                logger.log_event(
                    "AGENT_END",
                    {"steps": steps + 1, "outcome": "FINAL_ANSWER", "answer_preview": fa[:500]},
                )
                return fa

            act = parse_action(cleaned)
            if not act:
                parse_error_streak += 1
                logger.log_event(
                    "AGENT_ERROR",
                    {
                        "code": "PARSE_ERROR",
                        "step": steps,
                        "detail": "No Final Answer and no parseable Action: tool(args).",
                        "parse_error_streak": parse_error_streak,
                    },
                )
                if parse_error_streak > max_parse_retries:
                    logger.log_event(
                        "AGENT_END",
                        {
                            "steps": steps + 1,
                            "outcome": "FALLBACK_AFTER_PARSE_RETRIES",
                            "code": "PARSE_RETRY_EXCEEDED",
                        },
                    )
                    return self._safe_fallback_answer(user_input)
                scratch += (
                    "\nObservation: Parse error — you must output either "
                    "`Action: tool_name(...)` or `Final Answer: ...` using the required headers.\n"
                )
                steps += 1
                continue

            tool_name, args_blob = act
            parse_error_streak = 0
            action_sig = (tool_name, args_blob.strip())
            if action_sig == last_action_sig:
                repeated_action_count += 1
            else:
                repeated_action_count = 0
            last_action_sig = action_sig

            if repeated_action_count >= 1:
                logger.log_event(
                    "AGENT_ERROR",
                    {
                        "code": "LOOP_DETECTED",
                        "step": steps,
                        "tool": tool_name,
                        "args": args_blob[:200],
                    },
                )
                scratch += (
                    "\nObservation: Loop guardrail triggered — you repeated the same Action with "
                    "the same arguments. Choose a different tool, adjust arguments, or provide Final Answer.\n"
                )
                steps += 1
                continue

            observation = self._execute_tool(tool_name, args_blob)
            scratch += f"Observation: {observation}\n"
            steps += 1

        logger.log_event(
            "AGENT_END",
            {"steps": steps, "outcome": "MAX_STEPS", "code": "TIMEOUT"},
        )
        return (
            "Agent stopped: exceeded max_steps without a Final Answer. "
            "Inspect logs for PARSE_ERROR, HALLUCINATION_TOOL, or loop patterns."
        )
