### Sunflow Cryptobot ###
#
# General functions

# Load external libraries
from pybit.unified_trading import WebSocket
from datetime import datetime, timezone
#from time import sleep

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
    
    # Logic
    factor = 1 / step_size
    value = (value * factor) // 1 / factor  # Using floor division in Python
    
    # Return rounded value
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
             near = min(abs((avg_price / min_price * 100) - 100), abs((avg_price / max_price * 100) - 100))
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

# Outputs a (Pass) or (Fail)
def report_result(result):

    # Initialize variable
    pafa = "(No buy)"

    # Logic
    if result:
        pafa = "(Buy)"
    else:
        pafa = "(No buy)"

    # Return result
    return pafa

# Determines buy decission and outputs to stdout
def decide_buy(technical_advice, use_indicators, spread_advice, use_spread, orderbook_advice, use_orderbook, interval):
            
    # Debug
    debug = False

    # Initialize variables
    can_buy = False
    message = "Buy matrix (" + str(interval) + "m): "

    # Get the intervals
    intervals = list(technical_advice.keys())

    # Create message for stdout
    if use_indicators['enabled']:
        if intervals[1] != 0:
            message += "TA-1 " + str(intervals[0]) + "m: " + str(round(technical_advice[intervals[0]]['value'], 2)) + " "
            message += report_result(technical_advice[intervals[0]]['result']) + ", "
            message += "TA-2 " + str(intervals[1]) + "m: " + str(round(technical_advice[intervals[1]]['value'], 2)) + " "
            message += report_result(technical_advice[intervals[1]]['result']) + ", "
        else:
            message += "TA " + str(intervals[0]) + "m: " + str(round(technical_advice[intervals[0]]['value'], 2)) + " "
            message += report_result(technical_advice[intervals[0]]['result']) + ", "
    if use_spread['enabled']:
        message += "Spread: " + str(spread_advice['nearest']) + "% "
        message += report_result(spread_advice['result']) + ", "
    
    if use_orderbook['enabled']:
        message += "Orderbook: " + str(orderbook_advice['value']) + "% "
        message += report_result(orderbook_advice['result']) + ", "

    if (technical_advice[intervals[0]]['result']) and technical_advice[intervals[1]]['result'] and (spread_advice['result']) and (orderbook_advice['result']):
        can_buy = True
        message += "BUY!"
    else:
        can_buy = False
        message += "NO BUY"

    # Debug
    if debug:
        print("\n\n*** Simplified buy reporting ***\n")

        print("Intervals:")
        print(intervals, "\n")

        print("Technical advice:")
        print(technical_advice, "\n")
        
        print("Spread advice:")
        print(spread_advice, "\n")
        
        print("Orderbook advice:")
        print(orderbook_advice, "\n")
    
    # Return result
    return can_buy, message

# Calculate price changes for spike detection 
def spikes(prices, use_spikes):

    # Initialize variables
    debug   = False
    spiking = False

    # Time calculations
    latest_time = prices['time'][-1]  # Get the latest time
    span = latest_time - use_spikes['interval']    # timeframe in milliseconds

    # Find the closest index to the time {timeframe} ago
    closest_index = None
    min_diff = float('inf')

    for i, t in enumerate(prices['time']):
        diff = abs(t - span)
        if diff < min_diff:
            min_diff = diff
            closest_index = i

    # Calculate the change in close price
    price_change = None
    if closest_index is not None and prices['time'][-1] > span:
        price_change      = prices['price'][-1] - prices['price'][closest_index]
        price_change_perc = (price_change / prices['price'][closest_index]) * 100

    # Output to stdout
    if abs(price_change_perc) > use_spikes['threshold']:
        print(defs.now_utc()[1] + "Defs: spikes: *** SPIKE DETECTED ***\n")
        spiking = True 

    if debug or spiking:
        print(defs.now_utc()[1] + "Defs: spikes: Price change in the last " + str(round((use_spikes['interval'] / 1000), 2)) +  " seconds is " + str(round(price_change_perc, 2)) + "%\n")

    # Return price change percentage
    return abs(price_change_perc), spiking