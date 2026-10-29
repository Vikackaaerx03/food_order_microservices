import os, sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

DB=os.getenv("DB_PATH","orders.db")
URLS={"users":os.getenv("USER_URL","http://localhost:8001"),"restaurants":os.getenv("RESTAURANT_URL","http://localhost:8002"),"payments":os.getenv("PAYMENT_URL","http://localhost:8004"),"deliveries":os.getenv("DELIVERY_URL","http://localhost:8005"),"notifications":os.getenv("NOTIFICATION_URL","http://localhost:8006")}
app=FastAPI(title="Order Service",description="Створення замовлень і координація сервісів")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"], allow_methods=["*"], allow_headers=["*"])

@contextmanager
def db():
    os.makedirs(os.path.dirname(DB) or ".",exist_ok=True); con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
    try: yield con; con.commit()
    finally: con.close()
with db() as con:
    con.execute("CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,restaurant_id INTEGER NOT NULL,status TEXT NOT NULL,total REAL NOT NULL,address TEXT NOT NULL,created_at TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER NOT NULL,menu_item_id INTEGER NOT NULL,name TEXT NOT NULL,quantity INTEGER NOT NULL,unit_price REAL NOT NULL,subtotal REAL NOT NULL)")

class OrderItem(BaseModel): menu_item_id:int=Field(gt=0); quantity:int=Field(gt=0,le=50)
class OrderCreate(BaseModel): user_id:int=Field(gt=0); restaurant_id:int=Field(gt=0); address:str=Field(min_length=3,max_length=300); items:list[OrderItem]=Field(min_length=1)
class OrderAddressUpdate(BaseModel): address:str=Field(min_length=3,max_length=300)

async def request_json(client,method,url,**kwargs):
    try: response=await client.request(method,url,**kwargs)
    except httpx.RequestError: raise HTTPException(503,f"Не вдалося зв'язатися із сервісом: {url}")
    if response.status_code>=400:
        try: detail=response.json().get("detail",response.text)
        except ValueError: detail=response.text
        raise HTTPException(response.status_code,detail)
    return response.json()

async def enrich_order(client, order: dict) -> dict:
    order_id = order["id"]
    try:
        r_pay = await client.get(f"{URLS['payments']}/payments/order/{order_id}")
        order["payment"] = r_pay.json() if r_pay.status_code == 200 else None
    except httpx.RequestError:
        order["payment"] = None
    try:
        r_del = await client.get(f"{URLS['deliveries']}/deliveries/order/{order_id}")
        order["delivery"] = r_del.json() if r_del.status_code == 200 else None
    except httpx.RequestError:
        order["delivery"] = None
    return order

def read_order(con,order_id):
    row=con.execute("SELECT * FROM orders WHERE id=?",(order_id,)).fetchone()
    if row is None:return None
    result=dict(row); result["items"]=[dict(i) for i in con.execute("SELECT menu_item_id,name,quantity,unit_price,subtotal FROM order_items WHERE order_id=? ORDER BY id",(order_id,))]
    return result

@app.get("/health")
def health():return {"status":"ok","service":"order-service"}

@app.post("/orders",status_code=201)
async def create_order(data:OrderCreate):
    async with httpx.AsyncClient(timeout=8) as client:
        await request_json(client,"GET",f"{URLS['users']}/users/{data.user_id}")
        restaurant=await request_json(client,"GET",f"{URLS['restaurants']}/restaurants/{data.restaurant_id}")
        resolved=[]
        for requested in data.items:
            item=await request_json(client,"GET",f"{URLS['restaurants']}/menu/{requested.menu_item_id}")
            if item["restaurant_id"]!=data.restaurant_id: raise HTTPException(400,"Страва не належить вибраному ресторану")
            if not item["available"]: raise HTTPException(400,f"Страва «{item['name']}» зараз недоступна")
            resolved.append({"menu_item_id":item["id"],"name":item["name"],"quantity":requested.quantity,"unit_price":item["price"],"subtotal":round(item["price"]*requested.quantity,2)})
        total=round(sum(i["subtotal"] for i in resolved),2)
        with db() as con:
            cur=con.execute("INSERT INTO orders(user_id,restaurant_id,status,total,address,created_at) VALUES(?,?,?,?,?,?)",(data.user_id,data.restaurant_id,"created",total,data.address,datetime.now(timezone.utc).isoformat()))
            order_id=cur.lastrowid
            con.executemany("INSERT INTO order_items(order_id,menu_item_id,name,quantity,unit_price,subtotal) VALUES(?,?,?,?,?,?)",[(order_id,i["menu_item_id"],i["name"],i["quantity"],i["unit_price"],i["subtotal"]) for i in resolved])
        try:
            payment=await request_json(client,"POST",f"{URLS['payments']}/payments",json={"order_id":order_id,"user_id":data.user_id,"amount":total})
            delivery=await request_json(client,"POST",f"{URLS['deliveries']}/deliveries",json={"order_id":order_id,"restaurant_id":data.restaurant_id,"restaurant_name":restaurant["name"],"address":data.address})
            await request_json(client,"POST",f"{URLS['notifications']}/notifications",json={"user_id":data.user_id,"order_id":order_id,"message":f"Замовлення №{order_id} у «{restaurant['name']}» прийнято. Оплачено: {total:.2f} грн."})
        except HTTPException:
            with db() as con: con.execute("UPDATE orders SET status='processing_error' WHERE id=?",(order_id,))
            raise
    with db() as con:
        con.execute("UPDATE orders SET status='accepted' WHERE id=?",(order_id,)); result=read_order(con,order_id)
    result.update({"payment":payment,"delivery":delivery})
    return result

@app.get("/orders/{order_id}")
async def get_order(order_id:int):
    with db() as con: result=read_order(con,order_id)
    if result is None:raise HTTPException(404,"Замовлення не знайдено")
    async with httpx.AsyncClient(timeout=5) as client:
        return await enrich_order(client, result)

@app.get("/users/{user_id}/orders")
async def user_orders(user_id:int):
    with db() as con:
        ids=[r[0] for r in con.execute("SELECT id FROM orders WHERE user_id=? ORDER BY id DESC",(user_id,))]
        orders=[read_order(con,i) for i in ids]
    async with httpx.AsyncClient(timeout=5) as client:
        return [await enrich_order(client, o) for o in orders]

@app.post("/orders/{order_id}/cancel")
async def cancel_order(order_id:int):
    with db() as con:
        order = read_order(con, order_id)
    if order is None:
        raise HTTPException(404, "Замовлення не знайдено")
    async with httpx.AsyncClient(timeout=8) as client:
        if order["status"] == "cancelled":
            return await enrich_order(client, order)
        try:
            delivery = await request_json(client, "GET", f"{URLS['deliveries']}/deliveries/order/{order_id}")
            if delivery.get("status") == "delivered":
                raise HTTPException(400, "Замовлення вже доставлено — скасування неможливе")
        except HTTPException as exc:
            if exc.status_code == 400:
                raise
        payment = await request_json(client, "POST", f"{URLS['payments']}/payments/order/{order_id}/refund")
        delivery = await request_json(client, "PATCH", f"{URLS['deliveries']}/deliveries/order/{order_id}/status", json={"status": "cancelled"})
        with db() as con:
            con.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
            updated = read_order(con, order_id)
        await request_json(
            client,
            "POST",
            f"{URLS['notifications']}/notifications",
            json={
                "user_id": order["user_id"],
                "order_id": order_id,
                "message": f"Замовлення №{order_id} скасовано. Кошти у сумі {order['total']:.2f} грн повернуто на ваш рахунок.",
            },
        )
        updated.update({"payment": payment, "delivery": delivery})
        return updated

@app.patch("/orders/{order_id}/address")
async def update_order_address(order_id:int, data:OrderAddressUpdate):
    with db() as con:
        order = read_order(con, order_id)
    if order is None:
        raise HTTPException(404, "Замовлення не знайдено")
    if order["status"] == "cancelled":
        raise HTTPException(400, "Неможливо змінити адресу скасованого замовлення")
    async with httpx.AsyncClient(timeout=8) as client:
        delivery = await request_json(
            client,
            "PATCH",
            f"{URLS['deliveries']}/deliveries/order/{order_id}/address",
            json={"address": data.address},
        )
        with db() as con:
            con.execute("UPDATE orders SET address=? WHERE id=?", (data.address, order_id))
            updated = read_order(con, order_id)
        await request_json(
            client,
            "POST",
            f"{URLS['notifications']}/notifications",
            json={
                "user_id": order["user_id"],
                "order_id": order_id,
                "message": f"Адресу доставки замовлення №{order_id} змінено на: {data.address}",
            },
        )
        updated = await enrich_order(client, updated)
        updated["delivery"] = delivery
        return updated

@app.delete("/orders/{order_id}")
async def delete_order(order_id:int):
    with db() as con:
        order = read_order(con, order_id)
    if order is None:
        raise HTTPException(404, "Замовлення не знайдено")
    refunded_amount = 0.0
    async with httpx.AsyncClient(timeout=8) as client:
        if order["status"] != "cancelled":
            try:
                await request_json(client, "POST", f"{URLS['payments']}/payments/order/{order_id}/refund")
                refunded_amount = float(order["total"])
            except HTTPException:
                pass
            try:
                await request_json(client, "PATCH", f"{URLS['deliveries']}/deliveries/order/{order_id}/status", json={"status": "cancelled"})
            except HTTPException:
                pass
            try:
                await request_json(
                    client,
                    "POST",
                    f"{URLS['notifications']}/notifications",
                    json={
                        "user_id": order["user_id"],
                        "order_id": order_id,
                        "message": f"Замовлення №{order_id} видалено та відкликано. Кошти у сумі {order['total']:.2f} грн повернуто.",
                    },
                )
            except HTTPException:
                pass
    with db() as con:
        con.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
        con.execute("DELETE FROM orders WHERE id=?", (order_id,))
    return {"status": "deleted", "order_id": order_id, "refunded_amount": refunded_amount}
