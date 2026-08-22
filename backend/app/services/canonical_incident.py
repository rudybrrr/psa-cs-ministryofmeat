import json
from pathlib import Path

from backend.app.domain.scarcity import CanonicalIncidentFixture


DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "shared"
    / "fixtures"
    / "canonical-24-container.json"
)


class SyntheticCanonicalIncidentService:
    def __init__(self, fixture_path: Path = DEFAULT_FIXTURE_PATH) -> None:
        self._fixture_path = fixture_path

    def load(self) -> CanonicalIncidentFixture:
        data = json.loads(self._fixture_path.read_text(encoding="utf-8"))
        return CanonicalIncidentFixture.model_validate(data)
