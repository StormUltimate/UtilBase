"""Общие проверки схемы для идемпотентных миграций (БД после create_all в 001_initial)."""

from __future__ import annotations

import sqlalchemy as sa


def column_exists(connection, table: str, column: str, schema: str = "public") -> bool:
    r = connection.execute(
        sa.text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = :s AND table_name = :t AND column_name = :c
            """
        ),
        {"s": schema, "t": table, "c": column},
    )
    return r.scalar() is not None


def table_exists(connection, table: str, schema: str = "public") -> bool:
    r = connection.execute(
        sa.text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = :s AND table_name = :t
            """
        ),
        {"s": schema, "t": table},
    )
    return r.scalar() is not None


def index_exists(connection, table: str, index_name: str, schema: str = "public") -> bool:
    r = connection.execute(
        sa.text(
            """
            SELECT 1 FROM pg_indexes
            WHERE schemaname = :s AND tablename = :t AND indexname = :i
            """
        ),
        {"s": schema, "t": table, "i": index_name},
    )
    return r.scalar() is not None


def constraint_exists(connection, table: str, name: str, schema: str = "public") -> bool:
    r = connection.execute(
        sa.text(
            """
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = :s AND table_name = :t AND constraint_name = :n
            """
        ),
        {"s": schema, "t": table, "n": name},
    )
    return r.scalar() is not None
