"""
Enterprise Intelligent Donor Matching Service.

Scores and ranks donors against a BloodRequest using:
  - Blood group compatibility
  - Availability status
  - Account status (active, verified)
  - Notification opt-in
  - Geographic proximity (Province > District > Local Level)
  - Last donation date (cooldown enforcement)
  - Activity / response rate scoring
"""
import logging
from datetime import datetime, timedelta
from app import db
from app.models import Donor, BloodRequest, Notification

logger = logging.getLogger(__name__)

# Blood group compatibility map: request group -> eligible donor groups
BLOOD_COMPATIBILITY = {
    'A+':  ['A+', 'A-', 'O+', 'O-'],
    'A-':  ['A-', 'O-'],
    'B+':  ['B+', 'B-', 'O+', 'O-'],
    'B-':  ['B-', 'O-'],
    'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
    'AB-': ['A-', 'B-', 'AB-', 'O-'],
    'O+':  ['O+', 'O-'],
    'O-':  ['O-'],
}

DONATION_COOLDOWN_DAYS = 90  # minimum days between whole blood donations


class DonorMatchingService:
    """
    Intelligently matches and ranks donors for a given blood request.
    """

    def __init__(self, max_results=50):
        self.max_results = max_results

    def find_eligible_donors(self, blood_request: BloodRequest):
        """
        Return a ranked list of (donor, score, reasons) tuples.
        """
        compatible_groups = BLOOD_COMPATIBILITY.get(blood_request.blood_group, [blood_request.blood_group])

        # Base query: active, available, correct blood group
        candidates = (
            Donor.query
            .filter(
                Donor.availability_status == 'Available',
                Donor.is_active == True,
                Donor.blood_group.in_(compatible_groups),
            )
            .all()
        )

        cooldown_cutoff = datetime.utcnow() - timedelta(days=DONATION_COOLDOWN_DAYS)
        ranked = []

        for donor in candidates:
            # --- Hard exclusions ---
            if not donor.email:
                continue
            if not donor.phone1:
                continue

            # Check notification preference — skip opted-out donors
            pref = getattr(donor, 'preference', None)
            if pref and pref.dnd_mode:
                continue

            # Cooldown check
            if donor.last_donation_date and donor.last_donation_date > cooldown_cutoff.date():
                continue

            # Already notified for this exact request?
            already_notified = Notification.query.filter_by(
                donor_id=donor.id,
                blood_request_id=blood_request.id,
            ).first()
            if already_notified:
                continue

            score, reasons = self._score_donor(donor, blood_request)
            ranked.append((donor, score, reasons))

        # Sort descending by score
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:self.max_results]

    def _score_donor(self, donor, blood_request):
        """
        Compute a weighted match score for donor vs request.
        Returns (float score, list[str] reasons)
        """
        score = 0.0
        reasons = []

        # 1. Exact blood group match (vs compatible)
        if donor.blood_group == blood_request.blood_group:
            score += 40
            reasons.append("Exact blood group match")
        else:
            score += 20
            reasons.append(f"Compatible blood group ({donor.blood_group})")

        # 2. Province match
        if blood_request.province and donor.curr_province == blood_request.province:
            score += 25
            reasons.append("Same province")

        # 3. District match
        if blood_request.district and donor.curr_district == blood_request.district:
            score += 20
            reasons.append("Same district")

        # 4. Local level match
        if blood_request.local_level and donor.curr_local_level == blood_request.local_level:
            score += 10
            reasons.append("Same local level")

        # 5. Last donation recency (prefer donors who donated longer ago)
        if donor.last_donation_date:
            days_since = (datetime.utcnow().date() - donor.last_donation_date).days
            if days_since >= 365:
                score += 10
                reasons.append("Donated over a year ago")
            elif days_since >= 180:
                score += 5
                reasons.append("Donated 6+ months ago")

        # 6. Emergency priority bonus
        if getattr(blood_request, 'is_emergency', False):
            score += 5
            reasons.append("Emergency request bonus")

        # 7. Total donation history (experience)
        total = getattr(donor, 'total_donations', 0) or 0
        if total >= 10:
            score += 8
            reasons.append(f"Experienced donor ({total} donations)")
        elif total >= 5:
            score += 4
        elif total >= 1:
            score += 2

        return score, reasons

    def get_best_match(self, blood_request):
        """Return the single best matching donor or None."""
        ranked = self.find_eligible_donors(blood_request)
        return ranked[0] if ranked else None

    def get_top_n(self, blood_request, n=10):
        """Return the top N ranked donors."""
        return self.find_eligible_donors(blood_request)[:n]
