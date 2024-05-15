### Sunflow Cryptobot ###
#
# Traling buy and sell

# Load external libraries
from pathlib import Path
from pybit.unified_trading import HTTP
import importlib, sys

# Load internal libraries
import argparse, database, defs, orders

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

# Initialize variables
stuck_fresh      = True
stuck_counter    = 0
spiker_counter   = 0
def_trail_active = False
   
# Check if we can do trailing buy or sell
def check_order(symbol, active_order, all_buys, all_sells, use_delay, info):

    # Declare some variables global
    global stuck_fresh, stuck_counter, spiker_counter
    
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

    # Check every minute, sometimes orders get stuck
    if stuck_fresh:
        stuck_fresh = False
        stuck_counter = defs.now_utc()[4]
    current_time = defs.now_utc()[4]
    if current_time - stuck_counter > 10000:
        print(defs.now_utc()[1] + "Trailing: check_orders: Doing an additional check on trailing order\n")
        stuck_fresh    = True
        stuck_counter  = 0
        do_check_order = True

    # Current price crossed trigger price
    if do_check_order:

        # Output to stdout
        print(defs.now_utc()[1] + "Trailing: check_orders: Get open order from exchange\n")

        # Has trailing endend, check if order does still exist
        message = defs.now_utc()[1] + "Trailing: check_orders: session: get_open_orders\n"
        print(message)
        order = {}
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
            print(defs.now_utc()[1] + "Trailing: check_order: Trailing " + active_order['side'].lower() + ": *** Order has been filled! ***\n")
            if active_order['side'] == "Buy":
                currency = info['quoteCoin']
            else:
                currency = info['baseCoin']
            message = f"{active_order['side']} order closed for {active_order['qty']} {currency} with trigger price {active_order['trigger']} {info['quoteCoin']}"
            
            # Reset counters
            stuck_fresh    = True
            stuck_counter  = 0
            spiker_counter = 0
            
            # Close trailing process
            result       = close_trail(active_order, all_buys, all_sells, info)
            active_order = result[0]
            all_buys     = result[1]
            all_sells    = result[2]
            transaction  = result[3]
            profit       = result[4]
        
            # Fill in average price and report message
            if active_order['side'] == "Buy":
                message = message + f" and average fill price {transaction['avgPrice']} {info['quoteCoin']} for {symbol}"
            else:
                message = message + f", average fill price {transaction['avgPrice']} {info['quoteCoin']} and profit {profit} {info['quoteCoin']} for {symbol}"
            defs.notify(message, 1)
            
            # Handle buy delay
            if active_order['side'] == "Sell":
                if use_delay['enabled']:
                    use_delay['start'] = defs.now_utc()[4]
                    use_delay['end']   = use_delay['start'] + use_delay['timeframe']

        # Check if symbol is spiking
        else:
            result       = check_spiker(symbol, active_order, order, all_buys)
            active_order = result[0]
            all_buys     = result[1]

    # Return modified data
    return active_order, all_buys, use_delay

# Checks if the trailing error spiked
def check_spiker(symbol, active_order, order, all_buys):

    # Declare some variables global
    global spiker_counter

    # Check if the order spiked and is stuck
    transaction = orders.decode(order)
    if active_order['side'] == "Sell":
        # Did it spike and was forgotten when selling
        if transaction['triggerPrice'] > active_order['current']:
            spiker_counter = spiker_counter + 1
            # It spiked when selling
            if spiker_counter == 3:
                print(defs.now_utc()[1] + "Trailing: check_order: " + active_order['side'] + ": *** It spiked, yakes! ***\n")
                # Reset trailing sell
                active_order['active'] = False
                # Remove order from exchange
                orders.cancel(symbol, active_order['orderid'])
    else:
        # Did it spike and was forgotten when buying
        if transaction['triggerPrice'] < active_order['current']:
            spiker_counter = spiker_counter + 1
            # It spiked when buying
            if spiker_counter == 3:
                print(defs.now_utc()[1] + "Trailing: check_order: " + active_order['side'] + ": *** It spiked, yakes! ***\n")
                # Reset trailing buy
                active_order['active'] = False
                # Remove order from all buys
                all_buys = database.remove(active_order['orderid'], all_buys)
                # Remove order from exchange
                orders.cancel(symbol, active_order['orderid'])
        
    # Return data
    return active_order, all_buys

# Calculate profit from sell
def calculate_profit(transaction, all_sells, info):
    
    # Debug
    debug = True
    
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
        print(defs.now_utc()[1] + f"Total sells were {sells} {info['quoteCoin']}, buys were {buys} {info['quoteCoin']} and fees were {fees['total']} {info['quoteCoin']}, giving a profit of {profit} {info['quoteCoin']}\n")
    
    # Return profit
    return profit
    
# Trailing order does not exist anymore, close it
def close_trail(active_order, all_buys, all_sells, info):

    # Debug
    debug = False
    
    # Initialize variables
    profit = 0
    
    # Output to stdout
    print(defs.now_utc()[1] + "Trailing: close_trail: Trying to close trailing process\n")
    
    # Make active_order inactive
    active_order['active'] = False
    
    # Close the transaction on either buy or sell trailing order
    transaction = orders.transaction_from_id(active_order['orderid'])
    transaction['status'] = "Closed"
          
    # Order was bought, create new all buys database
    if transaction['side'] == "Buy":
        all_buys = database.register_buy(transaction, all_buys)
    
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
        all_buys = database.register_sell(all_buys, all_sells)
        
        # Rebalance new database
        all_buys = orders.rebalance(all_buys, info)
        
        # Clear all sells
        all_sells = []
    
    return active_order, all_buys, all_sells, transaction, profit

# Trailing buy or sell
def trail(symbol, active_order, info, all_buys, all_sells, prices, use_delay):

    # Debug
    debug = False

    # Define global variables
    global def_trail_active

    # Check if trailing is not already executed and if so wait for next tick
    if def_trail_active:
        print(defs.now_utc()[1] + "Trailing: trail: function is busy, no further action required\n")
        return active_order, all_buys, use_delay
    else:
        if debug:
            print(defs.now_utc()[1] + "Trailing: trail: function started\n")

    # Initialize variables
    result           = ()
    amend_code       = 0
    amend_error      = ""
    do_amend         = False
    def_trail_active = True

    # Output trailing to stdout
    if debug:
        print(defs.now_utc()[1] + "Trailing: trail: Trailing " + active_order['side'] + ": Checking if we can do trailing\n")

    # Check if the order still exists
    result       = check_order(symbol, active_order, all_buys, all_sells, use_delay, info)
    active_order = result[0]
    all_buys_new = result[1]
    use_delay    = result[2]

    # Order still exists, we can do trailing buy or sell
    if active_order['active']:
       
        # We have a new price
        active_order['previous'] = active_order['current']
                    
        # Determine distance of trigger price
        active_order = orders.distance(active_order, prices)
                    
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
                print(defs.now_utc()[1] + "Trailing: trail: Trailing " + active_order['side'] + ": " + message + "\n")
                defs.notify(message + f" for {symbol}", 0)
                active_order['trigger'] = active_order['trigger_new']
                all_buys                = all_buys_new

            if amend_code == 1:
                # Order slipped, close trailing process
                print(defs.now_utc()[1] + f"Trailing: trail: {active_order['side']} order slipped, we keep buys database as is and stop trailing\n")
                defs.notify(f"{active_order['side']} order slipped, we keep buys database as is and stop trailing for {symbol}", 1)
                result       = close_trail(active_order, all_buys, all_sells, info)
                active_order = result[0]
                all_buys     = result[1]
                all_sells    = result[2]
                # Revert old situation
                all_buys_new = all_buys

            if amend_code == 100:
                # Critical error, let's log it and revert
                all_buys_new = all_buys
                print(defs.now_utc()[1] + "Trailing: trail: Critical error, logging to file\n")
                defs.notify(f"While trailing a critical error occurred for {symbol}", 1)
                defs.log_error(amend_error)

    # Reset all_buys and allow function to be run again
    all_buys         = all_buys_new
    def_trail_active = False
    if debug:
        print(defs.now_utc()[1] + "Trailing: trail: function ended\n")

    # Debug output active_order and error
    if debug:
        print(defs.now_utc()[1] + "Trailing: trail: Debug output of active_order:\n" + str(active_order) + "\n")
        if amend_error:
            print(defs.now_utc()[1] + "Trailing: trail: Debug output of error code:\n" + amend_error + "\n")
        
    # Return modified data
    return active_order, all_buys, use_delay
   
# Change the quantity of the current trailing sell
def amend_quantity_sell(symbol, active_order, info):

    # Initialize variables
    order      = {}
    error_code = 0
    exception  = ""

    # Output to stdout
    print(defs.now_utc()[1] + "Trailing: amend_quantity_sell: Trying to adjust quantity from " + str(active_order['qty']) + " to " +  str(active_order['qty_new']) + " " + info['baseCoin'] + "\n")

    # Ammend order
    message = defs.now_utc()[1] + "Trailing: amend_sell: session: amend_order\n"
    print(message)
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
    print(defs.now_utc()[1] + "Trailing: amend_trigger_price: Trying to adjusted trigger price from " + str(active_order['trigger']) + " to " +  str(active_order['trigger_new']) + " " + info['quoteCoin'] + "\n")
    
    # Amend order
    message = defs.now_utc()[1] + "Trailing: amend_trigger_price: session: amend_order\n"
    print(message)
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
