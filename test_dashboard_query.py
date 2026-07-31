import sys
from app import create_app, db
from app.models import BloodBankAccount, BloodReservation
from app.services.tenant_service import TenantResolutionService
from flask import g

app = create_app()
with app.app_context():
    account = BloodBankAccount.query.get(1) # BBB-KOS-JHA-001 for BB 88
    if not account:
        print("Account not found")
        sys.exit(1)
        
    print(f"Resolving tenant {account.blood_bank.tenant_id} for bank {account.blood_bank_id}")
    TenantResolutionService.resolve_tenant(account.blood_bank.tenant_id)
    
    res = BloodReservation.query.filter_by(blood_bank_id=account.blood_bank_id).all()
    print(f"Reservations found for BB {account.blood_bank_id}: {len(res)}")
    for r in res:
        print(f" - ID: {r.id}, Hospital: {r.hospital_name}, Status: {r.status}")
