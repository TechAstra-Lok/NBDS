import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import BloodBank


def test_blood_bank_creation_and_status():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()

        bank = BloodBank(
            name='Nepal Red Cross Blood Bank',
            province='Bagmati Pradesh',
            district='Kathmandu',
            city='Kathmandu',
            is_active=True,
            service_type='Hospital Blood Bank',
            emergency_available=True,
        )
        db.session.add(bank)
        db.session.commit()

        saved = BloodBank.query.filter_by(name='Nepal Red Cross Blood Bank').first()
        assert saved is not None
        assert saved.status == 'active'
        assert saved.display_name == 'Nepal Red Cross Blood Bank'
