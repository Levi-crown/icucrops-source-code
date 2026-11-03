-- Wake the Raspberry Pi sync listener as soon as a hosted control changes.
-- The payload contains only the table name; commands and credentials never
-- travel through PostgreSQL NOTIFY.

CREATE OR REPLACE FUNCTION icucrops_notify_edge_sync()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM pg_notify('icucrops_sync', TG_TABLE_NAME);
    RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS system_state_edge_sync ON system_state;
CREATE TRIGGER system_state_edge_sync
AFTER INSERT OR UPDATE OR DELETE ON system_state
FOR EACH STATEMENT EXECUTE FUNCTION icucrops_notify_edge_sync();

DROP TRIGGER IF EXISTS sensor_registry_edge_sync ON sensor_registry;
CREATE TRIGGER sensor_registry_edge_sync
AFTER INSERT OR UPDATE OR DELETE ON sensor_registry
FOR EACH STATEMENT EXECUTE FUNCTION icucrops_notify_edge_sync();

DROP TRIGGER IF EXISTS irrigation_settings_edge_sync ON irrigation_settings;
CREATE TRIGGER irrigation_settings_edge_sync
AFTER INSERT OR UPDATE OR DELETE ON irrigation_settings
FOR EACH STATEMENT EXECUTE FUNCTION icucrops_notify_edge_sync();

DROP TRIGGER IF EXISTS irrigation_row_controls_edge_sync ON irrigation_row_controls;
CREATE TRIGGER irrigation_row_controls_edge_sync
AFTER INSERT OR UPDATE OR DELETE ON irrigation_row_controls
FOR EACH STATEMENT EXECUTE FUNCTION icucrops_notify_edge_sync();

DROP TRIGGER IF EXISTS irrigation_row_settings_edge_sync ON irrigation_row_settings;
CREATE TRIGGER irrigation_row_settings_edge_sync
AFTER INSERT OR UPDATE OR DELETE ON irrigation_row_settings
FOR EACH STATEMENT EXECUTE FUNCTION icucrops_notify_edge_sync();
