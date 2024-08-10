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
import argparse, importlib, sys

# Load internal libraries
import database, defs, orders, preload

# Parse command line arguments
parser = argparse.ArgumentParser(description="Run the Sunflow Cryptobot Tester with a specified config.")
parser.add_argument('-c', '--config', default='config.py', help='Specify the config file (with .py extension).')
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


### Analysis ###

# Display welcome screen
print("\n**********************************")
print("*** Sunflow Cryptobot Analyzer ***")
print("**********************************\n")
print(f"CONFIG FILE IN USE: {config_path}\n")

# Initialize variables
symbol       = config.symbol
multiplier   = config.multiplier
dbase_file   = config.dbase_file
revenue_file = config.revenue_file 

# Load all buys
ticker   = preload.get_ticker(symbol)
spot     = ticker['lastPrice']
info     = preload.get_info(symbol, spot, multiplier)
all_buys = database.load(dbase_file, info)

# Load data into a dataframes
df_all_buys = pd.DataFrame(all_buys)
df_revenue  = pd.read_csv(revenue_file)

# Convert timestamps to readable dates
df_all_buys['createdTime'] = pd.to_datetime(df_all_buys['createdTime'], unit='ms')
df_all_buys['updatedTime'] = pd.to_datetime(df_all_buys['updatedTime'], unit='ms')
df_revenue['createdTime'] = pd.to_datetime(df_revenue['createdTime'], unit='ms')

# Filter the all buys dataframe for status = 'Closed'
df_all_buys = df_all_buys[df_all_buys['status'] == 'Closed']

# Calculate oldest and latest order times
oldest_order = df_all_buys['createdTime'].min().strftime('%Y-%m-%d %H:%M:%S')
latest_order = df_all_buys['createdTime'].max().strftime('%Y-%m-%d %H:%M:%S')

# Calculate duration
start_date = df_revenue['createdTime'].min()
end_date = df_revenue['createdTime'].max()
duration = end_date - start_date

# Calculate days, hours, minutes, and seconds
days = duration.days
seconds = duration.seconds
hours = seconds // 3600
minutes = (seconds % 3600) // 60
seconds = seconds % 60

# Get total wallet
equity = orders.get_equity(info)

# Group the revenue data by date and calculate the total profit per day
df_revenue['date'] = df_revenue['createdTime'].dt.date
profit_per_day = df_revenue.groupby('date')['revenue'].sum().reset_index()

# Output to stdout
print("Equity data")
print("===========")
print(f"Used by bot   : {defs.format_number(equity, info['basePrecision'])} {info['baseCoin']}")
print(f"Spot price    : {spot} {info['quoteCoin']}")
print(f"Total value   : {defs.format_number(spot * equity, info['quotePrecision'])} {info['quoteCoin']}")

print()

print("Order data")
print("==========")
print(f"Order count   : {len(df_all_buys)}")
print(f"Oldest order  : {oldest_order}")
print(f"Newest order  : {latest_order}")
print(f"Total in base : {defs.format_number(df_all_buys['cumExecValue'].sum(), info['quotePrecision'])} {info['quoteCoin']}")
print(f"Total in quote: {defs.format_number(df_all_buys['cumExecQty'].sum(), info['basePrecision'])} {info['baseCoin']}")
print()
print(f"Average price : {defs.format_number(df_all_buys['avgPrice'].mean(), info['quotePrecision'])} {info['quoteCoin']}")
print(f"Minimum price : {defs.format_number(df_all_buys['avgPrice'].min(), info['quotePrecision'])} {info['quoteCoin']}")
print(f"Maximum price : {defs.format_number(df_all_buys['avgPrice'].max(), info['quotePrecision'])} {info['quoteCoin']}")

print()

print("Profit data")
print("===========")
print(f"Profit lines  : {len(df_revenue)}")
print(f"Total profit  : {defs.format_number(df_revenue['revenue'].sum(), info['quotePrecision'])} {info['quoteCoin']}")
print(f"Start date    : {df_revenue['createdTime'].min().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"End date      : {df_revenue['createdTime'].max().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Uptime        : {days} days, {hours} hours, {minutes} minutes, {seconds} seconds")

print()
print(f"Average profit: {defs.format_number(df_revenue['revenue'].mean(), info['quotePrecision'])} {info['quoteCoin']} / trade")
print(f"Minimum profit: {defs.format_number(df_revenue['revenue'].min(), info['quotePrecision'])} {info['quoteCoin']} / trade")
print(f"Maximum profit: {defs.format_number(df_revenue['revenue'].max(), info['quotePrecision'])} {info['quoteCoin']} / trade")

# Calculate the number of days between the start and end dates
days_diff = (df_revenue['createdTime'].max() - df_revenue['createdTime'].min()).days
if days_diff > 0:
    avg_profit_per_day = df_revenue['revenue'].sum() / days_diff
    print(f"Average profit: {defs.format_number(avg_profit_per_day, info['quotePrecision'])} {info['quoteCoin']} / day")
else:
    print("Average profit: N/A (Only one day of data)")
print()

# Create a figure with two subplots
plt.figure(figsize=(14, 10))

# First subplot: Histogram of average prices
plt.subplot(2, 1, 1)
sns.histplot(df_all_buys['avgPrice'], bins=20, kde=False)
plt.title('Distribution of Outstanding Orders')
plt.xlabel('Average Price')
plt.ylabel('Frequency')

# Second subplot: Profit per day
plt.subplot(2, 1, 2)
sns.lineplot(data=profit_per_day, x='date', y='revenue', marker='o')
plt.title('Profit per Day')
plt.xlabel('Date')
plt.ylabel(f'Profit ({info["quoteCoin"]})')
plt.xticks(rotation=45)

# Adjust layout to prevent overlap
plt.tight_layout()

# Show the plots
plt.show()
