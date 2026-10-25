"""CLI script to bootstrap or promote an admin user account.

Run via:
    py -m scripts.create_admin
or:
    python -m scripts.create_admin
"""

import getpass
import sys
from app.core.security import hash_password, validate_password_strength
from app.db.session import SessionLocal
from app.models.user import User


def main() -> None:
    """Prompt for credentials and create an admin user or promote an existing user."""
    print("=" * 60)
    print(" vision-api Admin Creation & Promotion Utility")
    print("=" * 60)

    email = input("Enter admin email: ").strip()
    if not email or "@" not in email:
        print("Error: A valid email address is required.")
        sys.exit(1)

    username = input("Enter admin username: ").strip()
    if not username:
        print("Error: Username cannot be blank.")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Check if a user with this email or username already exists
        existing_user = (
            db.query(User)
            .filter((User.email == email) | (User.username == username))
            .first()
        )

        if existing_user:
            print(f"\nUser found: id={existing_user.id}, username='{existing_user.username}', current_role='{existing_user.role}'")
            if existing_user.role == "admin":
                print("User is already an administrator. No changes made.")
                return

            confirm = input("User already exists. Promote to admin? [y/N]: ").strip().lower()
            if confirm in ("y", "yes"):
                existing_user.role = "admin"
                db.commit()
                print(f"Success: User '{existing_user.username}' has been promoted to 'admin'.")
            else:
                print("Promotion cancelled.")
            return

        # New admin creation: prompt for secure password with getpass until valid
        while True:
            password = getpass.getpass("Enter admin password: ")
            unmet_rules = validate_password_strength(password)
            if unmet_rules:
                print("Error: Password does not meet security requirements:")
                for rule in unmet_rules:
                    print(f"  - {rule}")
                continue

            password_confirm = getpass.getpass("Confirm admin password: ")
            if password != password_confirm:
                print("Error: Passwords do not match. Please try again.\n")
                continue

            break

        admin_user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(f"\nSuccess: Administrator account '{admin_user.username}' (ID: {admin_user.id}) created.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
