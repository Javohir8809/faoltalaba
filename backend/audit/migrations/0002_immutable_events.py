from django.db import migrations

FORWARD = """
CREATE FUNCTION reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Audit events are immutable' USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER audit_immutable_rows BEFORE UPDATE OR DELETE ON audit_auditevent
FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();
CREATE TRIGGER audit_immutable_truncate BEFORE TRUNCATE ON audit_auditevent
FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_mutation();
"""
REVERSE = """
DROP TRIGGER audit_immutable_truncate ON audit_auditevent;
DROP TRIGGER audit_immutable_rows ON audit_auditevent;
DROP FUNCTION reject_audit_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
