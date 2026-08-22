import logging
from datetime import datetime
from app.models import Donor

logger = logging.getLogger(__name__)

def update_donor_availability(app):
    """
    Background job to auto-update donor status based on last_donation_date (90 days logic).
    Recalculates status for all active donors using the new 3-tier availability engine.
    """
    with app.app_context():
        from app import db
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
    Enterprise Donor Alert System.
    Uses the new NotificationService for intelligent matching + multi-channel queuing.
    Falls back to the legacy dispatcher for backward compatibility.
    """
    with app.app_context():
        from app import db
        from app.models import BloodRequest
        try:
            from app.services.notification_service import NotificationService
            req = BloodRequest.query.get(request_id)
            if not req or req.status != 'active':
                return
            service = NotificationService()
            queued = service.dispatch_for_request(req)
            logger.info("Enterprise alert system queued %d donor notifications for request %s.", queued, req.request_id)
        except Exception as e:
            logger.error("Enterprise notification dispatch failed, falling back to legacy: %s", e)
            # --- Legacy fallback ---
            try:
                from app.models import Donor
                from app.services.notifications import NotificationDispatcher
                req = BloodRequest.query.get(request_id)
                if not req:
                    return
                matches = Donor.query.filter(
                    Donor.blood_group == req.blood_group,
                    Donor.availability_status == 'Available',
                    Donor.is_active == True,
                ).all()
                dispatcher = NotificationDispatcher()
                title = f"URGENT: {req.blood_group} Blood Required at {req.hospital}"
                message = (
                    f"Patient {req.patient_name} needs {req.blood_group} blood at "
                    f"{req.hospital}, {req.district}. "
                    f"Contact: {req.contact_person} ({req.contact_number})."
                )
                count = sum(
                    1 for d in matches
                    if dispatcher.dispatch(d, title, message, category='alert', request_id=req.id)
                )
                if count:
                    db.session.commit()
                logger.info("Legacy fallback dispatched %d alerts.", count)
            except Exception as e2:
                logger.error("Legacy fallback also failed: %s", e2)


def process_notification_queue(app):
    """Process pending notification queue items (called by APScheduler every 2 minutes)."""
    with app.app_context():
        try:
            from app.services.notification_service import NotificationService
            NotificationService.process_queue(batch_size=30)
            logger.debug("Notification queue processing cycle complete.")
        except Exception as e:
            logger.error("Notification queue processing error: %s", e)


def sync_shift_staff_statuses(app):
    """
    Synchronize staff availability_status based on current active shift assignments.
    Runs every 5 minutes aligned to Nepal Standard Time (UTC+5:45).
    """
    with app.app_context():
        try:
            from app.services.shift_service import ShiftService
            updated = ShiftService.sync_staff_statuses()
            if updated > 0:
                logger.info("Shift Status Sync: Updated %d staff duty statuses.", updated)
            else:
                logger.debug("Shift Status Sync: No status changes detected.")
        except Exception as e:
            logger.error("Shift staff status sync error: %s", e)


def schedule_jobs(app, scheduler):
    """
    Configures and starts all APScheduler background jobs.
    """
    # Job 1: Update donor availability statuses daily
    scheduler.add_job(
        id='update_donor_availability_job',
        func=update_donor_availability,
        args=[app],
        trigger='interval',
        hours=24,
        next_run_time=datetime.now(),
        replace_existing=True,
    )

    # Job 2: Process notification queue every 2 minutes
    scheduler.add_job(
        id='process_notification_queue_job',
        func=process_notification_queue,
        args=[app],
        trigger='interval',
        minutes=2,
        next_run_time=datetime.now(),
        replace_existing=True,
    )

    # Job 3: Sync blood bank staff duty statuses every 5 minutes (Nepal 3-Shift system)
    scheduler.add_job(
        id='sync_shift_staff_statuses_job',
        func=sync_shift_staff_statuses,
        args=[app],
        trigger='interval',
        minutes=5,
        next_run_time=datetime.now(),
        replace_existing=True,
    )

    logger.info("APScheduler jobs configured successfully.")
