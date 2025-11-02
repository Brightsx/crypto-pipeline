import os
import re
import time
import logging
import requests
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import zipfile
import pyarrow.parquet as pq
import pyarrow as pa
import calendar
import shutil
import random
import sys
import threading
from tqdm import tqdm

# 配置日志 - 使用线程安全的日志记录
def setup_logger(output_dir=None):
    logger = logging.getLogger("binance_data")
    logger.setLevel(logging.INFO)
    
    # 清除现有处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 控制台处理器 - 使用线程安全的日志记录
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    # 文件处理器（如果指定了输出目录）
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        log_file = os.path.join(output_dir, "download.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
    
    return logger

# 下载并处理文件 - 使用锁确保输出不混乱
output_lock = threading.Lock()

class TqdmLoggingHandler(logging.Handler):
    """重定向日志输出到tqdm.write，避免与进度条冲突"""
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
    
    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)

def setup_logger(output_dir=None):
    logger = logging.getLogger("binance_data")
    logger.setLevel(logging.INFO)
    
    # 清除现有处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 使用TqdmLoggingHandler作为控制台处理器
    console_handler = TqdmLoggingHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    # 文件处理器
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        log_file = os.path.join(output_dir, "download.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
    
    return logger

# 生成日期范围内的所有日期
def generate_date_range(start_date, end_date, base_path):
    # 从路径推断频率
    if 'daily' in base_path:
        frequency = 'daily'
    elif 'monthly' in base_path:
        frequency = 'monthly'
    else:
        raise ValueError("无法从路径推断频率 (daily/monthly)")
    
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    dates = []
    current = start
    
    if frequency == 'daily':
        while current <= end:
            dates.append(current.strftime("%Y-%m-%d"))
            current = current + pd.DateOffset(days=1)
    
    elif frequency == 'monthly':
        while current <= end:
            # 获取月份最后一天
            _, last_day = calendar.monthrange(current.year, current.month)
            month_end = datetime(current.year, current.month, last_day)
            
            # 如果月份结束日期超过结束日期，使用结束日期
            if month_end > end:
                dates.append(end.strftime("%Y-%m-%d"))
            else:
                dates.append(month_end.strftime("%Y-%m-%d"))
            
            # 跳到下个月
            current = current + pd.DateOffset(months=1)
    
    return dates

# 构建文件URL
def build_file_url(symbol, date, base_path):
    # 从完整路径中提取数据类型
    data_type = "spot" if "spot" in base_path else "futures"
    
    # 从路径中提取数据名称（最后一级目录）
    path_parts = base_path.split('/')
    data_name = path_parts[-1]
    
    # 构建文件名
    if "monthly" in base_path:
        date_str = date[:-3]
    else:
        date_str = date
    if data_type == "spot":
        filename = f"{symbol}-{data_name}-{date_str}.zip"
    else:
        # 期货数据有额外的市场类型前缀
        market_type = "um" if "um" in base_path else "cm"
        # filename = f"{symbol}-{market_type}-{data_name}-{date}.zip"
        filename = f"{symbol}-{data_name}-{date_str}.zip"
    
    # 完整URL
    url = f"https://data.binance.vision/{base_path}/{symbol}/{filename}"
    return url

# 下载并处理文件
def download_and_process(url, output_base, symbol, data_name, temp_dir, logger, position):
    try:
        # 创建临时目录
        os.makedirs(temp_dir, exist_ok=True)
        filename = os.path.basename(url)
        local_zip = os.path.join(temp_dir, filename)
        
        # 提取日期部分
        date_part = filename.split('.zip')[0]
        
        # 创建输出目录
        output_dir = os.path.join(output_base, symbol, data_name)
        os.makedirs(output_dir, exist_ok=True)
        
        # 新的文件命名
        output_file = os.path.join(output_dir, f"{date_part}.parquet")
        
        if os.path.exists(output_file):
            with output_lock:
                logger.info(f"文件已存在，跳过: {output_file}")
            return True, date_part
        
        # 下载文件
        with output_lock:
            logger.info(f"开始下载: {url}")
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        
        # 重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with requests.get(url, headers=headers, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get('content-length', 0))
                    
                    # 使用带位置的进度条
                    with tqdm(
                        total=total_size,
                        unit='B',
                        unit_scale=True,
                        desc=f"{symbol[:6]}..{date_part}",
                        position=position,
                        leave=False,
                        dynamic_ncols=True
                    ) as pbar:
                        with open(local_zip, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    pbar.update(len(chunk))
                break  # 成功则跳出重试循环
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    with output_lock:
                        logger.warning(f"下载失败 ({e}), 重试 {attempt+1}/{max_retries} in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
        
        # 解压并转换为Parquet
        with zipfile.ZipFile(local_zip, 'r') as zip_ref:
            csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
            if not csv_files:
                raise ValueError(f"ZIP文件中未找到CSV文件: {filename}")
            
            for csv_file in csv_files:
                with zip_ref.open(csv_file) as f:
                    file_size = zip_ref.getinfo(csv_file).file_size
                    # if file_size > 100 * 1024 * 1024:
                    #     chunks = pd.read_csv(f, chunksize=100000, header=None)  # header=None 忽略第一行作为列名
                    #     df = pd.concat(chunks)
                    # else:
                    #     df = pd.read_csv(f, header=None)
                    df = pd.read_csv(f)
                
                # # 如果你不确定列数，使用列数推测生成列名
                # num_columns = df.shape[1]  # 获取列数
                # df.columns = [f'column{i}' for i in range(num_columns)]  # 动态生成列名
                
                # 将 DataFrame 转换为 Parquet 格式
                table = pa.Table.from_pandas(df)
                pq.write_table(table, output_file)
                
                with output_lock:
                    logger.info(f"成功转换: {output_file} (大小: {len(df)} 行)")
        
        # 清理临时文件
        os.remove(local_zip)
        return True, date_part
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            with output_lock:
                logger.debug(f"文件不存在: {url}")
        else:
            with output_lock:
                logger.error(f"HTTP错误 {url}: {str(e)}")
        return False, date_part
    except Exception as e:
        with output_lock:
            logger.error(f"处理失败 {url}: {str(e)}")
        return False, date_part

# 下载主函数
def download_data(symbols, start_date, end_date, base_path, output_dir, max_workers=5):
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    logger = setup_logger(output_dir)
    temp_dir = os.path.join(output_dir, "_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    # 从路径中提取数据名称
    data_name = base_path.split('/')[-1]
    
    logger.info(f"任务启动: symbols={symbols} start={start_date} end={end_date}")
    logger.info(f"数据路径: {base_path}")
    
    # 生成日期范围内的所有日期
    dates = generate_date_range(start_date, end_date, base_path)
    logger.info(f"日期范围: {len(dates)} 天")
    
    # 处理每个币种和日期
    total_files = 0
    success_files = 0
    
    # 为每个符号创建进度条位置映射
    symbol_positions = {symbol: idx for idx, symbol in enumerate(symbols)}
    
    for symbol in symbols:
        logger.info(f"处理币种: {symbol}")
        
        # 为每个币种创建任务列表
        tasks = []
        for date in dates:
            url = build_file_url(symbol, date, base_path)
            tasks.append((url, date))
        
        logger.info(f"为 {symbol} 生成 {len(tasks)} 个下载任务")
        
        # 并发处理任务
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for url, date in tasks:
                # 为每个任务分配位置：符号位置 + 偏移量
                position = symbol_positions[symbol] * (max_workers + 1)
                future = executor.submit(
                    download_and_process, 
                    url, 
                    output_dir, 
                    symbol, 
                    data_name, 
                    temp_dir, 
                    logger,
                    position
                )
                futures[future] = (url, date)
            
            for future in as_completed(futures):
                url, date = futures[future]
                total_files += 1
                try:
                    success, date_part = future.result()
                    if success:
                        success_files += 1
                        logger.info(f"完成: {symbol}-{date_part}")
                except Exception as e:
                    logger.error(f"任务异常 {url}: {str(e)}")
                
                # 添加延迟避免请求过于频繁
                time.sleep(0.5)
    
    # 结果统计
    logger.info(f"任务完成! 总文件: {total_files}, 成功: {success_files}, 失败: {total_files - success_files}")
    
    # 清理临时目录
    try:
        shutil.rmtree(temp_dir)
        logger.info(f"清理临时目录: {temp_dir}")
    except Exception as e:
        logger.error(f"清理临时目录失败: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Binance历史数据工具')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # 下载数据命令
    download_parser = subparsers.add_parser('download', help='下载并转换数据')
    download_parser.add_argument('--symbols', nargs='+', required=True, help='交易对列表 例如 BTCUSDT ETHUSDT')
    download_parser.add_argument('--start_date', required=True, help='开始日期 YYYY-MM-DD')
    download_parser.add_argument('--end_date', required=True, help='结束日期 YYYY-MM-DD')
    download_parser.add_argument('--base_path', required=True, help='基础路径 例如 data/spot/daily/aggTrades')
    download_parser.add_argument('--output_dir', default='./binance_data', help='输出目录')
    download_parser.add_argument('--max_workers', type=int, default=5, help='最大并发数')
    
    args = parser.parse_args()
    
    if args.command == 'download':
        download_data(
            symbols=args.symbols,
            start_date=args.start_date,
            end_date=args.end_date,
            base_path=args.base_path,
            output_dir=args.output_dir,
            max_workers=args.max_workers
        )