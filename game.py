import threading
from time import time, sleep
import random
from telebot import types, TeleBot
from cfg.config import (API_TOKEN, MIN_USER_IN_GAME,
                        MAX_USER_IN_GAME, LOSE_MAFIA,
                        INACTIVITY_TIMEOUT, MARKUP_TG)
from db.sqlite.repository import DataBase
from db.sqlite.schema import TABLE_NAME_USERS, USERS_TABLE_CREATE
from db.json.dynamic_database import Json

table_chat = Json()
table_users = DataBase(TABLE_NAME_USERS, USERS_TABLE_CREATE)

bot = TeleBot(API_TOKEN)


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
        
        if role_name in ["Мафия", "Дон"]:
            # Send mafia composition to all mafia members
            message = f"{role_description}\n\n{mafia_composition}"
            if role_name == "Дон":
                message += "\n\n👑 Как Дон, ваш голос решающий при голосовании мафии!"
            bot.send_message(player_id, message)
        else:
            bot.send_message(player_id, role_description)
    
    bot.send_message(chat_id, "🌃| Игра началась! Ночь начинается.")
    table_chat.save_json_file_and_write(data)
    start_night_phase(chat_id)


def calculate_role_balance(num_players):
    """Calculate role distribution based on player count"""
    if num_players < 5:
        return {}
    
    # Base roles calculation
    if 5 <= num_players <= 6:
        mafia_count = 2  # 1 Don + 1 Mafia
        commissioner = 1
        doctor = 1
    elif 7 <= num_players <= 9:
        mafia_count = 3  # 1 Don + 2 Mafia
        commissioner = 1
        doctor = 1
    else:  # 10+ players (if ever expanded)
        mafia_count = 4  # 1 Don + 3 Mafia
        commissioner = 1
        doctor = 1
    
    civilians = num_players - mafia_count - commissioner - doctor
    
    return {
        'don': 1,
        'mafia': mafia_count - 1,  # Don is separate from regular mafia
        'commissioner': commissioner,
        'doctor': doctor,
        'civilian': civilians
    }

def get_role_description(role):
    """Get detailed role description"""
    descriptions = {
        'Дон': '👑 Дон мафии - Вы главарь мафии! Ваш голос решающий при голосовании мафии. Можете общаться с мафией в ЛС боту.',
        'Мафия': '🔪 Мафия - Вы член мафии! Голосуйте за жертву ночью. Можете общаться с другими мафиями в ЛС боту.',
        'Комиссар': '🕵️ Комиссар - Вы можете проверять игроков и стрелять в подозреваемых. Используйте меню в ЛС для действий.',
        'Доктор': '👨‍⚕️ Доктор - Вы можете спасти одного игрока за ночь от убийства мафии.',
        'Мирный житель': '👤 Мирный житель - Ваша цель найти и изгнать всю мафию. Участвуйте в дневных голосованиях.'
    }
    return descriptions.get(role, f'Ваша роль: {role}')

def assign_roles(chat_id, data):  # JSON DATABASE
    player_ids = list(data["chat_id"][chat_id]["players"].keys())
    random.shuffle(player_ids)
    num_players = len(player_ids)

    # Calculate role balance
    role_balance = calculate_role_balance(num_players)
    if not role_balance:
        return

    # Initialize data structures
    data["chat_id"][chat_id]["mafia"] = []
    data["chat_id"][chat_id]["don"] = None
    
    idx = 0
    
    # Assign Don
    if role_balance['don'] > 0:
        data["chat_id"][chat_id]["players"][player_ids[idx]]["roles"] = 'Дон'
        data["chat_id"][chat_id]["mafia"].append(player_ids[idx])
        data["chat_id"][chat_id]["don"] = player_ids[idx]
        idx += 1
    
    # Assign regular Mafia
    for _ in range(role_balance['mafia']):
        data["chat_id"][chat_id]["players"][player_ids[idx]]["roles"] = 'Мафия'
        data["chat_id"][chat_id]["mafia"].append(player_ids[idx])
        idx += 1
    
    # Assign Commissioner
    for _ in range(role_balance['commissioner']):
        data["chat_id"][chat_id]["players"][player_ids[idx]]["roles"] = 'Комиссар'
        idx += 1
    
    # Assign Doctor
    for _ in range(role_balance['doctor']):
        data["chat_id"][chat_id]["players"][player_ids[idx]]["roles"] = 'Доктор'
        idx += 1
    
    # Assign remaining as Civilians
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
            bot.send_message(player_id, "🔪| Голосуйте за цель для убийства:", reply_markup=markup)
        elif role["roles"] == 'Доктор':
            markup = types.InlineKeyboardMarkup()
            for target_id, target_name in data["chat_id"][chat_id]["players"].items():
                markup.add(
                    types.InlineKeyboardButton(text=target_name['name'],
                                               callback_data=f'night_save_{target_id}_{chat_id}'))
            bot.send_message(player_id, "⚙️| Выберите цель для 💊:", reply_markup=markup)
        elif role["roles"] == 'Комиссар':
            send_commissioner_menu(player_id, chat_id)

def send_commissioner_menu(player_id, chat_id):
    """Send commissioner action menu"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔎 Проверить", callback_data=f'comm_check_menu_{chat_id}'),
        types.InlineKeyboardButton("🔫 Стрелять", callback_data=f'comm_shoot_menu_{chat_id}')
    )
    bot.send_message(player_id, "🕵️| Выберите действие:", reply_markup=markup)


def handle_mafia_vote_callback(call):
    """Handle mafia voting"""
    data = table_chat.open_json_file_and_write()
    target_id = call.data.split('_')[2]
    chat_id = call.data.split('_')[3]
    voter_id = str(call.message.chat.id)
    
    # Record vote
    data["chat_id"][chat_id]["mafia_votes"][voter_id] = target_id
    data["chat_id"][chat_id]["players"][voter_id]['last_active'] = time()
    
    target_name = data["chat_id"][chat_id]["players"][target_id]["name"]
    bot.send_message(voter_id, f"🔪| Вы проголосовали за {target_name}")
    
    table_chat.save_json_file_and_write(data)
    
    # Check if all mafia voted
    mafia_count = len(data["chat_id"][chat_id]["mafia"])
    if len(data["chat_id"][chat_id]["mafia_votes"]) == mafia_count:
        determine_mafia_target(chat_id)

def determine_mafia_target(chat_id):
    """Determine mafia target based on votes and Don's decision"""
    data = table_chat.open_json_file_and_write()
    votes = data["chat_id"][chat_id]["mafia_votes"]
    
    # Count votes
    vote_counts = {}
    for target_id in votes.values():
        vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
    
    max_votes = max(vote_counts.values()) if vote_counts else 0
    top_targets = [target_id for target_id, count in vote_counts.items() if count == max_votes]
    
    # Don decides if there's a tie or if mafia count <= 2
    mafia_count = len(data["chat_id"][chat_id]["mafia"])
    don_id = data["chat_id"][chat_id]["don"]
    
    if len(top_targets) > 1 or mafia_count <= 2:
        if don_id and don_id in votes:
            # Don's vote is decisive
            final_target = votes[don_id]
        else:
            # Fallback to random if Don didn't vote
            final_target = random.choice(top_targets) if top_targets else None
    else:
        final_target = top_targets[0] if top_targets else None
    
    data["chat_id"][chat_id]["night_actions"]['Мафия'] = final_target
    table_chat.save_json_file_and_write(data)

def handle_commissioner_menu_callback(call):
    """Handle commissioner menu actions"""
    action = call.data.split('_')[1]  # 'check' or 'shoot'
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
    """Handle commissioner check/shoot actions"""
    data = table_chat.open_json_file_and_write()
    action_type = call.data.split('_')[1]  # 'check' or 'shoot'
    target_id = call.data.split('_')[2]
    chat_id = call.data.split('_')[3]
    player_id = str(call.message.chat.id)
    
    data["chat_id"][chat_id]["players"][player_id]['last_active'] = time()
    target_name = data["chat_id"][chat_id]["players"][target_id]["name"]
    target_role = data["chat_id"][chat_id]["players"][target_id]["roles"]
    
    if action_type == 'check':
        result_message = f"🔎| {target_name} является: {target_role}"
        bot.send_message(player_id, result_message)
        data["chat_id"][chat_id]["night_actions"]['Комиссар'] = target_id
    elif action_type == 'shoot':
        # Commissioner shoots - immediate kill regardless of doctor
        bot.send_message(player_id, f"🔫| Вы застрелили {target_name}")
        
        # Remove shot player
        if target_id not in data["chat_id"][chat_id]["admins"]:
            bot.restrict_chat_member(chat_id, target_id, until_date=int(time()) + 3600)
            data["chat_id"][chat_id]["mute_users"].append(target_id)
        
        table_users.update_data(target_id, "lose", 1)
        del data["chat_id"][chat_id]["players"][target_id]
        
        # Notify group
        bot.send_message(chat_id, f"🔫| {target_name} был застрелен Комиссаром. Он был {target_role}.")
        
        # Check for Don succession if Don was shot
        if target_role == "Дон":
            handle_don_succession(chat_id, data)
    
    table_chat.save_json_file_and_write(data)
    
    # Send menu again for unlimited actions
    send_commissioner_menu(player_id, chat_id)

def handle_don_succession(chat_id, data):
    """Handle Don succession when Don is eliminated"""
    remaining_mafia = [mid for mid in data["chat_id"][chat_id]["mafia"] 
                      if mid in data["chat_id"][chat_id]["players"] 
                      and data["chat_id"][chat_id]["players"][mid]["roles"] == "Мафия"]
    
    if remaining_mafia:
        new_don = remaining_mafia[0]  # First remaining mafia becomes Don
        data["chat_id"][chat_id]["don"] = new_don
        data["chat_id"][chat_id]["players"][new_don]["roles"] = "Дон"
        
        # Notify all remaining mafia
        for mafia_id in data["chat_id"][chat_id]["mafia"]:
            if mafia_id in data["chat_id"][chat_id]["players"]:
                player_name = data["chat_id"][chat_id]["players"][new_don]["name"]
                if mafia_id == new_don:
                    bot.send_message(mafia_id, f"👑| Вы стали новым Доном мафии!")
                else:
                    bot.send_message(mafia_id, f"👑| {player_name} стал новым Доном мафии!")

def handle_night_action_callback(call):
    data = table_chat.open_json_file_and_write()
    
    # Handle different callback types
    if call.data.startswith('mafia_vote_'):
        handle_mafia_vote_callback(call)
        return
    elif call.data.startswith('comm_check_menu_') or call.data.startswith('comm_shoot_menu_'):
        handle_commissioner_menu_callback(call)
        return
    elif call.data.startswith('comm_check_') or call.data.startswith('comm_shoot_'):
        handle_commissioner_action_callback(call)
        return
    
    # Original night action handling for doctor
    action, target_id, chat_id = call.data.split('_')[1], call.data.split('_')[2], call.data.split('_')[3]
    player_id = str(call.message.chat.id)
    data["chat_id"][chat_id]["players"][player_id]['last_active'] = time()
    role = data["chat_id"][chat_id]["players"][player_id]["roles"]

    if role == 'Доктор' and action == 'save':
        data["chat_id"][chat_id]["night_actions"]['Доктор'] = target_id
        bot.send_message(player_id, f"⚙️| Вы выбрали {data['chat_id'][chat_id]['players'][target_id]['name']}")
    
    table_chat.save_json_file_and_write(data)

    # Check if night can end (only need doctor action now, mafia votes handled separately)
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
    
    # Send commissioner check result if there was a check
    if check_target:
        check_result = f'🔎| {data["chat_id"][chat_id]["players"][check_target]["name"]} является {data["chat_id"][chat_id]["players"][check_target]["roles"]}.'
        for player_id, role in data["chat_id"][chat_id]["players"].items():
            if role["roles"] == 'Комиссар':
                bot.send_message(player_id, check_result)

    # Process mafia kill
    if kill_target and kill_target != save_target:
        player_name = data["chat_id"][chat_id]["players"][kill_target]["name"]
        player_role = data["chat_id"][chat_id]["players"][kill_target]["roles"]
        kill_result = f'{player_name} был убит. Он был {player_role}.'
        
        if kill_target not in data["chat_id"][chat_id]["admins"]:
            bot.restrict_chat_member(chat_id, kill_target, until_date=int(time()) + 3600)
            data["chat_id"][chat_id]["mute_users"].append(kill_target)
        
        table_users.update_data(kill_target, "lose", 1)
        
        # Check for Don succession if Don was killed
        if player_role == "Дон":
            handle_don_succession(chat_id, data)
            
        del data["chat_id"][chat_id]["players"][kill_target]

    bot.send_message(chat_id, kill_result)
    
    # Restore chat permissions for day phase
    for player_id in data["chat_id"][chat_id]["players"]:
        if player_id not in data["chat_id"][chat_id]["admins"]:
            bot.restrict_chat_member(chat_id, player_id, can_send_messages=True, can_send_media_messages=True,
                                     can_send_other_messages=True, can_add_web_page_previews=True)

    table_chat.save_json_file_and_write(data)
    
    if check_win_condition(chat_id):
        start_day_phase(chat_id)

def handle_mafia_chat_message(message):
    """Handle mafia chat messages sent to bot"""
    player_id = str(message.from_user.id)
    data = table_chat.open_json_file_and_write()
    
    # Find which chat this player belongs to and if they're mafia
    for chat_id in data["chat_id"]:
        if (data["chat_id"][chat_id]["game_in_progress"] and 
            player_id in data["chat_id"][chat_id]["players"] and
            data["chat_id"][chat_id]["players"][player_id]["roles"] in ["Мафия", "Дон"]):
            
            sender_name = data["chat_id"][chat_id]["players"][player_id]["name"]
            sender_role = data["chat_id"][chat_id]["players"][player_id]["roles"]
            
            # Forward message to all other mafia members
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
    data = table_chat.open_json_file_and_write()  # надо чат айди в json переделать чтобы не в лс последнему голосовавшему слал а в общую группу
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
                     f'🏃🚪| {data["chat_id"][chat_id]["players"][eliminated_id]["name"]} был изгнан. Он был {eliminated_role}.')
    
    if eliminated_id not in data["chat_id"][chat_id]["admins"]:
        bot.restrict_chat_member(chat_id, eliminated_id, until_date=int(time()) + 3600)
        data["chat_id"][chat_id]["mute_users"].append(eliminated_id)
    
    table_users.update_data(eliminated_id, "lose", 1)
    
    # Check for Don succession if Don was eliminated
    if eliminated_role == "Дон":
        handle_don_succession(chat_id, data)
    
    del data["chat_id"][chat_id]["players"][eliminated_id]
    table_chat.save_json_file_and_write(data)

    if check_win_condition(chat_id):
        start_night_phase(chat_id)


def check_win_condition(chat_id):  # здесь тоже самое переделать
    data = table_chat.open_json_file_and_write()
    mafia_count = sum(1 for role in data["chat_id"][chat_id]["players"].values() 
                     if role["roles"] in ['Мафия', 'Дон'])
    non_mafia_count = len(data["chat_id"][chat_id]["players"]) - mafia_count
    
    if mafia_count >= non_mafia_count:
        bot.send_message(chat_id, "🔪🩸| Мафия победила!")
        for player_id, role in data["chat_id"][chat_id]["players"].items():
            if role["roles"] in ["Мафия", "Дон"]:
                table_users.update_data(player_id, "win", 1)
        end_game(chat_id)
        return False
    elif mafia_count == LOSE_MAFIA:
        bot.send_message(chat_id, "🙎‍♂️| Мирные жители победили!")
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
    data = table_chat.open_json_file_and_write()  # SQL
    for chat_id in data["chat_id"]:
        if player_id in data["chat_id"][chat_id]["players"]:
            data["chat_id"][chat_id]["players"][player_id]['last_active'] = time()
            table_chat.save_json_file_and_write(data)
            return
    if chat_id_user in data["chat_id"] and data["chat_id"][chat_id_user]["game_in_progress"]:
        bot.delete_message(chat_id_user, message_id)
        if player_id not in data["chat_id"][chat_id_user]["admins"]:
            # Check if this player was Don before removing
            player_was_don = (player_id in data["chat_id"][chat_id_user]["players"] and 
                            data["chat_id"][chat_id_user]["players"][player_id]["roles"] == "Дон")
            
            bot.restrict_chat_member(chat_id_user, player_id,
                                     until_date=int(time()) + 3600)
            data["chat_id"][chat_id_user]["mute_users"].append(player_id)
            
            # Handle Don succession if needed
            if player_was_don:
                handle_don_succession(chat_id_user, data)
                
            table_chat.save_json_file_and_write(data)


inactivity_thread = threading.Thread(target=monitor_inactivity, daemon=True)
inactivity_thread.start()
