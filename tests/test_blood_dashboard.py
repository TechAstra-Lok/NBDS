import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import BloodBank, BloodInventory, BloodTransfer, LowStockAlert


def test_dashboard_analytics_summary():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()

        bank = BloodBank(name='Analytics Bank', province='Bagmati Pradesh', district='Kathmandu', city='Kathmandu', is_active=True)
        db.session.add(bank)
        db.session.commit()

        db.session.add(BloodInventory(blood_bank_id=bank.id, blood_group='A+', component='Whole Blood', units_available=2, units_reserved=0, minimum_stock=4, maximum_stock=20, expiry_date='2026-12-31'))
        db.session.add(BloodInventory(blood_bank_id=bank.id, blood_group='O+', component='Whole Blood', units_available=8, units_reserved=1, minimum_stock=4, maximum_stock=20, expiry_date='2026-11-30'))
        db.session.add(BloodTransfer(source_bank_id=bank.id, destination_bank_id=bank.id, blood_group='A+', component='Whole Blood', units=1, status='pending'))
        db.session.add(LowStockAlert(blood_bank_id=bank.id, blood_group='A+', component='Whole Blood', severity='warning', message='Low stock'))
        db.session.commit()

        from app.routes.admin import build_blood_bank_dashboard_summary

        summary = build_blood_bank_dashboard_summary(bank.id)

        assert summary['inventory_count'] == 2
        assert summary['low_stock_count'] == 1
        assert summary['pending_transfers'] == 1
        assert summary['critical_items'] >= 1
