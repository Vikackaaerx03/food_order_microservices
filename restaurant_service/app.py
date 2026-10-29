import os, sqlite3
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

DB = os.getenv("DB_PATH", "restaurants.db")
app = FastAPI(title="Restaurant Service", description="Ресторани та їхнє меню")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"], allow_methods=["*"], allow_headers=["*"])

@contextmanager
def db():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
    try: yield con; con.commit()
    finally: con.close()

with db() as con:
    con.execute("CREATE TABLE IF NOT EXISTS restaurants(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,address TEXT NOT NULL,description TEXT NOT NULL DEFAULT '')")
    con.execute("CREATE TABLE IF NOT EXISTS menu_items(id INTEGER PRIMARY KEY AUTOINCREMENT,restaurant_id INTEGER NOT NULL,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',price REAL NOT NULL CHECK(price>0),available INTEGER NOT NULL DEFAULT 1,FOREIGN KEY(restaurant_id) REFERENCES restaurants(id))")

    # Початкове наповнення ресторанів і страв (українською мовою)
    first_rest = con.execute("SELECT id FROM restaurants ORDER BY id LIMIT 1").fetchone()
    if first_rest is None:
        cur = con.execute(
            "INSERT INTO restaurants(name,address,description) VALUES(?,?,?)",
            ("Смачна кухня", "Київ, вул. Хрещатик, 1", "Домашні українські обіди, піца з печі та фірмові десерти"),
        )
        first_rest_id = cur.lastrowid
    else:
        first_rest_id = first_rest["id"]

    first_menu = [
        ("Піца Маргарита", "Томатний соус пелаті, тягуча моцарела, свіжий базилік та оливкова олія", 245.0),
        ("Борщ український з пампушками", "Наваристий червоний борщ зі сметаною, зеленню, салом та часниковими пампушками", 185.0),
        ("Котлета по-київськи з трюфельним пюре", "Соковите куряче філе з вершковим маслом і зеленню на подушці з ніжного картопляного пюре", 260.0),
        ("Піца Чотири сири", "Моцарела, дорблю, пармезан і чеддер на тонкому тісті з вершковим соусом", 295.0),
        ("Сирники з фермерського сиру", "Пухкі домашні сирники з ягідним кюлі та густою сметаною", 165.0),
    ]
    for name, desc, price in first_menu:
        exists = con.execute("SELECT 1 FROM menu_items WHERE restaurant_id=? AND name=?", (first_rest_id, name)).fetchone()
        if not exists:
            con.execute(
                "INSERT INTO menu_items(restaurant_id,name,description,price) VALUES(?,?,?,?)",
                (first_rest_id, name, desc, price),
            )

    asian_rest = con.execute("SELECT id FROM restaurants WHERE name LIKE '%Sakura%'").fetchone()
    if asian_rest is None:
        cur = con.execute(
            "INSERT INTO restaurants(name,address,description) VALUES(?,?,?)",
            ("Sakura & Wok Харків", "м. Харків, вул. Сумська, 72", "Сучасна азійська кухня: рамен, ролли, вок-локшина та парові булочки бао"),
        )
        asian_rest_id = cur.lastrowid
    else:
        asian_rest_id = asian_rest["id"]

    asian_menu = [
        ("Рамен Тонкоцу з куркою су-від", "Насичений бульйон, пшенична локшина, мариноване яйце адзітама, норі та зелена цибуля", 265.0),
        ("Ролл Філадельфія Класік", "Охолоджений норвезький лосось, вершковий сир, стигле авокадо, огірок, рис і норі (8 шт.)", 310.0),
        ("Локшина Удон з тигровими креветками", "Пшенична локшина вок у соусі теріякі з креветками, болгарським перцем, цукіні та кунжутом", 285.0),
        ("Том Ям з морепродуктами", "Тайський пікантний суп на кокосовому молоці з креветками, мідіями, грибами шиїтаке та паровим рисом", 295.0),
        ("Парові булочки Бао з качкою Хойсін", "Дві пухкі парові булочки з томленою качкою, свіжим огірком, кінзою та соусом хойсін", 230.0),
        ("Моті Манго-Маракуйя", "Японський десерт із ніжного рисового тіста з вершковим кремом і тропічним пюре (2 шт.)", 145.0),
    ]
    for name, desc, price in asian_menu:
        # Якщо азійська страва випадково була в першому ресторані, переносимо її в азійський ресторан
        con.execute("DELETE FROM menu_items WHERE restaurant_id=? AND name=?", (first_rest_id, name))
        exists = con.execute("SELECT 1 FROM menu_items WHERE restaurant_id=? AND name=?", (asian_rest_id, name)).fetchone()
        if not exists:
            con.execute(
                "INSERT INTO menu_items(restaurant_id,name,description,price) VALUES(?,?,?,?)",
                (asian_rest_id, name, desc, price),
            )

class RestaurantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=250)
    description: str = ""
class MenuItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    price: float = Field(gt=0)
class AvailabilityUpdate(BaseModel): available: bool

@app.get("/health")
def health(): return {"status":"ok","service":"restaurant-service"}

@app.post("/restaurants", status_code=201)
def create_restaurant(data: RestaurantCreate):
    with db() as con:
        cur=con.execute("INSERT INTO restaurants(name,address,description) VALUES(?,?,?)",(data.name,data.address,data.description))
        return {"id":cur.lastrowid,**data.model_dump()}

@app.get("/restaurants")
def list_restaurants():
    with db() as con: return [dict(r) for r in con.execute("SELECT * FROM restaurants ORDER BY id")]

@app.get("/restaurants/{restaurant_id}")
def get_restaurant(restaurant_id:int):
    with db() as con: row=con.execute("SELECT * FROM restaurants WHERE id=?",(restaurant_id,)).fetchone()
    if row is None: raise HTTPException(404,"Ресторан не знайдено")
    return dict(row)

@app.post("/restaurants/{restaurant_id}/menu", status_code=201)
def add_menu_item(restaurant_id:int,data:MenuItemCreate):
    with db() as con:
        if con.execute("SELECT 1 FROM restaurants WHERE id=?",(restaurant_id,)).fetchone() is None: raise HTTPException(404,"Ресторан не знайдено")
        cur=con.execute("INSERT INTO menu_items(restaurant_id,name,description,price) VALUES(?,?,?,?)",(restaurant_id,data.name,data.description,data.price))
        return {"id":cur.lastrowid,"restaurant_id":restaurant_id,**data.model_dump(),"available":True}

@app.get("/restaurants/{restaurant_id}/menu")
def get_menu(restaurant_id:int):
    with db() as con:
        if con.execute("SELECT 1 FROM restaurants WHERE id=?",(restaurant_id,)).fetchone() is None: raise HTTPException(404,"Ресторан не знайдено")
        return [dict(r) for r in con.execute("SELECT * FROM menu_items WHERE restaurant_id=? ORDER BY id",(restaurant_id,))]

@app.get("/menu/{item_id}")
def get_menu_item(item_id:int):
    with db() as con: row=con.execute("SELECT * FROM menu_items WHERE id=?",(item_id,)).fetchone()
    if row is None: raise HTTPException(404,"Страву не знайдено")
    return dict(row)

@app.patch("/menu/{item_id}/availability")
def update_availability(item_id:int,data:AvailabilityUpdate):
    with db() as con:
        cur=con.execute("UPDATE menu_items SET available=? WHERE id=?",(int(data.available),item_id))
        if cur.rowcount==0: raise HTTPException(404,"Страву не знайдено")
    return {"id":item_id,"available":data.available}
