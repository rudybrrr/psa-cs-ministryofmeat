from __future__ import annotations

from time import perf_counter
from typing import Callable, Literal, Sequence

from openai import APITimeoutError, OpenAI, OpenAIError

from backend.app.domain.live_evidence import LiveFailureKind, LiveStage, ProviderCallObservation


class LiveProviderCallCapExceeded(OpenAIError):
    pass


class ProviderCallBudget:
    def __init__(self, max_calls: int = 10) -> None:
        if not 0 < max_calls <= 10:
            raise ValueError("max_calls must be between 1 and 10")
        self.max_calls = max_calls
        self._attempted_calls = 0

    @property
    def attempted_calls(self) -> int:
        return self._attempted_calls

    @property
    def remaining_calls(self) -> int:
        return self.max_calls - self._attempted_calls

    def admit(self, method: Literal["responses.create", "responses.parse"]) -> int:
        if self._attempted_calls >= self.max_calls:
            raise LiveProviderCallCapExceeded("live provider call cap exceeded")
        self._attempted_calls += 1
        return self._attempted_calls


class _InstrumentedResponses:
    def __init__(self, client: InstrumentedOpenAIClient) -> None:
        self._client = client

    def create(self, *args: object, **kwargs: object) -> object:
        return self._client._call("responses.create", *args, **kwargs)

    def parse(self, *args: object, **kwargs: object) -> object:
        return self._client._call("responses.parse", *args, **kwargs)


class InstrumentedOpenAIClient:
    def __init__(
        self,
        client: OpenAI,
        budget: ProviderCallBudget,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._client = client
        self._budget = budget
        self._clock = clock
        self._observations: list[ProviderCallObservation] = []
        self.responses = _InstrumentedResponses(self)

    @classmethod
    def from_api_key(
        cls,
        api_key: str,
        budget: ProviderCallBudget,
        clock: Callable[[], float] = perf_counter,
    ) -> InstrumentedOpenAIClient:
        return cls(OpenAI(api_key=api_key, max_retries=0), budget, clock)

    @property
    def observations(self) -> Sequence[ProviderCallObservation]:
        return tuple(self._observations)

    def _call(
        self,
        method: Literal["responses.create", "responses.parse"],
        *args: object,
        **kwargs: object,
    ) -> object:
        call_number = self._budget.admit(method)
        configured_model = str(kwargs.get("model") or "unknown")
        delegated = getattr(self._client.responses, method.rsplit(".", 1)[1])
        started_at = self._clock()
        try:
            response = delegated(*args, **kwargs)
        except Exception as error:
            finished_at = self._clock()
            self._observations.append(
                ProviderCallObservation(
                    call_number=call_number,
                    stage=_stage_for(method),
                    method=method,
                    configured_model=configured_model,
                    returned_model=None,
                    success=False,
                    failure_kind=_failure_kind(error),
                    latency_ms=_latency_ms(started_at, finished_at),
                    input_tokens=None,
                    output_tokens=None,
                    total_tokens=None,
                    selected_tool=None,
                )
            )
            raise
        finished_at = self._clock()
        usage = getattr(response, "usage", None)
        self._observations.append(
            ProviderCallObservation(
                call_number=call_number,
                stage=_stage_for(method),
                method=method,
                configured_model=configured_model,
                returned_model=_string_or_none(getattr(response, "model", None)),
                success=True,
                failure_kind=None,
                latency_ms=_latency_ms(started_at, finished_at),
                input_tokens=_int_or_none(getattr(usage, "input_tokens", None)),
                output_tokens=_int_or_none(getattr(usage, "output_tokens", None)),
                total_tokens=_int_or_none(getattr(usage, "total_tokens", None)),
                selected_tool=None,
            )
        )
        return response


def _stage_for(method: Literal["responses.create", "responses.parse"]) -> LiveStage:
    return LiveStage.TOOL_SELECTION_SMOKE if method == "responses.create" else LiveStage.SEMANTIC_SAFETY_SMOKE


def _failure_kind(error: Exception) -> LiveFailureKind:
    if isinstance(error, APITimeoutError):
        return LiveFailureKind.PROVIDER_TIMEOUT
    if isinstance(error, OpenAIError):
        return LiveFailureKind.PROVIDER_ERROR
    if isinstance(error, (TypeError, ValueError)):
        return LiveFailureKind.INVALID_OUTPUT
    return LiveFailureKind.UNEXPECTED_FAILURE


def _latency_ms(started_at: float, finished_at: float) -> int:
    return max(0, round((finished_at - started_at) * 1000))


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
