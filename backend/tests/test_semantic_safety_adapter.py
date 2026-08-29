from types import SimpleNamespace

import pytest

from backend.app.domain.cargo_safety import (
    SemanticCheckFailureKind,
    SemanticCheckResult,
    SemanticSafetyCheckInput,
)
from backend.app.services.semantic_safety import (
    OpenAISemanticSafetyChecker,
    SemanticSafetyCheckerFailure,
)


NOTE_TEXT = "Shipment includes UN 3480 lithium-ion batteries packed separately."


def _input() -> SemanticSafetyCheckInput:
    return SemanticSafetyCheckInput(structured_dangerous_goods=False, structured_un_number=None, structured_commodity="Synthetic dry cargo", note_text=NOTE_TEXT)


def _checker(*, result: SemanticCheckResult = SemanticCheckResult.CONTRADICTION_FOUND, excerpt: str | None = None) -> OpenAISemanticSafetyChecker:
    output = SimpleNamespace(result=result, explanation="Fixture semantic result.", evidence_excerpt=excerpt)
    client = SimpleNamespace(responses=SimpleNamespace(parse=lambda **_: SimpleNamespace(output_parsed=output)))
    return OpenAISemanticSafetyChecker(api_key="test-key", model="test-model", client=client)


def test_missing_openai_key_fails_closed_without_a_client() -> None:
    checker = OpenAISemanticSafetyChecker(api_key="", model="test-model")
    with pytest.raises(SemanticSafetyCheckerFailure) as raised:
        checker.check(_input())
    assert raised.value.kind is SemanticCheckFailureKind.CONFIGURATION_ERROR


def test_exact_verbatim_evidence_excerpt_is_preserved() -> None:
    assert _checker(excerpt="UN 3480").check(_input()).evidence_excerpt == "UN 3480"


def test_non_verbatim_evidence_excerpt_is_normalized_to_none_without_changing_result() -> None:
    output = _checker(excerpt="The shipment includes UN-3480 batteries.").check(_input())
    assert output.result is SemanticCheckResult.CONTRADICTION_FOUND
    assert output.evidence_excerpt is None


@pytest.mark.parametrize("excerpt", ["", "   \t\n  "])
def test_blank_evidence_excerpt_is_normalized_to_none(excerpt: str) -> None:
    assert _checker(excerpt=excerpt).check(_input()).evidence_excerpt is None


def test_missing_parsed_semantic_output_fails_closed() -> None:
    client = SimpleNamespace(responses=SimpleNamespace(parse=lambda **_: SimpleNamespace(output_parsed=None)))
    checker = OpenAISemanticSafetyChecker(api_key="test-key", model="test-model", client=client)
    with pytest.raises(SemanticSafetyCheckerFailure) as raised:
        checker.check(_input())
    assert raised.value.kind is SemanticCheckFailureKind.INVALID_OUTPUT
