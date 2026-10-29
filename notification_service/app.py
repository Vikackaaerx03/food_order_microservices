import os,sqlite3
from datetime import datetime,timezone
from contextlib import contextmanager
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from fastapi.middleware.cors import CORSMiddleware
DB=os.getenv("DB_PATH","notifications.db");app=FastAPI(title="Notification Service",description="Збереження повідомлень про замовлення")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"], allow_methods=["*"], allow_headers=["*"])
@contextmanager
def db():
    os.makedirs(os.path.dirname(DB) or ".",exist_ok=True);c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
    try:yield c;c.commit()
    finally:c.close()
with db() as c:c.execute("CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,order_id INTEGER NOT NULL,message TEXT NOT NULL,channel TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL)")
class NotificationCreate(BaseModel):user_id:int=Field(gt=0);order_id:int=Field(gt=0);message:str=Field(min_length=1,max_length=1000);channel:str="in_app"
@app.get("/health")
def health():return {"status":"ok","service":"notification-service"}
@app.post("/notifications",status_code=201)
def create(data:NotificationCreate):
    created=datetime.now(timezone.utc).isoformat()
    with db() as c:
        cur=c.execute("INSERT INTO notifications(user_id,order_id,message,channel,status,created_at) VALUES(?,?,?,?,?,?)",(data.user_id,data.order_id,data.message,data.channel,"sent",created))
        return {"id":cur.lastrowid,**data.model_dump(),"status":"sent","created_at":created}
@app.get("/notifications/user/{user_id}")
def by_user(user_id:int):
    with db() as c:return [dict(r) for r in c.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC",(user_id,))]
@app.get("/notifications/order/{order_id}")
def by_order(order_id:int):
    with db() as c:return [dict(r) for r in c.execute("SELECT * FROM notifications WHERE order_id=? ORDER BY id DESC",(order_id,))]
