### Sunflow Cryptobot ###
#
# Calculate trigger price distance

# Load libraries
from loader import load_config
import math, pandas as pd
import defs

# Load config
config = load_config()

# Calculates the closest index
def get_closest_index(prices, span):
    
    # Find the closest index in the time {timeframe}
    closest_index = None
    min_diff = float('inf')

    for i, t in enumerate(prices['time']):
        diff = abs(t - span)
        if diff < min_diff:
            min_diff = diff
            closest_index = i

    # Return closest index
    return closest_index

# Protect buy and sell
def protect(active_order, price_distance):
    
    # Debug
    debug = False
    
    # Debug
    if debug:
        defs.announce( "debug: Distances before")
        print        (f"Trailing side   : {active_order['side']}")
        print        (f"Default distance: {active_order['distance']:.4f} %")
        print        (f"Price distance  : {price_distance:.4f} %")
        print        (f"Spot distance   : {active_order['fluctuation']:.4f} %")
        print        (f"Wave distance   : {active_order['wave']:.4f} %\n")
    
    # Selling
    if active_order['side'] == "Sell":

        # Set the wave for selling
        active_order['fluctuation'] = active_order['wave']

        # Prevent selling at a loss
        profitable = price_distance + active_order['distance']
        if active_order['wave'] > profitable:
            active_order['fluctuation'] = profitable
                        
        # Check direction of the wave
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

        # Set the wave for buying
        active_order['fluctuation'] = active_order['wave']
        
        # Check direction of the wave
        if active_order['wave'] < active_order['distance']:
            active_order['fluctuation'] = active_order['distance']

        # Check direction of the wave
        if active_order['wave'] < active_order['distance']:
            if price_distance > active_order['distance']:
                if active_order['wave'] > 0:
                    active_order['fluctuation'] = active_order['wave']
            else:
                active_order['fluctuation'] = active_order['distance']

        # Temp debug
        if debug:
            defs.announce( "debug: Distances after")
            print        (f"Default distance    : {active_order['distance']:.4f} %")
            print        (f"Wave distance       : {active_order['wave']:.4f} %")
            print        (f"Fluctuation distance: {active_order['fluctuation']:.4f} %\n")

        
    ''' Let's remove these fail safes for now 

    # Always keep wave at minimum distance
    if abs(active_order['wave']) < active_order['distance']:
        active_order['fluctuation'] = active_order['distance']

    # Double check, not really efficient, but it works
    if active_order['fluctuation'] < active_order['distance']:
        active_order['fluctuation'] = active_order['distance']

    '''
    
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

def distance_ema(active_order, prices, price_distance):
    
    # Devide normalized value by this, ie. 2 means it will range between 0 and 0.5
    scaler = 1
    
    # Time calculations
    latest_time = prices['time'][-1]                    # Get the time for the last element
    span        = latest_time - config.wave_timeframe   # Get the time of the last element minus the timeframe

    # Calculate amount of price items to use
    closest_index = get_closest_index(prices, span)
    number        = config.limit - closest_index

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
    fluctuation = df['ewm_std'].iloc[-1] / df['ewm_std'].max()
    
    # Calculate trigger price distance percentage
    active_order['wave'] = (fluctuation / scaler)
    
    # Check for failures
    if math.isnan(active_order['wave']):
        active_order['wave'] = active_order['distance']
    
    # Prevent sell at loss and other issues
    active_order = protect(active_order, price_distance)
    
    # Return active_order
    return active_order

# Calculate distance using hybrid *** CHECK *** Must calculated this over a timeframe, not a number of prices!
def distance_hybrid(active_order, prices, price_distance):

    # Devide normalized value by this, ie. 2 means it will range between 0 and 0.5
    scaler = 2

    # Time calculations
    latest_time = prices['time'][-1]                    # Get the time for the last element
    span        = latest_time - config.wave_timeframe   # Get the time of the last element minus the timeframe

    # Calculate amount of price items to use
    closest_index = get_closest_index(prices, span)
    number        = config.limit - closest_index
    
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
    fluctuation = df['ewm_std'].iloc[-1] / df['ewm_std'].max()

    # Calculate dynamic scaler based on market conditions (here we just use the default scaler, but it could be dynamic)
    dynamic_scaler = scaler

    # Calculate trigger price distance percentage
    active_order['fluctuation'] = (fluctuation / dynamic_scaler) + active_order['distance']

    # Prevent sell at loss and other issues
    active_order = protect(active_order, price_distance)
    
    # Return active_order
    return active_order

# Calculate distance using wave
def distance_wave(active_order, prices, price_distance):
    
    # Debug
    debug = False

    # Time calculations
    latest_time = prices['time'][-1]                     # Get the latest time
    span = latest_time - config.wave_timeframe   # timeframe in milliseconds

    # Get the closest index in the time {timeframe}
    closest_index = get_closest_index(prices, span)

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
    active_order = protect(active_order, price_distance)

    # Return active_order
    return active_order   

# Calculate trigger price distance
def calculate(active_order, prices):
   
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

    ''' Use EMA to set trigger price distance '''
    if active_order['wiggle'] == "EMA":
        active_order = distance_ema(active_order, prices, price_distance)

    ''' Use HYBRID to set distance '''
    if active_order['wiggle'] == "Hybrid":
        active_order = distance_hybrid(active_order, prices, price_distance)

    # Output to stdout
    if previous_fluctuation != active_order['fluctuation']:
        defs.announce(f"Adviced trigger price distance is now {active_order['fluctuation']:.4f} %")

    # Return modified data
    return active_order
