from datetime import UTC, datetime
from uuid import UUID


def test_prepare_command_uses_trusted_fixture_timing_not_model_arguments() -> None:
    from backend.app.orchestration.agent_runtime import CanonicalAgentRuntimeConfiguration

    command = CanonicalAgentRuntimeConfiguration.load().prepare_command(UUID(int=1), "JV2")
    assert command.incident_id == UUID(int=1)
    assert command.connection_id == "SYN-CONN-JV2"
    assert command.requested_eta_pta.tzinfo is UTC
    assert command.response_deadline > command.prepared_at


def test_fixed_clock_is_injectable() -> None:
    from backend.app.orchestration.agent_runtime import FixedAgentRuntimeClock

    now = datetime(2026, 8, 23, tzinfo=UTC)
    assert FixedAgentRuntimeClock(now).now() == now
