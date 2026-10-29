const API = {
  users: 'http://localhost:8001',
  restaurants: 'http://localhost:8002',
  orders: 'http://localhost:8003',
  payments: 'http://localhost:8004',
  deliveries: 'http://localhost:8005',
  notifications: 'http://localhost:8006'
};

const state = {
  user: JSON.parse(localStorage.getItem('food-order-user') || 'null'),
  users: [],
  restaurants: [],
  restaurant: null,
  menu: [],
  cart: [],
  orders: [],
  notifications: []
};

const $ = id => document.getElementById(id);

const DELIVERY_LABELS = {
  preparing: '🍳 Готується на кухні',
  picked_up: '📦 Кур’єр забрав',
  on_the_way: '🛵 Кур’єр у дорозі',
  delivered: '✅ Доставлено',
  cancelled: '❌ Доставку скасовано'
};

const NEXT_DELIVERY_STATUS = {
  preparing: { code: 'on_the_way', label: '🛵 Відправити кур’єра' },
  picked_up: { code: 'on_the_way', label: '🛵 Кур’єр у дорозі' },
  on_the_way: { code: 'delivered', label: '✅ Позначити «Доставлено»' }
};

async function call(url, options = {}) {
  const r = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(data.detail || `Помилка API (${r.status})`);
  return data;
}

function money(n) {
  return new Intl.NumberFormat('uk-UA', {
    style: 'currency',
    currency: 'UAH',
    maximumFractionDigits: 2
  }).format(Number(n) || 0);
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = String(s ?? '');
  return d.innerHTML;
}

function initials(name) {
  return String(name || 'КЛ')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase() || '')
    .join('') || 'КЛ';
}

function toast(message) {
  const el = $('toast');
  el.textContent = message;
  el.classList.remove('hidden');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => el.classList.add('hidden'), 3600);
}

function setUser(user) {
  state.user = user;
  localStorage.setItem('food-order-user', JSON.stringify(user));
  $('user-avatar').textContent = initials(user.name);
  $('user-id-badge').textContent = `ID клієнта: #${user.id}`;
  $('user-name-display').textContent = user.name;
  $('user-contacts-display').textContent = `📧 ${user.email}  ·  📞 ${user.phone}`;
  $('checkout').disabled = !state.restaurant || state.cart.length === 0;
  renderUsersChips();
}

function renderUsersChips() {
  const box = $('users-list');
  if (!state.users.length) {
    box.innerHTML = '<p class="muted">Немає збережених профілів.</p>';
    return;
  }
  box.innerHTML = state.users.map(u => `
    <button type="button" class="user-chip ${state.user?.id === u.id ? 'active' : ''}" data-select-user="${u.id}">
      <strong>${esc(u.name)} (#${u.id})</strong>
      <span>${esc(u.email)} · ${esc(u.phone)}</span>
    </button>
  `).join('');
}

async function initUserProfile() {
  try {
    state.users = await call(`${API.users}/users`);
    if (state.user) {
      const matched = state.users.find(u => u.id === state.user.id);
      if (matched) {
        setUser(matched);
        return;
      }
    }
    if (state.users.length > 0) {
      setUser(state.users[0]);
    }
  } catch (err) {
    toast(err.message);
  }
}

async function refreshServices() {
  const checks = await Promise.all(
    Object.entries(API).map(async ([name, url]) => {
      try {
        await call(`${url}/health`);
        return name;
      } catch {
        return null;
      }
    })
  );
  const ok = checks.filter(Boolean).length;
  $('api-state').textContent = `${ok}/6 мікросервісів онлайн`;
  $('api-state').style.color = ok === 6 ? '#215938' : '#a6362b';
}

async function loadRestaurants() {
  state.restaurants = await call(`${API.restaurants}/restaurants`);
  if (!state.restaurants.length) {
    $('restaurants').innerHTML = '<p class="muted">Ресторанів поки немає.</p>';
    return;
  }
  if (!state.restaurant) {
    state.restaurant = state.restaurants[0];
  } else {
    state.restaurant = state.restaurants.find(r => r.id === state.restaurant.id) || state.restaurants[0];
  }

  $('restaurants').innerHTML = state.restaurants.map(r => {
    const isAsian = r.name.toLowerCase().includes('sakura') || r.description.toLowerCase().includes('азійськ');
    const badge = isAsian ? 'Харків · Азійська кухня 🍜' : 'Українська та Європейська кухня 🍕';
    return `
      <button class="restaurant-card ${state.restaurant?.id === r.id ? 'selected' : ''}" data-id="${r.id}">
        <div class="rest-top">
          <strong>${esc(r.name)}</strong>
          <span class="city-badge">${esc(badge)}</span>
        </div>
        <span class="rest-addr">📍 ${esc(r.address)}</span>
        <span class="rest-desc">${esc(r.description || 'Свіжі страви щодня')}</span>
      </button>
    `;
  }).join('');

  if (state.restaurant && (!$('address').value || $('address').value.trim() === '')) {
    $('address').value = state.restaurant.address.includes('Харків')
      ? 'Харків, просп. Науки, 14, кв. 25'
      : 'Київ, вул. Велика Васильківська, 22, кв. 10';
  }
}

async function loadMenu(id) {
  state.restaurant = state.restaurants.find(r => r.id === Number(id)) || state.restaurants[0];
  if (!state.restaurant) return;
  state.menu = await call(`${API.restaurants}/restaurants/${state.restaurant.id}/menu`);
  $('menu-title').textContent = `Меню: «${state.restaurant.name}»`;
  $('menu-subtitle').textContent = `${state.menu.length} страв доступно`;
  $('menu').innerHTML = state.menu.length
    ? state.menu.map(d => `
        <article class="dish">
          <div>
            <h3>${esc(d.name)}</h3>
            <p>${esc(d.description || 'Фірмова страва закладу.')}</p>
          </div>
          <div class="dish-bottom">
            <strong>${money(d.price)}</strong>
            <button class="add" data-dish="${d.id}" ${!d.available ? 'disabled' : ''}>
              ${d.available ? '＋ У кошик' : 'Недоступно'}
            </button>
          </div>
        </article>
      `).join('')
    : '<p class="muted">У меню поки немає страв.</p>';
  await loadRestaurants();
}

function renderCart() {
  const count = state.cart.reduce((s, i) => s + i.quantity, 0);
  const total = state.cart.reduce((s, i) => s + i.price * i.quantity, 0);
  $('cart-count').textContent = count;
  $('total').textContent = money(total);
  $('checkout').disabled = !state.user || !state.restaurant || !state.cart.length;
  $('cart-items').innerHTML = state.cart.length
    ? state.cart.map(i => `
        <div class="cart-row">
          <strong>${esc(i.name)}</strong>
          <strong>${money(i.price * i.quantity)}</strong>
          <span>${money(i.price)} за порцію</span>
          <div class="qty">
            <button data-change="-1" data-id="${i.id}">−</button>
            <b>${i.quantity}</b>
            <button data-change="1" data-id="${i.id}">＋</button>
            <button class="remove" data-remove="${i.id}">Видалити</button>
          </div>
        </div>
      `).join('')
    : '<p class="muted">Додай страву з меню ресторану.</p>';
}

async function loadNotifications() {
  if (!state.user) return;
  try {
    state.notifications = await call(`${API.notifications}/notifications/user/${state.user.id}`);
    $('notif-count').textContent = state.notifications.length;
    $('notifications-list').innerHTML = state.notifications.length
      ? state.notifications.map(n => `
          <div class="notif-item">
            <span><strong>Замовлення №${n.order_id}:</strong> ${esc(n.message)}</span>
            <span class="notif-time">${new Date(n.created_at).toLocaleString('uk-UA')}</span>
          </div>
        `).join('')
      : '<p class="muted">Повідомлень для цього профілю ще немає.</p>';
  } catch {
    // Ігноруємо тимчасову помилку сповіщень
  }
}

function updateProfileStats() {
  const activeOrders = state.orders.filter(o => o.status !== 'cancelled' && o.delivery?.status !== 'delivered').length;
  const paidTotal = state.orders
    .filter(o => o.payment?.status === 'paid' && o.status !== 'cancelled')
    .reduce((sum, o) => sum + Number(o.total || 0), 0);
  const refundTotal = state.orders
    .filter(o => o.payment?.status === 'refunded' || o.status === 'cancelled')
    .reduce((sum, o) => sum + Number(o.total || 0), 0);

  $('stat-active-orders').textContent = activeOrders;
  $('stat-paid-total').textContent = money(paidTotal);
  $('stat-refund-total').textContent = money(refundTotal);
}

async function loadOrders() {
  if (!state.user) {
    $('orders').innerHTML = '<p class="muted">Спочатку оберіть або створіть профіль клієнта зверху сторінки.</p>';
    return;
  }
  state.orders = await call(`${API.orders}/users/${state.user.id}/orders`);
  updateProfileStats();
  await loadNotifications();

  if (!state.orders.length) {
    $('orders').innerHTML = '<p class="muted">У вас поки немає оформлених замовлень. Додайте страви в кошик та натисніть «Оформити та оплатити замовлення».</p>';
    return;
  }

  $('orders').innerHTML = state.orders.map(o => {
    const isCancelled = o.status === 'cancelled';
    const delStatus = o.delivery?.status || (isCancelled ? 'cancelled' : 'preparing');
    const isDelivered = delStatus === 'delivered';
    const payStatus = o.payment?.status || (isCancelled ? 'refunded' : 'paid');
    const restName = o.delivery?.restaurant_name || state.restaurants.find(r => r.id === o.restaurant_id)?.name || `Ресторан #${o.restaurant_id}`;
    const nextStep = !isCancelled && !isDelivered ? NEXT_DELIVERY_STATUS[delStatus] : null;

    return `
      <article class="order-card ${isCancelled ? 'order-cancelled' : ''}">
        <div class="order-head">
          <div class="order-title">
            <strong>Замовлення №${o.id}</strong>
            <span>· ${esc(restName)}</span>
            <span class="muted">${new Date(o.created_at).toLocaleString('uk-UA')}</span>
          </div>
          <div class="order-badges">
            <span class="badge ${isCancelled ? 'badge-red' : 'badge-green'}">
              ${isCancelled ? 'Замовлення відкликано' : 'Замовлення активне'}
            </span>
            <span class="badge ${payStatus === 'refunded' ? 'badge-amber' : 'badge-green'}">
              ${payStatus === 'refunded' ? `↩️ Кошти повернуто: ${money(o.total)}` : `💳 Оплачено: ${money(o.total)}`}
            </span>
            <span class="badge badge-blue">
              ${esc(DELIVERY_LABELS[delStatus] || delStatus)}
            </span>
          </div>
        </div>

        <p class="order-meta">
          🍽️ <strong>Склад замовлення:</strong>
          ${o.items.map(i => `${esc(i.name)} × ${i.quantity} (${money(i.subtotal)})`).join(', ')}
        </p>
        <div class="order-address-row">
          📍 <strong>Адреса доставки:</strong> ${esc(o.address)}
        </div>

        <div class="order-actions">
          ${!isCancelled && !isDelivered ? `
            <button type="button" class="btn-action btn-cancel" data-cancel-order="${o.id}">
              ↩️ Відкликати замовлення (повернути кошти)
            </button>
            <button type="button" class="btn-action" data-edit-address="${o.id}" data-current-address="${esc(o.address)}">
              ✏️ Змінити адресу доставки
            </button>
          ` : ''}
          ${nextStep ? `
            <button type="button" class="btn-action" data-advance-delivery="${o.id}" data-next-status="${nextStep.code}">
              ${nextStep.label}
            </button>
          ` : ''}
          <button type="button" class="btn-action" data-repeat-order="${o.id}">
            🔄 Повторити в кошик
          </button>
          <button type="button" class="btn-action btn-delete" data-delete-order="${o.id}">
            🗑️ Видалити замовлення
          </button>
        </div>
      </article>
    `;
  }).join('');
}

// ОБРОБНИКИ ПОДІЙ ПРОФІЛЮ
$('edit-profile-btn').addEventListener('click', () => {
  if (!state.user) return;
  $('user-form-mode').value = 'edit';
  $('user-form-title').textContent = `Редагувати профіль #${state.user.id}`;
  $('input-user-name').value = state.user.name;
  $('input-user-email').value = state.user.email;
  $('input-user-phone').value = state.user.phone;
  $('user-form-submit').textContent = 'Зберегти зміни';
  $('profile-drawer').classList.remove('hidden');
});

$('switch-user-btn').addEventListener('click', () => {
  $('user-form-mode').value = 'create';
  $('user-form-title').textContent = 'Створити новий профіль клієнта';
  $('input-user-name').value = '';
  $('input-user-email').value = '';
  $('input-user-phone').value = '+380';
  $('user-form-submit').textContent = 'Створити профіль';
  $('profile-drawer').classList.remove('hidden');
});

$('close-profile-drawer').addEventListener('click', () => {
  $('profile-drawer').classList.add('hidden');
});

$('toggle-notifications-btn').addEventListener('click', () => {
  $('notifications-drawer').classList.toggle('hidden');
});

$('close-notif-drawer').addEventListener('click', () => {
  $('notifications-drawer').classList.add('hidden');
});

$('users-list').addEventListener('click', async e => {
  const btn = e.target.closest('[data-select-user]');
  if (!btn) return;
  const selected = state.users.find(u => u.id === Number(btn.dataset.selectUser));
  if (selected) {
    setUser(selected);
    $('profile-drawer').classList.add('hidden');
    toast(`Обрано профіль: ${selected.name}`);
    await loadOrders();
  }
});

$('user-form').addEventListener('submit', async e => {
  e.preventDefault();
  const mode = $('user-form-mode').value;
  const payload = {
    name: $('input-user-name').value.trim(),
    email: $('input-user-email').value.trim(),
    phone: $('input-user-phone').value.trim()
  };
  try {
    let u;
    if (mode === 'edit' && state.user) {
      u = await call(`${API.users}/users/${state.user.id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      toast('Дані профілю успішно оновлено');
    } else {
      u = await call(`${API.users}/users`, {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      toast('Новий профіль клієнта створено');
    }
    state.users = await call(`${API.users}/users`);
    setUser(u);
    $('profile-drawer').classList.add('hidden');
    await loadOrders();
  } catch (err) {
    toast(err.message);
  }
});

// ОБРОБНИКИ РЕСТОРАНІВ І КОШИКА
$('restaurants').addEventListener('click', async e => {
  const b = e.target.closest('[data-id]');
  if (!b) return;
  try {
    const newRestId = Number(b.dataset.id);
    if (state.restaurant?.id !== newRestId) {
      state.cart = [];
      renderCart();
      const targetRest = state.restaurants.find(r => r.id === newRestId);
      if (targetRest) {
        $('address').value = targetRest.address.includes('Харків')
          ? 'Харків, просп. Науки, 14, кв. 25'
          : 'Київ, вул. Велика Васильківська, 22, кв. 10';
      }
    }
    await loadMenu(newRestId);
  } catch (err) {
    toast(err.message);
  }
});

$('menu').addEventListener('click', e => {
  const b = e.target.closest('[data-dish]');
  if (!b) return;
  const dish = state.menu.find(x => x.id === Number(b.dataset.dish));
  if (!dish) return;
  const found = state.cart.find(x => x.id === dish.id);
  if (found) found.quantity++;
  else state.cart.push({ id: dish.id, name: dish.name, price: dish.price, quantity: 1 });
  renderCart();
  toast(`Додано у кошик: «${dish.name}»`);
});

$('cart-items').addEventListener('click', e => {
  const remove = e.target.closest('[data-remove]');
  const change = e.target.closest('[data-change]');
  if (remove) state.cart = state.cart.filter(i => i.id !== Number(remove.dataset.remove));
  if (change) {
    const i = state.cart.find(x => x.id === Number(change.dataset.id));
    if (i) {
      i.quantity += Number(change.dataset.change);
      if (i.quantity < 1) state.cart = state.cart.filter(x => x !== i);
    }
  }
  renderCart();
});

$('clear-cart-btn').addEventListener('click', () => {
  state.cart = [];
  renderCart();
});

$('checkout').addEventListener('click', async () => {
  if (!state.user || !state.restaurant) return;
  const address = $('address').value.trim();
  if (address.length < 3) {
    toast('Будь ласка, вкажіть адресу доставки');
    return;
  }
  try {
    const order = await call(`${API.orders}/orders`, {
      method: 'POST',
      body: JSON.stringify({
        user_id: state.user.id,
        restaurant_id: state.restaurant.id,
        address,
        items: state.cart.map(i => ({ menu_item_id: i.id, quantity: i.quantity }))
      })
    });
    state.cart = [];
    renderCart();
    $('result').innerHTML = `
      ✅ Замовлення <b>№${order.id}</b> прийнято!
      Сума: <b>${money(order.total)}</b> ·
      Оплата: <b>Оплачено (${esc(order.payment.status)})</b> ·
      Доставка: <b>${esc(DELIVERY_LABELS[order.delivery.status] || order.delivery.status)}</b>.
    `;
    $('result').classList.remove('hidden');
    toast(`Замовлення №${order.id} успішно оформлено та оплачено!`);
    await loadOrders();
  } catch (err) {
    toast(err.message);
  }
});

// ОБРОБНИКИ ДІЙ ІЗ ЗАМОВЛЕННЯМИ (СКАСУВАННЯ З ПОВЕРНЕННЯМ КОШТІВ, АДРЕСА, ДОСТАВКА, ВИДАЛЕННЯ)
$('orders').addEventListener('click', async e => {
  const cancelBtn = e.target.closest('[data-cancel-order]');
  const editAddrBtn = e.target.closest('[data-edit-address]');
  const advDelivBtn = e.target.closest('[data-advance-delivery]');
  const repeatBtn = e.target.closest('[data-repeat-order]');
  const deleteBtn = e.target.closest('[data-delete-order]');

  if (cancelBtn) {
    const orderId = Number(cancelBtn.dataset.cancelOrder);
    try {
      const updated = await call(`${API.orders}/orders/${orderId}/cancel`, { method: 'POST' });
      toast(`Замовлення №${orderId} скасовано. Кошти (${money(updated.total)}) повернуто!`);
      await loadOrders();
    } catch (err) {
      toast(err.message);
    }
  }

  if (editAddrBtn) {
    const orderId = Number(editAddrBtn.dataset.editAddress);
    const current = editAddrBtn.dataset.currentAddress || '';
    const nextAddress = window.prompt(`Введіть нову адресу доставки для замовлення №${orderId}:`, current);
    if (!nextAddress || nextAddress.trim().length < 3 || nextAddress.trim() === current) return;
    try {
      await call(`${API.orders}/orders/${orderId}/address`, {
        method: 'PATCH',
        body: JSON.stringify({ address: nextAddress.trim() })
      });
      toast(`Адресу доставки для замовлення №${orderId} оновлено!`);
      await loadOrders();
    } catch (err) {
      toast(err.message);
    }
  }

  if (advDelivBtn) {
    const orderId = Number(advDelivBtn.dataset.advanceDelivery);
    const nextStatus = advDelivBtn.dataset.nextStatus;
    try {
      await call(`${API.deliveries}/deliveries/order/${orderId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus })
      });
      toast(`Статус доставки замовлення №${orderId} змінено: ${DELIVERY_LABELS[nextStatus]}`);
      await loadOrders();
    } catch (err) {
      toast(err.message);
    }
  }

  if (repeatBtn) {
    const orderId = Number(repeatBtn.dataset.repeatOrder);
    const ord = state.orders.find(o => o.id === orderId);
    if (!ord) return;
    try {
      await loadMenu(ord.restaurant_id);
      state.cart = ord.items.map(i => ({
        id: i.menu_item_id,
        name: i.name,
        price: i.unit_price,
        quantity: i.quantity
      }));
      $('address').value = ord.address;
      renderCart();
      toast(`Страви із замовлення №${orderId} додано в кошик!`);
      window.scrollTo({ top: 280, behavior: 'smooth' });
    } catch (err) {
      toast(err.message);
    }
  }

  if (deleteBtn) {
    const orderId = Number(deleteBtn.dataset.deleteOrder);
    try {
      const res = await call(`${API.orders}/orders/${orderId}`, { method: 'DELETE' });
      const refundMsg = res.refunded_amount > 0 ? ` (повернуто ${money(res.refunded_amount)})` : '';
      toast(`Замовлення №${orderId} видалено${refundMsg}`);
      await loadOrders();
    } catch (err) {
      toast(err.message);
    }
  }
});

$('reload').addEventListener('click', async () => {
  try {
    await refreshServices();
    await initUserProfile();
    await loadRestaurants();
    if (state.restaurant) await loadMenu(state.restaurant.id);
    await loadOrders();
    toast('Дані усіх сервісів оновлено');
  } catch (err) {
    toast(err.message);
  }
});

$('load-orders').addEventListener('click', () => loadOrders().catch(e => toast(e.message)));

// ІНІЦІАЛІЗАЦІЯ СТОРІНКИ
(async function bootstrap() {
  renderCart();
  await refreshServices();
  await initUserProfile();
  await loadRestaurants();
  if (state.restaurant) {
    await loadMenu(state.restaurant.id);
  }
  if (state.user) {
    await loadOrders();
  }
})();
