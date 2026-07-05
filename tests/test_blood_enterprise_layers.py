import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import BloodBank, BloodInventory, Notification, AuditLog
from app.routes.admin import create_inventory_notifications, log_audit_event, build_blood_inventory_report


def test_notification_audit_and_report_layers():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()

        bank = BloodBank(name='Enterprise Bank', province='Bagmati Pradesh', district='Kathmandu', city='Kathmandu', is_active=True)
        db.session.add(bank)
        db.session.commit()

        inventory = BloodInventory(
            blood_bank_id=bank.id,
            blood_group='A+',
            component='Whole Blood',
            units_available=2,
            units_reserved=0,
            minimum_stock=4,
            maximum_stock=20,
            expiry_date=(date.today() + timedelta(days=10)).strftime('%Y-%m-%d'),
        )
        db.session.add(inventory)
        db.session.commit()

        notifications = create_inventory_notifications(inventory)
        log_audit_event('inventory_created', inventory.id, 'Inventory created', actor='admin')
        db.session.commit()

        report = build_blood_inventory_report(bank.id)

        assert len(notifications) >= 1
        assert Notification.query.filter_by(category='low_stock').count() >= 1
        assert AuditLog.query.filter_by(action='inventory_created').count() >= 1
        assert report['inventory_count'] == 1
        assert report['low_stock_count'] >= 1
        assert report['expiring_soon_count'] >= 1
