"""Privacy contract for RFC 9457 problem-instance URIs."""


def test_problem_instance_omits_query_values(client):
    """Denied input must not be reflected through the problem instance URI."""
    marker = "USR-999999"
    response = client.get(f"/api/v1/auth/me?staff_ref={marker}")

    assert response.status_code == 401
    assert response.json()["instance"] == "http://testserver/api/v1/auth/me"
    assert marker not in response.text
