TABLE_NAME_USERS = 'users'
USERS_TABLE_CREATE = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME_USERS} (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            date INTEGER,
            win INTEGER,
            lose INTEGER
        );"""
