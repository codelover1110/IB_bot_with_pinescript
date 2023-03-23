from ib_insync import *
import math
import ta
from ta.utils import *
import time

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=16, timeout=0)

mnq_fut_contract = Future('MNQ', '202306', 'CME')

def strategy_entry():
    bars = ib.reqHistoricalData(
        mnq_fut_contract,
        endDateTime='',
        durationStr='900 S',
        barSizeSetting='1 secs',
        whatToShow='TRADES',
        useRTH=False,
        formatDate=1)

    # Create a Pandas dataframe from the historical data
    df = util.df(bars)

    # Calculate Heikin Ashi Open, High, Low, and Close
    df['HA_Close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    df['HA_Open'] = (df['open'].shift(1) + df['close'].shift(1)) / 2
    df['HA_High'] = df[['high', 'HA_Open', 'HA_Close']].max(axis=1)
    df['HA_Low'] = df[['low', 'HA_Open', 'HA_Close']].min(axis=1)

    # Display the Heikin Ashi data
    df = df.set_index(pd.to_datetime(df['date'])).drop(['date'], axis=1)

    # Params
    stoploss = 0.002
    takeprofit = 0.002

    # RWI params
    length = 12
    threshold = 3

    df['ema9'] = df['HA_Close'].ewm(span=9, adjust=False).mean()
    df['wma30'] = df['HA_Close'].rolling(window=30).apply(lambda x: (x * range(1,31)).sum() / sum(range(1,31)))


    # Define the RWI function
    def rwi(df, length, threshold):
        def calc30(x):
            return pd.Series(x).rolling(window=30).apply(lambda x: (x * range(1,31)).sum() / sum(range(1,31)))
        den = calc30(df['HA_Close'] * math.sqrt(length))
        rwi_high = calc30(df['HA_High'] - df['HA_Low'].shift(length).fillna(method='bfill')) / den
        rwi_low = calc30(df['HA_High'].shift(length).fillna(method='bfill') - df['HA_Low']) / den
        is_rw = (rwi_high < threshold) & (rwi_low < threshold)
        return pd.DataFrame({'is_rw': is_rw, 'rwi_high': rwi_high, 'rwi_low': rwi_low}, index=df.index)

    [is_rw, rwi_high, rwi_low] = rwi(df, length, threshold)

    candleRed = df['HA_Open'].iloc[-1] > df['HA_Close'].iloc[-1]
    candleGreen = df['HA_Open'].iloc[-1] < df['HA_Close'].iloc[-1]

    if candleRed:
        ib.placeOrder(mnq_fut_contract, MarketOrder('BUY', 1))
    elif candleGreen:
        # request market data to get the current price
        ticker = ib.reqTickers(mnq_fut_contract)[0]
        current_price = ticker.marketPrice()

        # calculate the prices for the stop loss and take profit orders
        stop_loss_price = round(current_price * (1 - 0.002), 2)
        take_profit_price = round(current_price * (1 + 0.002), 2)

        # calculate the price for the limit order, taking into account the minimum price variation
        price = round(current_price - (0.25 * round((current_price - 1) / 0.25)), 2)

        # place the limit order with the stop loss and take profit
        order = LimitOrder('BUY', 1, price)
        order.transmit = False
        ib.placeOrder(mnq_fut_contract, order)

        # place the stop loss order
        stop_loss_order = StopOrder('SELL', 1, stop_loss_price)
        stop_loss_order.transmit = False
        ib.placeOrder(mnq_fut_contract, stop_loss_order)

        # place the take profit order
        take_profit_order = LimitOrder('SELL', 1, take_profit_price)
        take_profit_order.transmit = True
        ib.placeOrder(mnq_fut_contract, take_profit_order)
        ib.placeOrder(mnq_fut_contract, LimitOrder('BUY', 1, df['HA_Close'].iloc[-1] * (1 + takeprofit)))

def strategy_exit():
    bars = ib.reqHistoricalData(
        mnq_fut_contract,
        endDateTime='',
        durationStr='900 S',
        barSizeSetting='1 secs',
        whatToShow='TRADES',
        useRTH=False,
        formatDate=1)

    # Create a Pandas dataframe from the historical data
    df = util.df(bars)

    # Calculate Heikin Ashi Open, High, Low, and Close
    df['HA_Close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    df['HA_Open'] = (df['open'].shift(1) + df['close'].shift(1)) / 2
    df['HA_High'] = df[['high', 'HA_Open', 'HA_Close']].max(axis=1)
    df['HA_Low'] = df[['low', 'HA_Open', 'HA_Close']].min(axis=1)

    # Display the Heikin Ashi data
    df = df.set_index(pd.to_datetime(df['date'])).drop(['date'], axis=1)

    # Params
    stoploss = 0.002
    takeprofit = 0.002

    # RWI params
    length = 12
    threshold = 3

    df['ema9'] = df['HA_Close'].ewm(span=9, adjust=False).mean()
    df['wma30'] = df['HA_Close'].rolling(window=30).apply(lambda x: (x * range(1,31)).sum() / sum(range(1,31)))


    # Define the RWI function
    def rwi(df, length, threshold):
        def calc30(x):
            return pd.Series(x).rolling(window=30).apply(lambda x: (x * range(1,31)).sum() / sum(range(1,31)))
        den = calc30(df['HA_Close'] * math.sqrt(length))
        rwi_high = calc30(df['HA_High'] - df['HA_Low'].shift(length).fillna(method='bfill')) / den
        rwi_low = calc30(df['HA_High'].shift(length).fillna(method='bfill') - df['HA_Low']) / den
        is_rw = (rwi_high < threshold) & (rwi_low < threshold)
        return pd.DataFrame({'is_rw': is_rw, 'rwi_high': rwi_high, 'rwi_low': rwi_low}, index=df.index)

    [is_rw, rwi_high, rwi_low] = rwi(df, length, threshold)

    candleRed = df['HA_Open'].iloc[-1] > df['HA_Close'].iloc[-1]
    candleGreen = df['HA_Open'].iloc[-1] < df['HA_Close'].iloc[-1]

    if candleRed:
        ib.placeOrder(mnq_fut_contract, MarketOrder('SELL', 1))
    elif candleGreen:
         # request market data to get the current price
        ticker = ib.reqTickers(mnq_fut_contract)[0]
        current_price = ticker.marketPrice()

        # calculate the prices for the stop loss and take profit orders
        stop_loss_price = round(current_price * (1 - 0.002), 2)
        take_profit_price = round(current_price * (1 + 0.002), 2)

        # calculate the price for the limit order, taking into account the minimum price variation
        price = round(current_price - (0.25 * round((current_price - 1) / 0.25)), 2)

        # place the limit order with the stop loss and take profit
        order = LimitOrder('BUY', 1, price)
        order.transmit = False
        ib.placeOrder(mnq_fut_contract, order)

        # place the stop loss order
        stop_loss_order = StopOrder('SELL', 1, stop_loss_price)
        stop_loss_order.transmit = False
        ib.placeOrder(mnq_fut_contract, stop_loss_order)

        # place the take profit order
        take_profit_order = LimitOrder('SELL', 1, take_profit_price)
        take_profit_order.transmit = True
        ib.placeOrder(mnq_fut_contract, take_profit_order)
        ib.placeOrder(mnq_fut_contract, LimitOrder('BUY', 1, df['HA_Close'].iloc[-1] * (1 + takeprofit)))
    
  
        
if __name__ == "__main__":
    while True:
        strategy_entry()
        time.sleep(1800)
        strategy_exit()

