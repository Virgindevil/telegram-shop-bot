# -*- coding: utf-8 -*-

import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()

    # Таблица для товаров
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            image_url PHOTO
        )
    ''')

    # Таблица для заказов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            items TEXT NOT NULL,
            address TEXT NOT NULL,
            total_price REAL NOT NULL,
            payment_method TEXT NOT NULL,
            payment_proof TEXT
        )
    ''')

    conn.commit()
    conn.close()

# Добавление тестовых товаров в базу данных
def add_test_products():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()

    # Очистка таблицы перед добавлением тестовых данных
    cursor.execute('DELETE FROM products')

    # Добавление товаров
    products = [
        ("Товар 1", 100, 10, "1.jpg"),
        ("Товар 2", 200, 5, "2.jpg"),
        ("Товар 3", 300, 3, "3.jpg")
    ]
    cursor.executemany('INSERT INTO products (name, price, stock, image_url) VALUES (?, ?, ?, ?)', products)

    conn.commit()
    conn.close()

# Получение списка товаров из базы данных
def get_products():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, stock, image_url FROM products')
    products = cursor.fetchall()
    conn.close()
    return {str(product[0]): {"name": product[1], "price": product[2], "stock": product[3], "image_url": product[4]} for product in products}

# Обновление остатков товара
def update_stock(product_id, quantity):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET stock = stock - ? WHERE id = ?', (quantity, product_id))
    conn.commit()
    conn.close()

# Сохранение заказа в базу данных
def save_order(user_id, username, items, address, total_price, payment_method, payment_proof):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (user_id, username, items, address, total_price, payment_method, payment_proof) VALUES (?, ?, ?, ?, ?, ?, ?)',
                   (user_id, username, items, address, total_price, payment_method, payment_proof))
    conn.commit()
    conn.close()



# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

    # Создаем новый интерфейс
    keyboard = [
        [InlineKeyboardButton("Просмотреть товары", callback_data="view_products")],
        [InlineKeyboardButton("Корзина", callback_data="view_cart")],
        [InlineKeyboardButton("Проверить свой заказ", callback_data="check_order")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Сохраняем username
    context.user_data[user_id] = {"username": update.message.from_user.username}

    message = await update.message.reply_text("Добро пожаловать в наш магазин!", reply_markup=reply_markup)

    # Сохраняем message_id
    context.user_data[user_id]["last_message_id"] = message.message_id

# Просмотр товаров
import uuid
async def view_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем коллбэк

    user_id = query.from_user.id

    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

    products = get_products()
    if not products:
        message = await query.message.reply_text(text="В магазине пока нет товаров.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return

    keyboard = []
    for product_id, product in products.items():
        button_text = f"{product['name']} ({product['price']} руб., в наличии: {product['stock']})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"add_to_cart_{product_id}")])

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем новое сообщение
    message = await query.message.reply_text(text="Выберите товар:", reply_markup=reply_markup)

    # Сохраняем message_id
    context.user_data[user_id]["last_message_id"] = message.message_id

# Возврат в главное меню
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем коллбэк

    user_id = query.from_user.id

    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
    
    
    
    # Возвращаемся в главное меню
    keyboard = [
        [InlineKeyboardButton("Просмотреть товары", callback_data="view_products")],
        [InlineKeyboardButton("Корзина", callback_data="view_cart")],
        [InlineKeyboardButton("Проверить свой заказ", callback_data="check_order")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.reply_text("Добро пожаловать в наш магазин!", reply_markup=reply_markup)

    # Сохраняем новый message_id
    context.user_data[user_id]["last_message_id"] = message.message_id

# Добавление товара в корзину
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):   
    query = update.callback_query
    await query.answer()  # Подтверждаем коллбэк

    user_id = query.from_user.id
    
    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")      
    
    # Инициализируем "cart", если его нет
    if user_id not in context.user_data:
        context.user_data[user_id] = {"cart": {}}
    elif "cart" not in context.user_data[user_id]:
        context.user_data[user_id]["cart"] = {}

    product_id = query.data.split("_")[3]
    products = get_products()

    if product_id not in products:
        await query.message.reply_text("Товар не найден.")
        return

    product = products[product_id]
    
    
    
    # Добавляем товар в корзину
    cart = context.user_data[user_id]["cart"]
    if product_id in cart:
        cart[product_id]["quantity"] += 1
    else:
        cart[product_id] = {"name": product["name"], "price": product["price"], "quantity": 1}

    # Отправляем новое сообщение с подтверждением
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Продолжить покупки", callback_data="view_products")],
        [InlineKeyboardButton("Перейти к корзине", callback_data="view_cart")]
    ])
    message = await query.message.reply_text(
        text=f"{product['name']} добавлен в корзину. Количество: {cart[product_id]['quantity']}",
        reply_markup=keyboard
    )
    # Сохраняем message_id
    context.user_data[user_id]["last_message_id"] = message.message_id
    

# Просмотр корзины
async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем коллбэк

    user_id = query.from_user.id

    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

    # Инициализируем "cart", если его нет
    if user_id not in context.user_data or "cart" not in context.user_data[user_id]:
        context.user_data[user_id] = {"cart": {}}

    cart = context.user_data[user_id]["cart"]

    if not cart:
        message = await query.message.reply_text(text="Ваша корзина пуста.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return

    total_price = sum(item["price"] * item["quantity"] for item in cart.values())
    delivery_cost = 0 if total_price >= 1500 else 400
    final_price = total_price + delivery_cost

    cart_text = "\n".join([
        f"{item['name']} - {item['price']} руб. x {item['quantity']} = {item['price'] * item['quantity']} руб."
        for item in cart.values()
    ])

    # Создаем клавиатуру
    keyboard = [
        [InlineKeyboardButton("Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton("Удалить товар", callback_data="remove_from_cart")],
        [InlineKeyboardButton("Продолжить покупки", callback_data="view_products")]
    ]

    # Добавляем кнопку "Удалить ВСЕ товары", только если товаров больше одного
    if len(cart) > 1:
        keyboard.insert(2, [InlineKeyboardButton("Удалить ВСЕ товары", callback_data="clear_cart")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем новое сообщение
    message = await query.message.reply_text(
        text=f"Ваша корзина:\n{cart_text}\n\nОбщая сумма: {total_price} руб.\n"
             f"Доставка: {delivery_cost} руб.\nИтого: {final_price} руб.",
        reply_markup=reply_markup
    )

    # Сохраняем новый message_id
    context.user_data[user_id]["last_message_id"] = message.message_id

# Удаление товара из корзины
async def remove_from_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем коллбэк

    user_id = query.from_user.id
    
    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
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

    message = await query.message.reply_text(text="Выберите товар для удаления:", reply_markup=reply_markup)

    # Сохраняем новый message_id
    context.user_data[user_id]["last_message_id"] = message.message_id

# Удаление конкретного товара из корзины
async def remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем коллбэк

    user_id = query.from_user.id
    product_id = query.data.split("_")[2]
    
    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
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

    # Уменьшаем количество товара или удаляем его
    if cart[product_id]["quantity"] > 1:
        cart[product_id]["quantity"] -= 1
        new_quantity = cart[product_id]["quantity"]
        text = f"Количество {cart[product_id]['name']} уменьшено до {new_quantity}."
    else:
        removed_item = cart.pop(product_id)
        text = f"{removed_item['name']} удален из корзины."

    # Проверяем, пуста ли корзина
    if not cart:
        message = await query.message.reply_text("Ваша корзина теперь пуста.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return

    # Обновляем корзину
    total_price = sum(item["price"] * item["quantity"] for item in cart.values())
    delivery_cost = 0 if total_price >= 1500 else 400
    final_price = total_price + delivery_cost

    cart_text = "\n".join([
        f"{item['name']} - {item['price']} руб. x {item['quantity']} = {item['price'] * item['quantity']} руб."
        for item in cart.values()
    ])

    # Создаем клавиатуру
    keyboard = [
        [InlineKeyboardButton("Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton("Удалить товар", callback_data="remove_from_cart")],
        [InlineKeyboardButton("Продолжить покупки", callback_data="view_products")]
    ]

    # Добавляем кнопку "Удалить ВСЕ товары", только если товаров больше одного
    if len(cart) > 1:
        keyboard.insert(2, [InlineKeyboardButton("Удалить ВСЕ товары", callback_data="clear_cart")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем новое сообщение
    message = await query.message.reply_text(
        text=f"{text}\n\nВаша корзина:\n{cart_text}\n\nОбщая сумма: {total_price} руб.\n"
             f"Доставка: {delivery_cost} руб.\nИтого: {final_price} руб.",
        reply_markup=reply_markup
    )

    # Сохраняем новый message_id
    context.user_data[user_id]["last_message_id"] = message.message_id

# Очистка всей корзины
async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем коллбэк

    user_id = query.from_user.id
    
    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
    
    # Очищаем корзину
    if user_id not in context.user_data or "cart" not in context.user_data[user_id]:
        message = await query.message.reply_text("Ваша корзина уже пуста.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return

    context.user_data[user_id]["cart"] = {}

    # Выводим сообщение о пустой корзине
    message = await query.message.reply_text("Ваша корзина очищена.")
    context.user_data[user_id]["last_message_id"] = message.message_id

# Оформление заказа
async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем коллбэк

    # Извлекаем user_id
    user_id = query.from_user.id

    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

    # Проверяем, есть ли товары в корзине
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

    # Запрашиваем адрес доставки
    message = await query.message.reply_text(
        text=f"Ваш заказ:\n{cart_text}\n\nОбщая сумма: {total_price} руб.\n"
             f"Доставка: {delivery_cost} руб.\nИтого: {final_price} руб.\n\n"
             "Пожалуйста, отправьте адрес доставки:"
    )

    # Сохраняем новый message_id
    context.user_data[user_id]["last_message_id"] = message.message_id

    # Устанавливаем состояние для получения адреса
    context.user_data[user_id]["state"] = "awaiting_address"

# Обработка адреса доставки
async def handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

    if user_id not in context.user_data or context.user_data[user_id].get("state") != "awaiting_address":
        return
    
    # Проверяем, есть ли товары в корзине
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
    
    address = update.message.text
    context.user_data[user_id]["address"] = address

    # Сохраняем username для дальнейшего использования
    context.user_data[user_id]["username"] = update.message.from_user.username

    await update.message.reply_text("Выберите способ оплаты:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("СБП (QR-код)", callback_data="payment_qr")],
        [InlineKeyboardButton("Номер карты", callback_data="payment_card")]
    ]))

    # Сохраняем message_id
    context.user_data[user_id]["last_message_id"] = update.message.message_id

# Обработка способов оплаты
async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем коллбэк

    # Извлекаем user_id
    user_id = query.from_user.id

    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
    
    # Проверяем, есть ли товары в корзине
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
    
    payment_method = query.data.split("_")[1]

    if payment_method == "qr":
        with open("QR-Code.jpg", "rb") as photo_file:
            await query.message.reply_photo(
                photo=photo_file,
                caption=f"Ваш заказ:\n{cart_text}\n\nОбщая сумма: {total_price} руб.\n"
             f"Доставка: {delivery_cost} руб.\nИтого: {final_price} руб.\n\n"
             "Отсканируйте QR-код для оплаты."
            )
    else:
        await query.message.reply_text(
        text=f"Ваш заказ:\n{cart_text}\n\nОбщая сумма: {total_price} руб.\n"
             f"Доставка: {delivery_cost} руб.\nИтого: {final_price} руб.\n\n"
             "Номер карты для оплаты: 2202 2016 3095 5124")

    context.user_data[user_id]["payment_method"] = payment_method
    await query.message.reply_text("Пожалуйста, отправьте скриншот подтверждения оплаты.")
    context.user_data[user_id]["state"] = "awaiting_payment_proof"

    # Сохраняем message_id
    context.user_data[user_id]["last_message_id"] = query.message

# Обработка изображения подтверждения оплаты
async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # Проверяем состояние пользователя
    if user_id not in context.user_data or context.user_data[user_id].get("state") != "awaiting_payment_proof":
        return

    # Проверяем тип сообщения
    if update.message.photo:
        # Если это изображение
        payment_proof = update.message.photo[-1].file_id
    elif update.message.document and update.message.document.mime_type == "application/pdf":
        # Если это PDF-документ
        payment_proof = update.message.document.file_id
    else:
        # Если тип сообщения не подходит
        await update.message.reply_text(
            "Пожалуйста, отправьте изображение или PDF-документ с подтверждением оплаты."
        )
        return

    # Сохраняем подтверждение оплаты
    context.user_data[user_id]["payment_proof"] = payment_proof

    # Сохранение заказа
    cart = context.user_data[user_id]["cart"]
    address = context.user_data[user_id]["address"]
    total_price = sum(item["price"] * item["quantity"] for item in cart.values())
    delivery_cost = 0 if total_price >= 1500 else 400
    final_price = total_price + delivery_cost
    items = ", ".join([f"{item['name']} x {item['quantity']}" for item in cart.values()])
    payment_method = context.user_data[user_id]["payment_method"]

    save_order(
        user_id=user_id,
        username=context.user_data[user_id]["username"],  # Теперь это значение будет доступно
        items=items,
        address=address,
        total_price=final_price,
        payment_method=payment_method,
        payment_proof=payment_proof
    )

    # Отправка уведомления администратору
    admin_message = f"Новый заказ от пользователя @{context.user_data[user_id]['username']}:\n" \
                    f"Товары: {items}\n" \
                    f"Адрес доставки: {address}\n" \
                    f"Сумма заказа: {final_price} руб.\n" \
                    f"Способ оплаты: {payment_method.capitalize()}"
    await context.bot.send_message(chat_id="753866988", text=admin_message)

    if update.message.photo:
        await context.bot.send_photo(chat_id="753866988", photo=payment_proof)
    elif update.message.document:
        await context.bot.send_document(chat_id="753866988", document=payment_proof)

    # Очистка корзины
    del context.user_data[user_id]
    await update.message.reply_text("Спасибо за заказ! Мы свяжемся с вами.")
    

# Проверка своего заказа
async def check_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id       
    
    # Инициализируем "cart", если его нет
    if user_id not in context.user_data:
        context.user_data[user_id] = {"cart": {}}
    elif "cart" not in context.user_data[user_id]:
        context.user_data[user_id]["cart"] = {}


    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT items, address, total_price, payment_method FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
    order = cursor.fetchone()
    conn.close()

    if not order:
        message = await query.message.reply_text(text="У вас нет активных заказов.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return

    items, address, total_price, payment_method = order
    message = await query.message.reply_text(
        text=f"Ваш последний заказ:\nТовары: {items}\nАдрес доставки: {address}\n"
             f"Сумма заказа: {total_price} руб.\nСпособ оплаты: {payment_method.capitalize()}"
    )

    # Сохраняем message_id
    context.user_data[user_id]["last_message_id"] = message.message_id

# Основная функция
def main():
    # Инициализация базы данных
    init_db()
    add_test_products()

    # Замените 'YOUR_BOT_TOKEN' на токен, который вы получили от BotFather
    TOKEN = "7771688126:AAFtHtiBQFs_Hb8HMr91QvYNKG5Gx1QRG4E"
    ADMIN_CHAT_ID = "753866988"  # Замените на ID администратора

    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(view_products, pattern="^view_products$"))
    application.add_handler(CallbackQueryHandler(add_to_cart, pattern=r"^add_to_cart_\d+$"))
    application.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    application.add_handler(CallbackQueryHandler(remove_from_cart, pattern="^remove_from_cart$"))
    application.add_handler(CallbackQueryHandler(remove_item, pattern=r"^remove_item_\d+$"))
    application.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    application.add_handler(CallbackQueryHandler(checkout, pattern="^checkout$"))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern=r"^payment_\w+$"))
    application.add_handler(CallbackQueryHandler(check_order, pattern="^check_order$"))
    application.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))  # Обработчик кнопки "Назад"
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address))
    application.add_handler(MessageHandler(
    filters.PHOTO | (filters.Document.MimeType("application/pdf")),
    handle_payment_proof
))

    # Запуск бота
    application.run_polling()
    print("Бот запущен...")

if __name__ == "__main__":
    main()