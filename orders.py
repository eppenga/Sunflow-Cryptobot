### Sunflow Cryptobot ###
#
# Order functions

# Load external libraries
from pybit.unified_trading import HTTP

# Load internal libraries
import config, database, defs, orders

# Initialize variables
debug  = False

# Connect to exchange
session = HTTP(
    testnet    = False,
    api_key    = config.api_key,
    api_secret = config.api_secret,
)

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

    # Log data if possible
    if order:      
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

        # Log data if possible
        if order:
            defs.log_exchange(order, message)

    # If realtime and history fails, throw an error
    if order['result']['list'] == []:
        message = defs.now()[1] + "Orders: history: Trying to load non-existing error, something is corrupt!"
        defs.log_error()

    if debug:
        print(defs.now_utc()[1] + "Orders: OrderId: Order history")
        print(order)

    return order

# Decode order from exchange to proper dictionary
# createdTime, updatedTime, orderId, orderLinkId, symbol, side, orderType, orderStatus, price, avgPrice, qty, cumExecQty, cumExecValue, cumExecFee, status
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

    # Return order
    return transaction

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
        
# New buy order
def buy(symbol, spot, active_order, all_buys, info):

    # Initialize variables
    active_order['side']     = "Buy"
    active_order['active']   = True
    active_order['start']    = spot
    active_order['previous'] = spot
    active_order['current']  = spot
    active_order['qty']      = info['minBuyQuote']
    active_order['trigger']  = defs.precision(spot * (1 + (active_order['distance'] / 100)), info['tickSize'])

    # Output to stdout
    print(defs.now_utc()[1] + "Orders: buy: *** BUY BUY BUY! ***\n")

    # Place Buy order
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
        
    # Log data if possible
    if order:      
        defs.log_exchange(order, message)
        
    # Get order info
    active_order['orderid'] = int(order['result']['orderId'])

    # Get the transaction
    transaction = orders.transaction_from_order(order)
    
    # Set the status
    transaction['status'] = "Open"
    print(defs.now_utc()[1] + "Orders: buy: Initial buy order placed for " + str(active_order['qty']) + " " + info['quoteCoin'] + " with trigger price " + str(active_order['trigger']) + " " + info['quoteCoin'] + "\n")
    
    # Store the transaction in the database buys file
    all_buys = database.register_buy(transaction, all_buys)
    print(defs.now_utc()[1] + "Orders: buy: Registered buy order in database " + config.dbase_file + "\n")

    # Output to stdout
    print(defs.now_utc()[1] + "Orders: buy: Starting trailing buy\n")
    
    # Return trailing order and new buy order database
    return active_order, all_buys
    
# What orders and how much can we sell with profit
def check_sell(spot, profit, active_order, all_buys, info):

    # Initialize variables
    qty               = 0
    distance          = active_order['distance']
    counter           = 0
    can_sell          = False
    all_sells         = []
       
    # Walk through buy database and find profitable buys
    for transaction in all_buys:

        # Only walk through closed buy orders
        if transaction['status'] == 'Closed':
                       
            # Check if a transaction is profitable
            profitable_price = transaction['avgPrice'] * (1 + ((profit + distance) / 100))        
            if  spot >= profitable_price:
                qty = qty + transaction['cumExecQty']
                all_sells.append(transaction)
                counter = counter + 1
    
    # Adjust quantity to exchange regulations
    qty = defs.precision(qty, info['basePrecision'])
    
    if all_sells:
        can_sell = True
        print(defs.now_utc()[1] + "Orders: check_sell: Selling " + str(counter) + " orders for a total of " + str(qty) + " " + info['baseCoin'] + "\n")
    
    # Return data
    return all_sells, qty, can_sell

# New sell order
def sell(symbol, spot, active_order, info):
    
    # Initialize variables
    active_order['side']     = "Sell"
    active_order['active']   = True
    active_order['start']    = spot
    active_order['previous'] = spot
    active_order['current']  = spot
    active_order['trigger']  = defs.precision(spot * (1 - (active_order['distance'] / 100)), info['tickSize'])

    # Output to stdout
    print(defs.now_utc()[1] + "Orders: sell: *** SELL SELL SELL! ***\n")

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
        
    # Log data if possible
    if order:      
        defs.log_exchange(order, message)
    
    # Get order info
    active_order['orderid'] = int(order['result']['orderId'])
    
    # Output to stdout
    print(defs.now_utc()[1] + "Orders: sell: Initial sell order placed for " + str(active_order['qty']) + " " + info['baseCoin'] + " with trigger price " + str(active_order['trigger']) + " " + info['quoteCoin'] + "\n")
    
    # Return data
    return active_order

