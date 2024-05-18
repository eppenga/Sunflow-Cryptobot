### Sunflow Cryptobot ###
#
# Order functions

# Load external libraries
from pathlib import Path
import importlib, math, sys
import pandas as pd
from pybit.unified_trading import HTTP

# Load internal libraries
import argparse, database, defs, distance, preload

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

# Connect to exchange
session = HTTP(
    testnet                 = False,
    api_key                 = config.api_key,
    api_secret              = config.api_secret,
    return_response_headers = True
)

# Initialize variables to prevent race conditions
def_buy_active  = False
def_sell_active = False

# Get orderId from exchange order
def order_id(order):
    
    id = order['result']['orderId']
    return id

# Get order history
def history(orderId):
    
    # Debug
    debug = False
    
    # Initialize variables
    order = []
    
    # First try realtime
    message = defs.now_utc()[1] + "Orders: history: session: get_open_orders\n"
    print(message)
    order = {}
    try:
        order = session.get_open_orders(
            category = "spot",
            orderId  = str(orderId)
        )
    except Exception as e:
        defs.log_error(e)

    # Check API rate limit and log data if possible
    if order:
        order = defs.rate_limit(order)
        defs.log_exchange(order, message)
      
    # If realtime fails, get it from history
    if order['result']['list'] == []:
        message = defs.now_utc()[1] + "Orders: history: session: get_order_history\n" 
        print(message)
        try:
            order = session.get_order_history(
                category = "spot",
                orderId  = str(orderId)
            )
        except Exception as e:
            defs.log_error(e)

        # Check API rate limit and log data if possible
        if order:
            order = defs.rate_limit(order)
            defs.log_exchange(order, message)

    # If realtime and history fails, throw an error
    if order['result']['list'] == []:
        message = defs.now_utc()[1] + "Orders: history: Trying to load non-existing order, something is corrupt!"
        defs.log_error(message)

    if debug:
        print(defs.now_utc()[1] + "Orders: OrderId: Order history")
        print(order)

    return order

# Decode order from exchange to proper dictionary
def decode(order):
    
    transaction                 = {}
    transaction['createdTime']  = int(order['result']['list'][0]['createdTime'])
    transaction['updatedTime']  = int(order['result']['list'][0]['updatedTime'])
    transaction['orderId']      = int(order['result']['list'][0]['orderId'])
    transaction['orderLinkId']  = int(order['result']['list'][0]['orderLinkId'])
    transaction['symbol']       = order['result']['list'][0]['symbol']
    transaction['side']         = order['result']['list'][0]['side']
    transaction['orderType']    = order['result']['list'][0]['orderType']
    transaction['orderStatus']  = order['result']['list'][0]['orderStatus']
    transaction['price']        = float(order['result']['list'][0]['price'])
    transaction['avgPrice']     = float(order['result']['list'][0]['avgPrice'])
    transaction['qty']          = float(order['result']['list'][0]['qty'])
    transaction['cumExecQty']   = float(order['result']['list'][0]['cumExecQty'])
    transaction['cumExecValue'] = float(order['result']['list'][0]['cumExecValue'])
    transaction['cumExecFee']   = float(order['result']['list'][0]['cumExecFee'])
    transaction['triggerPrice'] = float(order['result']['list'][0]['triggerPrice'])

    # Return order
    return transaction

# Cancel an order at the exchange
def cancel(symbol, orderid):
    
    # Initialize
    error_code = 0
    exception  = ""
    
    # Cancel order
    message = defs.now_utc()[1] + "Orders: cancel: session: cancel_order\n"
    print(message)
    order = {}
    try:
        order = session.cancel_order(
            category = "spot",
            symbol   = symbol,
            orderId  = str(orderid)
        )
    except Exception as e:
        exception = str(e)
        if "(ErrCode: 170213)" in exception:
            # Order does not exist
            error_code = 1
        else:
            # Any other error
            error_code = 100        
        
    # Check API rate limit and log data if possible
    if order:
        order = defs.rate_limit(order)
        defs.log_exchange(order, message)
        
    # Return error code
    return error_code, exception    

# Turn an order from the exchange into a properly formatted transaction after placing or amending an order
def transaction_from_order(order):

    # Get orderId first
    orderId       = order_id(order)
    order_history = history(orderId)
    transaction   = decode(order_history)
    
    # Return transaction
    return transaction

# Turn an order from the exchange into a properly formatted transaction after the order already exists
def transaction_from_id(orderId):
    
    order_history = history(orderId)
    transaction   = decode(order_history)

    # Return transaction
    return transaction

# Initialize active order for initial buy or sell
def initialize_trigger(spot, active_order, info):

    # Debug
    debug = False

    # Debug
    print(defs.now_utc()[1] + f"initialize_trigger: Fluctuation distance {round(active_order['fluctuation'], 4)}% and price {spot} {info['quoteCoin']}\n")

    # Check side buy or sell
    if active_order['side'] == "Buy":
        active_order['qty']     = info['minBuyQuote']
        active_order['trigger'] = defs.precision(spot * (1 + (active_order['fluctuation'] / 100)), info['tickSize'])
    else:
        active_order['trigger'] = defs.precision(spot * (1 - (active_order['fluctuation'] / 100)), info['tickSize'])

    # Return active_order
    return active_order

# What orders and how much can we sell with profit
def check_sell(spot, profit, active_order, all_buys, info):

    # Initialize variables
    qty               = 0
    counter           = 0
    rise_to           = ""
    nearest           = []
    distance          = active_order['distance']
    can_sell          = False
    all_sells         = []
       
    # Walk through buy database and find profitable buys
    for transaction in all_buys:

        # Only walk through closed buy orders
        if transaction['status'] == 'Closed':
                       
            # Check if a transaction is profitable
            profitable_price = transaction['avgPrice'] * (1 + ((profit + distance) / 100))
            nearest.append(profitable_price - spot)
            if spot >= profitable_price:
                qty = qty + transaction['cumExecQty']
                all_sells.append(transaction)
                counter = counter + 1
    
    # Adjust quantity to exchange regulations
    qty = defs.precision(qty, info['basePrecision'])
    
    # Can sell or not
    if all_sells and qty > 0:
        can_sell = True
        print(defs.now_utc()[1] + "Orders: check_sell: Can sell " + str(counter) + " orders for a total of " + str(qty) + " " + info['baseCoin'] + "\n")
    else:
        if nearest:
            rise_to = str(defs.precision(min(nearest), info['tickSize'])) + " " + info['quoteCoin']
    
    # Return data
    return all_sells, qty, can_sell, rise_to
        
# New buy order
def buy(symbol, spot, active_order, all_buys, prices, info):

    # Define global variables
    global def_buy_active

    # Prevent race condition
    if def_buy_active:
        print(defs.now_utc()[1] + "Orders: buy: function is busy, no further action required\n")
        return active_order, all_buys

    # Output to stdout
    print(defs.now_utc()[1] + "Orders: buy: *** BUY BUY BUY! ***\n")

    # Get latest symbol info
    #info = preload.get_info(symbol, spot, config.multiplier) #*** CHECK *** Better do this when it does not delay execution

    # Set race condition
    def_buy_active = True

    # Initialize active_order
    active_order['side']     = "Buy"
    active_order['active']   = True
    active_order['start']    = spot
    active_order['previous'] = spot
    active_order['current']  = spot

    # Determine distance of trigger price
    active_order = distance.calculate(active_order, prices)

    # Initialize trigger price
    active_order = initialize_trigger(spot, active_order, info)  

    # Place buy order
    message = defs.now_utc()[1] + "Orders: buy: session: place_order\n"
    print(message)
    order = {}
    try:
        order = session.place_order(
            category     = "spot",
            symbol       = symbol,
            side         = "Buy",
            orderType    = "Market",
            orderFilter  = "tpslOrder",
            qty          = str(active_order['qty']),
            triggerPrice = str(active_order['trigger'])
        )
    except Exception as e:
        defs.log_error(e)
        
    # Check API rate limit and log data if possible
    if order:
        order = defs.rate_limit(order)
        defs.log_exchange(order, message)
        
    # Get order info
    active_order['orderid'] = int(order['result']['orderId'])

    # Get the transaction
    transaction = transaction_from_order(order)
    
    # Set the status
    transaction['status'] = "Open"
    message = f"Buy order opened for {active_order['qty']} {info['quoteCoin']} with trigger price {active_order['trigger']} {info['quoteCoin']}"
    print(defs.now_utc()[1] + "Orders: buy: " + message + "\n")
    defs.notify(message + f" for {symbol}", 1)
    
    # Store the transaction in the database buys file
    all_buys = database.register_buy(transaction, all_buys)
    print(defs.now_utc()[1] + "Orders: buy: Registered buy order in database " + config.dbase_file + "\n")

    # Output to stdout
    print(defs.now_utc()[1] + "Orders: buy: Starting trailing buy\n")
    
    # Reset race condition
    def_buy_active = False
    
    # Return trailing order and new buy order database
    return active_order, all_buys
    
# New sell order
def sell(symbol, spot, active_order, prices, info):

    # Define global variables
    global def_buy_active

    # Prevent race condition
    if def_sell_active:
        print(defs.now_utc()[1] + "Orders: sell: function is busy, no further action required\n")
        return active_order

    # Output to stdout
    print(defs.now_utc()[1] + "Orders: sell: *** SELL SELL SELL! ***\n")

    # Set race condition
    def_buy_active = True

    # Initialize active_order
    active_order['side']     = "Sell"
    active_order['active']   = True
    active_order['start']    = spot
    active_order['previous'] = spot
    active_order['current']  = spot
  
    # Determine distance of trigger price
    active_order = distance.calculate(active_order, prices)

    # Initialize trigger price
    active_order = initialize_trigger(spot, active_order, info)

    # Place sell order
    message = defs.now_utc()[1] + "Orders: sell: session: place_order\n"
    print(message)
    order = {}
    try:
        order = session.place_order(
            category     = "spot",
            symbol       = symbol,
            side         = "Sell",
            orderType    = "Market",
            orderFilter  = "tpslOrder",
            qty          = str(active_order['qty']),
            triggerPrice = str(active_order['trigger'])
        )
    except Exception as e:
        defs.log_error(e)
        
    # Check API rate limit and log data if possible
    if order:
        order = defs.rate_limit(order)
        defs.log_exchange(order, message)
    
    # Get order info
    active_order['orderid'] = int(order['result']['orderId'])
    
    # Output to stdout and Apprise
    message = f"Sell order opened for {active_order['qty']} {info['baseCoin']} with trigger price {active_order['trigger']} {info['quoteCoin']}"
    print(defs.now_utc()[1] + message + "\n")
    defs.notify(message + f" for {symbol}", 1)

    # Reset race condition
    def_buy_active = False
    
    # Return data
    return active_order

# Rebalances the database vs exchange
def rebalance(all_buys, info):

    # Debug
    debug = False

    # Initialize variables
    wallet         = ()
    equity_wallet  = 0
    equity_dbase   = 0
    equity_remind  = 0
    equity_lost    = 0
    dbase_changed = False

    # Report to stdout
    if debug:
        print(defs.now_utc()[1] + "Orders: balance_wallet: Trying to rebalance buys database with exchange data\n")

    # Get all buys
    all_buys = preload.get_buys(config.dbase_file)

    # Get wallet
    message = defs.now_utc()[1] + "Orders: rebalance: session: get_wallet_balance\n"
    print(message)
    try:
        wallet = session.get_wallet_balance(
            accountType = "UNIFIED",
            coin        = info['baseCoin']
        )
    except Exception as e:
        defs.log_error(e)
        
    # Check API rate limit and log data if possible
    if wallet:
        wallet = defs.rate_limit(wallet)
        defs.log_exchange(wallet, message)

    # Get equity from wallet
    equity_wallet = float(wallet['result']['list'][0]['coin'][0]['equity'])

    # Get equity from all buys
    equity_dbase  = float(sum(order['cumExecQty'] for order in all_buys))
    equity_remind = equity_dbase

    # Report
    if debug:
        print(defs.now_utc()[1] + "Orders: balance_wallet: Before rebalance equity on exchange: " + str(equity_wallet) + " " + info['baseCoin'])
        print(defs.now_utc()[1] + "Orders: balance_wallet: Before rebalance equity in database: " + str(equity_dbase) + " " + info['baseCoin'])

    # Selling more than we have
    while equity_dbase > equity_wallet:
        
        # Database changed
        dbase_changed = True
        
        # Find the item with the lowest avgPrice
        lowest_avg_price_item = min(all_buys, key=lambda x: x['avgPrice'])

        # Remove this item from the list
        all_buys.remove(lowest_avg_price_item)
        
        # Recalculate all buys
        equity_dbase = sum(order['cumExecQty'] for order in all_buys)    

    # Report
    if debug:
        print(defs.now_utc()[1] + "Orders: balance_wallet: After rebalance equity on exchange: " + str(equity_wallet) + " " + info['baseCoin'])
        print(defs.now_utc()[1] + "Orders: balance_wallet: After rebalance equity in database: " + str(equity_dbase) + " " + info['baseCoin'] + "\n")

    # Save new database
    if dbase_changed:
        equity_lost = equity_remind - equity_dbase
        print(defs.now_utc()[1] + "Orders: balance_wallet: Rebalanced buys database with exchange data and lost " + str(equity_lost) + " " + info['baseCoin'] + "\n")
        database.save(all_buys)

    # Return all buys
    return all_buys