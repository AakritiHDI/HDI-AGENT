#!/usr/bin/env python3
"""
HANA HDI Agent — CLI entry point.

Usage:
    python main.py                              # interactive chat (will prompt for username)
    python main.py --username AAKRITI           # set username upfront
    python main.py -u AAKRITI --prompt "..."    # single prompt with username, then exit
    python main.py --container MY_CONTAINER     # override default HDI container
"""
from __future__ import annotations

import os
import sys
import threading
import time
import itertools

import click
from dotenv import load_dotenv

load_dotenv()


def _warmup_ai_core() -> None:
    """
    Send a minimal no-op request to SAP AI Core in a background thread
    so the model container is warm before the user types their first message.
    The warm-up runs silently — any error is ignored.
    """
    def _do_warmup() -> None:
        try:
            from agent.llm import get_client, chat_with_tools
            client = get_client()
            chat_with_tools(
                client=client,
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                system_prompt="Reply with one word.",
            )
        except Exception:
            pass  # warm-up failures must never affect the user experience

    t = threading.Thread(target=_do_warmup, daemon=True)
    t.start()


def _banner(username: str = "") -> None:
    print("\n" + "═" * 60)
    print("  🤖  HANA HDI Agent")
    print("  SAP HANA HDI Artifact Creator & Deployer")
    print("  Powered by SAP AI Core (gen_ai_hub)")
    print("═" * 60)
    if username:
        uname = username.upper()
        print(f"  👤  User       : {uname}")
        print(f"  📦  Group      : {uname}_CONTAINER_GROUP")
        print(f"  🗂️   Container  : {uname}_CONTAINER")
        print("═" * 60)
    print("  Describe what you need in plain English.")
    print("  Commands: /reset  /containers  /history  /whoami  /exit")
    print("═" * 60 + "\n")


def _prompt_username() -> str:
    """Interactively ask for the username if not provided via CLI."""
    print("\n" + "─" * 60)
    print("  👤  Username required for HDI resource naming.")
    print("  This is typically your git username (e.g. AAKRITI, SUSHANT).")
    print("─" * 60)
    while True:
        try:
            name = input("  Enter your username: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            raise SystemExit(1)
        if name:
            return name.upper()
        print("  ⚠️  Username cannot be empty. Please try again.")


class _Spinner:
    """
    A simple CLI spinner that shows a "Thinking..." animation while
    the agent waits for a response from SAP AI Core.

    Usage:
        with _Spinner():
            result = agent.chat(...)
    """
    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    _LABEL = "  🤔 Thinking"

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._first_token_received = threading.Event()

    def _spin(self) -> None:
        frames = itertools.cycle(self._FRAMES)
        dots = itertools.cycle(["", ".", "..", "..."])
        tick = 0
        while not self._stop_event.is_set():
            if self._first_token_received.is_set():
                # First token arrived — erase spinner line and stop
                sys.stdout.write("\r" + " " * 30 + "\r")
                sys.stdout.flush()
                return
            frame = next(frames)
            if tick % 4 == 0:
                dot = next(dots)
            sys.stdout.write(f"\r{self._LABEL}{dot} {frame}  ")
            sys.stdout.flush()
            time.sleep(0.1)
            tick += 1
        # Clean up the line when stopped
        sys.stdout.write("\r" + " " * 30 + "\r")
        sys.stdout.flush()

    def on_first_token(self) -> None:
        """Call this when the first token arrives to erase the spinner."""
        self._first_token_received.set()

    def __enter__(self) -> "_Spinner":
        self._stop_event.clear()
        self._first_token_received.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.5)


@click.command()
@click.option("--username", "-u", default=None, help="Your username (e.g. AAKRITI). Used to prefix HDI resources.")
@click.option("--prompt", "-p", default=None, help="Single prompt (non-interactive mode)")
@click.option("--container", "-c", default=None, help="Override default HDI container name")
def cli(username: str | None, prompt: str | None, container: str | None) -> None:
    """HANA HDI Agent — create and deploy HDI artifacts via natural language."""
    from agent.agent import HDIAgent

    # ── Resolve username ──────────────────────────────────────────────────────
    # Priority: --username flag > HDI_USERNAME env var > interactive prompt
    if not username:
        username = os.environ.get("HDI_USERNAME", "").strip().upper()
    if not username:
        username = _prompt_username()
    else:
        username = username.strip().upper()

    agent = HDIAgent(username=username)

    # Override container only if explicitly passed (rare — username-derived name is default)
    if container:
        agent.history.append({
            "role": "user",
            "content": [{"text": f"My HDI container is: {container}"}],
        })
        agent.history.append({
            "role": "assistant",
            "content": [{"text": f"Understood. I will use '{container}' as the HDI container."}],
        })

    # ── Non-interactive single prompt mode ────────────────────────────────────
    if prompt:
        try:
            print(agent.chat(prompt))
        finally:
            agent.close()
        return

    # ── Interactive mode ──────────────────────────────────────────────────────
    # Warm up AI Core in background while user reads the banner
    _warmup_ai_core()

    _banner(username)
    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                print("Goodbye!")
                break

            elif user_input.lower() == "/reset":
                agent.reset()
                print("[Conversation reset]\n")
                continue

            elif user_input.lower() == "/whoami":
                uname = agent.username or "(not set)"
                print(f"\n  User      : {uname}")
                print(f"  Group     : {uname}_CONTAINER_GROUP")
                print(f"  Container : {uname}_CONTAINER\n")
                continue

            elif user_input.lower() == "/history":
                for i, m in enumerate(agent.history):
                    role = m.get("role", "?")
                    content = m.get("content", [])
                    text = ""
                    if isinstance(content, list):
                        text = " ".join(
                            b.get("text", "") for b in content if isinstance(b, dict) and "text" in b
                        )
                    elif isinstance(content, str):
                        text = content
                    print(f"  [{i}] {role}: {text[:120]}")
                print()
                continue

            elif user_input.lower() == "/containers":
                user_input = "List all HDI containers available to me."

            print("\nAgent: ", end="", flush=True)
            try:
                # Start spinner — it will erase itself when first token arrives
                with _Spinner() as spinner:
                    first_token = [True]

                    def on_delta(t: str) -> None:
                        if first_token[0]:
                            spinner.on_first_token()
                            first_token[0] = False
                        print(t, end="", flush=True)

                    answer = agent.chat(user_input, on_text_delta=on_delta)

                # If on_text_delta was never called (no streaming tokens), print the full answer
                if first_token[0]:
                    print(answer, end="", flush=True)

                print()
            except Exception as exc:
                print(f"\n[ERROR] {exc}")
            print()

    finally:
        agent.close()


if __name__ == "__main__":
    cli()