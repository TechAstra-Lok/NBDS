import sqlite3
from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.session import Session
from sqlalchemy import create_engine

class TenantAwareSession(Session):
    def get_bind(self, mapper=None, clause=None, **kwargs):
        if mapper is not None:
            bind_key = getattr(mapper.class_, '__bind_key__', None)
            if bind_key == 'tenant':
                if hasattr(g, 'tenant_engine') and g.tenant_engine:
                    return g.tenant_engine
                raise RuntimeError("Accessing tenant model outside of a tenant context!")
        return super().get_bind(mapper, clause, **kwargs)

db = SQLAlchemy(session_options={"class_": TenantAwareSession})

class MainModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))

class TenantModel(db.Model):
    __bind_key__ = 'tenant'
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(50))

def test():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    # Define a dummy bind so Flask-SQLAlchemy doesn't complain about unconfigured bind key
    app.config['SQLALCHEMY_BINDS'] = {'tenant': 'sqlite:///:memory:'}
    db.init_app(app)
    
    with app.app_context():
        # Create main db
        db.create_all()
        
        # Test routing
        main_record = MainModel(name="main")
        db.session.add(main_record)
        db.session.commit()
        
        # Now create a tenant db
        tenant_engine = create_engine('sqlite:///:memory:')
        # create tables on tenant engine
        TenantModel.metadata.create_all(tenant_engine)
        
        g.tenant_engine = tenant_engine
        
        tenant_record = TenantModel(value="tenant")
        db.session.add(tenant_record)
        db.session.commit()
        
        # Verify
        print("Main count:", MainModel.query.count())
        print("Tenant count:", TenantModel.query.count())
        
        # Check standard behavior when outside context
        delattr(g, 'tenant_engine')
        try:
            TenantModel.query.count()
            print("FAILED: Should have raised RuntimeError")
        except RuntimeError as e:
            print("SUCCESS: Raised expected error:", str(e))

if __name__ == '__main__':
    test()
