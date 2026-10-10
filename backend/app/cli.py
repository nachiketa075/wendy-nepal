"""Owner account management.

    python -m app.cli create-owner owner@example.com
    python -m app.cli set-password owner@example.com

The password is read from an interactive prompt (or the OWNER_PASSWORD
environment variable for scripted setups). It is never given a default.
"""

import argparse
import getpass
import os
import sys

from sqlalchemy import delete, func, select

from .database import SessionLocal
from .models import Owner, OwnerSession
from .security import MIN_PASSWORD_LENGTH, hash_password


def _read_password() -> str:
    password = os.environ.get("OWNER_PASSWORD")
    if password is None:
        password = getpass.getpass("New owner password: ")
        if getpass.getpass("Repeat password: ") != password:
            sys.exit("Passwords do not match.")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Wendy Juice Shop owner accounts")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("create-owner", "set-password"):
        sub.add_parser(name).add_argument("email")
    args = parser.parse_args()
    email = args.email.strip().lower()
    if "@" not in email:
        sys.exit("Please give a valid email address.")

    with SessionLocal() as db:
        owner = db.scalar(select(Owner).where(func.lower(Owner.email) == email))
        if args.command == "create-owner":
            if owner is not None:
                sys.exit("An owner with that email already exists. Use set-password to change the password.")
            db.add(Owner(email=email, password_hash=hash_password(_read_password())))
            db.commit()
            print(f"Owner account created for {email}.")
        else:
            if owner is None:
                sys.exit("No owner with that email.")
            owner.password_hash = hash_password(_read_password())
            # Sign out everywhere when the password changes.
            db.execute(delete(OwnerSession).where(OwnerSession.owner_id == owner.id))
            db.commit()
            print(f"Password updated for {email}; existing sessions were signed out.")


if __name__ == "__main__":
    main()
