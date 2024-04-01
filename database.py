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
def save(transactions):

    # Write the file
    with open(config.dbase_file, 'w') as json_file:
        json.dump(transactions, json_file)
    
    print("Database: save: Saved database to file")

# Load the database with buy transactions
def load(dbase_file):

    # Initialize variables
    transactions     = []

    # Load existing database file
    try:
        with open(dbase_file, 'r') as json_file:
            transactions = json.load(json_file)
    except FileNotFoundError:
        print(defs.now_utc()[1] + "Database: load: Database with buy transactions not found, exiting...")
        exit()
    except json.decoder.JSONDecodeError:
        print(defs.now_utc()[1] + "Database: load: Database with buy transactions not yet filled, may come soon!")

    # Return database
    return transactions

# Register all buy transactions in a database file
def register_buy(transaction, transactions):

    # Initialize variables
    transactions_new = []
    loop_transaction = False
    loop_appended    = False
    
    # If order already exists in buys dbase, change status
    for loop_transaction in transactions:
        if loop_transaction['orderId'] == transaction['orderId']:
            loop_appended = True
            loop_transaction = transaction
        transactions_new.append(loop_transaction)
    
    # If not changed existing transaction, then add as new transaction
    if not loop_appended:
        transactions_new.append(transaction)
    
    if debug:
        print(defs.now_utc()[1] + "\nDatabase: register_buy: New Transactions")
        print(transactions_new)
        print()

    # Save to database
    save(transactions_new)    
    
    # Return new buy database
    return transactions_new

# Remove all sold buy transaction from the database file
def register_sell(all_buys, all_sells):
    
    # Get a set of all sell order IDs for efficient lookup
    sell_order_ids = {sell['orderId'] for sell in all_sells}

    # Filter out all_buys entries that have their orderId in sell_order_ids
    filtered_buys = [buy for buy in all_buys if buy['orderId'] not in sell_order_ids]

    # Count unique order ids
    unique_ids = len(sell_order_ids)
    
    # Save to database
    save(filtered_buys)
    
    # Output to stdout
    print("Database: register_sell: There were " + str(unique_ids) + " orders in trailing sell")
    
    # Return the cleaned buys
    return filtered_buys
