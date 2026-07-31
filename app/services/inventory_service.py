from datetime import datetime
from flask import g, current_app
from app import db
from app.models import BloodBag, LabTestResult, BloodInventoryTransaction, BloodInventory, PublicBloodBankCache

class InventoryService:
    @staticmethod
    def _sync_aggregate(blood_bank_id, blood_group, component):
        """
        Recalculates units_available and units_reserved in BloodInventory based on BloodBag status.
        """
        # Count available
        available_count = BloodBag.query.filter_by(
            blood_bank_id=blood_bank_id,
            blood_group=blood_group,
            component=component,
            status='available'
        ).count()
        
        # Count reserved
        reserved_count = BloodBag.query.filter_by(
            blood_bank_id=blood_bank_id,
            blood_group=blood_group,
            component=component,
            status='reserved'
        ).count()
        
        # Get or create aggregate record
        inventory = BloodInventory.query.filter_by(
            blood_bank_id=blood_bank_id,
            blood_group=blood_group,
            component=component
        ).first()
        
        if not inventory:
            inventory = BloodInventory(
                blood_bank_id=blood_bank_id,
                blood_group=blood_group,
                component=component,
                units_available=available_count,
                units_reserved=reserved_count
            )
            db.session.add(inventory)
        else:
            inventory.units_available = available_count
            inventory.units_reserved = reserved_count
            
        return inventory

    @staticmethod
    def sync_public_cache(blood_bank_id):
        """
        Reads inventory totals from the tenant DB and writes them into
        PublicBloodBankCache in the Main DB so the public finder can
        query availability without touching tenant databases.
        """
        # Map blood group strings to cache column names
        group_col_map = {
            'A+': 'a_pos', 'A-': 'a_neg',
            'B+': 'b_pos', 'B-': 'b_neg',
            'AB+': 'ab_pos', 'AB-': 'ab_neg',
            'O+': 'o_pos', 'O-': 'o_neg',
        }

        # Aggregate from tenant BloodInventory
        totals = {col: 0 for col in group_col_map.values()}
        inventories = BloodInventory.query.filter_by(blood_bank_id=blood_bank_id).all()
        for inv in inventories:
            col = group_col_map.get(inv.blood_group)
            if col:
                totals[col] += (inv.available_units or 0)

        # Upsert into the Main DB cache table
        cache = PublicBloodBankCache.query.filter_by(blood_bank_id=blood_bank_id).first()
        if not cache:
            cache = PublicBloodBankCache(blood_bank_id=blood_bank_id)
            db.session.add(cache)

        for col, val in totals.items():
            setattr(cache, col, val)
        cache.last_synced_at = datetime.utcnow()

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.warning(
                f"Failed to sync public cache for blood bank {blood_bank_id}",
                exc_info=True
            )

    @staticmethod
    def register_bag(bag_id, blood_bank_id, blood_group, component, volume_ml, collection_date, expiry_date, donor_id=None, qr_code=None):
        bag = BloodBag(
            # pyrefly: ignore [unexpected-keyword]
            bag_id=bag_id,
            # pyrefly: ignore [unexpected-keyword]
            blood_bank_id=blood_bank_id,
            # pyrefly: ignore [unexpected-keyword]
            donor_id=donor_id,
            # pyrefly: ignore [unexpected-keyword]
            blood_group=blood_group,
            # pyrefly: ignore [unexpected-keyword]
            component=component,
            # pyrefly: ignore [unexpected-keyword]
            volume_ml=volume_ml,
            # pyrefly: ignore [unexpected-keyword]
            collection_date=collection_date,
            # pyrefly: ignore [unexpected-keyword]
            expiry_date=expiry_date,
            # pyrefly: ignore [unexpected-keyword]
            status='testing',
            # pyrefly: ignore [unexpected-keyword]
            qr_code=qr_code
        )
        db.session.add(bag)
        db.session.flush()
        
        # Log transaction
        tx = BloodInventoryTransaction(
            # pyrefly: ignore [unexpected-keyword]
            bag_id=bag.id,
            # pyrefly: ignore [unexpected-keyword]
            blood_bank_id=blood_bank_id,
            # pyrefly: ignore [unexpected-keyword]
            transaction_type='collection',
            # pyrefly: ignore [unexpected-keyword]
            reason='New donation collected'
        )
        db.session.add(tx)
        
        # Aggregate won't change yet because status is 'testing'
        return bag

    @staticmethod
    def add_lab_test(bag_id_pk, test_name, result, tested_by=None):
        bag = BloodBag.query.get(bag_id_pk)
        if not bag:
            raise ValueError("Blood bag not found.")
            
        test = LabTestResult(
            # pyrefly: ignore [unexpected-keyword]
            bag_id=bag.id,
            # pyrefly: ignore [unexpected-keyword]
            test_name=test_name,
            # pyrefly: ignore [unexpected-keyword]
            result=result,
            # pyrefly: ignore [unexpected-keyword]
            tested_at=datetime.utcnow(),
            # pyrefly: ignore [unexpected-keyword]
            tested_by=tested_by
        )
        db.session.add(test)
        db.session.flush()
        
        # Check if all tests are negative to release bag
        tests = LabTestResult.query.filter_by(bag_id=bag.id).all()
        # Basic mandatory tests: HIV, HepB, HepC, Syphilis, Malaria
        mandatory_tests = {'HIV', 'HepB', 'HepC', 'Syphilis', 'Malaria'}
        completed_tests = {t.test_name for t in tests if t.result == 'negative'}
        
        has_positive = any(t.result == 'positive' for t in tests)
        
        if has_positive:
            bag.status = 'discarded'
            tx = BloodInventoryTransaction(
                # pyrefly: ignore [unexpected-keyword]
                bag_id=bag.id,
                # pyrefly: ignore [unexpected-keyword]
                blood_bank_id=bag.blood_bank_id,
                # pyrefly: ignore [unexpected-keyword]
                transaction_type='discard',
                # pyrefly: ignore [unexpected-keyword]
                reason='Positive lab test result'
            )
            db.session.add(tx)
        elif mandatory_tests.issubset(completed_tests) and bag.status == 'testing':
            bag.status = 'available'
            InventoryService._sync_aggregate(bag.blood_bank_id, bag.blood_group, bag.component)
            InventoryService.sync_public_cache(bag.blood_bank_id)
            
        return test

    @staticmethod
    def reserve_bag(bag_id_pk, request_id_or_reason):
        bag = BloodBag.query.get(bag_id_pk)
        if not bag or bag.status != 'available':
            raise ValueError("Bag is not available for reservation.")
            
        bag.status = 'reserved'
        tx = BloodInventoryTransaction(
            bag_id=bag.id,
            blood_bank_id=bag.blood_bank_id,
            transaction_type='reserve',
            reason=f'Reserved for request: {request_id_or_reason}'
        )
        db.session.add(tx)
        
        InventoryService._sync_aggregate(bag.blood_bank_id, bag.blood_group, bag.component)
        InventoryService.sync_public_cache(bag.blood_bank_id)
        return bag

    @staticmethod
    def issue_bag(bag_id_pk, reason):
        bag = BloodBag.query.get(bag_id_pk)
        if not bag or bag.status not in ('available', 'reserved'):
            raise ValueError("Bag is not available to be issued.")
            
        bag.status = 'used'
        tx = BloodInventoryTransaction(
            bag_id=bag.id,
            blood_bank_id=bag.blood_bank_id,
            transaction_type='issue',
            reason=reason
        )
        db.session.add(tx)
        
        InventoryService._sync_aggregate(bag.blood_bank_id, bag.blood_group, bag.component)
        InventoryService.sync_public_cache(bag.blood_bank_id)
        return bag

    @staticmethod
    def discard_bag(bag_id_pk, reason):
        bag = BloodBag.query.get(bag_id_pk)
        if not bag or bag.status in ('used', 'discarded'):
            raise ValueError("Bag cannot be discarded.")
            
        bag.status = 'discarded'
        tx = BloodInventoryTransaction(
            bag_id=bag.id,
            blood_bank_id=bag.blood_bank_id,
            transaction_type='discard',
            reason=reason
        )
        db.session.add(tx)
        
        InventoryService._sync_aggregate(bag.blood_bank_id, bag.blood_group, bag.component)
        InventoryService.sync_public_cache(bag.blood_bank_id)
        return bag
