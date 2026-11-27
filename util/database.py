import sqlite3
import pandas as pd
import os

# 配置
SQLITE_DB_NAME = 'yahoo_data.sqlite'  # 数据库文件名
TABLE_NAME = 'stock_data'  # 数据库表名
MONTHLY_VIEW_NAME = 'stock_monthly_change'  # 新增的月度分析视图名称


def get_db_connection():
    """获取数据库连接"""
    return sqlite3.connect(SQLITE_DB_NAME)


def create_monthly_change_view():
    """
    创建月度涨跌幅分析视图 stock_monthly_change。
    该视图计算每个股票每月的收盘价、上月收盘价、月度涨跌额和月度涨跌幅。
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # 1. 创建一个 Common Table Expression (CTE) 来筛选每个月的最后一天数据。
    # 2. 使用 LAG() 窗口函数获取上一个月的收盘价。
    query = f"""
        CREATE VIEW IF NOT EXISTS {MONTHLY_VIEW_NAME} AS
        WITH MonthlyData AS (
            SELECT
                Ticker,
                Country,
                Date,
                "Adj Close" AS Monthly_Close,
                -- 提取月份开始日期用于分组和排序 (例如: 'YYYY-MM-01')
                STRFTIME('%Y-%m-01', Date) AS Month_Start_Date,
                -- 找到每个月中的最后一天
                ROW_NUMBER() OVER(
                    PARTITION BY Ticker, STRFTIME('%Y-%m', Date)
                    ORDER BY Date DESC
                ) AS rn
            FROM {TABLE_NAME}
        )
        SELECT
            T1.Ticker,
            T1.Country,
            T1.Month_Start_Date,
            T1.Monthly_Close,
            -- 使用 LAG() 获取上个月的 Monthly_Close
            LAG(T1.Monthly_Close, 1) OVER (
                PARTITION BY Ticker
                ORDER BY T1.Month_Start_Date
            ) AS Prev_Monthly_Close,
            -- 计算月度涨跌额
            T1.Monthly_Close - LAG(T1.Monthly_Close, 1) OVER (
                PARTITION BY Ticker
                ORDER BY T1.Month_Start_Date
            ) AS Monthly_Change_Amt,
            -- 计算月度涨跌幅 (使用 NULLIF 处理分母为 0 或缺失值的情况)
            (T1.Monthly_Close - LAG(T1.Monthly_Close, 1) OVER (
                PARTITION BY Ticker
                ORDER BY T1.Month_Start_Date
            )) * 100.0 / NULLIF(LAG(T1.Monthly_Close, 1) OVER (
                PARTITION BY Ticker
                ORDER BY T1.Month_Start_Date
            ), 0) AS Monthly_Change_Pct
        FROM MonthlyData T1
        WHERE T1.rn = 1  -- 只保留每个月的最后一条记录 (月底数据)
        ORDER BY T1.Ticker, T1.Month_Start_Date;
    """
    try:
        cursor.execute(query)
        conn.commit()
        print(f"数据库视图 {MONTHLY_VIEW_NAME} 准备就绪。")
    except sqlite3.Error as e:
        # 如果 stock_data 表不存在，这里可能会失败，这是正常的，后续操作会创建表
        if "no such table" in str(e):
            print(f"视图 {MONTHLY_VIEW_NAME} 暂未创建，因为源表 {TABLE_NAME} 不存在。")
        else:
            print(f"创建视图 {MONTHLY_VIEW_NAME} 失败: {e}")
    finally:
        conn.close()


def create_table_if_not_exists():
    """创建股票数据表，如果它不存在的话，并确保视图也存在。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Ticker 和 Date 组合作为主键，使用 REPLACE 策略处理冲突
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            Ticker TEXT NOT NULL,
            Country TEXT NOT NULL,
            Date TEXT NOT NULL,
            Open REAL,
            High REAL,
            Low REAL,
            Close REAL,
            "Adj Close" REAL,
            Volume INTEGER,
            PRIMARY KEY (Ticker, Date) ON CONFLICT REPLACE
        );
    """)
    conn.commit()
    conn.close()
    print(f"数据库表 {TABLE_NAME} 准备就绪。")

    # 【关键修改】在表创建后同步创建视图
    create_monthly_change_view()


def save_data_to_db(df: pd.DataFrame, ticker: str, country: str):
    """将 DataFrame 写入 SQLite 数据库（UPSERT 操作）。"""
    conn = get_db_connection()

    # 确保 Ticker 和 Country 列存在
    if 'Ticker' not in df.columns:
        df.insert(0, 'Ticker', ticker)
    if 'Country' not in df.columns:
        df.insert(1, 'Country', country)

    # if_exists='append' 配合表定义中的 ON CONFLICT REPLACE 实现 UPSERT
    try:
        df.to_sql(
            TABLE_NAME,
            conn,
            if_exists='append',
            index=False
        )
        # print(f"  - DB: {ticker} 写入 {len(df)} 行。")
    except Exception as e:
        print(f"  - DB 写入 {ticker} 失败: {e}")
    finally:
        conn.close()


def load_data_from_db(ticker: str) -> pd.DataFrame:
    """从数据库加载单个股票的完整历史数据。"""
    conn = get_db_connection()
    query = f'SELECT Date, Open, High, Low, Close, "Adj Close", Volume FROM {TABLE_NAME} WHERE Ticker = ? ORDER BY Date ASC'
    df = pd.read_sql_query(query, conn, params=(ticker,))
    conn.close()
    return df


def get_last_date_from_db(ticker: str) -> str:
    """从数据库获取某个股票的最新日期。"""
    conn = get_db_connection()
    query = f'SELECT Date FROM {TABLE_NAME} WHERE Ticker = ? ORDER BY Date DESC LIMIT 1'
    cursor = conn.cursor()
    cursor.execute(query, (ticker,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def execute_and_fetch(query: str, params: tuple = None) -> pd.DataFrame:
    """
    执行 SQL 查询并将结果存储为 Pandas DataFrame。
    """
    conn = get_db_connection()
    try:
        df_result = pd.read_sql_query(query, conn, params=params if params else ())
    except Exception as e:
        print(f"执行查询失败: {e}\n查询语句: {query[:100]}...")
        return pd.DataFrame()
    finally:
        conn.close()
    return df_result


def save_dataframe_to_db(df: pd.DataFrame, table_name: str, if_exists: str = 'replace'):
    """将 DataFrame 存储到数据库中的指定表"""
    conn = get_db_connection()
    try:
        df.to_sql(table_name, conn, if_exists=if_exists, index=False)
    finally:
        conn.close()


# 初始化数据库结构（保持原有逻辑不变，但现在它会创建视图）
# 在您的环境中，这行代码在脚本启动时会执行
create_table_if_not_exists()