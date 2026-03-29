"""Подключаемый модуль договоров.

Первая итерация модульности:
- единая точка регистрации blueprint;
- конфиг для URL-префикса;
- без изменения текущего поведения.
"""

from dataclasses import dataclass

from .adapters import ContractsAdapters, default_contracts_adapters


@dataclass(slots=True)
class ContractsModuleConfig:
    url_prefix: str = "/contracts"
    adapters: ContractsAdapters | None = None


def register_contracts_module(app, config: ContractsModuleConfig | None = None):
    """Регистрирует модуль договоров в Flask app.

    Пока использует существующий blueprint из текущей реализации.
    Это позволяет постепенно переносить код в app/modules/contracts без
    изменения внешних URL и бизнес-логики.
    """

    cfg = config or ContractsModuleConfig()
    adapters = cfg.adapters or default_contracts_adapters()
    from app.blueprints.contracts.routes import contracts_bp

    # Публичная точка доступа для сервисов/роутов модуля.
    app.extensions["contracts_module"] = {
        "adapters": adapters,
        "config": cfg,
    }
    app.register_blueprint(contracts_bp, url_prefix=cfg.url_prefix)
    return contracts_bp
