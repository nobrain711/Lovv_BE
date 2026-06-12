import os

from shared.mysql_data import MySqlClient
from shared.rds_data import RdsDataClient


def create_database_client():
    access_mode = (os.environ.get("DB_ACCESS_MODE") or "aurora-data-api").strip().lower()
    if access_mode in ("mysql", "rds-mysql", "direct-mysql"):
        return MySqlClient()
    return RdsDataClient()
