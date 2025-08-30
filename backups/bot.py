# -*- coding: utf-8 -*-

import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('shop.db', timeout=10)  # Таймаут 10 секунд
    cursor = conn.cursor()
    # Таблица для категорий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    
    # Таблица для товаров
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            stock INTEGER NOT NULL,
            image_url TEXT,
            category_id INTEGER,
            FOREIGN KEY(category_id) REFERENCES categories(id)
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
            total_price INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            payment_proof TEXT,
            payment_proof_type TEXT
        )
    ''')

    conn.commit()
    conn.close()

# Обновление количества товара администратором
async def update_stock_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    # Проверяем, является ли пользователь администратором
    if str(user_id) != "753866988":  # Замените на ID администратора
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    # Получаем аргументы команды
    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            "Использование: /update_stock <product_id> <new_stock>"
        )
        return

    product_id, new_stock = args
    try:
        product_id = int(product_id)
        new_stock = int(new_stock)
    except ValueError:
        await update.message.reply_text("Некорректные параметры. Убедитесь, что product_id и new_stock являются числами.")
        return

    # Подключаемся к базе данных и обновляем stock
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()

    if not product:
        await update.message.reply_text(f"Товар с ID {product_id} не найден.")
        conn.close()
        return

    product_name = product[0]
    cursor.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock, product_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Количество товара '{product_name}' успешно обновлено до {new_stock}.")

# Просмотр списка всех заказов от всех пользователей администратором
async def view_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Проверяем, является ли пользователь администратором
    if str(user_id) != "753866988":  # замените на ваш ID администратора
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    # Подключаемся к базе данных и получаем все заказы
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            id, user_id, username, items, address, total_price, payment_method, payment_proof, payment_proof_type
        FROM orders
    ''')
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        await update.message.reply_text("Нет активных заказов.")
        return

    # Формируем текст с информацией о всех заказах
    orders_text = ""
    for order in orders:
        order_id, user_id, username, items, address, total_price, payment_method , payment_proof, payment_proof_type= order
        orders_text += (
            f"📦 Заказ #{order_id}\n"
            f"Пользователь: @{username} (ID: {user_id})\n"
            f"Товары: {items}\n"
            f"Адрес доставки: {address}\n"
            f"Сумма: {total_price} руб.\n"
            f"Оплата: {payment_method.capitalize()}\n"
            f"-------------------------------\n"
        )
        if payment_proof:
            try:
                if payment_proof_type == 'photo':
                    await context.bot.send_photo(chat_id="753866988", photo=payment_proof)
                elif payment_proof_type == 'document':
                    await context.bot.send_document(chat_id="753866988", document=payment_proof)
            except Exception as e:
                print(f"Ошибка при отправке файла: {e}")
            
    
    # Отправляем сообщение с полным списком заказов
    await update.message.reply_text(f"🛒 Список всех заказов:\n\n{orders_text}")

# Добавление тестовых товаров в базу данных
def add_test_products():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    
    # Проверяем, есть ли категории в таблице categories
    cursor.execute('SELECT COUNT(*) FROM categories')
    categories_count = cursor.fetchone()[0]
    
    if categories_count == 0:
        # Очистка таблицы перед добавлением тестовых данных (на случай, если ранее были ошибки)
        cursor.execute('DELETE FROM categories')
        
        # Добавление тестовых категорий
        categories = [
            ("Стикеры",),
            ("Постеры А3",),
            ("Постеры А4",)
        ]
        cursor.executemany('INSERT INTO categories (name) VALUES (?)', categories)
        
        print("Тестовые категории успешно добавлены в базу данных.")
    else:
        print("Тестовые категории уже существуют в базе данных. Данные не добавлены.")
    
    # Проверяем, есть ли товары в таблице products
    cursor.execute('SELECT COUNT(*) FROM products')
    product_count = cursor.fetchone()[0]

    # Если товаров нет, добавляем тестовые данные
    if product_count == 0:
        # Очистка таблицы перед добавлением тестовых данных (на случай, если ранее были ошибки)
        cursor.execute('DELETE FROM products')
                
        # Добавление тестовых товаров
        products = [
        ("Осеннее настроение", 350, 10, "1.jpg", 1),
        ("Кошка желе", 350, 5, "2.jpg", 1),
        ("Маления", 350, 5, "4.jpg", 2),
        ("Реальные упыри", 350, 3, "3.jpg", 1)
    ]
        cursor.executemany('INSERT INTO products (name, price, stock, image_url, category_id) VALUES (?, ?, ?, ?, ?)', products)

        print("Тестовые товары успешно добавлены в базу данных.")
    else:
        print("Тестовые товары уже существуют в базе данных. Данные не добавлены.")

    conn.commit()
    conn.close()    

# Получение списка категорий из базы данных   
def get_categories():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM categories')
    categories = cursor.fetchall()
    conn.close()
    return {str(cat[0]): cat[1] for cat in categories}

# Получение списка товаров из базы данных
def get_products():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, stock, image_url, category_id FROM products')
    products = cursor.fetchall()
    conn.close()
    return {str(product[0]): {"name": product[1], "price": product[2], "stock": product[3], "image_url": product[4], "category_id": product[5]} for product in products}
    
# Обновление остатков товара
def update_stock(product_id, quantity):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET stock = stock - ? WHERE id = ?', (quantity, product_id))
    conn.commit()
    conn.close()

# Сохранение заказа в базу данных
def save_order(user_id, username, items, address, total_price, payment_method, payment_proof, payment_proof_type):
    with sqlite3.connect('shop.db', timeout=10) as conn:
        conn = sqlite3.connect('shop.db')
        cursor = conn.cursor()

        # Если username пустой, используем значение по умолчанию
        username = username or f"user_{user_id}"

        cursor.execute(
            'INSERT INTO orders (user_id, username, items, address, total_price, payment_method, payment_proof, payment_proof_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (user_id, username, items, address, total_price, payment_method, payment_proof, payment_proof_type)
        )
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
    
    
    # Инициализируем данные пользователя, если их нет
    if user_id not in context.user_data:
        context.user_data[user_id] = {"cart": {}, "reserved_stock": {}}
    else:
        # Если данные уже есть, не затираем их
        if "cart" not in context.user_data[user_id]:
            context.user_data[user_id]["cart"] = {}
        if "reserved_stock" not in context.user_data[user_id]:
            context.user_data[user_id]["reserved_stock"] = {}
    
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
            
    # Удаляем сообщения с товарами
    if "product_messages" in context.user_data[user_id]:
        for message_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=message_id)
            except Exception as e:
                print(f"Ошибка при удалении сообщения {message_id}: {e}")
        context.user_data[user_id]["product_messages"].clear()

   
    # Получаем категории из базы данных
    categories = get_categories()

    if not categories:
        message = await query.message.reply_text("Категории пока отсутствуют.")
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    else:
        product_messages = []
        
    # Формируем кнопки для каждой категории    
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"category_{cat_id}")]
        for cat_id, name in categories.items()
    ]
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = await query.message.reply_text("Выберите категорию:", reply_markup=reply_markup)
    context.user_data[user_id]["last_message_id"] = message.message_id

    # Сохраняем message_id
    context.user_data[user_id]["last_message_id"] = message.message_id
    context.user_data[user_id]["product_messages"] = product_messages

#Функция для отображения товаров по выбранной категории
async def show_products_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем коллбэк
    user_id = query.from_user.id

    # Удаляем старое сообщение
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

    # Очищаем предыдущие сообщения с товарами
    if "product_messages" in context.user_data[user_id]:
        for message_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=message_id)
            except Exception as e:
                print(f"Ошибка при удалении сообщения {message_id}: {e}")
        context.user_data[user_id]["product_messages"] = []
        
    # Инициализируем "reserved_stock", если его нет
    if user_id not in context.user_data:
        context.user_data[user_id] = {"cart": {}, "reserved_stock": {}, "product_messages": []}
    elif "reserved_stock" not in context.user_data[user_id]:
        context.user_data[user_id]["reserved_stock"] = {}
    elif "product_messages" not in context.user_data[user_id]:
        context.user_data[user_id]["product_messages"] = []    

    # Извлекаем ID категории из callback_data
    category_id = query.data.split("_")[1]

    # Получаем товары этой категории
    products = get_products_by_category(category_id)

    # Если категорий нет, — показываем сообщение с кнопкой "Назад"
    if not products:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Назад", callback_data="back_to_menu")]
        ])
        message = await query.message.reply_text(
            text="В этой категории товаров нет.",
            reply_markup=keyboard
        )
        context.user_data[user_id]["last_message_id"] = message.message_id
        return


    # Отправляем товары
    product_messages = []
    for product_id, product in products.items():
        cart = context.user_data[user_id].get("cart", {})
        quantity_in_cart = cart.get(product_id, {}).get("quantity", 0)

        caption = (
            f"{product['name']}\n"
            f"Цена: {product['price']} руб.\n"
            f"В наличии: {product['stock']} шт."
        )
        if quantity_in_cart > 0:
            caption += f"\nВ корзине: {quantity_in_cart} шт."

        message = await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=product["image_url"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Добавить в корзину", callback_data=f"add_to_cart_{product_id}")]
            ])
        )
        product_messages.append(message.message_id)

    # Кнопка "Назад к категориям"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Назад к категориям", callback_data="view_products")]
    ])
    message = await query.message.reply_text("Выберите товар:", reply_markup=keyboard)

    # Сохраняем message_id и список сообщений
    context.user_data[user_id]["last_message_id"] = message.message_id
    context.user_data[user_id]["product_messages"] = product_messages


def get_products_by_category(category_id):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, stock, image_url, category_id FROM products WHERE category_id = ?', (category_id,))
    products = cursor.fetchall()
    conn.close()
    return {
        str(product[0]): {
            "name": product[1],
            "price": product[2],
            "stock": product[3],
            "image_url": product[4],
            "category_id": product[5]
        }
        for product in products
    }

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

    # Удаляем сообщения с товарами
    if "product_messages" in context.user_data[user_id]:
        for message_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=message_id)
            except Exception as e:
                print(f"Ошибка при удалении сообщения {message_id}: {e}")
        context.user_data[user_id]["product_messages"].clear()

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

    # Удаляем сообщения с товарами
    if "product_messages" in context.user_data[user_id]:
        for message_id in context.user_data[user_id]["product_messages"]:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=message_id)
            except Exception as e:
                print(f"Ошибка при удалении сообщения {message_id}: {e}")
        context.user_data[user_id]["product_messages"].clear()            
    
    # Инициализируем "cart" и "reserved_stock", если их нет
    if user_id not in context.user_data:
        context.user_data[user_id] = {"cart": {}, "reserved_stock": {}}
    elif "cart" not in context.user_data[user_id]:
        context.user_data[user_id]["cart"] = {}
    elif "reserved_stock" not in context.user_data[user_id]:
        context.user_data[user_id]["reserved_stock"] = {}

    product_id = query.data.split("_")[3]
    products = get_products()

    if product_id not in products:
        await query.message.reply_text("Товар не найден.")
        return

    product = products[product_id]      
    
    # Проверяем наличие товара с учетом резервирования
    reserved_quantity = context.user_data[user_id]["reserved_stock"].get(product_id, 0)
    available_stock = product["stock"] - reserved_quantity

    if available_stock <= 0:
        # Отправляем сообщение с кнопками
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Продолжить покупки", callback_data="view_products")],
            [InlineKeyboardButton("Вернуться в меню", callback_data="back_to_menu")]
        ])
        message = await query.message.reply_text(
            f"{product['name']} недоступен для заказа.",
            reply_markup=keyboard
        )
        # Сохраняем message_id
        context.user_data[user_id]["last_message_id"] = message.message_id
        return
    
    # Добавляем товар в корзину
    cart = context.user_data[user_id]["cart"]
    if product_id in cart:
        cart[product_id]["quantity"] += 1
    else:
        cart[product_id] = {"name": product["name"], "price": product["price"], "quantity": 1}
    
    # Резервируем товар
    context.user_data[user_id]["reserved_stock"][product_id] = context.user_data[user_id]["reserved_stock"].get(product_id, 0) + 1
    
    # Отправляем новое сообщение с подтверждением
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Продолжить покупки", callback_data="view_products")],
        [InlineKeyboardButton("Перейти к корзине", callback_data="view_cart")]
    ])
    message = await query.message.reply_text(
        text=(f"'{product['name']}' добавлен в корзину.\n Количество: {cart[product_id]['quantity']}"),
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
        # Корзина пуста — показываем сообщение с кнопкой "Назад"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Назад", callback_data="back_to_menu")]
        ])
        message = await query.message.reply_text(
            text="Ваша корзина пуста.",
            reply_markup=keyboard
        )
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
             f"Доставка: {delivery_cost} руб. (От 1500р. в чеке - бесплатно)\nИтого: {final_price} руб.",
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
        # Корзина пуста — показываем сообщение с кнопкой "Назад"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Назад", callback_data="back_to_menu")]
        ])
        message = await query.message.reply_text(
            text="Ваша корзина теперь пуста.",
            reply_markup=keyboard
        )
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
             f"Доставка: {delivery_cost} руб. (От 1500р. в чеке - бесплатно)\nИтого: {final_price} руб.",
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
    keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Назад", callback_data="back_to_menu")]
        ])
    message = await query.message.reply_text(
        text="Ваша корзина теперь пуста.",
        reply_markup=keyboard
        )
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
             f"Доставка: {delivery_cost} руб.(От 1500р. в чеке - бесплатно)\nИтого: {final_price} руб.\n\n"
             "Пожалуйста, напишите адрес доставки, индекс, ФИО получателя и номер телефона:"
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

    # Проверяем, есть ли username у пользователя
    username = update.message.from_user.username
    phone_number = update.message.contact.phone_number if update.message.contact else None

    # Если username отсутствует, используем phone_number или user_id
    if not username:
        username = phone_number or f"user_{user_id}"

    # Сохраняем username и адрес доставки
    context.user_data[user_id]["username"] = username
    address = update.message.text
    context.user_data[user_id]["address"] = address

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
             f"Доставка: {delivery_cost} руб.(От 1500р. в чеке - бесплатно)\nИтого: {final_price} руб.\n\n"
             "Отсканируйте QR-код для оплаты."
            )
    else:
        await query.message.reply_text(
        text=f"Ваш заказ:\n{cart_text}\n\nОбщая сумма: {total_price} руб.\n"
             f"Доставка: {delivery_cost} руб.(От 1500р. в чеке - бесплатно)\nИтого: {final_price} руб.\n\n"
             "Номер карты для оплаты: 2202 2016 3095 5124")

    context.user_data[user_id]["payment_method"] = payment_method
    await query.message.reply_text("Пожалуйста, отправьте скриншот или PDF-файл подтверждения оплаты.")
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
        payment_proof_type = 'photo'
    elif update.message.document and update.message.document.mime_type.startswith('image'):
        # Если это изображение, отправленное как документ (например, .jpg, .png и т.д.)
        payment_proof = update.message.document.file_id
        payment_proof_type = 'document'
    elif update.message.document and update.message.document.mime_type == "application/pdf":
        # Если это PDF-документ
        payment_proof = update.message.document.file_id
        payment_proof_type = 'document'
    
    else:
        # Если тип сообщения не подходит
        await update.message.reply_text(
            "Пожалуйста, отправьте скриншот или PDF-документ с подтверждением оплаты."
        )
        return
    
    cart = context.user_data[user_id]["cart"]
    
    # Получаем категории товаров
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

    # Формируем строку с товарами и категориями
    formatted_items = []
    for pid, product_name, category_name in product_info:
        item = cart.get(str(pid))
        if item:
            quantity = item["quantity"]
            formatted_items.append(f"{product_name} x{quantity} ({category_name})")

    items = ", ".join(formatted_items)
    
    # Обновляем базу данных
    for product_id, item in cart.items():
        update_stock(product_id, item["quantity"])
    
    # Сохраняем подтверждение оплаты
    context.user_data[user_id]["payment_proof"] = payment_proof
    context.user_data[user_id]["payment_proof_type"] = payment_proof_type

    # Сохранение заказа
    cart = context.user_data[user_id]["cart"]
    address = context.user_data[user_id]["address"]
    total_price = sum(item["price"] * item["quantity"] for item in cart.values())
    delivery_cost = 0 if total_price >= 1500 else 400
    final_price = total_price + delivery_cost
    payment_method = context.user_data[user_id]["payment_method"]    

    save_order(
        user_id=user_id,
        username=context.user_data[user_id]["username"],  # Теперь это значение будет доступно
        items=items,
        address=address,
        total_price=final_price,
        payment_method=payment_method,
        payment_proof=payment_proof,
        payment_proof_type=payment_proof_type
    )

    # Отправка уведомления администратору
    admin_message = f"Новый заказ от пользователя @{context.user_data[user_id]['username']}:\n" \
                    f"Товары: {items}\n" \
                    f"Информация для доставки: {address}\n" \
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

    # Удаляем старое сообщение, если оно есть
    if "last_message_id" in context.user_data.get(user_id, {}):
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data[user_id]["last_message_id"]
            )
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

    # Подключаемся к базе данных и получаем все заказы пользователя
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT items, address, total_price, payment_method FROM orders WHERE user_id = ? ORDER BY id DESC', (user_id,))
    orders = cursor.fetchall()
    conn.close()    

    # Если заказов нет, — показываем сообщение с кнопкой "Назад"
    if not orders:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Назад", callback_data="back_to_menu")]
        ])
        message = await query.message.reply_text(
            text="У вас нет активных заказов.",
            reply_markup=keyboard
        )
        context.user_data[user_id]["last_message_id"] = message.message_id
        return

    # Формируем текст для всех заказов
    orders_text = []
    for idx, order in enumerate(orders, start=1):
        items, address, total_price, payment_method = order
        order_text = (
            f"Заказ #{idx}:\n"
            f"Товары: {items}\n"
            f"Информация для доставки: {address}\n"
            f"Сумма заказа: {total_price} руб.\n"
            f"Способ оплаты: {payment_method.capitalize()}\n"
            "-----------------------------"
        )
        orders_text.append(order_text)

    # Объединяем все заказы в один текст
    full_orders_text = "\n".join(orders_text)


    keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Назад", callback_data="back_to_menu")]
        ])
    # Отправляем сообщение с историей заказов
    message = await query.message.reply_text(
        text=f"История ваших заказов:\n{full_orders_text}",
            reply_markup=keyboard
    )

    # Сохраняем message_id
    context.user_data[user_id]["last_message_id"] = message.message_id
    
def document_is_image(update: Update, context):
    return bool(
        update.message.document and 
        update.message.document.mime_type and 
        update.message.document.mime_type.startswith('image/')
    ) 
    
# Основная функция
def main():
    # Инициализация базы данных
    init_db()
    add_test_products() # Добавляем тестовые товары, если база данных пуста

    # Замените 'YOUR_BOT_TOKEN' на токен, который вы получили от BotFather
    TOKEN = "7771688126:AAFtHtiBQFs_Hb8HMr91QvYNKG5Gx1QRG4E"
    ADMIN_CHAT_ID = "753866988"  # Замените на ID администратора

    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("update_stock", update_stock_admin)) # Обновить количество товара по ID
    application.add_handler(CommandHandler("view_all_orders", view_all_orders)) # Просмотр списка всех заказов от всех пользователей администратором
    application.add_handler(CallbackQueryHandler(show_products_by_category, pattern=r"^category_\d+$")) # Показать товары этой категории
    application.add_handler(CallbackQueryHandler(view_products, pattern="^view_products$")) # Показать категории товаров
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
    filters.PHOTO | filters.Document.ALL,
    handle_payment_proof
))

    # Запуск бота
    application.run_polling()
    print("Бот запущен...")

if __name__ == "__main__":
    main()