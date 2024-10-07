### Sunflow Cryptobot ###
#
# Find optimal trigger price distance and profit percentage

# Load libraries
from loader import load_config
import defs, pprint
import math, pandas as pd

# Load config
config = load_config()

# Resample and create dataframe for optimizer
def resample_optimzer(prices, interval):

    # Debug
    debug = False
  
    # Convert the time and price data into a DataFrame
    df = pd.DataFrame(prices)
    
    # Convert the 'time' column to datetime format
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    
    # Set the 'time' column as the index
    df.set_index('time', inplace=True)
    
    # Resample the data to the specified interval
    df_resampled = df['price'].resample(interval).last()
    
    # Drop any NaN values that may result from resampling
    df_resampled.dropna(inplace=True)

    # Remove the last row
    df_resampled = df_resampled.iloc[:-1]

    # Debug
    if debug:
        defs.announce("Resampled dataframe:")
        pprint.pprint(df_resampled)

    # Return dataframe
    return df_resampled

# Optimize profit and default trigger price distance based on previous prices
def optimize(prices, profit, active_order, use_spread, optimizer):
       
    # Debug and speed
    debug = False
    speed = True
    stime = defs.now_utc()[4]
    
    # Global error counter
    global df_errors, halt_sunflow
  
    # Initialize variables
    volatility   = 0                                    # Volatility
    length       = 10                                   # Length over which the volatility is calculated
    interval     = str(optimizer['interval']) + "min"   # Interval used for indicator KPI (in our case historical volatility)
    profit       = optimizer['profit']                  # Initial profit
    profit_new   = optimizer['profit']                  # New profit to be
    distance     = optimizer['distance']                # Initial distance
    distance_new = optimizer['distance']                # New distance to be
    spread       = optimizer['spread']                  # Initial spread
    spread_new   = optimizer['spread']                  # New spread to be
    start_time   = defs.now_utc()[4]                    # Current time

    # Optimize only on desired sides
    if active_order['side'] not in optimizer['sides']:
        defs.announce(f"Optimization not executed, active side {active_order['side']} is not in {optimizer['sides']}")
        if speed: defs.announce(defs.report_exec(stime, "early return to optimizaton issue"))
        return profit, active_order, optimizer
    
    # Check if we can optimize
    if start_time - prices['time'][0] < optimizer['limit_min']:
        defs.announce(f"Optimization not possible yet, missing {start_time - prices['time'][0]} ms of price data")
        if speed: defs.announce(defs.report_exec(stime, "early return due to optimizaton issue"))
        return profit, active_order, optimizer

    # Try to optimize
    try:

        ## Create a dataframe in two steps, we do this for speed reasons. The first part of the dataframe is kept
        ## in something like a cache, and then we always add the last one or two intervals. 

        # Resample and create dataframe for the first time or get it from cache
        if optimizer['df'].empty:
            df = resample_optimzer(prices, interval)
        else:
            df = optimizer['df']
        
        # Get the timestamp of the last item in the dataframe in miliseconds
        last_timestamp = int(df.index[-1].timestamp() * 1000)
        
        # Which prices are not yet in the resampled data since last timestamp of dataframe
        prices_new = {
            'price': [price for price, time in zip(prices['price'], prices['time']) if time > last_timestamp],
            'time': [time for time in prices['time'] if time > last_timestamp]
        }

        # Create a dataframe from the new prices
        df_new         = pd.DataFrame(prices_new)
        df_new['time'] = pd.to_datetime(df_new['time'], unit='ms')
        df_new.set_index('time', inplace=True)

        # Debug to stdout
        if debug:
            defs.announce("Dataframes to be concatenated")
            print(df)
            print()
            print(df_new)

        # Concatenate the cached and new dataframes
        df = pd.concat([df, df_new])

        # Resample again and drop empty rows
        df = df['price'].resample(interval).last()
        df.dropna(inplace=True)


        ## Here we calculate the optimizer KPI, in this case volatility, but you can use anything you like

        # Calculate the log returns
        df = df.to_frame()
        df['log_return'] = df['price'].apply(lambda x: math.log(x)) - df['price'].shift(1).apply(lambda x: math.log(x))
        
        # Calculate the rolling volatility (standard deviation of log returns)
        df['volatility'] = df['log_return'].rolling(window=length).std() * math.sqrt(length)
        
        # Calculate the average volatility
        average_volatility = df['volatility'].mean()
        
        # Add a column for the deviation percentage from the average volatility
        df['volatility_deviation_pct'] = ((df['volatility'] - average_volatility) / average_volatility)
        
        # Drop the 'log_return' column if not needed
        df.drop(columns=['log_return'], inplace=True)
        
        # Debug report volatility
        if debug:
            defs.announce(f"Raw optimized volatility {df['volatility_deviation_pct'].iloc[-1]:.4f} %")
        
        # Get volatility deviation
        volatility   = df['volatility_deviation_pct'].iloc[-1] * optimizer['scaler']
        volatility   = min(volatility, optimizer['adj_max'] / 100)
        volatility   = max(volatility, optimizer['adj_min'] / 100)

        # Set new profit and trigger price distance
        profit_new   = profit * (1 + volatility)
        distance_new = (distance / profit) * profit_new
        
        # Set new spread distance
        if optimizer['spread_enabled']:
            spread_new = spread * (1 + volatility)

        # Debug to stdout
        if debug:
            defs.announce("Optimized full dataframe:")
            print(df)
            defs.annouce(f"Age of database {start_time - prices['time'][0]} ms")
            
        # Store the dataframe for future use, except for the last row
        optimizer['df'] = df.iloc[:-1]
        
    # In case of failure
    except Exception as e:
        
        # Count the errors and log
        df_errors  = df_errors + 1
        defs.log_error(e)
        
        # After three consecutive errors halt
        if df_errors > 2:
            halt_sunflow = True
        if speed: defs.announce(defs.report_exec(stime, "early return due to error"))    
        return profit, active_order, optimizer
   
    # Reset error counter
    df_errors = 0
  
    # Rework to original variable
    use_spread['distance']   = spread_new
    active_order['distance'] = distance_new
  
    # Report to stdout
    if volatility != 0:
        defs.announce(f"Volatility {(volatility * 100):.4f} %, profit {profit_new:.4f} %, trigger price distance {distance_new:.4f} %, spread {spread_new:.4f} %")
    else:
        defs.announce(f"Optimization not possible, volatility out of range")

    # Report execution time
    if speed: defs.announce(defs.report_exec(stime))

    # Return
    return profit_new, active_order, use_spread, optimizer
