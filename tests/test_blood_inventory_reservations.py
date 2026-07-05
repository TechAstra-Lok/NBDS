import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import BloodBank, BloodInventory, BloodReservation


def test_inventory_and_reservation_flow():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()

        bank = BloodBank(name='Test Bank', province='Bagmati Pradesh', district='Kathmandu', city='Kathmandu', is_active=True)
        db.session.add(bank)
        db.session.commit()

        inventory = BloodInventory(
            blood_bank_id=bank.id,
            blood_group='O+',
            component='Whole Blood',
            units_available=10,
            units_reserved=2,
            minimum_stock=4,
            maximum_stock=20,
        )
        db.session.add(inventory)
        db.session.commit()

        reservation = BloodReservation(
            blood_bank_id=bank.id,
            hospital_name='Test Hospital',
            patient_name='Asha',
            blood_group='O+',
            component='Whole Blood',
            units=2,
            priority='high',
            status='pending',
        )
        db.session.add(reservation)
        db.session.commit()

        saved_inventory = BloodInventory.query.filter_by(blood_bank_id=bank.id, blood_group='O+').first()
        saved_reservation = BloodReservation.query.filter_by(blood_bank_id=bank.id).first()

        assert saved_inventory is not None
        assert saved_inventory.available_units == 8
        assert saved_reservation is not None
        assert saved_reservation.status == 'pending'
