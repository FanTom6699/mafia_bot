import json
import random
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from telebot import types

players = {}
game_in_progress = False
votes = {}
db_lock = threading.Lock()

def load_game_data():
    global players
    try:
        with open('game_data.json', 'r') as f:
            players = json.load(f)
    except FileNotFoundError:
        players = {}

def save_game_data():
    with open('game_data.json', 'w') as f:
        json.dump(players, f)

def start_new_game(chat_id, bot):
    global game_in_progress
    if not check_player_count(chat_id, bot):
        return

    assign_roles()
    notify_roles(bot)
    game_in_progress = True
    bot.send_message(chat_id, "Игра начинается! Наступает ночь.")
    night_phase(chat_id, bot)

def check_player_count(chat_id, bot):
    if len(players) < 5:
        bot.send_message(chat_id, "Недостаточно игроков для начала игры. Нужно минимум 5 игроков.")
        return False
    return True

def assign_roles():
    roles = ['mafia', 'doctor', 'detective'] + ['villager'] * (len(players) - 3)
    random.shuffle(roles)
    for player_id, role in zip(players, roles):
        players[player_id]['role'] = role
        players[player_id]['alive'] = True

def notify_roles(bot):
    for player_id, player_info in players.items():
        bot.send_message(player_id, f"Ваша роль: {player_info['role']}")

def night_phase(chat_id, bot):
    bot.send_message(chat_id, "Наступает ночь. Мафия, доктор и детектив, проверьте свои личные сообщения.")
    for player_id, player_info in players.items():
        if player_info['role'] == 'mafia':
            markup = types.InlineKeyboardMarkup()
            for target_id, target_info in players.items():
                if target_id != player_id and target_info['alive']:
                    markup.add(types.InlineKeyboardButton(target_info['name'], callback_data=f"night_kill_{target_id}"))
            bot.send_message(player_id, "Выберите цель для убийства:", reply_markup=markup)
        elif player_info['role'] == 'doctor':
            markup = types.InlineKeyboardMarkup()
            for target_id, target_info in players.items():
                if target_info['alive']:
                    markup.add(types.InlineKeyboardButton(target_info['name'], callback_data=f"night_save_{target_id}"))
            bot.send_message(player_id, "Выберите цель для спасения:", reply_markup=markup)
        elif player_info['role'] == 'detective':
            markup = types.InlineKeyboardMarkup()
            for target_id, target_info in players.items():
                if target_id != player_id and target_info['alive']:
                    markup.add(types.InlineKeyboardButton(target_info['name'], callback_data=f"night_check_{target_id}"))
            bot.send_message(player_id, "Выберите цель для проверки:", reply_markup=markup)

def handle_night_action_callback(callback_query, bot):
    data = callback_query.data.split('_')
    action = data[1]
    target_id = int(data[2])
    player_id = callback_query.from_user.id

    if action == 'kill':
        players[player_id]['night_action'] = ('kill', target_id)
        bot.send_message(player_id, f"Вы выбрали цель для убийства: {players[target_id]['name']}")
    elif action == 'save':
        players[player_id]['night_action'] = ('save', target_id)
        bot.send_message(player_id, f"Вы выбрали цель для спасения: {players[target_id]['name']}")
    elif action == 'check':
        players[player_id]['night_action'] = ('check', target_id)
        bot.send_message(player_id, f"Вы выбрали цель для проверки: {players[target_id]['name']}")

    # проверка на ночные действия
    if all('night_action' in player_info for player_id, player_info in players.items() if player_info['role'] in ['mafia', 'doctor', 'detective']):
        resolve_night_actions(callback_query.message.chat.id, bot)


def resolve_night_actions(chat_id, bot):
    kill_target = None
    save_target = None
    check_target = None

    for player_id, player_info in players.items():
        if player_info['role'] == 'mafia':
            kill_target = player_info['night_action'][1]
        elif player_info['role'] == 'doctor':
            save_target = player_info['night_action'][1]
        elif player_info['role'] == 'detective':
            check_target = player_info['night_action'][1]

    if kill_target is not None and kill_target != save_target:
        players[kill_target]['alive'] = False

    night_report = "Ночь прошла:\n"
    if kill_target is not None:
        if kill_target == save_target:
            night_report += f"Доктор спас {players[kill_target]['name']}.\n"
        else:
            night_report += f"Мафия убила {players[kill_target]['name']}.\n"

    if check_target is not None:
        night_report += f"Детектив проверил {players[check_target]['name']}. Его роль: {players[check_target]['role']}.\n"

    for player_id, player_info in players.items():
        bot.send_message(player_id, night_report)

    day_phase(chat_id, bot)


def day_phase(chat_id, bot):
    bot.send_message(chat_id, "Наступает день. Обсудите и проголосуйте за игрока, которого хотите изгнать.")
    initiate_voting(chat_id, bot)

def initiate_voting(chat_id, bot):
    global votes
    votes = {}
    markup = types.InlineKeyboardMarkup()
    for player_id, player_info in players.items():
        if player_info['alive']:
            markup.add(types.InlineKeyboardButton(player_info['name'], callback_data=f"vote_{player_id}"))
    bot.send_message(chat_id, "За кого проголосуешь?", reply_markup=markup)

def handle_vote(callback_query, bot):
    voter_id = callback_query.from_user.id
    if voter_id in votes:
        bot.send_message(callback_query.message.chat.id, "Вы уже проголосовали.")
        return

    target_id = int(callback_query.data.split('_')[1])
    votes[voter_id] = target_id
    bot.send_message(callback_query.message.chat.id, f"{players[voter_id]['name']} проголосовал за {players[target_id]['name']}.")

    if len(votes) == len([player for player in players.values() if player['alive']]):
        tally_votes(callback_query.message.chat.id, bot)

def tally_votes(chat_id, bot):
    vote_counts = {}
    for target_id in votes.values():
        if target_id in vote_counts:
            vote_counts[target_id] += 1
        else:
            vote_counts[target_id] = 1

    if vote_counts:
        most_voted = max(vote_counts, key=vote_counts.get)
        players[most_voted]['alive'] = False
        bot.send_message(chat_id, f"Игрок {players[most_voted]['name']} был изгнан. Его роль: {players[most_voted]['role']}")

    check_game_end(chat_id, bot)

def check_game_end(chat_id, bot):
    mafia_count = sum(1 for player in players.values() if player['role'] == 'mafia' and player['alive'])
    citizen_count = sum(1 for player in players.values() if player['role'] != 'mafia' and player['alive'])

    if mafia_count >= citizen_count:
        bot.send_message(chat_id, "Мафия побеждает!")
        end_game(chat_id, "mafia", bot)
    elif mafia_count == 0:
        bot.send_message(chat_id, "Мирные жители побеждают!")
        end_game(chat_id, "citizens", bot)
    else:
        bot.send_message(chat_id, "Игра продолжается. Начинается ночь.")
        night_phase(chat_id, bot)

def end_game(chat_id, winner, bot):
    global game_in_progress, players
    game_in_progress = False
    update_stats(winner)
    players.clear()
    save_game_data()
    bot.send_message(chat_id, "Игра окончена. Вы можете начать новую игру с помощью команды /start.")

def update_stats(winner):
    global players, db_lock
    with db_lock:
        conn = sqlite3.connect('mafia_stats.db')
        cursor = conn.cursor()
        for player_id in players:
            cursor.execute("SELECT games_played, games_won FROM player_stats WHERE player_id=?", (player_id,))
            result = cursor.fetchone()
            if result:
                games_played, games_won = result
                games_played += 1
                if (winner == "mafia" and players[player_id]['role'] == 'mafia') or (winner == "citizens" and players[player_id]['role'] != 'mafia'):
                    games_won += 1
                cursor.execute("UPDATE player_stats SET games_played=?, games_won=? WHERE player_id=?", (games_played, games_won, player_id))
            else:
                games_played = 1
                games_won = 1 if (winner == "mafia" and players[player_id]['role'] == 'mafia') or (winner == "citizens" and players[player_id]['role'] != 'mafia') else 0
                cursor.execute("INSERT INTO player_stats (player_id, games_played, games_won) VALUES (?, ?, ?)", (player_id, games_played, games_won))
        conn.commit()
        conn.close()
