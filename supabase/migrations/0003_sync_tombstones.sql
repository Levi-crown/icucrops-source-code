-- Carry a deletion, not just an absence.
--
-- The edge sync reconciles two independent stores by comparing what each one
-- holds. That works for edits and for new rows, but not for removals: a row
-- that is simply gone is indistinguishable from one that never arrived, so a
-- plain DELETE on one device reads to the other as "you are missing
-- something" and the row comes straight back on the next pass.
--
-- notifications already solved this with a deleted_at column on the row
-- itself. cultivations and users cannot take the same treatment, because
-- cultivations.row_key and users.email are UNIQUE: a tombstoned row would sit
-- in the slot forever and block replanting row1 or re-registering an address.
-- The mark lives beside those tables instead.
--
-- natural_key names the individual record rather than the slot it occupied --
-- 'row1|<created_at>', '<email>|<created_at>' -- so a tombstone can never
-- reach the next cultivation planted on the same row, or a re-registered
-- account at the same address.

CREATE TABLE IF NOT EXISTS sync_tombstones (
    entity      text NOT NULL,
    natural_key text NOT NULL,
    deleted_at  text NOT NULL,
    PRIMARY KEY (entity, natural_key)
);

-- The sync purges tombstones older than its retention window, and that scan
-- is the only query that does not name a key.
CREATE INDEX IF NOT EXISTS sync_tombstones_deleted_idx ON sync_tombstones (deleted_at);

-- Same wake-up as the other tables the Pi mirrors: a deletion made on the
-- hosted dashboard should reach the farm as fast as an edit does, rather than
-- waiting for the periodic pass.
DROP TRIGGER IF EXISTS sync_tombstones_edge_sync ON sync_tombstones;
CREATE TRIGGER sync_tombstones_edge_sync
AFTER INSERT OR UPDATE OR DELETE ON sync_tombstones
FOR EACH STATEMENT EXECUTE FUNCTION icucrops_notify_edge_sync();

DROP TRIGGER IF EXISTS cultivations_edge_sync ON cultivations;
CREATE TRIGGER cultivations_edge_sync
AFTER INSERT OR UPDATE OR DELETE ON cultivations
FOR EACH STATEMENT EXECUTE FUNCTION icucrops_notify_edge_sync();

DROP TRIGGER IF EXISTS users_edge_sync ON users;
CREATE TRIGGER users_edge_sync
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH STATEMENT EXECUTE FUNCTION icucrops_notify_edge_sync();
