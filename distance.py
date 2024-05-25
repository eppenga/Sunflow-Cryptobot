### Sunflow Cryptobot ###
#
# Calculate trigger price distance

# Load libraries
import defs
import math, pandas as pd

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

# Calculate price changes to get wave length 
def waves(prices, use_waves):

    # Initialize variables
    debug   = False
    spiking = False

    # Time calculations
    latest_time = prices['time'][-1]              # Get the latest time
    span = latest_time - use_waves['timeframe']   # timeframe in milliseconds

    # Get the closest index in the time {timeframe}
    closest_index = get_closest_index(prices, span)

    # Calculate the change in price
    price_change      = 0
    price_change_perc = 0
    if closest_index is not None and prices['time'][-1] > span:
        price_change      = prices['price'][-1] - prices['price'][closest_index]
        price_change_perc = (price_change / prices['price'][closest_index]) * 100

    # Apply wave multiplier
    price_change_perc = price_change_perc * use_waves['multiplier']

    if debug:
        defs.announce(f"Price change in the last {use_waves['timeframe'] / 1000:.2f} seconds is {price_change_perc:.2f} %")

    # Return price change percentage
    return price_change_perc

# Calculate trigger price distance
def calculate(active_order, prices):

    # Debug
    debug = False

    # Initialize variables
    scaler              = 4       # Devide normalized value by this, ie. 2 means it will range between 0 and 0.5
    number              = 10      # Last {number} of prices will be used
    fluctuation         = 0       # Fluctuation distance of trigger price
    price_distance      = 0       # Price distance between start and current price in percentage
    fluc_price_distance = 0       # Price distance used in calculations
    
    # Store previous fluctuation
    previous_flucation = active_order['fluctuation']
    
    # By default fluctuation equals distance
    active_order['fluctuation'] = active_order['distance']
    
    # Calculate price distance in percentage as a given 
    price_distance = ((active_order['current'] - active_order['start']) / active_order['start']) * 100


    ''' Use FIXED to set trigger price distance '''
    
    if active_order['wiggle'] == "Fixed":
        active_order['fluctuation'] = active_order['distance']
        if previous_flucation != active_order['fluctuation']:
            defs.announce(f"Fixed calculated trigger price distance changed to {active_order['fluctuation']:.4f} %")


    ''' Use EMA to set trigger price distance '''
    
    if active_order['wiggle'] == "EMA":

        # Convert the list to a pandas DataFrame
        df = pd.DataFrame(prices['price'], columns=['price'])

        # Calculate the periodic returns
        df['returns'] = df['price'].pct_change()

        # Apply an exponentially weighted moving standard deviation to the returns
        df['ewm_std'] = df['returns'].ewm(span=number, adjust=False).std()

        # Normalize the last value of EWM_Std to a 0-1 scale
        fluctuation = df['ewm_std'].iloc[-1] / df['ewm_std'].max()

        # Calculate trigger price distance percentage
        active_order['fluctuation'] = (fluctuation / scaler) + active_order['distance']
        if previous_flucation != active_order['fluctuation']:
            defs.announce(f"EMA calculated trigger price distance changed to {active_order['fluctuation']:.4f} %")
    

    ''' Use SPOT to set trigger price distance '''
    
    if active_order['wiggle'] == "Spot":

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
        
        # Output to stdout
        if previous_flucation != active_order['fluctuation']:
            defs.announce(f"Spot calculated trigger price distance changed to {active_order['fluctuation']:.4f} %")


    ''' Use WAVE to set distance '''
    
    if active_order['wiggle'] == "Wave":

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

        # Output to stdout
        if previous_flucation != active_order['fluctuation']:
            defs.announce(f"Wave calculated trigger price distance is {active_order['fluctuation']:.4f} %")

    # Return modified data
    return active_order
