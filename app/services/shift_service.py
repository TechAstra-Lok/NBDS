"""
Blood Bank Shift Service
Handles 3-Shift calculation (Previous, Current, Next Shift),
Staff Shift Assignments, Overlap Validation, and Automatic Transitions in Nepal Timezone.
"""
from datetime import datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from app import db
from app.models import BloodBank, BloodBankShift, BloodBankShiftAssignment, StaffMember, AuditLog
import logging

logger = logging.getLogger(__name__)

# Nepal Time Offset: UTC + 5 hours 45 minutes
NEPAL_TIMEZONE_OFFSET = timezone(timedelta(hours=5, minutes=45))


class ShiftService:
    @staticmethod
    def get_nepal_now() -> datetime:
        """Return current datetime in Nepal Standard Time (UTC+5:45)."""
        return datetime.now(NEPAL_TIMEZONE_OFFSET)

    @classmethod
    def ensure_default_shifts(cls, blood_bank_id: int, creator_username: str = 'system') -> List[BloodBankShift]:
        """
        If a blood bank has no shifts configured, create the standard 3 shifts:
        1. Morning Shift: 06:00 - 14:00
        2. Evening Shift: 14:00 - 22:00
        3. Night Shift:   22:00 - 06:00
        """
        existing = BloodBankShift.query.filter_by(blood_bank_id=blood_bank_id, is_active=True).all()
        if existing:
            return existing

        today = cls.get_nepal_now().date()
        defaults = [
            {'name': 'Morning Shift', 'type': 'morning', 'start': time(6, 0), 'end': time(14, 0)},
            {'name': 'Evening Shift', 'type': 'evening', 'start': time(14, 0), 'end': time(22, 0)},
            {'name': 'Night Shift',   'type': 'night',   'start': time(22, 0), 'end': time(6, 0)},
        ]

        created = []
        for item in defaults:
            shift = BloodBankShift(
                blood_bank_id=blood_bank_id,
                shift_name=item['name'],
                shift_type=item['type'],
                start_time=item['start'],
                end_time=item['end'],
                shift_date=today,
                is_active=True,
                created_by=creator_username,
                notes='Standard operational shift'
            )
            db.session.add(shift)
            created.append(shift)

        db.session.commit()
        logger.info(f"Initialized default 3-shift roster for Blood Bank ID {blood_bank_id}.")
        return created

    @classmethod
    def get_three_shifts(cls, blood_bank_id: int, target_dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Determine Previous Shift, Current Shift, and Next Shift for a Blood Bank.
        Returns a structured dictionary containing shift objects, assigned staff, and duty metadata.
        """
        if target_dt is None:
            target_dt = cls.get_nepal_now()
        
        target_time = target_dt.time()
        shifts = BloodBankShift.query.filter_by(
            blood_bank_id=blood_bank_id,
            is_active=True
        ).all()

        if not shifts:
            shifts = cls.ensure_default_shifts(blood_bank_id)

        # Sort shifts by start_time
        shifts.sort(key=lambda s: s.start_time)
        n = len(shifts)

        current_idx = None

        # Determine which shift contains target_time
        for idx, s in enumerate(shifts):
            st = s.start_time
            et = s.end_time
            if st <= et:
                # Normal daytime shift (e.g. 06:00 to 14:00)
                if st <= target_time < et:
                    current_idx = idx
                    break
            else:
                # Overnight shift (e.g. 22:00 to 06:00)
                if target_time >= st or target_time < et:
                    current_idx = idx
                    break

        # Fallback if no exact match (e.g. gap between shifts), pick nearest previous
        if current_idx is None:
            for idx in range(n - 1, -1, -1):
                if shifts[idx].start_time <= target_time:
                    current_idx = idx
                    break
            if current_idx is None:
                current_idx = 0

        prev_idx = (current_idx - 1) % n
        next_idx = (current_idx + 1) % n

        curr_shift = shifts[current_idx]
        prev_shift = shifts[prev_idx]
        next_shift = shifts[next_idx]

        # Fetch assigned staff for each shift
        def get_staff_for_shift(shift_obj):
            if not shift_obj:
                return []
            assignments = BloodBankShiftAssignment.query.filter_by(
                shift_id=shift_obj.id,
                status='assigned'
            ).all()
            result = []
            for a in assignments:
                st = a.staff_member
                if st and st.is_active and st.employment_status == 'active':
                    result.append({
                        'assignment_id': a.id,
                        'staff_id': st.id,
                        'full_name': st.full_name,
                        'designation': st.designation,
                        'qualification': st.qualification,
                        'role_in_shift': a.role_in_shift or st.designation,
                        'contact_number': st.contact_number if st.profile_visibility == 'public' else None,
                        'emergency_contact': st.emergency_contact if st.profile_visibility == 'public' else None,
                        'image_url': st.image_url,
                        'profile_visibility': st.profile_visibility,
                        'availability_status': st.availability_status
                    })
            return result

        return {
            'blood_bank_id': blood_bank_id,
            'current_time_nepal': target_dt.strftime('%I:%M %p, %Y-%m-%d'),
            'current_shift': curr_shift,
            'current_staff': get_staff_for_shift(curr_shift),
            'previous_shift': prev_shift,
            'previous_staff': get_staff_for_shift(prev_shift),
            'next_shift': next_shift,
            'next_staff': get_staff_for_shift(next_shift),
            'total_configured_shifts': n
        }

    @classmethod
    def assign_staff(cls, blood_bank_id: int, shift_id: int, staff_id: int, role_in_shift: Optional[str] = None, actor: str = 'admin') -> Tuple[bool, str]:
        """
        Assign a staff member to a specific shift with validation:
        1. Staff must belong to the same Blood Bank.
        2. Staff must be active.
        3. Prevent duplicate active assignment in the same shift.
        """
        staff = StaffMember.query.filter_by(id=staff_id, blood_bank_id=blood_bank_id).first()
        if not staff:
            return False, "Staff member not found or does not belong to this Blood Bank."

        if not staff.is_active or staff.employment_status != 'active':
            return False, f"Staff member '{staff.full_name}' is inactive or not currently employed."

        shift = BloodBankShift.query.filter_by(id=shift_id, blood_bank_id=blood_bank_id).first()
        if not shift:
            return False, "Shift not found or does not belong to this Blood Bank."

        # Check existing active assignment
        existing = BloodBankShiftAssignment.query.filter_by(
            shift_id=shift_id,
            staff_id=staff_id,
            status='assigned'
        ).first()
        if existing:
            return False, f"'{staff.full_name}' is already assigned to {shift.shift_name}."

        assignment = BloodBankShiftAssignment(
            shift_id=shift.id,
            staff_id=staff.id,
            blood_bank_id=blood_bank_id,
            role_in_shift=role_in_shift or staff.designation,
            status='assigned'
        )
        db.session.add(assignment)

        # Audit log
        log = AuditLog(
            action='SHIFT_STAFF_ASSIGNED',
            entity_id=shift.id,
            details=f"Assigned staff {staff.full_name} ({staff.designation}) to {shift.shift_name} as '{role_in_shift or staff.designation}'.",
            actor=actor
        )
        db.session.add(log)
        db.session.commit()

        # Update staff availability status
        cls.sync_staff_statuses(blood_bank_id)

        return True, f"Successfully assigned {staff.full_name} to {shift.shift_name}."

    @classmethod
    def remove_assignment(cls, blood_bank_id: int, assignment_id: int, actor: str = 'admin') -> Tuple[bool, str]:
        """Remove a staff assignment from a shift."""
        assignment = BloodBankShiftAssignment.query.filter_by(
            id=assignment_id,
            blood_bank_id=blood_bank_id
        ).first()
        if not assignment:
            return False, "Shift assignment not found."

        staff_name = assignment.staff_member.full_name if assignment.staff_member else 'Staff'
        shift_name = assignment.shift.shift_name if assignment.shift else 'Shift'

        db.session.delete(assignment)

        log = AuditLog(
            action='SHIFT_STAFF_REMOVED',
            entity_id=assignment.shift_id,
            details=f"Removed assignment for {staff_name} from {shift_name}.",
            actor=actor
        )
        db.session.add(log)
        db.session.commit()

        cls.sync_staff_statuses(blood_bank_id)
        return True, f"Removed {staff_name} from {shift_name}."

    @classmethod
    def sync_staff_statuses(cls, blood_bank_id: Optional[int] = None) -> int:
        """
        Sync staff `availability_status` (on_duty, off_duty, emergency_standby)
        based on current active shift assignments in Nepal time.
        """
        now = cls.get_nepal_now()
        banks_query = BloodBank.query.filter_by(is_active=True)
        if blood_bank_id:
            banks_query = banks_query.filter_by(id=blood_bank_id)
        banks = banks_query.all()

        updated_count = 0
        for bank in banks:
            three = cls.get_three_shifts(bank.id, target_dt=now)
            current_staff_ids = {s['staff_id'] for s in three['current_staff']}

            all_bank_staff = StaffMember.query.filter_by(blood_bank_id=bank.id, is_active=True).all()
            for st in all_bank_staff:
                if st.employment_status != 'active':
                    new_status = 'inactive'
                elif st.id in current_staff_ids:
                    new_status = 'on_duty'
                elif st.availability_status == 'emergency_standby':
                    new_status = 'emergency_standby'
                elif st.availability_status == 'on_leave':
                    new_status = 'on_leave'
                else:
                    new_status = 'off_duty'

                if st.availability_status != new_status:
                    st.availability_status = new_status
                    updated_count += 1

        if updated_count > 0:
            db.session.commit()
            logger.info(f"Synchronized duty status for {updated_count} blood bank staff members.")
        return updated_count
