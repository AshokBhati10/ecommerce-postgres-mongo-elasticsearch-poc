"""Module-level database clients.

PostgreSQL: psycopg connection pool (dict rows).
MongoDB:    single thread-safe MongoClient.
Elasticsearch: single thread-safe Elasticsearch client.
"""
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pymongo import MongoClient
from elasticsearch import Elasticsearch

from .settings import settings

_pg_pool: ConnectionPool | None = None
_mongo_client: MongoClient | None = None
_es_client: Elasticsearch | None = None


def pg_pool() -> ConnectionPool:
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = ConnectionPool(
            settings.database_url, kwargs={"row_factory": dict_row}
        )
        _pg_pool.open()
    return _pg_pool


def mongo_db():
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(settings.mongo_url)
    return _mongo_client[settings.mongo_db]


def es_client() -> Elasticsearch:
    global _es_client
    if _es_client is None:
        _es_client = Elasticsearch(settings.elasticsearch_url)
    return _es_client


def close_all() -> None:
    global _pg_pool, _mongo_client, _es_client
    if _pg_pool is not None:
        _pg_pool.close()
        _pg_pool = None
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
    if _es_client is not None:
        _es_client.close()
        _es_client = None
