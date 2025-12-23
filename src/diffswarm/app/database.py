from functools import cache

from sapling import Database


@cache
def get_database() -> Database:
    return Database()
