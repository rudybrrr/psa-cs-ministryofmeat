from fastapi.testclient import TestClient


def test_carrier_recovery_routes_are_exposed_and_unknown_case_is_404(client: TestClient) -> None:
    routes = {route.path for route in client.app.routes}
    assert {
        "/incidents/{incident_id}/carrier-recovery-cases",
        "/carrier-recovery-cases/{case_id}/request-approval",
        "/carrier-recovery-cases/{case_id}/send",
        "/carrier-recovery-cases/{case_id}/simulate-carrier-response",
        "/carrier-recovery-cases/{case_id}/counter-approval",
        "/carrier-recovery-cases/{case_id}/evaluate-timeout",
        "/incidents/{incident_id}/carrier-recovery-cases",
        "/carrier-recovery-cases/{case_id}",
        "/carrier-recovery-cases/{case_id}/history",
    } <= routes
    response = client.get("/carrier-recovery-cases/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    assert response.status_code == 404
