from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [
        migrations.RunSQL(
            """
        CREATE FUNCTION reject_user_uuid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.id IS DISTINCT FROM OLD.id THEN
            RAISE EXCEPTION 'User UUID is immutable' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER user_uuid_immutable BEFORE UPDATE OF id ON accounts_user
        FOR EACH ROW EXECUTE FUNCTION reject_user_uuid_mutation();
        """,
            """
        DROP TRIGGER user_uuid_immutable ON accounts_user;
        DROP FUNCTION reject_user_uuid_mutation();
        """,
        )
    ]
