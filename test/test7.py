# import json

# my_dict = {
#     'version': "1.0.0",
#     'files': [
#         'credentials.json',
#         'scanner.py',
#         'logo.png',
#         'stylesheet.qss'
#     ]
# }

# with open("manifest.json", "w") as manifest:
#     json.dump(my_dict, manifest)

# with open("manifest.json") as manifest:
#     new_json = json.load(manifest)

# print(new_json)

# import configparser

# config = configparser.ConfigParser()
# config.read('config.ini')

# SPREADSHEET_KEY = config['SETTINGS']['spreadsheet_key']
# print(SPREADSHEET_KEY)

# config["SETTINGS"]["first_row"] = "2"

# print(config["SETTINGS"]["first_row"])
def dothing():
    try:
        1/0
        print("try block")
        return
    except ZeroDivisionError:
        print("Exception handled")
    
    raise ZeroDivisionError("This was raised outside the try/except block.")

dothing()
