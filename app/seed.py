from app.models import Customer
import secrets
from app.db import Base, SessionLocal, engine 
from app.security import hash_code

def make_customer(account_id:str, name:str, overdue:int, dpd:int, pan_last4:str, birth_year:str, loan_type:str = "Personal Loan"):
    salt = secrets.token_hex(8)
    return Customer(
        account_id=  account_id,
        full_name = name,
        loan_type = loan_type,
        overdue_amount = overdue,
        dpd = dpd,
        salt = salt,
        pan_last4_hash = hash_code(pan_last4,salt),
        birth_year_hash = hash_code(birth_year, salt),
    )

def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(Customer).count():
            print("Already seeded")
            return 
        db.add_all(
            [
                 make_customer("ACC-88392ACC-88392", "Rahul Sharma", 8499, 12, "1234", "1995"),
                make_customer("ACC-77120", "Priya Nair", 12500, 5, "5678", "1990", "Two-wheeler Loan"),
            ]
        )
        db.commit()
        print("seeded 2 customers.")

if __name__ == "__main__":
    main()