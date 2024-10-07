### Sunflow Cryptobot ###
#
# Calculate trigger price distance

# Load libraries
from loader import load_config
import defs, math, pandas as pd, pandas_ta as ta, preload

# Load config
config = load_config()

# Initialize ATR timer
atr_timer             = {}
atr_timer['check']    = False
atr_timer['time']     = 0
atr_timer['interval'] = 60000

# Initialize ATR Klines
atr_klines = {'time': [], 'open': [], 'high': [], 'low': [], 'close': [], 'volume': [], 'turnover': []}

# Calculate ATR as percentage
def calculate_atr():
    
    # Debug
    debug = False

    # Declare ATR timer and klines variables global
    global atr_timer, atr_klines

    # Initialize variables
    get_atr_klines = False

    # Check every interval
    current_time = defs.now_utc()[4]
    if atr_timer['check']:
        atr_timer['check'] = False
        atr_timer['time']  = current_time
    if current_time - atr_timer['time'] > atr_timer['interval']:
        defs.announce(f"Requesting {config.limit} klines for ATR")
        atr_timer['check'] = True
        atr_timer['time']  = 0
        get_atr_klines = True

    # Get ATR klines if required
    if get_atr_klines:
        start_time = defs.now_utc()[4]
        atr_klines = preload.get_klines(config.symbol, 1, config.limit)
        end_time   = defs.now_utc()[4]
        defs.announce(f"Received {config.limit} ATR klines in {end_time - start_time}ms")
    
    # Initialize dataframe
    df = pd.DataFrame(atr_klines)
    
    # Calculate ATR and ATR percentage
    start_time     = defs.now_utc()[4]
    df['ATR']      = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['ATRP']     = (df['ATR'] / df['close']) * 100
    atr_percentage = df['ATRP'].iloc[-1]
    atr_perc_avg   = df['ATRP'].mean()
    atr_multiplier = atr_percentage / atr_perc_avg
    end_time       = defs.now_utc()[4]

    # Report ATR data
    if get_atr_klines:
        print("ATR Data (experimental)")
        print(f"ATR current percentage is {atr_percentage} %")
        print(f"ATR average percentage over {config.limit} klines is {atr_perc_avg} %")
        print(f"ATR multiplier is {atr_multiplier}\n")

   # Output to stdout
    if debug:
        defs.announce(f"ATR percentage is {atr_percentage} %, on average it was {atr_perc_avg} %, the multiplier is {atr_multiplier} and it took {end_time - start_time}ms to calculate")
      
    # Return ATR as percentage
    return atr_percentage, atr_perc_avg, atr_multiplier

# Protect buy and sell
def protect(active_order, price_distance):
    
    # Debug
    debug = False
    
    # Initialize variables
    show_distance = False
    
    # Debug
    if debug:
        defs.announce( "Debug: Distances before")
        print(f"Trailing side       : {active_order['side']}")
        print(f"Default distance    : {active_order['distance']:.4f} %")
        print(f"Price distance      : {price_distance:.4f} %")
        print(f"Wave distance       : {active_order['wave']:.4f} %\n")
        print(f"Fluctuation distance: {active_order['fluctuation']:.4f} %")
    
    # Selling
    if active_order['side'] == "Sell":

        # Set standard distance
        active_order['fluctuation'] = active_order['wave']

        # Prevent selling at a loss
        profitable = price_distance + active_order['distance']
        if active_order['wave'] > profitable:
            active_order['fluctuation'] = profitable
                        
        # If price distance is larger than default, use smaller distances *** CHECK *** Maybe this can be better
        if config.protect_peaks:
            if active_order['wave'] < active_order['distance']:
                if price_distance > active_order['distance']:
                    if active_order['wave'] > 0:
                        active_order['fluctuation'] = active_order['wave']
                else:
                    active_order['fluctuation'] = active_order['distance']
                
    # Buying
    if active_order['side'] == "Buy":
        
        # Reverse wave and price difference for buying logic
        active_order['wave'] = active_order['wave'] * -1
        price_distance       = price_distance * -1

        # Set standard distance
        active_order['fluctuation'] = active_order['wave']
        
        # Use minimum distance
        if active_order['wave'] < active_order['distance']:
            active_order['fluctuation'] = active_order['distance']

        # If price distance is larger than default, use smaller distances *** CHECK *** Maybe this can be better
        if config.protect_peaks:
            if active_order['wave'] < active_order['distance']:
                if price_distance > active_order['distance']:
                    if active_order['wave'] > 0:
                        active_order['fluctuation'] = active_order['wave']
                else:
                    active_order['fluctuation'] = active_order['distance']

    # Debug
    if debug:
        defs.announce("Debug: Distances after")
        print(f"Trailing side       : {active_order['side']}")
        print(f"Default distance    : {active_order['distance']:.4f} %")
        print(f"Price distance      : {price_distance:.4f} %")
        print(f"Wave distance       : {active_order['wave']:.4f} %")
        print(f"Fluctuation distance: {active_order['fluctuation']:.4f} %\n")

    # Last failsafe
    if active_order['fluctuation'] < 0:
        defs.announce(f"*** Warning: Fluctuation distance is {active_order['fluctuation']:.4f} %, enforcing 0.0000 %! ***")
        active_order['fluctuation'] = 0
    
    # Return active_order
    return active_order

# Calculate distance using fixed
def distance_fixed(active_order):
    
    # Distance
    active_order['fluctuation'] = active_order['distance']
        
    # Return active_order
    return active_order

# Calculate distance using spot
def distance_spot(active_order, price_distance):
    
    # Reverse fluc_price_distance based on buy or sell
    if active_order['side'] == "Sell":
        fluc_price_distance = price_distance
        if price_distance < 0:
            fluc_price_distance = 0
    else:
        fluc_price_distance = price_distance * -1
        if price_distance > 0:
            fluc_price_distance = 0               

    # Calculate trigger price distance percentage
    fluctuation = (1 / math.pow(10, 1/1.2)) * math.pow(fluc_price_distance, 1/1.2) + active_order['distance']

    # Set fluctuation
    if fluctuation < active_order['distance']:
        active_order['fluctuation'] = active_order['distance']
    else:
        active_order['fluctuation'] = fluctuation

    # Return active_order
    return active_order

# Calculate distance using EMA
def distance_ema(active_order, prices, price_distance):
    
    # Devide normalized value by this, ie. 2 means it will range between 0 and 0.5
    scaler = 1
    
    # Number of prices to use
    number = defs.get_index_number(prices, config.timeframe, config.limit)

    # Convert the lists to a pandas DataFrame
    df = pd.DataFrame({
        'price': prices['price'],
        'time': pd.to_datetime(prices['time'], unit='ms')
    })
    
    # Set time as the index
    df.set_index('time', inplace=True)
        
    # Calculate the periodic returns
    df['returns'] = df['price'].pct_change()
    
    # Apply an exponentially weighted moving standard deviation to the returns
    df['ewm_std'] = df['returns'].ewm(span=number, adjust=False).std()
    
    # Normalize the last value of EWM_Std to a 0-1 scale
    wave = df['ewm_std'].iloc[-1] / df['ewm_std'].max()
    
    # Calculate trigger price distance percentage
    active_order['wave'] = (wave / scaler)
    
    # Check for failures
    if math.isnan(active_order['wave']):
        active_order['wave'] = active_order['distance']
    
    # Prevent sell at loss and other issues
    active_order = protect(active_order, price_distance)
    
    # Return active_order
    return active_order

# Calculate distance using hybrid
def distance_hybrid(active_order, prices, price_distance):

    # Devide normalized value by this, ie. 2 means it will range between 0 and 0.5
    scaler = 2

    # Number of prices to use
    number = defs.get_index_number(prices, config.wave_timeframe, config.limit)
    
    # Adaptive EMA span based on volatility
    recent_prices = pd.Series(prices['price'][-number:])      # Get recent prices
    volatility = recent_prices.std() / recent_prices.mean()   # Calculate volatility as a percentage
    if math.isnan(volatility): volatility = 0                 # Safeguard volatilty
    ema_span = max(5, int(number * (1 + volatility)))         # Adjust span based on volatility, minimum span of 5

    # Convert the list to a pandas DataFrame
    df = pd.DataFrame(prices['price'], columns=['price'])

    # Calculate the periodic returns
    df['returns'] = df['price'].pct_change()

    # Apply an exponentially weighted moving standard deviation to the returns
    df['ewm_std'] = df['returns'].ewm(span=ema_span, adjust=False).std()

    # Normalize the last value of EWM_Std to a 0-1 scale
    wave = df['ewm_std'].iloc[-1] / df['ewm_std'].max()

    # Calculate dynamic scaler based on market conditions (here we just use the default scaler, but it could be dynamic)
    dynamic_scaler = scaler

    # Calculate trigger price distance percentage
    active_order['wave'] = (wave / dynamic_scaler) + active_order['distance']

    # Prevent sell at loss and other issues
    active_order = protect(active_order, price_distance)
    
    # Return active_order
    return active_order

# Calculate distance using wave
def distance_wave(active_order, prices, price_distance, prevent=True):
    
    # Debug
    debug = False

    # Time calculations
    latest_time = prices['time'][-1]                     # Get the latest time
    span = latest_time - config.wave_timeframe   # timeframe in milliseconds

    # Get the closest index in the time {timeframe}
    closest_index = defs.get_closest_index(prices, span)

    # Calculate the change in price
    price_change      = 0
    price_change_perc = 0
    if closest_index is not None and prices['time'][-1] > span:
        price_change      = prices['price'][-1] - prices['price'][closest_index]
        price_change_perc = (price_change / prices['price'][closest_index]) * 100

    # Apply wave multiplier
    active_order['wave'] = price_change_perc * config.wave_multiplier

    if debug:
        defs.announce(f"Price change in the last {config.wave_timeframe / 1000:.2f} seconds is {active_order['wave']:.2f} %")

    # Prevent sell at loss and other issues
    if prevent:
        active_order = protect(active_order, price_distance)

    # Return active_order
    return active_order   

# Calculate distance using wave taking ATR into account
def distance_atr(active_order, prices, price_distance):

    # Initialize variables
    scaler = 1
    result = ()
    
    # Get ATR percentage and average
    result         = calculate_atr()
    atr_percentage = result[0]
    atr_perc_avg   = result[1]
    atr_multiplier = result[2] * scaler

    # Get wave
    active_order = distance_wave(active_order, prices, price_distance, False)

    # Adjust active_order
    active_order['wave'] = atr_multiplier * active_order['wave']

    # Prevent sell at loss and other issues
    active_order = protect(active_order, price_distance)
    
    # Return active_order
    return active_order

# Calculate trigger price distance
def calculate(active_order, prices):

    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]

    # Store previous fluctuation
    previous_fluctuation = active_order['fluctuation']
    
    # By default fluctuation equals distance
    active_order['fluctuation'] = active_order['distance']
    
    # Calculate price distance since start of trailing in percentages 
    price_distance = ((active_order['current'] - active_order['start']) / active_order['start']) * 100

    ''' Use FIXED to set trigger price distance '''
    if active_order['wiggle'] == "Fixed":
        active_order = distance_fixed(active_order)

    ''' Use SPOT to set trigger price distance '''
    if active_order['wiggle'] == "Spot":
        active_order = distance_spot(active_order, price_distance)

    ''' Use WAVE to set distance '''
    if active_order['wiggle'] == "Wave":
        active_order = distance_wave(active_order, prices, price_distance)

    ''' Use ATR for WAVE to set distance '''
    if active_order['wiggle'] == "ATR":
        active_order = distance_atr(active_order, prices, price_distance)

    ''' Use EMA to set trigger price distance '''
    if active_order['wiggle'] == "EMA":
        active_order = distance_ema(active_order, prices, price_distance)

    ''' Use HYBRID to set distance '''
    if active_order['wiggle'] == "Hybrid":
        active_order = distance_hybrid(active_order, prices, price_distance)

    # Output to stdout
    if previous_fluctuation != active_order['fluctuation']:
        defs.announce(f"Adviced trigger price distance is now {active_order['fluctuation']:.4f} %")

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return modified data
    return active_order
