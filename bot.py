# -*- coding: utf-8 -*-
import sqlite3
import os
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- FLASK ДЛЯ KEEP_ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "Бот работает! 🚀"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
ADMIN_ID = 753866988  # Убедитесь, что это int

# --- ФУНКЦИИ РАБОТЫ С БАЗОЙ ---
def get_subcategories(parent_id=None):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    if parent_id is None:
        cursor.execute("SELECT id, name FROM categories WHERE parent_id IS NULL")
    else:
        cursor.execute("SELECT id, name FROM categories WHERE parent_id = ?", (parent_id,))
    rows = cursor.fetchall()
    conn.close()
    return {str(row[0]): row[1] for row in rows}

def has_products(category_id):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products WHERE category_id = ?", (category_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def get_products_in_category(category_id):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock, image_url FROM products WHERE category_id = ?", (category_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": row[0], "name": row[1], "price": row[2], "stock": row[3], "photo": row[4]}
        for row in rows
    ]

def get_product_by_id(product_id):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock, image_url FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "name": row[1],
            "price": row[2],
            "stock": row[3],
            "photo": row[4]
        }
    return None

def update_stock(product_id, quantity):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))
    conn.commit()
    conn.close()

async def save_order(user_id, username, items, address, total_price, payment_method, payment_proof, payment_proof_type):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (user_id, username, items, address, total_price, payment_method, payment_proof, payment_proof_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, items, address, total_price, payment_method, payment_proof, payment_proof_type))
    conn.commit()
    conn.close()

# --- УНИВЕРСАЛЬНАЯ ИНИЦИАЛИЗАЦИЯ ПОЛЬЗОВАТЕЛЯ ---
def init_user_data(user_id, context):
    if user_id not in context.user_data:
        context.user_data[user_id] = {
            "cart": {},
            "reserved_stock": {},
            "category_path": [],
            "state": None
        }

# --- ОСНОВНЫЕ ОБРАБОТЧИКИ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    init_user_data(user_id, context)

    if "last_message_id" in context.user_data[user_id]:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка удаления: {e}")

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
    init_user_data(user_id, context)

    if "last_message_id" in context.user_data[user_id]:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка: {e}")

    if "product_messages" in context.user_data[user_id]:
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()

    if "category_path" not in context.user_data:
        context.user_data["category_path"] = {}
    context.user_data["category_path"][user_id] = []

    subcategories = get_subcategories()
    if not subcategories:
        await query.message.reply_text("Категории не найдены.")
        return

    keyboard = [[InlineKeyboardButton(name, callback_data=f"category_{cat_id}")] for cat_id, name in subcategories.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.reply_text("Выберите категорию:", reply_markup=reply_markup)
    context.user_data[user_id]["last_message_id"] = message.message_id

async def show_category_or_products(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id=None):
    query = update.callback_query
    if query:
        await query.answer()
    user_id = update.effective_user.id
    init_user_data(user_id, context)

    if category_id is None:
        data = query.data
        if data.startswith("category_"):
            category_id = int(data.split("_")[1])
        else:
            return

    if "category_path" not in context.user_data:
        context.user_data["category_path"] = {}
    path = context.user_data["category_path"].get(user_id, [])
    context.user_data["category_path"][user_id] = path + [category_id]

    if "last_message_id" in context.user_data[user_id]:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка: {e}")

    if "product_messages" in context.user_data[user_id]:
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()

    subcategories = get_subcategories(category_id)
    if subcategories and has_products(category_id):
        keyboard = []
        for cat_id, name in subcategories.items():
            keyboard.append([InlineKeyboardButton(name, callback_data=f"category_{cat_id}")])
        products = get_products_in_category(category_id)
        for product in products:
            btn_text = f"{product['name']} — {product['price']} руб. ({product['stock']} шт.)"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"show_product_{product['id']}")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_category")])
    elif subcategories:
        keyboard = [[InlineKeyboardButton(name, callback_data=f"category_{cat_id}")] for cat_id, name in subcategories.items()]
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_category")])
    elif has_products(category_id):
        products = get_products_in_category(category_id)
        keyboard = []
        for product in products:
            btn_text = f"{product['name']} — {product['price']} руб. ({product['stock']} шт.)"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"show_product_{product['id']}")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_category")])
    else:
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_category")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await context.bot.send_message(chat_id=update.effective_chat.id, text="Выберите:", reply_markup=reply_markup)
    context.user_data[user_id]["last_message_id"] = message.message_id

async def back_to_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    init_user_data(user_id, context)
    path = context.user_data["category_path"].get(user_id, [])
    if len(path) > 1:
        new_path = path[:-1]
        context.user_data["category_path"][user_id] = new_path
        last_cat_id = new_path[-1]
        await show_category_or_products(update, context, category_id=last_cat_id)
    elif len(path) == 1:
        context.user_data["category_path"][user_id] = []
        await view_products(update, context)
    else:
        await view_products(update, context)

async def show_product_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    init_user_data(user_id, context)
    product_id = int(query.data.split("_")[2])
    product = get_product_by_id(product_id)
    if not product:
        await query.message.reply_text("Товар не найден.")
        return

    if "last_message_id" in context.user_data[user_id]:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка: {e}")

    if "product_messages" in context.user_data[user_id]:
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()

    try:
        with open(product["photo"], "rb") as photo:
            sent_message = await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo,
                caption=f"{product['name']}\nЦена: {product['price']} руб.\nВ наличии: {product['stock']} шт."
            )
    except Exception as e:
        await query.message.reply_text(f"Ошибка загрузки фото: {e}")
        return

    context.user_data[user_id]["product_messages"] = [sent_message.message_id]
    keyboard = [
        [InlineKeyboardButton("➕ Добавить в корзину", callback_data=f"add_to_cart_{product_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_category")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    context.user_data[user_id]["last_message_id"] = message.message_id

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    init_user_data(user_id, context)
    product_id = int(query.data.split("_")[3])
    product = get_product_by_id(product_id)
    if not product:
        await query.message.reply_text("Товар не найден.")
        return

    cart = context.user_data[user_id]["cart"]
    if product_id in cart:
        cart[product_id]["quantity"] += 1
    else:
        cart[product_id] = {"name": product["name"], "price": product["price"], "quantity": 1}

    reserved = context.user_data[user_id]["reserved_stock"].get(str(product_id), 0)
    context.user_data[user_id]["reserved_stock"][str(product_id)] = reserved + 1

    await query.message.reply_text(f"✅ {product['name']} добавлен в корзину.")
    await show_product_details(update, context)

async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    init_user_data(user_id, context)

    if "last_message_id" in context.user_data[user_id]:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка: {e}")

    if "product_messages" in context.user_data[user_id]:
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()

    if user_id not in context.user_data or "cart" not in context.user_data[user_id]:
        context.user_data[user_id]["cart"] = {}

    cart = context.user_data[user_id]["cart"]
    if not cart:
        message = await query.message.reply_text("Ваша корзина пуста.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return

    cart_text = "🛒 Ваша корзина:\n\n"
    total_price = 0
    for item in cart.values():
        line_price = item["price"] * item["quantity"]
        cart_text += f"{item['name']} x{item['quantity']} = {line_price} руб.\n"
        total_price += line_price

    cart_text += f"\nИтого: {total_price} руб."

    keyboard = [
        [InlineKeyboardButton("💳 Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_category")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.reply_text(cart_text, reply_markup=reply_markup)
    context.user_data[user_id]["last_message_id"] = message.message_id

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    init_user_data(user_id, context)
    context.user_data[user_id]["cart"] = {}
    await query.message.reply_text("Корзина очищена.")
    await view_cart(update, context)

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    init_user_data(user_id, context)

    if "last_message_id" in context.user_data[user_id]:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка: {e}")

    if "product_messages" in context.user_data[user_id]:
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()

    if user_id not in context.user_data or "cart" not in context.user_data[user_id] or not context.user_data[user_id]["cart"]:
        message = await query.message.reply_text("Ваша корзина пуста.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return

    message = await query.message.reply_text("Введите ваше ФИО и адрес доставки:")
    context.user_data[user_id]["last_message_id"] = message.message_id
    context.user_data[user_id]["state"] = "awaiting_address"

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    init_user_data(user_id, context)

    if "last_message_id" in context.user_data[user_id]:
        try:
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    state = context.user_data[user_id].get("state")

    if state == "awaiting_address":
        return await handle_address_logic(update, context)
    elif state == "awaiting_admin_message":
        return await handle_admin_message_logic(update, context)

async def handle_address_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    address = update.message.text
    context.user_data[user_id]["address"] = address

    keyboard = [
        [InlineKeyboardButton("СБП (QR-код)", callback_data="payment_qr")],
        [InlineKeyboardButton("Номер карты", callback_data="payment_card")]
    ]
    message = await update.message.reply_text("Выберите способ оплаты:", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data[user_id]["last_message_id"] = message.message_id

async def handle_admin_message_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"user_{user_id}"
    text = update.message.text

    admin_message = (
        f"📬 Новое сообщение от пользователя:\n"
        f"@{username} (ID: {user_id})\n"
        f"Текст:\n{text}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)

    reply = await update.message.reply_text("✅ Ваше сообщение отправлено художнику.")
    context.user_data[user_id]["last_message_id"] = reply.message_id
    context.user_data[user_id]["state"] = None

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    init_user_data(user_id, context)
    payment_proof = update.message.document or update.message.photo

    if "payment_messages" in context.user_data.get(user_id, {}):
        for msg_id in context.user_data[user_id]["payment_messages"]:
            try:
                await context.bot.delete_message(chat_id=update.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка при удалении: {e}")
        del context.user_data[user_id]["payment_messages"]

    if payment_proof:
        if hasattr(payment_proof, 'file_id'):
            proof = payment_proof.file_id
            payment_proof_type = 'photo' if hasattr(payment_proof, 'file_size') else 'document'
        else:
            proof = payment_proof.file_id
            payment_proof_type = 'document'

        cart = context.user_data[user_id]["cart"]
        items = ", ".join([f"{item['name']} x{item['quantity']}" for item in cart.values()])
        final_price = sum(item["price"] * item["quantity"] for item in cart.values())
        address = context.user_data[user_id]["address"]
        payment_method = context.user_data[user_id]["payment_method"]
        username = context.user_data[user_id]["username"]

        await save_order(user_id, username, items, address, final_price, payment_method, proof, payment_proof_type)

        for product_id, item in cart.items():
            update_stock(product_id, item["quantity"])

        admin_message = (
            f"Новый заказ от @{username}:\n"
            f"Товары: {items}\n"
            f"Адрес: {address}\n"
            f"Сумма: {final_price} руб.\n"
            f"Оплата: {payment_method.capitalize()}"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
        if payment_proof_type == 'photo':
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=proof)
        else:
            await context.bot.send_document(chat_id=ADMIN_ID, document=proof)

    await update.message.reply_text("Спасибо за заказ! Мы свяжемся с вами.")
    del context.user_data[user_id]

async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    init_user_data(user_id, context)

    if "last_message_id" in context.user_data[user_id]:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data[user_id]["last_message_id"])
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    if "product_messages" in context.user_data[user_id]:
        for msg_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Ошибка: {e}")
        context.user_data[user_id]["product_messages"].clear()

    context.user_data[user_id]["state"] = "awaiting_admin_message"
    message = await query.message.reply_text("✍️ Пожалуйста, напишите ваше сообщение художнику. Оно будет отправлено напрямую.")
    context.user_data[user_id]["last_message_id"] = message.message_id

async def check_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    init_user_data(user_id, context)
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, items, address, total_price, payment_method FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        order_id, items, address, price, pmethod = row
        text = f"📦 Последний заказ #{order_id}:\nТовары: {items}\nАдрес: {address}\nСумма: {price} руб.\nОплата: {pmethod.capitalize()}"
    else:
        text = "У вас пока нет заказов."

    await query.message.reply_text(text)

# --- ЗАПУСК БОТА ---
def main():
    keep_alive()
    TOKEN = os.getenv("TOKEN")  # Убедитесь, что в Render
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(view_products, pattern="^view_products$"))
    application.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    application.add_handler(CallbackQueryHandler(check_order, pattern="^check_order$"))
    application.add_handler(CallbackQueryHandler(contact_admin, pattern="^contact_admin$"))
    application.add_handler(CallbackQueryHandler(show_category_or_products, pattern=r"^category_\d+$"))
    application.add_handler(CallbackQueryHandler(back_to_category, pattern="^back_to_category$"))
    application.add_handler(CallbackQueryHandler(show_product_details, pattern=r"^show_product_\d+$"))
    application.add_handler(CallbackQueryHandler(add_to_cart, pattern=r"^add_to_cart_\d+$"))
    application.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    application.add_handler(CallbackQueryHandler(checkout, pattern="^checkout$"))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern="^payment_(qr|card)$"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_payment_proof))

    application.run_polling()
    print("Бот запущен...")

if __name__ == "__main__":
    main()
