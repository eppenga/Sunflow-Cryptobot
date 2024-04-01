### Sunflow Cryptobot ###
#
# Calculate technical indicators

# Load external libraries
import time
import pandas as pd
import pandas_ta as ta

# Load internal libraries
import defs

# Initialize variables
debug = False

# Calculcate indicators based on klines
def calculate(klines, spot):
    
    # Initialize variables
    indicators = {}
    df = pd.DataFrame(klines)
    
    if debug:
        print(defs.now_utc()[1] + "Indicators: calculate: Calculating indicators")
        start_time = int(time.time() * 1000)
        
    ## Indicators: Calculate Oscillators
    df['RSI']      = ta.rsi(df['close'], length=14)
    #df['Stoch_K']
    df['CCI']      = ta.cci(df['high'], df['low'], df['close'], length=20)
    #df['ADX]
    df['AO']       = ta.ao(df['high'], df['low'], fast=5, slow=34)    
    df['Momentum'] = ta.mom(df['close'], length=10)
    #df['MACD']
    #df['Stoch_RSI]
    #df['William']
    #df['BullBear']
    #df['UO']

    ## Indicators: Calculate Moving Averages
    df['EMA10']    = ta.ema(df['close'], length=10)
    df['SMA10']    = ta.sma(df['close'], length=10)
    df['EMA20']    = ta.ema(df['close'], length=20)
    df['SMA20']    = ta.sma(df['close'], length=20)      
    df['EMA30']    = ta.ema(df['close'], length=30)
    df['SMA30']    = ta.sma(df['close'], length=30)
    df['EMA50']    = ta.ema(df['close'], length=50)
    df['SMA50']    = ta.sma(df['close'], length=50)
    df['VWMA']     = ta.vwma(df['close'], df['volume'], length=20)
    df['HMA']      = ta.hma(df['close'], length=9)

    ## Indicators: High Low
    #df['hilo']     = ta.hilo(df[])

    ## Show DataFrame
    if debug:print(df)

    ## Determine advice per indicator

    # Indicator RSI
    rsi = df['RSI'].iloc[-1]
    bsn = 'N'
    if rsi > 70:bsn = 'S'
    if rsi < 30:bsn = 'B'
    indicators['rsi'] = [rsi, bsn, 'O']

    # Indicator CCI
    cci = df['CCI'].iloc[-1]
    bsn = 'N'
    if rsi < -100:bsn = 'S'
    if rsi > 100 :bsn = 'B'
    indicators['cci'] = [cci, bsn, 'O']    
   
    # Indicators for EMA and SMA
    ema10 = df['EMA10'].iloc[-1]
    sma10 = df['SMA10'].iloc[-1]
    ema20 = df['EMA20'].iloc[-1]
    sma20 = df['SMA20'].iloc[-1]
    ema30 = df['EMA30'].iloc[-1]
    sma30 = df['SMA30'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]
    sma50 = df['SMA50'].iloc[-1]
    indicators['EMA10'] = [ema10, hesma(ema10, spot), 'A']
    indicators['SMA10'] = [sma10, hesma(sma10, spot), 'A']
    indicators['EMA20'] = [ema20, hesma(ema20, spot), 'A']
    indicators['SMA20'] = [sma20, hesma(sma20, spot), 'A']
    indicators['EMA30'] = [ema30, hesma(ema30, spot), 'A']
    indicators['SMA30'] = [sma30, hesma(sma30, spot), 'A']
    indicators['EMA50'] = [ema50, hesma(ema50, spot), 'A']
    indicators['SMA50'] = [sma50, hesma(sma50, spot), 'A']

    # Output to stdout
    if debug:
        print(defs.now_utc()[1] + "Indicators: calculate: Advice calculated:")
        print(indicators)
        end_time = int(time.time() * 1000)
        print(defs.now_utc()[1] + "Pandas_ta spent " + (str(end_time - start_time)) + " ms calculating indicators and advice\n")
    
    # Return technicals
    return indicators

# Get an advice for SMA, EMA and HULL
def hesma(hesma, spot):

    # Determine advice
    bsn = 'N'
    if hesma < spot:bsn = 'B'
    if hesma > spot:bsn = 'S'
   
    # Return bsn advice
    return bsn

# Calculate value of technical
def technicals_value(count, countB, countS):

    # Initialize variables
    strength = 0

    # Determine strength
    if countB > countS:
        strength = countB / count
    else:
        strength = -countS / count

    # Return strength
    return strength

# Convert value of technical in to advice
def technicals_advice(strength):
  
  # Initialize variables
  advice = "Neutral"
  
  # Determine advice  
  if strength > 0.5                     : advice = "Strong buy"
  if strength > 0.1 and strength <= 0.5 : advice = "Buy"
  if strength < -0.5                    : advice = "Strong sell"
  if strength < 0.1 and strength >= -0.5: advice = "Sell"
  
  # Return advice 
  return advice

# Caculate advice based on indicators
def advice(indicators):

    # Count the Buys, Sells and Neutrals
    countA  = 0;   # Moving Averages
    countAN = 0;   # Moving Averages Neutral
    countAB = 0;   # Moving Averages Buy
    countAS = 0;   # Moving Averages Sell
    countO  = 0;   # Oscillators
    countON = 0;   # Oscillators Neutral
    countOB = 0;   # Oscillators Buy
    countOS = 0;   # Oscillators Sell

    # Iterate through the data
    for technicality, indicatorData in indicators.items():
        # Check the conditions and increment counters accordingly
        if indicatorData[1] == 'B':
            if indicatorData[2] == 'O':
                countOB += 1
            else:  # Assuming 'A'
                countAB += 1
        elif indicatorData[1] == 'S':
            if indicatorData[2] == 'O':
                countOS += 1
            else:  # Assuming 'A'
                countAS += 1
        elif indicatorData[1] == 'N':
            if indicatorData[2] == 'O':
                countON += 1
            else:  # Assuming 'A'
                countAN += 1

    # Calculate the advice
    countA = countAN + countAB + countAS;                 # Moving Averages
    countO = countON + countOB + countOS;                 # Oscillators
    count  = countA + countO;                             # All
    countB = countAB + countOB;                           # Total Buys
    countS = countAS + countOS;                           # Total Sells
    countN = countAN + countON;                           # Total Neutrals

    # Calculate strengths
    strengthA = technicals_value(countA, countAB, countAS)        # Moving Averages
    strengthO = technicals_value(countO, countOB, countOS)        # Oscillators
    strength  = technicals_value(count, countB, countS)           # All

    # Get all advices
    advice  = technicals_advice(strength);                   # Total advice
    adviceA = technicals_advice(strengthA);                  # Moving Average advice
    adviceO = technicals_advice(strengthO);                  # Oscillator advice

    if debug:
        print(defs.now_utc()[1] + "Indicators: advice: Technical Indicator Advice")
        print("Moving Averages BUY      : " + str(countAB))
        print("Moving Averages NEUTRAL  : " + str(countAN))
        print("Moving Averages SELL     : " + str(countAS))
        print("Moving Averages          : " + str(countA))
        print("Moving Averages Strength : " + str(strengthA))
        print("Moving Averages Advice   : " + str(adviceA) + "\n")

        print("Oscillators BUY          : " + str(countOB))
        print("Oscillators NEUTRAL      : " + str(countON))
        print("Oscillators SELL         : " + str(countOS))
        print("Oscillators              : " + str(countO))
        print("Oscillators Strength     : " + str(strengthO))
        print("Oscillators Advice       : " + str(adviceO) + "\n")

        print("Total Indicators BUY     : " + str(countB))
        print("Total Indicators NEUTRAL : " + str(countN))
        print("Total Indicators SELL    : " + str(countS))
        print("Total Indicators         : " + str(count))
        print("Total Indicators Strength: " + str(strength))
        print("Total Indicators Advice  : " + str(advice) + "\n")

    return strength, advice
    