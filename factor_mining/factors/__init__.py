"""因子模块初始化"""
from factors.registry import factor_registry, factor
# from factors.basic_factors import *
# from factors.custom_factors import *
from factors.dev_factors import *

__all__ = ['factor_registry', 'factor']