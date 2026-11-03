-- Irrigation durations move from minutes to seconds.
--
-- The supply lines here deliver faster than the original design assumed: a
-- water, fertilizer or lime run that needed 15-20 minutes on paper reaches the
-- row in well under a minute. A minute was the smallest step the schema could
-- express, so the shortest possible run was already longer than most runs
-- should be, and the only way to stop early was to press Stop by hand.
--
-- Every duration column becomes seconds. They are renamed rather than
-- reinterpreted: leaving a column called *_minutes holding seconds is how a
-- report ends up claiming a 20-second run took 20 minutes, and nothing in the
-- code would look wrong while it did.
--
-- Existing values are multiplied by 60, so saved settings and run history keep
-- meaning exactly what they meant before this ran.

-- Per-channel defaults.
ALTER TABLE irrigation_settings
    RENAME COLUMN automatic_duration TO automatic_duration_seconds;
ALTER TABLE irrigation_settings
    RENAME COLUMN manual_duration TO manual_duration_seconds;
ALTER TABLE irrigation_settings
    RENAME COLUMN schedule_duration TO schedule_duration_seconds;

UPDATE irrigation_settings
   SET automatic_duration_seconds = automatic_duration_seconds * 60,
       manual_duration_seconds    = manual_duration_seconds * 60,
       schedule_duration_seconds  = schedule_duration_seconds * 60;

-- Per-row overrides.
ALTER TABLE irrigation_row_settings
    RENAME COLUMN automatic_duration TO automatic_duration_seconds;
ALTER TABLE irrigation_row_settings
    RENAME COLUMN manual_duration TO manual_duration_seconds;
ALTER TABLE irrigation_row_settings
    RENAME COLUMN schedule_duration TO schedule_duration_seconds;

UPDATE irrigation_row_settings
   SET automatic_duration_seconds = automatic_duration_seconds * 60,
       manual_duration_seconds    = manual_duration_seconds * 60,
       schedule_duration_seconds  = schedule_duration_seconds * 60;

ALTER TABLE irrigation_row_settings
    ALTER COLUMN automatic_duration_seconds SET DEFAULT 900;
ALTER TABLE irrigation_row_settings
    ALTER COLUMN manual_duration_seconds SET DEFAULT 900;
ALTER TABLE irrigation_row_settings
    ALTER COLUMN schedule_duration_seconds SET DEFAULT 1200;

-- Run history. Automatic runs store 0 here and always have: they are stopped
-- by the crop parameter being met, not by a timer, so there is no duration to
-- convert on those rows and multiplying zero leaves them alone.
ALTER TABLE irrigation_runs
    RENAME COLUMN duration_minutes TO duration_seconds;

UPDATE irrigation_runs
   SET duration_seconds = duration_seconds * 60;
