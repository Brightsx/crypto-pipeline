"""核心模块初始化"""
from core.config import config
from core.data_manager import DataManager
from core.factor_engine import FactorEngine
from core.utils import *

__all__ = ['config', 'DataManager', 'FactorEngine']