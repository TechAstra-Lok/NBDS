import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import BloodBank
from app.seed_blood_banks import seed_blood_banks


def test_seed_blood_banks_creates_filterable_directory_entries():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()

        inserted_count = seed_blood_banks()

        assert inserted_count >= 10
        bank = BloodBank.query.filter_by(province='Bagmati Pradesh', district='Kathmandu').first()
        assert bank is not None
        assert bank.contact_number or bank.phone
        assert bank.maps_url is not None

        emergency_bank = BloodBank.query.filter_by(is_emergency_panel=True).first()
        assert emergency_bank is not None


def test_public_blood_banks_page_lists_seeded_entries_and_map_links():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()

    with app.test_client() as client:
        response = client.get('/blood-banks')

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'Central Blood Transfusion Service' in html
        assert 'Open Map' in html
