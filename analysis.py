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
equity_base  = orders.get_equity(info['baseCoin'])
equity_quote = orders.get_equity(info['quoteCoin'])

# Group the revenue data by date and calculate the total profit per day
df_revenue['date'] = df_revenue['createdTime'].dt.date
profit_per_day = df_revenue.groupby('date')['revenue'].sum().reset_index()

# Output to stdout
print("*** Sunflow Cryptobot Report ***\n")

print("Exchange data")
print("=============")
print(f"Base assets   : {defs.format_number(equity_base, info['basePrecision'])} {info['baseCoin']}")
print(f"Spot price    : {defs.format_number(spot, info['tickSize'])} {info['quoteCoin']}")

print()

print(f"Base value    : {defs.format_number(spot * equity_base, info['quotePrecision'])} {info['quoteCoin']} (spot * base)")
print(f"Quote value   : {defs.format_number(equity_quote, info['quotePrecision'])} {info['quoteCoin']} (free to spend by bot)")
print(f"Total value   : {defs.format_number(spot * equity_base + equity_quote, info['quotePrecision'])} {info['quoteCoin']} (total bot value)")

print()

print("Database data")
print("=============")
print(f"Order count   : {len(df_all_buys)} orders to sell")
print(f"Oldest order  : {oldest_order} UTC")
print(f"Newest order  : {latest_order} UTC")

print()

print(f"Base assets   : {defs.format_number(df_all_buys['cumExecQty'].sum(), info['basePrecision'])} {info['baseCoin']} (from database)")
print(f"Base assets   : {defs.format_number(equity_base, info['basePrecision'])} {info['baseCoin']} (from exchange)")
print(f"Difference    : {defs.format_number(equity_base - df_all_buys['cumExecQty'].sum(), info['basePrecision'])} {info['baseCoin']} (synchronization misses)")

print()

print(f"Base value    : {defs.format_number(df_all_buys['cumExecValue'].sum(), info['quotePrecision'])} {info['quoteCoin']} (from database, buy value)")
print(f"Base value    : {defs.format_number(spot * equity_base, info['quotePrecision'])} {info['quoteCoin']} (from exchange, present value)")
print(f"Difference    : {defs.format_number(df_all_buys['cumExecValue'].sum() - spot * equity_base, info['basePrecision'])} {info['quoteCoin']} (between buy value and present value)")
print(f"Break even    : {defs.format_number(df_all_buys['cumExecValue'].sum() / df_all_buys['cumExecQty'].sum(), info['tickSize'])} {info['quoteCoin']} (equal to present value)")

print()

print(f"Average price : {defs.format_number(df_all_buys['avgPrice'].mean(), info['tickSize'])} {info['quoteCoin']}")
print(f"Minimum price : {defs.format_number(df_all_buys['avgPrice'].min(), info['tickSize'])} {info['quoteCoin']}")
print(f"Maximum price : {defs.format_number(df_all_buys['avgPrice'].max(), info['tickSize'])} {info['quoteCoin']}")

print()

print("Profit data")
print("===========")
print(f"Profit lines  : {len(df_revenue)} profit lines")
print(f"Start date    : {df_revenue['createdTime'].min().strftime('%Y-%m-%d %H:%M:%S')} UTC")
print(f"End date      : {df_revenue['createdTime'].max().strftime('%Y-%m-%d %H:%M:%S')} UTC")
print(f"Uptime        : {days} days, {hours} hours, {minutes} minutes, {seconds} seconds")

print()
print(f"Average profit: {defs.format_number(df_revenue['revenue'].mean(), info['quotePrecision'])} {info['quoteCoin']} / trade")
print(f"Minimum profit: {defs.format_number(df_revenue['revenue'].min(), info['quotePrecision'])} {info['quoteCoin']} / trade")
print(f"Maximum profit: {defs.format_number(df_revenue['revenue'].max(), info['quotePrecision'])} {info['quoteCoin']} / trade")

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

print(f"Total profit  : {defs.format_number(df_revenue['revenue'].sum(), info['quotePrecision'])} {info['quoteCoin']}")

print()

# Create a figure and subplots
fig, axes = plt.subplots(2, 1, figsize=(14, 10))

# Add top left text
message = f"Free to spend: {defs.format_number(equity_quote, info['quotePrecision'])} {info['quoteCoin']}\n"
message = message + f"Total value  : {defs.format_number(spot * equity_base + equity_quote, info['quotePrecision'])} {info['quoteCoin']}"
fig.text(0.01, 0.98, message, ha='left', va='top', fontsize=12, fontname='DejaVu Sans Mono')

# Add top right text
message = message_dp_graph
message = message + f"Total profit: {defs.format_number(df_revenue['revenue'].sum(), info['quotePrecision'])} {info['quoteCoin']}"
fig.text(0.99, 0.98, message, ha='right', va='top', fontsize=12, fontname='DejaVu Sans Mono')

# First subplot: Histogram of average prices
sns.histplot(df_all_buys['avgPrice'], bins=20, kde=False, ax=axes[0])
axes[0].set_title('Distribution of Outstanding Orders')
axes[0].set_xlabel('Average Price')
axes[0].set_ylabel('Frequency')

# Second subplot: Profit per day
sns.lineplot(data=profit_per_day, x='date', y='revenue', marker='o', ax=axes[1])
axes[1].set_title('Profit per Day')
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