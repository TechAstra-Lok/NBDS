import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import BloodBank, BloodInventory, BloodInventoryMovement


def test_inventory_movement_and_expiry_tracking():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()

        bank = BloodBank(name='Lifecycle Bank', province='Bagmati Pradesh', district='Kathmandu', city='Kathmandu', is_active=True)
        db.session.add(bank)
        db.session.commit()

        inventory = BloodInventory(
            blood_bank_id=bank.id,
            blood_group='O+',
            component='Whole Blood',
            units_available=10,
            units_reserved=0,
            minimum_stock=3,
            maximum_stock=20,
            expiry_date='2026-12-31',
        )
        db.session.add(inventory)
        db.session.commit()

        movement = BloodInventoryMovement(
            inventory_id=inventory.id,
            movement_type='received',
            units=5,
            note='Initial stock',
        )
        db.session.add(movement)
        db.session.commit()

        saved_inventory = BloodInventory.query.get(inventory.id)
        saved_movement = BloodInventoryMovement.query.filter_by(inventory_id=inventory.id).first()

        assert saved_inventory.expiry_date == '2026-12-31'
        assert saved_movement.movement_type == 'received'
        assert saved_movement.units == 5
