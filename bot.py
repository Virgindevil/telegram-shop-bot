# -*- coding: utf-8 -*-
import sqlite3
import os


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Бот работает! 🚀"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

ADMIN_ID = "753866988"

def get_subcategories(parent_id=None):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM categories WHERE parent_id IS ?', (parent_id,))
    rows = cursor.fetchall()
    conn.close()
    return {str(row[0]): row[1] for row in rows}

def has_products(category_id):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM products WHERE category_id = ?', (category_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def get_products_by_category(category_id):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, stock, image_url FROM products WHERE category_id = ?', (category_id,))
    rows = cursor.fetchall()
    conn.close()
    return {
        str(row[0]): {"name": row[1], "price": row[2], "stock": row[3], "image_url": row[4]}
        for row in rows
    }

def get_category_name(category_id):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM categories WHERE id = ?', (category_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "Каталог"

# ✅ НОВАЯ ФУНКЦИЯ: СОХРАНЕНИЕ ЗАКАЗА
def save_order(user_id, username, items, address, total_price, payment_method, payment_proof, payment_proof_type):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (user_id, username, items, address, total_price, payment_method, payment_proof, payment_proof_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, items, address, total_price, payment_method, payment_proof, payment_proof_type))
    conn.commit()
    conn.close()

# ✅ НОВАЯ ФУНКЦИЯ: ОБНОВЛЕНИЕ ОСТАТКОВ ТОВАРА
def update_stock(product_id, quantity_sold):
    """
    Уменьшает количество товара в базе данных.
    Вызывается после успешного оформления заказа.
    """
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE products SET stock = stock - ? WHERE id = ?', (quantity_sold, product_id))
        conn.commit()
    except Exception as e:
        print(f"Ошибка при обновлении количества товара {product_id}: {e}")
    finally:
        conn.close()


# --- ОСНОВНЫЕ КОМАНДЫ И ОБРАБОТЧИКИ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка: {e}")
    if user_id not in context.user_data:
        context.user_data[user_id] = {"cart": {}, "reserved_stock": {}, "category_path": []}
    username = update.message.from_user.username
    context.user_data[user_id]["username"] = username if username else f"user_{user_id}"
    keyboard = [
        [InlineKeyboardButton("🖼️ Просмотреть товары", callback_data="view_products")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="view_cart")],
        [InlineKeyboardButton("📦 Проверить заказ", callback_data="check_order")],
        [InlineKeyboardButton("✍️ Написать художнику", callback_data="contact_admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await update.message.reply_text("Добро пожаловать!", reply_markup=reply_markup)
    context.user_data[user_id]["last_message_id"] = message.message_id

async def view_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка: {e}")
    if "product_messages" in context.user_data.get(user_id, {}):
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()
    if "category_path" in context.user_data:
        context.user_data["category_path"][user_id] = []
    subcategories = get_subcategories(parent_id=None)
    if not subcategories:
        message = await query.message.reply_text("Категории отсутствуют.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    keyboard = []
    for cat_id, name in subcategories.items():
        keyboard.append([InlineKeyboardButton(name, callback_data=f"category_{cat_id}")])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.reply_text("Выберите категорию:", reply_markup=reply_markup)
    context.user_data[user_id]["last_message_id"] = message.message_id

async def show_category_or_products(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id=None):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Удаляем старые сообщения
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка удаления: {e}")
    if "product_messages" in context.user_data.get(user_id, {}):
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()

    # Работаем с category_id
    if category_id is None and query.data.startswith("category_"):
        category_id = int(query.data.split("_")[1])

    # Обновляем путь
    if "category_path" not in context.user_data:
        context.user_data["category_path"] = {}
    current_path = context.user_data["category_path"].get(user_id, [])
    if category_id is not None:
        if not current_path or current_path[-1] != category_id:
            current_path = current_path[:current_path.index(category_id)+1] if category_id in current_path else current_path + [category_id]
            context.user_data["category_path"][user_id] = current_path

    # Генерация клавиатуры
    subcategories = get_subcategories(category_id)
    keyboard = []

    for cat_id, name in subcategories.items():
        keyboard.append([InlineKeyboardButton(name, callback_data=f"category_{cat_id}")])

    if category_id is not None and has_products(category_id):
        products = get_products_by_category(category_id)
        for product_id in products:
            product = products[product_id]
            keyboard.append([InlineKeyboardButton(f"🖼️ {product['name']}", callback_data=f"show_product_{product_id}")])

    # Кнопка "назад"
    if len(current_path) > 1:
        parent_id = current_path[-2]
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"category_{parent_id}")])
    else:
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    category_name = get_category_name(category_id) if category_id is not None else "Каталог"
    message = await query.message.reply_text(f"Категория: {category_name}", reply_markup=reply_markup)
    context.user_data[user_id]["last_message_id"] = message.message_id

async def show_product_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка: {e}")
    if "product_messages" in context.user_data.get(user_id, {}):
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()
    product_id = int(query.data.split("_")[2])
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, price, stock, image_url FROM products WHERE id = ?', (product_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        message = await query.message.reply_text("Товар не найден.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    name, price, stock, image_path = row
    if os.path.exists(image_path):
        try:
            with open(image_path, 'rb') as photo:
                sent_message = await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=photo,
                    caption=f"{name}\nЦена: {price} руб.\nВ наличии: {stock} шт."
                )
                context.user_data[user_id]["product_messages"] = [sent_message.message_id]
        except Exception as e:
            print(f"Ошибка отправки фото: {e}")
            message = await query.message.reply_text(f"{name}\nЦена: {price} руб.\nВ наличии: {stock} шт.")
            context.user_data[user_id]["last_message_id"] = message.message_id
            return
    else:
        message = await query.message.reply_text(f"{name}\nЦена: {price} руб.\nВ наличии: {stock} шт.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    keyboard = [
        [InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f"add_to_cart_{product_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_category")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    context.user_data[user_id]["last_message_id"] = message.message_id
    context.user_data[user_id]["product_messages"] = [sent_message.message_id]

# ✅ ИСПРАВЛЕНО: Удалён дубликат, исправлено обращение к БД
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if user_id not in context.user_data:
        context.user_data[user_id] = {"cart": {}, "reserved_stock": {}, "category_path": []}
    user_id = query.from_user.id

    # Удаляем старое сообщение (например, с фото товара)
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении старого сообщения: {e}")

    product_id = int(query.data.split("_")[3])

    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, stock FROM products WHERE id = ?', (product_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        await query.message.reply_text("Товар не найден.")
        return

    _, name, price, stock = row

    reserved = context.user_data[user_id].get("reserved_stock", {}).get(str(product_id), 0)
    available = stock - reserved
    if available <= 0:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Продолжить покупки", callback_data="view_products")],
            [InlineKeyboardButton("Корзина", callback_data="view_cart")]
        ])
        message = await query.message.reply_text(f"Товар {name} закончился.", reply_markup=keyboard)
        context.user_data[user_id]["last_message_id"] = message.message_id
        return

    cart = context.user_data[user_id].setdefault("cart", {})
    if str(product_id) in cart:
        cart[str(product_id)]["quantity"] += 1
    else:
        cart[str(product_id)] = {"name": name, "price": price, "quantity": 1}

    context.user_data[user_id]["reserved_stock"][str(product_id)] = reserved + 1

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Продолжить покупки", callback_data="view_products")],
        [InlineKeyboardButton("Корзина", callback_data="view_cart")]
    ])
    message = await query.message.reply_text(f"'{name}' добавлен. Кол-во: {cart[str(product_id)]['quantity']}", reply_markup=keyboard)
    context.user_data[user_id]["last_message_id"] = message.message_id

# ✅ ИСПРАВЛЕНО: Нельзя изменять query.data — теперь вызывается функция напрямую
async def back_to_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    path = context.user_data.get("category_path", {}).get(user_id, [])

    if len(path) > 1:
        new_path = path[:-1]
        context.user_data.setdefault("category_path", {})[user_id] = new_path
        last_cat_id = new_path[-1]
        # Передаём ID напрямую
        await show_category_or_products(update, context, category_id=last_cat_id)
    elif len(path) == 1:
        context.user_data["category_path"][user_id] = []
        await view_products(update, context)
    else:
        await view_products(update, context)
        
async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or f"Пользователь (ID: {user_id})"
    
    if user_id not in context.user_data:
        context.user_data[user_id] = {}
    
    # Удаляем предыдущие сообщения
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    if "product_messages" in context.user_data.get(user_id, {}):
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()

    # Устанавливаем состояние ожидания сообщения
    context.user_data[user_id]["state"] = "awaiting_admin_message"
    
    message = await query.message.reply_text(
        "✍️ Пожалуйста, напишите ваше сообщение художнику. Оно будет отправлено напрямую."
    )
    context.user_data[user_id]["last_message_id"] = message.message_id
     
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка: {e}")
    if "product_messages" in context.user_data.get(user_id, {}):
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()
    if "category_path" in context.user_data:
        context.user_data["category_path"].pop(user_id, None)
    keyboard = [
        [InlineKeyboardButton("🖼️ Просмотреть товары", callback_data="view_products")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="view_cart")],
        [InlineKeyboardButton("📦 Проверить заказ", callback_data="check_order")],
        [InlineKeyboardButton("✍️ Написать художнику", callback_data="contact_admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.reply_text("Добро пожаловать!", reply_markup=reply_markup)
    context.user_data[user_id]["last_message_id"] = message.message_id


# ✅ ОСТАЛЬНЫЕ ФУНКЦИИ (без изменений)
async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Удаляем старое сообщение
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    # Удаляем сообщения с фото товаров
    if "product_messages" in context.user_data.get(user_id, {}):
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()
            
    if user_id not in context.user_data or "cart" not in context.user_data[user_id]:
        context.user_data[user_id] = {"cart": {}}
    cart = context.user_data[user_id]["cart"]
    if not cart:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_menu")]])
        message = await query.message.reply_text("Ваша корзина пуста.", reply_markup=keyboard)
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    total_price = sum(item["price"] * item["quantity"] for item in cart.values())
    delivery_cost = 0 if total_price >= 1500 else 400
    final_price = total_price + delivery_cost
    cart_text = "\n".join([
        f"{item['name']} - {item['price']} руб. x {item['quantity']} = {item['price'] * item['quantity']} руб."
        for item in cart.values()
    ])
    keyboard = [
        [InlineKeyboardButton("Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton("Удалить товар", callback_data="remove_from_cart")],
        [InlineKeyboardButton("Продолжить покупки", callback_data="view_products")]
    ]
    if len(cart) > 1:
        keyboard.insert(2, [InlineKeyboardButton("Удалить ВСЕ товары", callback_data="clear_cart")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.reply_text(
        text=f"Ваша корзина:\n{cart_text}\nОбщая сумма: {total_price} руб.\n"
             f"Доставка: {delivery_cost} руб. (От 1500р. в чеке - бесплатно)\nИтого: {final_price} руб.",
        reply_markup=reply_markup
    )
    context.user_data[user_id]["last_message_id"] = message.message_id

async def remove_from_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
    if user_id not in context.user_data or "cart" not in context.user_data[user_id]:
        message = await query.message.reply_text("Ваша корзина пуста.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    cart = context.user_data[user_id]["cart"]
    keyboard = [
        [InlineKeyboardButton(f"{item['name']} (x{item['quantity']})", callback_data=f"remove_item_{product_id}")]
        for product_id, item in cart.items()
    ]
    keyboard.append([InlineKeyboardButton("Назад", callback_data="view_cart")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.reply_text("Выберите товар для удаления:", reply_markup=reply_markup)
    context.user_data[user_id]["last_message_id"] = message.message_id

async def remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    product_id = query.data.split("_")[2]
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
    if user_id not in context.user_data or "cart" not in context.user_data[user_id]:
        message = await query.message.reply_text("Ваша корзина пуста.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    cart = context.user_data[user_id]["cart"]
    if product_id not in cart:
        message = await query.message.reply_text("Товар не найден в корзине.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    if cart[product_id]["quantity"] > 1:
        cart[product_id]["quantity"] -= 1
        text = f"Количество {cart[product_id]['name']} уменьшено до {cart[product_id]['quantity']}."
    else:
        removed_item = cart.pop(product_id)
        text = f"{removed_item['name']} удален из корзины."
    if not cart:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_menu")]])
        message = await query.message.reply_text("Ваша корзина теперь пуста.", reply_markup=keyboard)
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    total_price = sum(item["price"] * item["quantity"] for item in cart.values())
    delivery_cost = 0 if total_price >= 1500 else 400
    final_price = total_price + delivery_cost
    cart_text = "\n".join([
        f"{item['name']} - {item['price']} руб. x {item['quantity']} = {item['price'] * item['quantity']} руб."
        for item in cart.values()
    ])
    keyboard = [
        [InlineKeyboardButton("Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton("Удалить товар", callback_data="remove_from_cart")],
        [InlineKeyboardButton("Продолжить покупки", callback_data="view_products")]
    ]
    if len(cart) > 1:
        keyboard.insert(2, [InlineKeyboardButton("Удалить ВСЕ товары", callback_data="clear_cart")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.reply_text(
        text=f"{text}\nВаша корзина:\n{cart_text}\nОбщая сумма: {total_price} руб.\n"
             f"Доставка: {delivery_cost} руб. (От 1500р. в чеке - бесплатно)\nИтого: {final_price} руб.",
        reply_markup=reply_markup
    )
    context.user_data[user_id]["last_message_id"] = message.message_id

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
    if user_id not in context.user_data or "cart" not in context.user_data[user_id]:
        message = await query.message.reply_text("Ваша корзина уже пуста.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    context.user_data[user_id]["cart"] = {}
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_menu")]])
    message = await query.message.reply_text("Ваша корзина теперь пуста.", reply_markup=keyboard)
    context.user_data[user_id]["last_message_id"] = message.message_id

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
    if user_id not in context.user_data or "cart" not in context.user_data[user_id]:
        message = await query.message.reply_text("Ваша корзина пуста.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    cart = context.user_data[user_id]["cart"]
    if not cart:
        message = await query.message.reply_text("Ваша корзина пуста.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    total_price = sum(item["price"] * item["quantity"] for item in cart.values())
    delivery_cost = 0 if total_price >= 1500 else 400
    final_price = total_price + delivery_cost
    cart_text = "\n".join([
        f"{item['name']} - {item['price']} руб. x {item['quantity']} = {item['price'] * item['quantity']} руб."
        for item in cart.values()
    ])
    message = await query.message.reply_text(
        text=f"Ваш заказ:\n{cart_text}\nОбщая сумма: {total_price} руб.\n"
             f"Доставка: {delivery_cost} руб.(От 1500р. в чеке - бесплатно)\nИтого: {final_price} руб.\n\n"
             f"*Пожалуйста, напишите адрес доставки, индекс, ФИО получателя и номер телефона:*"
    )
    context.user_data[user_id]["last_message_id"] = message.message_id
    context.user_data[user_id]["state"] = "awaiting_address"

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # ✅ Инициализируем данные пользователя, если их нет
    if user_id not in context.user_data:
        context.user_data[user_id] = {}

    # Удаляем предыдущее сообщение-инструкцию, если есть
    if "last_message_id" in context.user_data[user_id]:
        try:
            await context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    state = context.user_data[user_id].get("state")

    # === Состояние: ожидание адреса ===
    if state == "awaiting_address":
        return await handle_address_logic(update, context)

    # === Состояние: ожидание сообщения художнику ===
    elif state == "awaiting_admin_message":
        return await handle_admin_message_logic(update, context)

    # === Нет состояния — возможно, это ошибка или "мусор" ===
    else:
        # Можно проигнорировать или отправить подсказку
        pass

async def handle_address_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    address = update.message.text
    context.user_data[user_id]["address"] = address

    # Показываем способы оплаты
    message = await update.message.reply_text(
        "Выберите способ оплаты:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("СБП (QR-код)", callback_data="payment_qr")],
            [InlineKeyboardButton("Номер карты", callback_data="payment_card")]
        ])
    )
    context.user_data[user_id]["last_message_id"] = message.message_id

async def handle_admin_message_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"user_{user_id}"
    text = update.message.text

    # Отправляем админу
    admin_message = (
        f"📬 Новое сообщение от пользователя:\n"
        f"@{username} (ID: {user_id})\n"
        f"Текст:\n{text}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)

    # Подтверждение пользователю
    reply = await update.message.reply_text("✅ Ваше сообщение отправлено художнику.")
    context.user_data[user_id]["last_message_id"] = reply.message_id

    # Сбрасываем состояние
    context.user_data[user_id]["state"] = None
   
async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
    if user_id not in context.user_data or "cart" not in context.user_data[user_id]:
        message = await query.message.reply_text("Ваша корзина пуста.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    payment_method = query.data.split("_")[1]
    context.user_data[user_id]["payment_method"] = payment_method
    if payment_method == "qr":
        with open("QR-Code.jpg", "rb") as photo_file:
            photo_msg = await query.message.reply_photo(photo=photo_file, caption="Отсканируйте QR-код для оплаты.")
            # Сохраняем ID фото
            context.user_data[user_id]["payment_messages"] = [photo_msg.message_id]
    else:
        await query.message.reply_text("Номер карты для оплаты: 2202 2016 3095 5124")
    text_msg = await query.message.reply_text("Пожалуйста, отправьте скриншот или PDF-файл подтверждения оплаты.")
    context.user_data[user_id]["state"] = "awaiting_payment_proof"
    context.user_data[user_id]["payment_messages"].append(text_msg.message_id)
    context.user_data[user_id]["last_message_id"] = query.message.message_id

# ✅ ИСПРАВЛЕНО: Добавлен вызов update_stock() после сохранения заказа
async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    payment_proof = update.message.document or update.message.photo
    
    # Удаляем все сообщения бота по оплате
    if "payment_messages" in context.user_data.get(user_id, {}):
        for msg_id in context.user_data[user_id]["payment_messages"]:
            try:
                await context.bot.delete_message(chat_id=update.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка при удалении: {e}")
        del context.user_data[user_id]["payment_messages"]

    
    if user_id not in context.user_data or context.user_data[user_id].get("state") != "awaiting_payment_proof":
        return

    if update.message.photo:
        payment_proof = update.message.photo[-1].file_id
        payment_proof_type = 'photo'
    elif update.message.document and (update.message.document.mime_type.startswith('image/') or update.message.document.mime_type == "application/pdf"):
        payment_proof = update.message.document.file_id
        payment_proof_type = 'document'
    else:
        await update.message.reply_text("Пожалуйста, отправьте скриншот или PDF-документ с подтверждением оплаты.")
        return

    cart = context.user_data[user_id]["cart"]
    product_ids = list(cart.keys())
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    placeholders = ", ".join("?" * len(product_ids))
    cursor.execute(f'''
        SELECT p.id, p.name, c.name 
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.id IN ({placeholders})
    ''', product_ids)
    product_info = cursor.fetchall()
    conn.close()

    formatted_items = []
    for pid, product_name, category_name in product_info:
        item = cart.get(str(pid))
        if item:
            quantity = item["quantity"]
            formatted_items.append(f"{product_name} x{quantity} ({category_name})")
    items = ", ".join(formatted_items)

    total_price = sum(item["price"] * item["quantity"] for item in cart.values())
    delivery_cost = 0 if total_price >= 1500 else 400
    final_price = total_price + delivery_cost
    payment_method = context.user_data[user_id]["payment_method"]

    # ✅ СОХРАНЯЕМ ЗАКАЗ
    save_order(
        user_id=user_id,
        username=context.user_data[user_id].get('username', f"user_{user_id}"),
        items=items,
        address=context.user_data[user_id]["address"],
        total_price=final_price,
        payment_method=payment_method,
        payment_proof=payment_proof,
        payment_proof_type=payment_proof_type
    )

    # ✅ СПИСЫВАЕМ ТОВАРЫ ПОСЛЕ УСПЕШНОГО СОХРАНЕНИЯ
    for product_id, item in cart.items():
        update_stock(product_id, item["quantity"])
        
    username = context.user_data[user_id]['username']
    
    # Уведомление админу
    admin_message = (f"Новый заказ от {context.user_data[user_id]['username']}:\n"
                     f"Товары: {items}\n"
                     f"Адрес: {context.user_data[user_id]['address']}\n"
                     f"Сумма: {final_price} руб.\n"
                     f"Оплата: {payment_method.capitalize()}")
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
    if payment_proof_type == 'photo':
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=payment_proof)
    else:
        await context.bot.send_document(chat_id=ADMIN_ID, document=payment_proof)

    # Очистка данных пользователя
    del context.user_data[user_id]
    await update.message.reply_text("Спасибо за заказ! Мы свяжемся с вами.")

async def check_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT items, address, total_price, payment_method FROM orders WHERE user_id = ? ORDER BY id DESC', (user_id,))
    orders = cursor.fetchall()
    conn.close()
    if not orders:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_menu")]])
        message = await query.message.reply_text("У вас нет активных заказов.", reply_markup=keyboard)
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    orders_text = []
    for idx, order in enumerate(orders, start=1):
        items, address, total_price, payment_method = order
        orders_text.append(f"Заказ #{idx}:\nТовары: {items}\nАдрес: {address}\nСумма: {total_price} руб.\nОплата: {payment_method.capitalize()}\n-----------------------------")
    full_orders_text = "\n".join(orders_text)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_menu")]])
    message = await query.message.reply_text(f"История ваших заказов:\n{full_orders_text}", reply_markup=keyboard)
    context.user_data[user_id]["last_message_id"] = message.message_id

# --- АДМИНСКИЕ КОМАНДЫ ---
async def update_stock_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if str(user_id) != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Использование: /update_stock <product_id> <new_stock>")
        return
    try:
        product_id = int(args[0])
        new_stock = int(args[1])
    except ValueError:
        await update.message.reply_text("Некорректные параметры.")
        return
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    if not product:
        await update.message.reply_text(f"Товар с ID {product_id} не найден.")
        conn.close()
        return
    cursor.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock, product_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"Количество товара '{product[0]}' обновлено до {new_stock}.")

async def view_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        user_id = update.message.from_user.id
        chat = update.message
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        chat = update.callback_query.message
    else:
        return
    if str(user_id) != ADMIN_ID:
        await chat.reply_text("У вас нет прав.")
        return
    page = context.user_data.get("view_all_orders_page", 1)
    PAGE_SIZE = 5
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, username, items, address, total_price, payment_method, payment_proof, payment_proof_type FROM orders ORDER BY id DESC')
    orders = cursor.fetchall()
    conn.close()
    if not orders:
        await chat.reply_text("Нет заказов.")
        return
    total_pages = (len(orders) + PAGE_SIZE - 1) // PAGE_SIZE
    start_index = (page - 1) * PAGE_SIZE
    current_page_orders = orders[start_index:start_index + PAGE_SIZE]
    orders_text = ""
    for order in current_page_orders:
        order_id, uid, uname, items, addr, price, pmethod, proof, ptype = order
        orders_text += f"📦 Заказ #{order_id}\nПользователь: @{uname} (ID: {uid})\nТовары: {items}\nАдрес: {addr}\nСумма: {price} руб.\nОплата: {pmethod.capitalize()}\n-------------------------------\n"
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(chat_id=chat.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка удаления: {e}")
    if "sent_files" in context.user_data.get(user_id, {}):
        for _, msg_id in context.user_data[user_id]["sent_files"]:
            try:
                await context.bot.delete_message(chat_id=chat.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка удаления файла: {e}")
        context.user_data[user_id]["sent_files"] = []
    sent_files = []
    for order in current_page_orders:
        _, _, _, _, _, _, _, proof, ptype = order
        if proof:
            try:
                if ptype == 'photo':
                    msg = await context.bot.send_photo(chat_id=chat.chat_id, photo=proof)
                    sent_files.append(("photo", msg.message_id))
                elif ptype == 'document':
                    msg = await context.bot.send_document(chat_id=chat.chat_id, document=proof)
                    sent_files.append(("document", msg.message_id))
            except Exception as e:
                print(f"Ошибка отправки: {e}")
    context.user_data[user_id]["sent_files"] = sent_files
    keyboard = []
    if page > 1:
        keyboard.append(InlineKeyboardButton("⬅️ Пред.", callback_data="prev_orders_page"))
    if start_index + PAGE_SIZE < len(orders):
        keyboard.append(InlineKeyboardButton("След. ➡️", callback_data="next_orders_page"))
    nav_row = []
    if keyboard:
        nav_row.extend(keyboard)
    nav_row.append(InlineKeyboardButton("❌ Закрыть", callback_data="close_orders"))
    reply_markup = InlineKeyboardMarkup([nav_row])
    try:
        message = await chat.reply_text(f"🛒 Заказы (Страница {page} из {total_pages}):\n{orders_text}", reply_markup=reply_markup)
        context.user_data["last_message_id"] = message.message_id
        context.user_data["view_all_orders_page"] = page
    except Exception as e:
        print(f"Ошибка: {e}")

async def navigate_orders_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if str(query.from_user.id) != ADMIN_ID:
        await query.edit_message_text("Доступ запрещён.")
        return
    page = context.user_data.get("view_all_orders_page", 1)
    context.user_data["view_all_orders_page"] = page + 1 if query.data == "next_orders_page" else max(1, page - 1)
    await view_all_orders(update, context)

async def close_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if str(query.from_user.id) != ADMIN_ID:
        await query.edit_message_text("Доступ запрещён.")
        return
    chat_id = query.message.chat_id
    if "last_message_id" in context.user_data.get(query.from_user.id, {}):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data[query.from_user.id]["last_message_id"])
            del context.user_data[query.from_user.id]["last_message_id"]
        except Exception as e:
            print(f"Ошибка: {e}")
    if "sent_files" in context.user_data.get(query.from_user.id, {}):
        for _, msg_id in context.user_data[query.from_user.id]["sent_files"]:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        del context.user_data[query.from_user.id]["sent_files"]
    try:
        await query.edit_message_text("Заказы закрыты.")
    except Exception as e:
        print(f"Ошибка: {e}")


# --- ЗАПУСК БОТА ---
def main():   
    keep_alive()
    TOKEN = "7771688126:AAFtHtiBQFs_Hb8HMr91QvYNKG5Gx1QRG4E"
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("update_stock", update_stock_admin))
    application.add_handler(CommandHandler("view_all_orders", view_all_orders))
    application.add_handler(CallbackQueryHandler(contact_admin, pattern="^contact_admin$"))   
    application.add_handler(CallbackQueryHandler(navigate_orders_page, pattern="^prev_orders_page$|^next_orders_page$"))
    application.add_handler(CallbackQueryHandler(close_orders, pattern="^close_orders$"))
    application.add_handler(CallbackQueryHandler(view_products, pattern="^view_products$"))
    application.add_handler(CallbackQueryHandler(add_to_cart, pattern=r"^add_to_cart_\d+$"))
    application.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    application.add_handler(CallbackQueryHandler(remove_from_cart, pattern="^remove_from_cart$"))
    application.add_handler(CallbackQueryHandler(remove_item, pattern=r"^remove_item_\d+$"))
    application.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    application.add_handler(CallbackQueryHandler(checkout, pattern="^checkout$"))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern=r"^payment_\w+$"))
    application.add_handler(CallbackQueryHandler(check_order, pattern="^check_order$"))
    application.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    application.add_handler(CallbackQueryHandler(show_category_or_products, pattern=r"^category_\d+$"))
    application.add_handler(CallbackQueryHandler(show_product_details, pattern=r"^show_product_\d+$"))
    application.add_handler(CallbackQueryHandler(back_to_category, pattern="^back_to_category$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_payment_proof)) 
    application.run_polling()
    print("Бот запущен...")


if __name__ == "__main__":
    main()
