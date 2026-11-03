/*
 * The greenhouse temperature and humidity with the fan and lamp's effect on
 * the air -- the browser's copy of greenhouse_response_step() in main.py.
 *
 * On the Pi the control cycle runs the model, decides the relays on it, and
 * sends the result in sharedMetrics (with `modelled: true`); the dashboards
 * then show those numbers as they are and this file is not consulted. The
 * hosted API has no control cycle, so there the browser steps this copy on
 * each poll instead. Keep the two in step: same rates, same limits.
 *
 * What it models, per poll:
 *
 *   fan running (Automatic and on, or a manual On)
 *       brings temperature and humidity down: faster above the crops'
 *       ceiling, stronger per unit past the critical margin, slowly inside
 *       the range. Never below the middle of the temperature range, or 1
 *       point above the humidity floor (where the safety limit would cut the
 *       fan). On Automatic the rule switches the fan off once
 *       the house is back inside; a manual On keeps it coming down to those
 *       limits.
 *   lamp running on Automatic
 *       warms towards the middle of the range, faster below the floor. Inside
 *       the range it only keeps warming while it runs for the cold.
 *   either stopped
 *       its effect wears off slowly towards the DHT22, not in one poll.
 *
 * The shown value is DHT22 + effect, so a real change at the sensor moves it
 * one-for-one. The DHT22 itself is kept apart by the caller
 * (SHARED_DHT22_MEASURED) and shown on the Shared DHT22 sensor card.
 */
(function attachClimateResponse(root, factory) {
  const api = factory();
  if (typeof module === "object" && module && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.ICuCropsClimateResponse = api;
  }
})(typeof window !== "undefined" ? window : globalThis, function climateResponseFactory() {
  "use strict";

  // Per minute. Mirrors GREENHOUSE_RESPONSE_RATES in main.py.
  const RATES = {
    temp: { outside: 0.3, gain: 0.1, criticalGain: 0.2, inside: 0.3, recoverMin: 0.05 },
    humidity: { outside: 1.0, gain: 0.15, criticalGain: 0.25, inside: 1.0, recoverMin: 0.2 },
  };
  const CRITICAL_MARGIN = { temp: 4, humidity: 15 };
  // Mirrors GREENHOUSE_RESPONSE_FAN_HUMIDITY_MARGIN: the safety limit cuts a fan
  // at the humidity floor itself.
  const FAN_HUMIDITY_MARGIN = 1;
  const RECOVER_MINUTES = 30;
  const TREND_SCALE = { temp: 0.5, humidity: 2 };
  const TREND_FLOOR = 0.3;
  const TREND_SECONDS = 60;
  // One step never covers more than this, so a tab left asleep does not come
  // back and apply an hour of fan in one poll.
  const MAX_STEP_SECONDS = 30;

  function finite(value) {
    if (value === null || value === undefined || value === "") return null;
    const number = typeof value === "number" ? value : Number.parseFloat(value);
    return Number.isFinite(number) ? number : null;
  }

  function classifyBand(value, range, criticalMargin) {
    const number = finite(value);
    const min = finite(range && range.min);
    const max = finite(range && range.max);
    if (number === null || min === null || max === null || !(min < max)) {
      return "normal";
    }
    const margin = Math.max(0, finite(criticalMargin) || 0);
    if (number < min - margin) return "critical-low";
    if (number < min) return "warning-low";
    if (number > max + margin) return "critical-high";
    if (number > max) return "warning-high";
    return "normal";
  }

  function pushRate(metric, beyond, insideAllowed) {
    const rates = RATES[metric];
    if (beyond <= 0) {
      return insideAllowed ? rates.inside : 0;
    }
    const margin = CRITICAL_MARGIN[metric];
    return rates.outside
      + rates.gain * Math.min(beyond, margin)
      + rates.criticalGain * Math.max(0, beyond - margin);
  }

  function trendShare(metric, helping) {
    if (!Number.isFinite(helping) || helping <= 0) return 1;
    return Math.max(TREND_FLOOR, 1 - helping / TREND_SCALE[metric]);
  }

  function recovered(effect, metric, minutes) {
    if (!effect) return 0;
    const speed = Math.max(RATES[metric].recoverMin, Math.abs(effect) / RECOVER_MINUTES);
    const step = Math.min(Math.abs(effect), speed * minutes);
    return effect > 0 ? effect - step : effect + step;
  }

  /*
   * The effects after `elapsedSeconds` more of what the relays are doing.
   * Same arguments and result as greenhouse_response_step() in main.py.
   */
  function effectStep(previous, {
    actual, bounds, fanRunning, lampRunning, lampWarming, trend, elapsedSeconds,
  }) {
    const minutes = Math.max(0, Math.min(finite(elapsedSeconds) || 0, MAX_STEP_SECONDS)) / 60;
    const beforeFan = (previous && previous.fan) || {};
    const beforeLamp = (previous && previous.light) || {};
    const fan = {};
    const light = {};
    for (const metric of ["temp", "humidity"]) {
      const value = finite(actual && actual[metric]);
      const [floor, ceiling] = bounds[metric];
      const middle = (floor + ceiling) / 2;
      const fanBefore = finite(beforeFan[metric]) || 0;
      const lampBefore = metric === "temp" ? finite(beforeLamp[metric]) || 0 : 0;
      if (value === null) {
        fan[metric] = 0;
        if (metric === "temp") light[metric] = 0;
        continue;
      }
      const rate = finite(trend && trend[metric]);

      const fanLimit = metric === "temp" ? middle : floor + FAN_HUMIDITY_MARGIN;
      let fanEffect;
      if (fanRunning) {
        const shown = value + fanBefore + lampBefore;
        const speed = pushRate(metric, shown - ceiling, true)
          * trendShare(metric, rate === null ? null : -rate);
        fanEffect = fanBefore - speed * minutes;
      } else {
        fanEffect = recovered(fanBefore, metric, minutes);
      }
      fan[metric] = Math.min(0, Math.max(fanEffect, Math.min(0, fanLimit - value)));

      if (metric === "temp") {
        let lampEffect;
        if (lampRunning) {
          const shown = value + fan[metric] + lampBefore;
          const speed = pushRate(metric, floor - shown, lampWarming === true)
            * trendShare(metric, rate);
          lampEffect = lampBefore + speed * minutes;
        } else {
          lampEffect = recovered(lampBefore, metric, minutes);
        }
        light[metric] = Math.max(0, Math.min(lampEffect, Math.max(0, middle - value)));
      }
    }
    return { fan, light };
  }

  function effectOf(state, metric) {
    if (!state) return 0;
    return (finite(state.fan && state.fan[metric]) || 0) + (finite(state.light && state.light[metric]) || 0);
  }

  function roundForDisplay(value) {
    return Math.round(value * 10) / 10;
  }

  /*
   * One poll for both metrics.
   *
   * previous: what the last call returned as `state`, or null.
   * input:    { actual: { temp, humidity }, nowMs, fresh,
   *             ranges: { temp: {min, max}, humidity: {min, max} },
   *             fan: { mode: "automatic"|"on"|"off", on },
   *             light: { mode, on, warming } }
   *
   * Returns { state, values: { temp, humidity }, modelled }. `modelled` is
   * false when the DHT22 is shown as is: no fresh reading, or nothing that
   * could move the air (no Automatic, no manual On).
   */
  function step(previous, input) {
    const actual = {
      temp: finite(input && input.actual && input.actual.temp),
      humidity: finite(input && input.actual && input.actual.humidity),
    };
    const nowMs = finite(input && input.nowMs);
    const fanMode = (input && input.fan && input.fan.mode) || "automatic";
    const lightMode = (input && input.light && input.light.mode) || "automatic";
    const fanRunning = fanMode === "on" || (fanMode === "automatic" && input.fan.on === true);
    const lampRunning = lightMode === "automatic" && input.light && input.light.on === true;
    const anything = fanMode === "automatic" || fanMode === "on" || lightMode === "automatic";
    const passthrough = { state: null, values: { ...actual }, modelled: false };
    if (nowMs === null || !(input && input.fresh === true) || !anything
      || (actual.temp === null && actual.humidity === null)) {
      return passthrough;
    }

    const bounds = {};
    for (const metric of ["temp", "humidity"]) {
      const range = input.ranges && input.ranges[metric];
      const min = finite(range && range.min);
      const max = finite(range && range.max);
      if (min === null || max === null || !(min < max)) {
        return passthrough;
      }
      bounds[metric] = [min, max];
    }

    const lastMs = previous ? finite(previous.atMs) : null;
    const elapsedSeconds = lastMs === null ? 0 : Math.max(0, nowMs - lastMs) / 1000;

    // The DHT22's own direction of change, smoothed over about a minute.
    const trend = { ...((previous && previous.trend) || { temp: 0, humidity: 0 }) };
    const actualBefore = (previous && previous.actual) || {};
    for (const metric of ["temp", "humidity"]) {
      const before = finite(actualBefore[metric]);
      if (before !== null && actual[metric] !== null && elapsedSeconds > 0) {
        const slope = ((actual[metric] - before) / elapsedSeconds) * 60;
        trend[metric] = (finite(trend[metric]) || 0)
          + (slope - (finite(trend[metric]) || 0)) * (1 - Math.exp(-elapsedSeconds / TREND_SECONDS));
      }
    }

    const effects = effectStep(previous, {
      actual,
      bounds,
      fanRunning,
      lampRunning,
      lampWarming: input.light && input.light.warming === true,
      trend,
      elapsedSeconds,
    });
    const state = { ...effects, atMs: nowMs, actual, trend };
    const values = {};
    for (const metric of ["temp", "humidity"]) {
      const effect = effectOf(state, metric);
      values[metric] = actual[metric] === null || !effect
        ? actual[metric]
        : roundForDisplay(actual[metric] + effect);
    }
    return { state, values, modelled: true };
  }

  // How far the number on a card may move per 3 s poll towards what the
  // server sends. The server's number already carries the fan and lamp's
  // effect forward smoothly between DHT22 publishes; this only spreads the
  // small correction when a new reading lands, or when a relay has just
  // switched, over a few polls instead of one. A sensor that really moves is
  // still followed: 2 C and 10 % a minute.
  const EASE_PER_3S = { temp: 0.1, humidity: 0.5 };

  /*
   * One poll of the card following the server's number.
   *
   * previous: what the last call returned as `state`, or null (first poll,
   *           or the reading went stale): the number is shown as sent.
   * target:   { temp, humidity } as the server sent them.
   */
  function easeToward(previous, target, nowMs) {
    const now = finite(nowMs);
    const values = {};
    // Where the card really is, unrounded. Keeping only the rounded number made
    // a one-second poll's 0.03 C step round back to where it started, so the
    // kiosk's temperature barely moved while a 3 s poll's did.
    const exact = {};
    const lastMs = previous ? finite(previous.atMs) : null;
    const elapsed = lastMs === null || now === null ? null : Math.max(0, now - lastMs);
    for (const metric of ["temp", "humidity"]) {
      const goal = finite(target && target[metric]);
      const kept = previous && previous.exact ? previous.exact : previous && previous.values;
      const before = previous ? finite(kept && kept[metric]) : null;
      if (goal === null || before === null || elapsed === null) {
        values[metric] = goal;
        exact[metric] = goal;
        continue;
      }
      const limit = EASE_PER_3S[metric] * (Math.min(elapsed, 30000) / 3000);
      const moved = before + Math.max(-limit, Math.min(limit, goal - before));
      exact[metric] = Math.abs(goal - moved) < 1e-9 ? goal : moved;
      values[metric] = exact[metric] === goal ? goal : roundForDisplay(moved);
    }
    return { state: { values, exact, atMs: now }, values };
  }

  return Object.freeze({
    RATES,
    EASE_PER_3S,
    easeToward,
    CRITICAL_MARGIN,
    RECOVER_MINUTES,
    classifyBand,
    effectStep,
    step,
  });
});
