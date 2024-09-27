### Sunflow Cryptobot ###
#
# General functions

# Load libraries
from loader import load_config
from pathlib import Path
from datetime import datetime, timezone
import defs, indicators, preload
import apprise, inspect, math, pprint, pytz, time

# Load config
config = load_config()

# Create an Apprise instance
apobj = apprise.Apprise()

# Primary and secondary notification urls for Apprise
urls_tags = [(config.notify_1_urls, "primary"), (config.notify_2_urls, "secondary")]
for urls, tag in urls_tags:
    for url in urls:
        apobj.add(url, tag=tag)

# Initialize variables 
df_errors    = 0        # Dataframe error counter
halt_sunflow = False    # Register halt or continue

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

# Return timestamp according to UTC and offset
def now_utc():
    
    # Current UTC datetime
    current_time = datetime.now(timezone.utc)
    milliseconds = math.floor(current_time.microsecond / 10000) / 100
    timestamp_0  = current_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}'
    timestamp_1  = current_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}' + " | " + config.symbol + ": "
    timestamp_2  = milliseconds
    timestamp_3  = str(milliseconds) + " | "
    timestamp_4  = int(time.time() * 1000)

    # Convert current UTC time to the specified local timezone
    local_tz = pytz.timezone(config.timezone_str)
    local_time = current_time.astimezone(local_tz)
    
    # Current local time
    timestamp_5  = local_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}'
    timestamp_6  = local_time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(milliseconds * 100):02d}' + " | " + config.symbol + ": "
    
    return timestamp_0, timestamp_1, timestamp_2, timestamp_3, timestamp_4, timestamp_5, timestamp_6

# Log all responses from exchange
def log_exchange(response, message):
    
    # Create log message   
    to_log = now_utc()[1] + message + "\n"
    
    # Extend log message based on error level
    if config.error_level == 0:
        to_log = message + "\n" + str(response) + "\n\n"
    
    # Write to exchange log file
    if config.exchange_log:    
        with open(config.exchange_file, 'a', encoding='utf-8') as file:
            file.write(to_log)

# Log all errors
def log_error(exception):
    
    # Debug
    debug = False

    # Declare global variables
    global halt_sunflow
    
    # Output debug
    if debug:
        defs.announce("Debug")
        print("Exception RAW:")
        print(exception)
        print()
       
    # Initialize variables
    halt_execution = True
    stack          = inspect.stack()
    call_frame     = stack[1]
    filename       = Path(call_frame.filename).name
    functionname   = call_frame.function
    timestamp      = now_utc()[1]

    # Safeguard from type errors
    exception = str(exception)

    # Create message
    message = timestamp + f"{filename}: {functionname}: {exception}"

    # Error: Dataframe failure
    if ("(30908)" in exception) or ("Length of values" in exception) or ("All arrays must be of the same length" in exception):
        defs.announce(f"*** Warning: Dataframe issue for the {df_errors} time! ***", True, 1)
        halt_execution = False

    # Error: Remote disconnected
    if ("(ErrCode: 12940)" in exception) or ("RemoteDisconnected" in exception):
        defs.announce("*** Warning: Remote disconnected! ***", True, 1)
        halt_execution = False
    
    # Error: Read time out
    if "HTTPSConnectionPool" in exception:
        defs.announce("*** Warning: Read time out! ***", True, 1)
        halt_execution = False
    
    # Write to error log file
    with open(config.error_file, 'a', encoding='utf-8') as file:
        file.write(message + "\n")
    
    # Output to stdout
    defs.announce(f"Exception: {exception}")
    
    # Terminate hard
    if halt_execution:
        defs.announce("*** Terminating Sunflow, error to severe! ***", True, 1)
        defs.announce(exception, True, 1)
        halt_sunflow = True

# Log revenue data
def log_revenue(active_order, transaction, revenue, info, sides=True, extended=False):
    
    # Debug
    debug = False
  
    # Initialize variables
    message   = "Something went wrong while logging revenue..."
    divider   = "================================================================================\n"
    seperator = "\n----------------------------------------\n"
    timestamp = defs.now_utc()[0]
    revenue   = defs.round_number(revenue, info['quotePrecision'])

    # Check if we can log
    if (not extended) and (not sides) and (transaction['side'] == "Buy"):
        return

    # Format data for extended messaging
    if extended:
        timedis = "timestamp\n" + timestamp
        a_order = "active_order\n" + pprint.pformat(active_order)
        t_order = "transaction\n" + pprint.pformat(transaction)
        r_order = "revenue\n" + pprint.pformat(revenue)
        i_order = "info\n" + pprint.pformat(info)
        message = divider + timedis+ seperator + a_order + seperator + t_order + seperator + r_order + seperator + i_order

    # Format data for normal messaging
    # UTC Time, createdTime, orderId, side, symbol, baseCoin, quoteCoin, orderType, orderStatus, avgPrice, qty, trigger_ini, triggerPrice, cumExecFee, cumExecQty, cumExecValue, revenue
    if not extended:
        message = f"{timestamp},{transaction['createdTime']},"
        message = message + f"{transaction['orderId']},{transaction['side']},{transaction['symbol']},{info['baseCoin']},{info['quoteCoin']},"
        message = message + f"{transaction['orderType']},{transaction['orderStatus']},"
        message = message + f"{transaction['avgPrice']},{transaction['qty']},{active_order['trigger_ini']},{transaction['triggerPrice']},"
        message = message + f"{transaction['cumExecFee']},{transaction['cumExecQty']},{transaction['cumExecValue']},{revenue}"
    
    # Debug
    if debug:
        defs.announce("Revenue log file message")
        print(message)
    
    # Write to revenue log file
    with open(config.revenue_file, 'a', encoding='utf-8') as file:
        file.write(message + "\n")
        
    # Return
    return

# Outputs a (Pass) or (Fail) for decide_buy()
def report_buy(result):

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
def advice_buy(indicators_advice, orderbook_advice, trade_advice, pricelimit_advice, use_indicators, use_spread, use_orderbook, use_trade, use_pricelimit, spot, klines, all_buys, interval):

    # Initialize variables
    spread_advice          = {}
    technical_indicators   = {}
    result                 = ()


    '''' Check TECHNICAL INDICATORS for buy decission '''
    
    if use_indicators['enabled']:
        indicators_advice[interval]['filled'] = True
        technical_indicators                  = indicators.calculate(klines[interval], spot)
        result                                = indicators.advice(technical_indicators)
        indicators_advice[interval]['value']  = result[0]
        indicators_advice[interval]['level']  = result[1]

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
        spread_advice['nearest'] = result[1]
    else:
        # If spread is not enabled, always true
        spread_advice['result'] = True


    ''' Check ORDERBOOK for buy decission '''
    
    if use_orderbook['enabled']:
        if (orderbook_advice['buy_perc'] >= use_orderbook['minimum']) and (orderbook_advice['buy_perc'] <= use_orderbook['maximum']):
            orderbook_advice['result'] = True
        else:
            orderbook_advice['result'] = False
    else:
        # If orderbook is not enabled, always true
        orderbook_advice['result'] = True


    ''' Check ORDERBOOK for buy decission '''
    
    if use_trade['enabled']:
        if (trade_advice['buy_ratio'] >= use_trade['minimum']) and (trade_advice['buy_ratio'] <= use_trade['maximum']):
            trade_advice['result'] = True
        else:
            trade_advice['result'] = False
    else:
        # If orderbook is not enabled, always true
        trade_advice['result'] = True


    ''' Check ORDERBOOK for buy decission '''

    if use_pricelimit['enabled']:
        if use_pricelimit['max_buy_enabled']:
            if spot < use_pricelimit['max_buy']:
                pricelimit_advice['buy_result'] = True
            else:
                pricelimit_advice['buy_result'] = False
    else:
        # If pricelimit is not enabled, always true
        pricelimit_advice['buy_result'] = True
        
    # Return all data
    return indicators_advice, spread_advice, orderbook_advice, trade_advice, pricelimit_advice

# Calculate the average of all active intervals
def indicators_average(indicators_advice, intervals, use_indicators):
    
    # Debug
    debug  = False
    
    # Initialize variables
    count          = 0
    total_value    = 0
    average_filled = True
    average_level  = "Neutral"
    average_result = False
    average_value  = 0
    
    # Exclude interval 0
    filtered_intervals = {k: v for k, v in intervals.items() if v != 0}

    # Check if all required intervals are filled
    for interval in filtered_intervals.values():
        if not indicators_advice[interval]['filled']:
            average_filled = False
    
    # Calculate the average value
    if average_filled:
        for interval in filtered_intervals.values():
            total_value += indicators_advice[interval]['value']
            count += 1
        average_value = total_value / count
        average_level = indicators.technicals_advice(average_value)
        if average_value >= use_indicators['minimum'] and average_value <= use_indicators['maximum']:
            average_result = True

    # Assign average indicators
    if average_filled:
        indicators_advice[0]['filled'] = average_filled
        indicators_advice[0]['level']  = average_level
        indicators_advice[0]['result'] = average_result
        indicators_advice[0]['value']  = average_value

    # Dump variables
    if debug:
        defs.announce(f"Dump of intervals advice variable:")
        pprint.pprint(indicators_advice)
        pprint.pprint(intervals)
       
    return indicators_advice

# Determines buy decission and outputs to stdout
def decide_buy(indicators_advice, use_indicators, spread_advice, use_spread, orderbook_advice, use_orderbook, trade_advice, use_trade, pricelimit_advice, use_pricelimit, interval, intervals, info):
            
    # Debug
    debug = False

    # Initialize variables
    do_buy    = {}
    do_buy[1] = False   # Indicator interval 1
    do_buy[2] = False   # Indicator interval 2
    do_buy[3] = False   # Indicator interval 3
    do_buy[4] = False   # Spread
    do_buy[5] = False   # Orderbook
    do_buy[6] = False   # Trades
    do_buy[7] = False   # Pricelimit
    can_buy   = False
    message   = ""
   
    # Regular update or grid bot style
    if interval != 0:
        message = f"Update {interval}m: "

    # Report and check indicators
    if use_indicators['enabled']:

        # Use average of all active intervals
        if config.interval_average:        

            # Calculate average
            indicators_advice = indicators_average(indicators_advice, intervals, use_indicators)
            do_buy[1] = indicators_advice[intervals[0]]['result']
            do_buy[2] = indicators_advice[intervals[0]]['result']
            do_buy[3] = indicators_advice[intervals[0]]['result']
                        
            # Create message
            for i in range(1, 4):
                if intervals[i] != 0:
                    message += f"{intervals[i]}m: "
                    if indicators_advice[intervals[i]]['filled']:
                        message +=  f"{indicators_advice[intervals[i]]['value']:.2f}, " 
                    else:
                        message += "?, "
            if indicators_advice[intervals[0]]['filled']:
                message += f"average: {indicators_advice[intervals[0]]['value']:.2f} "
            else:
                message += "average: ? "
            message += report_buy(indicators_advice[intervals[0]]['result']) + ", "

        # Use all intervals seperatly
        if not config.interval_average:

            # Create message
            for i in range(1, 4):
                if intervals[i] != 0:
                    if indicators_advice[intervals[i]]['result']:
                        do_buy[i] = True
                    message += f"{intervals[i]}m: "
                    if indicators_advice[intervals[i]]['filled']:
                        message += f"{indicators_advice[intervals[i]]['value']:.2f} " 
                    else:
                        message += "? "
                    message += report_buy(indicators_advice[intervals[i]]['result']) + ", "
                else:
                    do_buy[i] = True
    else:
        # Indicators are disabled
        do_buy[1] = True
        do_buy[2] = True
        do_buy[3] = True

    # Report spread
    if use_spread['enabled']:
        if spread_advice['result']:
            do_buy[4] = True
        message += f"Spread: {spread_advice['nearest']:.4f} % "
        message += report_buy(spread_advice['result']) + ", "
    else:
        do_buy[4] = True
    
    # Report orderbook
    if use_orderbook['enabled']:
        if orderbook_advice['result']:
            do_buy[5] = True
        message += f"Orderbook: {orderbook_advice['buy_perc']:.2f} % "
        message += report_buy(orderbook_advice['result']) + ", "
    else:
        do_buy[5] = True

    # Report trades
    if use_trade['enabled']:
        if trade_advice['result']:
            do_buy[6] = True
        message += f"Trade: {trade_advice['buy_ratio']:.2f} % "
        message += report_buy(trade_advice['result']) + ", "
    else:
        do_buy[6] = True

    # Report pricelimit
    if use_pricelimit['enabled']:
        if pricelimit_advice['buy_result']:
            do_buy[7] = True
        message += f"Max buy: {defs.format_number(use_pricelimit['max_buy'], info['tickSize'])} {info['quoteCoin']} "
        message += report_buy(pricelimit_advice['buy_result']) + ", "
    else:
        do_buy[7] = True

    # Determine buy decission
    if do_buy[1] and do_buy[2] and do_buy[3] and do_buy[4] and do_buy[5] and do_buy[6] and do_buy[7]:
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

        print("Pricelimit advice:")
        print(pricelimit_advice, "\n")

    # Return result
    return can_buy, message, indicators_advice

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
            defs.announce("*** Warning: API Rate Limit info does not exist in data, probably public request! ***")
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
            defs.announce("f*** ERROR: API RATE LIMIT EXCEED, STOPPED TO PREVENT PERMANENT BAN! ***", True, 0)
            defs.halt_sunflow = True
            exit()
        
        # Inform of delay
        if delay:
            defs.announce(f"*** WARNING: API RATE LIMIT HIT, DELAYING SUNFLOW {delay} SECONDS! ***", True, 1)
            time.sleep(delay)
    
    # Clean response data
    data = response[0]

    # Return cleaned response
    return data

# Report ticker info to stdout
def report_ticker(spot, new_spot, rise_to, active_order, all_buys, info):

    # Create message
    message = "Price went "
    if new_spot > spot:
        message += "up"
    else:
        message += "down"
    
    message += f" from {format_number(spot, info['tickSize'])} to {format_number(new_spot, info['tickSize'])} {info['quoteCoin']}"

    if active_order['active']:
        trigger_distance = abs(new_spot - active_order['trigger'])
        trigger_distance = defs.format_number(trigger_distance, info['tickSize'])
        message += f", trigger price distance is {trigger_distance} {info['quoteCoin']}"

    if not active_order['active']:
        if rise_to:
            message += f", needs to rise {rise_to}, NO SELL"
        else:
            if len(all_buys) > 0:
                message += ", SELL"
    
    # Return message
    return message

# Report on compounding
def calc_compounding(info, spot, compounding):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]
    
    # Calculate ratio
    compounding_ratio = compounding['now'] / compounding['start']
    
    # Profitable or not
    if compounding_ratio > 0:

        # Adjust minimum order values
        info = preload.calc_info(info, spot, config.multiplier, compounding)

        # Create message
        message = f"Compounding started at {defs.format_number(compounding['start'], info['quotePrecision'])} {info['quoteCoin']}, "
        message = message + f"currently {defs.format_number(compounding['now'], info['quotePrecision'])} {info['quoteCoin']}, "
        message = message + f"ratio is {compounding_ratio:.4f}x"

    else:
        message = "Compounding inactive because no profit yet"
        
    # Display message
    defs.announce(message)

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))
    
    # Return
    return info

# Announcement helper for notification function
def announce_helper(enabled, config_level, message_level, tag, message):
    
    # Do logic
    if enabled and message_level >= config_level:
        apobj.notify(
            body  = message,
            title = "Sunflow Cryptobot",
            tag   = tag
        )
    
    # Close function and return
    return

# Send out a notification via stdout or Apprise
def announce(message, to_group_1=False, level_1=1, to_group_2=False, level_2=1):
   
    # Initialize variables
    stack        = inspect.stack()
    call_frame   = stack[1]
    filename     = Path(call_frame.filename).name
    functionname = call_frame.function
    
    # Local or UTC time
    if config.timeutc_std:
        timestamp = now_utc()[1]
    else:
        timestamp = now_utc()[6]

    # Safeguard from type errors
    message = str(message)

    # Check if we can notify for blanc messages
    if not message:
        screen_message = timestamp + f"{filename}: {functionname}: No announcement available"
        return screen_message

    # Check if we can notify for session messages
    if not config.session_report and "session:" in message:
        return_message = timestamp + f"{filename}: {functionname}: No announcement available"
        return return_message
      
    # Compose messages
    screen_message  = timestamp + f"{filename}: {functionname}: {message}"
    group_1_message = f"{message} ({config.symbol})"
    group_2_message = f"{message}"
    
    # Output to stdout, we do not display group 2 active messages 
    if not to_group_2:
        print(screen_message + "\n")
    
    # Output to Apprise Group 1 (Usually Telegram)
    if to_group_1:
        announce_helper(config.notify_1_enabled, config.notify_1_level, level_1, "primary", group_1_message)

    # Output to Apprise Group 2 (Usually LaMetric)
    if to_group_2:
        announce_helper(config.notify_2_enabled, config.notify_2_level, level_2, "secondary", group_2_message)

    # Return message
    return screen_message

# Round value to the nearest step size
def round_number(value, step_size, rounding = ""):
    
    # Logic
    if step_size < 1:
        decimal_places = -int(math.log10(step_size))
        factor = 10 ** decimal_places
    else:
        factor = 1 / step_size

    # Round down
    if rounding == "down":
        rounded_value = math.floor(value * factor) / factor
    
    # Round up
    if rounding == "up":
        rounded_value = math.ceil(value * factor) / factor
    
    # Round half
    if not rounding:
        rounded_value = round(value * factor) / factor

    # Return rounded value
    return rounded_value

# Formats the price according to the ticksize.
def format_number(price, tickSize):

    # Check for number format
    modified_tickSize = scientific_to_decimal_str(tickSize)

    # Calculate the number of decimal places from ticksize
    decimal_places = get_decimal_places(modified_tickSize)
    
    # Format the price with the calculated decimal places
    formatted_price = f"{price:.{decimal_places}f}"
    
    # Return formatted price
    return formatted_price

# Returns the number of decimal places based on the ticksize value.
def get_decimal_places(ticksize_str):

    if '.' in ticksize_str:
        decimal_places = len(ticksize_str.split('.')[1])
    else:
        decimal_places = 0

    # Return decimal places
    return decimal_places

def scientific_to_decimal_str(number):
    # Convert the number to string
    number_str = str(number)
    
    # Check if it contains 'e' or 'E', which indicates scientific notation
    if 'e' in number_str or 'E' in number_str:
        # Convert the scientific notation number to a float and then to a decimal string
        decimal_str = f"{float(number):.10f}".rstrip('0').rstrip('.')
    else:
        # If it's not in scientific notation, just return it as a string with appropriate formatting
        decimal_str = f"{number:.10f}".rstrip('0').rstrip('.')
    
    return decimal_str
    
# Calculates the closest index
def get_closest_index(data, span):
    
    # Find the closest index in the time {timeframe}
    closest_index = None
    min_diff = float('inf')

    for i, t in enumerate(data['time']):
        diff = abs(t - span)
        if diff < min_diff:
            min_diff = diff
            closest_index = i

    # Return closest index
    return closest_index

# Calcuate number of items to use
def get_index_number(data, timeframe, limit):
    
    # Time calculations
    latest_time  = data['time'][-1]           # Get the time for the last element
    span         = latest_time - timeframe    # Get the time of the last element minus the timeframe
    
    # Calculate number of items to use
    missing  = 0
    elements = len(data['time'])
    ratio = (elements / limit) * 100
    if elements < limit:
        missing = limit - elements
        defs.announce(f"*** Warning: Still fetching data, message will disappear ({ratio:.0f} %)! ***")
    
    closest_index = defs.get_closest_index(data, span)
    number        = limit - closest_index - missing
    
    # Return number
    return number

# Caculate the average value in a list
def average(numbers):

    # Logic
    if not numbers:
        return 0
    
    total = sum(numbers)
    count = len(numbers)
    average = total / count

    # Return average
    return average

# Calculate average buy and sell percentage for timeframe
def average_depth(depth_data, use_orderbook, buy_percentage, sell_percentage):

    # Debug
    debug_1 = False
    debug_2 = True

    # Initialize variables
    datapoints   = {}
    
    # Number of depth elements to use
    number = defs.get_index_number(depth_data, use_orderbook['timeframe'], use_orderbook['limit'])

    # Validate data
    datapoints['depth']   = number
    datapoints['compare'] = len(depth_data['time'])
    datapoints['limit']   = use_orderbook['limit']
    if (datapoints['depth'] >= datapoints['compare']) and (datapoints['compare'] >= datapoints['limit']):
        defs.announce("*** Warning: Increase orderbook_limit variable in config file! ***", True, 1)
    
    # Debug elements
    if debug_1:
        print("All elements")
        pprint.pprint(depth_data['buy_perc'])
        print(f"Last {number} elements")
        pprint.pprint(depth_data['buy_perc'][(-number):])

    # Calculate average depth
    if datapoints['compare'] >= datapoints['limit']:
        new_buy_percentage  = defs.average(depth_data['buy_perc'][(-number):])
        new_sell_percentage = defs.average(depth_data['sell_perc'][(-number):])
    else:
        new_buy_percentage  = buy_percentage
        new_sell_percentage = sell_percentage
    
    # Debug announcement
    if debug_2: 
            message = f"There are {datapoints['compare']} / {datapoints['limit']} data points, "
            message = message + f"using the last {datapoints['depth']} points and "
            message = message + f"buy percentage is {new_buy_percentage:.2f} %"
            defs.announce(message)

    # Return data
    return new_buy_percentage, new_sell_percentage

# Calculate total buy and sell from trades
def calculate_total_values(trades):

    # Initialize variables
    total_sell = 0.0
    total_buy  = 0.0
    total_all  = 0.0 

    # Do logic
    for i in range(len(trades['price'])):
        price = float(trades['price'][i])
        size = float(trades['size'][i])
        value = price * size

        if trades['side'][i] == 'Sell':
            total_sell += value
        elif trades['side'][i] == 'Buy':
            total_buy += value

    total_all = total_buy + total_sell
    
    # Return totals
    return total_buy, total_sell, total_all, (total_buy / total_all) * 100, (total_sell / total_all) * 100

# Report time it took to execute a function
def report_exec(start_time, supplement = "", always_display = False):
       
    # Initialize variables
    message    = ""
    mess_delay = config.func_norm_delay
    warn_delay = config.func_warn_delay
    end_time   = now_utc()[4]
    exec_time  = end_time - start_time
    
    # Overrule always_display
    if config.func_show_delay:
        always_display = True
    
    # Create message
    if exec_time > mess_delay or always_display:
        message = f"Execution time of function was {exec_time} ms"
        if supplement:
            message = message + f" ({supplement})"
        if exec_time > warn_delay:
            message = "*** Warning: " + message + "! ***"
        
    # Return message
    return message