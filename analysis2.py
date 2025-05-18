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

# Debug
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

# Get wallet for base and quote coin
equity_base  = orders.equity_safe(orders.get_wallet(info['baseCoin'])['result']['balance'])
equity_quote = orders.equity_safe(orders.get_wallet(info['quoteCoin'])['result']['balance'])

# Group the revenue data by date
df_revenue['date'] = df_revenue['createdTime'].dt.date

# Debug to stdout
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

# Group the filtered revenue and trade data by date 
profit_per_day = filtered_df_revenue.groupby('date')['revenue'].sum().reset_index()
basecoin_sold_per_day = df_revenue.groupby('date')['qty'].sum().reset_index(name='trade_count')

# Add price bins for outstanding orders histogram
df_all_buys['price_bin'] = pd.cut(df_all_buys['avgPrice'], bins=20)
price_bins = df_all_buys.groupby('price_bin', observed=False)['cumExecValue'].sum().reset_index()
price_bins['bin_mid'] = price_bins['price_bin'].apply(lambda x: x.mid)

# Combine profit per day and trade counts for combined graph
combined_df = pd.merge(profit_per_day, basecoin_sold_per_day, on='date', how='inner')

# Calculate average profit per trade
combined_df['avg_profit_per_trade'] = combined_df['revenue'] / combined_df['trade_count']

# Create the plots
fig, axes = plt.subplots(2, 1, figsize=(14, 12))

# Top Graph: Distribution of Outstanding Orders
axes[0].bar(range(len(price_bins)), price_bins['cumExecValue'], width=0.9)
axes[0].set_xticks(range(len(price_bins)))
axes[0].set_xticklabels([f'{defs.format_number(mid, info["tickSize"])}' for mid in price_bins['bin_mid']], rotation=45)
axes[0].set_title('Distribution of Outstanding Orders')
axes[0].set_xlabel('Average Price')
axes[0].set_ylabel(f'Total ({info["quoteCoin"]})')

# Combined Graph: Profit and Number of Trades Per Day
ax1 = axes[1]
color_profit = 'tab:blue'
ax1.set_xlabel('Date')
ax1.set_ylabel(f'Profit ({info["quoteCoin"]})', color=color_profit)
ax1.plot(combined_df['date'], combined_df['revenue'], marker='o', color=color_profit, label='Profit')
ax1.tick_params(axis='y', labelcolor=color_profit)
ax1.tick_params(axis='x', rotation=45)

# Add the bar chart for trade counts on a second y-axis
ax2 = ax1.twinx()
color_trades = 'tab:green'
ax2.set_ylabel(f'{info["baseCoin"]} sold (profit per 1 {info["baseCoin"]} sold)', color=color_trades)
bars = ax2.bar(combined_df['date'], combined_df['trade_count'], color=color_trades, alpha=0.6, label='Trades')
ax2.tick_params(axis='y', labelcolor=color_trades)

# Annotate average profit per trade on top of the bars
for bar, avg_profit in zip(bars, combined_df['avg_profit_per_trade']):
    ax2.text(
        bar.get_x() + bar.get_width() / 2,  # Center the text horizontally
        bar.get_height(),  # Place the text at the top of the bar
        f'({defs.format_number(avg_profit, info["quotePrecision"])})',  # Format the average profit
        ha='center', va='bottom', fontsize=10, color='black'
    )

plt.title('Profit and Number of Trades Per Day')
fig.tight_layout()

# Show all plots
plt.show()
