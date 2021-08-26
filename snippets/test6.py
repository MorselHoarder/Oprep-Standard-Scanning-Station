
import json


SCRIPT_VERSION = "1.0.0"
QUEUE_DUMP_FILE = "queue_dump.json"
QUEUE_ITEMS_KEY = "queue_items"


def readQueueFromJSON():
    "Gets any queue items from queue_dump.json and puts them into the queue."
    try: 
        with open(QUEUE_DUMP_FILE) as queue_dump:
            data_dict = json.load(queue_dump)
    except FileNotFoundError:
        print("no file found")
        return
    
    for item in data_dict[QUEUE_ITEMS_KEY]:
        print(item)
        if isinstance(item, dict):
            func_name = item.get('function')
            if func_name == 'insert_row':
                print('insert_row')
            elif func_name == 'delete_rows':
                print('delete_rows')
    


if __name__ == '__main__':
    readQueueFromJSON()