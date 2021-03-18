import gspread
import threading
import queue
import time

def read_kbd_input(inputQueue):
    print('Ready for keyboard input:')
    while (True):
        input_str = input()
        inputQueue.put(input_str)


def main():
    # access spreadsheet
    gc = gspread.service_account(filename='credentials.json')
    ss = gc.open_by_key(' prepped organic standard inventory key goes here')
    scan = ss.worksheet('Scan')

    EXIT_COMMAND = "exit"
    inputQueue = queue.Queue()

    inputThread = threading.Thread(target=read_kbd_input, args=(inputQueue,), daemon=True)
    inputThread.start()

    while (True):
        if (inputQueue.qsize() > 0):
            input_str = inputQueue.get()
            print("input_str = {}".format(input_str))

            if (input_str == EXIT_COMMAND):
                print("Exiting serial terminal.")
                break

            # Insert your code here to do whatever you want with the input_str.
            scan.insert_row([input_str], index=1, value_input_option='RAW') # add a row with string

        # The rest of your program goes here.

        time.sleep(0.01) 
    print("End.")

if (__name__ == '__main__'): 
    main()


