### Sunflow Cryptobot ###
#
# General functions

# Load libraries
from loader import load_config
from pathlib import Path
from datetime import datetime, timezone
import defs, indicators
import apprise, inspect, math, time

# Load config
config = load_config()

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
            defs.announce("No adjacent order found, we can buy")
        else:
            defs.announce("Adjacent order found, we can't buy")

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
        defs.announce("Debug")
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
        defs.announce("*** Warning: Remote Disconnected! ***")
        halt_execution = False
    
    # Write to error log file
    with open(config.error_file, 'a', encoding='utf-8') as file:
        file.write(exception)
    
    # Output to stdout
    defs.announce(f"Displaying exception: {exception}")
    
    # Terminate hard
    if halt_execution:
        defs.announce("*** Terminating Sunflow, error to severe! ***", True, 1)
        defs.announce(exception, True, 1)
        exit()

# Outputs a (Pass) or (Fail) for decide_buy()
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
        message = f"Update {interval}m: "

    # Report and check indicators
    if use_indicators['enabled']:    
        if intervals[1] != 0:
            if indicators_advice[intervals[1]]['result']:
                do_buy[1] = True
            message += f"{intervals[1]}m: {indicators_advice[intervals[1]]['value']:.2f} "
            message += report_result(indicators_advice[intervals[1]]['result']) + ", "
        else:
            do_buy[1] = True
        if intervals[2] != 0:
            if indicators_advice[intervals[2]]['result']:
                do_buy[2] = True
            message += f"{intervals[2]}m: {indicators_advice[intervals[2]]['value']:.2f} "
            message += report_result(indicators_advice[intervals[2]]['result']) + ", "
        else:
            do_buy[2] = True
        if intervals[3] != 0:
            if indicators_advice[intervals[3]]['result']:
                do_buy[3] = True
            message +=f"{intervals[3]}m: {indicators_advice[intervals[3]]['value']:.2f} "
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
        message += f"Spread: {defs.format_price(spread_advice['nearest'], 0.01)} % "
        message += report_result(spread_advice['result']) + ", "
    else:
        do_buy[4] = True
    
    # Report orderbook
    if use_orderbook['enabled']:
        if orderbook_advice['result']:
            do_buy[5] = True
        message += f"Orderbook: {orderbook_advice['value']} % "
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
            defs.announce("Warning: API Rate Limit info does not exist in data, probably public request")
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
            defs.announce(f"Status is {status} and limit is {limit}, therefore API delay is set to {delay:.1f} seconds\n")
        
        # Hard exit
        if ratio > 1:
            defs.announce("f*** ERROR: API RATE LIMIT EXCEED, STOPPED TO PREVENT PERMANENT BAN! ***")
            exit()
        
        # Inform of delay
        if delay:
            defs.announce(f"*** WARNING: API RATE LIMIT HIT, DELAYING SUNFLOW {delay} SECONDS ***")
            time.sleep(delay)
    
    # Clean response data
    data = response[0]

    # Return cleaned response
    return data

# Report ticker info to stdout
def ticker_stdout(spot, new_spot, rise_to, active_order, all_buys, info):

    # Create message
    message = "Price went "
    if new_spot > spot:
        message += "up"
    else:
        message += "down"
    
    message += f" from {format_price(spot, info['tickSize'])} to {format_price(new_spot, info['tickSize'])} {info['quoteCoin']}"

    if active_order['active']:
        trigger_distance = abs(new_spot - active_order['trigger'])
        trigger_distance = defs.format_price(trigger_distance, info['tickSize'])
        message += f", distance is {trigger_distance} {info['quoteCoin']}"

    if not active_order['active']:
        if rise_to:
            message += f", needs to rise {rise_to}, NO SELL"
        else:
            if len(all_buys) > 0:
                message += ", SELL"
    
    # Return message
    return message

# Send out a notification via stdout or Apprise
def announce(message, to_apprise=False, level=1):
    
    # Initialize variables
    stack        = inspect.stack()
    call_frame   = stack[1]
    filename     = Path(call_frame.filename).name
    functionname = call_frame.function
    timestamp    = now_utc()[1]
      
    # Compose messages
    screen_message  = timestamp + f"{filename}: {functionname}: {message}"
    apprise_message = f"{message} ({config.symbol})"
    
    # Output to Screen
    print(screen_message + "\n")
    
    # Output to Apprise
    if to_apprise:
        if config.notify_enabled and level >= config.notify_level:
            apobj.notify(
                body  = apprise_message,
                title = "Sunflow Cryptobot"
            )
    
    # Return message
    return screen_message

# Formats the price according to the ticksize.
def format_price(price, tickSize):

    # Calculate the number of decimal places from ticksize
    decimal_places = get_decimal_places(tickSize)
    
    # Format the price with the calculated decimal places
    formatted_price = f"{price:.{decimal_places}f}"
    
    # Return formatted price
    return formatted_price

# Returns the number of decimal places based on the ticksize value.
def get_decimal_places(ticksize):

    ticksize_str = str(ticksize)

    if '.' in ticksize_str:
        decimal_places = len(ticksize_str.split('.')[1])
    else:
        decimal_places = 0

    # Return decimal places
    return decimal_places

    