import os,sqlite3
from datetime import datetime,timezone
from contextlib import contextmanager
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from fastapi.middleware.cors import CORSMiddleware
DB=os.getenv("DB_PATH","deliveries.db");app=FastAPI(title="Delivery Service",description="Створення та відстеження доставки")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"], allow_methods=["*"], allow_headers=["*"])
@contextmanager
def db():
    os.makedirs(os.path.dirname(DB) or ".",exist_ok=True);c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
    try:yield c;c.commit()
    finally:c.close()
with db() as c:c.execute("CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER UNIQUE NOT NULL,restaurant_id INTEGER NOT NULL,restaurant_name TEXT NOT NULL,address TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL)")
class DeliveryCreate(BaseModel):order_id:int=Field(gt=0);restaurant_id:int=Field(gt=0);restaurant_name:str;address:str=Field(min_length=3,max_length=300)
class StatusUpdate(BaseModel):status:str=Field(pattern="^(preparing|picked_up|on_the_way|delivered|cancelled)$")
class AddressUpdate(BaseModel):address:str=Field(min_length=3,max_length=300)
@app.get("/health")
def health():return {"status":"ok","service":"delivery-service"}
@app.post("/deliveries",status_code=201)
def create(data:DeliveryCreate):
    with db() as c:
        row=c.execute("SELECT * FROM deliveries WHERE order_id=?",(data.order_id,)).fetchone()
        if row:return dict(row)
        created=datetime.now(timezone.utc).isoformat();cur=c.execute("INSERT INTO deliveries(order_id,restaurant_id,restaurant_name,address,status,created_at) VALUES(?,?,?,?,?,?)",(data.order_id,data.restaurant_id,data.restaurant_name,data.address,"preparing",created))
        return {"id":cur.lastrowid,**data.model_dump(),"status":"preparing","created_at":created}
@app.get("/deliveries/{delivery_id}")
def get(delivery_id:int):
    with db() as c:r=c.execute("SELECT * FROM deliveries WHERE id=?",(delivery_id,)).fetchone()
    if r is None:raise HTTPException(404,"Доставку не знайдено")
    return dict(r)
@app.get("/deliveries/order/{order_id}")
def by_order(order_id:int):
    with db() as c:r=c.execute("SELECT * FROM deliveries WHERE order_id=?",(order_id,)).fetchone()
    if r is None:raise HTTPException(404,"Доставку не знайдено")
    return dict(r)
@app.patch("/deliveries/{delivery_id}/status")
def update_status(delivery_id:int,data:StatusUpdate):
    with db() as c:
        cur=c.execute("UPDATE deliveries SET status=? WHERE id=?",(data.status,delivery_id))
        if cur.rowcount==0:raise HTTPException(404,"Доставку не знайдено")
        r=c.execute("SELECT * FROM deliveries WHERE id=?",(delivery_id,)).fetchone()
    return dict(r)
@app.patch("/deliveries/order/{order_id}/status")
def update_status_by_order(order_id:int,data:StatusUpdate):
    with db() as c:
        cur=c.execute("UPDATE deliveries SET status=? WHERE order_id=?",(data.status,order_id))
        if cur.rowcount==0:raise HTTPException(404,"Доставку не знайдено")
        r=c.execute("SELECT * FROM deliveries WHERE order_id=?",(order_id,)).fetchone()
    return dict(r)
@app.patch("/deliveries/order/{order_id}/address")
def update_address_by_order(order_id:int,data:AddressUpdate):
    with db() as c:
        r=c.execute("SELECT * FROM deliveries WHERE order_id=?",(order_id,)).fetchone()
        if r is None:raise HTTPException(404,"Доставку не знайдено")
        if r["status"] in ("delivered","cancelled"):
            raise HTTPException(400,"Неможливо змінити адресу завершеної або скасованої доставки")
        c.execute("UPDATE deliveries SET address=? WHERE order_id=?",(data.address,order_id))
        updated=c.execute("SELECT * FROM deliveries WHERE order_id=?",(order_id,)).fetchone()
    return dict(updated)
