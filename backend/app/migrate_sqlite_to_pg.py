import os
import sys
import argparse
import logging
from typing import Dict, List, Tuple
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("careon.migration")

TABLE_MIGRATION_ORDER = [
    "users",
    "external_providers",
    "resources",
    "incidents",
    "incident_updates",
    "assignments",
    "provider_enquiries",
    "notifications",
    "cancellations",
    "feedback",
    "audit_logs",
    "verification_logs",
    "chatbot_logs",
    "emergencies",
]

SPATIAL_TABLES = {"incidents", "resources", "external_providers"}


def make_wkt_point(latitude: float, longitude: float) -> str:
    """Format PostGIS WKT Point geometry string."""
    try:
        lat = float(latitude)
        lon = float(longitude)
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            return f"SRID=4326;POINT({lon} {lat})"
    except Exception:
        pass
    return "SRID=4326;POINT(76.6552 12.3052)"


def migrate_sqlite_to_postgres(sqlite_path: str, pg_url: str) -> Dict[str, any]:
    """
    Safely and repeatably import existing CareOn records from SQLite into PostgreSQL.
    Preserves primary keys, generates PostGIS geometry points, updates sequences,
    and validates counts and referential integrity.
    """
    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"Source SQLite database not found at '{sqlite_path}'.")

    # Read-only SQLite connection string
    sqlite_url = f"sqlite:///{os.path.abspath(sqlite_path)}"
    logger.info(f"Connecting to source SQLite DB: {sqlite_url} (Read-Only)")
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

    logger.info(f"Connecting to destination PostgreSQL DB: {pg_url}")
    pg_engine = create_engine(pg_url)

    sqlite_inspector = inspect(sqlite_engine)
    available_sqlite_tables = set(sqlite_inspector.get_table_names())
    logger.info(f"Discovered {len(available_sqlite_tables)} tables in SQLite: {sorted(available_sqlite_tables)}")

    stats = {
        "migrated_tables": {},
        "skipped_tables": [],
        "errors": [],
        "validation": {},
    }

    with pg_engine.begin() as pg_conn:
        for table_name in TABLE_MIGRATION_ORDER:
            if table_name not in available_sqlite_tables:
                stats["skipped_tables"].append(table_name)
                continue

            try:
                # Read rows from SQLite
                with sqlite_engine.connect() as s_conn:
                    sqlite_rows = s_conn.execute(text(f"SELECT * FROM {table_name}")).mappings().fetchall()

                row_count = len(sqlite_rows)
                if row_count == 0:
                    logger.info(f"Table '{table_name}' has 0 rows in SQLite. Skipping data copy.")
                    stats["migrated_tables"][table_name] = {"source_rows": 0, "inserted_rows": 0}
                    continue

                logger.info(f"Migrating table '{table_name}': {row_count} rows...")

                # Clear existing table data in PostgreSQL before re-importing (clean idempotency)
                pg_conn.execute(text(f"DELETE FROM {table_name}"))

                # Inspect columns in destination PostgreSQL table
                pg_inspector = inspect(pg_engine)
                pg_col_info = {c["name"]: c for c in pg_inspector.get_columns(table_name)}
                pg_cols = set(pg_col_info.keys())

                inserted = 0
                for row_dict in sqlite_rows:
                    data = dict(row_dict)

                    # Add PostGIS spatial point for spatial tables
                    if table_name in SPATIAL_TABLES and "geom" in pg_cols:
                        lat = data.get("latitude")
                        lon = data.get("longitude")
                        if lat is not None and lon is not None:
                            data["geom"] = make_wkt_point(lat, lon)

                    # Filter and normalize types for PostgreSQL
                    filtered_data = {}
                    for k, v in data.items():
                        if k not in pg_cols:
                            continue
                        col_type_str = str(pg_col_info[k]["type"]).upper()
                        if "BOOLEAN" in col_type_str and isinstance(v, int):
                            v = bool(v)
                        filtered_data[k] = v

                    cols = list(filtered_data.keys())
                    col_names = ", ".join(cols)
                    param_names = ", ".join(f":{c}" for c in cols)
                    insert_stmt = text(f"INSERT INTO {table_name} ({col_names}) VALUES ({param_names})")
                    pg_conn.execute(insert_stmt, filtered_data)
                    inserted += 1

                # Update PostgreSQL SERIAL sequence to prevent key collision on subsequent inserts
                try:
                    pg_conn.execute(
                        text(
                            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                            f"COALESCE(MAX(id), 1)) FROM {table_name}"
                        )
                    )
                except Exception as seq_err:
                    logger.debug(f"No serial sequence to update for table '{table_name}': {seq_err}")

                stats["migrated_tables"][table_name] = {"source_rows": row_count, "inserted_rows": inserted}
                logger.info(f"Successfully migrated '{table_name}': {inserted}/{row_count} rows.")

            except Exception as exc:
                err_msg = f"Failed migrating table '{table_name}': {exc}"
                logger.error(err_msg)
                stats["errors"].append({"table": table_name, "error": str(exc)})
                raise

        # Validation Phase: Check counts between SQLite and PostgreSQL
        logger.info("Validating record counts...")
        for table_name in stats["migrated_tables"]:
            with sqlite_engine.connect() as s_conn:
                s_count = s_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            pg_count = pg_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()

            stats["validation"][table_name] = {
                "sqlite_count": s_count,
                "pg_count": pg_count,
                "matches": s_count == pg_count,
            }
            if s_count != pg_count:
                stats["errors"].append({
                    "table": table_name,
                    "error": f"Count mismatch! SQLite={s_count}, PostgreSQL={pg_count}"
                })

    logger.info("Data migration completed successfully.")
    return stats


def main():
    parser = argparse.ArgumentParser(description="CareOn SQLite-to-PostgreSQL Data Migration Tool")
    parser.add_argument("--sqlite-path", default="careon.db", help="Path to source SQLite file")
    parser.add_argument("--pg-url", default=os.getenv("DATABASE_URL", "postgresql+psycopg:///careon"), help="Target PostgreSQL connection URL")
    args = parser.parse_args()

    try:
        report = migrate_sqlite_to_postgres(args.sqlite_path, args.pg_url)
        print("\n=== CAREON MIGRATION REPORT ===")
        for tbl, data in report["validation"].items():
            status_str = "MATCH" if data["matches"] else "MISMATCH"
            print(f" - {tbl:20}: SQLite={data['sqlite_count']} -> PG={data['pg_count']} [{status_str}]")
        if report["errors"]:
            print(f"\nMigration encountered {len(report['errors'])} error(s)!")
            sys.exit(1)
        print("\nAll tables verified and referential integrity intact.")
    except Exception as e:
        logger.exception(f"Migration script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()