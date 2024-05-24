import logging
import telebot
from datetime import datetime
import threading
from game import (
    load_game_data, save_game_data,
    start_new_game, handle_night_action_callback,
    handle_vote, players,
    game_in_progress, check_player_count,
    monitor_inactivity, update_last_active
)

from config import API_TOKEN, MAX_USER_IN_GAME


bot = telebot.TeleBot(API_TOKEN)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_game_data()


@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Игра 'Мафия' начинается! Все желающие присоединиться, напишите /join.")


@bot.message_handler(commands=['join'])
def join(message):
    chat_id = message.chat.id
    if game_in_progress:
        bot.send_message(chat_id, "Игра уже идет. Вы не можете присоединиться.")
        return

    if len(players) >= MAX_USER_IN_GAME:
        bot.send_message(chat_id, "Игра уже достигла максимального количества игроков (8).")
        return

    player_id = message.from_user.id
    if player_id in players:
        bot.send_message(chat_id, "Вы уже присоединились к игре.")
    else:
        players[player_id] = {
            'name': message.from_user.first_name,
            'last_active': datetime.now(),
            'chat_id': chat_id
        }
        bot.send_message(chat_id, f"{message.from_user.first_name} присоединился к игре.")
        save_game_data()


@bot.message_handler(commands=['begin'])
def begin_game(message):
    chat_id = message.chat.id
    if not game_in_progress and check_player_count(chat_id):
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

bot.polling(none_stop=True)
