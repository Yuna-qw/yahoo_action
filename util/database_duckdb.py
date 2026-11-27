# 文件名: database_duckdb.py
import duckdb
import pandas as pd
import os
import pandas.api.types as pd_types

# 配置
DUCKDB_DB_NAME = 'yahoo_data.duckdb'  # 数据库文件名
TABLE_NAME = 'stock_data'  # 数据库表名
MONTHLY_VIEW_NAME = 'stock_monthly_change'  # 月度分析视图名称


def get_db_connection() -> duckdb.DuckDBPyConnection:
    """获取 DuckDB 数据库连接"""
    # 如果文件不存在会自动创建
    return duckdb.connect(database=DUCKDB_DB_NAME)


def execute_and_fetch(query: str, params: tuple = None) -> pd.DataFrame:
    """
    执行 SQL 查询并将结果存储为 Pandas DataFrame。
    """
    conn = get_db_connection()
    try:
        # 使用 DuckDB 的 execute 和 fetchdf
        if params:
            df_result = conn.execute(query, params).fetchdf()
        else:
            df_result = conn.execute(query).fetchdf()
    except Exception as e:
        print(f"执行查询失败: {e}\n查询语句: {query[:100]}...")
        return pd.DataFrame()
    finally:
        conn.close()
    return df_result


def get_last_date_from_db(ticker: str) -> str:
    """从数据库获取某个股票的最新日期。"""
    query = f'SELECT CAST(Date AS TEXT) AS Date FROM {TABLE_NAME} WHERE Ticker = ? ORDER BY Date DESC LIMIT 1'
    result_df = execute_and_fetch(query, (ticker,))
    return str(result_df['Date'].iloc[0]) if not result_df.empty else None


def save_data_to_db(df: pd.DataFrame, ticker: str, data_name: str):
    """
    将下载的股票数据批量保存到 DuckDB 数据库。
    使用 DELETE/INSERT 逻辑实现 UPSERT 操作。
    """
    conn = get_db_connection()
    try:
        # 添加 Ticker 和 Country 列
        df['Ticker'] = ticker
        df['Country'] = data_name

        # 确保 Date 是 TEXT 类型
        if pd_types.is_datetime64_any_dtype(df['Date']):
            df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')

        # 确保列名与数据库表结构一致 (注意: Adj Close 必须用双引号)
        required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume', 'Ticker', 'Country']
        df_db = df[[col for col in required_cols if col in df.columns]]

        # 1. 定义表的 SQL 结构 (如果表不存在则创建)
        create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                Date TEXT NOT NULL,
                Open DOUBLE,
                High DOUBLE,
                Low DOUBLE,
                Close DOUBLE,
                "Adj Close" DOUBLE,
                Volume BIGINT,
                Ticker TEXT NOT NULL,
                Country TEXT,
                PRIMARY KEY (Ticker, Date)
            );
        """
        conn.execute(create_table_sql)

        # 2. 插入数据到临时视图
        # 将 DataFrame 注册为临时视图
        temp_view_name = f"temp_{ticker.replace('.', '_').replace('-', '_')}"
        conn.register(temp_view_name, df_db)

        # 3. 从主表中删除重复的记录
        delete_sql = f"""
                    DELETE FROM {TABLE_NAME}
                    WHERE Ticker = '{ticker}' AND CAST(Date AS TEXT) IN (SELECT Date FROM {temp_view_name});
                """
        conn.execute(delete_sql)

        # 4. 将临时视图的数据插入到主表
        insert_sql = f"""
                    INSERT INTO {TABLE_NAME} (Date, Open, High, Low, Close, "Adj Close", Volume, Ticker, Country)
                    SELECT Date, Open, High, Low, Close, "Adj Close", Volume, Ticker, Country
                    FROM {temp_view_name};
                """
        conn.execute(insert_sql)

        # 5. 提交更改
        conn.commit()

    except Exception as e:
        print(f"DuckDB 存储失败 ({ticker}): {e}")
    finally:
        conn.close()


def create_monthly_change_view():
    """
    创建或替换月度涨跌幅分析视图 stock_monthly_change。
    """
    conn = get_db_connection()
    query = f"""
        CREATE OR REPLACE VIEW {MONTHLY_VIEW_NAME} AS
        WITH MonthlyData AS (
            SELECT
                Ticker,
                Country,
                Date,
                "Adj Close" AS Monthly_Close,
                ROW_NUMBER() OVER (PARTITION BY Ticker, DATE_TRUNC('month', Date) ORDER BY Date DESC) AS rn
            FROM {TABLE_NAME}
            WHERE "Adj Close" IS NOT NULL
        )
        SELECT
            Ticker,
            Country,
            Date,
            Monthly_Close,
            LAG(Monthly_Close, 1) OVER (PARTITION BY Ticker ORDER BY Date ASC) AS Prev_Monthly_Close,
            Monthly_Close - LAG(Monthly_Close, 1) OVER (PARTITION BY Ticker ORDER BY Date ASC) AS Monthly_Change_Amt,
            ROUND(
                (Monthly_Close - LAG(Monthly_Close, 1) OVER (PARTITION BY Ticker ORDER BY Date ASC)) * 100.0 
                / LAG(Monthly_Close, 1) OVER (PARTITION BY Ticker ORDER BY Date ASC),
                2
            ) AS Monthly_Change_Pct
        FROM MonthlyData
        WHERE rn = 1
        ORDER BY Ticker, Date;
    """
    try:
        conn.execute(query)
        print(f"DuckDB 视图 '{MONTHLY_VIEW_NAME}' 已成功创建/更新。")
    except Exception as e:
        print(f"创建视图失败: {e}")
    finally:
        conn.close()

def create_table_if_not_exists(conn: duckdb.DuckDBPyConnection):
    """
    创建股票数据表，如果它不存在的话。
    使用 Ticker 和 Date 组合作为 PRIMARY KEY。
    """
    # 定义表的结构，注意 DuckDB 倾向于使用 DATE 和 DOUBLE 类型
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            Ticker TEXT,
            Country TEXT,
            Date DATE, 
            Open DOUBLE,
            High DOUBLE,
            Low DOUBLE,
            Close DOUBLE,
            "Adj Close" DOUBLE,
            Volume BIGINT,
            PRIMARY KEY (Ticker, Date)
        );
    """)
    print(f"数据库表 {TABLE_NAME} 准备就绪。")


def load_data_from_db(ticker: str) -> pd.DataFrame:
    """从数据库加载单个股票的完整历史数据。"""
    query = f'SELECT Date, Open, High, Low, Close, "Adj Close", Volume FROM {TABLE_NAME} WHERE Ticker = ? ORDER BY Date ASC'
    return execute_and_fetch(query, (ticker,))


if __name__ == '__main__':
    print("DuckDB 数据库模块已运行。")
    create_monthly_change_view()