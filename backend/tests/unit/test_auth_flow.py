def test_register_login_me(client):
    register_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "founder@example.com", "password": "supersecret123", "full_name": "Founder"},
    )
    assert register_resp.status_code == 201

    login_resp = client.post(
        "/api/v1/auth/login", json={"email": "founder@example.com", "password": "supersecret123"}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "founder@example.com"


def test_wrong_password_rejected(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "second@example.com", "password": "supersecret123"},
    )
    resp = client.post(
        "/api/v1/auth/login", json={"email": "second@example.com", "password": "wrongpass"}
    )
    assert resp.status_code == 401
