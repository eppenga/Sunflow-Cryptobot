# Sunflow Crypto Trading Bot
**Crypto Trading Bot to use on Bybit, high frequency and efficient resource handling. Uses websockets to trade in realtime featuring trailing buy and sell. Option to use an additional klines interval to work as confirmation for buy orders, or via orderbook analysis or technical analysis simular to TradingView. Both prevent over-buying when price goes down. Can also behave as a dynamic gribot to save on funds where spread distance and profit percentage are customizable.**

_Please note: Sunflow needs API Version 5 of the "unified trading account" of Bybit (basically, the newest version)._

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
- Log files for analyses

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
Configure by creating a config.py file from the config.py.txt file. Rename config.py.txt to config.py and use your favorite editor to modify.
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

## Disclaimer
I give no warranty and accept no responsibility or liability for the accuracy or the completeness of the information and materials contained in this project. Under no circumstances will I be held responsible or liable in any way for any claims, damages, losses, expenses, costs or liabilities whatsoever (including, without limitation, any direct or indirect damages for loss of profits, business interruption or loss of information) resulting from or arising directly or indirectly from your use of or inability to use this code or any code linked to it, or from your reliance on the information and material on this code, even if I have been advised of the possibility of such damages in advance.

So use it at your own risk!

_Dedicated to my daughter who has sunflower eyes_
