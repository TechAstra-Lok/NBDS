import pytest
from app import create_app, db
from app.models import (
    BloodBank, BloodBankAccount, BloodReservation, BloodRequest,
    BloodBankNotification, BloodBankAlertSettings, SiteConfig
)
from app.services.bloodbank_alert_service import (
    haversine_distance, dispatch_reservation_alert, dispatch_nearby_request_alert
)

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app

@pytest.fixture
def client(app):
    return app.test_client()


# ── SEO Tests ───────────────────────────────────────────
def test_robots_txt(client):
    res = client.get('/robots.txt')
    assert res.status_code == 200
    assert 'text/plain' in res.headers.get('Content-Type', '')
    data = res.data.decode('utf-8')
    assert 'Disallow: /admin/' in data
    assert 'Disallow: /bloodbank/' in data
    assert 'Sitemap:' in data


def test_pwa_root_endpoints(client):
    # Test Service Worker
    res_sw = client.get('/sw.js')
    assert res_sw.status_code == 200
    assert 'javascript' in res_sw.headers.get('Content-Type', '')
    assert res_sw.headers.get('Service-Worker-Allowed') == '/'

    # Test Web App Manifest
    res_mf = client.get('/manifest.json')
    assert res_mf.status_code == 200
    assert 'manifest+json' in res_mf.headers.get('Content-Type', '')
    data = res_mf.get_json()
    assert data['display'] == 'standalone'
    assert len(data['icons']) >= 2


def test_sitemap_xml(client, app):
    with app.app_context():
        bank = BloodBank(
            name='Test Red Cross Central',
            province='Bagmati Pradesh',
            district='Kathmandu',
            is_active=True
        )
        db.session.add(bank)
        db.session.commit()

        res = client.get('/sitemap.xml')
        assert res.status_code == 200
        assert 'application/xml' in res.headers.get('Content-Type', '')
        data = res.data.decode('utf-8')
        assert '<urlset' in data
        assert f'/blood-banks/{bank.id}' in data
        assert '/blood-banks/location/bagmati' in data
        assert '/admin/' not in data
        assert '/bloodbank/' not in data


def test_location_seo_hub(client, app):
    with app.app_context():
        bank = BloodBank(
            name='Kathmandu Central Transfusion',
            province='Bagmati Pradesh',
            district='Kathmandu',
            is_active=True
        )
        db.session.add(bank)
        db.session.commit()

        res = client.get('/blood-banks/location/bagmati')
        assert res.status_code == 200
        data = res.data.decode('utf-8')
        assert 'Kathmandu Central Transfusion' in data
        assert 'MedicalOrganization' in data
        assert 'BreadcrumbList' in data


# ── Real-Time Alert & Notification Tests ────────────────
def test_haversine_distance():
    # Kathmandu (~27.7172, 85.3240) to Lalitpur (~27.6672, 85.3200) ≈ 5.5 km
    dist = haversine_distance(27.7172, 85.3240, 27.6672, 85.3200)
    assert dist is not None
    assert 4.0 <= dist <= 7.0

    # None handling
    assert haversine_distance(None, 85.0, 27.0, 85.0) is None


def test_dispatch_reservation_alert(app):
    with app.app_context():
        bank = BloodBank(name='Tribhuvan University Teaching Hospital Blood Bank', is_active=True)
        db.session.add(bank)
        db.session.commit()

        resv = BloodReservation(
            blood_bank_id=bank.id,
            hospital_name='Teaching Hospital',
            patient_name='Ram Bahadur',
            blood_group='O+',
            units=2,
            priority='emergency',
            status='pending'
        )
        db.session.add(resv)
        db.session.commit()

        notif = dispatch_reservation_alert(resv)
        assert notif is not None
        assert notif.notification_type == 'RESERVATION'
        assert notif.blood_bank_id == bank.id
        assert notif.priority == 'EMERGENCY'
        assert notif.is_read is False

        # Test deduplication
        dup = dispatch_reservation_alert(resv)
        assert dup is not None
        assert dup.id == notif.id
        total = BloodBankNotification.query.filter_by(blood_bank_id=bank.id).count()
        assert total == 1


def test_dispatch_nearby_request_alert(app):
    with app.app_context():
        bank = BloodBank(
            name='Bir Hospital Blood Bank',
            province='Bagmati Pradesh',
            district='Kathmandu',
            latitude=27.7050,
            longitude=85.3140,
            is_active=True
        )
        db.session.add(bank)
        db.session.commit()

        # Request at Civil Hospital (~27.6880, 85.3350) ≈ 2.8 km away
        req = BloodRequest(
            patient_name='Hari Maya',
            blood_group='B+',
            case_details='Accident Trauma',
            hospital='Civil Hospital, Kathmandu',
            province='Bagmati Pradesh',
            district='Kathmandu',
            contact_person='Ram Kumar',
            contact_number='9841234567',
            latitude=27.6880,
            longitude=85.3350,
            is_emergency=True
        )
        db.session.add(req)
        db.session.commit()

        notified = dispatch_nearby_request_alert(req)
        assert notified >= 1

        notif = BloodBankNotification.query.filter_by(
            blood_bank_id=bank.id,
            notification_type='NEARBY_REQUEST'
        ).first()
        assert notif is not None
        assert 'Hari Maya' in notif.message
        assert notif.priority == 'EMERGENCY'


def test_bloodbank_notifications_and_settings(client, app):
    with app.app_context():
        bank = BloodBank(name='Bhaktapur Blood Bank', is_active=True)
        db.session.add(bank)
        db.session.commit()

        import random
        rnd = random.randint(1000, 9999)
        acct = BloodBankAccount(
            blood_bank_id=bank.id,
            login_id=f'bb_bhaktapur_{rnd}',
            account_status='active'
        )
        acct.set_password('Pass@12345')
        db.session.add(acct)

        notif = BloodBankNotification(
            blood_bank_id=bank.id,
            notification_type='RESERVATION',
            title='Test Reservation',
            message='Test message',
            priority='HIGH'
        )
        db.session.add(notif)
        db.session.commit()

        with client.session_transaction() as sess:
            sess['bloodbank_account_id'] = acct.id
            sess['bloodbank_login_id'] = acct.login_id
            sess['bloodbank_bank_name'] = bank.name

        # 1. Notification Center
        res = client.get('/bloodbank/notifications')
        assert res.status_code == 200
        assert 'Test Reservation' in res.data.decode('utf-8')

        # 2. Mark read
        res_read = client.post(f'/bloodbank/notifications/{notif.id}/read', headers={'X-Requested-With': 'XMLHttpRequest'})
        assert res_read.status_code == 200

        # 3. Fallback Polling API
        res_poll = client.get('/bloodbank/api/notifications/poll')
        assert res_poll.status_code == 200
        json_data = res_poll.get_json()
        assert json_data['status'] == 'ok'

        # 4. Alert Settings Update
        res_settings = client.post('/bloodbank/settings/alerts', data={
            'reservation_alerts_enabled': '1',
            'nearby_request_alerts_enabled': '1',
            'alert_radius_km': '30',
            'blood_groups': ['A+', 'O+'],
            'sound_enabled': '1',
            'push_enabled': '1'
        }, follow_redirects=True)
        assert res_settings.status_code == 200

        saved = BloodBankAlertSettings.query.filter_by(blood_bank_id=bank.id).first()
        assert saved is not None
        assert saved.alert_radius_km == 30
        assert 'A+' in saved.alert_blood_groups
