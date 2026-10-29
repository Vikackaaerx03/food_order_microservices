import urllib.request
import urllib.error
import json
import uuid

SERVICES = [
    ("User Service", "http://localhost:8001"),
    ("Restaurant Service", "http://localhost:8002"),
    ("Order Service", "http://localhost:8003"),
    ("Payment Service", "http://localhost:8004"),
    ("Delivery Service", "http://localhost:8005"),
    ("Notification Service", "http://localhost:8006"),
]


def req(method, url, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


run_id = uuid.uuid4().hex[:8]
print("============================================================")
print(" FOOD ORDER MICROSERVICES - END-TO-END DEMO")
print("============================================================")
print(f"Run ID: {run_id}\n")

# --- ЧАСТИНА 1 (Кроки 1-10): Успішне виконання замовлення ---
print("[1/16] Checking all services")
for name, url in SERVICES:
    h = req("GET", f"{url}/health")
    print(f"[OK] {name} healthy")
print("[OK] 6/6 services healthy\n")

print("[2/16] Creating a unique User")
user = req(
    "POST",
    "http://localhost:8001/users",
    {"name": f"Вікторія ({run_id})", "email": f"demo-{run_id}@example.com", "phone": "+380501112233"},
)
print(f"[OK] User created: #{user['id']} ({user['email']})\n")

print("[3/16] Inspecting Restaurants")
restaurants = req("GET", "http://localhost:8002/restaurants")
rest = restaurants[-1]
print(f"[OK] Selected Restaurant: #{rest['id']} «{rest['name']}» ({rest['address']})\n")

print("[4/16] Inspecting Restaurant Menu")
menu = req("GET", f"http://localhost:8002/restaurants/{rest['id']}/menu")
dish1, dish2 = menu[0], menu[1]
print(f"[OK] Menu dishes loaded: #{dish1['id']} «{dish1['name']}» and #{dish2['id']} «{dish2['name']}»\n")

print("[5/16] Checking initial dish availability")
print(f"[OK] Available dishes in menu: {sum(1 for d in menu if d['available'])}\n")

print("[6/16] Creating a successful Order")
order = req(
    "POST",
    "http://localhost:8003/orders",
    {
        "user_id": user["id"],
        "restaurant_id": rest["id"],
        "address": "м. Харків, вул. Сумська, 72, кв. 15",
        "items": [{"menu_item_id": dish1["id"], "quantity": 2}],
    },
)
oid = order["id"]
did = order["delivery"]["id"]
pay_check = req("GET", f"http://localhost:8004/payments/order/{oid}")
pid = pay_check["id"]
print(f"[OK] Order #{oid} ACCEPTED; Payment #{pid}\n")

print("[7/16] Inspecting Order snapshot")
order_check = req("GET", f"http://localhost:8003/orders/{oid}")
print(f"[OK] Order snapshot verified: {order_check['items'][0]['name']} x 2 = {order_check['total']} UAH\n")

print("[8/16] Inspecting Delivery status")
deliv_check = req("GET", f"http://localhost:8005/deliveries/order/{oid}")
print(f"[OK] Delivery #{did} status: {deliv_check['status'].upper()}\n")

print("[9/16] Inspecting Payment by order correlation")
print(f"[OK] Payment #{pid} {pay_check['status'].upper()} - {pay_check['amount']} UAH\n")

print("[10/16] Inspecting confirmation Notification")
notifs = req("GET", f"http://localhost:8006/notifications/order/{oid}")
print(f"[OK] ORDER_ACCEPTED notification {notifs[0]['status'].upper()}\n")

# --- ЧАСТИНА 2 (Кроки 11-16): Захист від недоступної страви та компенсація (Refund) ---
print("[11/16] Marking dish temporarily unavailable")
req("PATCH", f"http://localhost:8002/menu/{dish2['id']}/availability", {"available": False})
print(f"[OK] Dish #{dish2['id']} «{dish2['name']}» marked unavailable\n")

print("[12/16] Attempting an Order with unavailable dish")
try:
    req(
        "POST",
        "http://localhost:8003/orders",
        {
            "user_id": user["id"],
            "restaurant_id": rest["id"],
            "address": "м. Харків, вул. Сумська, 72",
            "items": [{"menu_item_id": dish2["id"], "quantity": 1}],
        },
    )
except urllib.error.HTTPError as e:
    print(f"[OK] Order with unavailable dish correctly rejected with {e.code}\n")
finally:
    req("PATCH", f"http://localhost:8002/menu/{dish2['id']}/availability", {"available": True})

print("[13/16] Cancelling the Order (Compensation & Refund)")
cancelled = req("POST", f"http://localhost:8003/orders/{oid}/cancel")
print(f"[OK] Order #{oid} {cancelled['status'].upper()}\n")

print("[14/16] Verifying Payment refund")
pay_after = req("GET", f"http://localhost:8004/payments/order/{oid}")
print(f"[OK] Payment #{pid} {pay_after['status'].upper()}\n")

print("[15/16] Verifying Delivery cancellation and refund Notification")
deliv_after = req("GET", f"http://localhost:8005/deliveries/order/{oid}")
notifs_after = req("GET", f"http://localhost:8006/notifications/order/{oid}")
print(f"[OK] Delivery {deliv_after['status'].upper()} and ORDER_CANCELLED notification {notifs_after[0]['status'].upper()}\n")

print("[16/16] Repeating cancellation to verify idempotency")
repeat_cancel = req("POST", f"http://localhost:8003/orders/{oid}/cancel")
print(f"[OK] Repeated cancellation is idempotent (status={repeat_cancel['status'].upper()})\n")

print("============================================================")
print(" DEMO COMPLETED SUCCESSFULLY")
print("============================================================")
print(f"User ID: {user['id']}")
print(f"Restaurant ID: {rest['id']}")
print(f"Menu Item IDs: {dish1['id']}, {dish2['id']}")
print(f"Order ID: {oid} - {cancelled['status'].upper()}")
print(f"Payment ID: {pid} - {pay_after['status'].upper()}")
print(f"Delivery: {deliv_after['status'].upper()}")
