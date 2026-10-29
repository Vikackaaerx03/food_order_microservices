import os,sqlite3,uuid
from datetime import datetime,timezone
from contextlib import contextmanager
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from fastapi.middleware.cors import CORSMiddleware
DB=os.getenv("DB_PATH","payments.db"); app=FastAPI(title="Payment Service",description="Навчальна імітація онлайн-оплати")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"], allow_methods=["*"], allow_headers=["*"])
@contextmanager
def db():
    os.makedirs(os.path.dirname(DB) or ".",exist_ok=True); c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    try:yield c;c.commit()
    finally:c.close()
with db() as c:c.execute("CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,payment_ref TEXT UNIQUE NOT NULL,order_id INTEGER UNIQUE NOT NULL,user_id INTEGER NOT NULL,amount REAL NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL)")
class PaymentCreate(BaseModel):order_id:int=Field(gt=0);user_id:int=Field(gt=0);amount:float=Field(gt=0)
@app.get("/health")
def health():return {"status":"ok","service":"payment-service"}
@app.post("/payments",status_code=201)
def pay(data:PaymentCreate):
    with db() as c:
        existing=c.execute("SELECT * FROM payments WHERE order_id=?",(data.order_id,)).fetchone()
        if existing:return dict(existing)
        ref=str(uuid.uuid4()); created=datetime.now(timezone.utc).isoformat()
        cur=c.execute("INSERT INTO payments(payment_ref,order_id,user_id,amount,status,created_at) VALUES(?,?,?,?,?,?)",(ref,data.order_id,data.user_id,data.amount,"paid",created))
        return {"id":cur.lastrowid,"payment_ref":ref,"order_id":data.order_id,"user_id":data.user_id,"amount":data.amount,"status":"paid","created_at":created}
@app.get("/payments/order/{order_id}")
def get_payment(order_id:int):
    with db() as c:r=c.execute("SELECT * FROM payments WHERE order_id=?",(order_id,)).fetchone()
    if r is None:raise HTTPException(404,"Платіж не знайдено")
    return dict(r)

@app.get("/payments/user/{user_id}")
def list_user_payments(user_id:int):
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM payments WHERE user_id=? ORDER BY id DESC",(user_id,))]

@app.post("/payments/order/{order_id}/refund")
def refund_payment(order_id:int):
    with db() as c:
        r=c.execute("SELECT * FROM payments WHERE order_id=?",(order_id,)).fetchone()
        if r is None:
            raise HTTPException(404,"Платіж для цього замовлення не знайдено")
        if r["status"] == "refunded":
            return dict(r)
        c.execute("UPDATE payments SET status='refunded' WHERE order_id=?",(order_id,))
        updated=c.execute("SELECT * FROM payments WHERE order_id=?",(order_id,)).fetchone()
        return dict(updated)
