import json
from config import DB_NAME_JSON


class Json:
    def __init__(self):
        self.data_name = DB_NAME_JSON

    def open_json_file_and_write(self):
        with open(self.data_name, encoding="utf-8") as file:
            data = json.load(file)
        return data

    def save_json_file_and_write(self, data):
        with open(self.data_name, 'w', encoding='utf-8') as outfile:
            json.dump(data, outfile, ensure_ascii=False, indent=4)
