### Sunflow Cryptobot ###
#
# Do database stuff

# Load external libraries
import json

# Load internal libraries
import config, defs

# Initialize variables
debug = False

# Create a new all buy database file
def save(all_buys):

    # Write the file
    with open(config.dbase_file, 'w', encoding='utf-8') as json_file:
        json.dump(all_buys, json_file)
    
    print(defs.now_utc()[1] + "Database: save: Saved database with all buys to file\n")

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
        print(defs.now_utc()[1] + "Database: register_buy: New database with " + str(counter) + " buys")
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
        defs.log_error("\n0 orders in trailing sell when trying to register\n")
    
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
