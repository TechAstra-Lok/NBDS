import sys
import io
from app import create_app, db
from app.models import BloodBank, BloodReservation

app = create_app()
with app.test_client() as client:
    with app.app_context():
        # Find a valid provisioned blood bank
        bank = BloodBank.query.filter(BloodBank.tenant_id.isnot(None)).first()
        if not bank:
            print("No provisioned blood bank found")
            sys.exit(1)
        
        print(f"Testing reservation for Blood Bank: {bank.id} ({bank.tenant_id})")

    response = client.post(
        f'/blood-banks/{bank.id}/reserve',
        data={
            'hospital_name': 'Integration Test Hospital',
            'patient_name': 'John Doe',
            'blood_group': 'B+',
            'component': 'Whole Blood',
            'units': '2',
            'priority': 'normal',
            'hospital_paper': (io.BytesIO(b"test"), 'test.jpg') # Dummy file to pass validation
        },
        content_type='multipart/form-data'
    )
    
    print(f"Response status: {response.status_code}")
    
    with app.app_context():
        # Check main DB
        main_res = BloodReservation.query.filter_by(hospital_name='Integration Test Hospital').all()
        print(f"Found {len(main_res)} in main DB")
        
        # Check tenant DB
        from app.services.tenant_service import TenantResolutionService
        TenantResolutionService.resolve_tenant(bank.tenant_id)
        tenant_res = BloodReservation.query.filter_by(hospital_name='Integration Test Hospital').all()
        print(f"Found {len(tenant_res)} in tenant DB ({bank.tenant_id})")
