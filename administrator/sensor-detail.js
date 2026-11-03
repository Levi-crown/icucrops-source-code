function sensorDrawerTemplate(sensor) {
  const poweredOn = isSensorPoweredOn(sensor);
  const currentValue = poweredOn
    ? sensor.heroValue
      ? escapeHtml(sensor.heroValue)
      : `${escapeHtml(sensor.value)} <span>${escapeHtml(sensor.unit)}</span>`
    : "OFF <span>Sensor</span>";
  const deviceName = sensor.deviceName || sensor.name;
  const powerMode = poweredOn ? "On" : "Off";
  const detailCards = [
    metricCardTemplate("Metric", sensor.name),
    metricCardTemplate("Sensor Device", deviceName),
    metricCardTemplate("Power", powerMode),
    ...(sensor.detailMetrics || []).map((item) => metricCardTemplate(item.label, item.value)),
  ].join("");

  return `
    <div class="overlay overlay--drawer">
      <aside class="drawer sensor-detail-drawer">
        <div class="drawer__header">
          <h3 class="section-title">${escapeHtml(sensor.name)}</h3>
          <button class="icon-button" type="button" data-action="close-sensor-detail">
            ${icon("close")}
          </button>
        </div>

        <div class="drawer__hero sensor-detail-drawer__hero">
          <div class="section-copy">${escapeHtml(deviceName)}</div>
          <p class="drawer__hero-value">${currentValue}</p>
          <div class="progress-track">
            <div class="progress-fill ${progressClass(effectiveSensorStatus(sensor))}" style="width: ${effectiveSensorPercentage(sensor)}%"></div>
          </div>
        </div>

        <div class="page-stack" style="margin-top: 1.4rem;">
          <div>
            <h4 class="section-title">Sensor Details</h4>
            <p class="section-copy">${poweredOn ? "This sensor is active and currently sending data." : "This sensor is turned off from Sensor Management."}</p>
          </div>
          <div class="grid grid--cards sensor-detail-drawer__metrics">
            ${detailCards}
          </div>
        </div>

        ${sensorParameterRangeTemplate(sensor)}

        <div class="drawer__actions">
          <button class="button button--secondary button--full" type="button" data-action="close-sensor-detail">
            Close
          </button>
          <button class="button button--primary button--full" type="button" data-view="sensors">
            Open Sensor Management
          </button>
        </div>
      </aside>
    </div>
  `;
}

// The range a reading is judged against belongs next to the reading. Showing
// it here saves opening Cultivation just to remember what "Warning" means, and
// the card doubles as the shortcut to where the range is actually set.
function sensorParameterRangeTemplate(sensor) {
  const contexts = Array.isArray(sensor.parameters)
    ? sensor.parameters
    : [sensor.parameter].filter(Boolean);
  if (!contexts.length) {
    return "";
  }

  const rowKey = String(sensor.rowKey || "");
  const rows = contexts.map((context) => {
    const unit = context.field.unit;
    const custom = context.isCustom;
    const value = context.range
      ? `${formatParameterBound(context.range.min)} - ${formatParameterBound(context.range.max)}${unit ? ` ${escapeHtml(unit)}` : ""}`
      : "Not set";
    return `
      <div class="sensor-parameter-row">
        <div class="sensor-parameter-row__label">
          <span class="sensor-parameter-row__name">${escapeHtml(context.field.label)}</span>
          <span class="sensor-parameter-row__mode ${custom ? "sensor-parameter-row__mode--custom" : "sensor-parameter-row__mode--preset"}">
            ${custom ? "Custom" : "Recommended"}
          </span>
        </div>
        <span class="sensor-parameter-row__value">${value}</span>
      </div>
    `;
  }).join("");

  const cultivation = contexts.find((context) => context.cultivation)?.cultivation || null;
  if (!cultivation) {
    return `
      <div class="page-stack sensor-parameter-block" style="margin-top: 1.4rem;">
        <div>
          <h4 class="section-title">Parameter Range</h4>
          <p class="section-copy">No active cultivation on this row, so no range is being applied.</p>
        </div>
      </div>
    `;
  }

  const anyCustom = contexts.some((context) => context.isCustom);
  const cropName = escapeHtml(String(cultivation.crop || "this cultivation").trim());

  // A recommended range is the Department of Agriculture reference for the
  // crop. There is nothing to hand-edit in a reference, and Cultivation offers
  // no editor for one either -- sending someone there would land them on a
  // read-only dialog and look broken. So a preset range is shown and stops
  // there; only a hand-set one carries the shortcut to where it is changed.
  return `
    <div class="page-stack sensor-parameter-block" style="margin-top: 1.4rem;">
      <div>
        <h4 class="section-title">Parameter Range</h4>
        <p class="section-copy">
          ${anyCustom
            ? `Custom range set for ${cropName}. Open Cultivation to change it.`
            : `Department of Agriculture reference range, in use for ${cropName}.`}
        </p>
      </div>
      <div class="sensor-parameter-list">
        ${rows}
      </div>
      ${anyCustom ? `
        <button
          class="button button--secondary button--full sensor-parameter-block__link"
          type="button"
          data-action="open-sensor-parameters"
          data-row="${escapeHtml(rowKey)}"
        >
          ${icon("sprout")}
          <span>Edit in Cultivation</span>
        </button>
      ` : ""}
    </div>
  `;
}

// Trailing zeros make a hand-typed 6.5 read as 6.50; keep what was entered.
function formatParameterBound(value) {
  const numeric = Number.parseFloat(value);
  if (!Number.isFinite(numeric)) {
    return "--";
  }
  return String(Number(numeric.toFixed(2)));
}

function getSelectedSensor() {
  if (!state.selectedSensorId) {
    return null;
  }
  if (typeof findDashboardSensorById === "function") {
    return findDashboardSensorById(state.selectedSensorId);
  }
  return state.dashboardSensors.find((item) => item.id === state.selectedSensorId) || null;
}
