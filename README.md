# Sunflow Crypto Trading Bot
**Crypto Trading Bot to use on Bybit, high frequency and efficient resource handling. Uses websockets to trade in realtime featuring trailing buy and sell. Option to use an additional klines interval to work as confirmation for buy orders, or via orderbook analysis or technical analysis simular to TradingView. Both prevent over-buying when price goes down. Can also behave as a dynamic gribot to save on funds where spread distance and profit percentage are customizable.**

_Please note: Sunflow needs API Version 5 of the "unified trading account" of Bybit, and is tested on Ubuntu Server 24.04 LTS@AWS._

## Features
- Trailing Buy and Sell
- Flexible Trigger Distance (multiple methods)
- Three intervals (default and two confirmation)
- Automatically combines sell orders
- Orderbook as buy confirmation
- Technical Analysis (similar to TradingView)
- Can also work as gridbot
- Load custom config via CLI
- Uses Bybit websockets
- Telegram reporting
- Error handling including auto reconnect
- Log files for analysis
- Experimental analyzer

![Buy confirmation with optional multiple intervals and technical analysis](https://github.com/eppenga/Sunflow-Cryptobot/assets/4440994/90184716-a793-4c1a-8907-4d746809c763)
_Sunflow stops buying before price goes down via multiple intervals and technical analysis confirmation._

### Datafolder and reporting
It automatically creates a data folder where it stores a database of all buy trades (in a human readable json format), errors, revenue and a log file when a request was made to Bybit for offline analysis. Sunflow outputs price changes, buys, sells, trailing changes and other relevant messages to screen or via Telegram. Debug mode increases reporting.

## Install, configure and run

### Install dependancies
Use pip and requirements.txt file to install dependancies.
```
pip install -r requirements.txt
```

### Configure
Configure by creating a config.py file from the config.py.txt file. Rename config.py.txt to config.py and use your favorite editor to modify. The Github wiki has a few hints on what all parameters mean, but documentation isn't ready yet.
```
mv config.py.txt config.py
nano config.py
```

### Run
```
python sunflow.py
```

### Run multiple symbols
If you want to run multiple symbols, create a custom config file per symbol (including full custom settings if you wish) and run every instance of Sunflow in a seperate terminal, there is no need to install Sunflow multiple times. Data files are created with the name of the config file to keep everything seperated. By doing so, you can even run multiple bots of the same symbol via one API key, handy for testing. 
```
python sunflow.py -c {optional path/}config1.py
python sunflow.py -c {optional path/}config2.py
...
```

![Sunflow easily running with four symbols on a Raspberry Pi 4](https://github.com/eppenga/Sunflow-Cryptobot/assets/4440994/cebd15e1-0190-4a49-8aa9-c555884274d4)
_Sunflow easily running with four symbols on a Raspberry Pi 4, hardware requirements are minimal_

### Revenue log file
When the revenue log file is enabled (please see revenue_log in the config file) Sunflow will create a log file of all closed buy and sell orders for further analyses. If you set 'revenue_log_extend' to False it will create an CSV file easy for automated reporting, you can also only include the sell orders for easy profit calculation by setting revenue_log_sides to True. The format of the log file is: createdTime, orderId, side, symbol, baseCoin, quoteCoin, orderType, orderStatus, avgPrice, qty, trigger_ini, triggerPrice, cumExecFee, cumExecQty, cumExecValue, revenue.

### Experimental analyzer
For automated analysis there is an experimental functionality which can be run simular to sunflow. To use it you have to install additionally the python packages matplotlib and seaborn. Run it as shown below (data below is dummy data).
```
python analysis.py
python sunflow.py -c {optional path/}your-config.py
```

```
*** Sunflow Cryptobot Report ***

Exchange data
=============
Base assets   : 1086.71 XRP
Spot price    : 0.5831 USDC
Base value    : 633.660601 USDC

Base value    : 633.660601 USDC (spot * base)
Quote value   : 361.527528 USDC (free to spend)
Total value   : 995.188129 USDC (total bot value)

Database data
=============
Order count   : 371 orders to sell
Oldest order  : 2024-08-08 19:12:10 UTC
Newest order  : 2024-08-13 17:50:26 UTC

Base assets   : 1083.52 XRP (from database)
Base assets   : 1086.71 XRP (from exchange)
Difference    : 3.19 XRP (synchronization misses)

Base value    : 660.150646 USDC (from database)
Break even    : 0.6093 USDC (based on database)

Average price : 0.6093 USDC
Minimum price : 0.5820 USDC
Maximum price : 0.6411 USDC

Profit data
===========
Profit lines  : 818 profit lines
Start date    : 2024-08-08 16:03:28 UTC
End date      : 2024-08-13 17:54:56 UTC
Uptime        : 5 days, 1 hours, 51 minutes, 27 seconds

Average profit: 0.029504 USDC / trade
Minimum profit: -0.000876 USDC / trade
Maximum profit: 1.470700 USDC / trade
Daily profit  : 4.753309 USDC / day
Total profit  : 24.134478 USDC
```

![XRPUSDC_analysis](https://github.com/user-attachments/assets/0829a1e8-c6bb-4c5b-a174-72ec5c63b62f)
_Experimental analyzer including graphical representation and reporting_


## Disclaimer
I give no warranty and accept no responsibility or liability for the accuracy or the completeness of the information and materials contained in this project. Under no circumstances will I be held responsible or liable in any way for any claims, damages, losses, expenses, costs or liabilities whatsoever (including, without limitation, any direct or indirect damages for loss of profits, business interruption or loss of information) resulting from or arising directly or indirectly from your use of or inability to use this code or any code linked to it, or from your reliance on the information and material on this code, even if I have been advised of the possibility of such damages in advance.

So use it at your own risk!

## Thank you
You using my application is a thank you in itself and hopefully I helped you also by giving you this code. If you like to thank me personally, for all the countless hours I put into this project, please buy me a coffee!

<a href="https://www.buymeacoffee.com/eppenga" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

_Dedicated to my daughter who has sunflower eyes_
