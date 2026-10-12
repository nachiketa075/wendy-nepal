"""Administration commands.

    python -m app.cli create-owner owner@example.com --name "Owner Name"
    python -m app.cli set-password someone@example.com
    python -m app.cli import-menu [--apply] [--hide-legacy] [--file path.json]
    python -m app.cli purge-rate-limits

Owner accounts can only be created here, by someone with access to the server.
Passwords are read from an interactive prompt (or the OWNER_PASSWORD environment
variable for scripted setups) and are never given a default.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

from sqlalchemy import select

from .database import SessionLocal
from .models import Account
from .rate_limit import limiter
from .security import MIN_PASSWORD_LENGTH, hash_password, revoke_sessions


def _read_password() -> str:
    password = os.environ.get("OWNER_PASSWORD")
    if password is None:
        password = getpass.getpass("New password: ")
        if getpass.getpass("Repeat password: ") != password:
            sys.exit("Passwords do not match.")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Wendy Juice Shop administration")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-owner", help="Create an owner account")
    create.add_argument("email")
    create.add_argument("--name", default="Owner")
    sub.add_parser("set-password", help="Set a new password for any account").add_argument("email")
    menu = sub.add_parser("import-menu", help="Import the printed menu into the database (dry run by default)")
    menu.add_argument("--apply", action="store_true", help="Write the changes. Without this, only a summary is shown.")
    menu.add_argument("--hide-legacy", action="store_true", help="Hide older listing-based items from the public menu.")
    menu.add_argument("--file", type=Path, default=None)
    sub.add_parser("purge-rate-limits", help="Delete expired rate-limit records")
    args = parser.parse_args()

    if args.command == "purge-rate-limits":
        limiter.purge_expired()
        print("Expired rate-limit records removed.")
        return

    with SessionLocal() as db:
        if args.command == "import-menu":
            from .menu_import import DEFAULT_FILE, import_menu

            summary = import_menu(db, args.file or DEFAULT_FILE, apply=args.apply, hide_legacy=args.hide_legacy)
            print("\n".join(summary.lines()))
            return

        email = args.email.strip().lower()
        if "@" not in email:
            sys.exit("Please give a valid email address.")
        account = db.scalar(select(Account).where(Account.email == email))
        if args.command == "create-owner":
            if account is not None:
                sys.exit("An account with that email already exists. Use set-password to change its password.")
            db.add(Account(email=email, password_hash=hash_password(_read_password()), role="owner",
                           full_name=args.name.strip() or "Owner", permissions=[]))
            db.commit()
            print(f"Owner account created for {email}.")
        else:
            if account is None:
                sys.exit("No account with that email.")
            account.password_hash = hash_password(_read_password())
            revoke_sessions(db, account.id)  # sign out everywhere when the password changes
            db.commit()
            print(f"Password updated for {email} ({account.role}); existing sessions were signed out.")


if __name__ == "__main__":
    main()
