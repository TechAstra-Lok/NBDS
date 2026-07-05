import logging
from datetime import datetime, timedelta
from app.models import Donor, BloodRequest

logger = logging.getLogger(__name__)

def update_donor_availability(app):
    """
    Background job to auto-update donor status based on last_donation_date (90 days logic).
    Recalculates status for all active donors using the new 3-tier availability engine.
    """
    with app.app_context():
        from app import db
        today = datetime.utcnow().date()
        
        donors = Donor.query.filter_by(is_active=True).all()
        updated_count = 0
        
        for donor in donors:
            old_status = donor.availability_status
            donor.recalculate_and_save()
            if donor.availability_status != old_status:
                updated_count += 1
        
        if updated_count > 0:
            db.session.commit()
            logger.info(f"Auto-updated {updated_count} donors' availability status.")
        else:
            logger.info("No donors needed availability update today.")



def alert_matching_donors(app, request_id):
    """
    Intelligent Donor Alert System logic.
    Finds available donors matching the requested blood group in the same district.
    """
    with app.app_context():
        from app import db
        from app.models import BloodRequest, Donor
        from app.services.notifications import NotificationDispatcher
        
        req = BloodRequest.query.get(request_id)
        if not req or req.status != 'active':
            return
            
        # Match logic: Same blood group, available, same district, active account.
        matches = Donor.query.filter(
            Donor.blood_group == req.blood_group,
            Donor.availability_status == 'available',
            Donor.is_active == True,
            Donor.curr_district == req.district
        ).all()
        
        logger.info(f"Alert System: Found {len(matches)} matching donors for Blood Request {req.request_id} in {req.district}.")
        
        if not matches:
            return
            
        dispatcher = NotificationDispatcher()
        title = f"URGENT: {req.blood_group} Blood Required at {req.hospital}"
        
        # Build comprehensive message body
        urgency_str = "EMERGENCY" if req.is_emergency else "NORMAL"
        message = (
            f"Dear Donor,\n\n"
            f"An urgent request for {req.blood_group} blood has been posted near you.\n\n"
            f"Patient: {req.patient_name}\n"
            f"Hospital: {req.hospital}\n"
            f"Location: {req.local_level or ''}, {req.district}\n"
            f"Urgency: {urgency_str}\n"
            f"Contact Person: {req.contact_person}\n"
            f"Contact Number: {req.contact_number}\n\n"
        )
        if req.request_message:
            message += f"Message: {req.request_message}\n\n"
            
        message += f"If you are available to donate, please contact the number above.\nThank you for saving a life!"
        
        dispatched_count = 0
        for donor in matches:
            if dispatcher.dispatch(donor, title, message, category='alert', request_id=req.id):
                dispatched_count += 1
                
        if dispatched_count > 0:
            db.session.commit()
            logger.info(f"Successfully dispatched alerts to {dispatched_count} donors.")


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
