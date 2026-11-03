-- How a cultivation ended: harvested, or removed.
--
-- A removal used to DELETE the cultivation and record nothing, so the report
-- could not tell a scrapped crop from one that was never planted. Both
-- endings are the same shape of fact, so they share this table and are told
-- apart by this column.
--
-- Every row already here arrived through the harvest path, because that was
-- the only path that wrote one. The DEFAULT is therefore correct for them and
-- no backfill is needed.
ALTER TABLE cultivation_harvests
    ADD COLUMN IF NOT EXISTS outcome TEXT NOT NULL DEFAULT 'harvested';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'cultivation_harvests_outcome_check'
    ) THEN
        ALTER TABLE cultivation_harvests
            ADD CONSTRAINT cultivation_harvests_outcome_check
            CHECK (outcome IN ('harvested', 'removed'));
    END IF;
END $$;
