# Онлайн-замовлення їжі: мікросервісна система

Навчальний проєкт на Python, FastAPI, SQLite та Docker Compose. Система розділена на шість незалежних сервісів, кожен має власну SQLite-базу й REST API.

## Архітектура

```text
Покупець
  ├── Frontend :8080 — сайт (presentation layer)
  └── Swagger UI / REST — ручна перевірка API
        ├── User Service         :8001 — клієнти
        ├── Restaurant Service   :8002 — ресторани та меню
        ├── Order Service        :8003 — замовлення та координація процесу
        │     ├── User Service
        │     ├── Restaurant Service
        │     ├── Payment Service
        │     ├── Delivery Service
        │     └── Notification Service
        ├── Payment Service      :8004 — навчальна імітація оплати
        ├── Delivery Service     :8005 — адреса та статус доставки
        └── Notification Service :8006 — збереження сповіщень
```

## Запуск через Docker Compose

Потрібні встановлений Docker Desktop і запущений Docker Engine. У цій папці виконайте:

```powershell
docker compose up --build
```

Зупинити сервіси: `Ctrl+C`, потім `docker compose down`. Дані збережені в окремих Docker volumes. Для повного видалення даних використовується `docker compose down -v`.

## Локальний запуск Windows без Docker

Потрібні Python 3 і доступ до встановлення пакетів під час першого запуску. Запустіть `start-project.cmd` або виконайте:

```powershell
.\run-local.ps1 start
.\run-local.ps1 status
.\run-local.ps1 stop
```

Скрипт створює `.venv` та `.runtime` у папці проєкту, запускає шість API та локальний вебсервер для сторінки. Вебінтерфейс: `http://localhost:8080`. Журнали й локальні бази даних зберігаються в `.runtime`.

Початкові ресторани й страви додаються через `POST /restaurants` та `POST /restaurants/{id}/menu` у Swagger Restaurant Service. Після цього вони з'являться на сайті для покупців.

| Сервіс | Swagger UI |
|---|---|
| User | http://localhost:8001/docs |
| Restaurant | http://localhost:8002/docs |
| Order | http://localhost:8003/docs |
| Payment | http://localhost:8004/docs |
| Delivery | http://localhost:8005/docs |
| Notification | http://localhost:8006/docs |

Вебінтерфейс для покупця: http://localhost:8080. У Compose це статичний frontend; шість предметних мікросервісів залишаються окремими backend API.

Кожен сервіс має `GET /health` для перевірки доступності.

## Наскрізний сценарій у Swagger

Виконуйте кроки по черзі. Підставляйте ID, які повертає API, якщо вони не дорівнюють `1`.

1. Створити клієнта через `POST /users` на User Service:

```json
{"name":"Олена Коваль","email":"olena@example.com","phone":"+380501234567"}
```

2. Створити ресторан через `POST /restaurants` на Restaurant Service:

```json
{"name":"Смачна кухня","address":"Київ, вул. Хрещатик, 1","description":"Домашні обіди та піца"}
```

3. Додати страву через `POST /restaurants/{restaurant_id}/menu`:

```json
{"name":"Піца Маргарита","description":"Томатний соус, моцарела, базилік","price":245}
```

4. Створити замовлення через `POST /orders` на Order Service:

```json
{"user_id":1,"restaurant_id":1,"address":"Київ, вул. Хрещатик, 10, кв. 5","items":[{"menu_item_id":1,"quantity":2}]}
```

Order Service перевірить клієнта, ресторан і страви; порахує загальну суму; збереже замовлення; звернеться до Payment Service, Delivery Service та Notification Service. У відповіді будуть позиції, сума, статус, платіж і доставка.

5. Перевірити історію клієнта: `GET /users/{user_id}/orders` на Order Service.
6. Перевірити платіж: `GET /payments/order/{order_id}` на Payment Service.
7. Перевірити доставку: `GET /deliveries/order/{order_id}` на Delivery Service. Змінити її статус можна через `PATCH /deliveries/{delivery_id}/status`, наприклад `{"status":"on_the_way"}` або `{"status":"delivered"}`.
8. Перевірити повідомлення: `GET /notifications/user/{user_id}` на Notification Service.

## API

| Сервіс | Основні маршрути |
|---|---|
| User | `POST /users`, `GET /users`, `GET /users/{id}`, `PUT /users/{id}` |
| Restaurant | `POST /restaurants`, `GET /restaurants`, `GET /restaurants/{id}`, `POST /restaurants/{id}/menu`, `GET /restaurants/{id}/menu`, `PATCH /menu/{id}/availability` |
| Order | `POST /orders`, `GET /orders/{id}`, `GET /users/{id}/orders`, `POST /orders/{id}/cancel`, `PATCH /orders/{id}/address`, `DELETE /orders/{id}` |
| Payment | `POST /payments`, `GET /payments/order/{order_id}`, `GET /payments/user/{user_id}`, `POST /payments/order/{order_id}/refund` |
| Delivery | `POST /deliveries`, `GET /deliveries/{id}`, `GET /deliveries/order/{order_id}`, `PATCH /deliveries/{id}/status`, `PATCH /deliveries/order/{order_id}/status`, `PATCH /deliveries/order/{order_id}/address` |
| Notification | `POST /notifications`, `GET /notifications/user/{user_id}`, `GET /notifications/order/{order_id}` |

## Структура

Кожна папка сервісу містить `app.py`, `requirements.txt` і `Dockerfile`. `docker-compose.yml` збирає сервіси й задає адреси для їхньої REST-взаємодії. Кожен сервіс зберігає власні дані окремо.

## Межі навчальної реалізації

Оплата і сповіщення моделюються локально: реальні платіжні системи, SMS та email не підключені. Доставка представлена записом замовлення доставки та ручною зміною статусу. Для спрощення взаємодія синхронна через HTTP; брокер повідомлень, автентифікація й адміністративна панель не входять до базової версії.

Поточний базовий процес не реалізує повну Saga-компенсацію, скасування замовлення, idempotency key чи автоматичний запас порцій. У разі розширення проєкту ці функції варто додати в Order, Payment і Restaurant/Availability Service та покрити інтеграційними перевірками.
