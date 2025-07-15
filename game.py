import threading
from time import time, sleep
import random
from telebot import types
from cfg.config import (MIN_USER_IN_GAME,
                        MAX_USER_IN_GAME, LOSE_MAFIA,
                        INACTIVITY_TIMEOUT, MARKUP_TG)
from db.sqlite.repository import DataBase
from db.sqlite.schema import TABLE_NAME_USERS, USERS_TABLE_CREATE
from db.json.dynamic_database import Json

table_chat = Json()
table_users = DataBase(TABLE_NAME_USERS, USERS_TABLE_CREATE)

# Bot instance will be injected from bot.py
bot = None

def set_bot_instance(bot_instance):
    global bot
    bot = bot_instance

def get_admins(chat_id):
    user_status = bot.get_chat_administrators(chat_id)
    user_admins = []
    for admins in user_status:
        user_admins.append(str(admins.user.id))
    return user_admins

def check_player_count(chat_id, data):
    if len(data["chat_id"][chat_id]["players"]) < MIN_USER_IN_GAME:
        bot.send_message(chat_id, f"⚙️| Для начала игры требуется минимум {MIN_USER_IN_GAME} игроков.")
        return False
    elif len(data["chat_id"][chat_id]["players"]) > MAX_USER_IN_GAME:
        bot.send_message(chat_id, f"⚙️| Максимальное количество игроков - {MAX_USER_IN_GAME}.")
        return False
    return True

def get_role_description(role):
    """Get detailed role description"""
    descriptions = {
        'Дон': (
            "👑 Вы Дон мафии! Ваш голос решающий при голосовании мафии.\n"
            "Вам доступны ночные голосования, чат мафии и право окончательного решения."
        ),
        'Мафия': (
            "🔪 Вы член мафии! Ваши цели — избавиться от мирных жителей.\n"
            "Вам доступны ночные голосования и чат мафии."
        ),
        'Комиссар': (
            "🕵️‍♂️ Вы комиссар! Можете проверять игроков или стрелять в подозреваемых.\n"
            "Используйте ночное меню в ЛС."
        ),
        'Доктор': (
            "👨‍⚕️ Вы доктор! Можете спасти одного игрока за ночь от убийства мафии.\n"
            "Будьте внимательны и старайтесь спасти мирных жителей."
        ),
        'Мирный житель': (
            "👤 Вы мирный житель. Ваша цель — найти и изгнать мафию.\n"
            "Участвуйте в дневных обсуждениях и голосованиях."
        ),
    }
    return descriptions.get(role, f'Ваша роль: {role}')

def start_new_game(chat_id):
    data = table_chat.open_json_file_and_write()
    data["chat_id"][chat_id]["game_in_progress"] = True
    assign_roles(chat_id, data)
    
    # Send role descriptions and mafia composition
    mafia_composition = ""
    if data["chat_id"][chat_id]["mafia"]:
        mafia_names = []
        for mafia_id in data["chat_id"][chat_id]["mafia"]:
            player_name = data["chat_id"][chat_id]["players"][mafia_id]["name"]
            player_role = data["chat_id"][chat_id]["players"][mafia_id]["roles"]
            mafia_names.append(f"{player_name} ({player_role})")
        mafia_composition = "🔪 Состав мафии:\n" + "\n".join(mafia_names)
    
    for player_id, role in data["chat_id"][chat_id]["players"].items():
        role_name = role["roles"]
        role_description = get_role_description(role_name)
        
        # Отправляем описание роли с шаблоном для каждой роли
        bot.send_message(player_id, role_description)
        # Если игрок — мафия, отправляем состав мафии
        if role_name in ["Мафия", "Дон"]:
            bot.send_message(player_id, mafia_composition)
            if role_name == "Дон":
                bot.send_message(player_id, "👑 Как Дон, ваш голос решающий при голосовании мафии!")

    bot.send_message(chat_id, "🌃| Игра началась! Ночь начинается.")
    table_chat.save_json_file_and_write(data)
    start_night_phase(chat_id)

def calculate_role_balance(num_players):
    """Calculate role distribution based on player count"""
    if num_players < 5:
        return {}
    if 5 <= num_players <= 6:
        mafia_count = 2  # 1 Don + 1 Mafia
        commissioner = 1
        doctor = 1
    elif 7 <= num_players <= 9:
        mafia_count = 3  # 1 Don + 2 Mafia
        commissioner = 1
        doctor = 1
    else:  # 10+ players
        mafia_count = 4  # 1 Don + 3 Mafia
        commissioner = 1
        doctor = 1
    civilians = num_players - mafia_count - commissioner - doctor
    return {
        'don': 1,
        'mafia': mafia_count - 1,
        'commissioner': commissioner,
        'doctor': doctor,
        'civilian': civilians
    }

def assign_roles(chat_id, data):
    player_ids = list(data["chat_id"][chat_id]["players"].keys())
    random.shuffle(player_ids)
    num_players = len(player_ids)

    role_balance = calculate_role_balance(num_players)
    if not role_balance:
        return

    data["chat_id"][chat_id]["mafia"] = []
    data["chat_id"][chat_id]["don"] = None
    
    idx = 0
    if role_balance['don'] > 0:
        data["chat_id"][chat_id]["players"][player_ids[idx]]["roles"] = 'Дон'
        data["chat_id"][chat_id]["mafia"].append(player_ids[idx])
        data["chat_id"][chat_id]["don"] = player_ids[idx]
        idx += 1
    for _ in range(role_balance['mafia']):
        data["chat_id"][chat_id]["players"][player_ids[idx]]["roles"] = 'Мафия'
        data["chat_id"][chat_id]["mafia"].append(player_ids[idx])
        idx += 1
    for _ in range(role_balance['commissioner']):
        data["chat_id"][chat_id]["players"][player_ids[idx]]["roles"] = 'Комиссар'
        idx += 1
    for _ in range(role_balance['doctor']):
        data["chat_id"][chat_id]["players"][player_ids[idx]]["roles"] = 'Доктор'
        idx += 1
    for i in range(idx, num_players):
        data["chat_id"][chat_id]["players"][player_ids[i]]["roles"] = 'Мирный житель'
    table_chat.save_json_file_and_write(data)

def start_night_phase(chat_id):
    data = table_chat.open_json_file_and_write()
    data["chat_id"][chat_id]["night_actions"] = {'Мафия': {}, 'Доктор': None, 'Комиссар': None}
    data["chat_id"][chat_id]["mafia_votes"] = {}
    table_chat.save_json_file_and_write(data)
    bot.send_message(chat_id,
                     "🌃| Мафия, Доктор и Комиссар, проверьте свои личные сообщения для выполнения действий.",
                     reply_markup=MARKUP_TG)
    for player_id in data["chat_id"][chat_id]["players"]:
        if player_id not in data["chat_id"][chat_id]["admins"]:
            bot.restrict_chat_member(chat_id, player_id,
                                     until_date=int(time()) + 3600)

    for player_id, role in data["chat_id"][chat_id]["players"].items():
        if role["roles"] in ['Мафия', 'Дон']:
            # Mafia voting interface
            markup = types.InlineKeyboardMarkup()
            for target_id, target_name in data["chat_id"][chat_id]["players"].items():
                if target_id != player_id and target_name["roles"] not in ['Мафия', 'Дон']:
                    markup.add(
                        types.InlineKeyboardButton(text=target_name['name'],
                                                   callback_data=f'mafia_vote_{target_id}_{chat_id}'))
            # Мафии отправляем шаблон ночного действия
            bot.send_message(player_id, "🔪 Ночь наступила. Голосуйте за жертву в меню!", reply_markup=markup)
            if role["roles"] == "Дон":
                bot.send_message(player_id, "👑 Как Дон, вы можете принять окончательное решение по жертве мафии этой ночью.")
        elif role["roles"] == 'Доктор':
            markup = types.InlineKeyboardMarkup()
            for target_id, target_name in data["chat_id"][chat_id]["players"].items():
                markup.add(
                    types.InlineKeyboardButton(text=target_name['name'],
                                               callback_data=f'night_save_{target_id}_{chat_id}'))
            bot.send_message(player_id, "💊 Ночь наступила. Выберите, кого хотите спасти!", reply_markup=markup)
        elif role["roles"] == 'Комиссар':
            send_commissioner_menu(player_id, chat_id)
            bot.send_message(player_id, "🕵️‍♂️ Ночь наступила. Выберите действие: проверить или застрелить игрока!")

def send_commissioner_menu(player_id, chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔎 Проверить", callback_data=f'comm_check_menu_{chat_id}'),
        types.InlineKeyboardButton("🔫 Стрелять", callback_data=f'comm_shoot_menu_{chat_id}')
    )
    bot.send_message(player_id, "🕵️| Выберите действие:", reply_markup=markup)

def handle_mafia_vote_callback(call):
    data = table_chat.open_json_file_and_write()
    target_id = call.data.split('_')[2]
    chat_id = call.data.split('_')[3]
    voter_id = str(call.message.chat.id)
    data["chat_id"][chat_id]["mafia_votes"][voter_id] = target_id
    data["chat_id"][chat_id]["players"][voter_id]['last_active'] = time()
    target_name = data["chat_id"][chat_id]["players"][target_id]["name"]
    bot.send_message(voter_id, f"🔪| Вы проголосовали за {target_name}")
    table_chat.save_json_file_and_write(data)
    mafia_count = len(data["chat_id"][chat_id]["mafia"])
    if len(data["chat_id"][chat_id]["mafia_votes"]) == mafia_count:
        determine_mafia_target(chat_id)

def determine_mafia_target(chat_id):
    data = table_chat.open_json_file_and_write()
    votes = data["chat_id"][chat_id]["mafia_votes"]
    vote_counts = {}
    for target_id in votes.values():
        vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
    max_votes = max(vote_counts.values()) if vote_counts else 0
    top_targets = [target_id for target_id, count in vote_counts.items() if count == max_votes]
    mafia_count = len(data["chat_id"][chat_id]["mafia"])
    don_id = data["chat_id"][chat_id]["don"]
    if len(top_targets) > 1 or mafia_count <= 2:
        if don_id and don_id in votes:
            final_target = votes[don_id]
        else:
            final_target = random.choice(top_targets) if top_targets else None
    else:
        final_target = top_targets[0] if top_targets else None
    data["chat_id"][chat_id]["night_actions"]['Мафия'] = final_target
    table_chat.save_json_file_and_write(data)
    if final_target:
        bot.send_message(final_target, "🔪 Этой ночью мафия выбрала вас своей целью...")

def handle_commissioner_menu_callback(call):
    action = call.data.split('_')[1]
    chat_id = call.data.split('_')[3]
    player_id = str(call.message.chat.id)
    data = table_chat.open_json_file_and_write()
    markup = types.InlineKeyboardMarkup()
    for target_id, target_name in data["chat_id"][chat_id]["players"].items():
        if target_id != player_id:
            callback_prefix = 'comm_check' if action == 'check' else 'comm_shoot'
            markup.add(
                types.InlineKeyboardButton(
                    text=target_name['name'],
                    callback_data=f'{callback_prefix}_{target_id}_{chat_id}'
                )
            )
    action_text = "🔎 проверить" if action == 'check' else "🔫 застрелить"
    bot.send_message(player_id, f"🕵️| Выберите цель для {action_text}:", reply_markup=markup)

def handle_commissioner_action_callback(call):
    data = table_chat.open_json_file_and_write()
    action_type = call.data.split('_')[1]
    target_id = call.data.split('_')[2]
    chat_id = call.data.split('_')[3]
    player_id = str(call.message.chat.id)
    data["chat_id"][chat_id]["players"][player_id]['last_active'] = time()
    target_name = data["chat_id"][chat_id]["players"][target_id]["name"]
    target_role = data["chat_id"][chat_id]["players"][target_id]["roles"]
    if action_type == 'check':
        # Комиссар
        result_message = (
            "🕵️‍♂️ Ночная проверка завершена.\n"
            "Роль игрока:\n"
            f"{target_name} — {target_role}"
        )
        bot.send_message(player_id, result_message)
        data["chat_id"][chat_id]["night_actions"]['Комиссар'] = target_id
        # Проверяемый игрок
        checked_message = (
            "🕵️‍♂️ Этой ночью комиссар зашёл к вам с проверкой документов.\n"
            "С этого момента ваша роль больше не секрет для него."
        )
        bot.send_message(target_id, checked_message)
    elif action_type == 'shoot':
        bot.send_message(player_id, f"🔫| Вы застрелили {target_name}")
        if target_id not in data["chat_id"][chat_id]["admins"]:
            bot.restrict_chat_member(chat_id, target_id, until_date=int(time()) + 3600)
            data["chat_id"][chat_id]["mute_users"].append(target_id)
        table_users.update_data(target_id, "lose", 1)
        del data["chat_id"][chat_id]["players"][target_id]
        bot.send_message(chat_id, f"🔫| {target_name} был застрелен Комиссаром. Он был {target_role}.")
        if target_role == "Дон":
            handle_don_succession(chat_id, data)
    table_chat.save_json_file_and_write(data)
    send_commissioner_menu(player_id, chat_id)

def handle_don_succession(chat_id, data):
    remaining_mafia = [mid for mid in data["chat_id"][chat_id]["mafia"] 
                      if mid in data["chat_id"][chat_id]["players"] 
                      and data["chat_id"][chat_id]["players"][mid]["roles"] == "Мафия"]
    if remaining_mafia:
        new_don = remaining_mafia[0]
        data["chat_id"][chat_id]["don"] = new_don
        data["chat_id"][chat_id]["players"][new_don]["roles"] = "Дон"
        for mafia_id in data["chat_id"][chat_id]["mafia"]:
            if mafia_id in data["chat_id"][chat_id]["players"]:
                player_name = data["chat_id"][chat_id]["players"][new_don]["name"]
                if mafia_id == new_don:
                    bot.send_message(mafia_id, f"👑| Вы стали новым Доном мафии!")
                else:
                    bot.send_message(mafia_id, f"👑| {player_name} стал новым Доном мафии!")

def handle_night_action_callback(call):
    data = table_chat.open_json_file_and_write()
    if call.data.startswith('mafia_vote_'):
        handle_mafia_vote_callback(call)
        return
    elif call.data.startswith('comm_check_menu_') or call.data.startswith('comm_shoot_menu_'):
        handle_commissioner_menu_callback(call)
        return
    elif call.data.startswith('comm_check_') or call.data.startswith('comm_shoot_'):
        handle_commissioner_action_callback(call)
        return
    action, target_id, chat_id = call.data.split('_')[1], call.data.split('_')[2], call.data.split('_')[3]
    player_id = str(call.message.chat.id)
    data["chat_id"][chat_id]["players"][player_id]['last_active'] = time()
    role = data["chat_id"][chat_id]["players"][player_id]["roles"]
    if role == 'Доктор' and action == 'save':
        data["chat_id"][chat_id]["night_actions"]['Доктор'] = target_id
        bot.send_message(player_id, f"⚙️| Вы выбрали {data['chat_id'][chat_id]['players'][target_id]['name']}")
    table_chat.save_json_file_and_write(data)
    doctor_action = data["chat_id"][chat_id]["night_actions"]['Доктор']
    mafia_action = data["chat_id"][chat_id]["night_actions"]['Мафия']
    if doctor_action is not None and mafia_action is not None:
        end_night_phase(chat_id)

def end_night_phase(chat_id):
    data = table_chat.open_json_file_and_write()
    kill_target = data["chat_id"][chat_id]["night_actions"]['Мафия']
    save_target = data["chat_id"][chat_id]["night_actions"]['Доктор']
    check_target = data["chat_id"][chat_id]["night_actions"]['Комиссар']
    kill_result = 'Никто не был ☠️.'
    # Комиссар получает результат проверки, проверяемый игрок — уведомление уже отправлялись
    # Обработка спасения доктором
    if kill_target and kill_target == save_target:
        bot.send_message(kill_target, "💊 Этой ночью вас спас доктор!")
    # Обработка убийства мафией
    if kill_target and kill_target != save_target:
        player_name = data["chat_id"][chat_id]["players"][kill_target]["name"]
        player_role = data["chat_id"][chat_id]["players"][kill_target]["roles"]
        kill_result = f'{player_name} был убит. Он был {player_role}.'
        if kill_target not in data["chat_id"][chat_id]["admins"]:
            bot.restrict_chat_member(chat_id, kill_target, until_date=int(time()) + 3600)
            data["chat_id"][chat_id]["mute_users"].append(kill_target)
        table_users.update_data(kill_target, "lose", 1)
        if player_role == "Дон":
            handle_don_succession(chat_id, data)
        del data["chat_id"][chat_id]["players"][kill_target]
    bot.send_message(chat_id, kill_result)
    for player_id in data["chat_id"][chat_id]["players"]:
        if player_id not in data["chat_id"][chat_id]["admins"]:
            bot.restrict_chat_member(chat_id, player_id, can_send_messages=True, can_send_media_messages=True,
                                     can_send_other_messages=True, can_add_web_page_previews=True)
    table_chat.save_json_file_and_write(data)
    if check_win_condition(chat_id):
        start_day_phase(chat_id)

def handle_mafia_chat_message(message):
    player_id = str(message.from_user.id)
    data = table_chat.open_json_file_and_write()
    for chat_id in data["chat_id"]:
        if (data["chat_id"][chat_id]["game_in_progress"] and 
            player_id in data["chat_id"][chat_id]["players"] and
            data["chat_id"][chat_id]["players"][player_id]["roles"] in ["Мафия", "Дон"]):
            sender_name = data["chat_id"][chat_id]["players"][player_id]["name"]
            sender_role = data["chat_id"][chat_id]["players"][player_id]["roles"]
            for mafia_id in data["chat_id"][chat_id]["mafia"]:
                if mafia_id != player_id and mafia_id in data["chat_id"][chat_id]["players"]:
                    role_icon = "👑" if sender_role == "Дон" else "🔪"
                    bot.send_message(mafia_id, f"{role_icon} {sender_name}: {message.text}")
            break

def start_day_phase(chat_id):
    data = table_chat.open_json_file_and_write()
    bot.send_message(chat_id, "🏙️| День начался. Дается одна минута на переговоры.")
    sleep(60)
    for player_id, player_info in data["chat_id"][chat_id]["players"].items():
        markup = types.InlineKeyboardMarkup()
        for target_id, target_info in data["chat_id"][chat_id]["players"].items():
            if target_id != player_id:
                markup.add(
                    types.InlineKeyboardButton(text=target_info['name'], callback_data=f'vote_{target_id}_{chat_id}'))
        bot.send_message(player_id, "📢| Голосуйте за подозреваемого:", reply_markup=markup)
    bot.send_message(chat_id, "📢💬| Голосование в лс", reply_markup=MARKUP_TG)
    data["chat_id"][chat_id]["votes"] = {}
    table_chat.save_json_file_and_write(data)

def handle_vote(call):
    data = table_chat.open_json_file_and_write()
    voter_id = str(call.message.chat.id)
    target_id = call.data.split('_')[1]
    chat_id = call.data.split('_')[2]
    data["chat_id"][chat_id]["players"][voter_id]['last_active'] = time()
    data["chat_id"][chat_id]["votes"][voter_id] = target_id
    bot.send_message(voter_id, f"📢| Вы проголосовали за {data['chat_id'][chat_id]['players'][target_id]['name']}")
    table_chat.save_json_file_and_write(data)
    if len(data["chat_id"][chat_id]["votes"]) == len(data['chat_id'][chat_id]['players']):
        end_day_phase(chat_id)

def end_day_phase(chat_id):
    data = table_chat.open_json_file_and_write()
    vote_counts = {}
    for target_id in data["chat_id"][chat_id]["votes"].values():
        if target_id in vote_counts:
            vote_counts[target_id] += 1
        else:
            vote_counts[target_id] = 1
    max_votes = max(vote_counts.values())
    to_eliminate = [target_id for target_id, count in vote_counts.items() if count == max_votes]
    if len(to_eliminate) == 1:
        eliminated_id = to_eliminate[0]
    else:
        eliminated_id = random.choice(to_eliminate)
    eliminated_role = data["chat_id"][chat_id]["players"][eliminated_id]["roles"]
    bot.send_message(chat_id,
                     f'🏃🚪 {data["chat_id"][chat_id]["players"][eliminated_id]["name"]} был изгнан. Он был {eliminated_role}.')
    bot.send_message(eliminated_id, "🏃🚪 Вас изгнали из города. Игра для вас окончена.")
    if eliminated_id not in data["chat_id"][chat_id]["admins"]:
        bot.restrict_chat_member(chat_id, eliminated_id, until_date=int(time()) + 3600)
        data["chat_id"][chat_id]["mute_users"].append(eliminated_id)
    table_users.update_data(eliminated_id, "lose", 1)
    if eliminated_role == "Дон":
        handle_don_succession(chat_id, data)
    del data["chat_id"][chat_id]["players"][eliminated_id]
    table_chat.save_json_file_and_write(data)
    if check_win_condition(chat_id):
        start_night_phase(chat_id)

def check_win_condition(chat_id):
    data = table_chat.open_json_file_and_write()
    mafia_count = sum(1 for role in data["chat_id"][chat_id]["players"].values() 
                     if role["roles"] in ['Мафия', 'Дон'])
    non_mafia_count = len(data["chat_id"][chat_id]["players"]) - mafia_count
    if mafia_count >= non_mafia_count:
        bot.send_message(chat_id, "🔪🩸 Мафия победила! Все мирные жители проиграли.")
        for player_id, role in data["chat_id"][chat_id]["players"].items():
            if role["roles"] in ["Мафия", "Дон"]:
                table_users.update_data(player_id, "win", 1)
        end_game(chat_id)
        return False
    elif mafia_count == LOSE_MAFIA:
        bot.send_message(chat_id, "🙎‍♂️ Мирные жители победили! Все мафиози изгнаны.")
        for player_id, role in data["chat_id"][chat_id]["players"].items():
            if role["roles"] not in ["Мафия", "Дон"]:
                table_users.update_data(player_id, "win", 1)
        end_game(chat_id)
        return False
    return True

def monitor_inactivity():
    while True:
        data = table_chat.open_json_file_and_write()
        now = time()
        for chat_id in data["chat_id"]:
            if data["chat_id"][chat_id]["game_in_progress"]:
                for player_id, player_info in data["chat_id"][chat_id]["players"].items():
                    last_active = player_info.get('last_active')
                    if last_active and now - last_active > INACTIVITY_TIMEOUT:
                        end_game_due_to_inactivity(player_id, chat_id)
                        break
        sleep(60)

def end_game_due_to_inactivity(player_id, chat_id):
    data = table_chat.open_json_file_and_write()
    bot.send_message(chat_id,
                     f'⚙️| Игра завершена из-за неактивности игрока {data["chat_id"][chat_id]["players"][player_id]["name"]}.')
    for user_id in data["chat_id"][chat_id]["mute_users"]:
        bot.restrict_chat_member(chat_id, user_id, can_send_messages=True, can_send_media_messages=True,
                                 can_send_other_messages=True, can_add_web_page_previews=True)
    del data["chat_id"][chat_id]
    table_chat.save_json_file_and_write(data)

def end_game(chat_id):
    data = table_chat.open_json_file_and_write()
    for user_id in data["chat_id"][chat_id]["mute_users"]:
        bot.restrict_chat_member(chat_id, user_id, can_send_messages=True, can_send_media_messages=True,
                                 can_send_other_messages=True, can_add_web_page_previews=True)
    del data["chat_id"][chat_id]
    table_chat.save_json_file_and_write(data)

def update_last_active(player_id, chat_id_user, message_id):
    data = table_chat.open_json_file_and_write()
    for chat_id in data["chat_id"]:
        if player_id in data["chat_id"][chat_id]["players"]:
            data["chat_id"][chat_id]["players"][player_id]['last_active'] = time()
            table_chat.save_json_file_and_write(data)
            return
    if chat_id_user in data["chat_id"] and data["chat_id"][chat_id_user]["game_in_progress"]:
        bot.delete_message(chat_id_user, message_id)
        if player_id not in data["chat_id"][chat_id_user]["admins"]:
            player_was_don = (player_id in data["chat_id"][chat_id_user]["players"] and 
                            data["chat_id"][chat_id_user]["players"][player_id]["roles"] == "Дон")
            bot.restrict_chat_member(chat_id_user, player_id,
                                     until_date=int(time()) + 3600)
            data["chat_id"][chat_id_user]["mute_users"].append(player_id)
            if player_was_don:
                handle_don_succession(chat_id_user, data)
            table_chat.save_json_file_and_write(data)

inactivity_thread = threading.Thread(target=monitor_inactivity, daemon=True)
inactivity_thread.start()
