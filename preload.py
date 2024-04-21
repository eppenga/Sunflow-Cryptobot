### Sunflow Cryptobot ###
#
# Preload ticker, klines, instrument info and other data

# Load external libraries
from pybit.unified_trading import HTTP
import importlib, os, sys, time

# Load internal libraries
import database, defs, orders

# Load default config file or from command line
if len(sys.argv) > 1:
    config_file = sys.argv[1]
else:
    config_file = "config"
config = importlib.import_module(config_file)

# Debug
debug = False

# Connect to exchange
session = HTTP(
    testnet = False,
    return_response_headers = True
)

# Preload ticker
def get_ticker(symbol):

    # Initialize ticker
    ticker = {'time': 0, 'lastPrice': 0}
   
    # Load ticker via normal session
    message = defs.now_utc()[1] + "Preload: get_ticker: session: get_tickers\n"
    print(message)
    pre_ticker = {}
    try:
        pre_ticker   = session.get_tickers(
            category = "spot",
            symbol   = symbol,
        )
    except Exception as e:
        defs.log_error(e)

    # Check API rate limit and log data if possible
    if pre_ticker:
        pre_ticker = defs.rate_limit(pre_ticker)
        defs.log_exchange(pre_ticker, message)
   
    # Transform ticker into required format
    ticker['time']      = int(pre_ticker['time'])
    ticker['symbol']    = pre_ticker['result']['list'][0]['symbol']
    ticker['lastPrice'] = float(pre_ticker['result']['list'][0]['lastPrice'])
    
    # Output to stdout
    print(defs.now_utc()[1] + "Preload: get_ticker: Initial ticker loaded!\n")
    
    if debug:
        print(defs.now_utc()[1])
        print(ticker)
       
    #return ticker
    return ticker

# Preload klines
def get_klines(symbol, interval, limit):
   
    # Debug
    debug = False
    
    # Initialize klines
    klines = {'time': [], 'open': [], 'high': [], 'low': [], 'close': [], 'volume': [], 'turnover': []}
    
    # Load klines via normal session
    message = defs.now_utc()[1] + "Orders: get_klines: session: get_kline\n"
    print(message)
    pre_klines = {}
    try:
        pre_klines = session.get_kline(
            category = "spot",
            symbol   = symbol,
            interval = interval,
            limit    = limit
        )
    except Exception as e:
        defs.log_error(e)

    # Check API rate limit and log data if possible
    if pre_klines:
        pre_klines = defs.rate_limit(pre_klines)
        defs.log_exchange(pre_klines, message)
    
    # Transform klines into required format
    for item in pre_klines['result']['list']:
        klines['time'].append(int(item[0]))
        klines['open'].append(float(item[1]))
        klines['high'].append(float(item[2]))
        klines['low'].append(float(item[3]))
        klines['close'].append(float(item[4]))
        klines['volume'].append(float(item[5]))
        klines['turnover'].append(float(item[6]))
        
    # Reverse the items in the lists of the dictionary klines (thank you Bybit!)
    for key in klines:
        klines[key].reverse()
        
    # Output to stdout
    print(defs.now_utc()[1] + "Preload: get_klines: Initial klines with interval " + str(interval) + "m loaded!\n")
    
    if debug:
        print(defs.now_utc()[1] + "Preload: get_klines: Prefilled klines with interval " + str(interval) + "m")
        print(defs.now_utc()[1] + "Time : " + str(klines['time']))
        print(defs.now_utc()[1] + "Open : " + str(klines['open']))
        print(defs.now_utc()[1] + "High : " + str(klines['high']))
        print(defs.now_utc()[1] + "Low  : " + str(klines['low']))
        print(defs.now_utc()[1] + "Close: " + str(klines['close']))
    
    # return klines
    return klines

# Preload instrument info
def get_info(symbol, spot, multiplier):

    # Initialize info
    info   = {'time': 0, 'symbol': '', 'baseCoin': '', 'quoteCoin': '', 'status': '', 'basePrecision': 0, 'quotePrecision': 0, 'minOrderQty': 0, 'maxOrderQty': 0, 'minOrderAmt': 0, 'maxOrderAmt': 0, 'tickSize': 0} 

    # Load instrument info via normal session
    message = defs.now_utc()[1] + "Orders: get_info: session: get_instruments_info\n"
    print(message)
    pre_info = {}
    try:
        pre_info = session.get_instruments_info(
            category = "spot",
            symbol   = symbol
        )
    except Exception as e:
        defs.log_error(e)
        
    # Check API rate limit and log data if possible
    if pre_info:
        pre_info = defs.rate_limit(pre_info)
        defs.log_exchange(pre_info, message)
     
    # Transform instrument info intro rquired format
    info                   = {}
    info['time']           = pre_info['time']
    info['symbol']         = pre_info['result']['list'][0]['symbol']
    info['baseCoin']       = pre_info['result']['list'][0]['baseCoin']
    info['quoteCoin']      = pre_info['result']['list'][0]['quoteCoin']
    info['status']         = pre_info['result']['list'][0]['status']
    info['basePrecision']  = float(pre_info['result']['list'][0]['lotSizeFilter']['basePrecision'])
    info['quotePrecision'] = float(pre_info['result']['list'][0]['lotSizeFilter']['quotePrecision'])
    info['minOrderQty']    = float(pre_info['result']['list'][0]['lotSizeFilter']['minOrderQty'])
    info['maxOrderQty']    = float(pre_info['result']['list'][0]['lotSizeFilter']['maxOrderQty'])
    info['minOrderAmt']    = float(pre_info['result']['list'][0]['lotSizeFilter']['minOrderAmt'])
    info['maxOrderAmt']    = float(pre_info['result']['list'][0]['lotSizeFilter']['maxOrderAmt'])
    info['tickSize']       = float(pre_info['result']['list'][0]['priceFilter']['tickSize'])

    # Calculate minimum order value and add 10% to prevent strange errors
    minimumQty = info['minOrderQty'] * spot
    minimumAmt = info['minOrderAmt']

    if minimumQty < minimumAmt:
        minimumOrder = (minimumAmt / spot) * 1.1
    else:
        minimumOrder = (minimumQty / spot) * 1.1
    info['minBuyBase']  = defs.precision(minimumOrder * multiplier, info['basePrecision'])
    info['minBuyQuote'] = defs.precision(minimumOrder * spot * multiplier, info['quotePrecision'])

    # Output to stdout
    print(defs.now_utc()[1] + "Preload: get_info: Instrument info loaded!\n")
    
    if debug:
        print(defs.now_utc()[1] + "Preload: get_info: Instrument info")
        print(info)
    
    # Summarize all info and return data
    data                   = {}                            # Declare data variable
    data['time']           = info['time']                  # Time of last instrument update
    data['symbol']         = info['symbol']                # Symbol
    data['baseCoin']       = info['baseCoin']              # Base asset, in case of BTCUSDT it is BTC 
    data['quoteCoin']      = info['quoteCoin']             # Quote asset, in case of BTCUSDT it is USDT
    data['status']         = info['status']                # Is the symbol trading?
    data['basePrecision']  = info['basePrecision']         # Decimal precision of base asset
    data['quotePrecision'] = info['quotePrecision']        # Decimal precision of quote asset
    data['minOrderQty']    = info['minOrderQty']           # Minimum order quantity in base asset
    data['maxOrderQty']    = info['maxOrderQty']           # Maximum order quantity in base asset
    data['minOrderAmt']    = info['minOrderAmt']           # Minimum order quantity in quote asset
    data['maxOrderAmt']    = info['maxOrderAmt']           # Maximum order quantity in quote asset
    data['tickSize']       = info['tickSize']              # Smallest possible price increment (of base asset) 
    data['minBuyBase']     = info['minBuyBase']            # Minimum buy value in Base Asset (possibly corrected for multiplier!)
    data['minBuyQuote']    = info['minBuyQuote']           # Minimum buy value in Quote Asset (possibly corrected for multiplier!)
    
    # Return instrument info
    return data

# Preload database with buys
def get_buys(dbase_file):
    
    # Get the database
    all_buys = database.load(dbase_file)
    print(defs.now_utc()[1] + "Preload: get_buys: Loaded database with buy transactions!\n")
    
    # Return the database
    return all_buys
    
# Check if necessary files exists
def check_files():
        
    # Does the data folder exist
    if not os.path.exists(config.data_folder):
        os.makedirs(config.data_folder)
    
    # Does the buy orders database exist    
    if not os.path.exists(config.dbase_file):
        with open(config.dbase_file, 'a') as file:
            pass

    # Does the errors log file exist
    if not os.path.exists(config.error_file):
        with open(config.error_file, 'a') as file:
            pass

    # Does the exchange log file exist
    if not os.path.exists(config.exchange_file):
        with open(config.exchange_file, 'a') as file:
            pass
    
    print(defs.now_utc()[1] + "Preload: check_files: All folders and files checked!\n")
    
# Check orders in database if they still exist
def check_orders(transactions):
    
    # Debug
    debug = False

    # Initialize variables
    all_buys = []

    print(defs.now_utc()[1] + "Preload: check_orders: Checking all order on exchange!\n")

    # Loop through all buys
    for transaction in transactions:

        # Get exchange info
        print(defs.now_utc()[1] + "Preload: check_orders: Now checking order: " + str(transaction['orderId']) + "\n")
        exchange_transaction = orders.transaction_from_id(transaction['orderId'])

        if "Filled" in exchange_transaction['orderStatus']:
            exchange_transaction['status'] = "Closed"
            all_buys.append(exchange_transaction)
        
    # Save refreshed database
    database.save(all_buys)
    
    # Return correct database
    return all_buys 
