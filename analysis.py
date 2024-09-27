### Sunflow Cryptobot ###
#
# Analyzer reports how well your Sunflow Cryptobot is doing
# Usage is experimental and you need to install matplotlib and seaborn as well
#
# Use with or without config file:
# python analysis.py
# python analysis.py -c {optional path/}your_config.py

  
### Initialize ###

# Load external libraries
from pathlib import Path
from pybit.unified_trading import HTTP
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import argparse, importlib, pprint, sys

# Load internal libraries
import database, defs, orders, preload

# Parse command line arguments
parser = argparse.ArgumentParser(description="Run the Sunflow Cryptobot Tester with a specified config.")
parser.add_argument('-c', '--config', default='config.py', help='Specify the config file (with .py extension).')
parser.add_argument('-d', '--days', type=int, default=30, help='Number of days to display in the profit per day graph.')
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

# Connect to exchange
session = HTTP(
    testnet                 = False,
    api_key                 = config.api_key,
    api_secret              = config.api_secret,
    return_response_headers = True
)

# Initialize variables
debug = False

# Calculate time elements
def calc_time(df):

    # Calculate oldest and latest order times
    first = df['createdTime'].min().strftime('%d-%m-%Y %H:%M:%S')
    last = df['createdTime'].max().strftime('%d-%m-%Y %H:%M:%S')

    # Calculate duration
    start = df['createdTime'].min()
    end   = df['createdTime'].max()
    span   = end - start

    # Calculate days, hours, minutes, and seconds
    days    = span.days
    seconds = span.seconds
    hours   = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    time_elements            = {}
    time_elements['first']   = first
    time_elements['last']    = last
    time_elements['start']   = start
    time_elements['end']     = end
    time_elements['span']    = span
    time_elements['days']    = days
    time_elements['seconds'] = seconds
    time_elements['hours']   = hours
    time_elements['minutes'] = minutes
    time_elements['seconds'] = seconds
        
    # Return time elements
    return time_elements


### Analysis ###

# Display welcome screen
print("\n**********************************")
print("*** Sunflow Cryptobot Analyzer ***")
print("**********************************\n")
print(f"CONFIG FILE IN USE: {config_path}\n")

# Initialize variables
symbol                 = config.symbol
multiplier             = config.multiplier
dbase_file             = config.dbase_file
revenue_file           = config.revenue_file
compounding            = {}
compounding['enabled'] = config.compounding_enabled
compounding['start']   = config.compounding_start
compounding['now']     = config.compounding_start


# Load all buys
ticker   = preload.get_ticker(symbol)
spot     = ticker['lastPrice']
info     = preload.get_info(symbol, spot, multiplier, compounding)
all_buys = database.load(dbase_file, info)

# Load data into a dataframes
df_all_buys = pd.DataFrame(all_buys)
df_revenue  = pd.read_csv(revenue_file)

# Check if we can run
if df_all_buys.empty or df_revenue.empty:
    defs.announce("Not enough data available, no analysis possible")
    exit()

# Convert timestamps to readable dates
df_all_buys['createdTime'] = pd.to_datetime(df_all_buys['createdTime'], unit='ms')
df_all_buys['updatedTime'] = pd.to_datetime(df_all_buys['updatedTime'], unit='ms')
df_revenue['createdTime'] = pd.to_datetime(df_revenue['createdTime'], unit='ms')

# Filter the dataframes
df_all_buys = df_all_buys[df_all_buys['status'] == 'Closed']
df_revenue  = df_revenue[df_revenue['side'] == 'Sell'] 

# Get time elements
ab_elem = calc_time(df_all_buys)
rv_elem = calc_time(df_revenue)

# Get total wallet
equity_base  = orders.get_equity(info['baseCoin'])
equity_quote = orders.get_equity(info['quoteCoin'])

# Group the revenue data by date
df_revenue['date'] = df_revenue['createdTime'].dt.date

# Debug
if debug:
    print("df_all_buys: ")
    print(df_all_buys)
    print("df_revenue:")    
    print(df_revenue)
    print()
    pprint.pprint(ab_elem)
    pprint.pprint(rv_elem)
    print()

# Output to stdout
print("*** Sunflow Cryptobot Report ***\n")

print("Exchange data")
print("=============")
print(f"Base assets   : {defs.format_number(equity_base, info['basePrecision'])} {info['baseCoin']}")
print(f"Spot price    : {defs.format_number(spot, info['tickSize'])} {info['quoteCoin']}")
print(f"Total {info['baseCoin']}     : {defs.format_number(spot * equity_base, info['quotePrecision'])} {info['quoteCoin']} (spot price * assets)")
print(f"Total {info['quoteCoin']}    : {defs.format_number(equity_quote, info['quotePrecision'])} {info['quoteCoin']} (free to spend by bot)")
if compounding['enabled']:
    print(f"Start value   : {defs.format_number(compounding['start'], info['tickSize'])} {info['quoteCoin']} (when bot started)")
print(f"Total value   : {defs.format_number(spot * equity_base + equity_quote, info['quotePrecision'])} {info['quoteCoin']} (total bot value)")
if compounding['enabled']:
    print(f"Profit now    : {defs.format_number((spot * equity_base + equity_quote) - compounding['start'], info['tickSize'])} {info['quoteCoin']} (net present value)")

print()

print("Database data")
print("=============")
print(f"Order count   : {len(df_all_buys)} orders to sell")
print(f"First order   : {ab_elem['first']} UTC")
print(f"Last order    : {ab_elem['last']} UTC")
print(f"Timespan      : {ab_elem['days']} days, {ab_elem['hours']} hours, {ab_elem['minutes']} minutes, {ab_elem['seconds']} seconds")

print()

print(f"Base assets   : {defs.format_number(df_all_buys['cumExecQty'].sum(), info['basePrecision'])} {info['baseCoin']} (from database)")
print(f"Base assets   : {defs.format_number(equity_base, info['basePrecision'])} {info['baseCoin']} (from exchange)")
print(f"Difference    : {defs.format_number(equity_base - df_all_buys['cumExecQty'].sum(), info['basePrecision'])} {info['baseCoin']} (synchronization misses)")

print()

print(f"Average price : {defs.format_number(df_all_buys['avgPrice'].mean(), info['tickSize'])} {info['quoteCoin']}")
print(f"Minimum price : {defs.format_number(df_all_buys['avgPrice'].min(), info['tickSize'])} {info['quoteCoin']}")
print(f"Maximum price : {defs.format_number(df_all_buys['avgPrice'].max(), info['tickSize'])} {info['quoteCoin']}")

print()

print("Profit data")
print("===========")
print(f"Sell count    : {len(df_revenue)} orders sold")
print(f"First sell    : {rv_elem['first']} UTC")
print(f"Last sell     : {rv_elem['last']} UTC")
print(f"Timespan      : {rv_elem['days']} days, {rv_elem['hours']} hours, {rv_elem['minutes']} minutes, {rv_elem['seconds']} seconds")

print()

print(f"Average profit: {defs.format_number(df_revenue['revenue'].mean(), info['quotePrecision'])} {info['quoteCoin']} / trade")
print(f"Minimum profit: {defs.format_number(df_revenue['revenue'].min(), info['quotePrecision'])} {info['quoteCoin']} / trade")
print(f"Maximum profit: {defs.format_number(df_revenue['revenue'].max(), info['quotePrecision'])} {info['quoteCoin']} / trade")

print()

# Calculate the profit per day
total_time_diff = df_revenue['createdTime'].max() - df_revenue['createdTime'].min()
days_diff = total_time_diff.total_seconds() / (24 * 3600)
if days_diff > 0:
    avg_profit_per_day = df_revenue['revenue'].sum() / days_diff
    message_dp       = f"Daily profit  : {defs.format_number(avg_profit_per_day, info['quotePrecision'])} {info['quoteCoin']} / day"
    message_dp_graph = f"Daily profit: {defs.format_number(avg_profit_per_day, info['quotePrecision'])} {info['quoteCoin']}\n"
    print(message_dp)
else:
    message_dp       = "Daily profit  : N/A (Only one day of data)"
    message_dp_graph = "Daily profit  : N/A"
    print(message_dp)

# Calculate today's profit
today_date   = pd.Timestamp('now').normalize()
today_profit = df_revenue[df_revenue['createdTime'].dt.normalize() == today_date]['revenue'].sum()

# Output today's profit
print(f"Todays profit : {defs.format_number(today_profit, info['quotePrecision'])} {info['quoteCoin']} (today)")

# Output total profit
print(f"Trade profit  : {defs.format_number(df_revenue['revenue'].sum(), info['quotePrecision'])} {info['quoteCoin']} (alltime)")

print()

# Get the number of days from the argument
num_days = args.days

# Filter the df_revenue DataFrame to only include the last 'num_days' days
date_threshold = pd.Timestamp('now').normalize() - pd.Timedelta(days=num_days)
filtered_df_revenue = df_revenue[df_revenue['createdTime'] >= date_threshold]

# Group the filtered revenue data by date and calculate the total profit per day
profit_per_day = filtered_df_revenue.groupby('date')['revenue'].sum().reset_index()

# Create a figure and subplots
fig, axes = plt.subplots(2, 1, figsize=(14, 10))

# Add top left text
message = f"Quote assets : {defs.format_number(equity_base, info['basePrecision'])} {info['baseCoin']}\n"
message = message + f"Free to spend: {defs.format_number(equity_quote, info['quotePrecision'])} {info['quoteCoin']}\n"
message = message + f"Total value  : {defs.format_number(spot * equity_base + equity_quote, info['quotePrecision'])} {info['quoteCoin']}"
fig.text(0.01, 0.98, message, ha='left', va='top', fontsize=12, fontname='DejaVu Sans Mono')

# Add top right text
message = message_dp_graph
message = message + f"Todays profit: {defs.format_number(today_profit, info['quotePrecision'])} {info['quoteCoin']}\n"
message = message + f"Trade profit: {defs.format_number(df_revenue['revenue'].sum(), info['quotePrecision'])} {info['quoteCoin']}"
fig.text(0.99, 0.98, message, ha='right', va='top', fontsize=12, fontname='DejaVu Sans Mono')

# First subplot: Outstanding orders

# Bin the avgPrice into 20 bins
df_all_buys['price_bin'] = pd.cut(df_all_buys['avgPrice'], bins=20)

# Group by the bins and sum the cumExecQty for each bin
price_bins = df_all_buys.groupby('price_bin', observed=False)['cumExecValue'].sum().reset_index()

# Calculate the mid-point of each bin for labeling purposes
price_bins['bin_mid'] = price_bins['price_bin'].apply(lambda x: x.mid)

# Create an evenly spaced array for bar positions
x_positions = range(len(price_bins))

# Plotting the modified histogram with evenly spaced bars
axes[0].bar(x_positions, price_bins['cumExecValue'], width=0.9)  # Adjust width as needed

# Set the x-axis ticks to the custom positions with mid-point price values as labels
axes[0].set_xticks(x_positions)
axes[0].set_xticklabels([f'{defs.format_number(mid, info["tickSize"])}' for mid in price_bins['bin_mid']], rotation=45)

# Set title and labels
axes[0].set_title('Distribution of Outstanding Orders')
axes[0].set_xlabel('Average Price')
axes[0].set_ylabel(f'Total ({info["quoteCoin"]})')

# Second subplot: Profit per day
sns.lineplot(data=profit_per_day, x='date', y='revenue', marker='o', ax=axes[1])
axes[1].set_title('Profit per Day (Last {} Days)'.format(num_days))
axes[1].set_xlabel('Date')
axes[1].set_ylabel(f'Profit ({info["quoteCoin"]})')
axes[1].set_xticks(axes[1].get_xticks())  # Ensure xticks are set
axes[1].tick_params(axis='x', rotation=45)  # Rotate xticks

# Adjust layout to prevent overlap and give space for the text
plt.tight_layout(rect=[0, 0, 1, 0.96])

# Save the plot to the specified file
plt.savefig(config.data_suffix + "analysis.png")

# Show the plots
plt.show()
