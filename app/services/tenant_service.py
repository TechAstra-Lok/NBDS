import os
import uuid
from flask import g, current_app
from sqlalchemy import create_engine, MetaData
from app import db
from app.models import BloodBank

class TenantResolutionService:
    @staticmethod
    def resolve_tenant(tenant_id_or_db_name):
        """
        Resolves the tenant based on the given string identifier (either tenant_id or db_name)
        and attaches the tenant_engine to flask.g.
        """
        if not tenant_id_or_db_name:
            raise ValueError("Tenant ID or DB name must be provided.")
            
        # Try finding by tenant_id first
        tenant = BloodBank.query.filter_by(tenant_id=tenant_id_or_db_name).first()
        if not tenant:
            # Fallback to db_name for internal resolution
            tenant = BloodBank.query.filter_by(db_name=tenant_id_or_db_name).first()
            
        if not tenant or not tenant.db_name:
            raise ValueError("Tenant not found or has no assigned database.")
            
        if tenant.tenant_status not in ['Active', 'Provisioning']:
            raise ValueError("Tenant is suspended or not active.")
            
        # Construct the engine
        instance_dir = os.path.join(current_app.root_path, '..', 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        db_path = os.path.join(instance_dir, tenant.db_name)
        
        tenant_uri = f"sqlite:///{db_path}"
        g.tenant_engine = create_engine(tenant_uri)
        g.tenant = tenant
        
        return tenant


class TenantProvisioningService:
    @staticmethod
    def provision_tenant(blood_bank_id):
        """
        Creates a new tenant database, applies schemas, and activates it.
        """
        tenant = BloodBank.query.get(blood_bank_id)
        if not tenant:
            raise ValueError("Blood Bank not found.")
            
        if not tenant.tenant_id:
            uid = str(uuid.uuid4())[:6].upper()
            tenant.tenant_id = f"BB-{uid}"
            
        tenant.db_name = f"tenant_{tenant.tenant_id.lower().replace('-', '_')}.db"
        
        # Build the engine for this new DB
        instance_dir = os.path.join(current_app.root_path, '..', 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        db_path = os.path.join(instance_dir, tenant.db_name)
        tenant_uri = f"sqlite:///{db_path}"
        
        engine = create_engine(tenant_uri)
        
        # Create all tables associated with the 'tenant' bind
        tenant_metadata = db.metadatas.get('tenant')
        if tenant_metadata:
            tenant_metadata.create_all(engine)
        
        # Run idempotent seed scripts here if any
        
        tenant.tenant_status = 'Active'
        db.session.commit()
        return tenant

