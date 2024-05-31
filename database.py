### Sunflow Cryptobot ###
#
# Do database stuff

# Load libraries
from loader import load_config
import defs
import json

# Load config
config = load_config()

# Create a new all buy database file
def save(all_buys, info):

    # Write the file
    with open(config.dbase_file, 'w', encoding='utf-8') as json_file:
        json.dump(all_buys, json_file)

    # Get statistics and output to stdout
    result = order_count(all_buys, info)
    defs.announce(f"Database contains {result[0]} buy transactions and {defs.format_price(result[1], info['basePrecision'])} {info['baseCoin']} was bought")
    
# Load the database with all buys
def load(dbase_file, info):

    # Initialize variables
    all_buys = []

    # Load existing database file
    try:
        with open(dbase_file, 'r', encoding='utf-8') as json_file:
            all_buys = json.load(json_file)
    except FileNotFoundError:
        defs.announce("Database with all buys not found, exiting...")
        defs.halt_sunflow = True
        exit()
    except json.decoder.JSONDecodeError:
        defs.announce("Database with all buys not yet filled, may come soon!")

    # Get statistics and output to stdout
    result = order_count(all_buys, info)
    defs.announce(f"Database contains {result[0]} buy transactions and {defs.format_price(result[1], info['basePrecision'])} {info['baseCoin']} was bought")

    # Return database
    return all_buys

# Remove an order from the all buys database file
def remove(orderid, all_buys, info):
      
    # Initialize variables
    all_buys_new = []
    found_order   = False
    
    # Remove the order
    for loop_buy in all_buys:
        if loop_buy['orderId'] != orderid:
            found_order = True
            all_buys_new.append(loop_buy)

    # Output to stdout
    if not found_order:
        defs.announce(f"The order with ID {orderid} which we were about to remove was not found!")
    else:
        defs.announce(f"Database: remove: Order with ID {orderid} removed from all buys database!")
    
    # Save to database
    save(all_buys_new, info)
    
    # Retrun database
    return all_buys_new

# Register all buys in a database file
def register_buy(buy_order, all_buys, info):

    # Debug
    debug = False

    # Initialize variables
    counter       = 0
    all_buys_new  = []
    loop_buy      = False
    loop_appended = False
    
    # If order already exists in buys dbase, change status
    for loop_buy in all_buys:
        if loop_buy['orderId'] == buy_order['orderId']:
            counter = counter + 1
            loop_appended = True
            loop_buy = buy_order
        all_buys_new.append(loop_buy)
    
    # If not found in buy orders, then add new buy order
    if not loop_appended:
        all_buys_new.append(buy_order)
        counter = counter + 1
      
    if debug:
        defs.announce(f"Database: register_buy: New database with {counter} buy orders")
        print(all_buys_new)
        print()

    # Save to database
    save(all_buys_new, info)    
    
    # Return new buy database
    return all_buys_new

# Remove all sold buy transaction from the database file
def register_sell(all_buys, all_sells, info):
    
    # Debug
    debug = False
    
    # Initialize variables
    unique_ids = 0
    
    # Get a set of all sell order IDs for efficient lookup
    sell_order_ids = {sell['orderId'] for sell in all_sells}

    # Filter out all_buys entries that have their orderId in sell_order_ids
    filtered_buys = [buy for buy in all_buys if buy['orderId'] not in sell_order_ids]

    # Count unique order ids
    unique_ids = len(sell_order_ids)
    
    # Save to database
    save(filtered_buys, info)
    
    if debug:
        print("All sell orders")
        print(all_sells)
        
        print("\nRemoved these unique ids")
        print(sell_order_ids)
        print()   
        
        print("New all buys database")
        print(filtered_buys)
        print()
    
    # Output to stdout
    defs.announce(f"Sold {unique_ids} orders via trailing sell")
    
    # Return the cleaned buys
    return filtered_buys

# Determine number of orders and qty
def order_count(all_buys, info):
    
    # Get number of transactions
    order_count = len(all_buys)
    total_qty   = sum(item['cumExecQty'] for item in all_buys)
    total_qty   = defs.precision(total_qty, info['basePrecision'])
    
    # Return data
    return order_count, total_qty