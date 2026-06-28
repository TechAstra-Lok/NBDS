import logging
from datetime import datetime, timedelta
from app.models import Donor, BloodRequest

logger = logging.getLogger(__name__)

def update_donor_availability(app):
    """
    Background job to auto-update donor status based on last_donation_date (90 days logic).
    If a donor is marked as 'recently_donated' and their 90-day period has passed,
    they are automatically moved back to 'available'.
    """
    with app.app_context():
        from app import db
        today = datetime.utcnow().date()
        
        # Donors who are currently 'recently_donated'
        recent_donors = Donor.query.filter_by(availability_status='recently_donated').all()
        updated_count = 0
        
        for donor in recent_donors:
            if donor.last_donation_date:
                eligible_date = donor.last_donation_date + timedelta(days=90)
                if today >= eligible_date:
                    donor.availability_status = 'available'
                    updated_count += 1
        
        if updated_count > 0:
            db.session.commit()
            logger.info(f"Auto-updated {updated_count} donors to 'available' status.")
        else:
            logger.info("No donors needed availability update today.")


def alert_matching_donors(app, request_id):
    """
    Intelligent Donor Alert System logic.
    Finds available donors matching the requested blood group in the same district/local level.
    """
    with app.app_context():
        # This would typically integrate with an SMS/Email gateway.
        # For now, it logs the matches.
        req = BloodRequest.query.get(request_id)
        if not req or req.status != 'active':
            return
            
        # Match logic: Same blood group, available, same district.
        # Can further filter by local_level and ward for tighter proximity.
        matches = Donor.query.filter(
            Donor.blood_group == req.blood_group,
            Donor.availability_status == 'available',
            Donor.curr_district == req.district
        ).all()
        
        logger.info(f"Alert System: Found {len(matches)} matching donors for Blood Request {req.request_id} in {req.district}.")
        
        # TODO: Trigger SMS or Email API to alert these matches.


def schedule_jobs(app, scheduler):
    """
    Configures and starts all APScheduler background jobs.
    """
    # Job 1: Run every day at midnight (or periodically) to update donor statuses
    scheduler.add_job(
        id='update_donor_availability_job',
        func=update_donor_availability,
        args=[app],
        trigger='interval',
        hours=24,
        next_run_time=datetime.now(), # Run immediately once on startup, then every 24h
        replace_existing=True
    )
    
    logger.info("APScheduler jobs configured successfully.")
