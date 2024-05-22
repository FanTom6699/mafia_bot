import logging
import telebot
from datetime import datetime
from telebot import types
import threading
from game import (
    load_game_data, save_game_data, start_new_game, handle_night_action_callback,
    handle_vote, players, game_in_progress, check_player_count, monitor_inactivity, update_last_active, bot_instance
)

API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
bot = telebot.TeleBot(API_TOKEN)
bot_instance = bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_game_data()


@bot.message_handler(commands=['start'])
def start_game(message):
    global game_in_progress
    chat_id = message.chat.id
    if game_in_progress:
        bot.send_message(chat_id, "Игра уже идет.")
        return

    players.clear()
    game_in_progress = False
    bot.send_message(chat_id, "Игра 'Мафия' начинается! Все желающие присоединиться, напишите /join.")


@bot.message_handler(commands=['join'])
def join(message):
    global players, game_in_progress
    chat_id = message.chat.id
    if game_in_progress:
        bot.send_message(chat_id, "Игра уже идет. Вы не можете присоединиться.")
        return

    if len(players) >= 8:
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
    if not game_in_progress and check_player_count(chat_id, bot):
        start_new_game(chat_id, bot)


@bot.callback_query_handler(func=lambda call: call.data.startswith('night_'))
def handle_night_action(call):
    handle_night_action_callback(call, bot)


@bot.callback_query_handler(func=lambda call: call.data.startswith('vote_'))
def handle_vote_action(call):
    handle_vote(call, bot)


# обновление мониторинга активности
def update_last_active(player_id):
    if player_id in players:
        players[player_id]['last_active'] = datetime.now()


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    update_last_active(message.from_user.id)


bot.polling(none_stop=True)
