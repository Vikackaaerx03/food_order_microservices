import json
import uuid
import urllib.request
import urllib.error
import pytest


def api_call(method, url, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


@pytest.mark.integration
def test_all_services_healthy():
    for port in (8001, 8002, 8003, 8004, 8005, 8006):
        status, data = api_call("GET", f"http://localhost:{port}/health")
        assert status == 200
        assert data["status"] == "ok"


@pytest.mark.integration
def test_order_creation_and_services_coordination():
    uid = uuid.uuid4().hex[:8]
    _, user = api_call(
        "POST",
        "http://localhost:8001/users",
        {"name": f"Тест {uid}", "email": f"test-{uid}@example.com", "phone": "+380501234567"},
    )
    _, restaurants = api_call("GET", "http://localhost:8002/restaurants")
    rest = restaurants[0]
    _, menu = api_call("GET", f"http://localhost:8002/restaurants/{rest['id']}/menu")
    dish = menu[0]

    status, order = api_call(
        "POST",
        "http://localhost:8003/orders",
        {
            "user_id": user["id"],
            "restaurant_id": rest["id"],
            "address": "м. Харків, вул. Сумська, 10",
            "items": [{"menu_item_id": dish["id"], "quantity": 2}],
        },
    )
    assert status == 201
    assert order["status"] == "accepted"
    assert order["payment"]["status"] == "paid"
    assert order["delivery"]["status"] == "preparing"


@pytest.mark.integration
def test_unavailable_dish_rejection():
    uid = uuid.uuid4().hex[:8]
    _, user = api_call(
        "POST",
        "http://localhost:8001/users",
        {"name": f"Тест {uid}", "email": f"test-{uid}@example.com", "phone": "+380501234567"},
    )
    _, restaurants = api_call("GET", "http://localhost:8002/restaurants")
    rest = restaurants[0]
    _, menu = api_call("GET", f"http://localhost:8002/restaurants/{rest['id']}/menu")
    dish = menu[-1]

    api_call("PATCH", f"http://localhost:8002/menu/{dish['id']}/availability", {"available": False})
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            api_call(
                "POST",
                "http://localhost:8003/orders",
                {
                    "user_id": user["id"],
                    "restaurant_id": rest["id"],
                    "address": "м. Харків, вул. Сумська, 10",
                    "items": [{"menu_item_id": dish["id"], "quantity": 1}],
                },
            )
        assert exc.value.code == 400
    finally:
        api_call("PATCH", f"http://localhost:8002/menu/{dish['id']}/availability", {"available": True})


@pytest.mark.integration
def test_order_cancellation_refund_and_idempotency():
    uid = uuid.uuid4().hex[:8]
    _, user = api_call(
        "POST",
        "http://localhost:8001/users",
        {"name": f"Тест {uid}", "email": f"test-{uid}@example.com", "phone": "+380501234567"},
    )
    _, restaurants = api_call("GET", "http://localhost:8002/restaurants")
    rest = restaurants[-1]
    _, menu = api_call("GET", f"http://localhost:8002/restaurants/{rest['id']}/menu")
    dish = menu[0]

    _, order = api_call(
        "POST",
        "http://localhost:8003/orders",
        {
            "user_id": user["id"],
            "restaurant_id": rest["id"],
            "address": "м. Харків, вул. Сумська, 72",
            "items": [{"menu_item_id": dish["id"], "quantity": 1}],
        },
    )
    oid = order["id"]

    status, cancelled = api_call("POST", f"http://localhost:8003/orders/{oid}/cancel")
    assert status == 200
    assert cancelled["status"] == "cancelled"
    assert cancelled["payment"]["status"] == "refunded"
    assert cancelled["delivery"]["status"] == "cancelled"

    # Idempotent repeat cancellation
    status2, cancelled2 = api_call("POST", f"http://localhost:8003/orders/{oid}/cancel")
    assert status2 == 200
    assert cancelled2["status"] == "cancelled"

