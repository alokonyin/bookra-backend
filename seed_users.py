from app.database import SessionLocal
from app.models import User, RoleEnum  
from app.security import hash_password      

def seed_users():
    db = SessionLocal()

    # Optional: clear existing ones (only for dev)
    emails = [
        "admin@bookra.com",
        "admin@trinity.co.ke",
        "anyuon@gmail.com",
    ]
    db.query(User).filter(User.email.in_(emails)).delete(synchronize_session=False)

    # --- Admin ---
    admin = User(
        name="Platform Admin",
        email="admin@bookra.com",
        password_hash=hash_password("admin123"),
        role=RoleEnum.admin,
    )

    # --- Operator ---
    operator = User(
        name="Trinity Operator",
        email="admin@trinity.co.ke",
        password_hash=hash_password("trinity"),
        role=RoleEnum.operator,
        company_name="Trinity Co. Ltd",
    )

    # --- Traveler ---
    traveler = User(
        name="Anyuon",
        email="anyuon@gmail.com",
        password_hash=hash_password("anyuon"),
        role=RoleEnum.traveler,
    )

    db.add_all([admin, operator, traveler])
    db.commit()

    print("✅ Seeded users:")
    for user in [admin, operator, traveler]:
        print(f" - {user.role.value.capitalize()}: {user.email}")

    db.close()

if __name__ == "__main__":
    seed_users()

