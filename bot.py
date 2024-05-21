import logging
import sqlite3

import telebot
from datetime import datetime
from game import (
    load_game_data, save_game_data, start_new_game, handle_night_action_callback,
    handle_vote, players, game_in_progress, check_player_count
)

API_TOKEN = ''
bot = telebot.TeleBot(API_TOKEN)

# логи
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
    bot.send_message(chat_id, "Игра 'Мафия' начинается! Чтобы присоедениться, напишите /join.")


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
        }
        bot.send_message(chat_id, f"{message.from_user.first_name} присоединился к игре.")
        save_game_data()


@bot.message_handler(commands=['stats'])
def show_stats(message):
    player_id = message.from_user.id
    with sqlite3.connect('mafia_stats.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT games_played, games_won FROM player_stats WHERE player_id=?", (player_id,))
        result = cursor.fetchone()

    if result:
        games_played, games_won = result
        bot.send_message(message.chat.id, f"Игр сыграно: {games_played}\nИгр выиграно: {games_won}")
    else:
        bot.send_message(message.chat.id, "Вы еще не играли в эту игру.")


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



bot.polling(none_stop=True)
