"""
LLM Provider — wraps SAP gen_ai_hub via Amazon Bedrock client.

  from gen_ai_hub.proxy.native.amazon.clients import Session

Required env vars:
  AICORE_AUTH_URL, AICORE_CLIENT_ID, AICORE_CLIENT_SECRET,
  AICORE_RESOURCE_GROUP, AICORE_BASE_URL

Optional:
  MODEL_ID    (default: anthropic--claude-3-5-sonnet)
  TEMPERATURE (default: 0.2)
  MAX_TOKENS  (default: 4096)
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def get_model_id() -> str:
    return os.environ.get("MODEL_ID", "anthropic--claude-3-5-sonnet")


def get_temperature() -> float:
    return float(os.environ.get("TEMPERATURE", "0.2"))


def get_max_tokens() -> int:
    return int(os.environ.get("MAX_TOKENS", "4096"))


def get_client() -> Any:
    from gen_ai_hub.proxy.native.amazon.clients import Session  # type: ignore
    return Session()


def _build_bedrock_tools(tools: list[dict]) -> list[dict]:
    """
    Normalise tool definitions to Bedrock toolSpec format.

    Accepts:
      - Already-Bedrock format:  {"toolSpec": {"name": ..., ...}}
      - OpenAI function format:  {"type": "function", "function": {"name": ..., ...}}
      - Bare function dict:      {"name": ..., "description": ..., "parameters": ...}
    """
    result = []
    for t in tools:
        # Already in Bedrock toolSpec format — pass through
        if "toolSpec" in t:
            result.append(t)
            continue

        # OpenAI / bare function format
        fn = t.get("function", t)
        result.append({
            "toolSpec": {
                "name": fn["name"],
                "description": fn.get("description", ""),
                "inputSchema": {"json": fn.get("parameters", {"type": "object", "properties": {}})},
            }
        })
    return result


def _build_bedrock_messages(messages: list[dict]) -> list[dict]:
    """
    Convert history messages → Bedrock converse API format.

    History message formats:
      User (initial):  {"role": "user", "content": str}
      User (tools):    {"role": "user", "content": [{"toolResult": ...}, ...]}
      Assistant (raw): {"role": "assistant", "content": [...]}  ← raw Bedrock format
      Tool (legacy):   {"role": "tool", "tool_call_id": ..., "content": str}
    """
    bedrock_msgs = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue

        if role == "user":
            content = m.get("content", "")
            if isinstance(content, str):
                # Plain text user message (initial prompt)
                bedrock_msgs.append({"role": "user", "content": [{"text": content}]})
            elif isinstance(content, list):
                # Already in Bedrock format (tool results OR multi-part user msg)
                bedrock_msgs.append({"role": "user", "content": content})
            else:
                bedrock_msgs.append({"role": "user", "content": [{"text": str(content)}]})

        elif role == "assistant":
            content = m.get("content")
            if isinstance(content, list):
                # Raw Bedrock format — pass through as-is
                bedrock_msgs.append({"role": "assistant", "content": content})
            elif "tool_calls" in m:
                # Legacy OpenAI format — reconstruct
                parts = []
                text = content or ""
                if text:
                    parts.append({"text": text})
                for tc in m.get("tool_calls", []):
                    parts.append({
                        "toolUse": {
                            "toolUseId": tc["id"],
                            "name": tc["function"]["name"],
                            "input": json.loads(tc["function"]["arguments"]),
                        }
                    })
                bedrock_msgs.append({"role": "assistant", "content": parts})
            else:
                # Plain text assistant message
                text = content or ""
                if text:
                    bedrock_msgs.append({"role": "assistant", "content": [{"text": text}]})
                # Skip empty assistant messages (Bedrock doesn't allow empty content)

        elif role == "tool":
            # Legacy format — merge consecutive tool messages into one user message
            tool_result_block = {
                "toolResult": {
                    "toolUseId": m["tool_call_id"],
                    "content": [{"text": m.get("content", "")}],
                }
            }
            # If previous message is also a tool-result user message, merge
            if (bedrock_msgs and
                    bedrock_msgs[-1]["role"] == "user" and
                    bedrock_msgs[-1]["content"] and
                    isinstance(bedrock_msgs[-1]["content"][0], dict) and
                    "toolResult" in bedrock_msgs[-1]["content"][0]):
                bedrock_msgs[-1]["content"].append(tool_result_block)
            else:
                bedrock_msgs.append({"role": "user", "content": [tool_result_block]})

    return bedrock_msgs


def chat_with_tools(
    client: Any,
    messages: list[dict],
    tools: list[dict],
    system_prompt: str,
    on_text_delta: Any = None,
    max_retries: int = 3,
) -> dict:
    """
    Call the LLM via gen_ai_hub Bedrock converse API (same as HANA-TEA).

    Returns:
        {
            "stop_reason": "end_turn" | "tool_use",
            "text": "...",
            "tool_calls": [{"id":"..","name":"..","arguments":{..}}, ...]
        }
    """
    bedrock_messages = _build_bedrock_messages(messages)
    bedrock_tools = _build_bedrock_tools(tools) if tools else []
    system_block = [{"text": system_prompt}] if system_prompt else []

    kwargs: dict = {
        "modelId": get_model_id(),
        "messages": bedrock_messages,
        "inferenceConfig": {
            "temperature": get_temperature(),
            "maxTokens": get_max_tokens(),
        },
    }
    if system_block:
        kwargs["system"] = system_block
    if bedrock_tools:
        kwargs["toolConfig"] = {"tools": bedrock_tools}

    base_delay = 5
    bedrock_client = client.client(model_name=get_model_id())

    for attempt in range(max_retries + 1):
        try:
            response = bedrock_client.converse(**kwargs)

            stop_reason = response.get("stopReason", "end_turn")
            output_msg = response.get("output", {}).get("message", {})
            content_blocks = output_msg.get("content", [])

            text_parts = []
            tool_calls = []

            for block in content_blocks:
                if "text" in block:
                    text_parts.append(block["text"])
                if "toolUse" in block:
                    tu = block["toolUse"]
                    tool_calls.append({
                        "id": tu["toolUseId"],
                        "name": tu["name"],
                        "arguments": tu.get("input", {}),
                    })

            text = "".join(text_parts)
            if on_text_delta and text and stop_reason == "end_turn":
                on_text_delta(text)

            return {
                "stop_reason": "tool_use" if tool_calls else "end_turn",
                "text": text,
                "tool_calls": tool_calls,
                "raw_bedrock_message": output_msg,
            }

        except Exception as exc:
            msg_str = str(exc)
            retryable = (
                "ThrottlingException" in msg_str
                or "429" in msg_str
                or "timeout" in msg_str.lower()
                or "ServiceUnavailable" in msg_str
                or "InternalServerError" in msg_str
            )
            if retryable and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"[LLM] Retrying in {delay}s ({msg_str[:80]})")
                time.sleep(delay)
                continue
            raise

    raise RuntimeError("Unexpected exit from retry loop")