from django.test import Client

from core.models import Customer


def test_customer_signup_login_and_logout(db):
    client = Client()
    response = client.post(
        "/account/signup/",
        {"name": "A Customer", "mobile": "082 123 4567", "password": "password123"},
    )
    assert response.status_code == 302
    customer = Customer.objects.get(mobile_e164="+27821234567")
    assert customer.password_hash
    assert client.get("/account/").content.find(b"A Customer") >= 0

    client.get("/account/logout/")
    response = client.post(
        "/account/login/", {"mobile": "082 123 4567", "password": "password123"}
    )
    assert response.status_code == 302
    assert client.get("/account/").content.find(b"A Customer") >= 0


def test_customer_login_rejects_bad_password(db):
    Customer.objects.create(
        full_name="A Customer", mobile_e164="+27821234567", password_hash="not-a-real-hash"
    )
    response = Client().post(
        "/account/login/", {"mobile": "082 123 4567", "password": "wrong-password"}
    )
    assert response.status_code == 200
    assert b"couldn&#x27;t sign you in" in response.content
