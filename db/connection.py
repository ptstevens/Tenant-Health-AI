# db/connection.py

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URLS = {
    'Staging': os.getenv('STAGING_DB_URL'),
    'APAC': os.getenv('APAC_DB_URL'),
    'EU': os.getenv('EU_DB_URL'),
    'US': os.getenv('US_DB_URL'),
    'CA': os.getenv('CA_DB_URL'),
}

def get_db_connection(region):
    db_url = DB_URLS.get(region)
    if not db_url:
        raise ValueError(f"No database URL found for region: {region}")
    try:
        conn = psycopg2.connect(db_url)
        return conn
    except psycopg2.Error as e:
        raise Exception(f"Error connecting to {region} database: {e}")
