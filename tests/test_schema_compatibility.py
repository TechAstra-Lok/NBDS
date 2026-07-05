import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_existing_sqlite_schema_is_upgraded_for_inventory_columns(tmp_path, monkeypatch):
    db_path = tmp_path / 'legacy_blood.db'
    db_url = f'sqlite:///{db_path}'
    monkeypatch.setenv('DATABASE_URL', db_url)

    import sqlalchemy as sa
    from sqlalchemy import text

    engine = sa.create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE blood_banks (id INTEGER NOT NULL, name VARCHAR(200), is_active BOOLEAN, PRIMARY KEY (id))'))
        conn.execute(text(
            'CREATE TABLE blood_inventory ('
            'id INTEGER NOT NULL, '
            'blood_bank_id INTEGER NOT NULL, '
            'blood_group VARCHAR(5) NOT NULL, '
            'component VARCHAR(50) NOT NULL, '
            'units_available INTEGER, '
            'units_reserved INTEGER, '
            'minimum_stock INTEGER, '
            'maximum_stock INTEGER, '
            'PRIMARY KEY (id), '
            'FOREIGN KEY(blood_bank_id) REFERENCES blood_banks (id))'
        ))
        conn.execute(text("INSERT INTO blood_banks (id, name, is_active) VALUES (1, 'Legacy Bank', 1)"))
        conn.execute(text(
            "INSERT INTO blood_inventory (id, blood_bank_id, blood_group, component, units_available, units_reserved, minimum_stock, maximum_stock) "
            "VALUES (1, 1, 'O+', 'Whole Blood', 5, 0, 4, 20)"
        ))

    import config as config_module
    import app as app_module

    app_instance = app_module.create_app('development')
    with app_instance.app_context():
        with app_module.db.engine.connect() as connection:
            inspector = app_module.db.engine.dialect.get_columns(connection, 'blood_inventory')
            column_names = {column['name'] for column in inspector}
            assert 'expiry_date' in column_names
            assert 'qr_code' in column_names
            assert 'last_updated' in column_names
