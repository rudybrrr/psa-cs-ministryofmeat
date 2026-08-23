import json
import os
from pathlib import Path

import pytest

from backend.app.domain.cargo_safety import SemanticCheckResult, SemanticSafetyCheckInput
from backend.app.services.semantic_safety import OpenAISemanticSafetyChecker


@pytest.mark.skipif(os.getenv("RUN_LIVE_LLM_TESTS") != "1", reason="opt-in live LLM test")
def test_live_hero_contradiction() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for live LLM test")
    fixture = json.loads((Path(__file__).resolve().parents[2] / "shared/fixtures/canonical-dg-contradiction.json").read_text())
    output = OpenAISemanticSafetyChecker().check(SemanticSafetyCheckInput(structured_dangerous_goods=False, structured_un_number=None, structured_commodity="Synthetic dry cargo", note_text=fixture["note"]["text"]))
    assert output.result is SemanticCheckResult.CONTRADICTION_FOUND
