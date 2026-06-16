#!/usr/bin/env python3
"""
Nepali Blood Donors Society - Application Entry Point
Run: python run.py
"""

import os
import sys
from flask.cli import FlaskGroup
from app import create_app, db

# Create app
app = create_app(os.environ.get('FLASK_ENV', 'development'))
cli = FlaskGroup(create_app=create_app)


# ── Shell Context ──────────────────────────────
@app.shell_context_processor
def make_shell_context():
    from app.models import User, Donor, BloodRequest, News, Notice, Advertisement, Contact
    return {
        'db': db,
        'User': User,
        'Donor': Donor,
        'BloodRequest': BloodRequest,
        'News': News,
        'Notice': Notice,
        'Advertisement': Advertisement,
        'Contact': Contact,
    }


# ── CLI Commands ───────────────────────────────
@cli.command('create-admin')
def create_admin():
    """Create a new admin user"""
    from app.models import User
    
    print("Create Admin User")
    print("-" * 30)
    username = input("Username: ").strip()
    email    = input("Email: ").strip()
    password = input("Password: ").strip()
    role     = input("Role (admin/superadmin) [admin]: ").strip() or 'admin'
    
    if User.query.filter_by(username=username).first():
        print(f"User '{username}' already exists!")
        return
    
    user = User(username=username, email=email, full_name=username.title(), role=role)
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    print(f"Admin '{username}' created successfully!")


@cli.command('reset-db')
def reset_db():
    """Reset and recreate the database"""
    confirm = input("This will DELETE all data. Type 'yes' to confirm: ")
    if confirm.lower() == 'yes':
        db.drop_all()
        db.create_all()
        print("Database reset successfully!")
    else:
        print("Cancelled.")


@cli.command('seed-demo')
def seed_demo():
    """Seed demo data for testing"""
    from app.models import Donor, BloodRequest, News
    from datetime import date, timedelta
    import random
    
    # Sample donors
    demo_donors = [
        ('Ramesh Sharma', 28, 'A+', 'Kathmandu', 'Baneshwor', 'regular', '9841234567'),
        ('Sunita Poudel', 25, 'O+', 'Lalitpur', 'Patan', 'occasional', '9851234567'),
        ('Bikash KC', 32, 'B+', 'Bhaktapur', 'Thimi', 'emergency', '9861234567'),
        ('Priya Thapa', 22, 'AB+', 'Kathmandu', 'Thamel', 'regular', '9841111111'),
        ('Arjun Rai', 35, 'O-', 'Pokhara', 'Lakeside', 'regular', '9841222222'),
        ('Sita Gurung', 27, 'A-', 'Biratnagar', 'Morang', 'occasional', '9841333333'),
    ]
    
    added = 0
    for name, age, bg, district, city, dtype, phone in demo_donors:
        if not Donor.query.filter_by(phone1=phone).first():
            d = Donor(
                full_name=name, age=age, blood_group=bg,
                curr_province='Bagmati Pradesh', curr_district=district, curr_city=city,
                perm_province='Bagmati Pradesh', perm_district=district, perm_city=city,
                phone1=phone, donor_type=dtype, weight=65,
                donation_times=random.randint(0, 10),
                last_donation_date=date.today() - timedelta(days=random.randint(30, 365)),
            )
            db.session.add(d)
            added += 1
    
    # Sample blood requests
    demo_requests = [
        ('Mohan Basnet', 'B+', 'Bir Hospital, Kathmandu', 'Kidney surgery', '9841000001'),
        ('Kamala Adhikari', 'O-', 'Teaching Hospital, Kathmandu', 'Emergency delivery', '9841000002'),
        ('Ram Lal', 'AB+', 'Norvic Hospital, Kathmandu', 'Thalassemia', '9841000003'),
    ]
    
    for patient, bg, hospital, case, phone in demo_requests:
        if not BloodRequest.query.filter_by(contact_number=phone).first():
            r = BloodRequest(
                patient_name=patient, blood_group=bg, hospital=hospital,
                case_details=case, contact_person='Family Member',
                contact_number=phone, units_needed=2,
                request_message=f'Urgent {bg} blood needed for {patient}. {case} at {hospital}.',
                is_emergency=True
            )
            db.session.add(r)
    
    db.session.commit()
    print(f"Demo data seeded! Added {added} donors + {len(demo_requests)} requests.")


if __name__ == '__main__':
    cli()