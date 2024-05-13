### Sunflow Cryptobot ###
#
# General functions

# Load external libraries
from pathlib import Path
from pybit.unified_trading import WebSocket
from datetime import datetime, timezone
import apprise, argparse, importlib, math, re, sys, time

# Load internal libraries
import defs, indicators

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', default='config.py')
args = parser.parse_args()

# Resolve config file path
config_path = Path(args.config).resolve()
if not config_path.exists():
    print(f"Config file not found at {config_path}, aborting...\n")
    sys.exit()

# Dynamically load the config module
sys.path.append(str(config_path.parent))
config_module_name = config_path.stem
config = importlib.import_module(config_module_name)

# Create an Apprise instance
apobj = apprise.Apprise()

# Add all of the notification urls for Apprise
for url in config.notify_urls:
    apobj.add(url)

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

# Round value to the nearest step size
def precision(value, step_size):
    
    # Logic
    if step_size < 1:
        decimal_places = -int(math.log10(step_size))
        factor = 10 ** decimal_places
    else:
        factor = 1 / step_size

    # Round down
    rounded_value = math.floor(value * factor) / factor

    # Return rounded value    
    return rounded_value

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
    timestamp_0  = current_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}'
    timestamp_1  = current_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}' + " | " + config.symbol + ": "
    timestamp_2  = milliseconds
    timestamp_3  = str(milliseconds) + " | "
    timestamp_4  = int(time.time() * 1000)
    
    return timestamp_0, timestamp_1, timestamp_2, timestamp_3, timestamp_4

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
        defs.notify("Terminating Sunflow, error to severe!", 1)
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
def decide_buy(indicators_advice, use_indicators, spread_advice, use_spread, orderbook_advice, use_orderbook, interval, intervals):
            
    # Debug
    debug = False

    # Initialize variables
    do_buy    = {}
    do_buy[1] = False
    do_buy[2] = False
    do_buy[3] = False
    do_buy[4] = False
    do_buy[5] = False    
    can_buy   = False
    message   = ""
   
    # Regular update or grid bot style
    if interval != 0:
        message = "Update " + str(interval) + "m: "

    # Report and check indicators
    if use_indicators['enabled']:    
        if intervals[1] != 0:
            if indicators_advice[intervals[1]]['result']:
                do_buy[1] = True
            message += str(intervals[1]) + "m: " + str(round(indicators_advice[intervals[1]]['value'], 2)) + " "
            message += report_result(indicators_advice[intervals[1]]['result']) + ", "
        else:
            do_buy[1] = True
        if intervals[2] != 0:
            if indicators_advice[intervals[2]]['result']:
                do_buy[2] = True
            message += str(intervals[2]) + "m: " + str(round(indicators_advice[intervals[2]]['value'], 2)) + " "
            message += report_result(indicators_advice[intervals[2]]['result']) + ", "
        else:
            do_buy[2] = True
        if intervals[3] != 0:
            if indicators_advice[intervals[3]]['result']:
                do_buy[3] = True
            message += str(intervals[3]) + "m: " + str(round(indicators_advice[intervals[3]]['value'], 2)) + " "
            message += report_result(indicators_advice[intervals[3]]['result']) + ", "                
        else:
            do_buy[3] = True
    else:
        do_buy[1] = True
        do_buy[2] = True
        do_buy[3] = True

    # Report spread
    if use_spread['enabled']:
        if spread_advice['result']:
            do_buy[4] = True
        message += "Spread: " + str(spread_advice['nearest']) + "% "
        message += report_result(spread_advice['result']) + ", "
    else:
        do_buy[4] = True
    
    # Report orderbook
    if use_orderbook['enabled']:
        if orderbook_advice['result']:
            do_buy[5] = True
        message += "Orderbook: " + str(orderbook_advice['value']) + "% "
        message += report_result(orderbook_advice['result']) + ", "
    else:
        do_buy[5] = True

    # Determine buy decission
    if do_buy[1] and do_buy[2] and do_buy[3] and do_buy[4] and do_buy[5]:
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

        print("Indicator advice:")
        print(indicators_advice, "\n")
        
        print("Spread advice:")
        print(spread_advice, "\n")
        
        print("Orderbook advice:")
        print(orderbook_advice, "\n")

    # Return result
    return can_buy, message

# Calculates the closest index
def get_closest_index(prices, span):
    
    # Find the closest index in the time {timeframe}
    closest_index = None
    min_diff = float('inf')

    for i, t in enumerate(prices['time']):
        diff = abs(t - span)
        if diff < min_diff:
            min_diff = diff
            closest_index = i

    # Return closest index
    return closest_index

# Calculate price changes for spike detection 
def waves_spikes(prices, use_data, select):

    # Initialize variables
    debug   = False
    spiking = False

    # Time calculations
    latest_time = prices['time'][-1]             # Get the latest time
    span = latest_time - use_data['timeframe']   # timeframe in milliseconds

    # Get the closest index in the time {timeframe}
    closest_index = get_closest_index(prices, span)

    # Calculate the change in price
    price_change      = 0
    price_change_perc = 0
    if closest_index is not None and prices['time'][-1] > span:
        price_change      = prices['price'][-1] - prices['price'][closest_index]
        price_change_perc = (price_change / prices['price'][closest_index]) * 100

    # Apply wave multiplier
    if select == "Wave":
        price_change_perc = price_change_perc * use_data['multiplier']

    # Output to stdout
    if select == "Spike":
        if abs(price_change_perc) > use_data['threshold']:
            print(defs.now_utc()[1] + "Defs: waves_spikes: *** SPIKE DETECTED ***\n")
            spiking = True 

    if debug or spiking:
        print(defs.now_utc()[1] + "Defs: waves_spikes: Price change in the last " + str(round((use_data['timeframe'] / 1000), 2)) +  " seconds is " + str(round(price_change_perc, 2)) + "%\n")

    # Return price change percentage
    return price_change_perc, spiking

# Deal with API rate limit
def rate_limit(response):
    
    # Debug
    debug = False
    
    # Initialize variables
    delay  = 0
    status = 0
    limit  = 0
    skip   = False

    # Get Status and Limit
    try:
        status = float(response[2]['X-Bapi-Limit-Status'])
        limit  = float(response[2]['X-Bapi-Limit'])
    except:
        if debug:
            print(defs.now_utc()[1] + "Defs: rate_limit: Warning: API Rate Limit info does not exist in data, probably public request\n")
        skip = True

    # Continue when API Rate Limit is presence
    if not skip:
   
        # Delay logic
        ratio = (limit - status) / limit
        if ratio > 0.5:
            delay = delay + 0.1
        if ratio > 0.7:
            delay = delay + 0.3
        if ratio > 0.8:
            delay = delay + 0.6
        if ratio > 0.9:
            delay = delay + 1

        # Debug
        if debug:
            print(defs.now_utc()[1] + "Defs: rate_limit: Status is " + str(status) + " and limit is " + str(limit) + ", therefore API delay is set to " + str(round(delay, 1)) + " seconds\n")
        
        # Hard exit
        if ratio > 1:
            print(defs.now_utc()[1] + "Defs: rate_limit: *** ERROR: API RATE LIMIT EXCEED, STOPPED TO PREVENT PERMANENT BAN! ***\n")
            exit()
        
        # Inform of delay
        if delay:
            print(defs.now_utc()[1] + "Defs: rate_limit: *** WARNING: API RATE LIMIT HIT, DELAYING SUNFLOW " + str(delay) + " SECONDS ***\n")
            time.sleep(delay)
    
    # Clean response data
    data = response[0]

    # Return cleaned response
    return data

# Do a smart round because we are lazy :)
def smart_round(number):

    # Initialize variables
    num_str = f"{number:.20f}"
    
    # Search for the first occurrence of at least three consecutive zeros
    match = re.search(r'0{3,}', num_str)
    
    # Rounding logic
    if match:
        zero_start = match.start()
        rounded_number = round(number, zero_start - 2)
    else:
        rounded_number = number
    
    return rounded_number

# Report ticker info to stdout
def ticker_stdout(spot, new_spot, rise_to, active_order, all_buys, info):

    print(defs.now_utc()[1] + "Sunflow: handle_ticker: Price went ", end="")
    if new_spot > spot:
        print("up", end="")
    else:
        print("down", end="")
    print(" from " + str(spot) + " to " + str(new_spot) + " " + info['quoteCoin'], end="")
    if active_order['active']:
        trigger_distance = abs(new_spot - active_order['trigger'])
        trigger_distance = defs.precision(trigger_distance, info['tickSize'])
        print(", distance is " + str(trigger_distance) + " " + info['quoteCoin'], end="")
    if not active_order['active']:
        if rise_to:
            print(", needs to rise " + rise_to + ", NO SELL", end="")
        else:
            if len(all_buys) > 0:
                print(", SELL", end="")
    print("\n")

# Give an advice via the buy matrix
def advice_buy(indicators_advice, use_indicators, use_spread, use_orderbook, spot, klines, all_buys, interval):
    
    # Initialize variables
    spread_advice          = {}
    orderbook_advice       = {}
    technical_indicators   = {}
    result                 = ()

        
    '''' Check TECHNICAL INDICATORS for buy decission '''
    
    if use_indicators['enabled']:
        technical_indicators                 = indicators.calculate(klines[interval], spot)
        result                               = indicators.advice(technical_indicators)
        indicators_advice[interval]['value'] = result[0]
        indicators_advice[interval]['level'] = result[1]

        # Check if indicator advice is within range
        if (indicators_advice[interval]['value'] >= use_indicators['minimum']) and (indicators_advice[interval]['value'] <= use_indicators['maximum']):
            indicators_advice[interval]['result'] = True
        else:
            indicators_advice[interval]['result'] = False
    else:
        # If indicators are not enabled, always true
        indicators_advice[interval]['result'] = True

    
    ''' Check SPREAD for buy decission '''
    
    if use_spread['enabled']:
        result                   = defs.check_spread(all_buys, spot, use_spread['distance'])
        spread_advice['result']  = result[0]
        spread_advice['nearest'] = round(result[1], 2)
    else:
        # If spread is not enabled, always true
        spread_advice['result'] = True


    ''' Check ORDERBOOK for buy decission ''' # *** CHECK *** To be implemented
    
    if use_orderbook['enabled']:
        # Put orderbook logic here
        orderbook_advice['value']  = 0
        orderbook_advice['result'] = True
    else:
        # If orderbook is not enabled, always true
        orderbook_advice['result'] = True


    # Return all data
    return indicators_advice, spread_advice, orderbook_advice

# Send out a notification via Apprise
def notify(message, level):

    # Check if enabled
    if not config.notify_enabled:
        return

    # Messaging suitable for level
    if level >= config.notify_level:
        apobj.notify(
            body  = message,
            title = "Sunflow Cryptobot"
        )
