import re
import time
from contextlib import contextmanager

@contextmanager
def timed(msg, logger):
    t0 = time.time()
    yield
    t1 = time.time()
    logger.info(f"{msg} done in {t1 - t0:.2f}s")

def parse_delay_period(col: str):
    d = None; p = None
    m = re.search(r"delay_([0-9]+[smhd])", col)
    if m: d = m.group(1)
    m = re.search(r"period_([0-9]+[smhd])", col)
    if m: p = m.group(1)
    return d, p
