import sys, os
sys.path.insert(0, os.path.abspath('.'))

import pytest
from app import create_app, db
from app.models import (
    User, Donor, BloodRequest, BloodBank, BloodInventory,
    BloodReservation, BloodBankAccount
)
from app.services.auth_service import AuthService
from datetime import datetime, date, timedelta
import random

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_visitor_blood_request_without_login(client, app):
    """Phase 8: Visitor posts blood request without login."""
    unique_phone = '98' + str(random.randint(10000000, 99999999))
    unique_name = f"Patient {random.randint(100000, 999999)}"
    data = {
        'patient_name': unique_name,
        'case_details': 'Accident Emergency Case',
        'blood_group': 'O+',
        'required_component': 'Whole Blood',
        'units_needed': 2,
        'hospital': 'Bir Hospital',
        'province': 'Bagmati Pradesh',
        'district': 'Kathmandu',
        'local_level': 'Kathmandu Metropolitan',
        'contact_person': 'Hari Prasad',
        'contact_number': unique_phone,
        'pin': '1234',
        'confirm_pin': '1234',
        'is_emergency': True,
    }
    resp = client.post('/blood-request', data=data, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        req = BloodRequest.query.filter_by(contact_number=unique_phone).first()
        assert req is not None
        assert req.blood_group == 'O+'
        assert req.status == 'active'

def test_donor_registration_and_login(client, app):
    """Phase 6 & 11: Donor registration, PIN hash, login, profile view."""
    unique_phone = '98' + str(random.randint(10000000, 99999999))
    unique_name = f"Donor {random.randint(100000, 999999)}"
    reg_data = {
        'full_name': unique_name,
        'phone1': unique_phone,
        'pin': '5678',
        'confirm_pin': '5678',
        'age': 30,
        'weight': 68,
        'curr_province': 'Bagmati Pradesh',
        'curr_district': 'Kathmandu',
        'curr_local_level': 'Kathmandu Metropolitan',
        'blood_group': 'AB+',
        'donor_type': 'regular',
        'consent': True,
    }
    resp = client.post('/become-donor', data=reg_data, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        donor = Donor.query.filter_by(phone1=unique_phone).first()
        assert donor is not None
        assert donor.check_pin('5678') is True
        assert donor.donor_id.startswith('NBD-')
        donor_id = donor.donor_id

    # Test donor login
    login_data = {
        'login_id': unique_phone,
        'pin': '5678',
    }
    resp_login = client.post('/donor/login', data=login_data, follow_redirects=True)
    assert resp_login.status_code == 200

    # Test donor profile access
    resp_profile = client.get(f'/donor/{donor_id}')
    assert resp_profile.status_code == 200
    assert unique_name.encode() in resp_profile.data

def test_donor_availability_state_machine(app):
    """Phase 12: Availability engine calculations."""
    with app.app_context():
        # Donor who donated yesterday -> recently_donated
        d1 = Donor(
            full_name='Recent Donor',
            phone1='98' + str(random.randint(10000000, 99999999)),
            pin_hash='dummy',
            age=25,
            curr_province='Bagmati Pradesh',
            curr_district='Kathmandu',
            curr_local_level='KTM',
            blood_group='A+',
            donor_type='regular',
            last_donation_date=date.today() - timedelta(days=10)
        )
        status, date_after = d1.calculate_availability()
        assert status == 'recently_donated'
        assert date_after is not None

        # Donor who donated 100 days ago -> available
        d2 = Donor(
            full_name='Available Donor',
            phone1='98' + str(random.randint(10000000, 99999999)),
            pin_hash='dummy',
            age=25,
            curr_province='Bagmati Pradesh',
            curr_district='Kathmandu',
            curr_local_level='KTM',
            blood_group='A+',
            donor_type='regular',
            last_donation_date=date.today() - timedelta(days=100)
        )
        status2, date_after2 = d2.calculate_availability()
        assert status2 == 'available'
        assert date_after2 is None

def test_bloodbank_independent_authentication(client, app):
    """Phase 6C & 9: Blood bank separate auth from admin."""
    with app.app_context():
        bank = BloodBank.query.first()
        if not bank:
            bank = BloodBank(
                name='Test Central Bank',
                hospital_name='Test Hospital',
                province='Bagmati Pradesh',
                district='Kathmandu',
                city='Kathmandu',
                status='active',
                is_active=True
            )
            db.session.add(bank)
            db.session.commit()

        account = BloodBankAccount.query.filter_by(blood_bank_id=bank.id).first()
        raw_pwd = 'Password@1234'
        if not account:
            account, raw_pwd = AuthService.create_blood_bank_account(bank.id, 'BAG', 'KTM')
            account.password_change_required = False
            account.account_status = 'active'
            db.session.commit()
        else:
            account.set_password(raw_pwd)
            account.password_change_required = False
            account.account_status = 'active'
            db.session.commit()

        login_id = account.login_id

    # Test login
    resp = client.post('/bloodbank/login', data={'login_id': login_id, 'password': raw_pwd}, follow_redirects=True)
    assert resp.status_code == 200

    # Test dashboard access
    dash_resp = client.get('/bloodbank/dashboard')
    assert dash_resp.status_code == 200

def test_public_blood_bank_and_reservation_flow(client, app):
    """Phase 7 & 9: Public blood bank view and reservation page availability."""
    with app.app_context():
        bank = BloodBank.query.first()
        bank_id = bank.id

    # 1. Directory
    r1 = client.get('/blood-banks')
    assert r1.status_code == 200

    # 2. Detail
    r2 = client.get(f'/blood-banks/{bank_id}')
    assert r2.status_code == 200

    # 3. Reserve page GET
    r3 = client.get(f'/blood-banks/{bank_id}/reserve')
    assert r3.status_code == 200
