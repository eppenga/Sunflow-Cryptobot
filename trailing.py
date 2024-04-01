### Sunflow Cryptobot ###
#
# Traling buy and sell

# Load external libraries
import math
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
debug = False
check_counter = 0
   
# Check if we can do trailing buy or sell
def check_order(symbol, active_order, all_buys, all_sells):

    # Declare some variables global
    global check_counter
    
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
    check_counter = check_counter + 1
    if check_counter == 10:
        print(defs.now_utc()[1] + "Trailing: check_orders: Doing an additional check on trailing order\n")
        check_counter  = 0
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

        # Trailing has ended, the order doesn't exist anymore, make active_order inactive
        if order['result']['list'] == []:
            active_order['active'] = False
            print(defs.now_utc()[1] + "Trailing: check_order: Trailing " + active_order['side'] + ": *** Order has been filled! ***\n")

            # Close the transaction
            transaction = orders.transaction_from_id(active_order['orderid'])
            transaction['status'] = "Closed"
            
            # Order was bought, create new all buys database
            if transaction['side'] == "Buy":
                all_buys = database.register_buy(transaction, all_buys)
            
            # Order was sold, create new all buys database and reset all sells
            if transaction['side'] == "Sell":
                all_buys = database.register_sell(all_buys, all_sells)
                all_sells = []

    # Return modified data
    return active_order, all_buys

# Trailing buy or sell
def trail(symbol, active_order, info, all_buys, all_sells):

    # Initialize variables
    add_up      = 0
    do_amend    = False
    do_trailing = False

    # Mention trailing
    if debug:
        print(defs.now_utc()[1] + "Trailing: trail: Trailing " + active_order['side'] + ": Checking")

    # Check if the order still exists
    check_order_results = check_order(symbol, active_order, all_buys, all_sells)
    active_order = check_order_results[0]
    all_buys     = check_order_results[1]

    # Order still exists, we can do trailing buy or sell
    if active_order['active']:
                     
        # Check if price has moved
        if active_order['side'] == "Sell":
            if active_order['current'] > active_order['previous']:
                do_trailing = True
        else:
            if active_order['current'] < active_order['previous']:
                do_trailing = True
        
        # Price has moved, we can do trailing buy or sell
        if do_trailing:

            # Reset trigger price and default distance
            active_order['previous']      = active_order['current']
            active_order['calc_distance'] = active_order['distance']    
                       
            # Determine distance of trigger price, dynamic or static
            if active_order['wiggle']:
                
                # Calculate price difference
                if active_order['side'] == "Sell":
                    price_difference = active_order['current'] - active_order['start']
                else:
                    price_difference = active_order['start'] - active_order['current']

                # Calculate trigger price distance percentage
                if price_difference > 0:
                    active_order['calc_distance'] = 0.3 * math.sqrt(price_difference) + active_order['distance'] + add_up
                    print(defs.now_utc()[1] + "Trailing: trail: Dynamical trigger distance changed to " + str(round(active_order['calc_distance'], 4)) + "%\n")
                       
            # Choose trailing buy or sell
            if active_order['side'] == "Sell":
                active_order['trigger_new'] = defs.precision(active_order['current'] * (1 - (active_order['calc_distance'] / 100)), info['tickSize'])
            else:
                active_order['trigger_new'] = defs.precision(active_order['current'] * (1 + (active_order['calc_distance'] / 100)), info['tickSize'])

            # Check if we can amend order
            if active_order['side'] == "Sell":    
                if active_order['trigger_new'] > active_order['trigger']:
                    do_amend = True
            else:
                if active_order['trigger_new'] < active_order['trigger']:
                    do_amend = True

            # Amend order                
            if do_amend:
                active_order['trigger'] = active_order['trigger_new']
                message = defs.now_utc()[1] + "Trailing: trail: session: amend_order\n"
                print(message)
                order = {}
                try:
                    order = session.amend_order(
                        category     = "spot",
                        symbol       = symbol,
                        orderId      = str(active_order['orderid']),
                        triggerPrice = str(active_order['trigger'])
                    )
                except Exception as e:
                    defs.log_error(e)
                    
                # Log data if possible
                if order:
                    defs.log_exchange(order, message)
                
                # Output to stdout
                print(defs.now_utc()[1] + "Trailing: trail: Trailing " + active_order['side'] + ": lastPrice changed, adjusted trigger price to " + str(active_order['trigger']) + " " + info['quoteCoin'] + "\n")
            else:
                print(defs.now_utc()[1] + "Trailing: trail: Trailing " + active_order['side'] + ": lastPrice changed, trigger price not adjusted because lastPrice change was not relevant\n")

    # Output to stdout
    if debug:
        print(defs.now_utc()[0])
        print(str(active_order) + "\n")
    
    # Return modified data
    return active_order, all_buys

# Change the quantity of the current trailing sell
def amend_sell(symbol, orderid, qty, info):

    # Adjust quantity to precision
    qty = defs.precision(qty, info['basePrecision'])

    # Output to stdout
    print(defs.now_utc()[1] + "Trailing: amend_sell: Quantity of trailing sell order adjusted to " + str(qty) + " " + info['baseCoin'] + "\n")

    # Ammend order
    message = defs.now_utc()[1] + "Trailing: amend_sell: session: amend_order\n"
    print(message)
    order = {}
    try:
        order = session.amend_order(
            category = "spot",
            symbol   = symbol,
            orderId  = str(orderid),
            qty      = str(qty)
        )
    except Exception as e:
        defs.log_error(e)
    
    # Log data if possible
    if order:
        defs.log_exchange(order, message)
