### Sunflow Cryptobot ###
#
# Do database stuff

# Load external libraries
from pathlib import Path
import importlib, json, sys

# Load internal libraries
import argparse, defs

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

# Initialize variables
debug = False

# Create a new all buy database file
def save(all_buys):

    # Write the file
    with open(config.dbase_file, 'w', encoding='utf-8') as json_file:
        json.dump(all_buys, json_file)

    # Get number of orders 
    order_count = len(all_buys)
    total_qty   = sum(item['cumExecQty'] for item in all_buys)
    total_qty   = defs.smart_round(total_qty)
    
    # Output to stdout
    print(defs.now_utc()[1] + "Database: save: Saved database with " + str(order_count) + " buy orders and " + str(total_qty) + " executed in base currency to file\n")

# Load the database with all buys
def load(dbase_file):

    # Initialize variables
    all_buys = []

    # Load existing database file
    try:
        with open(dbase_file, 'r', encoding='utf-8') as json_file:
            all_buys = json.load(json_file)
    except FileNotFoundError:
        print(defs.now_utc()[1] + "Database: load: Database with all buys not found, exiting...\n")
        exit()
    except json.decoder.JSONDecodeError:
        print(defs.now_utc()[1] + "Database: load: Database with all buys not yet filled, may come soon!\n")

    # Return database
    return all_buys

# Remove an order from the all buys database file
def remove(orderid, all_buys):
      
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
        message = "Database: remove: The order with ID " + str(orderid) + " which we were about to remove was not found!"
        print(defs.now_utc()[1] + message + "\n")
    else:
        print(defs.now_utc()[1] + "Database: remove: Order with ID " + str(orderid) + " removed from all buys database!\n")
    
    # Save to database
    save(all_buys_new)   
    
    # Retrun database
    return all_buys_new

# Register all buys in a database file
def register_buy(buy_order, all_buys):

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
        print(defs.now_utc()[1] + "Database: register_buy: New database with " + str(counter) + " buy orders")
        print(all_buys_new)
        print()

    # Save to database
    save(all_buys_new)    
    
    # Return new buy database
    return all_buys_new

# Remove all sold buy transaction from the database file
def register_sell(all_buys, all_sells):
    
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
        
    if unique_ids == 0:
        print(defs.now_utc()[1] + "Database: register_sell: No orders in trailing sell when trying to register\n")
    
    # Save to database
    save(filtered_buys)
    
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
    print(defs.now_utc()[1] + "Database: register_sell: Sold " + str(unique_ids) + " orders via trailing sell\n")
    
    # Return the cleaned buys
    return filtered_buys
