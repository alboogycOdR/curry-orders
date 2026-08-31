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


def test_signup_refuses_to_claim_existing_guest_customer_row(db):
    """Task 8 account-takeover guard.

    A guest Customer row (password_hash=NULL) created at checkout by the
    reserve() path must not be silently claimed by anyone who later submits
    a signup form with the same mobile number.  v1 has no OTP verification
    so the only safe response is a "contact us" error.
    """
    # Simulate a guest customer row created at checkout.
    Customer.objects.create(
        full_name="Guest Orderer", mobile_e164="+27821234567", password_hash=None
    )
    response = Client().post(
        "/account/signup/",
        {"name": "Attacker", "mobile": "082 123 4567", "password": "password123"},
    )
    # Must NOT redirect (a 302 would mean a successful login = account claimed).
    assert response.status_code == 200
    # The guest row must still have no password — not taken over.
    customer = Customer.objects.get(mobile_e164="+27821234567")
    assert customer.password_hash is None
    # The error message must mention "contact us" so the real owner knows
    # how to proceed.
    assert b"contact us" in response.content
