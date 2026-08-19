import re
import string
import secrets
from werkzeug.security import check_password_hash
from app.models import BloodBankAccount, BloodBankPasswordHistory, BloodBank
from app import db
from datetime import datetime

class AuthService:
    """
    Handles authentication-related logic, specifically for Blood Bank accounts.
    Includes custom ID generation, secure password generation, and strict password policy validation.
    """
    
    @staticmethod
    def generate_login_id(province_code, district_code, sequence_number):
        """
        Generates a standardized Blood Bank login ID.
        Format: BBB-{ProvinceCode}-{DistrictCode}-{Sequence}
        Example: BBB-KTM-001
        """
        # Ensure it's uppercase and padded
        p_code = province_code.upper()[:3]
        d_code = district_code.upper()[:3]
        seq = str(sequence_number).zfill(3)
        return f"BBB-{p_code}-{d_code}-{seq}"

    @staticmethod
    def generate_secure_password(length=12):
        """
        Generates a cryptographically secure random password.
        Must contain uppercase, lowercase, digits, and special characters.
        """
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_+="
        while True:
            password = ''.join(secrets.choice(alphabet) for i in range(length))
            if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and sum(c.isdigit() for c in password) >= 2
                and any(c in "!@#$%^&*()-_+=" for c in password)):
                return password

    @staticmethod
    def validate_password_policy(password, account=None):
        """
        Validates a password against the strict policy:
        - Min 10 characters
        - Mixed case (upper/lower)
        - Numbers
        - Special characters
        - Block reuse of last 5 passwords (if account is provided)
        """
        if len(password) < 10:
            return False, "Password must be at least 10 characters long."
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter."
            
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter."
            
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number."
            
        if not re.search(r'[!@#$%^&*()\-_+=]', password):
            return False, "Password must contain at least one special character."
            
        # Check against last 5 passwords
        if account:
            recent_hashes = BloodBankPasswordHistory.query.filter_by(account_id=account.id)\
                                .order_by(BloodBankPasswordHistory.created_at.desc())\
                                .limit(5).all()
                                
            for history in recent_hashes:
                if check_password_hash(history.password_hash, password):
                    return False, "Password cannot be one of your last 5 used passwords."
                    
        return True, "Password is valid."
        
    @staticmethod
    def create_blood_bank_account(blood_bank_id, province_code, district_code):
        """
        Creates a new Blood Bank account with a generated login ID and secure password.
        """
        blood_bank = BloodBank.query.get(blood_bank_id)
        if not blood_bank:
            raise ValueError("Blood Bank not found.")
            
        # Determine sequence number by counting existing accounts in this district
        count = BloodBankAccount.query.join(BloodBank).filter(
            BloodBank.district == blood_bank.district
        ).count()
        
        login_id = AuthService.generate_login_id(province_code, district_code, count + 1)
        
        # Ensure uniqueness
        while BloodBankAccount.query.filter_by(login_id=login_id).first():
            count += 1
            login_id = AuthService.generate_login_id(province_code, district_code, count + 1)
            
        raw_password = AuthService.generate_secure_password()
        
        account = BloodBankAccount(
            # pyrefly: ignore [unexpected-keyword]
            blood_bank_id=blood_bank.id,
            # pyrefly: ignore [unexpected-keyword]
            login_id=login_id,
            # pyrefly: ignore [unexpected-keyword]
            temp_password=raw_password,
            # pyrefly: ignore [unexpected-keyword]
            password_change_required=True,
            # pyrefly: ignore [unexpected-keyword]
            account_status='pending',
            # pyrefly: ignore [unexpected-keyword]
            created_at=datetime.utcnow()
        )
        account.set_password(raw_password)
        
        db.session.add(account)
        db.session.flush() # Flush to get account ID
        
        # Record password history
        history = BloodBankPasswordHistory(
            # pyrefly: ignore [unexpected-keyword]
            account_id=account.id,
            # pyrefly: ignore [unexpected-keyword]
            password_hash=account.password_hash,
            # pyrefly: ignore [unexpected-keyword]
            created_at=datetime.utcnow()
        )
        db.session.add(history)
        db.session.commit()
        
        return account, raw_password
