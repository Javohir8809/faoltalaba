from django.db import migrations

FORWARD = r"""
CREATE FUNCTION protect_attendance_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.id, NEW.session_id, NEW.student_id, NEW.recorded_by_id, NEW.device_id,
NEW.checked_in_at, NEW.method)
     IS DISTINCT FROM
     (OLD.id, OLD.session_id, OLD.student_id, OLD.recorded_by_id, OLD.device_id,
OLD.checked_in_at, OLD.method)
     OR NEW.version <> OLD.version + 1
     OR NOT EXISTS (SELECT 1 FROM attendance_attendancechange c
       WHERE c.record_id=OLD.id AND c.version=NEW.version AND c.action='CORRECTION'
       AND c.previous_status=OLD.status AND c.new_status=NEW.status
       AND c.previous_note=OLD.note AND c.new_note=NEW.note)
  THEN RAISE EXCEPTION 'Attendance correction requires immutable matching history' USING
ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER attendance_record_guard BEFORE UPDATE ON attendance_attendancerecord
 FOR EACH ROW EXECUTE FUNCTION protect_attendance_record();
CREATE FUNCTION verify_attendance_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM attendance_attendancechange c
   WHERE c.record_id=NEW.id AND c.version=NEW.version
   AND c.new_status=NEW.status AND c.new_note=NEW.note)
 THEN RAISE EXCEPTION 'Attendance history is required' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER attendance_history_required AFTER INSERT OR UPDATE ON
attendance_attendancerecord
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_attendance_history();
CREATE FUNCTION verify_attendance_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM attendance_attendancerecord r WHERE r.id=NEW.record_id AND
   ((NEW.version=1 AND r.version=1 AND NEW.new_status=r.status AND NEW.new_note=r.note
     AND ((r.method='MANUAL' AND NEW.action='MANUAL_CHECK_IN') OR (r.method IN ('NFC','QR') AND
NEW.action='CHECK_IN')))
    OR (NEW.version=r.version+1 AND NEW.action='CORRECTION' AND NEW.previous_status=r.status AND
NEW.previous_note=r.note)))
 THEN RAISE EXCEPTION 'Attendance history snapshot is invalid' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER attendance_change_snapshot BEFORE INSERT ON attendance_attendancechange
 FOR EACH ROW EXECUTE FUNCTION verify_attendance_change();
CREATE TRIGGER attendance_changes_immutable BEFORE UPDATE OR DELETE ON attendance_attendancechange
 FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();
CREATE TRIGGER attendance_changes_truncate BEFORE TRUNCATE ON attendance_attendancechange
 FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_mutation();
CREATE TRIGGER attendance_records_delete BEFORE DELETE ON attendance_attendancerecord
 FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();
CREATE TRIGGER attendance_records_truncate BEFORE TRUNCATE ON attendance_attendancerecord
 FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_mutation();
CREATE FUNCTION protect_attendance_card() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.id, NEW.student_id, NEW.kind, NEW.token_digest, NEW.protocol, NEW.variant,
NEW.uid_readable, NEW.enrolled_by_id, NEW.created_at)
   IS DISTINCT FROM
   (OLD.id, OLD.student_id, OLD.kind, OLD.token_digest, OLD.protocol, OLD.variant,
OLD.uid_readable, OLD.enrolled_by_id, OLD.created_at)
   OR OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL
 THEN RAISE EXCEPTION 'Card identity is immutable' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER attendance_card_guard BEFORE UPDATE ON attendance_studentcardmapping
 FOR EACH ROW EXECUTE FUNCTION protect_attendance_card();
CREATE TRIGGER attendance_cards_delete BEFORE DELETE ON attendance_studentcardmapping
 FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();
CREATE TRIGGER attendance_cards_truncate BEFORE TRUNCATE ON attendance_studentcardmapping
 FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_mutation();
"""
REVERSE = r"""
DROP TRIGGER attendance_cards_truncate ON attendance_studentcardmapping;
DROP TRIGGER attendance_cards_delete ON attendance_studentcardmapping;
DROP TRIGGER attendance_card_guard ON attendance_studentcardmapping;
DROP FUNCTION protect_attendance_card();
DROP TRIGGER attendance_records_truncate ON attendance_attendancerecord;
DROP TRIGGER attendance_records_delete ON attendance_attendancerecord;
DROP TRIGGER attendance_changes_truncate ON attendance_attendancechange;
DROP TRIGGER attendance_changes_immutable ON attendance_attendancechange;
DROP TRIGGER attendance_change_snapshot ON attendance_attendancechange;
DROP FUNCTION verify_attendance_change();
DROP TRIGGER attendance_history_required ON attendance_attendancerecord;
DROP FUNCTION verify_attendance_history();
DROP TRIGGER attendance_record_guard ON attendance_attendancerecord;
DROP FUNCTION protect_attendance_record();
"""


class Migration(migrations.Migration):
    dependencies = [("attendance", "0001_initial"), ("audit", "0002_immutable_events")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
