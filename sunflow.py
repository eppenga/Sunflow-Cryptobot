### Sunflow Cryptobot ###
#
# File that drives it all! 

# Load external libraries
from time import sleep
from pathlib import Path
from pybit.unified_trading import WebSocket
from requests.exceptions import ChunkedEncodingError
from urllib3.exceptions import ProtocolError
from http.client import RemoteDisconnected
import argparse, importlib, sys, traceback

# Load internal libraries
import database, defs, preload, trailing, orders

# Parse command line arguments
parser = argparse.ArgumentParser(description="Run the Sunflow Cryptobot with a specified config.")
parser.add_argument('-c', '--config', default='config.py', help='Specify the config file (with .py extension).')
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

### Initialize variables ###

# Set default values
debug                        = config.debug                   # Debug
symbol                       = config.symbol                  # Symbol bot used for trading
klines                       = {}                             # Klines for symbol
intervals                    = {}                             # Klines intervals
intervals[1]                 = config.interval_1              # Klines timeframe interval 1
intervals[2]                 = config.interval_2              # Klines timeframe interval 2
intervals[3]                 = config.interval_3              # Klines timeframe interval 3
limit                        = config.limit                   # Number of klines downloaded, used for calculcating technical indicators
ticker                       = {}                             # Ticker data, including lastPrice and time
info                         = {}                             # Instrument info on symbol
spot                         = 0                              # Spot price, always equal to lastPrice
profit                       = config.profit                  # Minimum profit percentage
depth                        = config.depth                   # Depth in percentages used to calculate market depth from orderbook
multiplier                   = config.multiplier              # Multiply minimum order quantity by this
prices                       = {}                             # Last {limit} prices based on ticker

# Minimum spread between historical buy orders
use_spread                   = {}                             # Spread
use_spread['enabled']        = config.spread_enabled          # Use spread as buy trigger
use_spread['distance']       = config.spread_distance         # Minimum spread in percentages

# Technical indicators
use_indicators               = {}                             # Technical indicators
use_indicators['enabled']    = config.indicators_enabled      # Use technical indicators as buy trigger
use_indicators['minimum']    = config.indicators_minimum      # Minimum advice value
use_indicators['maximum']    = config.indicators_maximum      # Maximum advice value

# Orderbook
use_orderbook                = {}                             # Orderbook
use_orderbook['enabled']     = config.orderbook_enabled       # Use orderbook as buy trigger
use_orderbook['minimum']     = config.orderbook_minimum       # Minimum orderbook percentage
use_orderbook['maximum']     = config.orderbook_maximum       # Maximum orderbook percentage

# Spike detection
use_spikes                   = {}                             # Spikes
use_spikes['enabled']        = config.spike_enabled           # Use spike detection as buy trigger
use_spikes['timeframe']      = config.spike_timeframe         # Timeframe in ms to measure spikes
use_spikes['threshold']      = config.spike_threshold         # Threshold to reach within timeframe as percentage
use_spikes['multiplier']     = 1                              # Multiply spike percentage by this multiplier (and to keep compatible with waves)

# Wave measurement
use_waves                    = {}                             # Waves
use_waves['enabled']         = False                          # Use waves in trigger price distance calculation
if config.wiggle == "Wave"   : use_waves['enabled'] = True    # Automatically set to true
use_waves['timeframe']       = config.wave_timeframe          # Timeframe in ms to measure wave, used when wiggle is set to Wave
use_waves['multiplier']      = config.wave_multiplier         # Multiply wave percentage by this multiplier

# Delay
use_delay                    = {}
use_delay['enabled']         = config.delay_enabled           # Use delay after buy
use_delay['timeframe']       = config.delay_timeframe         # Timeframe in ms to delay buy
use_delay['start']           = 0                              # Miliseconds since epoch when delay started
use_delay['end']             = 0                              # Miliseconds since epoch when delay ends

# Trailing order
active_order                 = {}                             # Trailing order data
active_order['side']         = ""                             # Trailing buy
active_order['active']       = False                          # Trailing order active or not
active_order['start']        = 0                              # Start price when trailing order began     
active_order['previous']     = 0                              # Previous price
active_order['current']      = 0                              # Current price
active_order['wiggle']       = config.wiggle                  # Method to use to calculate trigger price distance
active_order['distance']     = config.distance                # Trigger price distance percentage when set to default
active_order['fluctuation']  = config.distance                # Trigger price distance percentage when set to wiggle
active_order['wave']         = config.distance                # Trigger price distance percentage when set to wave
active_order['orderid']      = 0                              # Orderid
active_order['trigger']      = 0                              # Trigger price for order
active_order['trigger_new']  = 0                              # New trigger price when trailing 
active_order['qty']          = 0                              # Order quantity
active_order['qty_new']      = 0                              # New order quantity when trailing

# Databases for buy and sell orders
all_buys                     = {}                             # All buys retreived from database file buy orders
all_sells                    = {}                             # Sell order linked to database with all buys orders

# Websockets to use
ws_kline                     = False                          # Initialize ws_kline
ws_orderbook                 = False                          # Initialize ws_orderbook
if config.indicators_enabled : ws_kline     = True            # Use klines websocket
if config.orderbook_enabled  : ws_orderbook = True            # Use orderbook websocket

# Initialize indicator advice variable
if not config.indicators_enabled:                             # Set intervals to zero if indicators are disabled
    intervals[1] = 0
    intervals[2] = 0
    intervals[3] = 0

# Initialize indicators advice variable
indicators_advice               = {}
indicators_advice[intervals[1]] = {'result': True, 'value': 0, 'level': 'Neutral'}
indicators_advice[intervals[2]] = {'result': True, 'value': 0, 'level': 'Neutral'}
indicators_advice[intervals[3]] = {'result': True, 'value': 0, 'level': 'Neutral'}

### Functions ###

# Handle messages to keep tickers up to date
def handle_ticker(message):
    
    # Errors are not reported within websocket
    try:
   
        # Declare some variables global
        global spot, ticker, active_order, all_buys, all_sells, prices, use_delay, indicators_advice

        # Initialize variables
        ticker                 = {}
        spiking                = False
        amend_code             = 0
        amend_error            = ""
        result                 = ()
        
        # Debug show incoming message
        if debug:
            print(defs.now_utc()[1] + "Sunflow: handle_ticker: *** Incoming ticker ***")
            print(str(message) + "\n")

        # Get ticker
        ticker['time']      = int(message['ts'])
        ticker['lastPrice'] = float(message['data']['lastPrice'])

        # Has price changed, then run all kinds of actions
        if spot != ticker['lastPrice']:
            new_spot = ticker['lastPrice']

            # Add last price to prices list and remove first
            prices['time'].append(ticker['time'])
            prices['price'].append(ticker['lastPrice'])
            prices['time'].pop(0)
            prices['price'].pop(0)

            # Determine if spiking
            if use_spikes['enabled']:
                spiking = defs.waves_spikes(prices, use_spikes, "Spike")[1]

            # Calculate price change when using waves
            if use_waves['enabled']:
                active_order['wave'] = defs.waves_spikes(prices, use_waves, "Wave")[0]

            # Run trailing if active
            if active_order['active']:
                active_order['current'] = new_spot
                active_order['status']  = 'Trailing'
                result       = trailing.trail(symbol, active_order, info, all_buys, all_sells, prices, use_delay)
                active_order = result[0]
                all_buys     = result[1]
                use_delay    = result[2]

            # Check if and how much we can sell
            result                  = orders.check_sell(new_spot, profit, active_order, all_buys, info)
            all_sells_new           = result[0]
            active_order['qty_new'] = result[1]
            can_sell                = result[2]
            rise_to                 = result[3]

            # Output to stdout
            defs.ticker_stdout(spot, new_spot, rise_to, active_order, all_buys, info)
            
            # If trailing buy is already running while we can sell
            if active_order['active'] and active_order['side'] == "Buy" and can_sell:
                
                # Output to stdout and Apprise
                print(defs.now_utc()[1] + "Sunflow: handle_ticker: *** Warning loosing money, we can sell while we are buying, canceling buy order! ***\n")
                defs.notify(f"Warning: loosing money, we can sell while we are buying for {symbol}, canceling buy order!", 1)
                
                # *** CHECK *** Needs testing: Cancel trailing buy, remove from all_buys database
                active_order['active'] = False
                result     = orders.cancel(symbol, active_order['orderid'])
                error_code = result[0]
                
                if error_code == 0:
                    # Situation normal, just remove the order
                    database.remove(active_order['orderid'], all_buys)

                if error_code == 1:
                    # Trailing buy was bought
                    result       = trailing.close_trail(active_order, all_buys, all_sells, info)
                    active_order = result[0]
                    all_buys     = result[1]
                    all_sells    = result[2]
                    
                if error_code == 100:
                    # Something went very wrong 
                    defs.log_error(result[1])
                
            # Initiate first sell
            if not active_order['active'] and can_sell:
                # There is no old quantity on first sell
                active_order['qty'] = active_order['qty_new']
                # Fill all_sells for the first time
                all_sells = all_sells_new
                # Place the first sell order
                active_order = orders.sell(symbol, new_spot, active_order, prices, info)
                
            # Amend existing sell trailing order if required
            if active_order['active'] and active_order['side'] == "Sell":

                # Only amend order if the quantity to be sold has changed
                if active_order['qty_new'] != active_order['qty'] and active_order['qty_new'] > 0:
                    result      = trailing.amend_quantity_sell(symbol, active_order, info)
                    amend_code  = result[0]
                    amend_error = result[1]

                    # Determine what to do based on error code of amend result
                    if amend_code == 0:
                        # Everything went fine, we can continue trailing
                        message = f"Adjusted quantity from {active_order['qty']} to {active_order['qty_new']} {info['baseCoin']} in {active_order['side'].lower()} order"
                        print(defs.now_utc()[1] + "Sunflow: handle_ticker: " + message + "\n")
                        defs.notify(message + f" for {symbol}", 0)
                        active_order['qty'] = active_order['qty_new']
                        all_sells           = all_sells_new

                    if amend_code == 1:
                        # Order slipped, close trailing process
                        print(defs.now_utc()[1] + "Trailing: trail: Order slipped, we keep buys database as is and stop trailing\n")
                        defs.notify(f"Sell order slipped, we keep buys database as is and stop trailing for {symbol}", 1)
                        result       = trailing.close_trail(active_order, all_buys, all_sells, info)
                        active_order = result[0]
                        all_buys     = result[1]
                        all_sells    = result[2]
                        # Revert old situation
                        all_sells_new = all_sells

                    if amend_code == 100:
                        # Critical error, let's log it and revert
                        all_sells_new = all_sells
                        print(defs.now_utc()[1] + "Trailing: trail: Critical error, logging to file\n")
                        defs.notify(f"While trailing a critical error occurred for {symbol}", 1)
                        defs.log_error(amend_error)

                # Reset all sells
                #all_sells = all_sells_new

            # Work as a true gridbot when only spread is used
            if use_spread['enabled'] and not use_indicators['enabled'] and not use_orderbook['enabled']:
                buy_matrix(new_spot, intervals[1])

            # Spiking, when not buying or selling, let's buy and see what happens :) *** CHECK *** Might want to change this to downwards spikes (negative pricechange)
            if not active_order['active'] and spiking:
                print(defs.now_utc()[1] + "Sunflow: handle_ticker: Spike detected, initiate buying!\n")
                result       = orders.buy(symbol, spot, active_order, all_buys, prices)
                active_order = result[0]
                all_buys     = result[1]

        # Always set new spot price
        spot = ticker['lastPrice']

    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        filename, line, func, text = tb_info[-1]
        print(defs.now_utc()[1] + f"Sunflow: handle_ticker: An error occurred in {filename} on line {line}: {e}")
        print("Full traceback:")
        traceback.print_tb(e.__traceback__)

def handle_kline_1(message):
    handle_kline(message, intervals[1])

def handle_kline_2(message):
    handle_kline(message, intervals[2])

def handle_kline_3(message):
    handle_kline(message, intervals[3])

# Handle messages to keep klines up to date
def handle_kline(message, interval):

    # Errors are not reported within websocket
    try:

        # Declare some variables global
        global klines, active_order, all_buys, indicators_advice

        # Initialize kline
        kline = {}
     
        # Show incoming message
        if debug:
            print(defs.now_utc()[1] + "Sunflow: handle_kline: *** Incoming kline with interval" + str(interval) + "m ***")
            print(message)

        # Get newest kline
        kline['time']     = int(message['data'][0]['start'])
        kline['open']     = float(message['data'][0]['open'])
        kline['high']     = float(message['data'][0]['high'])
        kline['low']      = float(message['data'][0]['low'])
        kline['close']    = float(message['data'][0]['close'])
        kline['volume']   = float(message['data'][0]['volume'])
        kline['turnover'] = float(message['data'][0]['turnover'])

        # Check if we have a finished kline
        if message['data'][0]['confirm'] == True:

            # Check if the number of klines still matches the config and report
            klines_count = len(klines[interval]['close'])
            if klines_count != limit:
                klines[interval] = preload.get_klines(symbol, interval, limit)
            print(defs.now_utc()[1] + "Sunflow: handle_kline: Added new "  + str(interval) + "m interval onto existing " + str(klines_count) + " klines\n")
            klines[interval] = defs.new_kline(kline, klines[interval])
      
        else:            
            # Remove the first kline and replace with fresh kline
            klines[interval] = defs.update_kline(kline, klines[interval])
        
        # Run buy matrix
        buy_matrix(spot, interval)

    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        filename, line, func, text = tb_info[-1]
        print(defs.now_utc()[1] + f"An error occurred in {filename} on line {line}: {e}")
        print("Full traceback:")
        traceback.print_tb(e.__traceback__)

def buy_matrix(spot, interval):

    # Declare some variables global
    global active_order, all_buys, indicators_advice

    # Initialize variables
    can_buy                = False
    spread_advice          = {}
    orderbook_advice       = {}
    initiate_buy           = {}
    initiate_buy['delay']  = False
    initiate_buy['order']  = False
    result                 = ()    
   
    # Only initiate buy when there is no delay
    if use_delay['enabled']:
        if defs.now_utc()[4] < use_delay['end']:
            print(defs.now_utc()[1] + "Sunflow: handle_kline: Buy delay is currently enabled, pausing for " + str(use_delay['end'] - defs.now_utc()[4]) + "ms \n")
            initiate_buy['delay'] = True
    
    # Only initiate buy and do complex calculations when not already trailing
    if active_order['active']:
        initiate_buy['order'] = True
    
    # Only initiate buy and do complex calculations when not already trailing
    if not initiate_buy['delay'] and not initiate_buy['order']:
        
        # Get buy advice
        result            = defs.advice_buy(indicators_advice, use_indicators, use_spread, use_orderbook, spot, klines, all_buys, interval)
        indicators_advice = result[0]
        spread_advice     = result[1]
        orderbook_advice  = result[2]
                    
        # Get buy decission and report
        result  = defs.decide_buy(indicators_advice, use_indicators, spread_advice, use_spread, orderbook_advice, use_orderbook, interval, intervals)
        can_buy = result[0]
        message = result[1]
        print(defs.now_utc()[1] + "Sunflow: buy_matrix: " + message + "\n")

        # Determine distance of trigger price and execute buy decission
        if can_buy:
            result       = orders.buy(symbol, spot, active_order, all_buys, prices)
            active_order = result[0]
            all_buys     = result[1]

# Handle messages to keep orderbook up to date
def handle_orderbook(message):

    # Errors are not reported within websocket
    try:
      
        # Show incoming message
        if debug:
            print(defs.now_utc()[1] + "Sunflow: handle_orderbook: *** Incoming orderbook ***")
            print(message)
        
        # Recalculate depth to numerical value
        depthN = ((2 * depth) / 100) * spot
        
        # Extracting bid (buy) and ask (sell) arrays
        bids = message['data']['b']
        asks = message['data']['a']

        # Initialize total quantities within depth for buy and sell
        total_buy_within_depth  = 0
        total_sell_within_depth = 0

        # Calculate total buy quantity within depth
        for bid in bids:
            price, quantity = float(bid[0]), float(bid[1])
            if (spot - depthN) <= price <= spot:
                total_buy_within_depth += quantity

        # Calculate total sell quantity within depth
        for ask in asks:
            price, quantity = float(ask[0]), float(ask[1])
            if spot <= price <= (spot + depthN):
                total_sell_within_depth += quantity

        # Calculate total quantity (buy + sell)
        total_quantity_within_depth = total_buy_within_depth + total_sell_within_depth

        # Calculate percentages
        buy_percentage = (total_buy_within_depth / total_quantity_within_depth) * 100 if total_quantity_within_depth > 0 else 0
        sell_percentage = (total_sell_within_depth / total_quantity_within_depth) * 100 if total_quantity_within_depth > 0 else 0

        # Output the stdout
        if debug:        
            print(defs.now_utc()[1] + "Sunflow: handle_orderbook: Orderbook")
            print(f"Spot price         : {spot}")
            print(f"Lower depth       : {spot - depth}")
            print(f"Upper depth       : {spot + depth}\n")

            print(f"Total Buy quantity : {total_buy_within_depth}")
            print(f"Total Sell quantity: {total_sell_within_depth}")
            print(f"Total quantity     : {total_quantity_within_depth}\n")

            print(f"Buy within depth  : {buy_percentage:.2f}%")
            print(f"Sell within depth : {sell_percentage:.2f}%")

        print(defs.now_utc()[1] + f"Sunflow: handle_orderbook: Orderbook: Market depth (Buy / Sell | depth (Advice)): {buy_percentage:.2f}% / {sell_percentage:.2f}% | {depth}% ", end="")
        if buy_percentage >= sell_percentage:
            print("(BUY)\n")
        else:
            print("(SELL)\n")

    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        filename, line, func, text = tb_info[-1]
        print(defs.now_utc()[1] + f"An error occurred in {filename} on line {line}: {e}")
        print("Full traceback:")
        traceback.print_tb(e.__traceback__)

# Prechecks to see if we can start sunflow
def prechecks():
    
    # Declare some variables global
    global symbol
    
    # Initialize variables
    goahead = True
    
    # Do checks
    if intervals[3] != 0 and intervals[2] == 0:
        goahead = False
        print(defs.now_utc()[1] + "Sunflow: prechecks: Interval 2 must be set if you use interval 3 for confirmation")
        
    if not use_spread['enabled'] and not use_indicators['enabled']:
        goahead = False
        print(defs.now_utc()[1] + "Sunflow: prechecks: Need at least either Technical Indicators enabled or Spread to determine buy action")
    
    # Return result
    return goahead

### Start main program ###

# Check if we can start
if prechecks():

    # Welcome screen
    print("\n*************************")
    print("*** Sunflow Cryptobot ***")
    print("*************************\n")
    print("Symbol    : " + symbol)
    if use_indicators['enabled']:
        print("Interval 1: " + str(intervals[1]) + "m")
        print("Interval 2: " + str(intervals[2]) + "m")
        print("Interval 3: " + str(intervals[3]) + "m")
    if use_spread['enabled']:
        print("Spread    : " + str(use_spread['distance']) + "%")
    print("Limit     : " + str(limit))
    print()
    
    # Preload all requirements
    print("*** Preloading ***\n")

    preload.check_files()
    if intervals[1] !=0  : klines[intervals[1]] = preload.get_klines(symbol, intervals[1], limit)
    if intervals[2] !=0  : klines[intervals[2]] = preload.get_klines(symbol, intervals[2], limit)
    if intervals[3] !=0  : klines[intervals[3]] = preload.get_klines(symbol, intervals[3], limit) # **** CHECK *** Eigenlijk ook technical indicators preloaden zie buy matrix!
    ticker               = preload.get_ticker(symbol)
    spot                 = ticker['lastPrice']
    info                 = preload.get_info(symbol, spot, multiplier)
    all_buys             = preload.get_buys(config.dbase_file) 
    all_buys             = preload.check_orders(all_buys)
    prices               = preload.get_prices(symbol, limit)

    # Delay buy for starting
    if use_delay['enabled']:
        use_delay['start'] = defs.now_utc()[4]
        use_delay['end']   = use_delay['start'] + use_delay['timeframe']
        print(defs.now_utc()[1] + "Sunflow: prechecks: Delaying buy cycle on startup with " + str(use_delay['timeframe']) + "ms\n")

    print("*** Starting ***\n")
    defs.notify(f"Started Sunflow Cryptobot for {symbol}", 1)

else:
    print("*** COULD NOT START ***\n")
    exit()

### Websockets ###

def connect_websocket():
    ws = WebSocket(testnet=False, channel_type="spot")
    return ws

def subscribe_streams(ws):
    # Continuously get tickers from websocket
    ws.ticker_stream(symbol=symbol, callback=handle_ticker)

    # At request get klines from websocket
    if ws_kline:
        ws.kline_stream(interval=intervals[1], symbol=symbol, callback=handle_kline_1)
        # Use second interval as confirmation
        if intervals[2] != 0:
            ws.kline_stream(interval=intervals[2], symbol=symbol, callback=handle_kline_2)
        # Use third interval as confirmation
        if intervals[3] != 0:
            ws.kline_stream(interval=intervals[3], symbol=symbol, callback=handle_kline_3)

    # At request get orderbook from websocket
    if ws_orderbook:
        ws.orderbook_stream(depth=50, symbol=symbol, callback=handle_orderbook)

def main():
    ws = connect_websocket()
    subscribe_streams(ws)

    while True:
        try:
            sleep(1)
        except (RemoteDisconnected, ProtocolError, ChunkedEncodingError) as e:
            message = f"Sunflow: main: Exchange connection lost. Reconnecting due to: {e}"
            print(defs.now_utc()[1] + message + "\n")
            defs.notify(message + f" for {symbol}", 1)
            sleep(5)
            ws = connect_websocket()
            subscribe_streams(ws)

if __name__ == "__main__":
    main()