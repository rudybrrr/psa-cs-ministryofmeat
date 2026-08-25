from backend.app.domain.cargo_safety import SemanticCheckResult, SemanticSafetyCheckInput
from backend.app.services.canonical_replay import (
    CANONICAL_SAFETY_NOTE_TEXT,
    CanonicalReplaySemanticChecker,
)


def _input(note: str, *, dangerous_goods: bool = False, commodity: str = "General cargo") -> SemanticSafetyCheckInput:
    return SemanticSafetyCheckInput(
        structured_dangerous_goods=dangerous_goods,
        structured_un_number=None,
        structured_commodity=commodity,
        note_text=note,
    )


def test_checker_identity_is_deterministic_and_credential_free() -> None:
    checker = CanonicalReplaySemanticChecker()
    assert checker.checker_kind == "canonical-replay-deterministic"
    assert checker.model_name is None


def test_canonical_note_produces_contradiction_with_verbatim_excerpt() -> None:
    output = CanonicalReplaySemanticChecker().check(_input(CANONICAL_SAFETY_NOTE_TEXT))
    assert output.result is SemanticCheckResult.CONTRADICTION_FOUND
    assert output.evidence_excerpt in CANONICAL_SAFETY_NOTE_TEXT
    assert "general" in output.explanation.lower()


def test_benign_note_produces_no_contradiction() -> None:
    output = CanonicalReplaySemanticChecker().check(_input("Manifest and handling note agree: dry general cargo, no special handling."))
    assert output.result is SemanticCheckResult.NO_CONTRADICTION_FOUND
    assert output.evidence_excerpt is None


def test_trusted_dg_declaration_is_not_a_contradiction() -> None:
    note = "Handling note flags hazardous material; structured declaration agrees."
    output = CanonicalReplaySemanticChecker().check(_input(note, dangerous_goods=True))
    assert output.result is SemanticCheckResult.NO_CONTRADICTION_FOUND


def test_every_pinned_hazard_token_matches_case_insensitively() -> None:
    checker = CanonicalReplaySemanticChecker()
    samples = [
        "note mentions UN 3480 packing",
        "declared as DANGEROUS GOODS by handler",
        "marked DG on the manifest",
        "flagged Hazardous by sensor",
        "spill risk: corrosive residue",
        "container holds flammable aerosols",
        "declared explosive contents",
        "labelled radioactive material",
        "suspected toxic fumes report",
        "crate contains lithium-ion batteries",
    ]
    for sample in samples:
        assert checker.check(_input(sample)).result is SemanticCheckResult.CONTRADICTION_FOUND, sample


def test_token_matching_respects_word_boundaries() -> None:
    checker = CanonicalReplaySemanticChecker()
    assert checker.check(_input("standard widget parts only")).result is SemanticCheckResult.NO_CONTRADICTION_FOUND
    assert checker.check(_input("uniquely numbered crates")).result is SemanticCheckResult.NO_CONTRADICTION_FOUND


def test_checker_never_classifies_cargo_or_assigns_un_numbers() -> None:
    output = CanonicalReplaySemanticChecker().check(_input(CANONICAL_SAFETY_NOTE_TEXT))
    payload = output.model_dump()
    allowed_keys = {"result", "explanation", "evidence_excerpt"}
    assert set(payload) == allowed_keys
    assert output.result in {SemanticCheckResult.CONTRADICTION_FOUND, SemanticCheckResult.NO_CONTRADICTION_FOUND}
