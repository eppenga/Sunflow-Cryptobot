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
import importlib, sys, traceback

# Load default config file or from command line
if len(sys.argv) > 1:
    config_file = sys.argv[1]
else:
    config_file = "config"

# Check if config file exists
check_path = Path(config_file + ".py")
if not check_path.exists():
    print("Config file not found, aborting...\n")
    exit()

# Load internal libraries
import defs, preload, indicators, trailing, orders

# Load config file dynamically
config = importlib.import_module(config_file)

### Initialize variables ###

# Set default values
debug                        = config.debug                   # Debug
symbol                       = config.symbol                  # Symbol bot used for trading
klines                       = {}                             # Klines for symbol
interval_1                   = config.interval_1              # Klines timeframe interval 1
interval_2                   = config.interval_2              # Klines timeframe interval 2
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
use_spread['enabled']        = config.spread_enabled          # Use spread
use_spread['distance']       = config.spread_distance         # Minimum spread in percentages

# Technical indicators
use_indicators               = {}                             # Technical indicators
use_indicators['enabled']    = config.indicators_enabled      # Use technical indicators
use_indicators['minimum']    = config.indicators_minimum      # Minimum advice value
use_indicators['maximum']    = config.indicators_maximum      # Maximum advice value

# Orderbook
use_orderbook                = {}                             # Orderbook
use_orderbook['enabled']     = config.orderbook_enabled       # Use orderbook
use_orderbook['minimum']     = config.orderbook_minimum       # Minimum orderbook percentage
use_orderbook['maximum']     = config.orderbook_maximum       # Maximum orderbook percentage

# Wave measurement
use_waves                    = {}
use_waves['enabled']         = False
if config.wiggle == "Wave"   : use_waves['enabled'] = True
use_waves['timeframe']       = config.wave_timeframe

# Spike detection
use_spikes                   = {}                             # Spikes
use_spikes['enabled']        = config.spike_enabled           # Use spike detection
use_spikes['timeframe']      = config.spike_timeframe         # Timeframe in ms to measure spikes
use_spikes['threshold']      = config.spike_threshold         # Threshold to reach within timeframe as percentage

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
if config.indicators_enabled : ws_kline     = True             # Use klines websocket
if config.orderbook_enabled  : ws_orderbook = True             # Use orderbook websocket

# Set technical advice variable
technical_advice             = {}
technical_advice[interval_1] = {'result': False, 'value': 0, 'level': 'Neutral'}
technical_advice[interval_2] = {'result': False, 'value': 0, 'level': 'Neutral'}

### Functions ###

# Handle messages to keep tickers up to date
def handle_ticker(message):
    
    # Errors are not reported within websocket
    try:
   
        # Declare some variables global
        global spot, ticker, active_order, all_buys, all_sells, prices

        # Initialize variables
        result      = ()
        ticker      = {}
        spiking     = False
        amend_code  = 0
        amend_error = ""

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
                result       = trailing.trail(symbol, active_order, info, all_buys, all_sells, prices)
                active_order = result[0]
                all_buys     = result[1]

            # Check if and how much we can sell
            result                  = orders.check_sell(new_spot, profit, active_order, all_buys, info)
            all_sells_new           = result[0]
            active_order['qty_new'] = result[1]
            can_sell                = result[2]
            rise_to                 = result[3]

            # Output to stdout
            print(defs.now_utc()[1] + "Sunflow: handle_ticker: lastPrice changed from " + str(spot) + " " + info['quoteCoin'] + " to " + str(new_spot) + " " + info['quoteCoin'], end="")
            if not active_order['active']:
                if rise_to:
                    print(", needs to rise " + rise_to + ", NO SELL", end="")
                else:
                    if len(all_buys) > 0:
                        print(", SELL", end="")
            print("\n")
            
            # If trailing buy is already running while we can sell
            if active_order['active'] and active_order['side'] == "Buy" and can_sell:
                print(defs.now_utc()[1] + "Sunflow: handle_ticker: *** Warning loosing money, we can sell while we are buying! ***\n")
                # Cancel trailing buy order *** CHECK *** To be implemented!
                # Remove from all_buys database
                # set active_order["side"] to Sell

            # Initiate first sell
            if not active_order['active'] and can_sell:
                # There is no old quantity on first sell
                active_order['qty'] = active_order['qty_new']
                # Fill all_sells for the first time
                all_sells = all_sells_new
                # Initialize active_order
                active_order = orders.initialize_active_order(new_spot, active_order, info, "Sell")
                # Determine distance of trigger price
                active_order = orders.distance(active_order, prices)
                # Place the first sell order
                active_order = orders.sell(symbol, active_order, info)

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
                        print(defs.now_utc()[1] + "Sunflow: handle_ticker: Adjusted quantity from " + str(active_order['qty']) + " " + info['baseCoin'] + " to " +  str(active_order['qty_new']) + " " + info['quoteCoin'] + "\n")
                        active_order['qty'] = active_order['qty_new']
                        all_sells           = all_sells_new
                    if amend_code == 1:
                        # Order slipped, close trailing process
                        print(defs.now_utc()[1] + "Trailing: trail: Order slipped, we keep buys database as is and stop trailing\n")
                        result       = trailing.close_trail(active_order, all_buys, all_sells)
                        active_order = result[0]
                        all_buys     = result[1]
                        all_sells    = result[2]
                        # Revert old situation
                        all_sells_new = all_sells
                    if amend_code == 100:
                        # Critical error, let's log it and revert
                        all_sells_new = all_sells
                        print(defs.now_utc()[1] + "Trailing: trail: Critical error, logging to file\n")
                        defs.log_error(amend_error)

                # Reset all sells
                #all_sells = all_sells_new

            # Spiking, when not buying or selling, let's buy and see what happens :)
            if not active_order['active'] and spiking:
                print(defs.now_utc()[1] + "Sunflow: handle_ticker: Spike detected, initiate buying!\n")
                active_order = orders.initialize_active_order(new_spot, active_order, info, "Buy")
                result       = orders.buy(symbol, active_order, all_buys, info)
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
    handle_kline(message, interval_1)

def handle_kline_2(message):
    handle_kline(message, interval_2)

# Handle messages to keep klines up to date
def handle_kline(message, interval):

    # Errors are not reported within websocket
    try:

        # Declare some variables global
        global klines, active_order, all_buys, technical_advice

        # Initialize variables
        can_buy              = False
        kline                = {}
        spread_advice        = {} 
        orderbook_advice     = {}
        technical_indicators = {}
        result               = ()
     
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
            print(defs.now_utc()[1] + "Sunflow: handle_kline: Added new kline with interval "  + str(interval) + "m onto existing " + str(klines_count) + " klines\n")
            klines[interval] = defs.new_kline(kline, klines[interval])
      
        else:            
            # Remove the first kline and replace with fresh kline
            klines[interval] = defs.update_kline(kline, klines[interval])
        
        # Only initiate buy and do complex calculations when not already trailing
        if not active_order['active']:
            
            # Check TECHNICAL INDICATORS for buy decission
            if use_indicators['enabled']:
                technical_indicators                = indicators.calculate(klines[interval], spot)
                result                              = indicators.advice(technical_indicators)
                technical_advice[interval]['value'] = result[0]
                technical_advice[interval]['level'] = result[1]

                # Check if technical advice is within range
                if (technical_advice[interval]['value'] >= use_indicators['minimum']) and (technical_advice[interval]['value'] <= use_indicators['maximum']):
                    technical_advice[interval]['result'] = True
                else:
                    technical_advice[interval]['result'] = False
            else:
                # If indicators are not enabled, always true
                technical_advice[interval]['result'] = True
            
            # Check SPREAD for buy decission
            if use_spread['enabled']:
                result                   = defs.check_spread(all_buys, spot, use_spread['distance'])
                spread_advice['result']  = result[0]
                spread_advice['nearest'] = round(result[1], 2)
            else:
                # If spread is not enabled, always true
                spread_advice['result'] = True

            # Check ORDERBOOK for buy decission *** CHECK *** To be implemented
            if use_orderbook['enabled']:
                # Put orderbook logic here
                orderbook_advice['value']  = 0
                orderbook_advice['result'] = True
            else:
                # If orderbook is not enabled, always true
                orderbook_advice['result'] = True
            
            # Get buy decission and report
            result  = defs.decide_buy(technical_advice, use_indicators, spread_advice, use_spread, orderbook_advice, use_orderbook, interval)
            can_buy = result[0]
            message = result[1]
            print(defs.now_utc()[1] + "Sunflow: handle_kline: " + message + "\n")
            
            # Determine distance of trigger price and execute buy decission
            if can_buy:
                active_order = orders.initialize_active_order(spot, active_order, info, "Buy")
                active_order = orders.distance(active_order, prices)
                result       = orders.buy(symbol, active_order, all_buys, info)
                active_order = result[0]
                all_buys     = result[1]

    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        filename, line, func, text = tb_info[-1]
        print(defs.now_utc()[1] + f"An error occurred in {filename} on line {line}: {e}")
        print("Full traceback:")
        traceback.print_tb(e.__traceback__)
    
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
    if not ws_kline and not ws_orderbook:
        goahead = False     
        print(defs.now_utc()[1] + "Sunflow: prechecks: ws_klines and ws_orderbook can't both be False")
    
    if not use_spread['enabled'] and not use_indicators['enabled']:
        goahead = False
        print(defs.now_utc()[1] + "Sunflow: prechecks: Indicators and Spread can't both be False")
        
    if not ws_kline and use_indicators['enabled']:
        goahead = False
        print(defs.now_utc()[1] + "Sunflow: prechecks: Must set ws_kline to True when indicators are enabled")

    if not ws_kline and use_orderbook['enabled']:
        goahead = False
        print(defs.now_utc()[1] + "Sunflow: prechecks: Must set ws_orderbook to True when orderbook is enabled")
        
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
    print("Interval 1: " + str(interval_1) + "m")
    print("Interval 2: " + str(interval_2) + "m")
    print("Limit     : " + str(limit))
    print()
    
    # Preload all requirements
    print("*** Preloading ***\n")

    preload.check_files()
    klines[interval_1] = preload.get_klines(symbol, 1, limit)
    klines[interval_2] = preload.get_klines(symbol, 3, limit)
    ticker             = preload.get_ticker(symbol)
    spot               = ticker['lastPrice']
    info               = preload.get_info(symbol, spot, multiplier)
    all_buys           = preload.get_buys(config.dbase_file) 
    all_buys           = preload.check_orders(all_buys)
    prices             = {
        'time': klines[interval_1]['time'],
        'price': klines[interval_1]['close']
    }

    print("*** Starting ***\n")

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
        ws.kline_stream(interval=interval_1, symbol=symbol, callback=handle_kline_1)
        # Use second interval as confirmation
        if interval_2 != 0:
            ws.kline_stream(interval=interval_2, symbol=symbol, callback=handle_kline_2)

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
            print(defs.now_utc()[1] + f"Sunflow: main: Connection lost. Reconnecting due to: {e}")
            sleep(5)
            ws = connect_websocket()
            subscribe_streams(ws)

if __name__ == "__main__":
    main()