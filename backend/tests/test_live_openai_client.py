from collections import deque
from types import SimpleNamespace

import pytest

from backend.app.evaluation.live_openai_client import (
    InstrumentedOpenAIClient,
    LiveProviderCallCapExceeded,
    ProviderCallBudget,
)


class FakeResponses:
    def __init__(self, responses: list[object]) -> None:
        self.responses = deque(responses)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(("responses.create", kwargs))
        return self.responses.popleft()

    def parse(self, **kwargs: object) -> object:
        self.calls.append(("responses.parse", kwargs))
        return self.responses.popleft()


class FakeSDK:
    def __init__(self, responses: list[object]) -> None:
        self.responses = FakeResponses(responses)


class FakeClock:
    def __init__(self) -> None:
        self.values = deque([1.0, 1.012] * 10)

    def __call__(self) -> float:
        return self.values.popleft()


def sdk_response() -> object:
    return SimpleNamespace(
        model="gpt-test",
        usage=SimpleNamespace(input_tokens=3, output_tokens=5, total_tokens=8),
    )


def test_create_and_parse_share_ten_call_budget() -> None:
    sdk = FakeSDK([sdk_response() for _ in range(10)])
    client = InstrumentedOpenAIClient(sdk, ProviderCallBudget(10), clock=FakeClock())

    for _ in range(5):
        client.responses.create(model="gpt-test")
    for _ in range(5):
        client.responses.parse(model="gpt-test")

    with pytest.raises(LiveProviderCallCapExceeded):
        client.responses.create(model="gpt-test")

    assert len(sdk.responses.calls) == 10


def test_response_identity_usage_and_redaction() -> None:
    response = sdk_response()
    sdk = FakeSDK([response])
    client = InstrumentedOpenAIClient(sdk, ProviderCallBudget(), clock=FakeClock())

    assert client.responses.create(input="secret", model="gpt-test") is response
    assert client.observations[0].input_tokens == 3
    assert "secret" not in client.observations[0].model_dump_json()
