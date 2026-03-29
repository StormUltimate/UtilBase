"""Адаптеры модуля договоров.

Позволяют подключать модуль к другому проекту с собственными моделями/хранилищем.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models.all_models import ContractDocument, Equipment, EquipmentTemplate, Request


class RequestsAdapter(Protocol):
    def by_contract_scope(self, contract_id: int) -> list[Request]: ...


class TemplatesAdapter(Protocol):
    def distinct_template_names(self) -> list[str]: ...


class EquipmentAdapter(Protocol):
    def detach_by_contract_id(self, contract_id: int) -> None: ...


class ContractDocumentsAdapter(Protocol):
    def create_document(self, **kwargs) -> ContractDocument: ...


@dataclass(slots=True)
class ContractsAdapters:
    requests: RequestsAdapter
    templates: TemplatesAdapter
    equipment: EquipmentAdapter
    documents: ContractDocumentsAdapter


class SQLAlchemyRequestsAdapter:
    def by_contract_scope(self, contract_id: int) -> list[Request]:
        return Request.query.filter(
            Request.contract_id == contract_id,
            Request.contract_scope_uid.isnot(None),
        ).all()


class SQLAlchemyTemplatesAdapter:
    def distinct_template_names(self) -> list[str]:
        names = [
            row[0]
            for row in EquipmentTemplate.query.with_entities(EquipmentTemplate.type.distinct())
            .filter(EquipmentTemplate.type.isnot(None))
            .all()
            if row[0]
        ]
        names.sort()
        return names


class SQLAlchemyEquipmentAdapter:
    def detach_by_contract_id(self, contract_id: int) -> None:
        Equipment.query.filter(Equipment.contract_id == contract_id).update(
            {Equipment.contract_id: None},
            synchronize_session=False,
        )


class SQLAlchemyContractDocumentsAdapter:
    def create_document(self, **kwargs) -> ContractDocument:
        return ContractDocument(**kwargs)


def default_contracts_adapters() -> ContractsAdapters:
    return ContractsAdapters(
        requests=SQLAlchemyRequestsAdapter(),
        templates=SQLAlchemyTemplatesAdapter(),
        equipment=SQLAlchemyEquipmentAdapter(),
        documents=SQLAlchemyContractDocumentsAdapter(),
    )
