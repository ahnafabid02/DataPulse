"""Interactive operator bootstrap: python -m datapulse.central.admin [--reset]."""

import argparse
from getpass import getpass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from datapulse.central.access import initialize_admin
from datapulse.central.config import Settings
from datapulse.central.db import build_engine, database_ready


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or recover the local demo administrator")
    parser.add_argument(
        "--reset", action="store_true", help="Reset an existing administrator password"
    )
    args = parser.parse_args()
    username = input("Administrator username: ").strip()
    password = getpass("New password (12–128 characters, hidden): ")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords did not match.")
    engine = build_engine(Settings())
    try:
        if not database_ready(engine):
            raise SystemExit("Database is not ready. Apply migrations first.")
        with Session(engine) as session, session.begin():
            initialize_admin(session, username, password, reset=args.reset)
        print("Administrator saved. Sign in to the local DataPulse workspace.")
    except ValueError as error:
        raise SystemExit(str(error)) from None
    except SQLAlchemyError:
        raise SystemExit("Administrator could not be saved. Check database readiness.") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
