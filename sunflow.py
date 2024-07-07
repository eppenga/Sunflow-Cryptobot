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
import argparse, importlib, pprint, sys, traceback

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
trades                       = {}                             # Trades for symbol
limit                        = config.limit                   # Number of klines downloaded, used for calculcating technical indicators
ticker                       = {}                             # Ticker data, including lastPrice and time
info                         = {}                             # Instrument info on symbol
spot                         = 0                              # Spot price, always equal to lastPrice
profit                       = config.profit                  # Minimum profit percentage
depth                        = config.depth                   # Depth in percentages used to calculate market depth from orderbook
multiplier                   = config.multiplier              # Multiply minimum order quantity by this
prices                       = {}                             # Last {limit} prices based on ticker
depth_data                   = {}                             # Depth buy and sell percentage indexed by time

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
use_orderbook['minimum']     = config.orderbook_minimum       # Minimum orderbook buy percentage
use_orderbook['maximum']     = config.orderbook_maximum       # Maximum orderbook buy percentage
use_orderbook['average']     = config.orderbook_average       # Average out orderbook depth data or use last data point
use_orderbook['limit']       = config.orderbook_limit         # Number of orderbook data elements to keep in database
use_orderbook['timeframe']   = config.orderbook_timeframe     # Timeframe for averaging out

# Trade
use_trade                    = {}
use_trade['enabled']         = config.trade_enabled           # Use realtime trades as buy trigger
use_trade['minimum']         = config.trade_minimum           # Minimum trade buy ratio percentage
use_trade['maximum']         = config.trade_maximum           # Maximum trade buy ratio percentage
use_trade['limit']           = config.trade_limit             # Number of trade orders to keep in database
use_trade['timeframe']       = config.trade_timeframe         # Timeframe in ms to collect realtime trades

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
ws_trade                     = False                          # Initialize ws_trade
if config.indicators_enabled : ws_kline     = True            # Use klines websocket
if config.orderbook_enabled  : ws_orderbook = True            # Use orderbook websocket
if config.trade_enabled      : ws_trade     = True            # Use trade websocker

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

# Initialize orderbook advice variable
orderbook_advice                = {}
orderbook_advice['buy_perc']    = 0
orderbook_advice['sell_perc']   = 0
orderbook_advice['result']      = False

# Initialize trade advice variable
trade_advice                    = {}
trade_advice['buy_ratio']       = 0
trade_advice['sell_ratio']      = 0
trade_advice['result']          = False

# Initialize trades variable
trades                          = {'time': [], 'side': [], 'size': [], 'price': []}

# Initialize depth variable
depth_data                      = {'time': [], 'buy_perc': [], 'sell_perc': []}

# Locking handle_ticker function to prevent race conditions
lock_ticker                     = {}
lock_ticker['time']             = defs.now_utc()[4]
lock_ticker['enabled']          = False


### Functions ###

# Handle messages to keep tickers up to date
def handle_ticker(message):
    
    # Debug
    debug = False
    
    # Errors are not reported within websocket
    try:
   
        # Declare some variables global
        global spot, ticker, active_order, all_buys, all_sells, prices, indicators_advice, lock_ticker

        # Initialize variables
        ticker              = {}
        amend_code          = 0
        amend_error         = ""
        result              = ()
        lock_ticker['time'] = defs.now_utc()[4]
        
        # Get ticker update
        ticker['time']      = int(message['ts'])
        ticker['lastPrice'] = float(message['data']['lastPrice'])
        ticker['simulated'] = False
        if message['data'].get('simulated', False):
            ticker['simulated'] = True

        # Popup new price
        prices['time'].append(ticker['time'])
        prices['price'].append(ticker['lastPrice'])
        prices['time'].pop(0)
        prices['price'].pop(0)

        # Show incoming message
        if debug: defs.announce(f"*** Incoming ticker with price {ticker['lastPrice']} {info['baseCoin']}, simulated = {ticker['simulated']} ***")

        # Prevent race conditions
        if lock_ticker['enabled']:
            spot = ticker['lastPrice']
            defs.announce("Function is busy, Sunflow will catch up with next tick")
            return
        
        # Lock handle_ticker function
        lock_ticker['enabled'] = True        
          
        # Run trailing if active
        if active_order['active']:
            active_order['current'] = ticker['lastPrice']
            active_order['status']  = 'Trailing'
            result       = trailing.trail(symbol, ticker['lastPrice'], active_order, info, all_buys, all_sells, prices)
            active_order = result[0]
            all_buys     = result[1]

        # Has price changed, then run all kinds of actions
        if spot != ticker['lastPrice']:
            new_spot = ticker['lastPrice']

            # Check if and how much we can sell
            result                  = orders.check_sell(new_spot, profit, active_order, all_buys, info)
            all_sells_new           = result[0]
            active_order['qty_new'] = result[1]
            can_sell                = result[2]
            rise_to                 = result[3]

            # Output to stdout
            message = defs.report_ticker(spot, new_spot, rise_to, active_order, all_buys, info)
            defs.announce(message)
            
            # If trailing buy is already running while we can sell
            if active_order['active'] and active_order['side'] == "Buy" and can_sell:
                
                # Output to stdout and Apprise
                defs.announce("*** Warning: Loosing money! Buying whilest selling is possible, trying to cancel buy order! ***", True, 1)
                
                # Cancel trailing buy, remove from all_buys database
                active_order['active'] = False
                result     = orders.cancel(symbol, active_order['orderid'])
                error_code = result[0]
                
                if error_code == 0:
                    # Situation normal, just remove the order
                    defs.announce("Buy order cancelled successfully", True, 1)
                    all_buys = database.remove(active_order['orderid'], all_buys, info)

                if error_code == 1:
                    # Trailing buy was bought
                    defs.announce("Buy order could not be cancelled, closing trailing buy", True, 1)
                    result       = trailing.close_trail(active_order, all_buys, all_sells, info)
                    active_order = result[0]
                    all_buys     = result[1]
                    all_sells    = result[2]
                    
                if error_code == 100:
                    # Something went very wrong
                    defs.log_error(result[1])
                
            # Initiate sell
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
                        message = f"Adjusted quantity from {defs.format_number(active_order['qty'], info['basePrecision'])} "
                        message = message + f"to {defs.format_number(active_order['qty_new'], info['basePrecision'])} {info['baseCoin']} in {active_order['side'].lower()} order"
                        defs.announce(message, True, 0)
                        all_sells           = all_sells_new
                        active_order['qty'] = active_order['qty_new']

                    if amend_code == 1:
                        # Order does not exist, trailing order was sold in between
                        all_sells_new = all_sells
                        defs.announce("Adjusting trigger quantity no possible, sell order already hit", True, 0)
                        
                    if amend_code == 2:
                        # Quantity could not be changed, do nothing
                        all_sells_new = all_sells
                        defs.announce("Sell order quantity could not be changed, doing nothing", True, 0)
                        
                    if amend_code == 10:
                        all_sells_new = all_sells                        
                        # Order does not support modification, do nothing
                        defs.announce("Sell order quantity could not be changed, order does not support modification", True, 0)                        

                    if amend_code == 100:
                        # Critical error, let's log it and revert
                        defs.announce("Critical error while trailing", True, 1)
                        defs.log_error(amend_error)

            # Work as a true gridbot when only spread is used
            if use_spread['enabled'] and not use_indicators['enabled'] and not active_order['active']:
                active_order = buy_matrix(new_spot, active_order, all_buys, intervals[1])

    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        filename, line, func, text = tb_info[-1]
        defs.announce(f"An error occurred in {filename} on line {line}: {e}")
        traceback.print_tb(e.__traceback__)

    # Always set new spot price and unlock function
    spot = ticker['lastPrice']
    lock_ticker['enabled'] = False
    
    # Close function
    return

def handle_kline_1(message):
    handle_kline(message, intervals[1])
    return

def handle_kline_2(message):
    handle_kline(message, intervals[2])
    return

def handle_kline_3(message):
    handle_kline(message, intervals[3])
    return

# Handle messages to keep klines up to date
def handle_kline(message, interval):

    # Errors are not reported within websocket
    try:

        # Declare some variables global
        global klines, active_order, all_buys, indicators_advice

        # Initialize variables
        kline = {}
     
        # Show incoming message
        if debug: defs.announce(f"*** Incoming kline with interval {interval}m ***")

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
            defs.announce(f"Added new {interval}m interval onto existing {klines_count} klines")
            klines[interval] = defs.new_kline(kline, klines[interval])
      
        else:            
            # Remove the first kline and replace with fresh kline
            klines[interval] = defs.update_kline(kline, klines[interval])
        
        # Run buy matrix
        active_order = buy_matrix(spot, active_order, all_buys, interval)

    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        filename, line, func, text = tb_info[-1]
        defs.announce(f"An error occurred in {filename} on line {line}: {e}")
        traceback.print_tb(e.__traceback__)
    
    # Close function
    return

# Handle messages to keep orderbook up to date
def handle_orderbook(message):
    
    # Debug
    debug_1 = False    # Show orderbook
    debug_2 = False    # Show buy and sell depth percentages

    # Errors are not reported within websocket
    try:

        # Declare some variables global
        global orderbook_advice, depth_data
        
        # Initialize variables
        total_buy_within_depth  = 0
        total_sell_within_depth = 0
          
        # Show incoming message
        if debug: defs.announce("*** Incoming orderbook ***")
        
        # Recalculate depth to numerical value
        depthN = ((2 * depth) / 100) * spot
        
        # Extracting bid (buy) and ask (sell) arrays
        bids = message['data']['b']
        asks = message['data']['a']

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
        buy_percentage  = (total_buy_within_depth / total_quantity_within_depth) * 100 if total_quantity_within_depth > 0 else 0
        sell_percentage = (total_sell_within_depth / total_quantity_within_depth) * 100 if total_quantity_within_depth > 0 else 0

        # Output the stdout
        if debug_1:        
            defs.announce("Orderbook")
            print(f"Spot price        : {spot}")
            print(f"Lower depth       : {spot - depth}")
            print(f"Upper depth       : {spot + depth}\n")

            print(f"Total Buy quantity : {total_buy_within_depth}")
            print(f"Total Sell quantity: {total_sell_within_depth}")
            print(f"Total quantity     : {total_quantity_within_depth}\n")

            print(f"Buy within depth  : {buy_percentage:.2f} %")
            print(f"Sell within depth : {sell_percentage:.2f} %")

        # Announce message only if it changed and debug
        if debug_2:
            if (buy_percentage != orderbook_advice['buy_perc']) or (sell_percentage != orderbook_advice['sell_perc']):
                message = f"Orderbook information (Buy / Sell | Depth): {buy_percentage:.2f} % / {sell_percentage:.2f} % | {depth} % "
                defs.announce(message)
        
        # Popup new depth data
        depth_data['time'].append(defs.now_utc()[4])
        depth_data['buy_perc'].append(buy_percentage)
        depth_data['sell_perc'].append(sell_percentage)
        if len(depth_data['time']) > use_orderbook['limit']:
            depth_data['time'].pop(0)
            depth_data['buy_perc'].pop(0)        
            depth_data['sell_perc'].pop(0)

        # Get average buy and sell percentage for timeframe
        new_buy_percentage  = buy_percentage
        new_sell_percentage = sell_percentage
        if use_orderbook['average']:
            result              = defs.average_depth(depth_data, use_orderbook, buy_percentage, sell_percentage)
            new_buy_percentage  = result[0]
            new_sell_percentage = result[1]
        
        # Set orderbook_advice
        orderbook_advice['buy_perc']  = new_buy_percentage
        orderbook_advice['sell_perc'] = new_sell_percentage

    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        filename, line, func, text = tb_info[-1]
        defs.announce(f"An error occurred in {filename} on line {line}: {e}")
        traceback.print_tb(e.__traceback__)
    
    # Close function
    return

# Handle messages to keep trades up to date
def handle_trade(message):
    
    # Debug
    debug_1 = False
    debug_2 = False

    # Declare some variables global
    global trade_advice, trades
    
    # Initialize variables
    result     = ()
    datapoints = {}
    compare    = {'time': [], 'side': [], 'size': [], 'price': []}
   
    # Errors are not reported within websocket
    try:

        # Show incoming message
        if debug_1: 
            defs.announce("*** Incoming trade ***")
            print(f"{message}\n")
                        
        # Combine the trades
        for trade in message['data']:
            trades['time'].append(trade['T'])      # T: Timestamp
            trades['side'].append(trade['S'])      # S: Side
            trades['size'].append(trade['v'])      # v: Trade size
            trades['price'].append(trade['p'])     # p: Trade price
    
        # Limit number of trades
        if len(trades['time']) > use_trade['limit']:
            trades['time']  = trades['time'][-use_trade['limit']:]
            trades['side']  = trades['side'][-use_trade['limit']:]
            trades['size']  = trades['size'][-use_trade['limit']:]
            trades['price'] = trades['price'][-use_trade['limit']:]
    
        # Number of trades to use for timeframe
        number = defs.get_index_number(trades, use_trade['timeframe'], use_trade['limit'])
        compare['time']  = trades['time'][-number:]
        compare['side']  = trades['side'][-number:]
        compare['size']  = trades['size'][-number:]
        compare['price'] = trades['price'][-number:]        
    
        # Get trade_advice
        result = defs.calculate_total_values(compare)        
        trade_advice['buy_ratio']  = result[3]
        trade_advice['sell_ratio'] = result[4]
        
        # Validate data
        datapoints['trade']   = len(trades['time'])
        datapoints['compare'] = len(compare['time'])
        datapoints['limit']   = use_trade['limit']
        if (datapoints['compare'] >= datapoints['trade']) and (datapoints['trade'] >= datapoints['limit']):
            defs.announce("*** Warning: Increase trade_limit variable in config file ***", True, 1)
        
        # Debug
        if debug_2:
            message = f"There are {datapoints['trade']} / {datapoints['limit']} data points, "
            message = message + f"using the last {datapoints['compare']} points and "
            message = message + f"buy ratio is {trade_advice['buy_ratio']:.2f} %"
            defs.announce(message)
    
    # Report error
    except Exception as e:
        tb_info = traceback.extract_tb(e.__traceback__)
        filename, line, func, text = tb_info[-1]
        defs.announce(f"An error occurred in {filename} on line {line}: {e}")
        traceback.print_tb(e.__traceback__)
       
    # Close function
    return

# Check if we can buy the based on signals
def buy_matrix(spot, active_order, all_buys, interval):

    # Declare some variables global
    global indicators_advice, orderbook_advice, trade_advice, info
    
    # Initialize variables
    can_buy                = False
    spread_advice          = {}
    result                 = ()    
          
    # Only initiate buy and do complex calculations when not already trailing
    if not active_order['active']:
        
        # Get buy advice
        result            = defs.advice_buy(indicators_advice, orderbook_advice, trade_advice, use_indicators, use_spread, use_orderbook, use_trade, spot, klines, all_buys, interval)
        indicators_advice = result[0]
        spread_advice     = result[1]
        orderbook_advice  = result[2]
        trade_advice      = result[3]
                    
        # Get buy decission and report
        result            = defs.decide_buy(indicators_advice, use_indicators, spread_advice, use_spread, orderbook_advice, use_orderbook, trade_advice, use_trade, interval, intervals)
        can_buy           = result[0]
        message           = result[1]
        defs.announce(message)

        # Determine distance of trigger price and execute buy decission
        if can_buy:
            result       = orders.buy(symbol, spot, active_order, all_buys, prices, info)
            active_order = result[0]
            all_buys     = result[1]
            info         = result[2]
    
    # Return active_order
    return active_order

# Prechecks to see if we can start sunflow
def prechecks():
    
    # Declare some variables global
    global symbol
    
    # Initialize variables
    goahead = True
    
    # Do checks
    if intervals[3] != 0 and intervals[2] == 0:
        goahead = False
        defs.announce("Interval 2 must be set if you use interval 3 for confirmation")
        
    if not use_spread['enabled'] and not use_indicators['enabled']:
        goahead = False
        defs.announce("Need at least either Technical Indicators enabled or Spread to determine buy action")
    
    # Return result
    return goahead


### Start main program ###

# Check if we can start
if not prechecks():
    defs.announce("*** NO START ***", True, 1)
    exit()
    
# Display welcome screen
print("\n*************************")
print("*** Sunflow Cryptobot ***")
print("*************************\n")
print(f"Symbol    : {symbol}")
if use_indicators['enabled']:
    print(f"Interval 1: {intervals[1]}m")
    print(f"Interval 2: {intervals[2]}m")
    print(f"Interval 3: {intervals[3]}m")
if use_spread['enabled']:
    print(f"Spread    : {use_spread['distance']} %")
print(f"Profit    : {profit} %")
print(f"Limit     : {limit}\n")

# Preload all requirements
print("\n*** Preloading ***\n")

preload.check_files()
if intervals[1] !=0  : klines[intervals[1]] = preload.get_klines(symbol, intervals[1], limit)
if intervals[2] !=0  : klines[intervals[2]] = preload.get_klines(symbol, intervals[2], limit)
if intervals[3] !=0  : klines[intervals[3]] = preload.get_klines(symbol, intervals[3], limit)
ticker               = preload.get_ticker(symbol)
spot                 = ticker['lastPrice']
info                 = preload.get_info(symbol, spot, multiplier)
all_buys             = database.load(config.dbase_file, info) 
all_buys             = preload.check_orders(all_buys, info)
if config.database_rebalance: all_buys = orders.rebalance(all_buys, info)
prices               = preload.get_prices(symbol, limit)

# Announce start
print("\n*** Starting ***\n")
defs.announce(f"Sunflow started at {defs.now_utc()[0]} UTC", True, 1)


### Websockets ###

# Connect websocket
def connect_websocket():
    ws = WebSocket(testnet=False, channel_type="spot")
    return ws

# Continuously get tickers from websocket
def subscribe_streams(ws):
    
    # Always stream ticker information
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
        ws.orderbook_stream(depth=200, symbol=symbol, callback=handle_orderbook)
        
    # At request get trades from websocket
    if ws_trade:
        ws.trade_stream(symbol=symbol, callback=handle_trade)

# Fire ticker at least everysecond
def simulated_ticker():
    return {
        'ts': defs.now_utc()[4],
        'data': {
            'lastPrice': str(spot),
            'simulated': "True"
        }
    }

def main():
    ws = connect_websocket()
    subscribe_streams(ws)

    while not defs.halt_sunflow:
        try:
            # Simulate or fetch the latest ticker message
            current_time      = defs.now_utc()[4]
            simulated_message = simulated_ticker()
            if current_time - lock_ticker['time'] > 1000:
                handle_ticker(simulated_message)
            sleep(1)
        except (RemoteDisconnected, ProtocolError, ChunkedEncodingError) as e:
            exception = str(e)
            message   = f"Exchange connection lost. Reconnecting due to: {exception}"
            defs.announce(message, True, 1)
            sleep(5)
            ws = connect_websocket()
            subscribe_streams(ws)

if __name__ == "__main__" and not defs.halt_sunflow:
    main()


### Say goodbye ###
defs.announce(f"*** Sunflow terminated at {defs.now_utc()[0]} UTC ***", True, 1)
