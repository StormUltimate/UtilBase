"""Модуль договоров (plugin-style registration)."""

from .adapters import ContractsAdapters, default_contracts_adapters
from .plugin import ContractsModuleConfig, register_contracts_module

__all__ = [
    "ContractsAdapters",
    "default_contracts_adapters",
    "ContractsModuleConfig",
    "register_contracts_module",
]
