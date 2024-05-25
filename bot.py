import logging
import telebot
from time import time
import threading
from game import (start_new_game, handle_night_action_callback,
                  handle_vote, check_player_count,
                  monitor_inactivity, update_last_active
                  )
from config import API_TOKEN, MAX_USER_IN_GAME, MARKUP_TG
from db.sqlite.repository import DataBase
from db.sqlite.schema import TABLE_NAME_USERS, USERS_TABLE_CREATE
from db.json.dynamic_database import Json

table_chat = Json()
table_users = DataBase(TABLE_NAME_USERS, USERS_TABLE_CREATE)
table_users.create_table()

bot = telebot.TeleBot(API_TOKEN)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    if str(chat_id)[0] == "-":
        bot.send_message(chat_id, "Данная команда работает только в лс бота", reply_markup=MARKUP_TG)
        return
    result = table_users.get_data("user_id", message.from_user.id)
    if not result:
        table_users.create_user(message.from_user.id, 0, 0)
        bot.send_message(chat_id, "Вы авторизованы, можете играть в мафию.")
    else:
        bot.send_message(chat_id, "Вы уже авторизованы.")


@bot.message_handler(commands=['start_game'])  # Проверка на чат это или нет, удаления чата
def start_game(message):
    chat_id = str(message.chat.id)
    if chat_id[0] != "-":
        bot.send_message(chat_id, "Данная команда работает только в группе")
        return
    data = table_chat.open_json_file_and_write()
    data["chat_id"][chat_id] = {"players": {},
                                "game_in_progress": False,
                                "night_actions": {},
                                "votes": {},
                                "mute_users": []}
    table_chat.save_json_file_and_write(data)
    bot.send_message(chat_id, "Игра 'Мафия' начинается! Все желающие присоединиться, напишите /join.")


@bot.message_handler(commands=['join'])
def join(message):
    chat_id = str(message.chat.id)
    if chat_id[0] != "-":
        bot.send_message(chat_id, "Данная команда работает только в группе")
        return
    data = table_chat.open_json_file_and_write()

    if chat_id not in data["chat_id"]:
        bot.send_message(int(chat_id), "Игру еще не начали.")
        return

    result = table_users.get_data("user_id", message.from_user.id)
    if not result:
        bot.send_message(int(chat_id), "Вы не авторизовались в боте.\nНапишите /start боту.")
        return

    if data["chat_id"][chat_id]["game_in_progress"]:
        bot.send_message(int(chat_id), "Игра уже идет. Вы не можете присоединиться.")
        return

    if len(data["chat_id"][chat_id]["players"]) >= MAX_USER_IN_GAME:
        bot.send_message(int(chat_id), f"Игра уже достигла максимального количества игроков ({MAX_USER_IN_GAME}).")
        return

    player_id = str(message.from_user.id)
    if player_id in data["chat_id"][chat_id]["players"]:
        bot.send_message(int(chat_id), "Вы уже присоединились к игре.")
    else:
        data["chat_id"][chat_id]["players"][player_id] = {
            'name': message.from_user.first_name,
            'last_active': time(),
            "role": None
        }
        bot.send_message(chat_id, f"{message.from_user.first_name} присоединился к игре.")
        table_chat.save_json_file_and_write(data)


@bot.message_handler(commands=['begin'])
def begin_game(message):
    chat_id = str(message.chat.id)
    if chat_id[0] != "-":
        bot.send_message(chat_id, "Данная команда работает только в группе")
        return
    data = table_chat.open_json_file_and_write()
    if not data["chat_id"][chat_id]["game_in_progress"] and check_player_count(chat_id, data):
        start_new_game(chat_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('night_'))
def handle_night_action(call):
    handle_night_action_callback(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith('vote_'))
def handle_vote_action(call):
    handle_vote(call)


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    update_last_active(message.from_user.id)


inactivity_thread = threading.Thread(target=monitor_inactivity, daemon=True)
inactivity_thread.start()

if __name__ == "__main__":
    bot.infinity_polling()
