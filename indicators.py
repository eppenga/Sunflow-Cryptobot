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
debug = True

# Calculcate indicators based on klines
def calculate(klines, spot):
    
    # Initialize variables
    indicators = {}
    df = pd.DataFrame(klines)
    
    if debug:
        print(defs.now_utc()[1] + "Indicators: calculate: Calculating indicators")
        start_time = int(time.time() * 1000)
        
    # Indicators: Calculate various Oscillators
    df['RSI']         = ta.rsi(df['close'], length=14)
    df['CCI']         = ta.cci(df['high'], df['low'], df['close'], length=20)
    df['AO']          = ta.ao(df['high'], df['low'], fast=5, slow=34)    
    df['Momentum']    = ta.mom(df['close'], length=10)
    df['WilliamsR']   = ta.willr(df['high'], df['low'], df['close'], length=14)
    #df['BullBear']
    df['UO']          = ta.uo(df['high'], df['low'], df['close'], fast=7, medium=14, slow=28)

    # Indicator: Stochastic %K Oscillator
    stoch_k           = {}
    stoch_k_result    = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3, smooth_k=3)
    stoch_k['k']      = stoch_k_result['STOCHk_14_3_3']
    stoch_k['d']      = stoch_k_result['STOCHd_14_3_3']

    # Indicator: MACD Lines Oscillator
    macd              = {}
    macd_result       = ta.macd(df['close'], fast=12, slow=26)
    macd['line']      = macd_result['MACD_12_26_9']
    macd['histogram'] = macd_result['MACDh_12_26_9']
    macd['signal']    = macd_result['MACDs_12_26_9']
    
    # Indicator: Stochastic RSI Fast Oscillator
    stoch_rsi         = {}
    stoch_rsi_result  = ta.stochrsi(df['close'], length=14, rsi_length=14, k=3, d=3)   
    stoch_rsi['k']    = stoch_rsi_result['STOCHRSIk_14_14_3_3']
    stoch_rsi['d']    = stoch_rsi_result['STOCHRSId_14_14_3_3']

    # Indicator: Average Directional Index Oscillator
    adx               = {}
    adx_result        = ta.adx(df['high'], df['low'], df['close'], length=14)
    adx['adx']        = adx_result['ADX_14']
    adx['dmp']        = adx_result['DMP_14']
    adx['dmn']        = adx_result['DMN_14']

    ## Indicators: Calculate various Moving Averages
    df['EMA10']       = ta.ema(df['close'], length=10)
    df['SMA10']       = ta.sma(df['close'], length=10)
    df['EMA20']       = ta.ema(df['close'], length=20)
    df['SMA20']       = ta.sma(df['close'], length=20)      
    df['EMA30']       = ta.ema(df['close'], length=30)
    df['SMA30']       = ta.sma(df['close'], length=30)
    df['EMA50']       = ta.ema(df['close'], length=50)
    df['SMA50']       = ta.sma(df['close'], length=50)
    df['EMA100']      = ta.ema(df['close'], length=100)
    df['SMA100']      = ta.sma(df['close'], length=100)
    df['EMA200']      = ta.ema(df['close'], length=200)
    df['SMA200']      = ta.sma(df['close'], length=200)
    df['VWMA']        = ta.vwma(df['close'], df['volume'], length=20)
    df['HMA']         = ta.hma(df['close'], length=9)

    ## Show DataFrame
    if debug:
        print("Combined Dataframes")
        print(df)
        print("MACD Dataframes")
        print(macd_result)
        print("Stochastic %K Dataframes")
        print(stoch_k_result)
        print("Stochastic RSI Fast Dataframes")
        print(stoch_rsi_result)
        print("Average Directional Index")
        print(adx_result)

    ## Determine advice per indicator

    # RSI Oscillator
    rsi = df['RSI'].iloc[-1]
    bsn = 'N'
    if rsi > 70:bsn = 'S'
    if rsi < 30:bsn = 'B'
    indicators['rsi'] = [rsi, bsn, 'O']

    # Stochastic %K Oscillator
    bsn = 'N'
    if stoch_k['k'].iloc[-1] < 20:
        if stoch_k['k'].iloc[-1] > stoch_k['d'].iloc[-1]: bsn = 'B'
    if stoch_k['k'].iloc[-1] > 80:
        if stoch_k['k'].iloc[-1] < stoch_k['d'].iloc[-1]: bsn = 'S'
    indicators['stochk'] = [stoch_k['k'].iloc[-1], bsn, 'O']

    # CCI Oscillator
    cci = df['CCI'].iloc[-1]
    bsn = 'N'
    if rsi < -100:bsn = 'S'
    if rsi > 100 :bsn = 'B'
    indicators['cci'] = [cci, bsn, 'O']
    
    # ADX Oscillator
    bsn = 'N'
    if adx['adx'].iloc[-1] > 25:
        if adx['dmp'].iloc[-1] > adx['dmn'].iloc[-1]: bsn = 'B'
        if adx['dmp'].iloc[-1] < adx['dmn'].iloc[-1]: bsn = 'S'
    indicators['adx'] = [adx['adx'].iloc[-1], bsn, 'O']

    # Awesome Oscillator
    ao = df['AO']
    bsn = 'N'
    if ao.iloc[-1] >= 0:
        if high_low(ao):bsn = 'B'
    if ao.iloc[-1] < 0:
        if high_low(ao, True):bsn = 'S'
    indicators['ao'] = [ao.iloc[-1], bsn, 'O']

    # Momentum Oscillator
    momentum = df['Momentum']
    bsn = 'N'
    if momentum.iloc[-1] >= 0:
        if high_low(momentum):bsn = 'B'
    if momentum.iloc[-1] < 0:
        if high_low(momentum, True):bsn = 'S'
    indicators['momentum'] = [momentum.iloc[-1], bsn, 'O']
    
    # MACD Oscillator
    bsn = 'N'
    if macd['histogram'].iloc[-1] >= 0:
        if high_low(macd['histogram']):bsn = 'B'
    if macd['histogram'].iloc[-1] < 0:
        if high_low(macd['histogram'], True): bsn = 'S'
    indicators['macd'] = [macd['histogram'].iloc[-1], bsn, 'O']

    # Stochastic RSI Fast Oscillator
    bsn = 'N'
    if stoch_rsi['k'].iloc[-1] < 20:
        if stoch_rsi['k'].iloc[-1] > stoch_rsi['d'].iloc[-1]: bsn = 'B'
    if stoch_rsi['k'].iloc[-1] > 80:
        if stoch_rsi['k'].iloc[-1] < stoch_rsi['d'].iloc[-1]: bsn = 'S'
    indicators['stochrsi'] = [stoch_rsi['k'].iloc[-1], bsn, 'O']

    # WilliamsR Oscillator
    williams_r = df['WilliamsR'].iloc[-1]
    bsn = 'N'
    if williams_r < 30:bsn = 'B'
    if williams_r > 70:bsn = 'S'
    indicators['williamsr'] = [williams_r, bsn, 'O']   

    # Ultimate Oscillator
    uo = df['UO'].iloc[-1]
    bsn = 'N'
    if uo < 30:bsn = 'B'
    if uo > 70:bsn = 'S'
    indicators['uo'] = [uo, bsn, 'O']

    # EMA and SMA Moving Averages
    ema10 = df['EMA10'].iloc[-1]
    sma10 = df['SMA10'].iloc[-1]
    ema20 = df['EMA20'].iloc[-1]
    sma20 = df['SMA20'].iloc[-1]
    ema30 = df['EMA30'].iloc[-1]
    sma30 = df['SMA30'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]
    sma50 = df['SMA50'].iloc[-1]
    ema100 = df['EMA100'].iloc[-1]
    sma100 = df['SMA100'].iloc[-1]
    ema200 = df['EMA200'].iloc[-1]
    sma200 = df['SMA200'].iloc[-1]    
    indicators['EMA10'] = [ema10, hesma(ema10, spot), 'A']
    indicators['SMA10'] = [sma10, hesma(sma10, spot), 'A']
    indicators['EMA20'] = [ema20, hesma(ema20, spot), 'A']
    indicators['SMA20'] = [sma20, hesma(sma20, spot), 'A']
    indicators['EMA30'] = [ema30, hesma(ema30, spot), 'A']
    indicators['SMA30'] = [sma30, hesma(sma30, spot), 'A']
    indicators['EMA50'] = [ema50, hesma(ema50, spot), 'A']
    indicators['SMA50'] = [sma50, hesma(sma50, spot), 'A']
    indicators['EMA100'] = [ema100, hesma(ema100, spot), 'A']
    indicators['SMA100'] = [sma100, hesma(sma100, spot), 'A']
    indicators['EMA200'] = [ema200, hesma(ema200, spot), 'A']
    indicators['SMA200'] = [sma200, hesma(sma200, spot), 'A']

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

# Check if the previous value was lower (default) or higher
def high_low(values, invert = False):
    
    # Initialize variables
    check = False
    
    # Get the last and single last value
    last_value  = values.iloc[-1]
    single_last = values.iloc[-2]
    
    # Compare the two
    if last_value >= single_last:
        check = True
        
    # Invert
    if invert:
        if single_last >= last_value:
            check = True
    
    # Return data
    return check

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
    