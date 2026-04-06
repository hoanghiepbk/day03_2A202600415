"""
Web server for interactive chatbot vs agent comparison UI.
Run: python web_server.py
Then open http://localhost:5000
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import chatbot as baseline_chatbot
from src.agent.agent import ReActAgent
from src.agent.dalat_prompts import (
    BASELINE_CHATBOT_SYSTEM_DALAT,
    build_dalat_system_prompt_v1,
    build_dalat_system_prompt_v2,
)
from src.core.provider_factory import create_llm_from_env
from src.telemetry.metrics import tracker
from src.tools.dalat_travel_tools import get_tool_specs_dalat

load_dotenv()

app = Flask(__name__, static_folder="web_ui", static_url_path="")
CORS(app)


@app.route("/")
def index():
    return send_from_directory("web_ui", "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("web_ui", path)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Unified chat endpoint.
    Body JSON: { "message": str, "mode": "chatbot"|"agent_v1"|"agent_v2", "provider": str|null }
    Returns: { "response": str, "metrics": dict, "mode": str, "elapsed_ms": int }
    """
    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    mode = data.get("mode", "chatbot")
    provider = data.get("provider") or None

    if not message:
        return jsonify({"error": "Message is required"}), 400

    tracker.reset()
    start = time.time()

    try:
        if mode == "chatbot":
            response_text = baseline_chatbot.run_chatbot(
                message, provider=provider, system_prompt=BASELINE_CHATBOT_SYSTEM_DALAT
            )
        elif mode == "agent_v1":
            tools = get_tool_specs_dalat()
            llm = create_llm_from_env(provider=provider)
            agent = ReActAgent(
                llm,
                tools,
                max_steps=12,
                prompt_version="dalat_v1",
                temperature=0.25,
                system_prompt_override=build_dalat_system_prompt_v1(tools),
            )
            response_text = agent.run(message)
        elif mode == "agent_v2":
            tools = get_tool_specs_dalat()
            llm = create_llm_from_env(provider=provider)
            agent = ReActAgent(
                llm,
                tools,
                max_steps=12,
                prompt_version="dalat_v2",
                temperature=0.15,
                system_prompt_override=build_dalat_system_prompt_v2(tools),
            )
            response_text = agent.run(message)
        else:
            return jsonify({"error": f"Unknown mode: {mode}"}), 400

        elapsed_ms = int((time.time() - start) * 1000)
        metrics = tracker.summarize_session()

        return jsonify(
            {
                "response": response_text,
                "metrics": metrics,
                "mode": mode,
                "elapsed_ms": elapsed_ms,
            }
        )
    except Exception as e:
        traceback.print_exc()
        elapsed_ms = int((time.time() - start) * 1000)
        return jsonify(
            {
                "error": str(e),
                "mode": mode,
                "elapsed_ms": elapsed_ms,
            }
        ), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "provider": os.getenv("DEFAULT_PROVIDER", "openai")})


if __name__ == "__main__":
    print("🚀 Starting web server at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
