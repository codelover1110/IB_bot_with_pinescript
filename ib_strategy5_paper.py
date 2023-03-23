import pandas as pd
from ib_insync import *
import math
import ta
from ta.utils import *
import time

df2 = pd.DataFrame(
    columns=['orderId', 'action', 'titalQuantity', 'status', 'filled', 'remaining', 'avgFillPrice', 'permId',
             'parentId', 'lastFillPrice',
             'clientId', 'whyHeld', 'mktCapPrice'])
j = 0
candle = []

ib = IB()
ib.connect('127.0.0.1', 4002, clientId=16, timeout=0)

mnq_fut_contract = Future('MNQ', '202306', 'CME')


def order_status(trade):
    if trade.orderStatus.status == 'Filled':
        fill = trade.fills[-1]

        print(
            f'{fill.time} - {fill.execution.side} {fill.contract.symbol} {fill.execution.shares} @ {fill.execution.avgPrice}')


def strategy_entry(df2, j):
    bars = ib.reqHistoricalData(
        mnq_fut_contract,
        endDateTime='',
        durationStr='1800 S',
        barSizeSetting='1 min',
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
    df['wma30'] = df['HA_Close'].rolling(window=30).apply(lambda x: (x * range(1, 31)).sum() / sum(range(1, 31)))
    # print(df)
    df.to_csv("Heikin.csv")

    # Define the RWI function
    def rwi(df, length, threshold):
        # print("Em here in rwi")

        def calc30(x):
            return pd.Series(x).rolling(window=30).apply(lambda x: (x * range(1, 31)).sum() / sum(range(1, 31)))

        den = calc30(df['HA_Close'] * math.sqrt(length))
        rwi_high = calc30(df['HA_High'] - df['HA_Low'].shift(length).fillna(method='bfill')) / den
        rwi_low = calc30(df['HA_High'].shift(length).fillna(method='bfill') - df['HA_Low']) / den
        is_rw = (rwi_high < threshold) & (rwi_low < threshold)
        return pd.DataFrame({'is_rw': is_rw, 'rwi_high': rwi_high, 'rwi_low': rwi_low}, index=df.index)
        # return [is_rw, rwi_high, rwi_low]

    data = rwi(df, length, threshold)
    # print("data", data)
    [is_rw, rwi_high, rwi_low] = rwi(df, length, threshold)

    is_rw = data['is_rw'].iloc[-1]
    rwi_high = data['rwi_high'].iloc[-1]
    rwi_low = data['rwi_low'].iloc[-1]

    # Strategy section
    bullish = df['ema9'].iloc[-1] > df['wma30'].iloc[-1]
    rwiCrossOver = (data['rwi_high'].iloc[-2] < data['rwi_low'].iloc[-2]) & (
            data['rwi_high'].iloc[-1] > data['rwi_low'].iloc[-1])
    rwiCrossUnder = (data['rwi_high'].iloc[-2] > data['rwi_low'].iloc[-2]) & (
            data['rwi_high'].iloc[-1] < data['rwi_low'].iloc[-1])
    long = bullish & rwiCrossOver
    short = (not bullish) & rwiCrossUnder

    candleRed = df['HA_Open'].iloc[-1] > df['HA_Close'].iloc[-1]
    candleGreen = df['HA_Open'].iloc[-1] < df['HA_Close'].iloc[-1]

    if candleRed:
        candle.append('red')
    if candleGreen:
        candle.append('green')

    print("CandleRed", candleRed)
    print("CandleGreen", candleGreen)
    print("bullish", bullish)
    print("rwiCrossOver", rwiCrossOver)
    print("rwiCrossUnder", rwiCrossUnder)
    print("long", long)
    print("short", short)

    # request market data to get the current price
    ticker = ib.reqTickers(mnq_fut_contract)[0]
    current_price = ticker.marketPrice()
    print("current price:", current_price)
    if current_price:
        pass
    else:
        current_price = 0.0
    # calculate the prices for the stop loss and take profit orders
    stop_loss_price = round(current_price * (1 - 0.002), 2)
    take_profit_price = round(current_price * (1 + 0.002), 2)

    # calculate the price for the limit order, taking into account the minimum price variation
    price = round(current_price - (0.25 * round((current_price - 1) / 0.25)), 2)

    print("===========================================================================")
    print("current price:", current_price, ", take_profit_price:", take_profit_price, ", stop_loss_price:",
          stop_loss_price
          , ", price:", price)
    print("===========================================================================")
    print("candle", candle, len(candle))

    # df = ib.reqAllOpenOrders()
    # print(df)

    if candleGreen:
        if len(candle) > 1:
            print('Last Element', candle[-1])
            print('Second last Element', candle[-2])
            if candle[-1] == candle[-2]:
                print("Trade already open")
                pass
            else:
                print("Going to open BUY Trade")
                trade = ib.placeOrder(mnq_fut_contract, MarketOrder('BUY', 1))
                trade.filledEvent += order_status
                ib.sleep(5)
                # while True:
                #     if trade.orderStatus.filled == 'Filled':
                #         print("Order Filled")
                #         break

                df2.loc[j] = [trade.orderStatus.orderId, trade.order.action, trade.order.totalQuantity,
                              trade.orderStatus.status, trade.orderStatus.filled, trade.orderStatus.remaining,
                              trade.orderStatus.avgFillPrice, trade.orderStatus.permId, trade.orderStatus.parentId,
                              trade.orderStatus.lastFillPrice,
                              trade.orderStatus.clientId, trade.orderStatus.whyHeld, trade.orderStatus.mktCapPrice]
        else:
            print("Going to open BUY Trade")
            trade = ib.placeOrder(mnq_fut_contract, MarketOrder('BUY', 1))
            trade.filledEvent += order_status
            ib.sleep(5)
            # while True:
            #     if trade.orderStatus.filled == 'Filled':
            #         print("Order Filled")
            #         break
            df2.loc[j] = [trade.orderStatus.orderId, trade.order.action, trade.order.totalQuantity,
                          trade.orderStatus.status, trade.orderStatus.filled, trade.orderStatus.remaining,
                          trade.orderStatus.avgFillPrice, trade.orderStatus.permId, trade.orderStatus.parentId,
                          trade.orderStatus.lastFillPrice,
                          trade.orderStatus.clientId, trade.orderStatus.whyHeld, trade.orderStatus.mktCapPrice]

    if candleRed:
        if len(candle) > 1:
            print('Last Element', candle[-1])
            print('Second last Element', candle[-2])
            if candle[-1] == candle[-2]:
                print("Trade already open")
                pass
            else:
                print("Going to open SELL Trade")
                trade = ib.placeOrder(mnq_fut_contract, MarketOrder('SELL', 1))
                trade.filledEvent += order_status
                ib.sleep(5)
                # while True:
                #     if trade.orderStatus.filled == 'Filled':
                #         print("Order Filled")
                #         break
                df2.loc[j] = [trade.orderStatus.orderId, trade.order.action, trade.order.totalQuantity,
                              trade.orderStatus.status, trade.orderStatus.filled, trade.orderStatus.remaining,
                              trade.orderStatus.avgFillPrice, trade.orderStatus.permId, trade.orderStatus.parentId,
                              trade.orderStatus.lastFillPrice,
                              trade.orderStatus.clientId, trade.orderStatus.whyHeld, trade.orderStatus.mktCapPrice]
        else:
            print("Going to open SELL Trade")
            trade = ib.placeOrder(mnq_fut_contract, MarketOrder('SELL', 1))
            trade.filledEvent += order_status
            ib.sleep(5)
            # while True:
            #     if trade.orderStatus.filled == 'Filled':
            #         print("Order Filled")
            #         break
            df2.loc[j] = [trade.orderStatus.orderId, trade.order.action, trade.order.totalQuantity,
                          trade.orderStatus.status, trade.orderStatus.filled, trade.orderStatus.remaining,
                          trade.orderStatus.avgFillPrice, trade.orderStatus.permId, trade.orderStatus.parentId,
                          trade.orderStatus.lastFillPrice,
                          trade.orderStatus.clientId, trade.orderStatus.whyHeld, trade.orderStatus.mktCapPrice]

    print("===========================================================================")
    print("============================== Trade Details ==============================")
    print("===========================================================================")
    df2.to_csv('order-status.csv')


if __name__ == "__main__":

    while True:
        strategy_entry(df2, j)
        time.sleep(18)
        # strategy_exit()
        j = j + 1
