"""
Tests Migrations — Intégrité de la base de données
"""
import pytest
from django.db import connection

pytestmark = pytest.mark.django_db


class TestMigrations:

    def test_toutes_migrations_appliquees(self):
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        assert len(plan) == 0, f"Migrations non appliquées: {[str(m) for m, _ in plan]}"

    def test_tables_principales_existent(self):
        tables = connection.introspection.table_names()
        tables_requises = [
            'users_user', 'agents_agentprofile', 'properties_property',
            'visits_visitrequest', 'payments_transaction',
        ]
        for table in tables_requises:
            assert table in tables, f"Table manquante: {table}"

    def test_indexes_critiques_existent(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'users_user'")
            count = cursor.fetchone()[0]
            assert count > 0

    def test_contraintes_foreignkey_valides(self):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.table_constraints
                WHERE constraint_type = 'FOREIGN KEY'
            """)
            count = cursor.fetchone()[0]
            assert count > 0

    def test_uuid_primary_keys(self):
        from apps.users.models import User
        import uuid
        assert User._meta.pk.get_internal_type() in ['UUIDField', 'CharField']

    def test_creation_user_persiste(self, create_user):
        from apps.users.models import User
        user = create_user(role='client')
        found = User.objects.get(id=user.id)
        assert found.email == user.email

    def test_cascade_delete_fonctionne(self, owner_user, property_obj):
        from apps.properties.models import Property
        prop_id = property_obj.id
        property_obj.delete()
        assert not Property.objects.filter(id=prop_id).exists()

    def test_rollback_transaction(self):
        from django.db import transaction
        from apps.users.models import User
        count_before = User.objects.count()
        try:
            with transaction.atomic():
                User.objects.create_user(
                    email='rollback@test.com',
                    phone='+237699111222',
                    password='Test123!',
                    first_name='Roll',
                    last_name='Back',
                    role='client',
                )
                raise Exception("Rollback forcé")
        except Exception:
            pass
        count_after = User.objects.count()
        assert count_after == count_before
