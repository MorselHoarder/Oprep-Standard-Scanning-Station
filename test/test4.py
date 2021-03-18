import gspread
from time import sleep


gc = gspread.service_account(filename='credentials.json')
ss = gc.open_by_key('') # test spreadsheet
scan = ss.worksheet('Scan')

# API_error_count = 0
# try:
#     scan.insert_row("hello")
# except gspread.exceptions.APIError as e:
#     if e.
#     API_error_count += 1
#     print(f"APIError count: {API_error_count}")
#     sleep(300*API_error_count)
# except Exception as e:
#     print("Other exception at gspread.insert_rows: ", e, " Retrying in 10 minutes.")
#     sleep(600)
# else: 
#     sleep(2.5)
#     API_error_count = 0

try:
    scan.insert_row("hello")
except gspread.exceptions.APIError as e:
    print(e.response.json()['error']['status'])
    print(f"API rate limit exceeded. Retrying in 5 minutes. Cycle number: {API_error_count}")