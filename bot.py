from telebot import TeleBot, types
from cfg.text_in_bot import *
from cfg.config import API_TOKEN, MAX_USER_IN_GAME

bot = TeleBot(API_TOKEN)
registration_data = {}  # chat_id: {'players': [user_ids], 'names': {user_id: name}, 'msg_id': int}

# Initialize game module with our bot instance
import game
game.set_bot_instance(bot)

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

@bot.message_handler(commands=['start_game'])
def start_game(message):
    chat_id = message.chat.id
    if str(chat_id)[0] != "-":
        bot.send_message(chat_id, "⚙️| Команда работает только в группе.")
        return
    registration_data[chat_id] = {'players': [], 'names': {}, 'msg_id': None}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Зайти в игру", callback_data="join_game"))
    text = get_registration_text(registration_data[chat_id]['players'], registration_data[chat_id]['names'])
    msg = bot.send_message(chat_id, text, reply_markup=markup)
    bot.pin_chat_message(chat_id, msg.message_id)
    registration_data[chat_id]['msg_id'] = msg.message_id

def get_registration_text(players, names):
    max_players = MAX_USER_IN_GAME
    text = f"🎮 Идёт набор в игру Мафия!\n"
    text += f"Игроки: {len(players)}/{max_players}\n"
    if players:
        text += "Участники:\n" + "\n".join([f"- {names[uid]}" for uid in players])
    else:
        text += "Нет участников. Нажмите кнопку ниже, чтобы присоединиться!"
    text += "\n\nЧтобы выйти из регистрации, нажмите '❌ Выйти'."
    return text

@bot.callback_query_handler(func=lambda call: call.data == "join_game")
def join_game(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    user_name = call.from_user.first_name
    if chat_id not in registration_data:
        bot.answer_callback_query(call.id, "Игра не запущена!")
        return
    if user_id in registration_data[chat_id]['players']:
        bot.answer_callback_query(call.id, "Вы уже в игре!")
        return
    if len(registration_data[chat_id]['players']) >= MAX_USER_IN_GAME:
        bot.answer_callback_query(call.id, "Максимум игроков!")
        return
    registration_data[chat_id]['players'].append(user_id)
    registration_data[chat_id]['names'][user_id] = user_name
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Зайти в игру", callback_data="join_game"))
    markup.add(types.InlineKeyboardButton("❌ Выйти", callback_data="leave_game"))
    text = get_registration_text(registration_data[chat_id]['players'], registration_data[chat_id]['names'])
    bot.edit_message_text(text, chat_id, registration_data[chat_id]['msg_id'], reply_markup=markup)
    bot.answer_callback_query(call.id, "Вы успешно зарегистрировались!")

@bot.callback_query_handler(func=lambda call: call.data == "leave_game")
def leave_game(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    if chat_id not in registration_data or user_id not in registration_data[chat_id]['players']:
        bot.answer_callback_query(call.id, "Вы не зарегистрированы в игре!")
        return
    registration_data[chat_id]['players'].remove(user_id)
    registration_data[chat_id]['names'].pop(user_id, None)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Зайти в игру", callback_data="join_game"))
    markup.add(types.InlineKeyboardButton("❌ Выйти", callback_data="leave_game"))
    text = get_registration_text(registration_data[chat_id]['players'], registration_data[chat_id]['names'])
    bot.edit_message_text(text, chat_id, registration_data[chat_id]['msg_id'], reply_markup=markup)
    bot.answer_callback_query(call.id, "Вы вышли из регистрации!")

@bot.message_handler(commands=['help'])
def handler_help(message):
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['rules'])
def handler_rules(message):
    bot.send_message(message.chat.id, rules_text)

@bot.message_handler(commands=['stats'])
def handler_stats(message):
    from db.sqlite.repository import get_player_stats
    stats = get_player_stats(message.from_user.id)
    bot.send_message(message.chat.id, f"Ваши победы: {stats['win']}, поражения: {stats['lose']}")

@bot.message_handler(commands=['top'])
def handler_top(message):
    from db.sqlite.repository import get_top_players
    top = get_top_players()
    msg = "🏆 ТОП игроков:\n" + "\n".join([f"{p['name']}: {p['win']} побед" for p in top])
    bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['begin'])
def handler_begin(message):
    from game import start_new_game, check_player_count, table_chat
    chat_id = message.chat.id
    if chat_id not in registration_data or not registration_data[chat_id]['players']:
        bot.send_message(chat_id, "Нет зарегистрированных игроков для начала игры.")
        return
    data = table_chat.open_json_file_and_write()
    if str(chat_id) not in data["chat_id"]:
        data["chat_id"][str(chat_id)] = {
            "players": {},
            "game_in_progress": False,
            "mafia": [],
            "don": None,
            "mute_users": [],
            "admins": []
        }
    for user_id in registration_data[chat_id]['players']:
        player_name = registration_data[chat_id]['names'][user_id]
        data["chat_id"][str(chat_id)]["players"][str(user_id)] = {
            "name": player_name,
            "roles": "",
            "last_active": 0
        }
    table_chat.save_json_file_and_write(data)
    if check_player_count(str(chat_id), data):
        start_new_game(str(chat_id))
        try:
            bot.unpin_chat_message(chat_id, registration_data[chat_id]['msg_id'])
        except Exception:
            pass
        registration_data.pop(chat_id, None)
    else:
        bot.send_message(chat_id, "Недостаточно игроков для начала игры.")

@bot.message_handler(commands=['leave'])
def cmd_leave(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    if chat_id not in registration_data or user_id not in registration_data[chat_id]['players']:
        bot.send_message(chat_id, f"{user_name}, вы не зарегистрированы в игре.")
    else:
        registration_data[chat_id]['players'].remove(user_id)
        registration_data[chat_id]['names'].pop(user_id, None)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Зайти в игру", callback_data="join_game"))
        markup.add(types.InlineKeyboardButton("❌ Выйти", callback_data="leave_game"))
        text = get_registration_text(registration_data[chat_id]['players'], registration_data[chat_id]['names'])
        bot.edit_message_text(text, chat_id, registration_data[chat_id]['msg_id'], reply_markup=markup)
        bot.send_message(chat_id, f"{user_name}, вы вышли из регистрации.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('night_', 'vote_', 'mafia_vote_', 'comm_')))
def handle_game_callbacks(call):
    from game import handle_night_action_callback, handle_vote
    if call.data.startswith('vote_'):
        handle_vote(call)
    else:
        handle_night_action_callback(call)

@bot.message_handler(func=lambda message: message.chat.type == 'private' and not message.text.startswith('/'))
def handle_private_messages(message):
    from game import handle_mafia_chat_message
    handle_mafia_chat_message(message)

if __name__ == "__main__":
    bot.infinity_polling()
