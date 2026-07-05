import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import BloodBank, BloodInventory, BloodReservation
from app.utils import generate_qr_code, verify_qr_code


def test_qr_code_generation_and_verification():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()

        bank = BloodBank(name='QR Bank', province='Bagmati Pradesh', district='Kathmandu', city='Kathmandu', is_active=True)
        db.session.add(bank)
        db.session.commit()

        inventory = BloodInventory(blood_bank_id=bank.id, blood_group='AB+', component='Whole Blood', units_available=5, units_reserved=0, minimum_stock=2, maximum_stock=10, expiry_date='2026-12-31')
        db.session.add(inventory)
        db.session.commit()

        reservation = BloodReservation(
            blood_bank_id=bank.id,
            hospital_name='Test Hospital',
            patient_name='Jane Doe',
            blood_group='AB+',
            component='Whole Blood',
            units=2,
            priority='urgent',
            status='pending',
        )
        db.session.add(reservation)
        db.session.commit()

        inventory.qr_code = generate_qr_code('inventory', inventory.id)
        reservation.qr_code = generate_qr_code('reservation', reservation.id)
        db.session.commit()

        verified_inventory = verify_qr_code(inventory.qr_code)
        verified_reservation = verify_qr_code(reservation.qr_code)

        assert inventory.qr_code.startswith('INV-')
        assert reservation.qr_code.startswith('RES-')
        assert verified_inventory['type'] == 'inventory'
        assert verified_inventory['id'] == inventory.id
        assert verified_reservation['type'] == 'reservation'
        assert verified_reservation['id'] == reservation.id
