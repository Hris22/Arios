import os
import getpass
from src.database import SessionLocal
from src import models
from src.services import get_password_hash

def create_admin():
    db = SessionLocal()
    
    email = os.environ.get("ADMIN_EMAIL") or input("Enter admin email [admin@example.com]: ") or "admin@example.com"
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Enter admin password: ")
    
    if not password:
        print("Password cannot be empty.")
        db.close()
        return

    # Check if the user already exists to avoid duplicate entries
    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        print(f"User '{email}' already exists!")
        db.close()
        return
        
    print(f"Creating admin user: {email}...")
    admin_user = models.User(
        email=email,
        hashed_password=get_password_hash(password),
        role=models.RoleType.ADMIN
    )
    
    db.add(admin_user)
    db.commit()
    db.close()
    print(f"Admin user created successfully! You can now log in with '{email}'.")

if __name__ == "__main__":
    create_admin()