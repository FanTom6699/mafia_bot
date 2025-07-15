from telebot import TeleBot, types
from cfg.text_in_bot import *
from cfg.config import API_TOKEN, MAX_USER_IN_GAME

bot = TeleBot(API_TOKEN)
registration_data = {}  # chat_id: {'players': [usernames], 'msg_id': int}

# --- Команды меню для Telegram ---
private_commands = [
    types.BotCommand("start", "🟢 Авторизация и инструкция"),
    types.BotCommand("help", "🆘 Справка по боту"),
    types.BotCommand("rules", "📜 Правила игры"),
    types.BotCommand("stats", "📊 Ваша статистика"),
]
group_commands = [
    types.BotCommand("start_game", "🏁 Начать новую игру"),
    types.BotCommand("join", "🔗 Присоединиться к игре"),
    types.BotCommand("leave", "❌ Выйти из игры"),
    types.BotCommand("begin", "🚩 Запустить фазу игры"),
    types.BotCommand("cancel", "🚫 Отменить игру"),
    types.BotCommand("top", "🔝 ТОП игроков чата"),
]

bot.set_my_commands(private_commands, scope=types.BotCommandScopeAllPrivateChats())
bot.set_my_commands(group_commands, scope=types.BotCommandScopeAllGroupChats())

# ---- Приветствие при добавлении в группу ----
@bot.message_handler(content_types=['new_chat_members'])
def greet_new_chat_members(message):
    for new_member in message.new_chat_members:
        if new_member.id == bot.get_me().id:
            bot.send_message(message.chat.id, start_text)

# ---- Старт регистрации ----
@bot.message_handler(commands=['start_game'])
def start_game(message):
    chat_id = message.chat.id
    if str(chat_id)[0] != "-":
        bot.send_message(chat_id, "⚙️| Команда работает только в группе.")
        return
    registration_data[chat_id] = {'players': [], 'msg_id': None}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Зайти в игру", callback_data="join_game"))
    text = get_registration_text(registration_data[chat_id]['players'])
    msg = bot.send_message(chat_id, text, reply_markup=markup)
    bot.pin_chat_message(chat_id, msg.message_id)
    registration_data[chat_id]['msg_id'] = msg.message_id

def get_registration_text(players):
    max_players = MAX_USER_IN_GAME
    text = f"🎮 Идёт набор в игру Мафия!\n"
    text += f"Игроки: {len(players)}/{max_players}\n"
    if players:
        text += "Участники:\n" + "\n".join([f"- {name}" for name in players])
    else:
        text += "Нет участников. Нажмите кнопку ниже, чтобы присоединиться!"
    text += "\n\nЧтобы выйти из регистрации, нажмите '❌ Выйти'."
    return text

# ---- Кнопка Зайти в игру ----
@bot.callback_query_handler(func=lambda call: call.data == "join_game")
def join_game(call):
    chat_id = call.message.chat.id
    user_name = call.from_user.first_name
    if chat_id not in registration_data:
        bot.answer_callback_query(call.id, "Игра не запущена!")
        return
    if user_name in registration_data[chat_id]['players']:
        bot.answer_callback_query(call.id, "Вы уже в игре!")
        return
    if len(registration_data[chat_id]['players']) >= MAX_USER_IN_GAME:
        bot.answer_callback_query(call.id, "Максимум игроков!")
        return
    registration_data[chat_id]['players'].append(user_name)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Зайти в игру", callback_data="join_game"))
    markup.add(types.InlineKeyboardButton("❌ Выйти", callback_data="leave_game"))
    text = get_registration_text(registration_data[chat_id]['players'])
    bot.edit_message_text(text, chat_id, registration_data[chat_id]['msg_id'], reply_markup=markup)
    bot.answer_callback_query(call.id, "Вы успешно зарегистрировались!")

# ---- Кнопка Выйти ----
@bot.callback_query_handler(func=lambda call: call.data == "leave_game")
def leave_game(call):
    chat_id = call.message.chat.id
    user_name = call.from_user.first_name
    if chat_id not in registration_data or user_name not in registration_data[chat_id]['players']:
        bot.answer_callback_query(call.id, "Вы не зарегистрированы в игре!")
        return
    registration_data[chat_id]['players'].remove(user_name)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Зайти в игру", callback_data="join_game"))
    markup.add(types.InlineKeyboardButton("❌ Выйти", callback_data="leave_game"))
    text = get_registration_text(registration_data[chat_id]['players'])
    bot.edit_message_text(text, chat_id, registration_data[chat_id]['msg_id'], reply_markup=markup)
    bot.answer_callback_query(call.id, "Вы вышли из регистрации!")

# ---- Отмена регистрации ----
@bot.message_handler(commands=['cancel'])
def cancel_registration(message):
    chat_id = message.chat.id
    if chat_id in registration_data:
        if registration_data[chat_id]['msg_id']:
            bot.unpin_chat_message(chat_id, registration_data[chat_id]['msg_id'])
        registration_data.pop(chat_id)
        bot.send_message(chat_id, "🚫 Набор в игру отменён.")
    else:
        bot.send_message(chat_id, "Нет активной регистрации.")

# ---- Остальные команды ----
@bot.message_handler(commands=['help'])
def handler_help(message):
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['rules'])
def handler_rules(message):
    bot.send_message(message.chat.id, rules_text)

@bot.message_handler(commands=['stats'])
def handler_stats(message):
    bot.send_message(message.chat.id, "Статистика пока не реализована.")

@bot.message_handler(commands=['top'])
def handler_top(message):
    bot.send_message(message.chat.id, "Топ игроков пока не реализован.")

@bot.message_handler(commands=['begin'])
def handler_begin(message):
    chat_id = message.chat.id
    if chat_id not in registration_data or not registration_data[chat_id]['players']:
        bot.send_message(chat_id, "Нет зарегистрированных игроков для начала игры.")
        return
    bot.send_message(chat_id, "Игра началась! (реализация логики игры будет тут)")
    # Можно откреплять меню регистрации, если нужно:
    try:
        bot.unpin_chat_message(chat_id, registration_data[chat_id]['msg_id'])
    except Exception: pass
    registration_data.pop(chat_id, None)

@bot.message_handler(commands=['leave'])
def cmd_leave(message):
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    if chat_id not in registration_data or user_name not in registration_data[chat_id]['players']:
        bot.send_message(chat_id, f"{user_name}, вы не зарегистрированы в игре.")
    else:
        registration_data[chat_id]['players'].remove(user_name)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Зайти в игру", callback_data="join_game"))
        markup.add(types.InlineKeyboardButton("❌ Выйти", callback_data="leave_game"))
        text = get_registration_text(registration_data[chat_id]['players'])
        bot.edit_message_text(text, chat_id, registration_data[chat_id]['msg_id'], reply_markup=markup)
        bot.send_message(chat_id, f"{user_name}, вы вышли из регистрации.")

if __name__ == "__main__":
    bot.infinity_polling()
