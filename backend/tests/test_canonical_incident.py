import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.domain.scarcity import (
    CanonicalIncidentFixture,
    CargoKind,
    ContainerRecoveryProfile,
)
from backend.app.services.canonical_incident import (
    DEFAULT_FIXTURE_PATH,
    SyntheticCanonicalIncidentService,
)


EXPECTED_ROWS = {
    "SYN-CNT-001": ("SF1", CargoKind.DRY, "SYN-A-EQ1", 2, True, True),
    "SYN-CNT-002": ("SF1", CargoKind.REEFER, "SYN-A-EQ1", 4, True, True),
    "SYN-CNT-003": ("SF1", CargoKind.DRY, "SYN-B-EQ2", 6, True, True),
    "SYN-CNT-004": ("SF1", CargoKind.DG, "SYN-B-EQ2", 14, True, True),
    "SYN-CNT-005": ("SF1", CargoKind.DRY, "SYN-A-EQ1", 24, True, True),
    "SYN-CNT-006": ("SF1", CargoKind.REEFER, "SYN-C-EQ3", 26, True, True),
    "SYN-CNT-007": ("SF1", CargoKind.DRY, "SYN-C-EQ3", 28, True, True),
    "SYN-CNT-008": ("SF1", CargoKind.DRY, "SYN-A-EQ1", -20, True, True),
    "SYN-CNT-009": ("SF1", CargoKind.DG, "SYN-B-EQ2", 45, True, False),
    "SYN-CNT-010": ("JV2", CargoKind.DRY, "SYN-A-EQ1", 8, True, True),
    "SYN-CNT-011": ("JV2", CargoKind.REEFER, "SYN-A-EQ1", 10, True, True),
    "SYN-CNT-012": ("JV2", CargoKind.DRY, "SYN-B-EQ2", 12, True, True),
    "SYN-CNT-013": ("JV2", CargoKind.DG, "SYN-B-EQ2", 16, True, True),
    "SYN-CNT-014": ("JV2", CargoKind.DRY, "SYN-C-EQ3", 18, True, True),
    "SYN-CNT-015": ("JV2", CargoKind.REEFER, "SYN-C-EQ3", 20, True, True),
    "SYN-CNT-016": ("JV2", CargoKind.DRY, "SYN-A-EQ1", -18, True, True),
    "SYN-CNT-017": ("JV2", CargoKind.DRY, "SYN-B-EQ2", 45, True, True),
    "SYN-CNT-018": ("EC3", CargoKind.DRY, "SYN-A-EQ1", -25, True, True),
    "SYN-CNT-019": ("EC3", CargoKind.REEFER, "SYN-B-EQ2", -20, True, True),
    "SYN-CNT-020": ("EC3", CargoKind.DRY, "SYN-C-EQ3", -15, True, True),
    "SYN-CNT-021": ("EC3", CargoKind.DRY, "SYN-A-EQ1", 45, True, True),
    "SYN-CNT-022": ("EC3", CargoKind.DG, "SYN-B-EQ2", 50, True, False),
    "SYN-CNT-023": ("EC3", CargoKind.REEFER, "SYN-C-EQ3", 55, False, True),
    "SYN-CNT-024": ("EC3", CargoKind.DRY, "SYN-A-EQ1", 60, True, True),
}

EXPECTED_SERVICE_WINDOWS = {
    "SF1": {
        "pta": datetime(2026, 8, 22, 5, 0, tzinfo=UTC),
        "boundary": datetime(2026, 8, 22, 5, 35, tzinfo=UTC),
        "connection_id": "SYN-CONN-SF1",
        "vessel": "M/V Synthetic Feeder One",
        "voyage": "SYN-SF1-0822",
        "destination": "MYPKG",
        "departure": datetime(2026, 8, 22, 6, 30, tzinfo=UTC),
    },
    "JV2": {
        "pta": datetime(2026, 8, 22, 5, 20, tzinfo=UTC),
        "boundary": datetime(2026, 8, 22, 5, 55, tzinfo=UTC),
        "connection_id": "SYN-CONN-JV2",
        "vessel": "M/V Synthetic Java Venture",
        "voyage": "SYN-JV2-0822",
        "destination": "IDJKT",
        "departure": datetime(2026, 8, 22, 7, 0, tzinfo=UTC),
    },
    "EC3": {
        "pta": datetime(2026, 8, 22, 7, 0, tzinfo=UTC),
        "boundary": datetime(2026, 8, 22, 7, 35, tzinfo=UTC),
        "connection_id": "SYN-CONN-EC3",
        "vessel": "M/V Synthetic Eastern Connector",
        "voyage": "SYN-EC3-0822",
        "destination": "CNSHA",
        "departure": datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
    },
}


def services_by_id(fixture: CanonicalIncidentFixture):
    return {service.service_id: service for service in fixture.services}


def is_structurally_eligible(profile: ContainerRecoveryProfile) -> bool:
    reefer_is_safe = (
        profile.cargo_kind is not CargoKind.REEFER
        or profile.reefer_continuity_available
    )
    dg_is_safe = (
        profile.cargo_kind is not CargoKind.DG or profile.dg_structurally_cleared
    )
    return reefer_is_safe and dg_is_safe


def normal_transfer_preserves(
    profile: ContainerRecoveryProfile,
    fixture: CanonicalIncidentFixture,
) -> bool:
    boundary = services_by_id(fixture)[profile.service_id].ready_boundary
    return is_structurally_eligible(profile) and profile.base_ready_at <= boundary


def expedited_transfer_preserves(
    profile: ContainerRecoveryProfile,
    fixture: CanonicalIncidentFixture,
) -> bool:
    boundary = services_by_id(fixture)[profile.service_id].ready_boundary
    expedited_ready_at = profile.base_ready_at - timedelta(
        minutes=profile.expedite_minutes_saved
    )
    return is_structurally_eligible(profile) and expedited_ready_at <= boundary


def test_canonical_fixture_has_the_approved_identity_and_shape(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    fixture = canonical_fixture

    assert fixture.fixture_id == "SYN-CANONICAL-24-V1"
    assert fixture.event.id == "SYN-EVT-ASX17-20260822-001"
    assert fixture.event.vessel_call_id == "SYN-ASX17-TUAS-001"
    assert fixture.event.vessel_name == "M/V Synthetic Meridian"
    assert fixture.event.terminal_id == "SYN-TUAS-TERMINAL"
    assert fixture.event.scheduled_arrival == datetime(
        2026, 8, 22, 1, 0, tzinfo=UTC
    )
    assert fixture.event.estimated_arrival == datetime(
        2026, 8, 22, 4, 15, tzinfo=UTC
    )
    assert fixture.event.delay_minutes == 195
    assert (
        fixture.event.estimated_arrival - fixture.event.scheduled_arrival
        == timedelta(minutes=195)
    )
    assert [service.service_id for service in fixture.services] == [
        "SF1",
        "JV2",
        "EC3",
    ]
    assert len(fixture.profiles) == 24
    assert [profile.container.id for profile in fixture.profiles] == list(
        EXPECTED_ROWS
    )
    assert len({profile.container.id for profile in fixture.profiles}) == 24


def test_canonical_fixture_matches_every_approved_table_row(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    services = services_by_id(canonical_fixture)

    for profile in canonical_fixture.profiles:
        (
            expected_service,
            expected_cargo,
            expected_group,
            expected_offset,
            expected_reefer_continuity,
            expected_dg_clearance,
        ) = EXPECTED_ROWS[profile.container.id]
        observed_offset = int(
            (
                profile.base_ready_at
                - services[profile.service_id].ready_boundary
            ).total_seconds()
            / 60
        )

        assert profile.service_id == expected_service
        assert profile.cargo_kind is expected_cargo
        assert profile.handling_group_id == expected_group
        assert observed_offset == expected_offset
        assert profile.expedite_minutes_saved == 30
        assert profile.reefer_continuity_available is expected_reefer_continuity
        assert profile.dg_structurally_cleared is expected_dg_clearance


def test_canonical_fixture_has_exact_service_and_cargo_distributions(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    assert Counter(profile.service_id for profile in canonical_fixture.profiles) == {
        "SF1": 9,
        "JV2": 8,
        "EC3": 7,
    }
    assert Counter(profile.cargo_kind for profile in canonical_fixture.profiles) == {
        CargoKind.DRY: 14,
        CargoKind.REEFER: 6,
        CargoKind.DG: 4,
    }


def test_service_windows_and_connections_match_exact_utc_values(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    for service in canonical_fixture.services:
        expected = EXPECTED_SERVICE_WINDOWS[service.service_id]
        connection = service.connection

        assert service.planned_time_of_arrival == expected["pta"]
        assert service.ready_boundary == expected["boundary"]
        assert service.ready_boundary - service.planned_time_of_arrival == timedelta(
            minutes=35
        )
        assert connection.id == expected["connection_id"]
        assert connection.outbound_vessel_name == expected["vessel"]
        assert connection.outbound_voyage == expected["voyage"]
        assert connection.destination_port == expected["destination"]
        assert connection.cutoff_at == service.ready_boundary
        assert connection.departure_at == expected["departure"]
        assert connection.minimum_transfer_minutes == 90
        assert connection.expedited_transfer_minutes == 60


def test_profile_connections_and_cargo_are_structurally_consistent(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    services = services_by_id(canonical_fixture)

    for profile in canonical_fixture.profiles:
        service = services[profile.service_id]
        container = profile.container
        numeric_suffix = int(container.id.rsplit("-", maxsplit=1)[1])

        assert container.origin_port == "NLRTM"
        assert container.destination_port == service.connection.destination_port
        assert container.inbound_vessel_call_id == "SYN-ASX17-TUAS-001"
        assert container.onward_connection == service.connection
        assert container.cargo.gross_weight_kg == 12_000 + 100 * numeric_suffix
        assert (profile.cargo_kind is CargoKind.DG) is container.cargo.dangerous_goods
        if profile.cargo_kind is CargoKind.DG:
            assert container.cargo.commodity == "Synthetic declared DG cargo"
            assert container.cargo.un_number == "UN1993"
        elif profile.cargo_kind is CargoKind.REEFER:
            assert container.cargo.commodity == "Synthetic chilled cargo"
            assert container.cargo.un_number is None
        else:
            assert container.cargo.commodity == "Synthetic dry cargo"
            assert container.cargo.un_number is None


def test_capacity_is_eight_slots_with_approved_hard_limits(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    capacity = canonical_fixture.capacity

    assert capacity.id == "SYN-CAPACITY-SF1-JV2-V1"
    assert capacity.terminal_id == "SYN-TUAS-TERMINAL"
    assert capacity.window_start == datetime(2026, 8, 22, 5, 0, tzinfo=UTC)
    assert capacity.window_end == datetime(2026, 8, 22, 5, 55, tzinfo=UTC)
    assert capacity.overlap_service_ids == ("SF1", "JV2")
    assert capacity.total_slots == 8
    assert {
        limit.handling_group_id: limit.slots
        for limit in capacity.handling_group_limits
    } == {
        "SYN-A-EQ1": 4,
        "SYN-B-EQ2": 3,
        "SYN-C-EQ3": 3,
    }
    assert capacity.max_reefer_slots == 3
    assert capacity.max_dg_slots == 1


def test_thirteen_beneficiaries_are_derived_from_times_and_safety(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    beneficiaries = tuple(
        profile
        for profile in canonical_fixture.profiles
        if not normal_transfer_preserves(profile, canonical_fixture)
        and expedited_transfer_preserves(profile, canonical_fixture)
    )

    assert tuple(profile.container.id for profile in beneficiaries) == (
        "SYN-CNT-001",
        "SYN-CNT-002",
        "SYN-CNT-003",
        "SYN-CNT-004",
        "SYN-CNT-005",
        "SYN-CNT-006",
        "SYN-CNT-007",
        "SYN-CNT-010",
        "SYN-CNT-011",
        "SYN-CNT-012",
        "SYN-CNT-013",
        "SYN-CNT-014",
        "SYN-CNT-015",
    )
    assert Counter(profile.service_id for profile in beneficiaries) == {
        "SF1": 7,
        "JV2": 6,
    }
    assert "beneficiary" not in ContainerRecoveryProfile.model_fields
    assert canonical_fixture.capacity.total_slots == 8


def test_five_containers_need_no_expedition(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    no_expedition = tuple(
        profile.container.id
        for profile in canonical_fixture.profiles
        if normal_transfer_preserves(profile, canonical_fixture)
    )

    assert no_expedition == (
        "SYN-CNT-008",
        "SYN-CNT-016",
        "SYN-CNT-018",
        "SYN-CNT-019",
        "SYN-CNT-020",
    )


def test_six_containers_cannot_be_preserved_by_expedition_alone(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    cannot_be_preserved = tuple(
        profile.container.id
        for profile in canonical_fixture.profiles
        if not normal_transfer_preserves(profile, canonical_fixture)
        and not expedited_transfer_preserves(profile, canonical_fixture)
    )

    assert cannot_be_preserved == (
        "SYN-CNT-009",
        "SYN-CNT-017",
        "SYN-CNT-021",
        "SYN-CNT-022",
        "SYN-CNT-023",
        "SYN-CNT-024",
    )


def test_computed_classifications_partition_all_24_containers(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    normal = {
        profile.container.id
        for profile in canonical_fixture.profiles
        if normal_transfer_preserves(profile, canonical_fixture)
    }
    expedited = {
        profile.container.id
        for profile in canonical_fixture.profiles
        if not normal_transfer_preserves(profile, canonical_fixture)
        and expedited_transfer_preserves(profile, canonical_fixture)
    }
    not_preserved = {
        profile.container.id
        for profile in canonical_fixture.profiles
        if not normal_transfer_preserves(profile, canonical_fixture)
        and not expedited_transfer_preserves(profile, canonical_fixture)
    }

    assert normal.isdisjoint(expedited)
    assert normal.isdisjoint(not_preserved)
    assert expedited.isdisjoint(not_preserved)
    assert normal | expedited | not_preserved == set(EXPECTED_ROWS)


def test_structural_safety_flags_match_the_approved_fixture(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    uncleared_dg = {
        profile.container.id
        for profile in canonical_fixture.profiles
        if profile.cargo_kind is CargoKind.DG
        and not profile.dg_structurally_cleared
    }
    reefers_without_continuity = {
        profile.container.id
        for profile in canonical_fixture.profiles
        if profile.cargo_kind is CargoKind.REEFER
        and not profile.reefer_continuity_available
    }

    assert uncleared_dg == {"SYN-CNT-009", "SYN-CNT-022"}
    assert reefers_without_continuity == {"SYN-CNT-023"}


def test_all_operational_fixture_values_are_clearly_synthetic_and_tuas_based(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    serialized = canonical_fixture.model_dump_json().upper()

    assert "PASIR" not in serialized
    assert "PANJANG" not in serialized
    assert canonical_fixture.fixture_id.startswith("SYN-")
    assert canonical_fixture.event.id.startswith("SYN-")
    assert canonical_fixture.event.vessel_call_id.startswith("SYN-")
    assert canonical_fixture.event.vessel_name.startswith("M/V Synthetic")
    assert canonical_fixture.capacity.id.startswith("SYN-")
    for service in canonical_fixture.services:
        assert service.connection.id.startswith("SYN-")
        assert service.connection.outbound_vessel_name.startswith("M/V Synthetic")
        assert service.connection.outbound_voyage.startswith("SYN-")
    for profile in canonical_fixture.profiles:
        assert profile.container.id.startswith("SYN-CNT-")
        assert profile.container.cargo.commodity.startswith("Synthetic")
        assert profile.handling_group_id.startswith("SYN-")


def test_loader_reads_a_custom_fixture_without_modifying_it(tmp_path: Path) -> None:
    fixture_path = tmp_path / "canonical.json"
    fixture_path.write_bytes(DEFAULT_FIXTURE_PATH.read_bytes())
    before = fixture_path.read_bytes()

    loaded = SyntheticCanonicalIncidentService(fixture_path).load()

    assert loaded.fixture_id == "SYN-CANONICAL-24-V1"
    assert fixture_path.read_bytes() == before


def test_loader_validates_json_through_the_frozen_contract(tmp_path: Path) -> None:
    data = json.loads(DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8"))
    data["profiles"][0]["beneficiary"] = True
    invalid_path = tmp_path / "invalid-canonical.json"
    invalid_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValidationError, match="beneficiary"):
        SyntheticCanonicalIncidentService(invalid_path).load()
