### Sunflow Cryptobot ###
#
# General functions

# Load external libraries
from pybit.unified_trading import WebSocket
from datetime import datetime, timezone
from time import sleep

# Load internal libraries
import config, defs

# Initialize variables
debug = False

# Add new kline and remove the oldest
def new_kline(kline, klines):

    # Add new kline
    klines['time'].append(kline['time'])
    klines['open'].append(kline['open'])
    klines['high'].append(kline['high'])
    klines['low'].append(kline['low'])
    klines['close'].append(kline['close'])
    klines['volume'].append(kline['volume'])
    klines['turnover'].append(kline['turnover'])
    
    # Remove first kline
    klines['time'].pop(0)
    klines['open'].pop(0)
    klines['high'].pop(0)
    klines['low'].pop(0)
    klines['close'].pop(0)
    klines['volume'].pop(0)
    klines['turnover'].pop(0)

    # Return klines
    return klines

# Remove the first kline and replace with fresh kline
def update_kline(kline, klines): 

    # Remove last kline
    klines['time'].pop()
    klines['open'].pop()
    klines['high'].pop()
    klines['low'].pop()
    klines['close'].pop()
    klines['volume'].pop()
    klines['turnover'].pop()
    
    # Add new kline
    klines['time'].append(kline['time'])
    klines['open'].append(kline['open'])
    klines['high'].append(kline['high'])
    klines['low'].append(kline['low'])
    klines['close'].append(kline['close'])
    klines['volume'].append(kline['volume'])
    klines['turnover'].append(kline['turnover'])

    # Return klines
    return klines

# Round value to the nearest stepSize
def precision(value, step_size=0.1):
    
    factor = 1 / step_size
    value = (value * factor) // 1 / factor  # Using floor division in Python
    return value

# Check if there are no adjacent orders already 
def check_spread(all_buys, spot, spread):

    # Debug
    debug = False

    # Initialize variables
    near    = 0
    can_buy = True

    # Get the boundaries
    min_price = spot * (1 - (spread / 100))
    max_price = spot * (1 + (spread / 100))

    # Loop through the all buys
    for transaction in all_buys:
        avg_price = transaction["avgPrice"]
        if (avg_price >= min_price) and (avg_price <= max_price):
             can_buy = False
             near = min((avg_price / min_price * 100) - 100, (avg_price / max_price * 100) - 100)
             break
         
    if debug:
        if can_buy:
            print(defs.now_utc()[1] + "Defs: check_spread: No adjacent order found, we can buy")
        else:
            print(defs.now_utc()[1] + "Defs: check_spread: Adjacent order found, we can't buy")

    # Return buy advice
    return can_buy, near

# Return timestamp according to UTC
def now_utc():
    
    # Current UTC datetime
    current_time = datetime.now(timezone.utc)
    milliseconds = round(current_time.microsecond / 10000) / 100
    timestamp_0 = current_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}'
    timestamp_1 = current_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}' + " | "
    timestamp_2 = str(milliseconds)
    timestamp_3 = str(milliseconds) + " | "
    
    return timestamp_0, timestamp_1, timestamp_2, timestamp_3

# Log all responses from exchange
def log_exchange(response, message):
    
    # Create log message   
    to_log = now_utc()[1] + message
    
    # Extend log message based on error level
    if config.error_level == 0:
        to_log = message + "\n" + str(response) + "\n\n"
    
    # Write to exchange log file
    with open(config.exchange_file, 'a', encoding='utf-8') as file:
        file.write(to_log)

# Log all errors
def log_error(exception):
    
    # Debug
    debug = False

    # Output debug
    if debug:
        print(defs.now_utc()[1] + "Defs: log_exchange: Debug")
        print("Exception RAW:")
        print(exception)
        print()
        print("Exception STRING:")
        print(str(exception))
        print()
       
    # Initialize variables
    halt_execution = True
    
    # Safeguard from type errors
    exception = str(exception)

    # Add timestamp to exception
    exception = now_utc()[1] + exception + "\n"

    if ("(ErrCode: 12940)" in exception) or ("RemoteDisconnected" in exception):
        print(defs.now_utc()[1] + "Defs: log_error: *** Warning: Remote Disconnected! ***\n")
        halt_execution = False
    
    # Write to error log file
    with open(config.error_file, 'a', encoding='utf-8') as file:
        file.write(exception)
    
    # Output to stdout
    print(defs.now_utc()[1] + "Defs: log_error: Displaying exception:\n")
    print(exception)
    
    # Terminate hard
    if halt_execution:
        print(defs.now_utc()[1] + "Defs: error: *** Termination program, error to severe! ***\n")
        print(exception)
        exit()
