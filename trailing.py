### Sunflow Cryptobot ###
#
# Traling buy and sell

# Load libraries
from loader import load_config
from pybit.unified_trading import HTTP
import database, defs, distance, orders

# Load config
config = load_config()

# Connect to exchange
session = HTTP(
    testnet                 = False,
    api_key                 = config.api_key,
    api_secret              = config.api_secret,
    return_response_headers = True
)

# Initialize variables
stuck          = {}
stuck['check']    = True
stuck['time']     = 0
stuck['interval'] = 10000
spike_counter  = 0
   
# Check if we can do trailing buy or sell
def check_order(symbol, spot, active_order, all_buys, all_sells, info):

    # Declare some variables global
    global stuck, spike_counter
    
    # Initialize variables
    result         = ()
    do_check_order = False

    # Has current price crossed trigger price
    if active_order['side'] == "Sell":
        if active_order['current'] <= active_order['trigger']:
            do_check_order = True
    else:
        if active_order['current'] >= active_order['trigger']:
            do_check_order = True

    # Check every interval, sometimes orders get stuck
    current_time = defs.now_utc()[4]
    if stuck['check']:
        stuck['check'] = False
        stuck['time']  = defs.now_utc()[4]
    if current_time - stuck['time'] > stuck['interval']:
        defs.announce("Doing an additional check on trailing order")
        stuck['check'] = True
        stuck['time']  = 0
        do_check_order = True

    # Current price crossed trigger price
    if do_check_order:

        # Output to stdout
        defs.announce("Get open order from exchange")

        # Has trailing endend, check if order does still exist
        order = {}
        message = defs.announce("session: get_open_orders")
        try:
            order = session.get_open_orders(
                category = "spot",
                symbol   = symbol,
                orderID  = str(active_order['orderid'])
            )
        except Exception as e:
            defs.log_error(e)

        # Check API rate limit and log data if possible
        if order:
            order = defs.rate_limit(order)
            defs.log_exchange(order, message)

        # Check if trailing order is filled, if so reset counters and close trailing process
        if order['result']['list'] == []:
            
            # Prepare message for stdout and Apprise
            defs.announce(f"Trailing {active_order['side'].lower()}: *** Order has been filled! ***")
            if active_order['side'] == "Buy":
                currency = info['quoteCoin']
            else:
                currency = info['baseCoin']
            message = f"{active_order['side']} order closed for {active_order['qty']} {currency} at trigger price {active_order['trigger']} {info['quoteCoin']}"
            
            # Reset counters
            stuck['check']= True
            stuck['time'] = 0
            spike_counter = 0
            
            # Close trailing process
            result       = close_trail(active_order, all_buys, all_sells, info)
            active_order = result[0]
            all_buys     = result[1]
            all_sells    = result[2]
            transaction  = result[3]
            profit       = result[4]
        
            # Fill in average price and report message
            if active_order['side'] == "Buy":
                message = message + f" and average fill price {defs.format_price(transaction['avgPrice'], info['tickSize'])} {info['quoteCoin']}"
            else:
                message = message + f", average fill price {defs.format_price(transaction['avgPrice'], info['tickSize'])} {info['quoteCoin']} and profit {profit} {info['quoteCoin']}"
            defs.announce(message, True, 1)
            
        # Check if symbol is spiking
        else:
            result       = check_spike(symbol, spot, active_order, order, all_buys, info)
            active_order = result[0]
            all_buys     = result[1]

    # Return modified data
    return active_order, all_buys

# Checks if the trailing error spiked
def check_spike(symbol, spot, active_order, order, all_buys, info):

    # Declare some variables global
    global spike_counter

    # Initialize variables
    error_code = 0

    # Check if the order spiked and is stuck
    transaction = orders.decode(order)
    if active_order['side'] == "Sell":

        # Did it spike and was forgotten when selling
        if transaction['triggerPrice'] > spot:
            spike_counter = spike_counter + 1
            # It spiked when selling
            if spike_counter > 3:
                defs.announce(f"*** {active_order['side']} order spiked, yakes! ***", True, 1)
                # Reset trailing sell
                active_order['active'] = False
                # Remove order from exchange
                orders.cancel(symbol, active_order['orderid'])
    else:

        # Did it spike and was forgotten when buying
        if transaction['triggerPrice'] < spot:
            spike_counter = spike_counter + 1
            # It spiked when buying
            if spike_counter > 3:
                defs.announce(f"*** {active_order['side']} order spiked, yakes! ***", True, 1)
                # Reset trailing buy
                active_order['active'] = False
                # Remove order from all buys
                all_buys = database.remove(active_order['orderid'], all_buys, info)
                # Remove order from exchange
                orders.cancel(symbol, active_order['orderid'])
    
    if error_code == 1:
        defs.announce(f"Although order {active_order['orderid']} spiked, this order was not found at the exchange", True, 1)
    
    # Return data
    return active_order, all_buys

# Calculate profit from sell
def calculate_profit(transaction, all_sells, info):
    
    # Debug
    debug = False
    
    # Initialize variables
    sells  = 0
    buys   = 0
    profit = 0
    fees          = {}
    fees['total'] = 0
    
    # Logic
    sells  = transaction['cumExecValue']
    buys   = sum(item['cumExecValue'] for item in all_sells)
    #fees['buy']   = sum(item['cumExecFee'] for item in all_sells)    # **** CHECK *** is trading fee in quote or base?
    #fees['sell']  = transaction['cumExecFee']
    #fees['total'] = fees['buy'] + fees['sell']
    profit = sells - buys - fees['total']
    profit = defs.precision(profit, info['quotePrecision'])
    
    # Output to stdout for debug
    if debug:
        defs.announce(f"Total sells were {sells} {info['quoteCoin']}, buys were {buys} {info['quoteCoin']} and fees were {fees['total']} {info['quoteCoin']}, giving a profit of {profit} {info['quoteCoin']}")
    
    # Return profit
    return profit
    
# Trailing order does not exist anymore, close it
def close_trail(active_order, all_buys, all_sells, info):

    # Debug
    debug = False
    
    # Initialize variables
    profit = 0
    
    # Make active_order inactive
    active_order['active'] = False
    
    # Close the transaction on either buy or sell trailing order
    transaction = orders.transaction_from_id(active_order['orderid'])
    transaction['status'] = "Closed"
          
    # Order was bought, create new all buys database
    if transaction['side'] == "Buy":
        all_buys = database.register_buy(transaction, all_buys, info)
    
    # Order was sold, create new all buys database, rebalance database and clear all sells
    if transaction['side'] == "Sell":

        # Output to stdout for debug
        if debug:
            print("All sell orders at close_trail")
            print(all_sells)
            print()

        # Calculate profit
        profit = calculate_profit(transaction, all_sells, info)
        
        # Create new all buys database
        all_buys = database.register_sell(all_buys, all_sells, info)
        
        # Rebalance new database
        all_buys = orders.rebalance(all_buys, info)
        
        # Clear all sells
        all_sells = []

    # Output to stdout
    defs.announce(f"Closed trailing {active_order['side'].lower()} order")
    
    return active_order, all_buys, all_sells, transaction, profit

# Trailing buy or sell
def trail(symbol, spot, active_order, info, all_buys, all_sells, prices):

    # Debug
    debug = False

    # Initialize variables
    result           = ()
    amend_code       = 0
    amend_error      = ""
    do_amend         = False

    # Output trailing to stdout
    if debug:
        defs.announce(f"Trailing {active_order['side']}: Checking if we can do trailing")

    # Check if the order still exists
    result       = check_order(symbol, spot, active_order, all_buys, all_sells, info)
    active_order = result[0]
    all_buys_new = result[1]

    # Order still exists, we can do trailing buy or sell
    if active_order['active']:
       
        # We have a new price
        active_order['previous'] = active_order['current']
                    
        # Determine distance of trigger price
        active_order = distance.calculate(active_order, prices)
                    
        # Calculate new trigger price
        if active_order['side'] == "Sell":
            active_order['trigger_new'] = defs.precision(active_order['current'] * (1 - (active_order['fluctuation'] / 100)), info['tickSize'])
        else:
            active_order['trigger_new'] = defs.precision(active_order['current'] * (1 + (active_order['fluctuation'] / 100)), info['tickSize'])

        # Check if we can amend trigger price
        if active_order['side'] == "Sell":
            if active_order['trigger_new'] > active_order['trigger']:
                do_amend = True
        else:
            if active_order['trigger_new'] < active_order['trigger']:
                do_amend = True

        # Amend trigger price
        if do_amend:
            result      = amend_trigger_price(symbol, active_order, info)
            amend_code  = result[0]
            amend_error = result[1]

            # Determine what to do based on error code of amend result
            if amend_code == 0:
                # Everything went fine, we can continue trailing
                message = f"Adjusted trigger price from {active_order['trigger']} to {active_order['trigger_new']} {info['quoteCoin']} in {active_order['side'].lower()} order"
                defs.announce(message, True, 0)
                active_order['trigger'] = active_order['trigger_new']
                all_buys                = all_buys_new

            if amend_code == 1:
                # Order slipped, close trailing process
                message = f"{active_order['side']} order slipped, we keep buys database as is and stop trailing"
                defs.announce(message, True, 1)
                database.remove(active_order['orderid'], all_buys, info)
                result       = close_trail(active_order, all_buys, all_sells, info)
                active_order = result[0]
                all_buys     = result[1]
                all_sells    = result[2]
                # Revert old situation
                all_buys_new = all_buys
                # Just for safety remove the order although it might not exist anymore *** CHECK *** Might not be correct this action, test!
                orders.cancel(symbol, active_order['orderid'])

            if amend_code == 100:
                # Critical error, let's log it and revert
                all_buys_new = all_buys
                defs.announce("Critical error while trailing", True, 1)
                defs.log_error(amend_error)

    # Reset all_buys and allow function to be run again
    all_buys = all_buys_new
        
    # Return modified data
    return active_order, all_buys
   
# Change the quantity of the current trailing sell
def amend_quantity_sell(symbol, active_order, info):

    # Initialize variables
    order      = {}
    error_code = 0
    exception  = ""

    # Output to stdout
    defs.announce(f"Trying to adjust quantity from {active_order['qty']} to {active_order['qty_new']} {info['baseCoin']}")

    # Ammend order
    order = {}
    message = defs.announce("session: amend_order")
    try:
        order = session.amend_order(
            category = "spot",
            symbol   = symbol,
            orderId  = str(active_order['orderid']),
            qty      = str(active_order['qty_new'])
        )
    except Exception as e:
        exception = str(e)
        if "(ErrCode: 170213)" in exception:
            # Order slipped
            error_code = 1
        elif "(ErrCode: 10001)" in exception:
            error_code = 2
        else:
            # Any other error
            error_code = 100

    # Check API rate limit and log data if possible
    if order:
        order = defs.rate_limit(order)
        defs.log_exchange(order, message)

    # Return error code 
    return error_code, exception

# Change the trigger price of the current trailing sell
def amend_trigger_price(symbol, active_order, info):

    # Initialize variables
    order      = {}
    error_code = 0
    exception  = ""
    
    # Output to stdout    
    defs.announce(f"Trying to adjusted trigger price from {active_order['trigger']} to {active_order['trigger_new']} {info['quoteCoin']}")
    
    # Amend order
    order = {}
    message = defs.announce("session: amend_order")
    try:
        order = session.amend_order(
            category     = "spot",
            symbol       = symbol,
            orderId      = str(active_order['orderid']),
            triggerPrice = str(active_order['trigger_new'])
        )
    except Exception as e:
        exception = str(e)
        if "(ErrCode: 170213)" in exception:
            # Order slipped
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
