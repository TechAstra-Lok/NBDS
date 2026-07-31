from app import create_app, db
from app.models import BloodBank, BloodReservation
from app.services.tenant_service import TenantResolutionService
from flask import g

app = create_app()
with app.app_context():
    bank = BloodBank.query.get(89)
    print(f"Bank: {bank.display_name}, tenant: {bank.tenant_id}")
    
    TenantResolutionService.resolve_tenant(bank.tenant_id)
    print(f"Tenant Engine: {g.tenant_engine}")
    
    res = BloodReservation(
        blood_bank_id=bank.id,
        hospital_name="Test Hospital",
        patient_name="Test Patient",
        blood_group="A+",
        component="Whole Blood",
        units=1,
        priority="normal",
        status="pending"
    )
    db.session.add(res)
    db.session.commit()
    print(f"Reservation ID: {res.id}")
