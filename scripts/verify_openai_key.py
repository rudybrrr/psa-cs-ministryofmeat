#!/usr/bin/env python3
"""Quick OpenAI API key auth check. Loads .env from repo root if present."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from openai import AuthenticationError, OpenAI, OpenAIError


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your-openai-api-key-here":
        print("FAIL: OPENAI_API_KEY is missing or still set to the placeholder.")
        return 1

    agent_model = os.environ.get("OPENAI_AGENT_MODEL", "(not set)")
    semantic_model = os.environ.get("OPENAI_MODEL", "(not set)")
    print(f"Checking key against OpenAI (agent model: {agent_model}, semantic model: {semantic_model})...")

    try:
        client = OpenAI(api_key=api_key)
        model = os.environ.get("OPENAI_AGENT_MODEL", "gpt-5.6-luna")
        client.responses.create(model=model, input="ping")
    except AuthenticationError:
        print("FAIL: Authentication rejected — key is invalid or revoked.")
        return 1
    except OpenAIError as error:
        if "model" in str(error).lower():
            print(f"FAIL: Key authenticated but model '{agent_model}' is unavailable ({error.__class__.__name__}).")
        else:
            print(f"FAIL: OpenAI request failed ({error.__class__.__name__}).")
        return 1

    print("OK: API key is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
