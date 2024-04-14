### Sunflow Cryptobot ###
#
# Traling buy and sell

# Load external libraries
from pybit.unified_trading import HTTP

# Load internal libraries
import config, database, defs, orders

# Connect to exchange
session = HTTP(
    testnet    = False,
    api_key    = config.api_key,
    api_secret = config.api_secret
)

# Initialize variables
debug          = False
stuck_counter  = 0
spiker_counter = 0
   
# Check if we can do trailing buy or sell
def check_order(symbol, active_order, all_buys, all_sells):

    # Declare some variables global
    global stuck_counter, spiker_counter
    
    # Initialize variables
    do_check_order = False

    # Has current price crossed trigger price
    if active_order['side'] == "Sell":
        if active_order['current'] <= active_order['trigger']:
            do_check_order = True
    else:
        if active_order['current'] >= active_order['trigger']:
            do_check_order = True

    # Check any 10th check_order anyway, sometimes orders get stuck *** CHECK *** MAYBE CHECK EVERY MINUTE
    stuck_counter = stuck_counter + 1
    if stuck_counter == 10:
        print(defs.now_utc()[1] + "Trailing: check_orders: Doing an additional check on trailing order\n")
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

        # Log data if possible
        if order:
            defs.log_exchange(order, message)

        # Check if trailing order if filled, and if so close trailing process
        if order['result']['list'] == []:
            print(defs.now_utc()[1] + "Trailing: check_order: Trailing " + active_order['side'] + ": *** Order has been filled! ***\n")
            spiker_counter = 0
            close_trail_results = close_trail(active_order, all_buys, all_sells)
            active_order = close_trail_results[0]
            all_buys     = close_trail_results[1]
            all_sells    = close_trail_results[2]
        else:
            check_spiker_result = check_spiker(active_order, order, all_buys)
            active_order = check_spiker_result[0]
            all_buys     = check_spiker_result[1]

    # Return modified data
    return active_order, all_buys

# Checks if the trailing error spiked
def check_spiker(active_order, order, all_buys):

    # Declare some variables global
    global spiker_counter

    # Check if the order spiked and is stuck
    transaction = orders.decode(order)
    if active_order['side'] == "Sell":
        # Did it spike and was forgotten when selling
        if transaction['triggerPrice'] > active_order['current']:
            spiker_counter = spiker_counter + 1
            # It spiked when selling
            if check_spiker == 3:
                print(defs.now_utc()[1] + "Trailing: check_order: " + active_order['side'] + ": *** It spiked, yakes! ***\n")
                # Reset trailing sell
                active_order['active'] = False
                # Remove order from exchange
                orders.cancel(active_order['orderid'])
    else:
        # Did it spike and was forgotten when buying
        if transaction['triggerPrice'] < active_order['current']:
            spiker_counter = spiker_counter + 1
            # It spiked when buying
            if check_spiker == 3:
                print(defs.now_utc()[1] + "Trailing: check_order: " + active_order['side'] + ": *** It spiked, yakes! ***\n")
                # Reset trailing buy
                active_order['active'] = False
                # Remove order from all buys
                database.remove(active_order['orderid'])                        
                # Remove order from exchange
                all_buys = orders.cancel(active_order['orderid'], all_buys)                                
        
    # Return data
    return active_order, all_buys

# Trailing order does not exist anymore, close it
def close_trail(active_order, all_buys, all_sells):

    # Debug
    debug = False
    
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
    
    # Order was sold, create new all buys database and clear all sells
    if transaction['side'] == "Sell":

        if debug:
            print("All sell orders at close_trail")
            print(all_sells)
            print()
        
        all_buys = database.register_sell(all_buys, all_sells)
        all_sells = []
    
    return active_order, all_buys, all_sells

# Trailing buy or sell
def trail(symbol, active_order, info, all_buys, all_sells, prices):

    # Initialize variables
    do_amend    = False     # We can amend a trailing order
    do_trailing = False     # We can do trailing buy or sell

    # Mention trailing
    if debug:
        print(defs.now_utc()[1] + "Trailing: trail: Trailing " + active_order['side'] + ": Checking if we can do trailing")

    # Check if the order still exists
    check_order_results = check_order(symbol, active_order, all_buys, all_sells)
    active_order = check_order_results[0]
    all_buys_new = check_order_results[1]

    # Order still exists, we can do trailing buy or sell
    if active_order['active']:
                     
        # If price moved in the correct direction, we can do trailing
        if active_order['side'] == "Sell":
            if active_order['current'] > active_order['previous']:
                do_trailing = True
        else:
            if active_order['current'] < active_order['previous']:
                do_trailing = True
        
        # Price has moved, adjusting trigger price when possible
        if do_trailing:

            # We have a new price
            active_order['previous'] = active_order['current']
            
            # Set calculated distance by default to distance
            active_order['fluctuation'] = active_order['distance']
            
            # Determine distance of trigger price
            if active_order['wiggle']:
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
                amend_result = amend_trigger_price(symbol, active_order, info)
                amend_code   = amend_result[0]
                amend_error  = amend_result[1]

                # Determine what to do based on error code of amend result
                if amend_code == 0:
                    # Everything went fine, we can continue trailing
                    print(defs.now_utc()[1] + "Trailing: trail: Trailing " + active_order['side'] + ": Trigger price adjusted from " + str(active_order['trigger']) + " " + info['quoteCoin'], end=" ")
                    print("to " + str(active_order['trigger_new']) + " " + info['quoteCoin'] + "\n")
                    active_order['trigger'] = active_order['trigger_new']
                    all_buys                = all_buys_new
                if amend_code == 1:
                    # Order slipped, close trailing process
                    print(defs.now_utc()[1] + "Trailing: trail: Order slipped, we keep buys database as is and stop trailing\n")
                    close_trail_results = close_trail(active_order, all_buys, all_sells)
                    active_order = close_trail_results[0]
                    all_buys     = close_trail_results[1]
                    all_sells    = close_trail_results[2]
                    # Revert old situation
                    all_buys_new = all_buys
                if amend_code == 100:
                    # Critical error, let's log it and revert
                    all_buys_new = all_buys
                    print(defs.now_utc()[1] + "Trailing: trail: Critical error, logging to file\n")
                    defs.log_error(amend_error)

    # Reset all_buys
    all_buys = all_buys_new

    # Debug output active_order and error
    if debug:
        print(defs.now_utc()[1] + "Trailing: trail: Debug output of active_order:")
        print(str(active_order) + "\n")
        print(defs.now_utc()[1] + "Trailing: trail: Debug output of error code: " + str(amend_result) + "\n")
        
    # Return modified data
    return active_order, all_buys
   
# Change the quantity of the current trailing sell
def amend_quantity_sell(symbol, active_order, info):

    # Initialize variables
    order      = {}
    error_code = 0
    exception  = ""

    # Output to stdout
    print(defs.now_utc()[1] + "Trailing: amend_quantity_sell: Trying to adjust quantity from " + str(active_order['qty']) + " " + info['baseCoin'] + " to " +  str(active_order['qty_new']) + " " + info['baseCoin'] + "\n")

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
        else:
            # Any other error
            error_code = 100

    # Log data if possible
    if order:
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
    print(defs.now_utc()[1] + "Trailing: amend_trigger_price: Trying to adjusted trigger price from " + str(active_order['trigger']) + " " + info['quoteCoin'] + " to " +  str(active_order['trigger_new']) + " " + info['quoteCoin'] + "\n")
    
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

    # Log data if possible
    if order:
        defs.log_exchange(order, message)

    # Return error code 
    return error_code, exception
