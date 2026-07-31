import sys
from app import create_app, db
from app.models import BloodBankAccount, BloodReservation, BloodInventory
from app.services.tenant_service import TenantResolutionService
from flask import g

app = create_app()
with app.app_context():
    account = BloodBankAccount.query.get(1) # BBB-KOS-JHA-001 for BB 88
    TenantResolutionService.resolve_tenant(account.blood_bank.tenant_id)
    
    res = BloodReservation.query.filter_by(id=2, blood_bank_id=account.blood_bank_id).first()
    if not res:
        print("Reservation not found")
        sys.exit(1)
        
    print(f"Found reservation: {res.id}, Status: {res.status}")
    
    inventory = BloodInventory.query.filter_by(
        blood_bank_id=account.blood_bank_id, 
        blood_group=res.blood_group, 
        component=res.component
    ).first()
    
    if not inventory:
        print("Inventory not found!")
    else:
        print(f"Inventory before: Available {inventory.units_available}, Reserved {inventory.units_reserved}")
        
    if inventory and inventory.units_available >= res.units:
        inventory.units_available -= res.units
        inventory.units_reserved += res.units
        res.status = 'approved'
        db.session.commit()
        print(f"Inventory after: Available {inventory.units_available}, Reserved {inventory.units_reserved}")
    else:
        print("Not enough units")
