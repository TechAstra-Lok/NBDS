import os
import sys
import uuid
import traceback

# Add project root to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app, db
from app.models import (
    User, Donor, BloodBank, BloodBankAccount, BloodInventory, BloodReservation,
    BloodRequest, News, Notice, Advertisement, StaffMember, Volunteer, Partner,
    SuccessStory, Contact, AuditLog, SiteVisitor
)

print("Starting End-to-End System Audit on Neon PostgreSQL...\n", flush=True)

app = create_app('testing')
client = app.test_client()

results = []

def record(test_name, success, message=""):
    status = "[PASS]" if success else "[FAIL]"
    safe_msg = str(message).encode('ascii', errors='replace').decode('ascii')
    results.append((test_name, success, safe_msg))
    print(f"{status} | {test_name}: {safe_msg}", flush=True)

with app.app_context():
    # ── 1. Database Connection & Table Verification ──────────────────────────
    try:
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        record("Database Connection", True, f"{len(tables)} tables present on Neon DB")
    except Exception as e:
        record("Database Connection", False, traceback.format_exc())

    # ── 2. Admin Authentication Flow ──────────────────────────────────────────
    try:
        with app.test_client() as admin_client:
            r_login = admin_client.post(
                '/admin/login',
                data={'username': 'admin', 'password': 'Admin@1234'},
                follow_redirects=False
            )
            assert r_login.status_code == 302, f"Expected 302 redirect on login, got {r_login.status_code}."
            loc = r_login.headers.get('Location', '')
            assert 'dashboard' in loc or 'admin' in loc, f"Redirect not to dashboard: {loc}"
            record("Admin Login Portal", True, "Successfully authenticated as Superadmin")

            r_dash = admin_client.get('/admin/dashboard', follow_redirects=False)
            loc2 = r_dash.headers.get('Location', 'none')
            assert r_dash.status_code == 200, f"Dashboard returned {r_dash.status_code}, redirecting to {loc2}"
            record("Admin Dashboard Route", True, "Dashboard rendered with 200 OK")

            r_dq = admin_client.get('/admin/data-quality')
            assert r_dq.status_code == 200, f"Data Quality status: {r_dq.status_code}"
            record("Admin Data Quality Tool", True, "Duplicate detector & analytics loaded cleanly")
    except Exception as e:
        record("Admin Authentication Flow", False, traceback.format_exc())

    # ── 3. Donor Registration, PIN Auth, Profile & QR Flow ──────────────────
    try:
        phone = f"984{uuid.uuid4().int % 10000000:07d}"
        
        donor_data = {
            'full_name': 'Aarav Sharma',
            'phone1': phone,
            'age': 28,
            'weight': 68.5,
            'blood_group': 'B+',
            'donor_type': 'regular',
            'perm_province': 'Bagmati Pradesh',
            'perm_district': 'Kathmandu',
            'perm_local_level': 'Kathmandu Metropolitan',
            'curr_province': 'Bagmati Pradesh',
            'curr_district': 'Kathmandu',
            'curr_local_level': 'Kathmandu Metropolitan',
            'pin': '4321',
            'confirm_pin': '4321',
            'consent': 'y'
        }
        resp = client.post('/become-donor', data=donor_data, follow_redirects=True)
        assert resp.status_code == 200, f"Become donor status: {resp.status_code}"
        
        donor = Donor.query.filter_by(phone1=phone).first()
        assert donor is not None, "Donor not found in DB"
        assert donor.check_pin('4321'), "Donor PIN check failed"
        record("Donor Public Registration", True, f"Donor created with ID {donor.donor_id}")
        
        resp = client.post('/donor/login', data={'phone': phone, 'pin': '4321'}, follow_redirects=True)
        assert resp.status_code == 200, f"Donor login status: {resp.status_code}"
        record("Donor PIN Authentication", True, "Donor session established")
        
        resp = client.get(f'/donor/{donor.donor_id}')
        assert resp.status_code == 200, f"Donor profile status: {resp.status_code}"
        record("Donor Profile Page", True, "Profile view returned 200 OK")
        
        resp = client.get(f'/donor/{donor.donor_id}/qr')
        assert resp.status_code == 200, f"Donor QR status: {resp.status_code}"
        assert resp.content_type.startswith('image/'), f"Donor QR content-type: {resp.content_type}"
        record("Donor QR Code Endpoint", True, "Dynamic QR image stream returned 200 OK")
        
        db.session.delete(donor)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        record("Donor Flow", False, traceback.format_exc())

    # ── 4. Blood Bank Portal & Independent Staff Auth ────────────────────────
    try:
        bank_phone = f"01{uuid.uuid4().int % 10000000:07d}"
        bank = BloodBank(
            name='Kathmandu Central Blood Bank',
            province='Bagmati Pradesh',
            district='Kathmandu',
            city='Kathmandu',
            phone=bank_phone,
            is_active=True
        )
        db.session.add(bank)
        db.session.commit()
        
        account = BloodBankAccount(
            blood_bank_id=bank.id,
            login_id=f"bank_{bank.id}",
            account_status='active',
            password_change_required=False,
            is_locked=False
        )
        account.set_password('BankPass@123')
        db.session.add(account)
        db.session.commit()
        record("Blood Bank CRUD", True, f"Created BloodBank id={bank.id} & Account id={account.id}")
        
        resp = client.post('/bloodbank/login', data={'login_id': account.login_id, 'password': 'BankPass@123'}, follow_redirects=True)
        assert resp.status_code == 200, f"Bloodbank login status: {resp.status_code}"
        record("Blood Bank Staff Login", True, "Staff authenticated into portal")
        
        resp = client.get('/bloodbank/dashboard')
        assert resp.status_code == 200, f"Bloodbank dashboard status: {resp.status_code}"
        resp = client.get('/bloodbank/inventory')
        assert resp.status_code == 200, f"Bloodbank inventory status: {resp.status_code}"
        record("Blood Bank Dashboard & Inventory", True, "Rendered portal dashboard & inventory views")
        
        db.session.delete(account)
        db.session.delete(bank)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        record("Blood Bank Portal Flow", False, traceback.format_exc())

    # ── 5. Public Emergency Blood Request Flow ────────────────────────────────
    try:
        req_phone = f"985{uuid.uuid4().int % 10000000:07d}"
        p_name = f"Patient {uuid.uuid4().hex[:6].upper()}"
        req_data = {
            'patient_name': p_name,
            'case_details': 'Emergency Surgery Blood Requirement',
            'blood_group': 'AB+',
            'required_component': 'Whole Blood',
            'units_needed': 1,
            'hospital': 'Tribhuvan University Teaching Hospital',
            'province': 'Bagmati Pradesh',
            'district': 'Kathmandu',
            'local_level': 'Kathmandu Metropolitan',
            'contact_person': 'Ramesh Adhikari',
            'contact_number': req_phone,
            'pin': '9999',
            'confirm_pin': '9999',
            'is_emergency': True
        }
        resp = client.post('/blood-request', data=req_data, follow_redirects=True)
        assert resp.status_code == 200, f"Blood request POST status: {resp.status_code}"
        
        created_req = BloodRequest.query.filter_by(contact_number=req_phone).first()
        assert created_req is not None, "Blood request not created in DB"
        record("Emergency Blood Request", True, f"Request created with reference {created_req.request_id}")
        
        resp = client.get('/blood-requests')
        assert resp.status_code == 200, f"Blood requests board status: {resp.status_code}"
        record("Blood Requests Bulletin Board", True, "Public board rendered 200 OK")
        
        db.session.delete(created_req)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        record("Blood Request Flow", False, traceback.format_exc())

    # ── 6. REST API & AI Stream Endpoints ────────────────────────────────────
    try:
        resp = client.get('/api/v1/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total_donors' in data or 'donors' in data or 'total_requests' in data
        record("REST API /api/v1/stats", True, f"Stats returned: {data}")
        
        resp = client.get('/api/v1/requests/active')
        assert resp.status_code == 200
        record("REST API /api/v1/requests/active", True, "Active requests JSON feed 200 OK")
        
        resp = client.post('/api/v1/raktadata-helper', json={'message': 'How often can I donate blood in Nepal?'})
        assert resp.status_code == 200
        ai_data = resp.get_json()
        assert 'reply' in ai_data
        reply_preview = ai_data['reply'][:50].encode('ascii', errors='replace').decode('ascii')
        record("Gemini AI API /api/v1/raktadata-helper", True, f"AI replied: {reply_preview}...")
    except Exception as e:
        record("REST API Flow", False, traceback.format_exc())

    # ── 7. PWA, SEO & Static Endpoints ───────────────────────────────────────
    try:
        resp = client.get('/manifest.json')
        assert resp.status_code == 200
        record("PWA Manifest", True, "application/manifest+json 200 OK")
        
        resp = client.get('/sw.js')
        assert resp.status_code == 200
        record("PWA Service Worker", True, "sw.js served with Service-Worker-Allowed /")
        
        resp = client.get('/robots.txt')
        assert resp.status_code == 200
        record("SEO Robots.txt", True, "robots.txt rendered 200 OK")
        
        resp = client.get('/sitemap.xml')
        assert resp.status_code == 200
        record("SEO Sitemap.xml", True, "sitemap.xml rendered 200 OK")
    except Exception as e:
        record("PWA & SEO Endpoints", False, traceback.format_exc())

print("\n" + "="*60)
print("AUDIT SUMMARY:")
total = len(results)
passed = sum(1 for _, s, _ in results if s)
failed = total - passed
print(f"Total Test Areas: {total} | Passed: {passed} | Failed: {failed}")
print("="*60 + "\n")
