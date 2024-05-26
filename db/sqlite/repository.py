import logging
import sqlite3
from cfg.config import DB_NAME_SQLITE


class DataBase:
    def __init__(self, TABLE_NAME, CREATE_TABLE):
        self.DB_NAME = DB_NAME_SQLITE
        self.TABLE_NAME = TABLE_NAME
        self.CREATE_TABLE = CREATE_TABLE

    def execute_query(self, query, data=None):
        try:
            with sqlite3.connect(self.DB_NAME) as connection:
                cursor = connection.cursor()

                if data:
                    cursor.execute(query, data)
                else:
                    cursor.execute(query)
                cursor = cursor.fetchall()
                connection.commit()
                return cursor

        except sqlite3.Error as e:
            logging.error("Ошибка при выполнении запроса:", e)

    def create_table(self):
        sql_query = self.CREATE_TABLE
        self.execute_query(sql_query)

    def update_data(self, user_id, column, value):

        sql_query = f'UPDATE {self.TABLE_NAME} SET {column} = {column} + ? WHERE user_id = ?;'
        data = (value, user_id)
        self.execute_query(sql_query, data)

    def get_data(self, column, user_id=None):
        if user_id:
            sql_query = f'SELECT {column} FROM {self.TABLE_NAME} WHERE user_id = ?;'
            data = (user_id,)
            result = self.execute_query(sql_query, data)
        else:
            sql_query = f'SELECT {column} FROM {self.TABLE_NAME};'
            result = self.execute_query(sql_query)
        return result

    def create_user(self, user_id, win, lose):

        sql_query = f'INSERT INTO {self.TABLE_NAME} (user_id, win, lose) VALUES (?, ?, ?);'
        data = (user_id, win, lose)
        self.execute_query(sql_query, data)
