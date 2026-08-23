import pytest

from backend.app.domain.cargo_safety import (
    SemanticCheckFailureKind,
    SemanticSafetyCheckInput,
)
from backend.app.services.semantic_safety import (
    OpenAISemanticSafetyChecker,
    SemanticSafetyCheckerFailure,
)


def test_missing_openai_key_fails_closed_without_a_client() -> None:
    checker = OpenAISemanticSafetyChecker(api_key="", model="test-model")
    with pytest.raises(SemanticSafetyCheckerFailure) as raised:
        checker.check(SemanticSafetyCheckInput(structured_dangerous_goods=False, structured_un_number=None, structured_commodity="Synthetic dry cargo", note_text="Shipment includes UN 3480 lithium-ion batteries packed separately."))
    assert raised.value.kind is SemanticCheckFailureKind.CONFIGURATION_ERROR
