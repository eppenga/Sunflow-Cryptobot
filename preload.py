### Sunflow Cryptobot ###
#
# Preload ticker, klines, instrument info and other data

# Load external libraries
from loader import load_config
from pybit.unified_trading import HTTP
import database, defs, orders, os, pprint

# Load config
config = load_config()

# Connect to exchange
session = HTTP(
    testnet = False,
    return_response_headers = True
)

# Preload ticker
def get_ticker(symbol):

    # Debug
    debug = False

    # Initialize variables
    data   = {}
    ticker = {'time': 0, 'symbol': symbol, 'lastPrice': 0}
   
    # Load ticker via normal session
    message = defs.announce("session: get_tickers")
    try:
        data = session.get_tickers(
            category = "spot",
            symbol   = symbol,
        )
    except Exception as e:
        defs.log_error(e)
  
    # Check API rate limit and log data if possible
    if data:
        data = defs.rate_limit(data)
        defs.log_exchange(data, message)
   
    # Transform ticker into required format
    ticker['time']      = int(data['time'])
    ticker['symbol']    = data['result']['list'][0]['symbol']
    ticker['lastPrice'] = float(data['result']['list'][0]['lastPrice'])
    
    # Output to stdout
    defs.announce(f"Initial ticker price set to {ticker['lastPrice']} {ticker['symbol']} via exchange")
    
    if debug:
        defs.announce(ticker)
       
    # Return ticker
    return ticker

# Preload klines
def get_klines(symbol, interval, limit):
   
    # Debug
    debug = False
    
    # Initialize variables
    data            = {}
    klines          = {'time': [], 'open': [], 'high': [], 'low': [], 'close': [], 'volume': [], 'turnover': []}
    end_timestamp   = defs.now_utc()[4]
    start_timestamp = end_timestamp - (interval * (limit - 1) * 60 * 1000)

    # Load klines via normal session
    message = defs.announce("session: getkline")
    try:
        data = session.get_kline(
            category = "spot",
            symbol   = symbol,
            interval = interval,
            limit    = limit
        )
    except Exception as e:
        defs.log_error(e)

    # Check API rate limit and log data if possible
    if data:
        data = defs.rate_limit(data)
        defs.log_exchange(data, message)
    
    # Transform klines into required format
    for item in data['result']['list']:
        klines['time'].append(int(item[0]))         # Time
        klines['open'].append(float(item[1]))       # Open prices
        klines['high'].append(float(item[2]))       # High prices
        klines['low'].append(float(item[3]))        # Low prices
        klines['close'].append(float(item[4]))      # Close prices
        klines['volume'].append(float(item[5]))     # Volume
        klines['turnover'].append(float(item[6]))   # Turnover
        
    # Reverse the items in the lists of the dictionary klines (thank you Bybit!)
    for key in klines:
        klines[key].reverse()
        
    # Output to stdout
    defs.announce(f"Initial {limit} klines with {interval}m interval loaded from exchange")
    
    if debug:
        defs.announce(f"Prefilled klines with interval {interval}m")
        defs.announce(f"Time : {klines['time']}")
        defs.announce(f"Open : {klines['open']}")
        defs.announce(f"High : {klines['high']}")
        defs.announce(f"Low  : {klines['low']}")
        defs.announce(f"Close: {klines['close']}")
    
    # return klines
    return klines

# Preload prices
def get_prices(symbol, interval, limit):

    # Debug
    debug = False
       
    # Initialize prices
    prices = {}

    # Get kline with the lowest interval (1 minute)
    kline_prices = get_klines(symbol, interval, limit)
    prices       = {
        'time' : kline_prices['time'],
        'price': kline_prices['close']
    }

    # Report to stdout
    defs.announce(f"Initial {limit} prices with {interval}m interval extracted from klines")

    # Return prices
    return prices

# Combine two lists of prices
def combine_prices(prices_1, prices_2):
    
    # Combine and sort by 'time'
    prices = sorted(zip(prices_1['time'] + prices_2['time'], prices_1['price'] + prices_2['price']))

    # Use a dictionary to remove duplicates, keeping the first occurrence of each 'time'
    unique_prices = {}
    for t, p in prices:
        if t not in unique_prices:
            unique_prices[t] = p

    # Separate into 'time' and 'price' lists
    combined_prices = {
        'time': list(unique_prices.keys()),
        'price': list(unique_prices.values())
    }
    
    # Return combined list
    return combined_prices

# Calculations required for info
def calc_info(info, spot, multiplier, compounding):

    # Debug
    debug = False
    
    # Initialize variables
    add_up            = 1.1
    compounding_ratio = 1.0

    # Calculate minimum order value, add up and round up to prevent strange errors
    minimumQty = info['minOrderQty'] * spot
    minimumAmt = info['minOrderAmt']

    # Choose to use quantity or amount
    if minimumQty < minimumAmt:
        minimumOrder = (minimumAmt / spot) * add_up
    else:
        minimumOrder = (minimumQty / spot) * add_up

    # Do compounding if enabled
    if compounding['enabled']:
        
        # Only compound if when profitable
        if compounding['now'] > compounding['start']:
            compounding_ratio = compounding['now'] / compounding['start']

    # Round correctly, adjust for multiplier and compounding
    info['minBuyBase']  = defs.round_number(minimumOrder * multiplier * compounding_ratio, info['basePrecision'], "up")
    info['minBuyQuote'] = defs.round_number(minimumOrder * spot * multiplier * compounding_ratio, info['quotePrecision'], "up")

    # Debug
    if debug:
        defs.announce(f"Minimum order in base is {info['minBuyBase']} {info['baseCoin']} and in quote is {info['minBuyQuote']} {info['quoteCoin']}")

    # Return instrument info
    return info

# Preload instrument info
def get_info(symbol, spot, multiplier, compounding):

    # Debug
    debug = False
    
    # Initialize variables
    data = {}
    info = {}

    # Load instrument info via normal session
    message  = defs.announce("session: get_instruments_info")
    try:
        data = session.get_instruments_info(
            category = "spot",
            symbol   = symbol
        )
    except Exception as e:
        defs.log_error(e)

    # Check API rate limit and log data if possible
    if data:
        data = defs.rate_limit(data)
        defs.log_exchange(data, message)
     
    # Transform instrument info intro rquired format
    info['time']           = data['time']                                                           # Time of last instrument update
    info['symbol']         = data['result']['list'][0]['symbol']                                    # Symbol
    info['baseCoin']       = data['result']['list'][0]['baseCoin']                                  # Base asset, in case of BTCUSDT it is BTC
    info['quoteCoin']      = data['result']['list'][0]['quoteCoin']                                 # Quote asset, in case of BTCUSDT it is USDT
    info['status']         = data['result']['list'][0]['status']                                    # Is the symbol trading?
    info['basePrecision']  = float(data['result']['list'][0]['lotSizeFilter']['basePrecision'])     # Decimal precision of base asset (BTC)
    info['quotePrecision'] = float(data['result']['list'][0]['lotSizeFilter']['quotePrecision'])    # Decimal precision of quote asset (USDT)
    info['minOrderQty']    = float(data['result']['list'][0]['lotSizeFilter']['minOrderQty'])       # Minimum order quantity in quote asset (BTC)
    info['maxOrderQty']    = float(data['result']['list'][0]['lotSizeFilter']['maxOrderQty'])       # Maximum order quantity in base asset (BTC)
    info['minOrderAmt']    = float(data['result']['list'][0]['lotSizeFilter']['minOrderAmt'])       # Minimum order quantity in quote asset (USDT)
    info['maxOrderAmt']    = float(data['result']['list'][0]['lotSizeFilter']['maxOrderAmt'])       # Maximum order quantity in quote asset (USDT)
    info['tickSize']       = float(data['result']['list'][0]['priceFilter']['tickSize'])            # Smallest possible price increment of base asset (USDT)

    # Calculate additional values
    data = calc_info(info, spot, multiplier, compounding)
    
    # Add info
    info['minBuyBase']     = data['minBuyBase']                                                     # Minimum buy value in Base Asset (possibly corrected for multiplier and compounding!)
    info['minBuyQuote']    = data['minBuyQuote']                                                    # Minimum buy value in Quote Asset (possibly corrected for multiplier and compounding!)

    # Debug
    if debug:
        defs.announce("Instrument info")
        pprint.pprint(info)
  
    # Return instrument info
    return info
    
# Create empty files for check_files
def create_file(create_file, content=""):
        
    # Does the file exist and if not create a file    
    if not os.path.exists(create_file):
        with open(create_file, 'a') as file:
            if content:
                file.write(content)
            else:
                pass

    # Return
    return

# Check if necessary files exists
def check_files():
        
    # Does the data folder exist
    if not os.path.exists(config.data_folder):
        os.makedirs(config.data_folder)
    
    # Headers for files
    revenue_header = "UTCTime,createdTime,orderId,side,symbol,baseCoin,quoteCoin,orderType,orderStatus,avgPrice,qty,triggerStart,triggerEnd,cumExecFee,cumExecQty,cumExecValue,revenue\n"
    
    # Does the buy orders database exist
    create_file(config.dbase_file)                      # Buy orders database
    create_file(config.error_file)                      # Errors log file
    create_file(config.exchange_file)                   # Exchange log file
    create_file(config.revenue_file, revenue_header)    # Revenue log file
    
    defs.announce("All folders and files checked")
    
# Check orders in database if they still exist
def check_orders(transactions, info):
    
    # Initialize variables
    message          = ""
    all_buys         = []
    transaction      = {}
    temp_transaction = {}
    quick            = config.quick_check

    # Output to stdout
    defs.announce("Checking all orders on exchange")

    # Loop through all buys
    for transaction in transactions:

        # Check orders
        if quick:
            # Only check order on exchange if status is not Closed
            defs.announce(f"Checking order from database with ID {transaction['orderId']}")
            temp_transaction = transaction
            if transaction['status'] != "Closed":
                defs.announce("Performing an additional check on order status via exchange")
                temp_transaction = orders.transaction_from_id(transaction['orderId'])
        else:
            # Check all order on exchange regardless of status
            defs.announce(f"Checking order on exchange: {transaction['orderId']}")
            temp_transaction = orders.transaction_from_id(transaction['orderId'])

        # Assign status
        if "Filled" in temp_transaction['orderStatus']:
            temp_transaction['status'] = "Closed"
            all_buys.append(temp_transaction)
        
    # Save refreshed database
    database.save(all_buys, info)
    
    # Return correct database
    return all_buys 
