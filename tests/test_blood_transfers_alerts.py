import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import BloodBank, BloodInventory, BloodTransfer, LowStockAlert


def test_transfer_and_alert_creation():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()

        source = BloodBank(name='Source Bank', province='Bagmati Pradesh', district='Kathmandu', city='Kathmandu', is_active=True)
        target = BloodBank(name='Target Bank', province='Bagmati Pradesh', district='Lalitpur', city='Lalitpur', is_active=True)
        db.session.add_all([source, target])
        db.session.commit()

        inventory = BloodInventory(blood_bank_id=source.id, blood_group='A+', component='Whole Blood', units_available=3, units_reserved=0, minimum_stock=4, maximum_stock=20)
        db.session.add(inventory)
        db.session.commit()

        transfer = BloodTransfer(
            source_bank_id=source.id,
            destination_bank_id=target.id,
            blood_group='A+',
            component='Whole Blood',
            units=2,
            status='pending',
        )
        db.session.add(transfer)
        db.session.commit()

        alert = LowStockAlert(
            blood_bank_id=source.id,
            blood_group='A+',
            component='Whole Blood',
            severity='warning',
            message='Low stock',
        )
        db.session.add(alert)
        db.session.commit()

        saved_transfer = BloodTransfer.query.filter_by(source_bank_id=source.id, destination_bank_id=target.id).first()
        saved_alert = LowStockAlert.query.filter_by(blood_bank_id=source.id).first()

        assert saved_transfer is not None
        assert saved_transfer.units == 2
        assert saved_alert is not None
        assert saved_alert.severity == 'warning'
