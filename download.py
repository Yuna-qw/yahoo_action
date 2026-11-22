import random
import threading
import os
import time
import datetime
import pandas as pd
import requests
import yfinance as yf
from calendar import monthrange


print(f"yfinance 版本: {yf.__version__}")

fail_download = {'Shanghai_Shenzhen': [], 'Snp500_Ru1000': [], 'TSX': []}


def downloader(ticker, data_name, start_date, end_date, sleep_time=1, repeat=3, option=None):
    """
    下载股票数据，支持yfinance和requests两种方式，并可选择下载方式。
    参数:
        ticker (str): 股票代码。
        data_name (str): 数据类别名称（用于创建子文件夹）。
        start_date (datetime.date): 数据开始日期。
        end_date (datetime.date): 数据结束日期。
        sleep_time (int): 每次重试前的等待时间（秒）。
        repeat (int): 最大重试次数。
        option (int, optional): 下载方式选项。
            - None (或任何非0/1值): 先尝试yfinance，失败后回退到requests。
            - 0: 只尝试yfinance。
            - 1: 只尝试requests。
            默认为 None。
    """
    for _ in range(repeat):
        if option is None or option == 0:
            try:
                data = yf.Ticker(ticker).history(
                    period="max",
                    interval="1d",
                    start=start_date,
                    end=end_date,
                    prepost=False,
                    actions=False,
                    auto_adjust=False,
                    back_adjust=False,
                    proxy=None,
                    rounding=False
                )
                if data is None or data.shape[0] <= 1:
                    fail_download[data_name].append(ticker)
                    print(ticker + ' None')
                else:
                    data = data.asfreq('ME', method='pad')  # 数据频度为每月（python环境3.11）
                    # data = data.asfreq('M', method='pad')    # 数据频度为每月（python环境3.7）
                    data.to_csv(os.path.join('new_csv', str(data_name), f'{ticker}.csv'))
                    print(ticker + ' Successful')
                break
            except Exception as e:
                print(f"{ticker} Error: {e}")
                time.sleep(sleep_time)

        # 使用 requests 备用接口
        # 仅当 option 为 None (默认行为) 或 option 为 1 时尝试
        if option is None or option == 1:
            # 如果 option 为 0，在 yfinance 失败后应该跳过此部分。
            # 此检查确保如果 option 明确为 0 且 yfinance 失败，
            if option == 0 and 'e_yf' in locals(): # 检查 yfinance 是否失败且 option 是否为 0
                continue # 如果 option 为 0，则跳过此重试的 requests 尝试
            try:
                # 重新计算 yfinance 时间范围，确保结束日期是上个月的最后一天
                today = datetime.date.today()
                # 确定上个月的最后一天
                if today.month == 1:
                    # 如果当前月份是 1 月，则上个月是上一年的 12 月
                    target_month = 12
                    target_year = today.year - 1
                else:
                    target_month = today.month - 1
                    target_year = today.year
                target_day = monthrange(target_year, target_month)[1]
                req_end_date = datetime.date(target_year, target_month, target_day)
                start_unix = int(time.mktime(start_date.timetuple()))
                # Yahoo Finance API 的 end_unix 通常是独占的，所以加一天然后减去 1 秒
                end_unix = int(time.mktime((req_end_date + datetime.timedelta(days=1)).timetuple())) - 1
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start_unix}&period2={end_unix}&interval=1d&events=div%2Csplits"
                headers = {
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "application/json",
                    "Referer": "https://finance.yahoo.com/",
                }
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code != 200:

                    raise ValueError(f"requests 状态码错误: {response.status_code}")
                result = response.json()
                chart = result.get("chart", {})
                if chart.get("error"):
                    fail_download[data_name].append(ticker)
                    raise ValueError(f"requests API 错误: {chart['error']}")

                result_data = chart.get("result", [])
                if not result_data:
                    fail_download[data_name].append(ticker)
                    raise ValueError("requests 未返回数据。")

                timestamps = result_data[0].get("timestamp", [])
                indicators = result_data[0].get("indicators", {})
                quote = indicators.get("quote", [{}])[0]
                adjclose_data = indicators.get("adjclose", [{}])[0]

                if not timestamps or not quote.get("close") or not adjclose_data.get("adjclose"):
                    fail_download[data_name].append(ticker)
                    raise ValueError("requests 数据缺失: 收盘价或调整收盘价数据缺失。")

                df = pd.DataFrame({
                    "Date": pd.to_datetime([datetime.datetime.fromtimestamp(ts, datetime.UTC) for ts in timestamps]).tz_localize(None),
                    "Open": quote.get("open", []),
                    "High": quote.get("high", []),
                    "Low": quote.get("low", []),
                    "Close": quote.get("close", []),
                    "Adj Close": adjclose_data.get("adjclose", []),
                    "Volume": quote.get("volume", []),
                })

                if df.shape[0] <= 1:
                    raise ValueError("requests 数据不足。")

                # 对齐到自然月的最后一天，填充缺失日期
                monthly_rows = []
                for ym, group in df.groupby(df['Date'].dt.to_period('M')):
                    last_day = ym.to_timestamp(how='end')
                    # 确保处理 'Close' 列中的 NaN 值以确定最后一个有效行
                    last_valid_row = group.loc[group['Close'].notna()].iloc[-1]
                    if last_valid_row['Date'].date() == last_day.date():
                        monthly_rows.append(last_valid_row)
                    else:
                        new_row = last_valid_row.copy()
                        new_row['Date'] = last_day
                        monthly_rows.append(new_row)

                df_monthly = pd.DataFrame(monthly_rows)
                df_monthly['Date'] = df_monthly['Date'].dt.strftime('%Y-%m-%d')

                os.makedirs(os.path.join('new_csv', data_name), exist_ok=True)
                filepath = os.path.join('new_csv', data_name, f"{ticker}.csv")
                df_monthly.to_csv(filepath, index=False)
                print(f"{ticker} requests API 下载成功。")
                return  # 成功下载，退出

            except Exception as e_req:
                if option == 1: # 如果只选择 requests，则不尝试 yfinance
                    print(f"{ticker} requests API 下载失败: {e_req}")
                    break # 退出重试循环
                else: # 如果 option 为 None，则返回 yfinance（通过外部循环重试）
                    print(f"{ticker} requests API 下载失败: {e_req}")
                    time.sleep(sleep_time)
                    # 如果 requests 失败且不是 requests-only 模式，它将重试外部循环，
                    # 外部循环将再次尝试 yfinance（如果 option 为 None）。

def download(data_option=0, use_threads=1, sleep_time=1, repeat=1, download_option_method=None):
    # 新建文件夹
    if not os.path.exists('new_csv'):
        os.mkdir('new_csv')
    for country in ['Shanghai_Shenzhen', 'Snp500_Ru1000', 'TSX']:
        if not os.path.exists(os.path.join('new_csv', country)):
            os.mkdir(os.path.join('new_csv', country))

    print("正在加载数据...")
    # data 将有三列: 'country', 'Yahoo_adj_Ticker_symbol', 'currently use'
    data = pd.DataFrame(data=None, index=None, columns=['country', 'Yahoo_adj_Ticker_symbol', 'currently use'], dtype=object)
    data_dict = {'country': None, 'Yahoo_adj_Ticker_symbol': None, 'currently use': None}

    # 加载所有数据
    if data_option == 0:
        data_Shanghai_Shenzhen = pd.read_excel('master_symbol_v1.6_2023.03.xlsx', sheet_name='Shanghai_Shenzhen', dtype='object', engine='openpyxl')
        for i, row in data_Shanghai_Shenzhen.iterrows():
            data_dict['country'] = 'Shanghai_Shenzhen'
            data_dict['Yahoo_adj_Ticker_symbol'] = row['Yahoo_adj_Ticker_symbol']
            data_dict['currently use'] = row['currently use']
            data.loc[i] = data_dict
        index = data.index[-1] + 1
        data_Snp500_Ru1000 = pd.read_excel('master_symbol_v1.6_2023.03.xlsx', sheet_name='Snp500_Ru1000', dtype='object', engine='openpyxl')
        for i, row in data_Snp500_Ru1000.iterrows():
            data_dict['country'] = 'Snp500_Ru1000'
            data_dict['Yahoo_adj_Ticker_symbol'] = row['Yahoo_adj_Ticker_symbol']
            data_dict['currently use'] = row['currently use']
            data.loc[index] = data_dict
            index += 1

        data_TSX = pd.read_excel('master_symbol_v1.6_2023.03.xlsx', sheet_name='TSX', dtype='object', engine='openpyxl')
        for i, row in data_TSX.iterrows():
            data_dict['country'] = 'TSX'
            data_dict['Yahoo_adj_Ticker_symbol'] = row['Yahoo_adj_Ticker_symbol']
            data_dict['currently use'] = row['currently use']
            data.loc[index] = data_dict
            index += 1
    # 加载指定国家的数据
    else:
        sheetname = {1: 'Shanghai_Shenzhen', 2: 'Snp500_Ru1000', 3: 'TSX'}
        data_chosen = pd.read_excel('master_symbol_v1.6_2023.03.xlsx', sheet_name=sheetname[data_option], dtype='object', engine='openpyxl')
        for i, row in data_chosen.iterrows():
            data_dict['country'] = sheetname[data_option]
            data_dict['Yahoo_adj_Ticker_symbol'] = row['Yahoo_adj_Ticker_symbol']
            data_dict['currently use'] = row['currently use']
            data.loc[i] = data_dict

    # 设置股票数据的开始和结束日期
    start_date = datetime.datetime(1970, 2, 1)
    now = datetime.datetime.now()

    # 计算结束日期为上个月的最后一天
    if now.month == 1:
        end = datetime.datetime(now.year - 1, 12, 1) # 上一年的 12 月
    else:
        end = datetime.datetime(now.year, now.month, 1) - datetime.timedelta(days=1) # 上个月的最后一天

    end_date = end # 用于 yfinance 的 end 参数，它是独占的

    # 格式化 endDate 用于检查现有文件
    endDate = end.strftime('%Y-%m-%d')


    thread_list = []

    while repeat:
        print("正在开始数据下载...")
        for index, row in data.iterrows():
            ticker = row['Yahoo_adj_Ticker_symbol']
            data_name = row['country']
            # 只下载标记为 'currently use' 的股票
            if row['currently use'] != 'yes':
                continue
            # 检查股票是否已下载，以及最后一个日期是否是上个月的月底
            filename = os.path.join(os.getcwd(), (os.path.join('new_csv', str(data_name), f'{ticker}.csv')))
            if os.path.exists(filename):
                d = pd.read_csv(filename)
                if not d.empty and d.iloc[-1, 0] == endDate:
                    continue
            # 使用线程或不使用
            if use_threads == 1:
                t = threading.Thread(target=downloader, args=(ticker, data_name, start_date, end_date),
                                     kwargs={'option': download_option_method}) # 在这里传递新参数
                thread_list.append(t)
            else:
                downloader(ticker, data_name, start_date, end_date, option=download_option_method) # 在这里传递新参数

        # 启动线程
        for i, thread in enumerate(thread_list):
            thread.start()
            # 每个添加的下载线程暂停主线程 1 秒
            time.sleep(sleep_time)
        # 等待所有线程完成
        for thread in thread_list:
            thread.join()
        # 清空线程列表
        thread_list.clear()
        repeat -= 1

    # 记录失败的下载
    record = ''
    for country in ['Shanghai_Shenzhen', 'Snp500_Ru1000', 'TSX']:
        record += ('\n' + country + '\n失败下载数量: ' + str(len(fail_download[country])) + '\n' + '\n'.join(fail_download[country]) + '\n')
    if not os.path.exists('failed_txt'):
        os.mkdir('failed_txt')
    with open('failed_txt/failed.txt', 'w', encoding='utf-8')as f:
        f.write(record)
    print("下载完成！")


if __name__ == '__main__':
    start_time = time.time()
    data_option = 0  # 0:全部, 1:上海_深圳, 2:标普500_罗素1000, 3:多伦多证券交易所
    use_threads = 1  # 0: 不使用线程, 1: 使用线程
    sleep_time = 1  # 线程间隔时间（秒），例如 1 或 random.randint(10, 20)
    repeat = 3  # 下载重试次数
    download_method_choice = 1 # None: 先 yfinance 后 requests; 0: 只 yfinance; 1: 只 requests

    download(data_option, use_threads, sleep_time, repeat, download_method_choice)
    print(f"耗时: {time.time() - start_time:.2f}秒")