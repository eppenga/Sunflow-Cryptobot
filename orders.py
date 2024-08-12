### Sunflow Cryptobot ###
#
# Order functions

# Load libraries
from loader import load_config
from pybit.unified_trading import HTTP
import database, defs, distance, pprint, preload

# Load config
config = load_config()

# Connect to exchange
session = HTTP(
    testnet                 = False,
    api_key                 = config.api_key,
    api_secret              = config.api_secret,
    return_response_headers = True
)

# Get orderId from exchange order
def order_id(order):
    
    # Logic
    id = order['result']['orderId']
    return id

# Get order history
def history(orderId):
    
    # Debug
    debug = False
       
    # First try realtime
    order   = {}
    message = defs.announce("session: get_open_orders")
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
        message = defs.announce("session: get_order_history") 
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
        message = defs.announce("Trying to load non-existing order, something is corrupt!")
        defs.log_error(message)

    if debug:
        defs.announce("Order history")
        print(order)

    return order

# Decode order from exchange to proper dictionary
def decode(order):
    
    # Initialize transaction
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
    order   = {}
    message = defs.announce("session: cancel_order")
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
def set_trigger(spot, active_order, info):

    # Debug
    defs.announce(f"Trigger price distance {active_order['fluctuation']:.4f} % and price {defs.format_number(spot, info['tickSize'])} {info['quoteCoin']}")

    # Check side buy or sell
    if active_order['side'] == "Buy":
        active_order['qty']     = info['minBuyQuote']
        active_order['trigger'] = defs.round_number(spot * (1 + (active_order['fluctuation'] / 100)), info['tickSize'], "up")
    else:
        active_order['trigger'] = defs.round_number(spot * (1 - (active_order['fluctuation'] / 100)), info['tickSize'], "down")
        
    # Set initial trigger price so we can remember
    active_order['trigger_ini'] = active_order['trigger']

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
    qty = defs.round_number(qty, info['basePrecision'], "down")
    
    # Can sell or not
    if all_sells and qty > 0:
        can_sell = True
        defs.announce(f"Trying to sell {counter} orders for a total of {defs.format_number(qty, info['basePrecision'])} {info['baseCoin']}")
    else:
        if nearest:
            rise_to = f"{defs.format_number(min(nearest), info['tickSize'])} {info['quoteCoin']}"
    
    # Return data
    return all_sells, qty, can_sell, rise_to
        
# New buy order
def buy(symbol, spot, active_order, all_buys, prices, info):

    # Output to stdout
    defs.announce("*** BUY BUY BUY! ***")

    # Recalculate minimum values
    info = preload.calc_info(info, spot, config.multiplier)

    # Initialize active_order
    active_order['side']     = "Buy"
    active_order['active']   = True
    active_order['start']    = spot
    active_order['previous'] = spot
    active_order['current']  = spot

    # Determine distance of trigger price
    active_order = distance.calculate(active_order, prices)

    # Initialize trigger price
    active_order = set_trigger(spot, active_order, info)  

    # Place buy order
    order   = {}
    message = defs.announce("session: place_order")
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
        
        # Buy order failed, reset active_order and return
        active_order['active'] = False
        defs.announce("Buy order failed due to error, trailing stopped")
        return active_order, all_buys
        
    # Check API rate limit and log data if possible
    if order:
        order = defs.rate_limit(order)
        defs.log_exchange(order, message)
        
    # Get order info
    active_order['orderid'] = int(order['result']['orderId'])

    # Report to stdout
    message = f"Buy order opened for {defs.format_number(active_order['qty'], info['quotePrecision'])} {info['quoteCoin']} "
    message = message + f"at trigger price {defs.format_number(active_order['trigger'], info['tickSize'])} {info['quoteCoin']} "
    message = message + f"with order ID {active_order['orderid']}"
    defs.announce(message, True)

    # Get the transaction
    transaction = transaction_from_order(order)
    transaction['status'] = "Open"

    # Store the transaction in the database buys file
    all_buys = database.register_buy(transaction, all_buys, info)
    defs.announce(f"Registered buy order in database {config.dbase_file}")

    # Return trailing order and new buy order database
    return active_order, all_buys, info
    
# New sell order
def sell(symbol, spot, active_order, prices, info):

    # Output to stdout
    defs.announce("*** SELL SELL SELL! ***")

    # Initialize active_order
    active_order['side']     = "Sell"
    active_order['active']   = True
    active_order['start']    = spot
    active_order['previous'] = spot
    active_order['current']  = spot
  
    # Determine distance of trigger price
    active_order = distance.calculate(active_order, prices)

    # Initialize trigger price
    active_order = set_trigger(spot, active_order, info)

    # Place sell order
    order   = {}
    message = defs.announce("session: place_order")
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

        # Sell order failed, reset active_order and return
        active_order['active'] = False
        defs.announce("Sell order failed due to error, trailing stopped")
        return active_order
        
    # Check API rate limit and log data if possible
    if order:
        order = defs.rate_limit(order)
        defs.log_exchange(order, message)
    
    # Get order info
    active_order['orderid'] = int(order['result']['orderId'])
    
    # Output to stdout and Apprise
    message = f"Sell order opened for {defs.format_number(active_order['qty'], info['basePrecision'])} {info['baseCoin']} "
    message = message + f"at trigger price {defs.format_number(active_order['trigger'], info['tickSize'])} {info['quoteCoin']} "
    message = message + f"with order ID {active_order['orderid']}"
    defs.announce(message, True)
   
    # Return data
    return active_order

# Handle equity requests safely
def equity_safe(equity):
    
    # Do logic
    if equity:
        equity = float(equity)
    else:
        equity = float(0)
    
    # Return equity
    return equity

# Get total equity of wallet
def get_equity(coin):
    
    # Debug
    debug = False

    # Initialize variables
    wallet        = {}
    equity_wallet = 0

    # Get wallet
    message = defs.announce("session: get_wallet_balance")
    try:
        wallet = session.get_wallet_balance(
            accountType = "UNIFIED",
            coin        = coin
        )
    except Exception as e:
        defs.log_error(e)
        
    # Check API rate limit and log data if possible
    if wallet:
        wallet = defs.rate_limit(wallet)
        defs.log_exchange(wallet, message)

    if debug:
        defs.announce("Wallet information:")
        pprint.pprint(wallet)

    # Get equity from wallet
    equity_wallet = equity_safe(wallet['result']['list'][0]['coin'][0]['equity'])

    # Return equity of wallet
    return equity_wallet

# Rebalances the database vs exchange by removing orders with the highest price
def rebalance(all_buys, info):

    # Debug
    debug = False

    # Initialize variables
    wallet         = ()
    equity_wallet  = 0
    equity_dbase   = 0
    equity_diff    = 0
    equity_remind  = 0
    equity_lost    = 0
    dbase_changed = False

    # Report to stdout
    if debug:
        defs.announce("Trying to rebalance buys database with exchange data")

    # Get equity from wallet
    equity_wallet = get_equity(info['baseCoin'])
  
    # Get equity from all buys
    equity_dbase  = float(sum(order['cumExecQty'] for order in all_buys))
    equity_remind = float(equity_dbase)
    equity_diff   = equity_wallet - equity_dbase

    # Report
    if debug:
        defs.announce(f"Before rebalance equity on exchange: {equity_wallet} {info['baseCoin']}")
        defs.announce(f"Before rebalance equity in database: {equity_dbase} {info['baseCoin']}")

    # Selling more than we have
    while equity_dbase > equity_wallet:
        
        # Database changed
        dbase_changed = True
        
        # Find the item with the highest avgPrice
        highest_avg_price_item = max(all_buys, key=lambda x: x['avgPrice'])

        # Remove this item from the list
        all_buys.remove(highest_avg_price_item)
        
        # Recalculate all buys
        equity_dbase = sum(order['cumExecQty'] for order in all_buys)    

    # Report
    if debug:
        defs.announce(f"After rebalance equity on exchange: {equity_wallet} {info['baseCoin']}")
        defs.announce(f"After rebalance equity in database: {equity_dbase} {info['baseCoin']}")

    # Save new database
    if dbase_changed:
        equity_lost = equity_remind - equity_dbase
        defs.announce(f"Rebalanced buys database with exchange data and lost {defs.round_number(equity_lost, info['basePrecision'])} {info['baseCoin']}")
        database.save(all_buys, info)
    
    # Report to stdout
    defs.announce(f"Difference between exchange and database is {defs.round_number(equity_diff, info['basePrecision'])} {info['baseCoin']}")

    # Return all buys
    return all_buys

# Report wallet info to stdout
def report_wallet(all_buys, info):

    # Initialize variables
    message    = ""
    wallet     = {}
    order_info = ()

    # Get order count and quantity
    order_info = database.order_count(all_buys, info)
    
    # Get wallet values
    message = defs.announce("session: get_wallet_balance")
    try:
        wallet = session.get_wallet_balance(
            accountType="UNIFIED",
            coin="USDC"
        )
    except Exception as e:
        defs.log_error(e)
        
    # Check API rate limit and log data if possible
    if wallet:
        wallet = defs.rate_limit(wallet)
        defs.log_exchange(wallet, message)

    # Get results
    total_equity = equity_safe(wallet['result']['list'][0]['totalEquity'])
    total_quote  = equity_safe(wallet['result']['list'][0]['coin'][0]['equity'])
    
    # Create messsage
    message = f"Wallet value {total_equity} {info['quoteCoin']}, "
    message = message + f"database has {order_info[0]} buy orders "
    message = message + f"worth {defs.format_number(order_info[1], info['basePrecision'])} {info['baseCoin']} and "
    message = message + f"{total_quote} {info['quoteCoin']} is free"
  
    # Return message
    return message
