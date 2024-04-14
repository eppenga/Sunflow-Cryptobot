# Sunflow Crypto Trading Bot
**Crypto Trading Bot to use on Bybit, high frequency and efficient resource handling. Uses websockets to trade in realtime featuring trailing buy and sell. Option to use an additional klines interval to work as confirmation for buy orders or via technical analysis simular to TradingView. Both prevent over buying when price goes down. Can also behave as a dynamic gribot to save on funds, spread distance and profit percentage are customizable.**

## Features
- Trailing Buy and Sell
- Two intervals (default and confirmation)
- Automatically combines sell orders
- Technical Analysis (similar to TradingView)
- Can also work as gridbot
- Uses Bybit websockets
- Error handling including auto reconnect

![Buy confirmation with optional multiple intervals and technical analysis](https://github.com/eppenga/Sunflow-Cryptobot/assets/4440994/90184716-a793-4c1a-8907-4d746809c763)
_Sunflow stops buying before price goes down via multiple intervals and technical analysis confirmation._

### Datafolder
It automatically creates a data folder where it stores a database of all buy trades (in a human readable json format), errors and a log when a request was made to Bybit. 

### Disclaimer
I give no warranty and accepts no responsibility or liability for the accuracy or the completeness of the information and materials contained in this project. Under no circumstances will I be held responsible or liable in any way for any claims, damages, losses, expenses, costs or liabilities whatsoever (including, without limitation, any direct or indirect damages for loss of profits, business interruption or loss of information) resulting from or arising directly or indirectly from your use of or inability to use this code or any code linked to it, or from your reliance on the information and material on this code, even if I have been advised of the possibility of such damages in advance.

So use it at your own risk!

_Dedicated to my daughter who has sunflowers eyes_
