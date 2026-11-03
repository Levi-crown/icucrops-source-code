const APP_ASSET_BASE_PATH = window.location.pathname.includes("/mobile_web/") ? "../../assets" : "../assets";
const LOGO_PATH = `${APP_ASSET_BASE_PATH}/icucrops-logo-transparent.png`;
const SARATE_LOGO_PATH = `${APP_ASSET_BASE_PATH}/sarate-farm-logo.png`;
const DA_LOGO_PATH = "/assets/da-logo-transparent.png?v=20260815a";
const ICON_SPRITE_PATH = `${APP_ASSET_BASE_PATH}/ui-icons.svg?v=20260831r5`;
const MAX_PROFILE_PHOTO_BYTES = 5 * 1024 * 1024;
// Longer than any realistic photo upload; the success path re-marks with
// the normal window once the response is in.
const PROFILE_SAVE_SYNC_SUPPRESS_MS = 120000;
const PASSWORD_POLICY_MESSAGE = window.ICuCropsAuth?.PASSWORD_POLICY_MESSAGE
  || "Password must be 8–64 characters and include uppercase, lowercase, number, and special character.";

function isValidNewPassword(value) {
  const sharedValidator = window.ICuCropsAuth?.isValidNewPassword;
  if (typeof sharedValidator === "function") {
    return sharedValidator(value);
  }
  const password = String(value || "");
  const characterCount = Array.from(password).length;
  return characterCount >= 8
    && characterCount <= 64
    && /\p{Lu}/u.test(password)
    && /\p{Ll}/u.test(password)
    && /\p{N}/u.test(password)
    && /[^\p{L}\p{N}\s]/u.test(password);
}

const ICONS = {
  dashboard: `
    <rect x="3" y="3" width="7" height="7"></rect>
    <rect x="14" y="3" width="7" height="5"></rect>
    <rect x="14" y="12" width="7" height="9"></rect>
    <rect x="3" y="14" width="7" height="7"></rect>
  `,
  activity: `
    <path d="M3 12h4l3-7 4 14 3-7h4"></path>
  `,
  droplets: `
    <path d="M12 3s6 6 6 10a6 6 0 0 1-12 0c0-4 6-10 6-10Z"></path>
  `,
  droplet: `
    <path d="M12 3s6 6 6 10a6 6 0 0 1-12 0c0-4 6-10 6-10Z"></path>
  `,
  sprout: `
    <path d="M12 20v-8"></path>
    <path d="M12 12c0-4.4 3.6-8 8-8 0 4.4-3.6 8-8 8Z"></path>
    <path d="M12 14c0-3.3-2.7-6-6-6 0 3.3 2.7 6 6 6Z"></path>
    <path d="M8 20h8"></path>
  `,
  leaf: `
    <path d="M12 19v-4.5"></path>
    <path d="M12 14.5c0-2.8 2.3-5 5.1-5.1 0 2.8-2.3 5.1-5.1 5.1Z"></path>
    <path d="M12 15.6c0-2.1-1.7-3.8-3.8-3.8 0 2.1 1.7 3.8 3.8 3.8Z"></path>
  `,
  users: `
    <path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2"></path>
    <circle cx="9.5" cy="7" r="3"></circle>
    <path d="M21 21v-2a4 4 0 0 0-3-3.87"></path>
    <path d="M16 4.13a4 4 0 0 1 0 7.75"></path>
  `,
  settings: `
    <circle cx="12" cy="12" r="3"></circle>
    <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 1-3 0 1.7 1.7 0 0 0-1-.6 1.7 1.7 0 0 0-1.82.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 1 0-3 1.7 1.7 0 0 0 .6-1 1.7 1.7 0 0 0-.34-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 1 3 0 1.7 1.7 0 0 0 1 .6 1.7 1.7 0 0 0 1.82-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c0 .38.14.75.4 1a1.7 1.7 0 0 1 0 3c-.26.25-.4.62-.4 1Z"></path>
  `,
  logout: `
    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path>
    <path d="M10 17l5-5-5-5"></path>
    <path d="M15 12H3"></path>
  `,
  user: `
    <circle cx="12" cy="8" r="4"></circle>
    <path d="M5 20a7 7 0 0 1 14 0"></path>
  `,
  thermometer: `
    <path d="M14 14.76V5a2 2 0 1 0-4 0v9.76a4 4 0 1 0 4 0Z"></path>
  `,
  fan: `
    <circle cx="12" cy="12" r="8.4"></circle>
    <circle cx="12" cy="12" r="1.6"></circle>
    <path d="M12 10.4V4.6"></path>
    <path d="M13.6 12h5.8"></path>
    <path d="M12 13.6v5.8"></path>
    <path d="M10.4 12H4.6"></path>
  `,
  wind: `
    <path d="M3 8h11a3 3 0 1 0-3-3"></path>
    <path d="M2 13h15a3 3 0 1 1-3 3"></path>
    <path d="M4 18h9"></path>
  `,
  zap: `
    <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z"></path>
  `,
  wifi: `
    <path d="M2 8.82A15 15 0 0 1 22 8.82"></path>
    <path d="M5 12.86a10 10 0 0 1 14 0"></path>
    <path d="M8.5 16.89a5 5 0 0 1 7 0"></path>
    <path d="M12 20h.01"></path>
  `,
  "wifi-off": `
    <path d="M2 8.82A15 15 0 0 1 22 8.82"></path>
    <path d="M8.5 16.89a5 5 0 0 1 4.95-.31"></path>
    <path d="M5 12.86a10 10 0 0 1 6.24-2.81"></path>
    <path d="M2 2l20 20"></path>
  `,
  "trending-up": `
    <path d="M3 17l6-6 4 4 7-7"></path>
    <path d="M14 8h6v6"></path>
  `,
  "trending-down": `
    <path d="M3 7l6 6 4-4 7 7"></path>
    <path d="M14 16h6v-6"></path>
  `,
  minus: `
    <path d="M5 12h14"></path>
  `,
  x: `
    <path d="M18 6 6 18"></path>
    <path d="m6 6 12 12"></path>
  `,
  "alert-triangle": `
    <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"></path>
    <path d="M12 9v4"></path>
    <path d="M12 17h.01"></path>
  `,
  "check-circle": `
    <circle cx="12" cy="12" r="9"></circle>
    <path d="m9 12 2 2 4-4"></path>
  `,
  "x-circle": `
    <circle cx="12" cy="12" r="9"></circle>
    <path d="m15 9-6 6"></path>
    <path d="m9 9 6 6"></path>
  `,
  calendar: `
    <rect x="3" y="5" width="18" height="16" rx="2"></rect>
    <path d="M16 3v4"></path>
    <path d="M8 3v4"></path>
    <path d="M3 11h18"></path>
  `,
  hand: `
    <path d="M7 11V5a1 1 0 1 1 2 0v6"></path>
    <path d="M11 11V4a1 1 0 1 1 2 0v7"></path>
    <path d="M15 12V6a1 1 0 1 1 2 0v9"></path>
    <path d="M7 11a3 3 0 0 0-3 3v1a5 5 0 0 0 5 5h5a5 5 0 0 0 5-5v-2a3 3 0 0 0-3-3"></path>
  `,
  clock: `
    <circle cx="12" cy="12" r="9"></circle>
    <path d="M12 7v5l3 2"></path>
  `,
  flask: `
    <path d="M10 3v5.4L5.4 17.1A2.2 2.2 0 0 0 7.37 20h9.26a2.2 2.2 0 0 0 1.97-2.9L14 8.4V3"></path>
    <path d="M9 3h6"></path>
    <path d="M8.7 13h6.6"></path>
  `,
  bell: `
    <path d="M15 17h5l-1.4-1.4a2 2 0 0 1-.6-1.41V11a6 6 0 0 0-12 0v3.19a2 2 0 0 1-.59 1.41L4 17h5"></path>
    <path d="M10 17a2 2 0 0 0 4 0"></path>
  `,
  moon: `
    <path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a7 7 0 1 0 11 11Z"></path>
  `,
  sun: `
    <circle cx="12" cy="12" r="4"></circle>
    <path d="M12 2v2"></path>
    <path d="M12 20v2"></path>
    <path d="m4.93 4.93 1.41 1.41"></path>
    <path d="m17.66 17.66 1.41 1.41"></path>
    <path d="M2 12h2"></path>
    <path d="M20 12h2"></path>
    <path d="m6.34 17.66-1.41 1.41"></path>
    <path d="m19.07 4.93-1.41 1.41"></path>
  `,
  history: `
    <path d="M3 12a9 9 0 1 0 3-6.71"></path>
    <path d="M3 3v5h5"></path>
    <path d="M12 7v5l3 2"></path>
  `,
  "user-plus": `
    <path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2"></path>
    <circle cx="9.5" cy="7" r="3"></circle>
    <path d="M19 8v6"></path>
    <path d="M16 11h6"></path>
  `,
  trash: `
    <path d="M3 6h18"></path>
    <path d="M8 6V4h8v2"></path>
    <path d="M19 6l-1 14H6L5 6"></path>
    <path d="M10 11v6"></path>
    <path d="M14 11v6"></path>
  `,
  shield: `
    <path d="M12 3 5 6v5c0 5 3.5 8.5 7 10 3.5-1.5 7-5 7-10V6l-7-3Z"></path>
  `,
  mail: `
    <rect x="3" y="5" width="18" height="14" rx="2"></rect>
    <path d="m4 7 8 6 8-6"></path>
  `,
  camera: `
    <path d="M4 8h3l2-3h6l2 3h3a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2Z"></path>
    <circle cx="12" cy="13" r="4"></circle>
  `,
  lock: `
    <rect x="4" y="11" width="16" height="10" rx="2"></rect>
    <path d="M8 11V8a4 4 0 0 1 8 0v3"></path>
  `,
  eye: `
    <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"></path>
    <circle cx="12" cy="12" r="3"></circle>
  `,
  "eye-off": `
    <path d="m3 3 18 18"></path>
    <path d="M10.58 10.58a2 2 0 0 0 2.83 2.83"></path>
    <path d="M9.88 5.08A10.94 10.94 0 0 1 12 5c6 0 10 7 10 7a18.74 18.74 0 0 1-3.04 3.81"></path>
    <path d="M6.61 6.61A18.7 18.7 0 0 0 2 12s4 7 10 7a9.76 9.76 0 0 0 5.39-1.61"></path>
  `,
  info: `
    <circle cx="12" cy="12" r="9"></circle>
    <path d="M12 16v-4"></path>
    <path d="M12 8h.01"></path>
  `,
  close: `
    <path d="M18 6 6 18"></path>
    <path d="m6 6 12 12"></path>
  `,
  pencil: `
    <path d="M12 20h9"></path>
    <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
  `,
};

const NAV_ITEMS = [
  { view: "dashboard", label: "Dashboard", icon: "dashboard" },
  { view: "history", label: "History", icon: "history" },
  { view: "cultivation", label: "Cultivation", icon: "sprout" },
  // A grower can take a copy of the farm's own record. The page is read-only:
  // it builds a download and writes nothing back.
  { view: "reports", label: "Reports", icon: "file-text" },
];

const VIEW_HASHES = {
  dashboard: "#/",
  history: "#/history",
  cultivation: "#/cultivation",
  reports: "#/reports",
};

const VIEW_INDEX = Object.fromEntries(NAV_ITEMS.map((item, index) => [item.view, index]));
// The outgoing scene fades over 160ms (.page-content--transition-out
// .page-scene in styles.css). Waiting 300ms before swapping the route left the
// faded-out page on screen for ~140ms of dead time on every navigation, which
// read as lag rather than as motion. Hold just long enough for the fade.
const PAGE_TRANSITION_EXIT_MS = 170;
const BUTTON_PRESS_FEEDBACK_MS = 220;
const MOBILE_DASHBOARD_QUERY = "(max-width: 640px)";
const ENABLE_CUSTOM_PAGE_WHEEL_SMOOTHING = false;
const THEME_CACHE_KEY = "icucrops.theme.v1";
const REPORTS_RECENT_KEY = "icucrops.reports.recent.v1";
const REPORT_PREVIEW_TIMEOUT_MS = 30000;
// Asking for a password-change code waits on the outbound email send, which
// measured ~10.5s on the Pi and can retry up to ~37s. The 10s default aborted
// it with "The server took too long to respond. Please try again." while the
// code was already on its way -- the forgot-password screens got 45s for the
// same reason. Confirming hashes the new password (310k iterations), which
// the Pi also cannot always do inside 10s.
const PASSWORD_OTP_REQUEST_TIMEOUT_MS = 45000;
const PASSWORD_CONFIRM_TIMEOUT_MS = 30000;
// Vercel stops the function at 60s (vercel.json maxDuration). Waiting 90s
// meant the browser sat on a request the host had already killed, then
// surfaced the platform's HTML error page as an unexplained failure.
// Stopping first lets the report say what actually went wrong.
const REPORT_EXPORT_TIMEOUT_MS = 55000;
// How long a finished download's object URL is kept alive for the browser
// to pick up. Long enough for the hand-off, short enough that the file is
// not left pinned in memory afterwards.
const REPORT_BLOB_RELEASE_MS = 5000;

const REPORT_MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];


const REPORT_DATA_SECTIONS = [
  { key: "sensors", label: "Sensor Readings", hint: "Moisture, pH, EC, temperature and humidity" },
  { key: "irrigation", label: "Irrigation History", hint: "Every run with its duration and mode" },
  { key: "cultivations", label: "Cultivation Records", hint: "Planted crops and per-row health" },
  { key: "alerts", label: "Alerts", hint: "Notifications raised in the period" },
  { key: "health", label: "Sensor Health", hint: "Which devices are powered on" },
];

const REPORT_RANGE_PRESETS = [
  { key: "today", label: "Today", days: 0 },
  { key: "7d", label: "7 Days", days: 6 },
  { key: "30d", label: "30 Days", days: 29 },
  { key: "planting", label: "Since Planting", days: null },
];

const THEME_DARK = "dark";
const THEME_LIGHT = "light";
const SETTINGS_SECTIONS = [
  { key: "profile", label: "Profile", icon: "user" },
  { key: "about", label: "About Us", icon: "info" },
  { key: "developers", label: "Developers", icon: "users" },
  { key: "guide", label: "Guide", icon: "info" },
];

const ALERT_OPTIONS = ["Website Only", "Disabled"];
const DEFAULT_ALERT_MODE = ALERT_OPTIONS[0];

function normalizeAlertMode(value, { allowEmpty = false, fallback = DEFAULT_ALERT_MODE } = {}) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return allowEmpty ? "" : fallback;
  }
  if (normalized === "disabled" || normalized === "off" || normalized === "none") {
    return "Disabled";
  }
  if (
    normalized === "website only"
    || normalized === "web only"
    || normalized === "website"
    || normalized === "web"
    || normalized === "in-app"
    || normalized === "in app"
    || normalized === "email only"
    || normalized === "email"
    || normalized === "sms only"
    || normalized === "sms + email"
    || normalized === "sms"
  ) {
    return "Website Only";
  }
  return allowEmpty ? "" : fallback;
}

// Matches IRRIGATION_MIN_DURATION_SECONDS in main.py. One second, not ten:
// the entered number is the duration, and nothing here rounds it up. This is
// only a guard for an empty or unreadable box, which is not a request for a
// zero-second run.
const IRRIGATION_MIN_DURATION_SECONDS = 1;

const IRRIGATION_DURATION_FIELDS = new Set([
  "automaticDuration",
  "manualDuration",
  "scheduleDuration",
]);

const IRRIGATION_CHANNELS = [
  {
    key: "water",
    label: "Water",
    icon: "droplets",
    description: "Primary watering line",
    automaticEnabled: true,
    manualDuration: "900",
    scheduleEnabled: true,
    scheduleStartTime: "06:00",
    scheduleDuration: "1200",
    scheduleFrequency: "daily",
  },
  {
    key: "fertilizer",
    label: "Fertilizer",
    icon: "sprout",
    description: "Nutrient dosing line",
    automaticEnabled: true,
    manualDuration: "600",
    scheduleEnabled: true,
    scheduleStartTime: "06:15",
    scheduleDuration: "900",
    scheduleFrequency: "every-2-days",
  },
  {
    key: "limeSolution",
    label: "Lime Solution",
    icon: "flask",
    description: "pH balancing solution line",
    automaticEnabled: true,
    manualDuration: "480",
    scheduleEnabled: true,
    scheduleStartTime: "06:30",
    scheduleDuration: "600",
    scheduleFrequency: "weekly",
  },
];

const IRRIGATION_FREQUENCIES = [
  { value: "daily", label: "Daily" },
  { value: "every-2-days", label: "Every 2 days" },
  { value: "every-3-days", label: "Every 3 days" },
  { value: "weekly", label: "Weekly" },
];

const DEVELOPERS = [
  {
    name: "Chris Benedict Corona",
    role: "Developer",
    description: "Developed the web app, backend flow, sensor integrations, testing, and calibration support.",
    avatar: "C",
    imagePath: "../assets/ChrisPic.png",
  },
  {
    name: "Shiela Mae Abejero",
    role: "Leader",
    description: "Led the research work and organized the project papers, documentation, and study requirements.",
    avatar: "S",
    imagePath: "../assets/sheilaPic.png",
    imageScale: "96%",
  },
  {
    name: "Jhonel Azañes",
    role: "Designer",
    description: "Designed the IoT device layout and helped prepare the project documents.",
    avatar: "J",
    imagePath: "../assets/jhonelPic.png",
  },
  {
    name: "Eron Cataga",
    role: "IoT Builder",
    description: "Built and wired the IoT device and checked that the sensors worked correctly.",
    avatar: "E",
    imagePath: "../assets/EronPic.png",
  },
];

const SENSOR_HEALTH = [
  { key: "dht22", name: "DHT22" },
  { key: "moisture", name: "Soil Capacitive Sensor" },
  { key: "ph", name: "Soil pH RS485 Multi Sensor" },
  { key: "ec", name: "Soil Nutrients RS485 Multi Sensor" },
];

const SENSOR_MANAGEMENT_CARDS = [
  {
    sensorId: "moisture",
    powerKey: "moisture",
    deviceName: "Soil Capacitive Sensor",
    readingLabel: "Soil Moisture",
    icon: "droplet",
    accent: "linear-gradient(135deg, var(--green-300), var(--green-600))",
  },
  {
    sensorId: "ph",
    powerKey: "ph",
    deviceName: "Soil pH RS485 Multi Sensor",
    readingLabel: "Soil pH",
    icon: "activity",
    accent: "linear-gradient(135deg, var(--purple-500), var(--green-900))",
  },
  {
    sensorId: "ec",
    powerKey: "ec",
    deviceName: "Soil Nutrients RS485 Multi Sensor",
    readingLabel: "Soil Nutrients",
    icon: "leaf",
    accent: "linear-gradient(135deg, var(--amber-500), var(--green-600))",
  },
  {
    sensorId: "temp",
    powerKey: "dht22",
    deviceName: "DHT22",
    readingLabel: "Temperature",
    icon: "thermometer",
    accent: "linear-gradient(135deg, var(--green-600), var(--green-900))",
  },
  {
    sensorId: "humidity",
    powerKey: "dht22",
    deviceName: "DHT22",
    readingLabel: "Humidity",
    icon: "wind",
    accent: "linear-gradient(135deg, var(--green-300), var(--green-500))",
  },
];

const IOT_ROW_METRICS = [
  {
    key: "moisture",
    label: "Soil Moisture",
    unit: "%",
    icon: "droplet",
    deviceName: "Soil Capacitive Sensor",
    displayMin: 0,
    displayMax: 100,
    normalMin: 40,
    normalMax: 55,
    criticalMargin: 15.0,
  },
  {
    key: "ec",
    label: "Soil Nutrients",
    unit: "mS/cm",
    icon: "leaf",
    deviceName: "RS485 Multi Sensor",
    cardSource: "Soil Nutrients Monitor",
    displayMin: 0,
    displayMax: 3,
    normalMin: 1.4,
    normalMax: 1.8,
    criticalMargin: 0.6,
  },
  {
    key: "ph",
    label: "Soil pH",
    unit: "pH",
    icon: "activity",
    deviceName: "RS485 Multi Sensor",
    cardSource: "Soil pH Monitor",
    displayMin: 4,
    displayMax: 9,
    normalMin: 6.2,
    normalMax: 6.8,
    criticalMargin: 0.8,
  },
  {
    key: "temp",
    label: "Temperature",
    unit: "\u00B0C",
    icon: "thermometer",
    deviceName: "DHT22",
    shared: true,
    displayMin: 10,
    displayMax: 40,
    normalMin: 24,
    normalMax: 29,
    criticalMargin: 4.0,
  },
  {
    key: "humidity",
    label: "Humidity",
    unit: "%",
    icon: "wind",
    deviceName: "DHT22",
    shared: true,
    displayMin: 0,
    displayMax: 100,
    normalMin: 55,
    normalMax: 70,
    criticalMargin: 15.0,
  },
];

const DEFAULT_IOT_DEVICE_ROWS = [
  { key: "row1", label: "Row 1", moisture: null, ec: null, ph: null },
  { key: "row2", label: "Row 2", moisture: null, ec: null, ph: null },
  { key: "row3", label: "Row 3", moisture: null, ec: null, ph: null },
  { key: "row4", label: "Row 4", moisture: null, ec: null, ph: null },
];
let IOT_DEVICE_ROWS = DEFAULT_IOT_DEVICE_ROWS.map((row) => ({ ...row }));

const CULTIVATION_ROW_OPTIONS = DEFAULT_IOT_DEVICE_ROWS.map((row) => ({
  key: row.key,
  label: row.label,
}));

const DEFAULT_SHARED_DHT22_METRICS = {
  temp: null,
  humidity: null,
  capturedAt: "",
  // true/false once the backend has ever tracked the DHT22 board's MQTT
  // status, null before that -- see sensorHealthStatus(), which falls back to
  // reading freshness only in the null case.
  connected: null,
};
let SHARED_DHT22_METRICS = { ...DEFAULT_SHARED_DHT22_METRICS };

// The DHT22 as it last reported. SHARED_DHT22_METRICS is what the screen shows,
// which carries the fan and lamp's effect on the air -- see
// applyClimateResponseModel(). Kept apart so the model always works from the
// real reading, and so the Shared DHT22 sensor card can show it as measured.
let SHARED_DHT22_MEASURED = { temp: null, humidity: null };
let climateResponseState = null;
// The cards following the Pi's numbers (applyClimateResponseModel).
let climateEaseState = null;
// True when the Pi's control cycle sent modelled numbers in sharedMetrics.
let SHARED_DHT22_MODELLED_BY_PI = false;
// True when sharedMetrics carries the kiosk's cards already eased on the Pi
// (greenhouse_display_step in main.py): shown exactly as sent.
let SHARED_DHT22_EASED_BY_PI = false;

// What the automatic fan and grow light rules would do right now, and the
// thresholds behind that, straight from the backend. Kept beside the readings
// rather than inside state.sensorsPage because that object is mirrored into
// localStorage, and these are live facts with no business being restored from
// a previous session.
const DEFAULT_SENSOR_AUTOMATION = {
  // The exhaust fan answers to humidity and the lamp to temperature: each to
  // the one it can actually move. The fan extracts damp air rather than
  // stirring it, which is why humidity alone drives it -- a circulating fan
  // would push humidity up as the crop keeps transpiring into the same air.
  // The greenhouse entry is advice for a person: above the crop's temperature
  // ceiling nothing here can cool the house.
  fan: { on: false, humidity: null, readingFresh: false, thresholdPercent: null, fromCropParameters: false, tooHumid: false, tooHot: false, temperature: null, thresholdCelsius: null },
  light: { on: false, temperature: null, readingFresh: false, thresholdC: null, fromCropParameters: false },
  greenhouse: {
    open: false,
    reason: "",
    humidity: null,
    temperature: null,
    humidityCeiling: null,
    temperatureCeiling: null,
    affectedRows: [],
    allRowsAffected: false,
    activeRowCount: 0,
    readingFresh: false,
    fromCropParameters: false,
  },
};
let SENSOR_AUTOMATION = {
  fan: { ...DEFAULT_SENSOR_AUTOMATION.fan },
  light: { ...DEFAULT_SENSOR_AUTOMATION.light },
  greenhouse: { ...DEFAULT_SENSOR_AUTOMATION.greenhouse },
};

// Misting is the one actuator that closes itself. These bound what the field
// will accept: wide, because a mist is used both to settle dust for a few
// seconds and to bring a dry house up over several minutes, but not unbounded,
// so a typo cannot leave the line on all night. Kept in step with
// MISTING_MIN/MAX_DURATION_SECONDS in main.py, which enforces them.
const ACTUATOR_MIN_DURATION_SECONDS = 1;
// 50, not 900: the farm's limit since 2026-10-01.
const ACTUATOR_MAX_DURATION_SECONDS = 50;
// Shown as the box's placeholder, never as its value: the range the box takes.
// An empty box no longer means "on until Off" -- On is refused until a number
// is typed (requireActuatorRunDuration), and the backend refuses it too.
const ACTUATOR_DURATION_PLACEHOLDER_SECONDS = `${ACTUATOR_MIN_DURATION_SECONDS}-${ACTUATOR_MAX_DURATION_SECONDS}`;

const SENSOR_ACTUATORS = [
  {
    key: "fan",
    label: "Exhaust Fan Control",
    // Its own glyph now. Sharing "wind" with the Humidity metric meant the
    // fan control and a sensor reading carried the same icon on one screen.
    icon: "fan",
    // An exhaust fan, not a circulating one. A fan that only stirs the air
    // raises humidity as the crop keeps transpiring into it; this one pushes
    // the damp air out of the house, which is why humidity alone drives it.
    copy: "Choose Automatic, On, or Off for the exhaust fan.",
    accent: "linear-gradient(135deg, var(--green-500), var(--green-800))",
  },
  // The grow light holds soil-node-4/relay3/in6, beside the two fan groups
  // on in8 and in7 -- and misting holds
  // soil-node-1/relay2/in6, on GPIO32. All three move hardware, so none of
  // them carries a pendingHardware note.
  {
    key: "light",
    label: "Grow Light Control",
    icon: "zap",
    copy: "Choose Automatic, On, or Off for the grow light.",
    accent: "linear-gradient(135deg, var(--amber-500), var(--green-700))",
  },
  // Three modes since 2026-10-07. In Automatic the backend opens the mist
  // together with the water line and closes it with it, on a water run that
  // started while every planted row was below its minimum moisture
  // (build_relay_desired_state in main.py). On is the timed run below, and
  // Off keeps it off whether water runs or not.
  {
    key: "misting",
    label: "Misting Control",
    icon: "mist",
    copy: "Automatic mists with water irrigation when every planted row is low on moisture. On runs it for the seconds you set. Off keeps it off.",
    accent: "linear-gradient(135deg, var(--cyan-500), var(--green-700))",
    // Where the card rests until the backend answers. Off, not Automatic: it
    // is a water line, and main.py rests it there too (ACTUATOR_RESTING_MODES).
    restingMode: "off",
    // The only actuator with a duration. A mist left running raises the
    // humidity the fan is working to remove, and whoever started it is
    // usually elsewhere by the time that matters.
    timed: true,
  },
];

const DASHBOARD_SENSOR_GRAPH_METRICS = [
  { key: "moisture", label: "Moisture" },
  { key: "temp", label: "Temp" },
  { key: "humidity", label: "Humidity" },
  { key: "ph", label: "pH" },
  { key: "ec", label: "Nutrients" },
];

// How often the LOCAL kiosk polls the Pi for new readings.
//
// The Pi is the farm's own machine: the boards publish to its broker over the
// LAN, it writes SQLite on the same box, and the browser asking for the data is
// running on that box too. Nothing in that path leaves the building, so a poll
// costs a local request against a file that is already in page cache.
//
// This used to be 5000 with the hosted site on 3000, which had the kiosk --
// the one screen with no network between it and the data -- refreshing slower
// than a phone on mobile data. 1000 puts the panel back to reacting in about a
// second, which is what "realtime" meant here before the publish intervals
// were raised.
//
// Polling faster than this is wasted rather than harmful: the refresh only
// re-renders when dashboardLiveRefreshSnapshot() differs from the previous
// tick, so a poll that finds nothing new costs a request and no paint. What
// sets the floor is the sensors themselves -- the fastest of them samples
// every 1.5 s, so a tick under a second can never find anything the previous
// one did not.
const DASHBOARD_LIVE_SENSOR_UPDATE_MS = 1000;
const DASHBOARD_SENSOR_MAX_AGE_MS = 15 * 60 * 1000;
// How long a board may say nothing before its cards read "Offline". A live one
// republishes a reading every three seconds and its status every fifteen
// (NodeConfig::SOIL_PUBLISH_MS / STATUS_PUBLISH_MS), so this is still a dozen
// missed publishes rather than a pause -- and it matches the backend's own
// MQTT_NODE_STATUS_MAX_AGE_SECONDS, so the two sides stop disagreeing about
// when a board died. Only presence uses it; DASHBOARD_SENSOR_MAX_AGE_MS still
// decides how long a value stays worth drawing, and this window is only
// consulted at all when the board's MQTT status has never been tracked.
const SENSOR_PRESENCE_MAX_AGE_MS = 45 * 1000;
// Presence flips on a clock, not on a payload: a board that stops publishing
// leaves every timestamp exactly where it was, so no fetch can announce it.
// Re-check often enough that "Offline" appears on its own.
const SENSOR_PRESENCE_WATCHDOG_MS = 1000;
const DHT22_LIVE_MAX_AGE_MS = 30 * 1000;
const DASHBOARD_LIVE_GRAPH_SCROLL_PAUSE_MS = 900;
const INTERACTION_PERFORMANCE_PAUSE_MS = 520;
const INTERFACE_SCROLL_SETTLE_MS = 160;

const DASHBOARD_GRAPH_POINT_LIMIT = 7;
// Points across the 24-hour range: one every two hours. See the comment where
// this is used -- the multi-day ranges want few, coarse points, but a day-long
// window has to be fine enough that an outage looks like a gap in the line
// rather than like the graph itself having failed.
const DASHBOARD_GRAPH_DAY_BUCKETS = 12;
const DASHBOARD_GRAPH_DEFAULT_RANGE = "realtime";
const DASHBOARD_GRAPH_RANGES = [
  { key: "realtime", label: "Real Time", realtime: true },
  { key: "24h", label: "24 Hours", hours: 24 },
  // Growth moves in whole days, so the cultivation graph gets a short window
  // that would only add noise to the live sensor lines.
  { key: "3d", label: "3 Days", days: 3, cultivationOnly: true },
  { key: "7d", label: "7 Days", days: 7 },
  { key: "14d", label: "14 Days", days: 14 },
  { key: "30d", label: "30 Days", days: 30 },
  { key: "crop", label: "Since Planting", plantingBased: true },
];
const DASHBOARD_GRAPH_RANGE_CACHE_KEY = "icucrops.dashboardGraphRanges.v1";

const ACTIVE_CULTIVATIONS = [];

const CROP_GROWTH_PERIODS = {
  bok_choy: { min: 20, max: 30 },
  mustasa: { min: 25, max: 45 },
  green_ice_lettuce: { min: 45, max: 60 },
  pechay: { min: 30, max: 45 },
};

const USER_CULTIVATION_CROP_KEYS = Object.keys(CROP_GROWTH_PERIODS);

const CROP_LABELS = {
  bok_choy: "Bok Choy",
  mustasa: "Mustasa",
  green_ice_lettuce: "Green Ice Lettuce",
  pechay: "Pechay",
  custom: "Custom Plant",
};

const CULTIVATION_PARAMETER_FIELDS = [
  { key: "moisture", sensorId: "moisture", label: "Soil Moisture", unit: "%", icon: "droplet", step: "1" },
  { key: "ph", sensorId: "ph", label: "pH Level", unit: "pH", icon: "activity", step: "0.1" },
  { key: "temp", sensorId: "temp", label: "Temperature", unit: "\u00B0C", icon: "thermometer", step: "1" },
  { key: "humidity", sensorId: "humidity", label: "Humidity", unit: "%", icon: "wind", step: "1" },
  { key: "ec", sensorId: "ec", label: "Soil Nutrients", unit: "mS/cm", icon: "leaf", step: "0.1" },
];

const CULTIVATION_PARAMETER_PRESETS = {
  bok_choy: {
    moisture: { min: 50, max: 65 },
    ph: { min: 6, max: 7 },
    temp: { min: 18, max: 30 },
    humidity: { min: 60, max: 75 },
    ec: { min: 0.8, max: 1.5 },
  },
  mustasa: {
    moisture: { min: 65, max: 75 },
    ph: { min: 6, max: 7.5 },
    temp: { min: 15, max: 22 },
    humidity: { min: 60, max: 80 },
    ec: { min: 1.2, max: 2.4 },
  },
  green_ice_lettuce: {
    moisture: { min: 70, max: 85 },
    ph: { min: 6, max: 7 },
    temp: { min: 15, max: 23 },
    humidity: { min: 50, max: 70 },
    ec: { min: 1.0, max: 1.8 },
  },
  pechay: {
    moisture: { min: 60, max: 80 },
    ph: { min: 5.5, max: 6.5 },
    temp: { min: 18, max: 20 },
    humidity: { min: 70, max: 85 },
    ec: { min: 1.2, max: 2.0 },
  },
  custom: {
    moisture: { min: 55, max: 75 },
    ph: { min: 6, max: 7 },
    temp: { min: 18, max: 28 },
    humidity: { min: 55, max: 80 },
    ec: { min: 1.0, max: 1.8 },
  },
};

const CULTIVATION_PARAMETER_MODE_LABELS = {
  recommended: "Recommended",
  custom: "Custom",
};
const CULTIVATION_CURRENT_YEAR = new Date().getFullYear();
const CULTIVATION_DATE_MIN = `${CULTIVATION_CURRENT_YEAR}-01-01`;
const CULTIVATION_DATE_MAX = `${CULTIVATION_CURRENT_YEAR}-12-31`;

const DEFAULT_PROFILE_NAME = "User 1";
const DEFAULT_PROFILE_ROLE = "User";
const PROFILE_NAME_MIN_LENGTH = 2;
const PROFILE_NAME_MAX_LENGTH = 30;

function initialActiveCultivations() {
  return ACTIVE_CULTIVATIONS.map((item, index) => ({
    ...item,
    id: String(item.id || `active-cultivation-${index + 1}`),
    rowLabel: cultivationRowLabel(item.rowKey),
  }));
}

function readAuthenticatedProfile() {
  const session = window.ICuCropsAuth?.readSession?.();
  return {
    profileId: session?.id || "",
    profileName: session?.displayName?.trim() || DEFAULT_PROFILE_NAME,
    profileRole: session?.roleLabel || DEFAULT_PROFILE_ROLE,
    profilePhotoDataUrl: session?.profilePhotoUrl || "",
  };
}

const initialOtpCode = () => ["", "", "", "", "", ""];

function minutesAgoIso(minutes) {
  return new Date(Date.now() - (minutes * 60000)).toISOString();
}

// How many history rows are painted per page, and the initial cap. See
// historyTemplate() for the measurements behind it.
const HISTORY_RENDER_PAGE_SIZE = 50;

const initialNotifications = () => [];

function initialNotificationHistory() {
  return [];
}

function initialNotificationState() {
  return {
    notifications: initialNotifications(),
    history: initialNotificationHistory(),
  };
}

function normalizeNotificationRecord(notification) {
  const type = String(notification?.type || "success").trim().toLowerCase();
  return {
    id: String(notification?.id || ""),
    type: type === "warning" || type === "critical" ? type : "success",
    message: String(notification?.message || "").trim(),
    createdAt: String(notification?.createdAt || minutesAgoIso(0)).trim() || minutesAgoIso(0),
    read: Boolean(notification?.read),
  };
}

function mapNotificationRecords(notifications) {
  return Array.isArray(notifications) ? notifications.map(normalizeNotificationRecord) : [];
}

function applyCreatedNotification(notification) {
  const normalized = normalizeNotificationRecord(notification);
  if (!normalized.id || !normalized.message) {
    return;
  }
  state.notificationHistory = [
    normalized,
    ...state.notificationHistory.filter((item) => item.id !== normalized.id),
  ];
  state.notifications = state.notificationHistory.filter((item) => !item.read);
  renderNotificationHeaderState();
  if (state.activeView === "history") {
    renderPage();
  }
  if (state.notificationsOpen) {
    renderOverlays();
  }
  pushNotification(normalized.type, normalized.message);
}

const initialUsers = () => [];

function normalizeUserAccount(user) {
  const email = String(user?.email || "").trim().toLowerCase();
  const name = String(user?.displayName || user?.name || "").trim() || email;
  const role = String(user?.role || "user").trim().toLowerCase() === "admin" ? "admin" : "user";
  return {
    id: String(user?.id || ""),
    name,
    email,
    role,
  };
}

function mapUserAccounts(users) {
  return Array.isArray(users) ? users.map(normalizeUserAccount) : [];
}

function normalizeActiveCultivation(item) {
  const crop = String(item?.crop || item?.cropName || "").trim() || "Cultivation";
  const rowKey = String(item?.rowKey || "").trim().toLowerCase();
  const plantingDate = String(item?.plantingDate || "").trim();
  const harvestDate = String(item?.harvestDate || "").trim();
  const baseEntry = plantingDate && harvestDate
    ? buildActiveCultivationEntry({ crop, rowKey, plantingDate, harvestDate })
    : {
        id: "",
        rowKey,
        rowLabel: cultivationRowLabel(rowKey),
        crop,
        accent: "var(--green-500)",
        planted: String(item?.planted || "").trim(),
        remaining: String(item?.remaining || "").trim(),
        harvest: String(item?.harvest || "").trim(),
        remainingColor: String(item?.remainingColor || "var(--green-600)").trim(),
      };

  return {
    ...baseEntry,
    id: String(item?.id || baseEntry.id || ""),
    rowKey,
    rowLabel: String(item?.rowLabel || baseEntry.rowLabel || cultivationRowLabel(rowKey)).trim(),
    cropType: String(item?.cropType || "").trim(),
    customPlantName: String(item?.customPlantName || "").trim(),
    parameterMode: String(item?.parameterMode || "").trim(),
    parameters: item?.parameters && typeof item.parameters === "object" ? item.parameters : null,
    plantingDate: plantingDate || String(item?.plantingDate || "").trim(),
    harvestDate: harvestDate || String(item?.harvestDate || "").trim(),
  };
}

function mapActiveCultivations(cultivations) {
  return Array.isArray(cultivations) ? cultivations.map(normalizeActiveCultivation) : [];
}

const initialNewUser = () => ({
  name: "",
  email: "",
  role: "user",
  password: "",
  confirmPassword: "",
  otpCode: ["", "", "", "", "", ""],
});

const initialSensorsPageState = () => ({
  sensorPower: {
    moisture: "on",
    ph: "on",
    ec: "on",
    dht22: "on",
  },
  rowSensorPower: {
    "row1-moisture": "on",
    "row1-rs485": "on",
    "row2-moisture": "on",
    "row2-rs485": "on",
    "row3-moisture": "on",
    "row3-rs485": "on",
    "row4-moisture": "on",
    "row4-rs485": "on",
    dht22: "on",
  },
  actuatorMode: {
    fan: "automatic",
    light: "automatic",
    misting: "off",
  },
  // Seconds a timed actuator runs for. Only misting has one; 0 means "on
  // until Off is pressed", which is what this control did before it had a
  // duration at all, and is what a farm that has never set a duration should
  // get. Starting at a number would have quietly changed what On does for
  // anyone who never touched the field.
  actuatorDuration: {
    misting: 0,
  },
});

const SENSOR_CONTROL_CACHE_KEY = "icucrops.sensorControls.v1";
const IRRIGATION_ROW_SELECTION_CACHE_KEY = "icucrops.irrigation.selectedRow.v1";

function readSensorControlCache() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(SENSOR_CONTROL_CACHE_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (error) {
    return {};
  }
}

function normalizeSensorControlMap(value, allowedValues) {
  if (!value || typeof value !== "object") {
    return {};
  }

  const allowed = new Set(allowedValues);
  return Object.fromEntries(
    Object.entries(value)
      .map(([key, itemValue]) => [String(key).trim(), String(itemValue || "").trim()])
      .filter(([key, itemValue]) => key && allowed.has(itemValue)),
  );
}

// A duration is a number of seconds, not one of a fixed set of words, so it
// cannot go through normalizeSensorControlMap -- that keeps only values found
// in an allow-list and would drop every one of them.
//
// Leaving it out of the cache normalizer is what stopped a typed duration
// being saved. setActuatorRunDuration wrote it to localStorage correctly, but
// the read path ran the cache through normalizedSensorControlCache(), which
// returned only the three word-valued maps. actuatorDuration came back
// undefined, the base default (0) won, and the field was empty again on the
// next load -- so the box accepted a number, kept it until reload, and lost
// it. It survived in memory only because the live-refresh merge happened to
// spread the previous state over the base.
function normalizeActuatorDurationMap(value) {
  if (!value || typeof value !== "object") {
    return {};
  }

  const entries = Object.entries(value)
    .map(([key, itemValue]) => [String(key).trim(), Number.parseInt(itemValue, 10)])
    // 0 is a real stored answer -- "stay on until Off is pressed" -- so it is
    // kept. Only an unreadable or out-of-range one is dropped, and dropping it
    // falls back to the default rather than storing a duration nobody chose.
    .filter(([key, seconds]) =>
      key
      && Number.isFinite(seconds)
      && seconds >= 0
      && seconds <= ACTUATOR_MAX_DURATION_SECONDS);
  return Object.fromEntries(entries);
}

function normalizedSensorControlCache() {
  const cached = readSensorControlCache();
  return {
    sensorPower: normalizeSensorControlMap(cached.sensorPower, ["on", "off"]),
    rowSensorPower: normalizeSensorControlMap(cached.rowSensorPower, ["on", "off"]),
    actuatorMode: normalizeSensorControlMap(cached.actuatorMode, ["automatic", "on", "off"]),
    actuatorDuration: normalizeActuatorDurationMap(cached.actuatorDuration),
  };
}

function normalizedSensorControlPayload(controls) {
  const source = controls && typeof controls === "object" ? controls : {};
  return {
    sensorPower: normalizeSensorControlMap(source.sensorPower, ["on", "off"]),
    rowSensorPower: normalizeSensorControlMap(source.rowSensorPower, ["on", "off"]),
    actuatorMode: normalizeSensorControlMap(source.actuatorMode, ["automatic", "on", "off"]),
  };
}

function setSensorControlOptimisticLock(controlType, key, value) {
  sensorControlOptimisticLocks.set(`${controlType}:${key}`, {
    controlType,
    key,
    value,
    expiresAt: Date.now() + SENSOR_CONTROL_OPTIMISTIC_LOCK_MS,
  });
}

function sensorControlsWithOptimisticLocks(controls) {
  const stableControls = normalizedSensorControlPayload(controls);
  const now = Date.now();
  for (const [requestKey, lock] of sensorControlOptimisticLocks.entries()) {
    // The timer is a floor, not a deadline. While the save is still in flight
    // the pressed value is the truth and the server's answer is simply older
    // than the press, so an expired timer must not hand a concurrent poll the
    // stale mode. Off on the hosted site was reverting for exactly this: the
    // control round-trip there routinely outlives five seconds, and the save
    // itself bumps the "sensors" realtime scope, which guarantees a refresh
    // lands in the window between the timer expiring and the answer arriving.
    if (!lock || (lock.expiresAt <= now && !sensorControlRequests.has(requestKey))) {
      sensorControlOptimisticLocks.delete(requestKey);
      continue;
    }
    if (stableControls[lock.controlType]) {
      stableControls[lock.controlType][lock.key] = lock.value;
    }
  }
  return stableControls;
}

function sensorsPageStateWithCachedControls(base = initialSensorsPageState()) {
  const cached = normalizedSensorControlCache();
  return {
    ...base,
    sensorPower: {
      ...base.sensorPower,
      ...cached.sensorPower,
    },
    rowSensorPower: {
      ...base.rowSensorPower,
      ...cached.rowSensorPower,
    },
    actuatorMode: {
      ...base.actuatorMode,
      ...cached.actuatorMode,
    },
    actuatorDuration: {
      ...base.actuatorDuration,
      ...cached.actuatorDuration,
    },
  };
}

function writeSensorControlCache(nextState = state.sensorsPage) {
  try {
    const base = initialSensorsPageState();
    window.localStorage.setItem(SENSOR_CONTROL_CACHE_KEY, JSON.stringify({
      sensorPower: {
        ...base.sensorPower,
        ...(nextState?.sensorPower || {}),
      },
      rowSensorPower: {
        ...base.rowSensorPower,
        ...(nextState?.rowSensorPower || {}),
      },
      actuatorMode: {
        ...base.actuatorMode,
        ...(nextState?.actuatorMode || {}),
      },
      actuatorDuration: {
        ...base.actuatorDuration,
        ...(nextState?.actuatorDuration || {}),
      },
      updatedAt: new Date().toISOString(),
    }));
  } catch (error) {
    console.warn("Unable to cache sensor controls locally.", error);
  }
}

function setSynchronizedSensorPowerState(key, value) {
  const normalizedKey = String(key || "").trim();
  const normalizedValue = value === "off" ? "off" : "on";
  state.sensorsPage.sensorPower[normalizedKey] = normalizedValue;
  if (normalizedKey === "dht22") {
    state.sensorsPage.rowSensorPower.dht22 = normalizedValue;
  }
}

function initialIrrigationChannels() {
  return IRRIGATION_CHANNELS.reduce((channels, channel) => {
    channels[channel.key] = {
      automaticEnabled: channel.automaticEnabled,
      manualDuration: channel.manualDuration,
      scheduleEnabled: channel.scheduleEnabled,
      scheduleStartTime: channel.scheduleStartTime,
      scheduleDuration: channel.scheduleDuration,
      scheduleFrequency: channel.scheduleFrequency,
    };
    return channels;
  }, {});
}

function readIrrigationSelectedRowKey() {
  try {
    return String(window.localStorage.getItem(IRRIGATION_ROW_SELECTION_CACHE_KEY) || "").trim();
  } catch (error) {
    return "";
  }
}

function writeIrrigationSelectedRowKey(rowKey) {
  try {
    const normalizedRowKey = String(rowKey || "").trim();
    if (normalizedRowKey) {
      window.localStorage.setItem(IRRIGATION_ROW_SELECTION_CACHE_KEY, normalizedRowKey);
    } else {
      window.localStorage.removeItem(IRRIGATION_ROW_SELECTION_CACHE_KEY);
    }
  } catch (error) {
    // The current in-memory selection still works if browser storage is unavailable.
  }
}

const IRRIGATION_ROW_MODES = new Set(["automatic", "schedule", "manual"]);

function normalizeIrrigationRowMode(value) {
  const mode = String(value || "").trim().toLowerCase();
  return IRRIGATION_ROW_MODES.has(mode) ? mode : "automatic";
}

const initialIrrigationPageState = () => ({
  mode: "automatic",
  autoEnabled: true,
  activeManualLine: "",
  activeManualLines: {},
  activeScheduleLines: {},
  activeAutomaticLines: {},
  targetRows: {},
  scheduleArmedRows: {},
  activeManualRows: {},
  activeScheduleRows: {},
  activeAutomaticRows: {},
  selectedRowKey: readIrrigationSelectedRowKey(),
  rows: CULTIVATION_ROW_OPTIONS.map((row) => ({
    ...row,
    active: false,
    cultivationId: "",
    crop: "",
    mode: "automatic",
    controllerEnabled: false,
    readings: {},
    thresholds: {},
    sensorAvailable: {},
    needs: {},
    channels: initialIrrigationChannels(),
  })),
  overlayMode: "",
  channels: initialIrrigationChannels(),
});

function normalizeIrrigationRunMap(value, fallbackLine = "") {
  const validChannels = new Set(IRRIGATION_CHANNELS.map((channel) => channel.key));
  const lines = {};

  if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, isActive]) => {
      if (validChannels.has(key) && Boolean(isActive)) {
        lines[key] = true;
      }
    });
  }

  const fallback = String(fallbackLine || "").trim();
  if (fallback && validChannels.has(fallback)) {
    lines[fallback] = true;
  }

  return lines;
}

function firstActiveIrrigationLine(lines) {
  const normalizedLines = normalizeIrrigationRunMap(lines);
  const activeChannel = IRRIGATION_CHANNELS.find((channel) => normalizedLines[channel.key]);
  return activeChannel?.key || "";
}

function cultivationParametersFor(cropType) {
  const preset = CULTIVATION_PARAMETER_PRESETS[cropType] || CULTIVATION_PARAMETER_PRESETS.bok_choy;

  return CULTIVATION_PARAMETER_FIELDS.reduce((parameters, field) => {
    parameters[field.key] = {
      min: preset[field.key].min,
      max: preset[field.key].max,
    };
    return parameters;
  }, {});
}

function isCustomCultivation(cropType) {
  return cropType === "custom";
}

function supportsRecommendedCultivation(cropType) {
  return USER_CULTIVATION_CROP_KEYS.includes(cropType);
}

function isCultivationParameterModeAvailable(mode, cultivation = state.cultivation) {
  return mode === "recommended" && supportsRecommendedCultivation(cultivation.cropType);
}

// Bring a duration field to a value the backend will accept, and say so when
// that changes what was typed. Returns the committed string.
function commitIrrigationDurationField(target) {
  const field = target?.dataset?.irrigationField;
  if (!(target instanceof HTMLInputElement) || !IRRIGATION_DURATION_FIELDS.has(field)) {
    return null;
  }

  const typed = String(target.value ?? "").trim();
  const parsed = Number.parseInt(typed, 10);

  // Whatever was entered is the duration. Five seconds means five seconds, and
  // nothing here raises it or announces a correction -- the only value that
  // cannot be saved is one that is not a number at all.
  if (!typed || !Number.isFinite(parsed) || parsed < IRRIGATION_MIN_DURATION_SECONDS) {
    const restored = String(IRRIGATION_MIN_DURATION_SECONDS);
    target.value = restored;
    return restored;
  }

  const normalized = String(parsed);
  target.value = normalized;
  return normalized;
}

function updateIrrigationPageField(target) {
  if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) {
    return false;
  }

  const { irrigationChannel, irrigationField, irrigationRow } = target.dataset;

  if (irrigationRow && irrigationChannel && irrigationField) {
    const row = state.irrigationPage.rows.find((item) => item.key === irrigationRow);
    if (row?.active && row.channels?.[irrigationChannel]) {
      row.channels[irrigationChannel][irrigationField] = target instanceof HTMLInputElement && target.type === "checkbox"
        ? target.checked
        : target.value;
      markIrrigationRowChanged(irrigationRow);
      return true;
    }
  }

  if (irrigationChannel && irrigationField && state.irrigationPage.channels[irrigationChannel]) {
    state.irrigationPage.channels[irrigationChannel][irrigationField] = target instanceof HTMLInputElement && target.type === "checkbox"
      ? target.checked
      : target.value;
    return true;
  }

  return false;
}

function effectiveCultivationParameterMode(cultivation = state.cultivation) {
  return cultivation.parameterMode;
}

function recommendedCultivationParameters(cultivation = state.cultivation) {
  return cultivationParametersFor(cultivation.cropType || USER_CULTIVATION_CROP_KEYS[0]);
}

function activeCultivationParameters(cultivation = state.cultivation) {
  return effectiveCultivationParameterMode(cultivation) === "recommended"
    ? recommendedCultivationParameters(cultivation)
    : cultivation.parameters;
}

function selectedCultivationName(cultivation = state.cultivation) {
  if (!cultivation.cropType) {
    return "";
  }

  if (isCustomCultivation(cultivation.cropType)) {
    return cultivation.customPlantName.trim() || CROP_LABELS.custom;
  }

  return CROP_LABELS[cultivation.cropType] || CROP_LABELS.custom;
}

function daysBetweenDateInputs(startDate, endDate) {
  if (!startDate || !endDate) {
    return Number.NaN;
  }

  const start = parseDateInput(startDate);
  const end = parseDateInput(endDate);
  const diff = end.getTime() - start.getTime();
  return Math.round(diff / 86400000);
}

function selectedCultivationGrowthDays(cultivation = state.cultivation) {
  if (isCustomCultivation(cultivation.cropType)) {
    return daysBetweenDateInputs(effectivePlantingDate(), cultivation.customHarvestTargetDate);
  }

  return cropGrowthDaysForCalculation(cultivation.cropType);
}

function cropGrowthPeriodRange(cropType) {
  const range = CROP_GROWTH_PERIODS[cropType];
  if (!range || !Number.isFinite(range.min) || !Number.isFinite(range.max)) {
    return null;
  }

  return range;
}

function cropGrowthDaysForCalculation(cropType) {
  const range = cropGrowthPeriodRange(cropType);
  if (!range) {
    return Number.NaN;
  }

  return range.max;
}

function cropGrowthPeriodLabel(cropType) {
  const range = cropGrowthPeriodRange(cropType);
  if (!range) {
    return "Custom";
  }

  return `${range.min}-${range.max} days`;
}

function canCalculateCultivation(cultivation = state.cultivation) {
  return supportsRecommendedCultivation(cultivation.cropType)
    && Boolean(cultivation.rowKey)
    && effectiveCultivationParameterMode(cultivation) === "recommended";
}

const initialCultivationState = () => ({
  cropType: "",
  rowKey: "",
  customPlantName: "",
  customHarvestTargetDate: "",
  plantingDate: "",
  harvestDate: "",
  daysToHarvest: 0,
  parameterMode: "",
  parameters: cultivationParametersFor("custom"),
  successMessage: "",
  setupOpen: false,
  successOpen: false,
  parameterPreviewMode: "",
});

const initialLoginFormState = () => ({
  email: "",
  password: "",
});
const initialSensors = () => [
  {
    id: "moisture",
    name: "Soil Moisture",
    deviceName: "Soil Capacitive Sensor",
    powerKey: "moisture",
    value: null,
    unit: "%",
    icon: "droplet",
    status: "warning",
    min: 30,
    max: 70,
    percentage: 0,
    alertMode: DEFAULT_ALERT_MODE,
  },
  {
    id: "ph",
    name: "pH Level",
    deviceName: "Soil pH RS485 Multi Sensor",
    powerKey: "ph",
    value: null,
    unit: "pH",
    icon: "activity",
    status: "warning",
    min: 6,
    max: 7.5,
    percentage: 0,
    alertMode: DEFAULT_ALERT_MODE,
  },
  {
    id: "temp",
    name: "Temperature",
    deviceName: "DHT22",
    powerKey: "dht22",
    value: null,
    unit: "\u00B0C",
    icon: "thermometer",
    status: "warning",
    min: 20,
    max: 35,
    percentage: 0,
    alertMode: DEFAULT_ALERT_MODE,
  },
  {
    id: "humidity",
    name: "Humidity",
    deviceName: "DHT22",
    powerKey: "dht22",
    value: null,
    unit: "%",
    icon: "wind",
    status: "warning",
    min: 40,
    max: 80,
    percentage: 0,
    alertMode: DEFAULT_ALERT_MODE,
  },
  {
    id: "ec",
    name: "Soil Nutrients",
    deviceName: "Soil Nutrients RS485 Multi Sensor",
    powerKey: "ec",
    value: null,
    unit: "mS/cm",
    icon: "leaf",
    status: "warning",
    min: 1,
    max: 2.5,
    percentage: 0,
    alertMode: DEFAULT_ALERT_MODE,
  },
];

function initialDashboardSeries() {
  return {
    metrics: {},
    rows: {},
    rowMetrics: {},
  };
}

function initialDashboardGraphRanges() {
  const cached = readDashboardGraphRangeCache();
  return {
    sensor: normalizeDashboardGraphRangeCacheValue(cached.sensor, "sensor"),
    cultivation: normalizeDashboardGraphRangeCacheValue(cached.cultivation, "cultivation"),
  };
}

function restoreDashboardGraphRangesFromCache() {
  const cached = readDashboardGraphRangeCache();
  const current = state.dashboardGraphRanges || {};
  state.dashboardGraphRanges = {
    sensor: normalizeDashboardGraphRangeCacheValue(cached.sensor ?? current.sensor, "sensor"),
    cultivation: normalizeDashboardGraphRangeCacheValue(cached.cultivation ?? current.cultivation, "cultivation"),
  };
}

function normalizeIrrigationRowMap(value) {
  const validRows = new Set(CULTIVATION_ROW_OPTIONS.map((row) => row.key));
  const rows = {};
  if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, isActive]) => {
      if (validRows.has(key) && Boolean(isActive)) {
        rows[key] = true;
      }
    });
  }
  return rows;
}

function normalizeIrrigationChannelRowMap(value) {
  const validChannels = new Set(IRRIGATION_CHANNELS.map((channel) => channel.key));
  const result = {};
  if (value && typeof value === "object") {
    Object.entries(value).forEach(([channelKey, rows]) => {
      const normalizedRows = normalizeIrrigationRowMap(rows);
      if (validChannels.has(channelKey) && Object.keys(normalizedRows).length) {
        result[channelKey] = normalizedRows;
      }
    });
  }
  return result;
}

// The rows the next save is about. A press on one row used to send every
// row's mode and every running line, so a phone whose copy was a few seconds
// behind the Pi put the other rows back to what it last saw -- row 1's Manual
// press turned row 2 back to Automatic, and it started watering on its own.
// Only the rows marked here are sent; the backend keeps its own copy of the
// rest (see scopeRows in update_irrigation_state).
let irrigationChangedRows = new Set();

function markIrrigationRowChanged(...rowKeys) {
  rowKeys.forEach((rowKey) => {
    if (rowKey) {
      irrigationChangedRows.add(String(rowKey));
    }
  });
}

// The Start and Stop presses the next save carries, channel -> row -> on/off,
// sent instead of this page's copy of every running line. That copy is always
// a little behind, and a save carrying a run that had already ended made the
// Pi run it a second time. Same as the administrator shell; see
// apply_manual_line_changes in main.py.
let irrigationManualLineChanges = {};

function markIrrigationManualLineChange(channelKey, rowKey, isOn) {
  if (!channelKey || !rowKey) {
    return;
  }
  irrigationManualLineChanges[channelKey] = {
    ...(irrigationManualLineChanges[channelKey] || {}),
    [rowKey]: Boolean(isOn),
  };
  markIrrigationRowChanged(rowKey);
}

function irrigationRowModesPayload(scopeRows) {
  return Object.fromEntries(
    state.irrigationPage.rows
      .filter((row) => row.active && scopeRows.includes(row.key))
      .map((row) => [row.key, ["automatic", "schedule", "manual"].includes(row.mode) ? row.mode : "automatic"]),
  );
}

function irrigationRowChannelsPayload(scopeRows) {
  return Object.fromEntries(
    state.irrigationPage.rows
      .filter((row) => row.active && scopeRows.includes(row.key))
      .map((row) => [row.key, row.channels || initialIrrigationChannels()]),
  );
}

function irrigationLinesFromChannelRows(value) {
  const rowsByChannel = normalizeIrrigationChannelRowMap(value);
  return Object.fromEntries(
    IRRIGATION_CHANNELS
      .filter((channel) => Object.keys(rowsByChannel[channel.key] || {}).length)
      .map((channel) => [channel.key, true]),
  );
}

function removeIrrigationRowFromRunMap(value, rowKey) {
  const next = normalizeIrrigationChannelRowMap(value);
  Object.keys(next).forEach((channelKey) => {
    delete next[channelKey][rowKey];
    if (!Object.keys(next[channelKey]).length) {
      delete next[channelKey];
    }
  });
  return next;
}

function readDashboardGraphRangeCache() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(DASHBOARD_GRAPH_RANGE_CACHE_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (error) {
    return {};
  }
}

function normalizeDashboardGraphRangeCacheValue(value, graphKey = "sensor") {
  const normalizedGraphKey = graphKey === "cultivation" ? graphKey : "sensor";
  const normalizedValue = String(value || "").trim().toLowerCase();
  // Whatever the selector offers. The cultivation list used to hold only
  // "crop", so a picked 3/7/14/30 Days was saved as Since Planting and came
  // back that way on the next load.
  const allowedKeys = dashboardGraphRangeOptions(normalizedGraphKey).map((option) => option.key);
  if (allowedKeys.includes(normalizedValue)) {
    return normalizedValue;
  }

  return normalizedGraphKey === "cultivation" ? "crop" : DASHBOARD_GRAPH_DEFAULT_RANGE;
}

function writeDashboardGraphRangeCache(nextRanges = state.dashboardGraphRanges) {
  try {
    window.localStorage.setItem(DASHBOARD_GRAPH_RANGE_CACHE_KEY, JSON.stringify({
      sensor: normalizeDashboardGraphRangeCacheValue(nextRanges?.sensor, "sensor"),
      cultivation: normalizeDashboardGraphRangeCacheValue(nextRanges?.cultivation, "cultivation"),
      updatedAt: new Date().toISOString(),
    }));
  } catch (error) {
    // Ignore storage failures; the dashboard still works with in-memory ranges.
  }
}

const externalTemplateCache = new Map();

function createInitialState() {
  const notificationState = initialNotificationState();
  const authenticatedProfile = readAuthenticatedProfile();

  return {
    isAuthenticated: true,
    activeView: "dashboard",
    settingsOpen: false,
    settingsMenuOpen: false,
    settingsMenuPosition: null,
    notificationsOpen: false,
    logoutConfirmOpen: false,
    // Which cultivation's target range is open, by id. "" is closed.
    cultivationParametersId: "",
    // The unsaved copy the editor works on, or null while it is only being
    // read. Held apart from activeCultivations so cancelling costs nothing and
    // a live refresh cannot overwrite what is being typed.
    cultivationParametersEdit: null,
    cultivationParametersSaving: false,
    dashboardAllRowsOpen: false,
    activeSettingsTab: "profile",
    activeGuideStep: 0,
    profileName: authenticatedProfile.profileName,
    savedProfileName: authenticatedProfile.profileName,
    profileNameError: "",
    profileRole: authenticatedProfile.profileRole,
    profilePhotoDataUrl: authenticatedProfile.profilePhotoDataUrl,
    selectedProfilePhotoFile: null,
    profilePhotoObjectUrl: "",
    currentPassword: "",
    newPassword: "",
    otpCode: initialOtpCode(),
    passwordChangeOtpRequested: false,
    passwordChangeChallengeId: "",
    passwordChangeSubmitting: false,
    dashboardSensors: initialSensors(),
    dashboardSeries: initialDashboardSeries(),
    dashboardLiveSensorSeries: {},
    dashboardGraphRanges: initialDashboardGraphRanges(),
    // How many days of history the loaded series covers, so widening a graph
    // range knows whether it already holds the rows.
    dashboardSeriesDays: 0,
    selectedSensorId: null,
    sensorDraft: null,
    notifications: notificationState.notifications,
    notificationHistory: notificationState.history,
    toasts: [],
    users: initialUsers(),
    activeCultivations: initialActiveCultivations(),
    // Plantings asked for and not yet answered by an administrator. Read with
    // the crops from /api/cultivations; see list_pending_cultivation_requests.
    cultivationRequests: [],
    cultivationRequestSending: false,
    reports: initialReportsState(),
    showAddUserModal: false,
    deleteScheduleConfirmOpen: false,
    deleteScheduleTargetChannel: "",
    newUser: initialNewUser(),
    loginForm: initialLoginFormState(),
    sensorsPage: sensorsPageStateWithCachedControls(),
    irrigationPage: initialIrrigationPageState(),
    cultivation: initialCultivationState(),
    // The pending "you may not need this" confirmation, or null. Held as a
    // plain descriptor rather than a callback so it renders and re-renders
    // like every other overlay in this file.
    controlAdvisory: null,
    // Which lime tank checks have been acknowledged, keyed by row, by the
    // cultivation, and by the solution that was confirmed. A row needing the
    // other solution later -- or a new crop on the same row -- asks again.
    limeTankConfirmations: {},
    // Tank checks someone pressed Cancel on. The lime line for that row stays
    // held; this only stops an automatic or scheduled row's card from popping
    // straight back up. The row card keeps a "Check Tank" button instead.
    limeTankDeferred: {},
  };
}

let state = createInitialState();

const notificationTimers = new Map();
let pendingRouteTransition = null;
let routeTransitionTimer = 0;
let settingsMenuWatchFrame = 0;
let settingsMenuScrollSnapshot = null;
let mobileDashboardMediaQuery = null;
let mobileDashboardLayoutActive = false;
let smoothPageScrollFrame = 0;
let smoothPageScrollCurrent = 0;
let smoothPageScrollTarget = 0;
let dashboardLiveSensorGraphTimer = 0;
let dashboardLiveGraphPausedUntil = 0;
let lastDht22LiveState = null;
let dashboardScrollActivityTimer = 0;
let interfaceInteractionTimer = 0;
let interfaceScrollActivityTimer = 0;
let viewportInteractionFrame = 0;
let dashboardChartTooltip = null;
let dashboardActiveChartHoverZone = null;
let irrigationRefreshTimer = 0;
let sharedFarmRefreshTimer = 0;
let sensorPresenceWatchdogTimer = 0;
let lastSensorPresenceFingerprint = null;
let sharedFarmRefreshBusy = false;
let lastCultivationLiveRefreshAt = 0;
// How often the live loop re-seeds the reading history behind the longer graph
// ranges. The live payload keeps the cards and the recent curve current on its
// own; only the hourly archive has to come from the server, and it moves once
// an hour, so asking for it on every tick meant fetching thirty days of history
// several times a minute to redraw one number.
const SENSOR_HISTORY_REFRESH_MS = 300000;
let lastSensorHistoryRefreshAt = 0;
// Whether the backend has ever answered. A later failure says nothing about
// whether the farm has data, so it must not reset the dashboard to blanks.
let sensorOverviewEverLoaded = false;
// Guards the one widening request that follows the fast first paint.
let dashboardHistoryBackfillPending = false;
let dashboardGraphSuppressIntro = false;
const sensorControlRequests = new Map();
const sensorControlOptimisticLocks = new Map();
const SENSOR_CONTROL_OPTIMISTIC_LOCK_MS = 5000;
// The longest an irrigation save may hold off the live refresh. Reached only
// when the backend does not answer; a normal save releases the lock as soon as
// its response is applied. Short because the relay itself closes on time -- the
// lock only ever delays what the screen shows, never the water.
const IRRIGATION_SAVE_LOCK_CEILING_MS = 1500;
// A control press writes, reconciles irrigation, queues the Pi command and
// builds a fresh overview: 37 SQL statements, each a network round trip on
// the hosted backend. It needs its own deadline rather than the 10s a read
// gets, or a slow minute reverts a press that would have landed.
const SENSOR_CONTROL_REQUEST_TIMEOUT_MS = 30000;
// Two more tries before a press is given up on, spaced so a passing stall
// clears. Only network-shaped failures are retried; a refusal is final.
const SENSOR_CONTROL_RETRY_ATTEMPTS = 3;
const SENSOR_CONTROL_RETRY_DELAY_MS = 900;
let lastSensorControlError = null;
let irrigationSaveTail = Promise.resolve(true);
let irrigationSaveRevision = 0;
let irrigationSavePendingCount = 0;
let irrigationOptimisticLockUntil = 0;

const elements = {};
const buttonPressTimers = new WeakMap();

document.addEventListener("DOMContentLoaded", init);

async function init() {
  if ("scrollRestoration" in window.history) {
    window.history.scrollRestoration = "manual";
  }

  elements.sidebar = document.querySelector(".sidebar");
  elements.topbar = document.querySelector(".topbar");
  elements.appMain = document.querySelector(".app-main");
  elements.sidebarNav = document.getElementById("sidebar-nav");
  elements.pageContent = document.getElementById("page-content");
  elements.overlayRoot = document.getElementById("overlay-root");
  elements.toastRoot = document.getElementById("toast-root");
  elements.headerProfileName = document.getElementById("header-profile-name");
  elements.headerProfileRole = document.getElementById("header-profile-role");
  elements.headerProfileAvatar = document.getElementById("header-profile-avatar");
  elements.headerNotificationButton = document.getElementById("header-notification-button");
  elements.headerNotificationIcon = document.getElementById("header-notification-icon");
  elements.headerNotificationCount = document.getElementById("header-notification-count");
  elements.headerThemeToggleButton = document.getElementById("header-theme-toggle-button");
  elements.headerThemeToggleIcon = document.getElementById("header-theme-toggle-icon");

  applyTheme(readThemePreference());
  setupMobileDashboardLayout();
  bindEvents();

  // Paint the authenticated shell immediately. Independent backend/Firebase
  // reads hydrate it in parallel instead of keeping the login transition
  // blank while six network requests run one after another.
  syncViewFromHash(true);
  setupIrrigationLiveRefresh();
  setupSharedFarmLiveRefresh();
  setupSensorPresenceWatchdog();
  setupConnectionIndicator();
  void hydrateInitialAppData();
}

async function hydrateInitialAppData() {
  await Promise.all([
    preloadExternalTemplates(),
    refreshUsers({ render: false }),
    refreshProfile({ render: false }),
    refreshSensors({ render: false }),
    refreshIrrigation({ render: false }),
    refreshCultivations({ render: false }),
    refreshNotifications({ render: false }),
  ]);

  renderSidebar();
  renderHeader();
  renderPage();
  renderOverlays();
  renderToasts();
}

function setupIrrigationLiveRefresh() {
  window.clearInterval(irrigationRefreshTimer);
  // The kiosk is the screen someone stands at to open a valve, so it is the
  // one that must not lag. It was the slowest of the three: 15 s against the
  // hosted site's 3 s, on the machine that owns the data and reaches it over a
  // loopback request rather than the internet.
  //
  // 2 s here rather than the dashboard's 1 s. This page re-reads irrigation
  // settings and run state, which is more work per request than a sensor
  // snapshot, and the guards below already suppress a tick while a field is
  // focused, a save is in flight, or an optimistic lock is held -- so the
  // interval only decides how quickly a press made somewhere else shows up.
  const refreshInterval = window.ICuCropsPiMode === true ? 2000 : 3000;
  irrigationRefreshTimer = window.setInterval(() => {
    const focusedField = document.activeElement?.closest?.("[data-irrigation-field]");
    if (
      state.isAuthenticated
      && state.activeView === "irrigation"
      && !focusedField
      && irrigationSavePendingCount === 0
      && Date.now() >= irrigationOptimisticLockUntil
    ) {
      void refreshIrrigation({ render: true });
    }
  }, refreshInterval);
}

function dashboardLatestSeriesSnapshot(seriesByKey = {}) {
  return Object.fromEntries(Object.entries(seriesByKey).map(([key, points]) => [
    key,
    Array.isArray(points) && points.length ? points[points.length - 1] : null,
  ]));
}

function dashboardLiveRefreshSnapshot() {
  return {
    sensors: JSON.stringify({
      rows: IOT_DEVICE_ROWS,
      shared: SHARED_DHT22_METRICS,
      series: dashboardLatestSeriesSnapshot(state.dashboardSeries?.metrics),
      presence: dashboardSensorPresenceFingerprint(),
    }),
  };
}

// Every badge the row cards can show, as one string. Compared tick to tick so
// a board going quiet repaints on its own: the live refresh below only redraws
// when the payload JSON differs, and a board that stops publishing never
// changes the payload -- it just stops renewing it.
function dashboardSensorPresenceFingerprint() {
  const rowBadges = IOT_DEVICE_ROWS
    .map((row) => [
      ...IOT_ROW_METRICS.map((metric) => iotRowMetricStatusLabel(row, metric)),
      iotMonitorGroupStatusLabel(row, ["ec", "ph"]),
    ].join("|"))
    .join("/");
  // The Sensor Health panel turns on the same clock, and none of the row badges
  // above describe it -- a board can go quiet without moving a single one of
  // them -- so its badges have to reach this string too, or the watchdog never
  // learns the panel needs repainting.
  const healthBadges = sensorHealthItems()
    .map((sensor) => `${sensor.name}:${sensor.badge}`)
    .join("|");
  return `${rowBadges}#${healthBadges}`;
}

// Repaints the moment a board's silence passes the presence window, without
// waiting for the next poll and without a reload. Costs one string compare per
// tick; it only touches the DOM when a badge actually changed.
function setupSensorPresenceWatchdog() {
  window.clearInterval(sensorPresenceWatchdogTimer);
  lastSensorPresenceFingerprint = null;
  sensorPresenceWatchdogTimer = window.setInterval(() => {
    if (!state.isAuthenticated || document.hidden) {
      return;
    }

    const fingerprint = dashboardSensorPresenceFingerprint();
    if (fingerprint === lastSensorPresenceFingerprint) {
      return;
    }

    const isFirstReading = lastSensorPresenceFingerprint === null;
    lastSensorPresenceFingerprint = fingerprint;
    if (isFirstReading) {
      return;
    }

    // The regular refresh already repaints whatever the payload changed. This
    // only has to cover the flips it cannot see, so patch the cards in place
    // rather than re-rendering the page underneath the user.
    const patched = state.activeView === "dashboard"
      && [updateDashboardRowCards(), updateSensorHealthCards()].some(Boolean);
    if (patched || state.selectedSensorId) {
      renderOverlays();
    }
  }, SENSOR_PRESENCE_WATCHDOG_MS);
}

// Cloud-sync state, shown in the top bar.
//
// /api/health answers {"ok": true} when Supabase is reachable and
// {"ok": false, "degraded": true} when it is not -- the backend serves from
// local SQLite either way. So "Offline" here means changes are queued for the
// next sync, not that anything has stopped working, and the wording says so:
// an operator who reads "Offline" as "broken" walks out to the greenhouse for
// something that fixes itself.
//
// Deliberately not folded into the dashboard refresh above. That loop is gated
// on the active view, on authentication and on scroll state, and the
// connection state has to keep updating regardless of all three.
let connectionIndicatorTimer = null;
const CONNECTION_INDICATOR_INTERVAL_MS = 15000;

function applyConnectionState(online, { piDown = false } = {}) {
  const pill = document.querySelector("#connection-indicator");
  const label = document.querySelector("#connection-indicator-label");
  if (!pill || !label) return;
  pill.hidden = false;
  pill.classList.toggle("is-online", online);
  pill.classList.toggle("is-offline", !online);
  // Just Online or Offline. The badge sits in a tight topbar next to the farm
  // name, and a third wording made it the widest thing in the bar for a
  // distinction most people reading it do not need to act on.
  //
  // The two offline causes still differ, so they stay in the tooltip: the
  // cloud being unreachable fixes itself, whereas the greenhouse Pi having
  // stopped means the readings on screen are old and a control pressed here
  // will not reach the hardware.
  label.textContent = online ? "Online" : "Offline";
  pill.title = online
    ? "Syncing to the cloud."
    : piDown
      ? "The greenhouse Pi has stopped reporting. Readings shown are the last it sent, and controls will not reach the hardware."
      : "No cloud connection. Working from this device; changes sync when it returns.";
}

async function refreshConnectionIndicator() {
  try {
    // cache:"no-store" matters on the kiosk: a cached 200 from when the link
    // was up would keep reporting Online for as long as the entry lived.
    const response = await fetch("/api/health", { cache: "no-store" });
    if (!response.ok) {
      applyConnectionState(false);
      return;
    }
    const payload = await response.json();
    // On the hosted site, what the operator needs to know is whether the farm's
    // Pi is still reporting in. Supabase keeps serving the last rows the Pi
    // ever pushed, so a dead Pi looks like a quiet one: the dashboard was
    // equally green either way. Answered first because it is the more serious
    // condition -- a farm whose Pi is down is not merely unsynced.
    if (payload?.piOnline === false) {
      applyConnectionState(false, { piDown: true });
      return;
    }
    // "cloudOnline" when the sync daemon is publishing it, and it is the only
    // signal that works on the Pi. There, the database is the local SQLite
    // file, so it is reachable whether or not the farm has internet, "degraded"
    // never fires, and this badge sat on "Online" through every outage. The
    // daemon is the process actually talking to Supabase, so its verdict is
    // the truthful one.
    //
    // Absent -- no daemon, as on the hosted site, or its state file too old to
    // trust -- this falls back to the database signal, which is correct there:
    // on Vercel the database IS the cloud, so an unreachable one is exactly
    // what being offline means.
    if (typeof payload?.cloudOnline === "boolean") {
      applyConnectionState(payload.cloudOnline);
      return;
    }
    if (payload?.piOnline === true) {
      applyConnectionState(true);
      return;
    }
    // Explicitly "degraded", not merely "not ok": a backend that is genuinely
    // failing should not be reported as a healthy offline Pi.
    applyConnectionState(payload?.ok === true && payload?.degraded !== true);
  } catch (_error) {
    // The request itself failing is the clearest offline signal there is.
    applyConnectionState(false);
  }
}

function setupConnectionIndicator() {
  window.clearInterval(connectionIndicatorTimer);
  refreshConnectionIndicator();
  connectionIndicatorTimer = window.setInterval(
    refreshConnectionIndicator,
    CONNECTION_INDICATOR_INTERVAL_MS,
  );
  // The browser's own events are a free head start on the poll: they fire the
  // moment the interface changes, where the interval can be up to 15s behind.
  // They report the local link only -- not whether Supabase is reachable --
  // so each one triggers a real check rather than setting the state directly.
  window.addEventListener("online", refreshConnectionIndicator);
  window.addEventListener("offline", refreshConnectionIndicator);
  // A kiosk left on a dark panel stops firing timers reliably; re-check on the
  // way back so the first thing an operator sees is current.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshConnectionIndicator();
  });
}

function setupSharedFarmLiveRefresh() {
  window.clearInterval(sharedFarmRefreshTimer);
  const piLocalLive = window.ICuCropsPiMode === true;
  // The kiosk polls fastest, because it is the only screen with no network
  // between it and the data. The worry this used to carry -- that faster
  // polling makes Chromium rebuild card and SVG regions before the small GPU
  // has painted the previous frame -- does not apply to a tick that finds
  // nothing new: the body below compares dashboardLiveRefreshSnapshot()
  // against the previous tick and returns without rendering when they match,
  // so an unchanged farm costs a local request and no paint. When the snapshot
  // does differ there is genuinely new data, and that frame is the one the
  // operator is standing there waiting for.
  const refreshInterval = piLocalLive ? DASHBOARD_LIVE_SENSOR_UPDATE_MS : 3000;
  sharedFarmRefreshTimer = window.setInterval(async () => {
    const piInteractionActive = piLocalLive && (
      Date.now() < dashboardLiveGraphPausedUntil
      || document.body.classList.contains("is-interface-scrolling")
      || document.body.classList.contains("is-motion-paused")
    );
    if (
      sharedFarmRefreshBusy
      || document.hidden
      || piInteractionActive
      || !state.isAuthenticated
      || document.activeElement?.closest?.("input, textarea, [contenteditable='true'], select:not([data-graph-range])")
      || !["dashboard", "cultivation", "sensors", "irrigation"].includes(state.activeView)
    ) {
      return;
    }

    sharedFarmRefreshBusy = true;
    const now = Date.now();
    const refreshCultivationsNow = !piLocalLive || now - lastCultivationLiveRefreshAt >= 15000;
    const previousCultivations = JSON.stringify([state.activeCultivations, state.cultivationRequests]);
    const refreshDashboardSensors = ["dashboard", "cultivation", "sensors"].includes(state.activeView);
    const previousSnapshot = refreshDashboardSensors ? dashboardLiveRefreshSnapshot() : null;
    // `live` was tied to piLocalLive, so only the kiosk ever took the light
    // payload -- the hosted dashboards, on the slower connection, pulled the
    // full history every few seconds instead. Both take it now, and both
    // re-seed the archive on the interval above.
    const wantsHistory = refreshDashboardSensors
      && now - lastSensorHistoryRefreshAt >= SENSOR_HISTORY_REFRESH_MS;
    try {
      const [cultivationsLoaded, sensorsLoaded] = await Promise.all([
        refreshCultivationsNow
          ? refreshCultivations({ render: false })
          : Promise.resolve(false),
        refreshDashboardSensors
          ? refreshSensors({ render: false, live: !wantsHistory })
          : Promise.resolve(false),
      ]);
      if (cultivationsLoaded) {
        lastCultivationLiveRefreshAt = now;
      }
      const cultivationsChanged = cultivationsLoaded
        && previousCultivations !== JSON.stringify([state.activeCultivations, state.cultivationRequests]);
      const nextSnapshot = sensorsLoaded ? dashboardLiveRefreshSnapshot() : null;
      const dht22LiveState = dashboardDht22ReadingIsFresh();
      const dht22FreshnessChanged = lastDht22LiveState !== null
        && lastDht22LiveState !== dht22LiveState;
      lastDht22LiveState = dht22LiveState;
      const sensorMetricsChanged = sensorsLoaded
        && (previousSnapshot?.sensors !== nextSnapshot?.sensors || dht22FreshnessChanged);
      const sensorsChanged = sensorMetricsChanged;
      if (cultivationsChanged || sensorsChanged) {
        if (state.activeView === "dashboard" && reconcileDashboardLiveState({
          sensorMetricsChanged,
          cultivationsChanged,
          refreshCultivationHealth: sensorMetricsChanged && refreshCultivationsNow,
        })) {
          renderOverlays();
        } else if (state.activeView === "cultivation" && reconcileCultivationLiveState({ cultivationsChanged })) {
          renderOverlays();
        } else if (state.activeView === "sensors" && reconcileSensorsLiveState()) {
          renderOverlays();
        } else {
          renderPage();
          renderOverlays();
        }
      }
    } finally {
      sharedFarmRefreshBusy = false;
    }
  }, refreshInterval);
}

function updateDashboardRowCards() {
  if (!elements.pageContent) {
    return false;
  }

  const visibleRows = dashboardRowsToShow();
  let updated = false;

  const desktopGrid = elements.pageContent.querySelector(".iot-row-dashboard-grid");
  if (desktopGrid) {
    updated = replaceChildrenWhenChanged(
      desktopGrid,
      visibleRows.map(iotDashboardRowCardTemplate).join(""),
    ) || updated;
  }

  const mobileList = elements.pageContent.querySelector(".mobile-row-list");
  if (mobileList) {
    updated = replaceChildrenWhenChanged(
      mobileList,
      visibleRows.map(mobileIotRowCardTemplate).join(""),
    ) || updated;
  }

  return updated;
}

// Both Sensor Health surfaces -- the desktop panel and the mobile chip strip --
// so an offline board reaches the badge without waiting for the next poll and
// without re-rendering the page underneath whoever is reading it.
function updateSensorHealthCards() {
  if (!elements.pageContent) {
    return false;
  }

  const items = sensorHealthItems();
  let updated = false;

  const healthGrid = elements.pageContent.querySelector(".health-grid");
  if (healthGrid) {
    updated = replaceChildrenWhenChanged(
      healthGrid,
      items.map(healthItemTemplate).join(""),
    ) || updated;
  }

  const mobileHealthGrid = elements.pageContent.querySelector(".mobile-health-grid");
  if (mobileHealthGrid) {
    updated = replaceChildrenWhenChanged(
      mobileHealthGrid,
      items.map(mobileHealthChipTemplate).join(""),
    ) || updated;
  }

  return updated;
}

// sensorsChanged is what the realtime feed reports: one scope covering every
// sensor-shaped change. It
// was not among the names read here, so a live sensor update patched nothing,
// returned false, and realtime-sync fell back to rebuilding the whole page --
// dozens of times a minute on a farm that is publishing readings, which is
// what made the kiosk feel like it was hanging.
function reconcileDashboardLiveState({
  sensorsChanged = false,
  sensorMetricsChanged = sensorsChanged,
  cultivationsChanged = false,
  refreshCultivationHealth = false,
} = {}) {
  if (!state.isAuthenticated || state.activeView !== "dashboard" || !elements.pageContent) {
    return false;
  }

  let patched = false;

  dashboardGraphSuppressIntro = true;
  try {
    if (sensorMetricsChanged || cultivationsChanged) {
      if (updateDashboardRowCards()) {
        patched = true;
      }
      if (updateSensorHealthCards()) {
        patched = true;
      }
    }

    if (sensorMetricsChanged) {
      renderDashboardLiveGraphSections("sensor");
      patched = true;
    }

    if (cultivationsChanged || refreshCultivationHealth) {
      renderDashboardLiveGraphSections("cultivation");
      patched = true;
    }
  } finally {
    dashboardGraphSuppressIntro = false;
  }

  return patched;
}

function mapCultivationRequests(requests) {
  return Array.isArray(requests)
    ? requests
      .filter((item) => item && typeof item === "object" && String(item.id || "").trim())
      .map((item) => ({
        id: String(item.id).trim(),
        rowKey: String(item.rowKey || "").trim(),
        rowLabel: String(item.rowLabel || "").trim() || cultivationRowLabel(String(item.rowKey || "")),
        cropName: String(item.cropName || "").trim(),
        plantingDate: String(item.plantingDate || "").trim(),
        requestedBy: String(item.requestedByName || item.requestedByEmail || "").trim(),
        requestedByEmail: String(item.requestedByEmail || "").trim().toLowerCase(),
      }))
    : [];
}

function pendingCultivationRequestForRow(rowKey) {
  return state.cultivationRequests.find((item) => item.rowKey === rowKey) || null;
}

function cultivationRequestTemplate(request) {
  const ownEmail = String(window.ICuCropsAuth?.readSession?.()?.email || "").trim().toLowerCase();
  const who = ownEmail && ownEmail === request.requestedByEmail
    ? "You"
    : (request.requestedBy || "Another user");
  const planted = request.plantingDate ? formatLongDate(request.plantingDate) : "";
  return `
    <div class="cultivation-item cultivation-item--request">
      <div class="cultivation-item__meta">
        <div class="cultivation-item__icon" aria-hidden="true">
          ${icon("clock")}
        </div>
        <div>
          <p class="user-row__name">${escapeHtml(request.cropName)}</p>
          <p class="section-copy">${escapeHtml(request.rowLabel)} &middot; Requested by ${escapeHtml(who)}</p>
          <p class="section-copy">Planting: ${escapeHtml(planted)}</p>
        </div>
      </div>
      <div class="cultivation-item__right">
        <div class="text-right cultivation-item__summary">
          <p class="section-copy">Waiting for an administrator</p>
        </div>
      </div>
    </div>
  `;
}

function activeCultivationsPanelContentTemplate() {
  return `
    ${state.cultivationRequests.length ? `
      <h3 class="section-title">Waiting for Approval</h3>
      ${state.cultivationRequests.map(cultivationRequestTemplate).join("")}
    ` : ""}
    <h3 class="section-title">Active Cultivations</h3>
    ${state.activeCultivations.length
      ? state.activeCultivations.map(activeCultivationTemplate).join("")
      : `
        <div class="cultivation-item cultivation-item--empty">
          <p class="section-copy">No active cultivations yet.</p>
        </div>
      `}
  `;
}

function reconcileCultivationLiveState({ cultivationsChanged = false } = {}) {
  if (!state.isAuthenticated || state.activeView !== "cultivation" || !elements.pageContent) {
    return false;
  }
  if (!cultivationsChanged) {
    return true;
  }

  const activePanel = elements.pageContent.querySelector(".cultivation-panel--active");
  if (!activePanel) {
    return false;
  }
  activePanel.innerHTML = activeCultivationsPanelContentTemplate();
  return true;
}

async function refreshUsers({ render = true } = {}) {
  const requestJson = window.ICuCropsAuth?.requestJson;
  if (typeof requestJson !== "function") {
    if (render) {
      renderPage();
      renderOverlays();
    }
    return false;
  }

  try {
    const response = await requestJson("/api/users");
    state.users = mapUserAccounts(response.users);
  } catch (error) {
    if (!state.users.length) {
      state.users = initialUsers();
    }
    console.warn("Unable to load user accounts from the backend.", error);
  }

  if (render) {
    renderPage();
    renderOverlays();
  }
  return true;
}

function getAuthenticatedSessionUserId() {
  return String(window.ICuCropsAuth?.readSession?.()?.id || "").trim();
}

// The id, re-fetched from the backend when the stored session has lost it.
//
// Every profile route is keyed on the id (/api/profile/<user_id> and both
// password OTP routes), so a session that still holds a valid token but no id
// could not save a profile, change a password or even ask for an OTP -- it
// answered "Logged-in account could not be detected" while the dashboard
// itself stayed signed in and live.
//
// /api/auth/session resolves the user from the Authorization token rather than
// from an id, so it is exactly the door that still works in that state. The
// recovered id is written straight back, so this costs one request once.
//
// writeSession() no longer drops the id, so new sessions cannot land here;
// this repairs the ones already stored in a browser.
async function resolveAuthenticatedSessionUserId() {
  const stored = getAuthenticatedSessionUserId();
  if (stored) {
    return stored;
  }

  const session = window.ICuCropsAuth?.readSession?.();
  const requestJson = window.ICuCropsAuth?.requestJson;
  if (!session?.accessToken || typeof requestJson !== "function") {
    return "";
  }

  try {
    const response = await requestJson("/api/auth/session");
    const recovered = String(response?.user?.id || "").trim();
    if (!recovered) {
      return "";
    }
    window.ICuCropsAuth?.writeSession?.({
      ...session,
      id: recovered,
      displayName: response.user.displayName || session.displayName,
      email: response.user.email || session.email,
      role: response.user.role || session.role,
    });
    return recovered;
  } catch (error) {
    console.warn("Unable to recover the signed-in account id.", error);
    return "";
  }
}

function getAuthenticatedSessionRole() {
  return String(window.ICuCropsAuth?.readSession?.()?.role || "").trim().toLowerCase();
}

function releaseProfilePhotoObjectUrl() {
  if (state.profilePhotoObjectUrl) {
    URL.revokeObjectURL(state.profilePhotoObjectUrl);
    state.profilePhotoObjectUrl = "";
  }
}

function syncAuthenticatedProfileSession(user) {
  const session = window.ICuCropsAuth?.readSession?.();
  if (!session || !window.ICuCropsAuth?.writeSession) {
    return;
  }

  // A served profile record is authoritative about its own photo. Falling back to
  // the stored session when the backend reports none resurrects a deleted photo
  // URL that can only ever answer 404, and rewrites it back into storage so it
  // survives every reload. Only guess when the response carried no photo field.
  const servedPhotoUrl = user && "profilePhotoUrl" in user
    ? String(user.profilePhotoUrl || "").trim()
    : state.profilePhotoDataUrl || String(session.profilePhotoUrl || "").trim();

  window.ICuCropsAuth.writeSession({
    id: user?.id || session.id,
    displayName: user?.displayName || state.savedProfileName,
    email: user?.email || session.email,
    role: user?.role || session.role,
    profilePhotoUrl: servedPhotoUrl,
  });
}

function extractRequestMessage(error, fallback) {
  if (error && typeof error === "object" && "payload" in error && error.payload?.message) {
    return String(error.payload.message);
  }

  // A request that never reached the server has no message worth showing. The
  // browser's own wording for that is "Failed to fetch" (Safari says "Load
  // failed", Firefox "NetworkError"), which went straight into a toast and told
  // the user nothing about what had happened or what to do. The same guard is
  // already on the forgot-password screens; the dashboards never got it, which
  // is why the string kept surfacing here long after it was thought fixed.
  if (
    error instanceof TypeError
    && /failed to fetch|networkerror|load failed/i.test(String(error.message || ""))
  ) {
    return fallback;
  }

  if (
    error
    && typeof error === "object"
    && "code" in error
    && String(error.code || "").toUpperCase() === "INVALID_API_RESPONSE"
  ) {
    return fallback;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}

function sensorStatusFromRange(value, min, max) {
  const numericValue = Number.parseFloat(value);
  if (!Number.isFinite(numericValue)) {
    return "critical";
  }
  if (numericValue < min || numericValue > max) {
    return "warning";
  }
  return "normal";
}

function sensorPercentageFromRange(value, min, max) {
  const numericValue = Number.parseFloat(value);
  if (!Number.isFinite(numericValue)) {
    return 0;
  }

  const span = max - min;
  if (!span) {
    return 0;
  }

  const percent = ((numericValue - min) / span) * 100;
  return Math.max(0, Math.min(100, percent));
}

function normalizeSeriesPoints(points) {
  if (!Array.isArray(points)) {
    return [];
  }

  return points
    .map((point) => {
      const rawValue = point && typeof point === "object" ? point.value : point;
      const value = Number.parseFloat(rawValue);
      if (!Number.isFinite(value)) {
        return null;
      }
      return {
        value,
        capturedAt: String(point?.capturedAt || "").trim(),
      };
    })
    .filter(Boolean);
}

function normalizeRowDailyPoints(points) {
  if (!Array.isArray(points)) {
    return [];
  }

  return points
    .map((point) => {
      const value = Number.parseFloat(point?.value);
      const date = String(point?.date || "").trim().slice(0, 10);
      return Number.isFinite(value) && date ? { value, date } : null;
    })
    .filter(Boolean);
}

function normalizeRowDailySeries(rows) {
  const incoming = rows && typeof rows === "object" ? rows : {};
  const normalized = {};

  for (const row of DEFAULT_IOT_DEVICE_ROWS) {
    const metrics = incoming[row.key] && typeof incoming[row.key] === "object" ? incoming[row.key] : {};
    normalized[row.key] = {
      moisture: normalizeRowDailyPoints(metrics.moisture),
      ec: normalizeRowDailyPoints(metrics.ec),
      ph: normalizeRowDailyPoints(metrics.ph),
    };
  }

  return normalized;
}

function normalizeDashboardSeries(series = {}) {
  const incomingMetrics = series.metrics && typeof series.metrics === "object" ? series.metrics : {};
  const metrics = {};

  for (const metric of DASHBOARD_SENSOR_GRAPH_METRICS) {
    metrics[metric.key] = normalizeSeriesPoints(incomingMetrics[metric.key]);
  }

  return {
    metrics,
    rows: normalizeRowDailySeries(series.rows),
    rowMetrics: normalizeRowMetricSeries(series.rowMetrics),
  };
}

// The soil readings the dashboard graph draws for one row. `metrics` averages
// every row's boards into one line, which is right for nothing on a dashboard
// that shows a single row: a row reading 0% moisture sat above a graph reading
// 28% because the other rows were wet.
const DASHBOARD_ROW_GRAPH_METRIC_KEYS = ["moisture", "ec", "ph"];

function normalizeRowMetricSeries(rows) {
  const incoming = rows && typeof rows === "object" ? rows : {};
  const normalized = {};

  for (const row of DEFAULT_IOT_DEVICE_ROWS) {
    const metrics = incoming[row.key] && typeof incoming[row.key] === "object" ? incoming[row.key] : {};
    normalized[row.key] = Object.fromEntries(
      DASHBOARD_ROW_GRAPH_METRIC_KEYS.map((metricKey) => [metricKey, normalizeSeriesPoints(metrics[metricKey])]),
    );
  }

  return normalized;
}

// A full payload used to replace the whole series outright. That was harmless
// while the dashboard asked for one on every tick, but it now re-seeds only
// every few minutes and builds the trace from live payloads in between --
// so replacing threw away everything accumulated since the last re-seed. On the
// Real Time range that left a single sample, which draws one dot at the right
// edge and no line at all: a graph that looks like it stopped working.
//
// Union by capturedAt instead. The server's history and the points merged in
// live are the same readings, so a shared timestamp is the same sample.
function mergeDashboardSeries(existing, incoming) {
  const current = normalizeDashboardSeries(existing);
  const next = normalizeDashboardSeries(incoming);

  const unite = (mine, theirs) => {
    const merged = new Map();
    [...normalizeSeriesPoints(mine), ...normalizeSeriesPoints(theirs)].forEach((point) => {
      if (point.capturedAt) {
        merged.set(point.capturedAt, point);
      }
    });
    return [...merged.values()]
      .sort((left, right) => Date.parse(left.capturedAt) - Date.parse(right.capturedAt))
      .slice(-900);
  };

  const metrics = {};
  for (const key of Object.keys(next.metrics)) {
    metrics[key] = unite(current.metrics?.[key], next.metrics[key]);
  }
  const rowMetrics = {};
  for (const rowKey of Object.keys(next.rowMetrics)) {
    rowMetrics[rowKey] = {};
    for (const metricKey of DASHBOARD_ROW_GRAPH_METRIC_KEYS) {
      rowMetrics[rowKey][metricKey] = unite(
        current.rowMetrics?.[rowKey]?.[metricKey],
        next.rowMetrics[rowKey][metricKey],
      );
    }
  }
  // Row history is daily and rebuilt server-side; nothing live accumulates there.
  return { metrics, rows: next.rows, rowMetrics };
}

function appendLiveSeriesPoint(points, value, capturedAt) {
  const numericValue = Number.parseFloat(value);
  const timestamp = String(capturedAt || "").trim();
  if (!Number.isFinite(numericValue) || !timestamp) {
    return normalizeSeriesPoints(points);
  }

  const merged = new Map();
  normalizeSeriesPoints(points).forEach((point) => {
    if (point.capturedAt) {
      merged.set(point.capturedAt, point);
    }
  });
  merged.set(timestamp, { value: numericValue, capturedAt: timestamp });
  return [...merged.values()]
    .sort((left, right) => Date.parse(left.capturedAt) - Date.parse(right.capturedAt))
    .slice(-900);
}

function mergeLiveSensorOverviewSeries(response = {}) {
  const current = normalizeDashboardSeries(state.dashboardSeries);
  const sensors = response.sensors && typeof response.sensors === "object" ? response.sensors : {};
  for (const metric of DASHBOARD_SENSOR_GRAPH_METRICS) {
    const reading = sensors[metric.key];
    // seriesValue, where the payload has one, is the number the history series
    // holds for this same reading. The card's value is eased and keeps moving
    // under one captured_at, so plotting it made each browser's line depend on
    // when it last reloaded the history -- admin and user drew different lines.
    const seriesValue = Number.parseFloat(reading?.seriesValue);
    current.metrics[metric.key] = appendLiveSeriesPoint(
      current.metrics[metric.key],
      Number.isFinite(seriesValue) ? seriesValue : reading?.value,
      reading?.capturedAt,
    );
  }
  const liveRows = Array.isArray(response.rows) ? response.rows : [];
  for (const row of liveRows) {
    const rowSeries = current.rowMetrics[row?.key];
    if (!rowSeries) {
      continue;
    }
    for (const metricKey of DASHBOARD_ROW_GRAPH_METRIC_KEYS) {
      rowSeries[metricKey] = appendLiveSeriesPoint(
        rowSeries[metricKey],
        row[metricKey],
        dashboardRowMetricCapturedAt(row, metricKey),
      );
    }
  }
  state.dashboardSeries = current;
}

function applySensorOverviewResponse(response = {}) {
  const hasSensorMap = response.sensors && typeof response.sensors === "object";
  const sensorMap = hasSensorMap ? response.sensors : {};
  const controls = sensorControlsWithOptimisticLocks(response.controls);
  const rows = Array.isArray(response.rows) ? response.rows : [];
  const sharedMetrics = response.sharedMetrics && typeof response.sharedMetrics === "object"
    ? response.sharedMetrics
    : {};

  if (hasSensorMap) {
    const currentDashboardSensors = Object.fromEntries(
      (state.dashboardSensors || []).map((sensor) => [sensor.id, sensor]),
    );
    state.dashboardSensors = initialSensors().map((sensor) => {
      const currentSensor = { ...sensor, ...(currentDashboardSensors[sensor.id] || {}) };
      const backendReading = sensorMap[sensor.id];
      const soilDecimals = { moisture: 1, ec: 3, ph: 2 }[sensor.id];
      const numericValue = soilDecimals === undefined
        ? Number.parseFloat(backendReading?.value)
        : soilReadingAtBoardPrecision(backendReading?.value, soilDecimals);
      if (!Number.isFinite(numericValue)) {
        return currentSensor;
      }

      return {
        ...currentSensor,
        value: numericValue,
        status: sensorStatusFromRange(numericValue, currentSensor.min, currentSensor.max),
        percentage: sensorPercentageFromRange(numericValue, currentSensor.min, currentSensor.max),
        alertMode: normalizeAlertMode(backendReading?.alertMode || currentSensor.alertMode),
        hardwareIdentifier: String(backendReading?.hardwareIdentifier || currentSensor.hardwareIdentifier || "").trim(),
        capturedAt: String(backendReading?.capturedAt || currentSensor.capturedAt || "").trim(),
      };
    });
  }

  if (rows.length) {
    const fallbackRows = Object.fromEntries(DEFAULT_IOT_DEVICE_ROWS.map((row) => [row.key, row]));
    IOT_DEVICE_ROWS = rows.map((row) => {
      const fallbackRow = fallbackRows[row?.key] || { key: "", label: "" };
      return {
        ...fallbackRow,
        ...row,
        // Shown at the boards' own precision. After a fertilizer or lime run
        // the Pi stores the easing EC or pH with four decimals (0.7456 mS/cm,
        // 4.9519 pH); the reading itself is unchanged, only how it is shown.
        moisture: Number.isFinite(Number.parseFloat(row?.moisture))
          ? soilReadingAtBoardPrecision(row.moisture, 1)
          : fallbackRow.moisture,
        ec: Number.isFinite(Number.parseFloat(row?.ec))
          ? soilReadingAtBoardPrecision(row.ec, 3)
          : fallbackRow.ec,
        ph: Number.isFinite(Number.parseFloat(row?.ph))
          ? soilReadingAtBoardPrecision(row.ph, 2)
          : fallbackRow.ph,
      };
    });
  }

  if (response.sharedMetrics && typeof response.sharedMetrics === "object") {
    SHARED_DHT22_METRICS = {
      ...DEFAULT_SHARED_DHT22_METRICS,
      ...SHARED_DHT22_METRICS,
      ...(Number.isFinite(Number.parseFloat(sharedMetrics.temp))
        ? { temp: Number.parseFloat(sharedMetrics.temp) }
        : {}),
      ...(Number.isFinite(Number.parseFloat(sharedMetrics.humidity))
        ? { humidity: Number.parseFloat(sharedMetrics.humidity) }
        : {}),
      capturedAt: String(sharedMetrics.capturedAt || SHARED_DHT22_METRICS.capturedAt || "").trim(),
      connected: typeof sharedMetrics.connected === "boolean" ? sharedMetrics.connected : null,
    };
    // The DHT22 as measured. The Pi sends it apart from the modelled numbers
    // above; the hosted API sends only the DHT22, so temp/humidity are it.
    const measured = sharedMetrics.measured && typeof sharedMetrics.measured === "object"
      ? sharedMetrics.measured
      : sharedMetrics;
    SHARED_DHT22_MEASURED = {
      temp: Number.isFinite(Number.parseFloat(measured.temp))
        ? Number.parseFloat(measured.temp)
        : SHARED_DHT22_MEASURED.temp,
      humidity: Number.isFinite(Number.parseFloat(measured.humidity))
        ? Number.parseFloat(measured.humidity)
        : SHARED_DHT22_MEASURED.humidity,
    };
    // authoritative: the numbers are the Pi's control cycle's -- on the kiosk,
    // or relayed to the hosted API -- so they are shown as they are even when
    // no effect is running. A copy of the model stepped here instead started
    // from whenever this page loaded, and the website read 32 C beside a
    // kiosk reading 20 C.
    SHARED_DHT22_MODELLED_BY_PI = sharedMetrics.modelled === true || sharedMetrics.authoritative === true;
    SHARED_DHT22_EASED_BY_PI = sharedMetrics.eased === true;
  }

  if (response.automation && typeof response.automation === "object") {
    SENSOR_AUTOMATION = {
      fan: { ...DEFAULT_SENSOR_AUTOMATION.fan, ...(response.automation.fan || {}) },
      light: { ...DEFAULT_SENSOR_AUTOMATION.light, ...(response.automation.light || {}) },
      greenhouse: {
        ...DEFAULT_SENSOR_AUTOMATION.greenhouse,
        ...(response.automation.greenhouse || {}),
      },
      // The per-actuator safety verdict, keyed by actuator. Copied straight
      // through rather than merged into a default: it is the backend's answer
      // about the crops' own limits, and a stale local default standing in for
      // a missing one would claim a limit nobody set.
      safety: response.automation.safety && typeof response.automation.safety === "object"
        ? response.automation.safety
        : {},
    };
  }

  if (response.series && typeof response.series === "object" && response.live !== true) {
    state.dashboardSeries = mergeDashboardSeries(state.dashboardSeries, response.series);
    const covered = Number.parseInt(response.historyDays, 10);
    state.dashboardSeriesDays = Number.isFinite(covered) && covered > 0 ? covered : 0;
  }
  if (response.live === true) {
    mergeLiveSensorOverviewSeries(response);
  }

  const baseSensorsPage = sensorsPageStateWithCachedControls();
  const currentSensorsPage = state.sensorsPage && typeof state.sensorsPage === "object" ? state.sensorsPage : {};
  state.sensorsPage = {
    ...baseSensorsPage,
    ...currentSensorsPage,
    sensorPower: {
      ...baseSensorsPage.sensorPower,
      ...(currentSensorsPage.sensorPower || {}),
      ...controls.sensorPower,
    },
    rowSensorPower: {
      ...baseSensorsPage.rowSensorPower,
      ...(currentSensorsPage.rowSensorPower || {}),
      ...controls.rowSensorPower,
    },
    actuatorMode: {
      ...baseSensorsPage.actuatorMode,
      ...(currentSensorsPage.actuatorMode || {}),
      ...controls.actuatorMode,
    },
    // Carried explicitly, like the three maps above it. It used to be left to
    // the `...currentSensorsPage` spread, which did keep it -- but only by
    // accident of ordering, and only in memory. Naming it here means a refresh
    // cannot drop what the operator typed, and keeps this merge readable as
    // the full list of what a server response is allowed to touch.
    //
    // The server has no say in it: the duration rides with the ON command
    // rather than being stored as its own control, so there is no
    // `controls.actuatorDuration` to spread. What is on screen wins.
    actuatorDuration: {
      ...baseSensorsPage.actuatorDuration,
      ...(currentSensorsPage.actuatorDuration || {}),
    },
  };
  const dht22PowerState = controls.sensorPower.dht22
    || controls.rowSensorPower.dht22
    || state.sensorsPage.sensorPower.dht22
    || state.sensorsPage.rowSensorPower.dht22
    || "on";
  setSynchronizedSensorPowerState("dht22", dht22PowerState);
  writeSensorControlCache(state.sensorsPage);
  // Last, so it sees this response's actuator modes and automation verdict.
  applyClimateResponseModel();
}

// The range the one shared air is judged against for the easing's bands: the
// tightest bound every active row's crop can live with, as the backend's
// crop_parameter_bounds() does for the relays. Each row's range is its own
// crop parameter, so Row 1 at 18-30 C and Row 2 at 20-30 C give 20-30 C.
function sharedClimateRange(metric) {
  const ranges = IOT_DEVICE_ROWS
    .map((row) => activeCultivationForRow(row.key)?.parameters?.[metric.key])
    .map((configured) => ({
      min: Number.parseFloat(configured?.min),
      max: Number.parseFloat(configured?.max),
    }))
    .filter((range) => Number.isFinite(range.min) && Number.isFinite(range.max) && range.min < range.max);
  if (!ranges.length) {
    return { min: metric.normalMin, max: metric.normalMax };
  }
  const min = Math.max(...ranges.map((range) => range.min));
  const max = Math.min(...ranges.map((range) => range.max));
  return min < max ? { min, max } : { min: metric.normalMin, max: metric.normalMax };
}

// The fan and lamp's effect on the greenhouse air (assets/icucrops-climate-
// response.js has the model and why). On the Pi the backend runs the model,
// decides the relays on it and sends the result, so the numbers are shown as
// they came. The hosted API has no control cycle, so the browser steps its own
// copy here. SHARED_DHT22_MEASURED -- the DHT22 itself -- is never touched.
function applyClimateResponseModel() {
  const model = window.ICuCropsClimateResponse;
  if (SHARED_DHT22_EASED_BY_PI) {
    // The kiosk's own numbers, eased once on the Pi and relayed to the
    // website. Easing them again here is what let each screen drift: a page
    // just opened jumped straight to the target while the kiosk was still on
    // its way, so the website ran ahead of the Pi.
    climateResponseState = null;
    climateEaseState = null;
    showClimateValues({ temp: SHARED_DHT22_METRICS.temp, humidity: SHARED_DHT22_METRICS.humidity });
    return;
  }
  if (SHARED_DHT22_MODELLED_BY_PI) {
    // The server's numbers are the Pi's, carried smoothly between DHT22
    // publishes. Followed, not recomputed: only the small correction when a
    // new reading lands is spread over a few polls, so the card never jumps.
    climateResponseState = null;
    if (!model || typeof model.easeToward !== "function" || !dashboardDht22ReadingIsFresh()) {
      climateEaseState = null;
      return;
    }
    const eased = model.easeToward(
      climateEaseState,
      { temp: SHARED_DHT22_METRICS.temp, humidity: SHARED_DHT22_METRICS.humidity },
      Date.now(),
    );
    climateEaseState = eased.state;
    showClimateValues(eased.values);
    return;
  }
  climateEaseState = null;
  if (!model || typeof model.step !== "function") {
    climateResponseState = null;
    return;
  }
  const modes = state.sensorsPage?.actuatorMode || {};
  const result = model.step(climateResponseState, {
    actual: { ...SHARED_DHT22_MEASURED },
    nowMs: Date.now(),
    fresh: dashboardDht22ReadingIsFresh(),
    ranges: Object.fromEntries(
      IOT_ROW_METRICS.filter((metric) => metric.shared).map((metric) => [metric.key, sharedClimateRange(metric)]),
    ),
    fan: { mode: modes.fan || "automatic", on: SENSOR_AUTOMATION.fan?.on === true },
    light: {
      mode: modes.light || "automatic",
      on: SENSOR_AUTOMATION.light?.on === true,
      warming: SENSOR_AUTOMATION.light?.tooCold === true,
    },
  });
  climateResponseState = result.state;
  if (!result.modelled) {
    return;
  }
  showClimateValues(result.values);
}

// Puts the shared temperature and humidity on the cards, with the status and
// gauge drawn from the same number.
function showClimateValues(values) {
  for (const metric of IOT_ROW_METRICS.filter((item) => item.shared)) {
    const shown = values[metric.key];
    if (!Number.isFinite(shown)) {
      continue;
    }
    SHARED_DHT22_METRICS[metric.key] = shown;
    state.dashboardSensors = (state.dashboardSensors || []).map((sensor) => (
      sensor.id === metric.key && Number.isFinite(Number.parseFloat(sensor.value))
        ? {
          ...sensor,
          value: shown,
          measuredValue: SHARED_DHT22_MEASURED[metric.key],
          status: sensorStatusFromRange(shown, sensor.min, sensor.max),
          percentage: sensorPercentageFromRange(shown, sensor.min, sensor.max),
        }
        : sensor
    ));
  }
}

function applyIrrigationResponse(irrigation = {}) {
  // Drop any tank confirmation whose row no longer needs that solution. The
  // backend retires them the same way; keeping them here would leave the card
  // suppressed after the pH has already come back into range.
  if (Array.isArray(irrigation.rows)) {
    // Another screen may have answered the card already; the backend hands
    // back every answer that still counts.
    const answeredElsewhere = irrigation.limeTankAcknowledged
      && typeof irrigation.limeTankAcknowledged === "object"
      ? irrigation.limeTankAcknowledged
      : {};
    const stillNeeded = {};
    const stillDeferred = {};
    // An answer is kept while its row grows the same cultivation and does not
    // need the other solution -- including while the pH is back in range. The
    // RS485 pH swings in and out of range by itself, and dropping the answer
    // on every in-range reading is what made the confirmed tank ask again.
    // Matches relevant_lime_tank_acknowledgements() in main.py.
    irrigation.rows.forEach((row) => {
      if (!row?.active) {
        return;
      }
      const needed = String(row?.limeSolutionNeeded || "").trim();
      ["up", "down"].forEach((solutionKey) => {
        if (needed && needed !== solutionKey) {
          return;
        }
        const key = limeTankConfirmationKey(row.key, solutionKey, row.cultivationId);
        if (state.limeTankConfirmations?.[key] || answeredElsewhere[key]) {
          stillNeeded[key] = true;
        }
      });
    });
    // A "not now" runs its full time whatever this pass says. The pH sits
    // near its threshold while it corrects, so a row can drop out of one
    // refresh and back into the next; dropping its deferral there brought the
    // card straight back instead of after its timer. An expired or unneeded
    // deferral hides nothing: pendingLimeTankCheck asks only for rows that
    // still need a solution. Coming back to Irrigation still clears them.
    const now = Date.now();
    Object.entries(state.limeTankDeferred || {}).forEach(([key, until]) => {
      if (Number(until) > now) {
        stillDeferred[key] = until;
      }
    });
    state.limeTankConfirmations = stillNeeded;
    state.limeTankDeferred = stillDeferred;
  }

  const base = initialIrrigationPageState();
  const currentChannels = state.irrigationPage?.channels || {};
  const incomingChannels = irrigation.channels && typeof irrigation.channels === "object"
    ? irrigation.channels
    : {};
  const channels = {};

  for (const channel of IRRIGATION_CHANNELS) {
    channels[channel.key] = {
      ...base.channels[channel.key],
      ...(currentChannels[channel.key] || {}),
      ...(incomingChannels[channel.key] || {}),
    };
  }

  const activeManualLines = normalizeIrrigationRunMap(
    "activeManualLines" in irrigation
      ? irrigation.activeManualLines
      : state.irrigationPage?.activeManualLines,
    irrigation.activeManualLine || state.irrigationPage?.activeManualLine || base.activeManualLine,
  );
  const activeScheduleLines = normalizeIrrigationRunMap(
    "activeScheduleLines" in irrigation
      ? irrigation.activeScheduleLines
      : state.irrigationPage?.activeScheduleLines,
  );
  const incomingRows = Array.isArray(irrigation.rows) ? irrigation.rows : [];
  const rowFallbacks = Object.fromEntries(base.rows.map((row) => [row.key, row]));
  const incomingRowModes = irrigation.rowModes && typeof irrigation.rowModes === "object"
    ? irrigation.rowModes
    : {};
  const rows = CULTIVATION_ROW_OPTIONS.map((rowOption) => {
    const fallbackRow = rowFallbacks[rowOption.key] || rowOption;
    const currentRow = state.irrigationPage?.rows?.find((row) => row?.key === rowOption.key) || {};
    const incomingRow = incomingRows.find((row) => row?.key === rowOption.key) || {};
    const rowChannels = {};
    for (const channel of IRRIGATION_CHANNELS) {
      rowChannels[channel.key] = {
        ...base.channels[channel.key],
        ...(currentRow.channels?.[channel.key] || {}),
        ...(incomingRow.channels?.[channel.key] || {}),
      };
    }
    return {
      ...fallbackRow,
      ...currentRow,
      ...incomingRow,
      mode: normalizeIrrigationRowMode(
        incomingRow.mode || incomingRowModes[rowOption.key] || currentRow.mode,
      ),
      channels: rowChannels,
    };
  });
  const requestedSelectedRow = String(
    state.irrigationPage?.selectedRowKey || irrigation.selectedRowKey || "",
  ).trim();
  const selectedRowKey = rows.some((row) => row.active && row.key === requestedSelectedRow)
    ? requestedSelectedRow
    : rows.find((row) => row.active)?.key || "";
  writeIrrigationSelectedRowKey(selectedRowKey);
  state.irrigationPage = {
    ...base,
    ...state.irrigationPage,
    ...irrigation,
    channels,
    mode: String(irrigation.mode || state.irrigationPage?.mode || base.mode).trim() || base.mode,
    autoEnabled: typeof irrigation.autoEnabled === "boolean"
      ? irrigation.autoEnabled
      : state.irrigationPage?.autoEnabled ?? base.autoEnabled,
    activeManualLine: firstActiveIrrigationLine(activeManualLines),
    activeManualLines,
    activeScheduleLines,
    activeAutomaticLines: normalizeIrrigationRunMap(irrigation.activeAutomaticLines),
    targetRows: normalizeIrrigationRowMap(irrigation.targetRows),
    scheduleArmedRows: normalizeIrrigationRowMap(irrigation.scheduleArmedRows),
    activeManualRows: normalizeIrrigationChannelRowMap(irrigation.activeManualRows),
    activeScheduleRows: normalizeIrrigationChannelRowMap(irrigation.activeScheduleRows),
    activeAutomaticRows: normalizeIrrigationChannelRowMap(irrigation.activeAutomaticRows),
    selectedRowKey,
    rows,
    overlayMode: state.irrigationPage?.overlayMode || "",
  };
}

async function refreshSensors({ render = true, live = false } = {}) {
  const requestJson = window.ICuCropsAuth?.requestJson;
  let loaded = false;

  if (typeof requestJson === "function") {
    try {
      const requestedDays = live ? 0 : dashboardHistoryDaysToRequest();
      const response = await requestJson(
        live ? "/api/sensors?live=1" : `/api/sensors?days=${requestedDays}`,
        // The shared request timeout is ten seconds and a month of history is
        // about ten and a half seconds of database work by the measurement in
        // dashboardHistoryDaysNeeded's comment, so every widening to 7, 14 or
        // 30 Days aborted just short of its answer. The live poll keeps the
        // short timeout; only the history query is allowed to take its time.
        live ? {} : { timeoutMs: DASHBOARD_HISTORY_REQUEST_TIMEOUT_MS },
      );
      applySensorOverviewResponse(response);
      loaded = true;
      sensorOverviewEverLoaded = true;
      if (!live) {
        // Records the first load as well as the periodic re-seed, so a dashboard
        // that has just started does not immediately ask for the history again.
        lastSensorHistoryRefreshAt = Date.now();
        // The first pass deliberately asked for less than the ranges on screen
        // can plot. Fetch the remainder now that the recent window is painted.
        if (requestedDays < dashboardHistoryDaysNeeded()) {
          scheduleDashboardHistoryBackfill();
        }
      }
    } catch (error) {
      console.warn("Unable to load sensors from the backend.", error);
    }
  }

  // Only before the backend has ever answered. A request that timed out is
  // not a report that the farm has no readings, and clearing the series on one
  // was why pressing 7, 14 or 30 Days replaced every graph -- Real Time
  // included -- with "No backend readings".
  if (!loaded && !sensorOverviewEverLoaded && window.ICuCropsPiMode !== true) {
    IOT_DEVICE_ROWS = DEFAULT_IOT_DEVICE_ROWS.map((row) => ({ ...row }));
    SHARED_DHT22_METRICS = { ...DEFAULT_SHARED_DHT22_METRICS };
    SHARED_DHT22_MEASURED = { temp: null, humidity: null };
    climateResponseState = null;
    climateEaseState = null;
    SHARED_DHT22_MODELLED_BY_PI = false;
    SHARED_DHT22_EASED_BY_PI = false;
    state.dashboardSeries = initialDashboardSeries();
  }

  if (render) {
    renderPage();
    renderOverlays();
  }
  return loaded;
}

async function refreshIrrigation({ render = true, force = false } = {}) {
  if (
    !force
    && (irrigationSavePendingCount > 0 || Date.now() < irrigationOptimisticLockUntil)
  ) {
    return false;
  }
  const requestJson = window.ICuCropsAuth?.requestJson;
  let loaded = false;

  if (typeof requestJson === "function") {
    try {
      const response = await requestJson("/api/irrigation");
      applyIrrigationResponse(response.irrigation || {});
      loaded = true;
    } catch (error) {
      console.warn("Unable to load irrigation settings from the backend.", error);
    }
  }

  if (render) {
    renderPage();
    renderOverlays();
  }
  return loaded;
}

async function persistSensorControl(controlType, key, value) {
  const requestJson = window.ICuCropsAuth?.requestJson;
  if (typeof requestJson === "function") {
    try {
      const response = await requestJson("/api/sensors/control", {
        method: "POST",
        // The duration rides with the mode. Only misting has one, and only
        // an On uses it -- the backend clears the deadline on anything else,
        // so sending it unconditionally cannot arm a line that is off.
        body: {
          controlType,
          key,
          value,
          ...(controlType === "actuatorMode" && value === "on"
            ? { durationSeconds: Number(state.sensorsPage.actuatorDuration?.[key]) || 0 }
            : {}),
        },
        // One press costs the backend 37 statements, and on the hosted site
        // every one of those crosses the network to Supabase. The 10s default
        // is the same deadline a plain read gets, which is why a press could
        // fail on a slow minute while nothing was actually wrong with it.
        timeoutMs: SENSOR_CONTROL_REQUEST_TIMEOUT_MS,
      });
      // Re-arm the lock before the answer is merged, not after. The overview
      // that comes back is a read taken around the write, and on the hosted
      // site the round trip routinely outlives the five-second window -- so by
      // the time it landed the lock had expired and this response was free to
      // paint the pre-press mode back onto the card. That is the Grow Light going
      // Automatic -> Off and springing back to Automatic. The press is the
      // truth until the request finishes, whatever the clock says.
      setSensorControlOptimisticLock(controlType, key, value);
      applySensorOverviewResponse(response);
      if (response.notification) {
        applyCreatedNotification(response.notification);
      }
      // The hosted backend writes the row and then queues a command for the
      // Pi. When the queue step does not happen the row is still saved, so the
      // card repaints and the press looks successful while the hardware is
      // never told. Say it plainly rather than let a dead button look alive.
      if (response.queued === false) {
        pushNotification("warning", response.message
          || "Saved, but the farm hardware was not told about this change.");
      }
      window.icuCropsRealtimeSync?.markLocalMutation?.("sensors", 2500);
      return true;
    } catch (error) {
      console.warn("Unable to save sensor control state to the backend.", error);
      // Keep why it failed, so the notice can say so instead of the flat
      // "It was reverted." that gave an operator nothing to act on.
      lastSensorControlError = error;
    }
  }

  return false;
}

// A press is a physical intent, so one bad minute should not silently undo it.
// A refusal (the safety limit, a rejected session) is final and returns at
// once; a timeout or an unreachable backend is retried briefly first, because
// those are the failures that resolve on their own.
async function persistSensorControlWithRetry(controlType, key, value) {
  for (let attempt = 0; attempt < SENSOR_CONTROL_RETRY_ATTEMPTS; attempt += 1) {
    if (await persistSensorControl(controlType, key, value)) {
      return true;
    }

    const status = Number(lastSensorControlError?.status) || 0;
    const retryable = status === 0 || status === 429 || status >= 500;
    if (!retryable || attempt === SENSOR_CONTROL_RETRY_ATTEMPTS - 1) {
      return false;
    }

    await new Promise((resolve) => {
      window.setTimeout(resolve, SENSOR_CONTROL_RETRY_DELAY_MS * (attempt + 1));
    });
  }

  return false;
}

function runSensorControlRequest(controlType, key, value, { confirmedValue, onRollback } = {}) {
  const requestKey = `${controlType}:${key}`;
  setSensorControlOptimisticLock(controlType, key, value);
  const existing = sensorControlRequests.get(requestKey);
  if (existing) {
    existing.desiredValue = value;
    return;
  }

  const entry = { desiredValue: value, confirmedValue, onRollback };
  sensorControlRequests.set(requestKey, entry);

  (async () => {
    try {
      for (;;) {
        const attemptedValue = entry.desiredValue;
        const ok = await persistSensorControlWithRetry(controlType, key, attemptedValue);
        if (ok) {
          entry.confirmedValue = attemptedValue;
          // A slow save can land with its own lock already expired. Restart the
          // window from the answer rather than from the press, so the settle
          // poll that follows cannot repaint the card from a pre-save read.
          setSensorControlOptimisticLock(controlType, key, attemptedValue);
        }

        if (entry.desiredValue !== attemptedValue) {
          continue;
        }

        if (!ok) {
          sensorControlOptimisticLocks.delete(requestKey);
          entry.onRollback?.(entry.confirmedValue);
        }
        break;
      }
    } finally {
      sensorControlRequests.delete(requestKey);
    }
  })();
}

function markupFragment(html) {
  const template = document.createElement("template");
  template.innerHTML = String(html || "").trim();
  return template.content;
}

// Replacing a node throws away everything the browser was holding for it: its
// scroll offset, the focus inside it, and -- the one that reads as a "blink" --
// every CSS animation on it starts again. `.drawer` slides in, a timeline bar
// regrows, a card fades. A live reading arriving every few seconds then
// replayed those entrances for as long as the panel stayed open. Walking the
// two trees and touching only what actually differs keeps the live nodes, so
// nothing re-enters and nothing loses its place.
function morphNode(current, next) {
  if (current.nodeType !== next.nodeType) {
    return false;
  }

  if (current.nodeType === Node.TEXT_NODE || current.nodeType === Node.COMMENT_NODE) {
    if (current.nodeValue !== next.nodeValue) {
      current.nodeValue = next.nodeValue;
    }
    return true;
  }

  if (current.nodeType !== Node.ELEMENT_NODE || current.tagName !== next.tagName) {
    return false;
  }

  if (current.isEqualNode(next)) {
    return true;
  }

  // Replacing a select's children moves the parsed <option> nodes out of
  // `next`. Capture its selected value first, or next.value becomes "" and a
  // perfectly valid active row is cleared during the form-state sync below.
  const nextSelectValue = next instanceof HTMLSelectElement ? next.value : null;

  morphAttributes(current, next);

  const currentChildren = Array.from(current.childNodes);
  const nextChildren = Array.from(next.childNodes);

  if (currentChildren.length !== nextChildren.length) {
    // A different shape is a different card, not the same one with new
    // numbers. Swapping the children still keeps `current` itself alive.
    current.replaceChildren(...nextChildren);
  } else {
    currentChildren.forEach((child, index) => {
      const replacement = nextChildren[index];
      if (!morphNode(child, replacement)) {
        child.replaceWith(replacement);
      }
    });
  }

  morphFormState(current, next, nextSelectValue);
  return true;
}

function morphAttributes(current, next) {
  Array.from(current.attributes).forEach((attribute) => {
    if (!next.hasAttribute(attribute.name)) {
      current.removeAttribute(attribute.name);
    }
  });

  Array.from(next.attributes).forEach((attribute) => {
    if (current.getAttribute(attribute.name) !== attribute.value) {
      current.setAttribute(attribute.name, attribute.value);
    }
  });
}

function morphFormState(current, next, nextSelectValue = null) {
  // `value` and `checked` live on the property, not the attribute, so an
  // attribute sync alone would leave a field showing what it held before.
  // Whatever someone is typing into right now is never overwritten.
  if (current === document.activeElement && !(current instanceof HTMLSelectElement)) {
    return;
  }

  if (current instanceof HTMLInputElement && next instanceof HTMLInputElement) {
    if (current.type === "checkbox" || current.type === "radio") {
      if (current.checked !== next.checked) {
        current.checked = next.checked;
      }
    } else if (current.value !== next.value) {
      current.value = next.value;
    }
    return;
  }

  if (current instanceof HTMLTextAreaElement && next instanceof HTMLTextAreaElement) {
    if (current.value !== next.value) {
      current.value = next.value;
    }
    return;
  }

  if (current instanceof HTMLSelectElement && next instanceof HTMLSelectElement) {
    const desiredValue = typeof nextSelectValue === "string" ? nextSelectValue : next.value;
    if (current.value !== desiredValue) {
      current.value = desiredValue;
    }
    if (
      current.id === "irrigation-active-row-select"
      && !current.value
      && current.options.length
    ) {
      const firstActiveOption = Array.from(current.options).find(
        (option) => !option.disabled && Boolean(option.value),
      );
      if (firstActiveOption) {
        current.value = firstActiveOption.value;
      }
    }
  }
}

// Same idea as morphNode, one level up: keep the container and its children
// and reconcile into them, so a data re-render is not a page rebuild.
function isMeaningfulNode(node) {
  return node.nodeType !== Node.TEXT_NODE || Boolean(node.textContent.trim());
}

function morphContainer(node, html) {
  const fragment = markupFragment(html);
  // markupFragment trims, but the container was filled from the untrimmed
  // string and still holds the whitespace around it. Line up what carries
  // content, or the counts never match and every page falls back to a rebuild.
  const currentChildren = Array.from(node.childNodes).filter(isMeaningfulNode);
  const nextChildren = Array.from(fragment.childNodes).filter(isMeaningfulNode);

  if (!currentChildren.length || currentChildren.length !== nextChildren.length) {
    return false;
  }

  currentChildren.forEach((child, index) => {
    const replacement = nextChildren[index];
    if (!morphNode(child, replacement)) {
      child.replaceWith(replacement);
    }
  });

  return true;
}

function replaceChildrenWhenChanged(node, html) {
  const fragment = markupFragment(html);
  const nextChildren = Array.from(fragment.childNodes);
  const currentChildren = Array.from(node.childNodes).filter(
    (child) => child.nodeType !== Node.TEXT_NODE || child.textContent.trim(),
  );
  const meaningfulNextChildren = nextChildren.filter(
    (child) => child.nodeType !== Node.TEXT_NODE || child.textContent.trim(),
  );
  const unchanged = currentChildren.length === meaningfulNextChildren.length
    && currentChildren.every((child, index) => child.isEqualNode(meaningfulNextChildren[index]));
  if (unchanged) {
    return false;
  }

  if (currentChildren.length === meaningfulNextChildren.length) {
    currentChildren.forEach((child, index) => {
      const replacement = meaningfulNextChildren[index];
      if (!morphNode(child, replacement)) {
        child.replaceWith(replacement);
      }
    });
    return true;
  }

  node.replaceChildren(fragment);
  return true;
}

function replaceOuterHTMLPreservingFocus(node, html) {
  const fragment = markupFragment(html);
  const replacement = fragment.firstElementChild;
  if (!(replacement instanceof Element)) {
    return false;
  }
  if (node.isEqualNode(replacement)) {
    return false;
  }

  // Keeping the node is always better than swapping it -- see morphNode. Only
  // a shape it cannot express falls through to the swap below.
  if (morphNode(node, replacement)) {
    return true;
  }

  const activeElement = document.activeElement;
  const ownsFocus = activeElement instanceof HTMLElement && node.contains(activeElement);
  const focusedId = ownsFocus && activeElement.id ? activeElement.id : null;
  const focusedGraphRange = ownsFocus ? activeElement.dataset.graphRange || "" : "";
  const focusedSensorPower = ownsFocus ? activeElement.dataset.sensorPower || "" : "";
  const focusedRowSensorPower = ownsFocus ? activeElement.dataset.rowSensorPower || "" : "";
  const scroller = pageScrollElement();
  const scrollTop = scroller.scrollTop;
  const scrollLeft = scroller.scrollLeft;
  node.replaceWith(replacement);
  const nextFocus = focusedId
    ? document.getElementById(focusedId)
    : focusedGraphRange
      ? elements.pageContent?.querySelector(`[data-graph-range="${CSS.escape(focusedGraphRange)}"]`)
      : focusedSensorPower
        ? elements.pageContent?.querySelector(`[data-sensor-power="${CSS.escape(focusedSensorPower)}"]`)
        : focusedRowSensorPower
          ? elements.pageContent?.querySelector(`[data-row-sensor-power="${CSS.escape(focusedRowSensorPower)}"]`)
          : null;
  nextFocus?.focus({ preventScroll: true });
  if (scroller.scrollTop !== scrollTop || scroller.scrollLeft !== scrollLeft) {
    setScrollOffsetInstantly(scroller, scrollTop, scrollLeft);
  }
  return true;
}

function updateSensorManagementCardsByPowerKey(powerKey) {
  if (!elements.pageContent) {
    return false;
  }

  let updated = false;
  for (const config of SENSOR_MANAGEMENT_CARDS) {
    if (config.powerKey !== powerKey) {
      continue;
    }
    const card = elements.pageContent.querySelector(`[data-sensor-card="${CSS.escape(config.sensorId)}"]`);
    if (card) {
      updated = replaceOuterHTMLPreservingFocus(card, sensorManagementCardTemplate(config)) || updated;
    }
  }
  return updated;
}

function updateActuatorCard(key) {
  if (!elements.pageContent) {
    return false;
  }

  const control = SENSOR_ACTUATORS.find((item) => item.key === key);
  if (!control) {
    return false;
  }

  const card = elements.pageContent.querySelector(`[data-actuator-card="${CSS.escape(key)}"]`);
  if (!card) {
    return false;
  }

  return replaceOuterHTMLPreservingFocus(card, actuatorControlCardTemplate(control));
}

function reconcileSensorsLiveState() {
  if (!state.isAuthenticated || state.activeView !== "sensors" || !elements.pageContent) {
    return false;
  }

  let updated = false;
  for (const config of SENSOR_MANAGEMENT_CARDS) {
    updated = updateSensorManagementCardsByPowerKey(config.powerKey) || updated;
  }
  for (const control of SENSOR_ACTUATORS) {
    updated = updateActuatorCard(control.key) || updated;
  }
  return updated;
}

function irrigationRequestId() {
  try {
    if (typeof crypto?.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch (error) {
    // Not a secure context; fall through to the plain id.
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function irrigationStateRequestPayload() {
  const scopeRows = [...irrigationChangedRows];
  irrigationChangedRows = new Set();
  const manualLineChanges = irrigationManualLineChanges;
  irrigationManualLineChanges = {};
  return JSON.parse(JSON.stringify({
    // One id per save. The request helper retries a save that timed out, as a
    // new request, and the backend skips an id it has already applied -- a
    // retried Start used to run the line a second time.
    requestId: irrigationRequestId(),
    scopeRows,
    // Always sent, even empty: the backend then switches only these lines and
    // ignores the running-line maps below, which older backends still read.
    manualLineChanges,
    mode: state.irrigationPage.mode,
    autoEnabled: state.irrigationPage.autoEnabled,
    activeManualLine: state.irrigationPage.activeManualLine,
    activeManualLines: state.irrigationPage.activeManualLines,
    activeScheduleLines: state.irrigationPage.activeScheduleLines,
    activeAutomaticLines: state.irrigationPage.activeAutomaticLines,
    targetRows: state.irrigationPage.targetRows,
    scheduleArmedRows: state.irrigationPage.scheduleArmedRows,
    activeManualRows: state.irrigationPage.activeManualRows,
    activeScheduleRows: state.irrigationPage.activeScheduleRows,
    activeAutomaticRows: state.irrigationPage.activeAutomaticRows,
    rowModes: irrigationRowModesPayload(scopeRows),
    rowChannels: irrigationRowChannelsPayload(scopeRows),
    channels: state.irrigationPage.channels,
    // Which lime tank checks have been answered. The backend holds the same
    // gate, because automatic runs happen with no page open.
    limeTankAcknowledged: state.limeTankConfirmations || {},
  }));
}

async function persistIrrigationSnapshot(payload, revision) {
  const requestJson = window.ICuCropsAuth?.requestJson;
  if (typeof requestJson === "function") {
    try {
      const response = await requestJson("/api/irrigation", {
        method: "POST",
        body: payload,
      });
      if (revision === irrigationSaveRevision) {
        applyIrrigationResponse(response.irrigation || {});
        // The response IS the authoritative state -- it is what the backend
        // just committed and what it published to MQTT. Holding the live
        // refresh off any longer only delays the next true state, which for a
        // short run is the run having already ended.
        irrigationOptimisticLockUntil = 0;
      }
      return true;
    } catch (error) {
      console.warn("Unable to save irrigation settings to the backend.", error);
    }
  }

  return false;
}

function persistIrrigationState() {
  const payload = irrigationStateRequestPayload();
  const revision = ++irrigationSaveRevision;
  irrigationSavePendingCount += 1;
  // A ceiling, not a delay. The lock exists so the live refresh cannot repaint
  // a stale payload over a save that is still in flight; it is released the
  // moment the response lands (persistIrrigationSnapshot), so a press normally
  // clears in the time one request takes.
  //
  // It used to be a flat 5000 here and 1500 on success, which meant the screen
  // could not show the run ending for five seconds even though the relay had
  // already closed. On a 2 second run that reads as "hindi pumuputol": the
  // water is off and the card still says Running. Worst on the Pi kiosk, whose
  // irrigation poll is 15s, so the stale card could sit there far longer.
  irrigationOptimisticLockUntil = Date.now() + IRRIGATION_SAVE_LOCK_CEILING_MS;
  window.icuCropsRealtimeSync?.markLocalMutation?.(
    "irrigation",
    IRRIGATION_SAVE_LOCK_CEILING_MS,
  );

  const request = irrigationSaveTail
    .catch(() => false)
    .then(() => persistIrrigationSnapshot(payload, revision));
  irrigationSaveTail = request.catch(() => false);
  return request.finally(() => {
    irrigationSavePendingCount = Math.max(0, irrigationSavePendingCount - 1);
  });
}

async function saveIrrigationStateWithFeedback({ successMessage = "", warningMessage = "" } = {}) {
  const saved = await persistIrrigationState();

  if (saved) {
    // Alert history is secondary to the physical control. Let the toggle and
    // MQTT state settle first, then refresh notifications independently.
    window.setTimeout(() => void refreshNotifications({ render: false }), 0);
    if (successMessage) {
      pushNotification("success", successMessage);
    }
    if (warningMessage) {
      pushNotification("warning", warningMessage);
    }
  } else {
    pushNotification("warning", "Unable to save irrigation schedule right now.");
  }

  renderIrrigationPageUpdate();
  renderOverlays();
}

async function refreshProfile({ render = true } = {}) {
  const requestJson = window.ICuCropsAuth?.requestJson;
  const userId = getAuthenticatedSessionUserId();
  if (!userId || typeof requestJson !== "function") {
    if (render) {
      renderHeader();
      renderOverlays();
    }
    return false;
  }

  try {
    const response = await requestJson(`/api/profile/${encodeURIComponent(userId)}`);
    const user = response.user || {};
    state.savedProfileName = String(user.displayName || state.savedProfileName).trim() || DEFAULT_PROFILE_NAME;
    state.profileName = state.savedProfileName;
    state.profileRole = String(user.roleLabel || state.profileRole).trim() || DEFAULT_PROFILE_ROLE;
    state.selectedProfilePhotoFile = null;
    // Track a cleared photo too, so a removed image stops being re-requested.
    // A response without the field means the backend told us nothing about it.
    if ("profilePhotoUrl" in user) {
      releaseProfilePhotoObjectUrl();
      state.profilePhotoDataUrl = String(user.profilePhotoUrl || "").trim();
    }
    syncAuthenticatedProfileSession(user);
  } catch (error) {
    console.warn("Unable to load profile from the backend.", error);
  }

  if (render) {
    renderHeader();
    renderOverlays();
  }
  return true;
}

async function refreshCultivations({ render = true } = {}) {
  const requestJson = window.ICuCropsAuth?.requestJson;
  if (typeof requestJson !== "function") {
    if (render) {
      renderPage();
      renderOverlays();
    }
    return false;
  }

  try {
    const response = await requestJson("/api/cultivations");
    state.activeCultivations = mapActiveCultivations(response.cultivations);
    state.cultivationRequests = mapCultivationRequests(response.requests);
  } catch (error) {
    if (!state.activeCultivations.length) {
      state.activeCultivations = initialActiveCultivations();
    }
    console.warn("Unable to load cultivations from the backend.", error);
  }

  if (render) {
    renderPage();
    renderOverlays();
  }
  return true;
}

async function refreshNotifications({ render = true } = {}) {
  const requestJson = window.ICuCropsAuth?.requestJson;
  const userId = getAuthenticatedSessionUserId();
  const role = getAuthenticatedSessionRole();
  if (!userId || !role || typeof requestJson !== "function") {
    if (render) {
      renderHeader();
      if (state.activeView === "history") {
        renderPage();
      }
      if (state.notificationsOpen) {
        renderOverlays();
      }
    }
    return false;
  }

  try {
    const params = new URLSearchParams({
      userId,
      role,
    });
    const response = await requestJson(`/api/notifications?${params.toString()}`);
    state.notificationHistory = mapNotificationRecords(response.notifications);
    state.notifications = state.notificationHistory.filter((notification) => !notification.read);
  } catch (error) {
    if (!state.notificationHistory.length) {
      state.notificationHistory = initialNotificationHistory();
      state.notifications = initialNotifications();
    }
    console.warn("Unable to load notifications from the backend.", error);
  }

  if (render) {
    renderHeader();
    if (state.activeView === "history") {
      renderPage();
    }
    if (state.notificationsOpen) {
      renderOverlays();
    }
  }
  return true;
}

async function syncNotificationReadState(notificationIds = []) {
  const requestJson = window.ICuCropsAuth?.requestJson;
  const userId = getAuthenticatedSessionUserId();
  const role = getAuthenticatedSessionRole();
  if (!userId || !role || typeof requestJson !== "function") {
    return false;
  }

  try {
    const response = await requestJson("/api/notifications/mark-read", {
      method: "POST",
      body: {
        userId,
        role,
        notificationIds,
      },
    });
    state.notificationHistory = mapNotificationRecords(response.notifications);
    state.notifications = state.notificationHistory.filter((notification) => !notification.read);
    window.icuCropsRealtimeSync?.markLocalMutation?.("notifications", 1500);
    return true;
  } catch (error) {
    console.warn("Unable to sync notification read state.", error);
    return false;
  }
}

function bindEvents() {
  document.addEventListener("click", handleClick);
  document.addEventListener("change", handleChange);
  document.addEventListener("input", handleInput);
  document.addEventListener("submit", handleSubmit);
  document.addEventListener("keydown", handleKeyDown);
  document.addEventListener("pointerdown", handlePointerDown, true);
  if (window.matchMedia?.("(hover: hover) and (pointer: fine)")?.matches) {
    document.addEventListener("pointerover", handleDashboardChartPointerOver);
    document.addEventListener("pointermove", handleDashboardChartPointerMove);
    document.addEventListener("pointerout", handleDashboardChartPointerOut);
  }
  document.addEventListener("scroll", queueViewportInteraction, { capture: true, passive: true });
  window.addEventListener("scroll", queueViewportInteraction, { passive: true });
  window.addEventListener("resize", queueViewportInteraction, { passive: true });
  if (ENABLE_CUSTOM_PAGE_WHEEL_SMOOTHING) {
    elements.pageContent?.addEventListener("scroll", syncSmoothPageScrollPosition, { passive: true });
    elements.appMain?.addEventListener("wheel", handlePageContentWheel, { passive: false });
  }
  window.addEventListener("hashchange", () => syncViewFromHash());
}

function dashboardEnsureChartTooltip() {
  if (dashboardChartTooltip && document.body.contains(dashboardChartTooltip)) {
    return dashboardChartTooltip;
  }

  dashboardChartTooltip = document.createElement("div");
  dashboardChartTooltip.className = "dashboard-chart-tooltip";
  dashboardChartTooltip.hidden = true;
  document.body.appendChild(dashboardChartTooltip);
  return dashboardChartTooltip;
}

function dashboardClearChartTooltip() {
  if (!dashboardChartTooltip || dashboardChartTooltip.hidden) {
    return;
  }

  dashboardActiveChartHoverZone = null;
  dashboardChartTooltip.hidden = true;
  dashboardChartTooltip.replaceChildren();
}

function dashboardPositionChartTooltip(event) {
  const tooltip = dashboardEnsureChartTooltip();
  if (tooltip.hidden) {
    return;
  }

  const offset = 16;
  const maxX = window.innerWidth - tooltip.offsetWidth - 8;
  const maxY = window.innerHeight - tooltip.offsetHeight - 8;
  tooltip.style.left = `${Math.min(event.clientX + offset, Math.max(8, maxX))}px`;
  tooltip.style.top = `${Math.min(event.clientY + offset, Math.max(8, maxY))}px`;
}

function dashboardRowsFromHoverZone(zone) {
  try {
    const rows = JSON.parse(zone.dataset.rows || "[]");
    return Array.isArray(rows) ? rows : [];
  } catch {
    return [];
  }
}

function dashboardActivateChartHover(zone, event) {
  const svg = zone.closest("svg");
  if (!svg) {
    return;
  }

  const rows = dashboardRowsFromHoverZone(zone);
  const x = zone.dataset.x || "0";
  const hoverLine = svg.querySelector(".dashboard-chart-hover-line");
  if (hoverLine) {
    hoverLine.setAttribute("x1", x);
    hoverLine.setAttribute("x2", x);
    hoverLine.setAttribute("visibility", "visible");
  }

  svg.querySelectorAll("[data-dashboard-hover-dot]").forEach((dot) => {
    const row = rows[Number.parseInt(dot.dataset.dashboardHoverDot || "", 10)];
    if (!row) {
      dot.setAttribute("visibility", "hidden");
      return;
    }

    dot.setAttribute("cx", x);
    dot.setAttribute("cy", String(row.y));
    dot.setAttribute("fill", row.color);
    dot.setAttribute("visibility", "visible");
  });

  dashboardActiveChartHoverZone = zone;
  const tooltip = dashboardEnsureChartTooltip();
  tooltip.innerHTML = `
    <div class="dashboard-chart-tooltip__title">${escapeHtml(zone.dataset.title || "")}</div>
    ${rows.map((row) => `
      <div class="dashboard-chart-tooltip__row">
        <span class="dashboard-chart-tooltip__swatch" style="background:${escapeHtml(row.color)};"></span>
        <span>${escapeHtml(row.label)}</span>
        <strong>${escapeHtml(row.value)}</strong>
      </div>
    `).join("")}
  `;
  tooltip.hidden = false;
  dashboardPositionChartTooltip(event);
}

function handleDashboardChartPointerOver(event) {
  const zone = event.target instanceof Element ? event.target.closest(".dashboard-chart-hover-zone") : null;
  if (zone) {
    dashboardActivateChartHover(zone, event);
  }
}

function handleDashboardChartPointerMove(event) {
  const zone = event.target instanceof Element ? event.target.closest(".dashboard-chart-hover-zone") : null;
  if (zone) {
    if (zone !== dashboardActiveChartHoverZone) {
      dashboardActivateChartHover(zone, event);
      return;
    }
    dashboardPositionChartTooltip(event);
  }
}

function handleDashboardChartPointerOut(event) {
  const zone = event.target instanceof Element ? event.target.closest(".dashboard-chart-hover-zone") : null;
  if (!zone || zone.contains(event.relatedTarget)) {
    return;
  }

  const svg = zone.closest("svg");
  svg?.querySelector(".dashboard-chart-hover-line")?.setAttribute("visibility", "hidden");
  svg?.querySelectorAll("[data-dashboard-hover-dot]").forEach((dot) => {
    dot.setAttribute("visibility", "hidden");
  });
  dashboardActiveChartHoverZone = null;
  dashboardClearChartTooltip();
}

function setupMobileDashboardLayout() {
  mobileDashboardMediaQuery = window.matchMedia?.(MOBILE_DASHBOARD_QUERY) || null;
  mobileDashboardLayoutActive = isMobileDashboardLayout();
  document.body.classList.toggle("is-mobile-dashboard-layout", mobileDashboardLayoutActive);

  const handleLayoutChange = () => {
    const nextActive = isMobileDashboardLayout();
    document.body.classList.toggle("is-mobile-dashboard-layout", nextActive);

    if (nextActive === mobileDashboardLayoutActive) {
      return;
    }

    mobileDashboardLayoutActive = nextActive;
    stopSmoothPageScroll();
    if (state.isAuthenticated && state.activeView === "dashboard") {
      pendingRouteTransition = null;
      renderPage();
      renderToasts();
    }
  };

  if (typeof mobileDashboardMediaQuery?.addEventListener === "function") {
    mobileDashboardMediaQuery.addEventListener("change", handleLayoutChange);
  } else if (typeof mobileDashboardMediaQuery?.addListener === "function") {
    mobileDashboardMediaQuery.addListener(handleLayoutChange);
  }
}

function isMobileDashboardLayout() {
  return document.body?.classList.contains("mobile-web") === true;
}

function supportsDesktopWheelSmoothing() {
  return window.matchMedia?.("(hover: hover) and (pointer: fine)")?.matches ?? false;
}

function shouldUseSmoothPageScroll() {
  return ENABLE_CUSTOM_PAGE_WHEEL_SMOOTHING
    && state.isAuthenticated
    && !isMobileDashboardLayout()
    && window.innerWidth > 880
    && supportsDesktopWheelSmoothing()
    && !prefersReducedMotion();
}

// Which element actually scrolls the page is not the same on every layout.
// On the desktop site .page-content is its own scroll box -- app-main is
// 100vh and hides its overflow -- while the mobile shell leaves it
// overflow: visible and lets the document scroll. Anything that saves and
// restores the reader's place has to ask which one is live: writing to the
// other one is a no-op, and the real scroller is then left wherever the
// browser clamped it when the swapped-in markup was briefly shorter.
function pageScrollElement() {
  const pageContent = elements.pageContent;
  if (pageContent instanceof HTMLElement) {
    const overflowY = window.getComputedStyle(pageContent).overflowY;
    if (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") {
      return pageContent;
    }
  }

  return document.scrollingElement || document.documentElement;
}

function syncSmoothPageScrollPosition() {
  if (!elements.pageContent || smoothPageScrollFrame) {
    return;
  }

  smoothPageScrollCurrent = elements.pageContent.scrollTop;
  smoothPageScrollTarget = elements.pageContent.scrollTop;
}

function stopSmoothPageScroll() {
  if (smoothPageScrollFrame) {
    window.cancelAnimationFrame(smoothPageScrollFrame);
    smoothPageScrollFrame = 0;
  }

  smoothPageScrollCurrent = elements.pageContent?.scrollTop || 0;
  smoothPageScrollTarget = smoothPageScrollCurrent;
}

function scrollViewportToTop(options = {}) {
  const behavior = options.behavior || (prefersReducedMotion() ? "auto" : "smooth");
  stopSmoothPageScroll();

  if (elements.pageContent) {
    elements.pageContent.scrollTo({ top: 0, behavior });
    elements.pageContent.scrollTop = 0;
  }

  const scrollingElement = document.scrollingElement || document.documentElement;
  if (scrollingElement) {
    scrollingElement.scrollTo({ top: 0, behavior });
    scrollingElement.scrollTop = 0;
  }

  window.scrollTo({ top: 0, behavior });
  smoothPageScrollCurrent = 0;
  smoothPageScrollTarget = 0;
}

function findNestedScrollContainer(target, boundary) {
  let node = target instanceof Element ? target : null;

  while (node && node !== boundary) {
    const style = window.getComputedStyle(node);
    const overflowY = style.overflowY;
    const canScroll = /(auto|scroll|overlay)/.test(overflowY) && node.scrollHeight > node.clientHeight + 1;
    if (canScroll) {
      return node;
    }
    node = node.parentElement;
  }

  return boundary;
}

function normalizeWheelDelta(event) {
  const lineHeight = 18;
  const pageHeight = elements.pageContent?.clientHeight || window.innerHeight;

  if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) {
    return event.deltaY * lineHeight;
  }

  if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) {
    return event.deltaY * pageHeight;
  }

  return event.deltaY;
}

function animateSmoothPageScroll() {
  if (!elements.pageContent) {
    stopSmoothPageScroll();
    return;
  }

  const next = smoothPageScrollCurrent + (smoothPageScrollTarget - smoothPageScrollCurrent) * 0.16;
  const done = Math.abs(smoothPageScrollTarget - next) < 0.5;

  smoothPageScrollCurrent = done ? smoothPageScrollTarget : next;
  elements.pageContent.scrollTop = smoothPageScrollCurrent;

  if (done) {
    smoothPageScrollFrame = 0;
    return;
  }

  smoothPageScrollFrame = window.requestAnimationFrame(animateSmoothPageScroll);
}

function handlePageContentWheel(event) {
  if (!elements.pageContent || !shouldUseSmoothPageScroll() || event.defaultPrevented || event.ctrlKey) {
    return;
  }

  const target = event.target;
  if (!(target instanceof Element)) {
    return;
  }

  const insidePageContent = elements.pageContent.contains(target);
  const insideTopbar = Boolean(target.closest(".topbar"));
  if (!insidePageContent && !insideTopbar) {
    return;
  }

  if (insidePageContent) {
    const scrollContainer = findNestedScrollContainer(target, elements.pageContent);
    if (scrollContainer !== elements.pageContent) {
      return;
    }
  }

  if (target.closest("textarea, [contenteditable='true']")) {
    return;
  }

  const maxScrollTop = Math.max(0, elements.pageContent.scrollHeight - elements.pageContent.clientHeight);
  if (maxScrollTop <= 0) {
    return;
  }

  const deltaY = normalizeWheelDelta(event);
  if (!deltaY) {
    return;
  }

  event.preventDefault();

  // Re-anchor on the real scroll position before accumulating. `current` was
  // always re-read from the DOM here, but `target` accumulated from its own
  // previous value, so anything that moved the page without going through this
  // handler left the two disagreeing: dragging the scrollbar, PageDown/Home,
  // a focus jump, or a re-render that resets scrollTop. The next wheel tick
  // then animated straight to that stale target instead of scrolling by one
  // notch. On History a single notch teleported the list up by however far the
  // stale target sat, hiding the page heading and its counters entirely.
  //
  // Accumulation is still what makes repeated ticks feel fast, so it is kept
  // while an animation is genuinely mid-flight and tracking the DOM.
  const actualScrollTop = elements.pageContent.scrollTop;
  if (!smoothPageScrollFrame || Math.abs(actualScrollTop - smoothPageScrollCurrent) > 1) {
    smoothPageScrollTarget = actualScrollTop;
  }
  smoothPageScrollCurrent = actualScrollTop;
  smoothPageScrollTarget = Math.min(
    maxScrollTop,
    Math.max(0, smoothPageScrollTarget + deltaY * 0.72),
  );

  if (smoothPageScrollFrame) {
    return;
  }

  smoothPageScrollFrame = window.requestAnimationFrame(animateSmoothPageScroll);
}

function handleClick(event) {
  markInterfaceInteractionActivity();

  const target = event.target;
  const nativeDateInput = target.closest?.('.date-picker-control > input[type="date"]');
  if (nativeDateInput instanceof HTMLInputElement && !nativeDateInput.disabled && !nativeDateInput.readOnly) {
    if (typeof nativeDateInput.showPicker === "function") {
      try {
        nativeDateInput.focus({ preventScroll: true });
        nativeDateInput.showPicker();
        event.preventDefault();
        return;
      } catch (_error) {
        // Let the browser's normal date-input action run on older builds.
      }
    }
  }
  const interactiveButton = target.closest("button, [role='button'], [data-action], [data-view], [data-tab]");
  if (interactiveButton?.dataset.smoothActivationReady !== "true") {
    beginButtonPressFeedback(interactiveButton);
  }

  const viewButton = target.closest("[data-view]");
  if (viewButton) {
    navigateTo(viewButton.dataset.view);
    return;
  }

  const tabButton = target.closest("[data-tab]");
  if (tabButton) {
    state.activeSettingsTab = tabButton.dataset.tab;
    renderOverlays();
    return;
  }

  const actionButton = target.closest("[data-action]");
  if (!actionButton || actionButton.disabled) {
    return;
  }

  const { action, id, mode } = actionButton.dataset;

  switch (action) {
    case "open-settings":
      if (state.settingsMenuOpen) {
        closeSettingsMenu();
      } else {
        openSettingsMenu(actionButton);
      }
      return;
    case "toggle-theme":
      toggleTheme();
      return;
    case "open-notifications":
      if (state.notificationsOpen) {
        closeNotificationsDrawer();
      } else {
        openNotificationsDrawer();
      }
      return;
    case "toggle-dashboard-rows":
      state.dashboardAllRowsOpen = true;
      renderOverlays();
      return;
    case "close-dashboard-all-rows":
      state.dashboardAllRowsOpen = false;
      renderOverlays();
      return;
    case "open-profile-settings":
      openSettings("profile");
      return;
    case "open-settings-section":
      openSettings(actionButton.dataset.section || "profile");
      return;
    case "guide-prev-step":
      state.activeGuideStep = typeof normalizeGuideStep === "function"
        ? normalizeGuideStep(state.activeGuideStep - 1)
        : Math.max(0, state.activeGuideStep - 1);
      if (typeof updateGuideStepView !== "function" || !updateGuideStepView()) {
        renderOverlays();
      }
      return;
    case "guide-next-step":
      state.activeGuideStep = typeof normalizeGuideStep === "function"
        ? normalizeGuideStep(state.activeGuideStep + 1)
        : state.activeGuideStep + 1;
      if (typeof updateGuideStepView !== "function" || !updateGuideStepView()) {
        renderOverlays();
      }
      return;
    case "guide-jump-step":
      state.activeGuideStep = typeof normalizeGuideStep === "function"
        ? normalizeGuideStep(Number.parseInt(actionButton.dataset.step || "0", 10))
        : Number.parseInt(actionButton.dataset.step || "0", 10);
      if (typeof updateGuideStepView !== "function" || !updateGuideStepView()) {
        renderOverlays();
      }
      return;
    case "change-profile-photo": {
      const fileInput = document.getElementById("profile-photo-input");
      if (!(fileInput instanceof HTMLInputElement)) {
        return;
      }

      // The Pi kiosk must never reach Chromium's native file dialog: it browses
      // the whole filesystem -- root, /media, every home folder -- from a panel
      // standing in the open. The in-app picker reads one server-side folder
      // instead, and a picker that cannot load fails closed rather than falling
      // back to the dialog it exists to replace.
      const kioskPhotoPicker = window.ICuCropsKioskPhotoPicker;
      if (kioskPhotoPicker?.isEnabled?.()) {
        void kioskPhotoPicker.open().then((selectedPhoto) => {
          if (selectedPhoto) {
            applyProfilePhotoFile(fileInput, selectedPhoto);
          }
        });
        return;
      }

      fileInput.click();
      return;
    }
    case "close-settings-menu":
      closeSettingsMenu();
      return;
    case "close-settings":
      closeSettings();
      return;
    case "noop":
      return;
    case "close-notifications":
      closeNotificationsDrawer();
      return;
    case "show-more-history":
      showMoreHistory();
      return;
    case "logout":
      openLogoutConfirm();
      return;
    case "close-logout-confirm":
      closeLogoutConfirm();
      return;
    case "close-greenhouse-alert":
      dismissGreenhouseVentAlert();
      return;
    case "view-cultivation-parameters":
      openCultivationParameters(actionButton.dataset.id);
      return;
    case "open-sensor-parameters":
      openSensorRowParameters(actionButton.dataset.row);
      return;
    case "close-cultivation-parameters":
      closeCultivationParameters();
      return;
    case "edit-cultivation-parameters":
      beginCultivationParametersEdit();
      return;
    case "cancel-cultivation-parameters-edit":
      cancelCultivationParametersEdit();
      return;
    case "save-cultivation-parameters":
      void saveCultivationParameters();
      return;
    case "confirm-logout":
      logoutUser();
      return;
    case "close-delete-schedule-confirm":
      closeDeleteScheduleConfirm();
      return;
    case "confirm-delete-schedule":
      void confirmDeleteSchedule();
      return;
    case "forgot-password":
      requestPasswordReset();
      return;
    case "toggle-password-visibility":
      togglePasswordVisibility(actionButton.dataset.target);
      return;
    case "open-sensor-detail":
      openSensorDetail(id);
      return;
    case "close-sensor-detail":
      closeSensorDetail();
      return;
    case "save-profile":
      void saveProfile();
      return;
    case "change-password":
      requestPasswordChange();
      return;
    case "cancel-password-change-otp":
      resetPasswordChangeState(false);
      renderOverlays();
      return;
    case "verify-otp":
      completePasswordChange();
      return;
    case "set-row-irrigation-mode": {
      const rowKey = actionButton.dataset.row;
      const row = state.irrigationPage.rows.find((item) => item.key === rowKey);
      const nextMode = ["automatic", "schedule", "manual"].includes(mode) ? mode : "automatic";
      if (!row?.active) {
        pushNotification("warning", `${row?.label || "This row"} is inactive. Start a cultivation first.`);
        renderOverlays();
        return;
      }
      row.mode = nextMode;
      markIrrigationRowChanged(rowKey);
      if (nextMode !== "manual") {
        state.irrigationPage.activeManualRows = removeIrrigationRowFromRunMap(
          state.irrigationPage.activeManualRows,
          rowKey,
        );
        state.irrigationPage.activeManualLines = irrigationLinesFromChannelRows(state.irrigationPage.activeManualRows);
        state.irrigationPage.activeManualLine = firstActiveIrrigationLine(state.irrigationPage.activeManualLines);
      }
      if (nextMode !== "schedule") {
        const scheduleArmedRows = normalizeIrrigationRowMap(state.irrigationPage.scheduleArmedRows);
        delete scheduleArmedRows[rowKey];
        state.irrigationPage.scheduleArmedRows = scheduleArmedRows;
        state.irrigationPage.activeScheduleRows = removeIrrigationRowFromRunMap(
          state.irrigationPage.activeScheduleRows,
          rowKey,
        );
        state.irrigationPage.activeScheduleLines = irrigationLinesFromChannelRows(state.irrigationPage.activeScheduleRows);
      }
      if (nextMode !== "automatic") {
        state.irrigationPage.activeAutomaticRows = removeIrrigationRowFromRunMap(
          state.irrigationPage.activeAutomaticRows,
          rowKey,
        );
        state.irrigationPage.activeAutomaticLines = irrigationLinesFromChannelRows(state.irrigationPage.activeAutomaticRows);
      }
      renderIrrigationPageUpdate();
      void saveIrrigationStateWithFeedback({
        successMessage: `${row.label} is now in ${nextMode} mode.`,
      });
      return;
    }
    case "toggle-row-schedule-irrigation": {
      const rowKey = actionButton.dataset.row;
      const row = state.irrigationPage.rows.find((item) => item.key === rowKey);
      if (!row?.active || row.mode !== "schedule") {
        return;
      }
      const armedRows = normalizeIrrigationRowMap(state.irrigationPage.scheduleArmedRows);
      const isArmed = Boolean(armedRows[rowKey]);
      if (isArmed) {
        delete armedRows[rowKey];
        state.irrigationPage.activeScheduleRows = removeIrrigationRowFromRunMap(
          state.irrigationPage.activeScheduleRows,
          rowKey,
        );
      } else {
        const enabledChannels = IRRIGATION_CHANNELS.filter(
          (channel) => row.channels?.[channel.key]?.scheduleEnabled,
        );
        if (!enabledChannels.length) {
          pushNotification("warning", `Enable at least one solution for ${row.label}.`);
          renderOverlays();
          return;
        }
        armedRows[rowKey] = true;
      }
      state.irrigationPage.scheduleArmedRows = armedRows;
      markIrrigationRowChanged(rowKey);
      state.irrigationPage.activeScheduleLines = irrigationLinesFromChannelRows(
        state.irrigationPage.activeScheduleRows,
      );
      renderIrrigationPageUpdate();
      void saveIrrigationStateWithFeedback({
        successMessage: isArmed ? "" : `${row.label} schedule armed. Each solution will start at its configured time.`,
        warningMessage: isArmed ? `${row.label} schedule stopped.` : "",
      });
      return;
    }
    case "toggle-row-manual-irrigation": {
      const rowKey = actionButton.dataset.row;
      const channel = actionButton.dataset.channel;
      const row = state.irrigationPage.rows.find((item) => item.key === rowKey);
      if (!row?.active || row.mode !== "manual" || !row.channels?.[channel]) {
        return;
      }
      const activeRows = normalizeIrrigationChannelRowMap(state.irrigationPage.activeManualRows);
      const isRunning = Boolean(activeRows[channel]?.[rowKey]);
      if (!isRunning) {
        // The lime tank check comes first. Dosing the wrong solution moves the
        // pH the wrong way, which is a worse mistake than dosing when the row
        // did not need it, and it cannot be undone by stopping the run.
        if (channel === "limeSolution") {
          const tankAdvisory = limeTankAdvisory(row, { kind: "irrigation", mode: "manual" });
          if (tankAdvisory) {
            state.controlAdvisory = tankAdvisory;
            renderOverlays();
            return;
          }
          if (!row.sensorAvailable?.limeSolution) {
            state.controlAdvisory = limeUnreadableAdvisory(row);
            renderOverlays();
            return;
          }
        }
        // Only a start is worth questioning, and only when the live reading
        // says the row already holds what this line would add.
        const advisory = manualIrrigationAdvisory(row, channel);
        if (advisory) {
          state.controlAdvisory = advisory;
          renderOverlays();
          return;
        }
        activeRows[channel] = { ...(activeRows[channel] || {}), [rowKey]: true };
      } else {
        delete activeRows[channel][rowKey];
        if (!Object.keys(activeRows[channel]).length) {
          delete activeRows[channel];
        }
      }
      markIrrigationManualLineChange(channel, rowKey, !isRunning);
      applyManualIrrigationRows(activeRows);
      void saveIrrigationStateWithFeedback({
        successMessage: isRunning ? "" : `${irrigationChannelMeta(channel).label} started for ${row.label}.`,
        warningMessage: isRunning ? `${irrigationChannelMeta(channel).label} stopped for ${row.label}.` : "",
      });
      return;
    }
    case "dismiss-control-advisory": {
      const advisory = state.controlAdvisory;
      state.controlAdvisory = null;
      if (advisory?.confirmationKey) {
        // Cancel means "not now", never "yes". Nothing is confirmed, so the
        // lime line for this row stays off. The card is parked, not ended: it
        // asks again after limeTankCardReturnMs(), when the person comes back
        // to Irrigation or picks this row there, or at once from the row
        // card's Check Tank button -- until the tank is confirmed or the pH is
        // back in range. Both kinds are parked; a Cancel on the Start press
        // would otherwise bring the same row's card straight back.
        const returnAt = Date.now() + limeTankCardReturnMs();
        state.limeTankDeferred = {
          ...(state.limeTankDeferred || {}),
          ...Object.fromEntries(limeTankAdvisoryKeys(advisory).map((key) => [key, returnAt])),
        };
        scheduleLimeTankCardReturn();
        renderIrrigationPageUpdate();
        pushNotification(
          "warning",
          `Lime Solution stays off for ${advisory.rowLabel} until the tank is confirmed.`,
        );
      }
      renderOverlays();
      return;
    }
    case "review-lime-tank": {
      const row = state.irrigationPage.rows.find((item) => item.key === actionButton.dataset.row);
      if (!row?.active) {
        return;
      }
      const advisory = limeTankAdvisory(row, { kind: "lime-hold", mode: row.mode });
      if (!advisory) {
        return;
      }
      state.controlAdvisory = advisory;
      renderOverlays();
      return;
    }
    case "confirm-control-advisory": {
      const advisory = state.controlAdvisory;
      if (!advisory) {
        renderOverlays();
        return;
      }
      // The tank card is two steps. The first says what the row needs; the
      // second asks the person to confirm the tank really holds it. Nothing
      // runs, and nothing is remembered, until that second answer.
      if (advisory.step === "check") {
        state.controlAdvisory = limeTankConfirmStep(advisory);
        renderOverlays();
        return;
      }
      // Remember that this row's tank was checked for this solution, so the
      // card does not reappear on every pass while the pH is still correcting.
      // Recorded before the overlays redraw: that redraw raises any row still
      // waiting, and this one must no longer count as waiting.
      const answeredKeys = limeTankAdvisoryKeys(advisory);
      if (answeredKeys.length) {
        state.limeTankConfirmations = {
          ...(state.limeTankConfirmations || {}),
          ...Object.fromEntries(answeredKeys.map((key) => [key, true])),
        };
        const deferred = { ...(state.limeTankDeferred || {}) };
        answeredKeys.forEach((key) => {
          delete deferred[key];
        });
        state.limeTankDeferred = deferred;
      }
      state.controlAdvisory = null;
      renderOverlays();
      if (advisory.kind === "lime-hold") {
        // Automatic or scheduled lime was held back waiting for this answer.
        // Saving lets the backend see the row as ready; it runs on the next
        // automatic pass or at the next scheduled time.
        renderIrrigationPageUpdate();
        void saveIrrigationStateWithFeedback({
          successMessage: `${advisory.rowLabel}: tank confirmed for ${advisory.solutionLabel}.`,
        });
        return;
      }
      if (advisory.blocked) {
        // Nothing to confirm on a blocked card; it has no confirm button, and
        // a stray action must not start the run it refused.
        return;
      }
      if (advisory.kind === "irrigation") {
        startManualIrrigationRun(advisory.rowKey, advisory.channelKey);
      } else {
        applyActuatorMode(advisory.actuatorKey, "on");
      }
      return;
    }
    case "set-irrigation-mode": {
      const nextMode = ["automatic", "schedule", "manual"].includes(mode) ? mode : "automatic";
      state.irrigationPage.mode = nextMode;
      state.irrigationPage.overlayMode = "";
      renderIrrigationPageUpdate({ animateMode: true });
      renderOverlays();
      void saveIrrigationStateWithFeedback();
      return;
    }
    case "close-irrigation-overlay":
      state.irrigationPage.overlayMode = "";
      renderIrrigationPageUpdate();
      renderOverlays();
      void persistIrrigationState();
      return;
    case "toggle-auto-irrigation":
      state.irrigationPage.autoEnabled = !state.irrigationPage.autoEnabled;
      renderIrrigationPageUpdate();
      void saveIrrigationStateWithFeedback();
      return;
    case "toggle-irrigation-target-row": {
      const rowKey = actionButton.dataset.row;
      const row = state.irrigationPage.rows.find((item) => item.key === rowKey);
      if (!row?.active) {
        pushNotification("warning", `${row?.label || "This row"} is inactive. Start a cultivation before using irrigation.`);
        renderOverlays();
        return;
      }
      const targetRows = normalizeIrrigationRowMap(state.irrigationPage.targetRows);
      if (targetRows[rowKey]) {
        delete targetRows[rowKey];
      } else {
        targetRows[rowKey] = true;
      }
      state.irrigationPage.targetRows = targetRows;
      renderIrrigationPageUpdate();
      void persistIrrigationState();
      return;
    }
    case "toggle-schedule-irrigation": {
      const scheduleArmedRows = normalizeIrrigationRowMap(state.irrigationPage.scheduleArmedRows);
      const hasArmedSchedule = Object.keys(scheduleArmedRows).length > 0;

      if (hasArmedSchedule) {
        state.irrigationPage.scheduleArmedRows = {};
        state.irrigationPage.activeScheduleLines = {};
        state.irrigationPage.activeScheduleRows = {};
        state.irrigationPage.overlayMode = "";
        renderIrrigationPageUpdate();
        renderOverlays();
        void saveIrrigationStateWithFeedback({
          warningMessage: "Irrigation schedule canceled.",
        });
      } else {
        const targetRows = normalizeIrrigationRowMap(state.irrigationPage.targetRows);
        if (!Object.keys(targetRows).length) {
          pushNotification("warning", "Select at least one active row before starting the schedule.");
          renderOverlays();
          return;
        }
        const enabledChannels = IRRIGATION_CHANNELS.filter(
          (channel) => state.irrigationPage.channels[channel.key]?.scheduleEnabled,
        );
        if (!enabledChannels.length) {
          pushNotification("warning", "Enable at least one solution for the schedule.");
          renderOverlays();
          return;
        }
        state.irrigationPage.scheduleArmedRows = { ...targetRows };
        state.irrigationPage.activeScheduleLines = {};
        state.irrigationPage.activeScheduleRows = {};
        state.irrigationPage.rows.forEach((row) => {
          if (targetRows[row.key]) {
            row.mode = "schedule";
          }
        });
        state.irrigationPage.mode = "schedule";
        state.irrigationPage.overlayMode = "";
        renderIrrigationPageUpdate({ animateMode: true });
        renderOverlays();
        void saveIrrigationStateWithFeedback({
          successMessage: "Irrigation schedule armed. Each solution will start at its configured time.",
        });
      }
      return;
    }
    case "remove-schedule-line": {
      const channel = actionButton.dataset.channel;
      if (!channel || !state.irrigationPage.channels[channel]) {
        return;
      }

      const activeScheduleLines = normalizeIrrigationRunMap(state.irrigationPage.activeScheduleLines);
      if (!activeScheduleLines[channel]) {
        return;
      }

      openDeleteScheduleConfirm(channel);
      return;
    }
    case "toggle-manual-irrigation": {
      const channel = actionButton.dataset.channel;
      if (!channel || !state.irrigationPage.channels[channel]) {
        return;
      }

      const activeManualLines = normalizeIrrigationRunMap(state.irrigationPage.activeManualLines);
      if (activeManualLines[channel]) {
        delete activeManualLines[channel];
        Object.keys(state.irrigationPage.activeManualRows[channel] || {}).forEach((rowKey) => {
          markIrrigationManualLineChange(channel, rowKey, false);
        });
        delete state.irrigationPage.activeManualRows[channel];
      } else {
        const targetRows = normalizeIrrigationRowMap(state.irrigationPage.targetRows);
        if (!Object.keys(targetRows).length) {
          pushNotification("warning", "Select at least one active row before starting irrigation.");
          renderOverlays();
          return;
        }
        activeManualLines[channel] = true;
        Object.keys(targetRows).forEach((rowKey) => {
          markIrrigationManualLineChange(channel, rowKey, true);
        });
        state.irrigationPage.activeManualRows[channel] = { ...targetRows };
      }
      state.irrigationPage.activeManualLines = activeManualLines;
      state.irrigationPage.activeManualLine = firstActiveIrrigationLine(activeManualLines);
      renderIrrigationPageUpdate();
      renderOverlays();
      void persistIrrigationState();
      return;
    }
    case "set-actuator-mode": {
      const key = actionButton.dataset.actuator;
      const nextValue = actionButton.dataset.mode;
      if (!key || !nextValue) {
        return;
      }
      if (nextValue === "on") {
        // Every On is worth the second look, not only one that overrides
        // Automatic. The check used to require the card to be in Automatic
        // first, on the reasoning that coming from Off is already a deliberate
        // decision. It is -- but the thing being decided is whether to run the
        // hardware past the crops' limit, and someone pressing On from Off
        // cannot see that limit anywhere on the card. They got no warning at
        // all, which is the opposite of what the guard is for.
        //
        // Past the limit this warns and still lets the press through: the
        // operator is the one who can see the greenhouse, and the reading
        // behind the limit is a single shared DHT22. Turning Off, or handing
        // the decision back to Automatic, is never questioned.
        const advisory = actuatorSafetyWarning(key) || actuatorAdvisory(key);
        if (advisory) {
          state.controlAdvisory = advisory;
          renderOverlays();
          return;
        }
      }
      applyActuatorMode(key, nextValue);
      return;
    }
    case "calculate-harvest":
      void calculateHarvest();
      return;
    case "select-crop-type":
      selectCultivationCrop(actionButton.dataset.value || "");
      return;
    case "open-cultivation-setup":
      if (state.cultivation.cropType) {
        state.cultivation.setupOpen = true;
        state.cultivation.parameterPreviewMode = "";
        renderOverlays();
      }
      return;
    case "close-cultivation-setup":
      state.cultivation.setupOpen = false;
      state.cultivation.parameterPreviewMode = "";
      renderOverlays();
      return;
    case "close-cultivation-parameter-preview":
      state.cultivation.parameterPreviewMode = "";
      renderOverlays();
      return;
    case "confirm-cultivation-parameter-preview":
      state.cultivation.parameterPreviewMode = "";
      renderOverlays();
      return;
    case "open-cultivation-parameter-preview":
      if (!isCultivationParameterModeAvailable(state.cultivation.parameterMode, state.cultivation)) {
        return;
      }
      state.cultivation.parameterPreviewMode = state.cultivation.parameterMode;
      renderOverlays();
      return;
    case "report-preset":
      applyReportPreset(id);
      return;
    case "report-toggle-section":
      toggleReportSection(id);
      return;
    case "report-download":
      void downloadReport(id);
      return;
    case "report-clear-recent":
      clearRecentReports();
      return;
    case "dismiss-toast":
      beginNotificationExit(id);
      return;
    default:
      return;
  }
}

function handleSubmit(event) {
  const target = event.target;
  if (!(target instanceof HTMLFormElement) || target.id !== "login-form") {
    return;
  }

  event.preventDefault();
  loginUser();
}

function handleChange(event) {
  markInterfaceInteractionActivity();

  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }

  if (target instanceof HTMLSelectElement && target.id === "irrigation-active-row-select") {
    const activeRows = state.irrigationPage.rows.filter((row) => row.active);
    const selectedRow = activeRows.find((row) => row.key === target.value)
      || activeRows.find((row) => row.key === state.irrigationPage.selectedRowKey)
      || activeRows[0]
      || null;
    state.irrigationPage.selectedRowKey = selectedRow?.key || "";
    if (selectedRow) {
      target.value = selectedRow.key;
      clearLimeTankDeferrals(selectedRow.key);
    }
    writeIrrigationSelectedRowKey(state.irrigationPage.selectedRowKey);
    renderIrrigationPageUpdate();
    return;
  }

  if (target instanceof HTMLSelectElement && target.dataset.graphRange) {
    const graphKey = target.dataset.graphRange === "cultivation"
      ? target.dataset.graphRange
      : "sensor";
    state.dashboardGraphRanges[graphKey] = normalizeDashboardGraphRange(target.value, graphKey);
    writeDashboardGraphRangeCache();

    // Only a range wider than what is already loaded costs a request; narrowing
    // back down draws from the rows the browser is already holding.
    if (state.isAuthenticated && dashboardHistoryDaysNeeded() > (state.dashboardSeriesDays || 0)) {
      void refreshSensors({ render: state.activeView !== "dashboard" }).then(() => {
        if (state.activeView === "dashboard") {
          renderDashboardLiveGraphSections(graphKey);
          syncDashboardLiveSensorGraph();
        }
      });
    }

    if (state.isAuthenticated && state.activeView === "dashboard") {
      renderDashboardLiveGraphSections(graphKey);
      syncDashboardLiveSensorGraph();
      return;
    }

    renderPage();
    return;
  }

  if (target.dataset?.irrigationField && IRRIGATION_DURATION_FIELDS.has(target.dataset.irrigationField)) {
    // Normalize before reading the field into state, so what gets saved and
    // what stays on screen are the same number.
    commitIrrigationDurationField(target);
  }

  if (updateIrrigationPageField(target)) {
    renderIrrigationPageUpdate();
    renderOverlays();
    void persistIrrigationState();
    return;
  }

  if (target.dataset.sensorPower) {
    const key = target.dataset.sensorPower;
    const nextValue = target.value;
    const previousValue = state.sensorsPage.sensorPower[key] || "on";
    setSynchronizedSensorPowerState(key, nextValue);
    writeSensorControlCache(state.sensorsPage);
    if (!updateSensorManagementCardsByPowerKey(key)) {
      console.warn(`Sensor control card was not found: ${key}`);
    }
    runSensorControlRequest("sensorPower", key, nextValue, {
      confirmedValue: previousValue,
      onRollback: (confirmedValue) => {
        setSynchronizedSensorPowerState(key, confirmedValue);
        writeSensorControlCache(state.sensorsPage);
        if (!updateSensorManagementCardsByPowerKey(key)) {
          console.warn(`Sensor control card was not found during rollback: ${key}`);
        }
        pushNotification("warning", "Could not save the sensor power change. It was reverted.");
        renderOverlays();
      },
    });
    return;
  }

  if (target.dataset.rowSensorPower) {
    const key = target.dataset.rowSensorPower;
    const nextValue = target.value;
    const previousValue = state.sensorsPage.rowSensorPower[key] || "on";
    if (key === "dht22") {
      setSynchronizedSensorPowerState(key, nextValue);
    } else {
      state.sensorsPage.rowSensorPower[key] = nextValue;
    }
    writeSensorControlCache(state.sensorsPage);
    if (!updateSensorManagementCardsByPowerKey(key)) {
      console.warn(`Row sensor control card was not found: ${key}`);
    }
    runSensorControlRequest("rowSensorPower", key, nextValue, {
      confirmedValue: previousValue,
      onRollback: (confirmedValue) => {
        if (key === "dht22") {
          setSynchronizedSensorPowerState(key, confirmedValue);
        } else {
          state.sensorsPage.rowSensorPower[key] = confirmedValue;
        }
        writeSensorControlCache(state.sensorsPage);
        if (!updateSensorManagementCardsByPowerKey(key)) {
          console.warn(`Row sensor control card was not found during rollback: ${key}`);
        }
        pushNotification("warning", "Could not save the sensor power change. It was reverted.");
        renderOverlays();
      },
    });
    return;
  }

  switch (target.id) {
    case "cultivation-crop-type-select":
      if (target.value) {
        selectCultivationCrop(target.value);
      } else {
        state.cultivation.cropType = "";
        state.cultivation.successMessage = "";
        state.cultivation.successOpen = false;
        renderPage();
        renderOverlays();
      }
      return;
    case "planting-date-input":
    case "planting-date-input-modal":
      syncCultivationPlantingDate(target);
      return;
    case "cultivation-row-select":
    case "cultivation-row-select-modal":
      syncCultivationRowSelection(target.value);
      if (target.id === "cultivation-row-select") {
        renderPage();
      } else {
        renderOverlays();
      }
      return;
    case "cultivation-parameter-mode-select":
      if (target.value !== "recommended" || !supportsRecommendedCultivation(state.cultivation.cropType)) {
        return;
      }

      state.cultivation.parameterMode = "recommended";
      state.cultivation.parameterPreviewMode = "";
      state.cultivation.successMessage = "";
      state.cultivation.successOpen = false;
      renderOverlays();
      return;

    case "new-user-role":
      state.newUser.role = target.value;
      return;
    case "profile-photo-input":
      if (target instanceof HTMLInputElement) {
        handleProfilePhotoSelection(target);
      }
      return;
    default:
      return;
  }
}

function handleInput(event) {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }

  const actuatorDurationKey = target.getAttribute("data-actuator-duration");
  if (actuatorDurationKey) {
    // Held in state, not read off the DOM at press time: the card re-renders
    // on every live refresh, and a value read from an input that has just been
    // replaced is the old one.
    setActuatorRunDuration(actuatorDurationKey, target.value);
    return;
  }

  if (updateIrrigationPageField(target)) {
    // Typing is not yet a save -- that waits for "change", on blur or Enter.
    // Until then the live refresh is the only thing racing the half-typed
    // value, and its focus guard misses the gap between the last keystroke and
    // the commit: an answer already in flight lands after the field is no
    // longer focused and repaints the old duration over the new one. Holding
    // the same optimistic lock a save takes keeps what was typed on screen
    // until it has somewhere to be saved to.
    irrigationOptimisticLockUntil = Date.now() + 5000;
    return;
  }

  if (/^otp-\d$/.test(target.id)) {
    handleOtpInput(target);
    return;
  }

  if (target.dataset.cultivationParametersDate) {
    const draft = state.cultivationParametersEdit;
    if (draft) {
      draft[target.dataset.cultivationParametersDate === "harvest" ? "harvestDate" : "plantingDate"] = target.value;
    }
    return;
  }

  if (target.dataset.cultivationParametersField && target.dataset.cultivationParametersBound) {
    const { cultivationParametersField, cultivationParametersBound } = target.dataset;
    const draft = state.cultivationParametersEdit;
    if (draft && draft.parameters[cultivationParametersField]) {
      draft.parameters[cultivationParametersField][cultivationParametersBound] = target.value;
    }
    return;
  }

  if (target.dataset.cultivationField && target.dataset.cultivationBound) {
    const { cultivationField, cultivationBound } = target.dataset;
    if (state.cultivation.parameters[cultivationField]) {
      state.cultivation.parameters[cultivationField][cultivationBound] = target.value;
      state.cultivation.successMessage = "";
      state.cultivation.successOpen = false;
    }
    return;
  }

  switch (target.id) {
    case "profile-name-input": {
      const validationMessage = profileNameValidationMessage(target.value);
      const exceedsTypingLimit = target.value.length > PROFILE_NAME_MAX_LENGTH
        || hasExcessiveConsecutiveLetters(target.value);
      if (exceedsTypingLimit) {
        target.value = state.profileName;
        state.profileNameError = validationMessage;
        updateProfileNameValidationUI();
        return;
      }
      state.profileName = target.value;
      state.profileNameError = validationMessage;
      updateProfilePreview();
      updateProfileNameValidationUI();
      return;
    }
    case "current-password-input": {
      const shouldResetOtp = state.passwordChangeOtpRequested;
      state.currentPassword = target.value;
      if (shouldResetOtp) {
        state.passwordChangeOtpRequested = false;
        state.passwordChangeChallengeId = "";
        state.passwordChangeSubmitting = false;
        state.otpCode = initialOtpCode();
        renderOverlays();
        return;
      }
      updateSettingsButtonStates();
      return;
    }
    case "new-password-input": {
      const shouldResetOtp = state.passwordChangeOtpRequested;
      state.newPassword = target.value;
      if (shouldResetOtp) {
        state.passwordChangeOtpRequested = false;
        state.passwordChangeChallengeId = "";
        state.passwordChangeSubmitting = false;
        state.otpCode = initialOtpCode();
        renderOverlays();
        return;
      }
      updateSettingsButtonStates();
      return;
    }
    case "new-user-name":
      state.newUser.name = target.value;
      updateAddUserButtonState();
      return;
    case "new-user-email":
      state.newUser.email = target.value;
      updateAddUserButtonState();
      return;
    case "new-user-password":
      state.newUser.password = target.value;
      updateAddUserButtonState();
      return;
    case "new-user-confirm-password":
      state.newUser.confirmPassword = target.value;
      updateAddUserButtonState();
      return;
    case "login-email-input":
      state.loginForm.email = target.value;
      updateLoginButtonState();
      return;
    case "login-password-input":
      state.loginForm.password = target.value;
      updateLoginButtonState();
      return;
    case "planting-date-input":
    case "planting-date-input-modal":
      syncCultivationPlantingDate(target);
      return;
    case "custom-plant-name-input":
      state.cultivation.customPlantName = target.value;
      state.cultivation.harvestDate = "";
      state.cultivation.daysToHarvest = 0;
      state.cultivation.successMessage = "";
      state.cultivation.successOpen = false;
      return;
    case "custom-harvest-date-input":
      state.cultivation.customHarvestTargetDate = target.value;
      state.cultivation.harvestDate = "";
      state.cultivation.daysToHarvest = 0;
      state.cultivation.successMessage = "";
      state.cultivation.successOpen = false;
      return;
    default:
      return;
  }
}

function handleKeyDown(event) {
  if (event.key === "Escape" && state.logoutConfirmOpen) {
    closeLogoutConfirm();
    return;
  }

  if (event.key === "Escape" && state.cultivationParametersId) {
    // Escape leaves the editor first. Closing the whole dialog from under an
    // unsaved change would throw the change away with it.
    if (state.cultivationParametersEdit) {
      cancelCultivationParametersEdit();
      return;
    }
    closeCultivationParameters();
    return;
  }

  if (event.key === "Escape" && state.settingsMenuOpen) {
    closeSettingsMenu();
    return;
  }

  const target = event.target;
  if (target instanceof HTMLElement && target.dataset.action === "open-profile-settings") {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openSettings("profile");
      return;
    }
  }

  if (!(target instanceof HTMLElement) || !/^otp-\d$/.test(target.id)) {
    return;
  }

  const index = Number(target.id.split("-")[1]);
  if (event.key === "Backspace" && !target.value && index > 0) {
    const previous = document.getElementById(`otp-${index - 1}`);
    previous?.focus();
  }
}

function queueViewportInteraction() {
  if (viewportInteractionFrame) {
    return;
  }

  viewportInteractionFrame = window.requestAnimationFrame(() => {
    viewportInteractionFrame = 0;
    handleViewportInteraction();
  });
}

function handleViewportInteraction() {
  markInterfaceInteractionActivity();
  markInterfaceScrollActivity();
  markDashboardScrollActivity();
  dashboardClearChartTooltip();

  if (!state.settingsMenuOpen) {
    return;
  }

  closeSettingsMenu();
}

function markInterfaceScrollActivity() {
  document.body.classList.add("is-interface-scrolling");

  if (interfaceScrollActivityTimer) {
    window.clearTimeout(interfaceScrollActivityTimer);
  }

  interfaceScrollActivityTimer = window.setTimeout(() => {
    interfaceScrollActivityTimer = 0;
    document.body.classList.remove("is-interface-scrolling");
  }, INTERFACE_SCROLL_SETTLE_MS);
}

function markInterfaceInteractionActivity() {
  document.body.classList.add("is-motion-paused");

  if (interfaceInteractionTimer) {
    window.clearTimeout(interfaceInteractionTimer);
  }

  interfaceInteractionTimer = window.setTimeout(() => {
    interfaceInteractionTimer = 0;
    document.body.classList.remove("is-motion-paused");
  }, INTERACTION_PERFORMANCE_PAUSE_MS);
}

function markDashboardScrollActivity() {
  if (!state.isAuthenticated || state.activeView !== "dashboard") {
    return;
  }

  dashboardLiveGraphPausedUntil = Date.now() + DASHBOARD_LIVE_GRAPH_SCROLL_PAUSE_MS;
  document.body.classList.add("is-dashboard-scrolling");

  if (dashboardScrollActivityTimer) {
    window.clearTimeout(dashboardScrollActivityTimer);
  }

  dashboardScrollActivityTimer = window.setTimeout(() => {
    dashboardScrollActivityTimer = 0;
    document.body.classList.remove("is-dashboard-scrolling");
  }, DASHBOARD_LIVE_GRAPH_SCROLL_PAUSE_MS);
}

function readSettingsMenuScrollSnapshot() {
  const scrollingElement = document.scrollingElement;

  return {
    windowX: window.scrollX,
    windowY: window.scrollY,
    documentTop: scrollingElement?.scrollTop || 0,
    documentLeft: scrollingElement?.scrollLeft || 0,
    pageContentTop: elements.pageContent?.scrollTop || 0,
    pageContentLeft: elements.pageContent?.scrollLeft || 0,
    sidebarTop: elements.sidebar?.scrollTop || 0,
    sidebarLeft: elements.sidebar?.scrollLeft || 0,
  };
}

function hasSettingsMenuScrolled() {
  if (!settingsMenuScrollSnapshot) {
    return false;
  }

  const nextSnapshot = readSettingsMenuScrollSnapshot();
  return Object.keys(settingsMenuScrollSnapshot).some(
    (key) => nextSnapshot[key] !== settingsMenuScrollSnapshot[key],
  );
}

function watchSettingsMenuScroll() {
  if (!state.settingsMenuOpen) {
    settingsMenuWatchFrame = 0;
    return;
  }

  if (hasSettingsMenuScrolled()) {
    closeSettingsMenu();
    return;
  }

  settingsMenuWatchFrame = window.requestAnimationFrame(watchSettingsMenuScroll);
}

function startSettingsMenuWatcher() {
  stopSettingsMenuWatcher();
  settingsMenuScrollSnapshot = readSettingsMenuScrollSnapshot();
}

function stopSettingsMenuWatcher() {
  if (settingsMenuWatchFrame) {
    window.cancelAnimationFrame(settingsMenuWatchFrame);
    settingsMenuWatchFrame = 0;
  }

  settingsMenuScrollSnapshot = null;
}

function handlePointerDown(event) {
  markInterfaceInteractionActivity();

  if (!state.settingsMenuOpen) {
    return;
  }

  const target = event.target;
  if (!(target instanceof Element)) {
    closeSettingsMenu();
    return;
  }

  if (target.closest(".settings-menu")) {
    return;
  }

  if (target.closest('[data-action="open-settings"]')) {
    return;
  }

  closeSettingsMenu();
}

function applyShellState() {
  const authScreen = !state.isAuthenticated;
  if (authScreen || isMobileDashboardLayout()) {
    stopSmoothPageScroll();
  }
  document.body.classList.toggle("is-auth-screen", authScreen);
  document.body.classList.toggle("is-cultivation-view", !authScreen && state.activeView === "cultivation");
  elements.sidebar?.toggleAttribute("hidden", authScreen);
  elements.topbar?.toggleAttribute("hidden", authScreen);
  elements.appMain?.classList.toggle("app-main--auth", authScreen);
  elements.pageContent?.classList.toggle("page-content--auth", authScreen);
}

function renderSidebar() {
  applyShellState();

  if (!state.isAuthenticated) {
    elements.sidebarNav.innerHTML = "";
    delete elements.sidebarNav.dataset.rendered;
    return;
  }

  if (elements.sidebarNav.dataset.rendered !== "true") {
    const navMarkup = NAV_ITEMS.map((item) => `
      <button class="nav-button" type="button" data-view="${item.view}">
        <span class="nav-button__icon" aria-hidden="true">${icon(item.icon)}</span>
        <span>${item.label}</span>
      </button>
    `).join("");

    elements.sidebarNav.innerHTML = navMarkup;
    elements.sidebarNav.dataset.rendered = "true";
  }

  elements.sidebarNav.querySelectorAll("[data-view]").forEach((button) => {
    const active = button.dataset.view === state.activeView;
    button.classList.toggle("is-active", active);
    if (active) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  });

  const settingsButtonIcon = document.querySelector('[data-action="open-settings"] .nav-button__icon');
  const logoutButtonIcon = document.querySelector('[data-action="logout"] .nav-button__icon');
  if (settingsButtonIcon) {
    setIconSlot(settingsButtonIcon, "settings");
  }
  if (logoutButtonIcon) {
    setIconSlot(logoutButtonIcon, "logout");
  }
}

// Re-assigning innerHTML swaps every node underneath even when the markup is
// identical, and each swap is a repaint of that icon. Compare against the
// browser's own serialisation of the markup, so attribute quoting and
// self-closing tags cannot make an unchanged icon look different.
const normalizedInnerMarkupCache = new Map();

function replaceInnerMarkupIfChanged(element, markup) {
  let normalized = normalizedInnerMarkupCache.get(markup);
  if (normalized === undefined) {
    const template = document.createElement("template");
    template.innerHTML = markup;
    normalized = template.innerHTML;
    normalizedInnerMarkupCache.set(markup, normalized);
  }
  if (element.innerHTML !== normalized) {
    element.innerHTML = markup;
  }
}

// The mobile shell restyles the header icons in place, so their markup never
// matches icon() again and cannot be compared. Remember which icon each slot
// holds instead, and only redraw it when that changes -- every header and
// sidebar pass used to rebuild these, several times per profile upload.
const iconSlotNames = new WeakMap();

function setIconSlot(element, name) {
  if (iconSlotNames.get(element) === name && element.querySelector("svg")) {
    return;
  }
  element.innerHTML = icon(name);
  iconSlotNames.set(element, name);
}

function renderHeader() {
  applyShellState();
  syncThemeToggleButton();

  if (!state.isAuthenticated) {
    return;
  }

  elements.headerProfileName.textContent = state.savedProfileName.trim() || DEFAULT_PROFILE_NAME;
  if (elements.headerProfileRole) {
    elements.headerProfileRole.textContent = state.profileRole || DEFAULT_PROFILE_ROLE;
  }
  syncProfileAvatarElement(elements.headerProfileAvatar, "profile-pill__avatar");
  if (elements.headerNotificationIcon) {
    setIconSlot(elements.headerNotificationIcon, "bell");
  }
  renderNotificationHeaderState();
}

function renderNotificationHeaderState() {
  if (!state.isAuthenticated) {
    return;
  }

  const unread = unreadNotificationCount();

  if (elements.headerNotificationCount) {
    elements.headerNotificationCount.textContent = unread > 99 ? "99+" : String(unread);
    elements.headerNotificationCount.hidden = unread === 0;
  }
  if (elements.headerNotificationButton) {
    elements.headerNotificationButton.classList.toggle("is-active", state.notificationsOpen);
    elements.headerNotificationButton.setAttribute("aria-pressed", String(state.notificationsOpen));
    elements.headerNotificationButton.setAttribute(
      "aria-label",
      unread > 0
        ? `Open notifications, ${unread} unread`
        : "Open notifications"
    );
  }
}

function beginButtonPressFeedback(button) {
  if (!(button instanceof HTMLElement) || button.matches(":disabled, [disabled]") || prefersReducedMotion()) {
    return;
  }

  button.classList.add("is-button-pressing");
  const activeTimer = buttonPressTimers.get(button);
  if (activeTimer) {
    window.clearTimeout(activeTimer);
  }

  const timer = window.setTimeout(() => {
    button.classList.remove("is-button-pressing");
    buttonPressTimers.delete(button);
  }, BUTTON_PRESS_FEEDBACK_MS);
  buttonPressTimers.set(button, timer);
}

function readThemePreference() {
  try {
    const storedTheme = window.localStorage?.getItem(THEME_CACHE_KEY);
    return storedTheme === THEME_DARK ? THEME_DARK : THEME_LIGHT;
  } catch (error) {
    return THEME_LIGHT;
  }
}

function writeThemePreference(theme) {
  try {
    window.localStorage?.setItem(THEME_CACHE_KEY, theme);
  } catch (error) {
    // Theme persistence is optional; the current page can still update.
  }
}

function applyTheme(theme) {
  const nextTheme = theme === THEME_DARK ? THEME_DARK : THEME_LIGHT;
  document.documentElement.setAttribute("data-theme", nextTheme);
  document.documentElement.style.colorScheme = nextTheme;
  document.body?.classList.toggle("is-dark-theme", nextTheme === THEME_DARK);
  syncThemeToggleButton(nextTheme);
}

// Theme and dashboard graph range are deliberately device-local. They used to
// be mirrored to the account and pushed back down on every profile load, which
// meant one device could silently flip another device's theme mid-session and
// the two could fight over the graph range. They now live only in this
// browser's localStorage (writeThemePreference / writeDashboardGraphRangeCache).

function toggleTheme() {
  const nextTheme = document.documentElement.dataset.theme === THEME_DARK ? THEME_LIGHT : THEME_DARK;
  const root = document.documentElement;
  const commitTheme = () => {
    applyTheme(nextTheme);
    writeThemePreference(nextTheme);
  };

  if (typeof document.startViewTransition !== "function" || prefersReducedMotion()) {
    commitTheme();
    return;
  }

  root.classList.add("is-theme-transitioning");

  try {
    const transition = document.startViewTransition(commitTheme);
    const finishThemeTransition = () => root.classList.remove("is-theme-transitioning");
    transition.finished.then(finishThemeTransition, finishThemeTransition);
  } catch (error) {
    root.classList.remove("is-theme-transitioning");
    commitTheme();
  }
}

function syncThemeToggleButton(theme = document.documentElement.dataset.theme) {
  const dark = theme === THEME_DARK;

  if (elements.headerThemeToggleIcon) {
    setIconSlot(elements.headerThemeToggleIcon, dark ? "sun" : "moon");
  }

  if (elements.headerThemeToggleButton) {
    elements.headerThemeToggleButton.classList.toggle("is-active", dark);
    elements.headerThemeToggleButton.setAttribute("aria-pressed", String(dark));
    elements.headerThemeToggleButton.setAttribute("aria-label", dark ? "Turn off dark mode" : "Turn on dark mode");
    elements.headerThemeToggleButton.setAttribute("title", dark ? "Light Mode" : "Dark Mode");
  }
}

let lastRenderedPageMarkup = null;
let lastRenderedPageView = null;

function renderPage() {
  applyShellState();

  if (!state.isAuthenticated) {
    pendingRouteTransition = null;
    elements.pageContent?.classList.remove(
      "page-content--transition-out",
      "page-content--transition-forward",
      "page-content--transition-backward"
    );
    elements.pageContent.innerHTML = loginTemplate();
    lastRenderedPageMarkup = null;
    lastRenderedPageView = null;
    syncPasswordToggleButtons(elements.pageContent);
    updateLoginButtonState();
    syncDashboardLiveSensorGraph();
    return;
  }

  const templates = {
    dashboard: dashboardTemplate,
    history: historyTemplate,
    sensors: sensorsTemplate,
    irrigation: irrigationTemplate,
    cultivation: cultivationTemplate,
    reports: reportsTemplate,
  };

  const template = state.activeView === "dashboard" && isMobileDashboardLayout()
    ? mobileDashboardTemplate
    : templates[state.activeView] || dashboardTemplate;
  const shouldResetScroll = Boolean(pendingRouteTransition);
  const nextPageMarkup = renderPageSceneMarkup(template(), state.activeView);
  const pageMarkupChanged = nextPageMarkup !== lastRenderedPageMarkup || state.activeView !== lastRenderedPageView;
  if (pageMarkupChanged) {
    // Replacing innerHTML collapses the scroll height, so the browser clamps
    // this container back to the top. Data re-renders happen on their own -- a
    // notification arrives, an item is deleted, a sensor value ticks -- and
    // dropping the reader's place in a long list on every one of those is
    // wrong on its own. It also fed the History jump: the wheel smoothing was
    // still holding the pre-render target, so the next frame animated the list
    // down to it and the page heading scrolled off screen. A route change does
    // belong at the top, and that is shouldResetScroll below.
    const scroller = pageScrollElement();
    const previousScrollTop = shouldResetScroll ? 0 : scroller.scrollTop;
    // A data re-render must not take the keyboard with it. The card-level
    // patches already put focus back by id; the whole-page swap was the one
    // path that dropped it, so a value ticking under an open control kicked
    // the caret out to <body>.
    const activeElement = document.activeElement;
    const focusedId = activeElement instanceof HTMLElement
      && elements.pageContent.contains(activeElement)
      && activeElement.id
      ? activeElement.id
      : "";
    // A route change wants the new scene built fresh so its transition plays.
    // A data re-render is the same page with new numbers, and rebuilding it
    // was what made the reader's place, the focus and every entrance animation
    // start over on each reading.
    if (shouldResetScroll || !morphContainer(elements.pageContent, nextPageMarkup)) {
      elements.pageContent.innerHTML = nextPageMarkup;
    }
    lastRenderedPageMarkup = nextPageMarkup;
    lastRenderedPageView = state.activeView;
    // Password toggles inside a page template (Change Password on the profile)
    // ship with an empty icon slot, the way the reset-password pages do, so
    // the eye is drawn from one place and always matches the field's current
    // state. Only the login template used to be synced, which would have left
    // those buttons rendered blank.
    syncPasswordToggleButtons(elements.pageContent);
    if (focusedId) {
      document.getElementById(focusedId)?.focus({ preventScroll: true });
    }
    if (previousScrollTop > 0) {
      const maxScrollTop = Math.max(0, scroller.scrollHeight - scroller.clientHeight);
      const restoredScrollTop = Math.min(previousScrollTop, maxScrollTop);
      setScrollOffsetInstantly(scroller, restoredScrollTop, scroller.scrollLeft);
      // An in-flight fling keeps going, but neither end of it may point past
      // the content that now exists.
      if (scroller === elements.pageContent) {
        smoothPageScrollCurrent = restoredScrollTop;
        smoothPageScrollTarget = Math.min(smoothPageScrollTarget, maxScrollTop);
      }
    }
  }
  if (state.activeView === "cultivation") {
    updateHarvestButtonState();
  }
  if (state.activeView === "history") {
    observeHistoryTail();
  }
  finalizeRouteTransition();

  if (pageMarkupChanged && shouldResetScroll) {
    scrollViewportToTop({ behavior: "auto" });
    window.requestAnimationFrame(() => scrollViewportToTop({ behavior: "auto" }));
  }

  syncDashboardLiveSensorGraph();
}

// A rebuild of the irrigation region swaps in brand-new input nodes. When the
// caret is inside one of them -- which it is for every keystroke in a duration
// box -- the node it belongs to stops existing and the edit is lost. These two
// carry the selection across the swap by field identity, not by node.
function irrigationFieldSelector(dataset) {
  const parts = ["[data-irrigation-field]"];
  if (dataset.irrigationField) {
    parts[0] = `[data-irrigation-field="${CSS.escape(dataset.irrigationField)}"]`;
  }
  if (dataset.irrigationChannel) {
    parts.push(`[data-irrigation-channel="${CSS.escape(dataset.irrigationChannel)}"]`);
  }
  if (dataset.irrigationRow) {
    parts.push(`[data-irrigation-row="${CSS.escape(dataset.irrigationRow)}"]`);
  }
  return parts.join("");
}

function captureIrrigationFieldFocus() {
  const active = document.activeElement;
  if (!(active instanceof HTMLInputElement) || !active.dataset.irrigationField) {
    return null;
  }

  const snapshot = {
    selector: irrigationFieldSelector(active.dataset),
    value: active.value,
    start: null,
    end: null,
  };

  // selectionStart throws on a number input in some browsers; the value alone
  // is still worth restoring when it does.
  try {
    snapshot.start = active.selectionStart;
    snapshot.end = active.selectionEnd;
  } catch (error) {
    snapshot.start = null;
    snapshot.end = null;
  }

  return snapshot;
}

function restoreIrrigationFieldFocus(snapshot) {
  if (!snapshot) {
    return;
  }

  const next = document.querySelector(snapshot.selector);
  if (!(next instanceof HTMLInputElement)) {
    return;
  }

  // The freshly rendered node carries the committed value. What the person
  // typed is newer than that, so it wins until they leave the field.
  if (next.value !== snapshot.value) {
    next.value = snapshot.value;
  }

  next.focus({ preventScroll: true });
  if (snapshot.start !== null && snapshot.end !== null) {
    try {
      next.setSelectionRange(snapshot.start, snapshot.end);
    } catch (error) {
      // A number input that refuses a selection range is still focused, which
      // is the part that matters for continuing to type.
    }
  }
}

// How long Cancel or X parks a row's tank card before it asks again: the same
// wait as the greenhouse alert, so the two warnings come back on one rhythm.
// A function, not a constant, because GREENHOUSE_ALERT_RETURN_MS is declared
// further down the file.
function limeTankCardReturnMs() {
  return GREENHOUSE_ALERT_RETURN_MS;
}

let limeTankReturnTimer = 0;

// Deferrals are the time the card may ask again. A true left by an older page
// counts as "not deferred", so the card is never silenced for good.
function limeTankIsDeferred(key) {
  const until = Number(state.limeTankDeferred?.[key]);
  return Number.isFinite(until) && until > Date.now();
}

// Wakes the overlays when the soonest parked card is due, so it comes back on
// time rather than on whichever refresh happens next.
function scheduleLimeTankCardReturn() {
  if (limeTankReturnTimer) {
    window.clearTimeout(limeTankReturnTimer);
    limeTankReturnTimer = 0;
  }
  const now = Date.now();
  const due = Object.values(state.limeTankDeferred || {})
    .map(Number)
    .filter((until) => Number.isFinite(until) && until > now);
  if (!due.length) {
    return;
  }
  limeTankReturnTimer = window.setTimeout(() => {
    limeTankReturnTimer = 0;
    renderOverlays();
    scheduleLimeTankCardReturn();
  }, Math.min(...due) - now + 50);
}

// Forget "not now" for the rows given, or for every row. Used when the person
// comes back to Irrigation or picks a row there: both are the moment to ask
// again about a tank that is still unconfirmed.
function clearLimeTankDeferrals(rowKey = "") {
  if (!rowKey) {
    state.limeTankDeferred = {};
  } else {
    state.limeTankDeferred = Object.fromEntries(
      Object.entries(state.limeTankDeferred || {})
        .filter(([key]) => !key.startsWith(`${rowKey}:`)),
    );
  }
  scheduleLimeTankCardReturn();
}

// The row's lime line is held until its tank card is answered, or null when
// nothing is waiting. The card is per row: one row's answer never releases
// another's line.
// Manual and schedule rows are asked as soon as the pH leaves the crop range.
// Automatic only doses at critical, so it is asked then -- or while it is
// already correcting -- and not at warning. Matches lime_tank_ask_is_due() in
// main.py and the administrator shell.
function limeTankAskIsDue(row) {
  if (row?.mode !== "automatic") {
    return true;
  }
  if (row?.criticalNeeds?.limeSolution) {
    return true;
  }
  return Boolean(state.irrigationPage?.activeAutomaticRows?.limeSolution?.[row.key]);
}

function pendingLimeTankCheck(row) {
  const needed = limeTankSolutionNeeded(row);
  if (!needed || !limeTankAskIsDue(row)) {
    return null;
  }
  const key = limeTankConfirmationKey(row.key, needed.key, row.cultivationId);
  if (state.limeTankConfirmations?.[key]) {
    return null;
  }
  return { ...needed, confirmationKey: key, deferred: limeTankIsDeferred(key) };
}

// Lime runs in every mode -- automatic, scheduled and manual -- are held by
// the backend until the tank is confirmed, so the person has to be told which
// solution each row wants. The ask is raised whenever the page is drawn and a
// row is waiting on it, including straight after a cultivation is started,
// which is when a new row first needs it. One row at a time, the row picked on
// the Irrigation page first; the next row's card follows once this one is
// answered. Cancel parks a card for limeTankCardReturnMs(), and it asks again
// until the tank is confirmed or the pH is back in range.
function raisePendingLimeTankAdvisory() {
  if (state.controlAdvisory || !Array.isArray(state.irrigationPage?.rows)) {
    return false;
  }

  const selectedKey = state.irrigationPage.selectedRowKey;
  const waitingRows = state.irrigationPage.rows.filter((row) => {
    if (!row?.active) {
      return false;
    }
    const pending = pendingLimeTankCheck(row);
    return Boolean(pending && !pending.deferred);
  });
  if (!waitingRows.length) {
    return false;
  }
  const first = waitingRows.find((row) => row.key === selectedKey) || waitingRows[0];
  const solutionKey = pendingLimeTankCheck(first)?.key;
  // Every row waiting on the same solution is asked in one card, the way the
  // greenhouse alert names every affected row: one tank, one fill, one answer.
  // Rows that need the other solution get their own card after this one.
  const group = waitingRows.filter((row) => pendingLimeTankCheck(row)?.key === solutionKey);

  state.controlAdvisory = group.length > 1
    ? limeTankGroupAdvisory(group)
    : limeTankAdvisory(first, { kind: "lime-hold", mode: first.mode });
  return Boolean(state.controlAdvisory);
}

// Several rows, one solution. Answering it confirms the tank for each of them,
// and Cancel parks each of them, exactly as if each had its own card.
function limeTankGroupAdvisory(rows) {
  const advisories = rows
    .map((row) => limeTankAdvisory(row, { kind: "lime-hold", mode: row.mode }))
    .filter(Boolean);
  if (!advisories.length) {
    return null;
  }
  if (advisories.length === 1) {
    return advisories[0];
  }
  const first = advisories[0];
  const needed = limeTankSolutionNeeded(rows[0]);
  const activeCount = state.irrigationPage.rows.filter((row) => row.active).length;
  const rowsLabel = greenhouseAffectedRowsLabel({
    affectedRows: rows.map((row) => ({ label: row.label })),
    allRowsAffected: rows.length === activeCount,
  });
  const modes = [...new Set(rows.map((row) => row.mode))];
  const mode = modes.length === 1 && LIME_TANK_MODE_LABELS[modes[0]] ? modes[0] : "mixed";
  const condition = first.limeSolutionKey === "up" ? "too acidic" : "too alkaline";
  const readings = rows
    .map((row) => `${row.label} pH ${Math.round(Number.parseFloat(row.readings?.limeSolution) * 100) / 100}`)
    .join(", ");
  return {
    ...first,
    mode,
    rowKey: "",
    rowKeys: rows.map((row) => row.key),
    rowLabel: rowsLabel,
    confirmationKeys: advisories.map((advisory) => advisory.confirmationKey),
    eyebrow: `Lime Solution · ${LIME_TANK_MODE_LABELS[mode]}`,
    title: `${rowsLabel} need ${first.solutionLabel}`,
    message: `The soil in ${rowsLabel} is ${condition} (${readings}). `
      + `Fill the lime solution tank with ${first.solutionLabel}, which ${needed?.detail || "corrects it"}. `
      + "Every row shares this tank, so each of these rows receives whatever is in it. "
      + "Their lime lines stay off until you confirm.",
    // The title already names the rows; a tile only has room for the count.
    metrics: [
      { label: "Rows", value: `${rows.length} rows` },
      { label: "Tank needs", value: first.solutionLabel },
    ],
  };
}

// The keys a tank card answers: several for a card covering several rows.
function limeTankAdvisoryKeys(advisory) {
  if (Array.isArray(advisory?.confirmationKeys) && advisory.confirmationKeys.length) {
    return advisory.confirmationKeys;
  }
  return advisory?.confirmationKey ? [advisory.confirmationKey] : [];
}

function renderIrrigationPageUpdate({ animateMode = false } = {}) {
  if (state.activeView !== "irrigation") {
    renderPage();
    return false;
  }

  if (raisePendingLimeTankAdvisory()) {
    renderOverlays();
  }

  const region = document.querySelector("[data-irrigation-mode-region]");
  if (!(region instanceof HTMLElement)) {
    renderPage();
    return false;
  }

  syncIrrigationModeCards();

  const nextMarkup = irrigationModeContentTemplate();
  const nextMode = state.irrigationPage.mode;
  const shouldAnimate = animateMode && !prefersReducedMotion();

  // Rebuilding the region replaces every input node, so anything the caret is
  // sitting in is destroyed mid-edit. Remember which field was focused and
  // where the caret was, then put both back on the fresh node below.
  const focusSnapshot = captureIrrigationFieldFocus();

  if (!shouldAnimate) {
    region.classList.remove("irrigation-mode-region--leaving", "irrigation-mode-region--entering");
    region.classList.add("irrigation-mode-region--ready");
    region.dataset.irrigationMode = nextMode;
    region.innerHTML = nextMarkup;
    restoreIrrigationFieldFocus(focusSnapshot);
    return true;
  }

  // Swap the new mode in on this frame. Waiting out a leave animation first
  // delayed the pump controls themselves, so the fade now runs on content that
  // is already live instead of gating it.
  region.classList.remove("irrigation-mode-region--ready", "irrigation-mode-region--leaving");
  region.innerHTML = nextMarkup;
  restoreIrrigationFieldFocus(focusSnapshot);
  region.dataset.irrigationMode = nextMode;
  region.classList.add("irrigation-mode-region--entering");

  window.requestAnimationFrame(() => {
    region.classList.add("irrigation-mode-region--ready");
  });

  return true;
}

function syncIrrigationModeCards() {
  document.querySelectorAll('[data-action="set-irrigation-mode"]').forEach((button) => {
    if (!(button instanceof HTMLElement)) {
      return;
    }

    const active = button.dataset.mode === state.irrigationPage.mode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

let lastRenderedOverlays = [];

// Overlays carry live values -- the All IoT Device Rows modal is the whole
// dashboard grid, the sensor drawer is a live reading -- so a sensor tick
// changes their markup several times a minute. Rewriting overlayRoot.innerHTML
// for that threw away every open overlay's DOM: the modal flashed and its body
// snapped back to the top while the reader was scrolling it, and anything typed
// into a modal lost the caret. Only the overlay whose markup actually changed
// is replaced now, with the scroll offsets and the focused field carried
// across. Opening or closing an overlay still rebuilds -- that is a real change
// of what is on screen.
function captureOverlayScrollState(node) {
  const captured = [];

  if (node.scrollTop || node.scrollLeft) {
    captured.push({ path: [], top: node.scrollTop, left: node.scrollLeft });
  }

  node.querySelectorAll("*").forEach((child) => {
    if (!child.scrollTop && !child.scrollLeft) {
      return;
    }

    const path = overlayIndexPath(node, child);
    if (path) {
      captured.push({ path, top: child.scrollTop, left: child.scrollLeft });
    }
  });

  return captured;
}

function overlayIndexPath(root, node) {
  const path = [];
  let current = node;

  while (current && current !== root) {
    const parent = current.parentElement;
    if (!parent) {
      return null;
    }
    path.unshift(Array.prototype.indexOf.call(parent.children, current));
    current = parent;
  }

  return current === root ? path : null;
}

function restoreOverlayScrollState(node, captured) {
  captured.forEach(({ path, top, left }) => {
    let target = node;
    for (const index of path) {
      target = target?.children?.[index];
    }

    if (!(target instanceof HTMLElement)) {
      return;
    }

    setScrollOffsetInstantly(target, top, left);
    if (target.scrollTop !== top || target.scrollLeft !== left) {
      // A subtree inserted this tick can still measure as empty when the
      // offset is written, and the browser clamps it straight back to 0. One
      // more go on the frame it was actually laid out in lands on the real
      // height -- which is the difference between the All Rows modal keeping
      // the reader's place and snapping to the top on every sensor tick.
      window.requestAnimationFrame(() => setScrollOffsetInstantly(target, top, left));
    }
  });
}

// Every restore in this file is putting a position back, not scrolling the
// reader somewhere new. `.page-content`, `.modal__body`, `.drawer` and the All
// Rows body all carry `scroll-behavior: smooth !important`, so a plain
// scrollTop assignment starts an animation instead of moving the panel -- and
// the next render, a fraction of a second later, reads the position it is
// animating *through* (0) and puts the reader there for real. The offset has
// to land on the same frame, which means overriding that rule for the write.
// Reading the extent first also forces the layout the assignment depends on.
function setScrollOffsetInstantly(target, top, left) {
  const maxTop = Math.max(0, target.scrollHeight - target.clientHeight);
  const maxLeft = Math.max(0, target.scrollWidth - target.clientWidth);
  const previous = target.style.getPropertyValue("scroll-behavior");
  const priority = target.style.getPropertyPriority("scroll-behavior");

  target.style.setProperty("scroll-behavior", "auto", "important");
  target.scrollTop = Math.min(top, maxTop);
  target.scrollLeft = Math.min(Number.isFinite(left) ? left : target.scrollLeft, maxLeft);

  if (previous) {
    target.style.setProperty("scroll-behavior", previous, priority);
  } else {
    target.style.removeProperty("scroll-behavior");
  }
}

function replaceOverlayNodePreservingState(node, markup) {
  const fragment = markupFragment(markup);
  if (fragment.children.length !== 1) {
    return false;
  }

  const replacement = fragment.firstElementChild;
  if (node.isEqualNode(replacement)) {
    return true;
  }

  if (morphNode(node, replacement)) {
    return true;
  }

  const activeElement = document.activeElement;
  const ownsFocus = activeElement instanceof HTMLElement && node.contains(activeElement);
  const focusedId = ownsFocus && activeElement.id ? activeElement.id : "";
  const selectionStart = ownsFocus && isTextEntryElement(activeElement) ? activeElement.selectionStart : null;
  const selectionEnd = ownsFocus && isTextEntryElement(activeElement) ? activeElement.selectionEnd : null;
  const scrollState = captureOverlayScrollState(node);

  node.replaceWith(replacement);
  restoreOverlayScrollState(replacement, scrollState);

  if (focusedId) {
    const nextFocus = document.getElementById(focusedId);
    if (nextFocus instanceof HTMLElement) {
      nextFocus.focus({ preventScroll: true });
      if (selectionStart !== null && isTextEntryElement(nextFocus)) {
        try {
          nextFocus.setSelectionRange(selectionStart, selectionEnd);
        } catch (error) {
          // Not every input type exposes a selection range; focus is enough.
        }
      }
    }
  }

  return true;
}

function isTextEntryElement(element) {
  if (element instanceof HTMLTextAreaElement) {
    return true;
  }

  return element instanceof HTMLInputElement
    && ["text", "search", "url", "tel", "password", "email", ""].includes(element.type);
}

function applyOverlayRender(nextOverlays) {
  const root = elements.overlayRoot;
  const sameShape = nextOverlays.length === lastRenderedOverlays.length
    && nextOverlays.length === root.children.length
    && nextOverlays.every((overlay, index) => overlay.key === lastRenderedOverlays[index].key);

  let patched = sameShape;
  if (sameShape) {
    for (let index = 0; index < nextOverlays.length; index += 1) {
      if (nextOverlays[index].markup === lastRenderedOverlays[index].markup) {
        continue;
      }

      const node = root.children[index];
      if (!(node instanceof HTMLElement) || !replaceOverlayNodePreservingState(node, nextOverlays[index].markup)) {
        patched = false;
        break;
      }
    }
  }

  if (!patched) {
    root.innerHTML = nextOverlays.map((overlay) => overlay.markup).join("");
  }

  lastRenderedOverlays = nextOverlays;
}

// ------------------------------------------------------------- advisories
//
// Starting a line by hand, or forcing the fan or light on, stays allowed at
// any time. But when the live reading already sits inside the crop's target,
// the action spends water, nutrient, or power for nothing -- and on the
// solution lines an overshoot is far harder to walk back than a shortfall.
//
// So the control stops once and shows what the sensor reads against what the
// crop asked for. Cancel leaves everything exactly as it was; Start Anyway
// runs precisely what the button would have run on its own -- this never
// blocks an action, it only makes sure the numbers were seen first.
//
// Raised only for a start. Stopping is never questioned, and neither is a
// start the readings cannot judge: a sensor that is missing, powered off, or
// stale means there is no advice to give, so the control behaves as before.

const IRRIGATION_ADVISORY_UNITS = {
  water: "%",
  fertilizer: "mS/cm",
  // Blank on purpose: "Soil pH reads 6.5 pH" says it twice, and the metric
  // label in front of the number already names the scale.
  limeSolution: "",
};

const IRRIGATION_ADVISORY_COPY = {
  water: {
    metricLabel: "Soil moisture",
    withinTitle: "already has enough water",
    aboveTitle: "is already above its water target",
    withinReason:
      "Watering now pushes the row past its target and uses more water than the schedule expects.",
    aboveReason:
      "Adding more water now risks waterlogging the roots, and the row has no way to drain itself.",
  },
  fertilizer: {
    metricLabel: "Soil Nutrients",
    withinTitle: "already has enough fertilizer",
    aboveTitle: "is already above its nutrient target",
    withinReason:
      "Dosing now lifts the nutrient concentration past what this crop was set up for, and an excessive level is far harder to correct than a low one.",
    aboveReason:
      "Dosing now drives the concentration further above target, which burns roots long before the reading comes back down.",
  },
  limeSolution: {
    metricLabel: "Soil pH",
    withinTitle: "is already within its pH range",
    aboveTitle: "is already above its pH range",
    withinReason:
      "Dosing now pushes the soil further alkaline, and bringing pH back down takes much longer than raising it.",
    aboveReason:
      "Dosing now drives the soil further alkaline, locking out the nutrients the crop can still reach at this pH.",
  },
};

function formatAdvisoryReading(value, unit) {
  const numericValue = Number.parseFloat(value);
  if (!Number.isFinite(numericValue)) {
    return "--";
  }
  const rounded = Math.round(numericValue * 100) / 100;
  // "%" reads as part of the number; every other unit is a separate word.
  return unit === "%" ? `${rounded}%` : `${rounded}${unit ? ` ${unit}` : ""}`;
}

function formatAdvisoryRange(range, unit) {
  if (!range) {
    return "--";
  }
  const minimum = Number.parseFloat(range.min);
  const maximum = Number.parseFloat(range.max);
  if (!Number.isFinite(minimum) || !Number.isFinite(maximum)) {
    return "--";
  }
  const suffix = unit === "%" ? "%" : unit ? ` ${unit}` : "";
  return `${Math.round(minimum * 100) / 100} – ${Math.round(maximum * 100) / 100}${suffix}`;
}

// The lime line is one tank shared by every row, and it holds either a pH Up
// or a pH Down solution -- never both. Which one is needed depends on the
// reading: below the crop's range the soil has to come up, above it has to
// come down. Nothing in software can tell which solution is physically in the
// tank, so before a lime run the person is asked to confirm they have put the
// right one in, and the run waits for that answer.
//
// Only a reading outside the range raises this. A row sitting inside its pH
// range needs no correction, so there is nothing to confirm and no card.
const LIME_TANK_SOLUTIONS = {
  up: {
    key: "up",
    label: "Soil pH Up",
    // Said plainly, because this is an instruction to go and do something in
    // the greenhouse rather than a description of a chemical. "Raises the pH"
    // is what the solution does; "too acidic" is what the row is.
    detail: "raises the pH of soil that has turned too acidic",
  },
  down: {
    key: "down",
    label: "Soil pH Down",
    detail: "lowers the pH of soil that has turned too alkaline",
  },
};

function limeTankSolutionNeeded(row) {
  const range = row?.thresholds?.limeSolution;
  const reading = Number.parseFloat(row?.readings?.limeSolution);
  if (!range || !row?.sensorAvailable?.limeSolution || !Number.isFinite(reading)) {
    return null;
  }

  const minimum = Number.parseFloat(range.min);
  const maximum = Number.parseFloat(range.max);
  if (Number.isFinite(minimum) && reading < minimum) {
    return { ...LIME_TANK_SOLUTIONS.up, reading, range };
  }
  if (Number.isFinite(maximum) && reading > maximum) {
    return { ...LIME_TANK_SOLUTIONS.down, reading, range };
  }
  // Inside the range: nothing to correct, so nothing to ask about.
  return null;
}

// The card is per row and per direction. Confirming pH Up for row 1 says
// nothing about row 2, or about row 1 once it needs pH Down instead -- that is
// a different solution in the tank and has to be checked again.
//
// The cultivation is part of the key for the same reason: an answer given for
// the last crop must not switch the line on for the next one. Matches
// lime_tank_acknowledgement_key() in main.py, which holds the same gate.
function limeTankConfirmationKey(rowKey, solutionKey, cultivationId = "") {
  const cultivation = String(cultivationId || "").trim();
  return cultivation
    ? `${rowKey}:${cultivation}:${solutionKey}`
    : `${rowKey}:${solutionKey}`;
}

const LIME_TANK_MODE_LABELS = {
  automatic: "Automatic irrigation",
  schedule: "Scheduled irrigation",
  manual: "Manual irrigation",
  mixed: "Mixed modes",
};

// What happens the moment the second card is confirmed, in the words of the
// mode the row is in.
const LIME_TANK_MODE_OUTCOME = {
  automatic: "Automatic irrigation will start the line on its next check.",
  schedule: "The line will run at its next scheduled time.",
  manual: "The line will start as soon as you confirm.",
  mixed: "Each row's line then runs by its own mode.",
};

function limeTankAdvisory(row, { kind = "irrigation", mode = "manual" } = {}) {
  const needed = limeTankSolutionNeeded(row);
  if (!needed) {
    return null;
  }

  const confirmationKey = limeTankConfirmationKey(row.key, needed.key, row.cultivationId);
  if (state.limeTankConfirmations?.[confirmationKey]) {
    return null;
  }
  const modeKey = LIME_TANK_MODE_LABELS[mode] ? mode : "manual";

  const channel = irrigationChannelMeta("limeSolution");
  const reading = Math.round(needed.reading * 100) / 100;
  const minimum = Math.round(Number.parseFloat(needed.range.min) * 100) / 100;
  const maximum = Math.round(Number.parseFloat(needed.range.max) * 100) / 100;
  const rangeText = `${minimum} – ${maximum}`;
  // Which side of the range the row fell off, in the operator's words. The
  // reading is the evidence; "too acidic" is the diagnosis they act on.
  const condition = needed.key === "up" ? "too acidic" : "too alkaline";
  const limit = needed.key === "up" ? minimum : maximum;
  const boundary = needed.key === "up" ? "minimum" : "maximum";

  return {
    kind,
    mode: modeKey,
    step: "check",
    rowKey: row.key,
    rowLabel: row.label,
    channelKey: "limeSolution",
    limeSolutionKey: needed.key,
    solutionLabel: needed.label,
    confirmationKey,
    icon: channel.icon,
    eyebrow: `Lime Solution · ${LIME_TANK_MODE_LABELS[modeKey]}`,
    // Names the row first. The tank is shared but the pumps are not, so this
    // is one row's problem and the title has to say which one -- an operator
    // reading "change the tank" with no row named has no idea where to look.
    title: `${row.label} needs ${needed.label}`,
    message: `The soil in ${row.label} is ${condition}. It reads pH ${reading}, `
      + `${needed.key === "up" ? "below" : "above"} the ${boundary} of ${limit} `
      + `set${row.crop ? ` for ${row.crop}` : " for this crop"}. `
      + `Fill the lime solution tank with ${needed.label}, which ${needed.detail}. `
      + `Every row shares this tank, so this row receives whatever is in it. `
      + `The lime line for ${row.label} stays off until you confirm.`,
    metrics: [
      { label: "Soil pH now", value: `${reading}` },
      { label: "Target range", value: rangeText },
      { label: "Tank needs", value: needed.label },
    ],
    confirmLabel: "Continue",
    confirmIcon: "check-circle",
    cancelLabel: "Cancel",
  };
}

// The second card: the same row and solution, asked as a yes or no. Only
// Confirm here releases the line.
function limeTankConfirmStep(advisory) {
  const modeKey = LIME_TANK_MODE_OUTCOME[advisory.mode] ? advisory.mode : "manual";
  // A manual row asked without a Start press starts nothing on Confirm; it only
  // lets the Start button work.
  const outcome = advisory.kind === "lime-hold" && modeKey === "manual"
    ? "Lime Solution can then be started with its Start button."
    : LIME_TANK_MODE_OUTCOME[modeKey];
  return {
    ...advisory,
    step: "confirm",
    eyebrow: `Confirm · ${advisory.rowLabel}`,
    title: "Are you sure?",
    message: `Confirm that the lime solution tank now holds ${advisory.solutionLabel} `
      + `for ${advisory.rowLabel}. ${outcome} `
      + `Dosing the wrong solution moves the soil pH the wrong way and cannot be undone.`,
    metrics: [
      {
        label: "Row",
        value: advisory.rowKeys?.length > 1 ? `${advisory.rowKeys.length} rows` : advisory.rowLabel,
      },
      { label: "Mode", value: modeKey === "mixed" ? "Mixed" : LIME_TANK_MODE_LABELS[modeKey].replace(" irrigation", "") },
      { label: "Tank holds", value: advisory.solutionLabel },
    ],
    confirmLabel: "Confirm",
    confirmIcon: advisory.icon,
    cancelLabel: "Cancel",
  };
}

function manualIrrigationAdvisory(row, channelKey) {
  const copy = IRRIGATION_ADVISORY_COPY[channelKey];
  const range = row?.thresholds?.[channelKey];
  const reading = Number.parseFloat(row?.readings?.[channelKey]);
  // `sensorAvailable` already folds in the powered-off and stale cases, and
  // `needs` is the backend's own "below the crop minimum" verdict -- the same
  // one automatic irrigation acts on. Reusing it keeps the warning and the
  // controller from ever disagreeing about what "enough" means.
  if (!copy || !range || !row?.sensorAvailable?.[channelKey] || row?.needs?.[channelKey]) {
    return null;
  }
  if (!Number.isFinite(reading)) {
    return null;
  }

  const channel = irrigationChannelMeta(channelKey);
  const unit = IRRIGATION_ADVISORY_UNITS[channelKey] || "";
  const above = reading > Number.parseFloat(range.max);
  const cropSuffix = row.crop ? ` set for ${row.crop}` : " set for this row";

  return {
    kind: "irrigation",
    rowKey: row.key,
    channelKey,
    icon: channel.icon,
    eyebrow: `Manual ${channel.label.toLowerCase()}`,
    title: `${row.label} ${above ? copy.aboveTitle : copy.withinTitle}`,
    message: `${copy.metricLabel} reads ${formatAdvisoryReading(reading, unit)}, ${
      above ? "above" : "inside"
    } the ${formatAdvisoryRange(range, unit)} range${cropSuffix}. ${
      above ? copy.aboveReason : copy.withinReason
    }`,
    metrics: [
      { label: "Reading now", value: formatAdvisoryReading(reading, unit) },
      { label: "Crop target", value: formatAdvisoryRange(range, unit) },
    ],
    // Water and fertilizer start on any reading: the card shows the numbers
    // and Start Anyway runs the duration that was typed. Lime is different --
    // with the pH in range there is no pH Up or pH Down to confirm in the
    // tank, and the backend holds an unconfirmed lime run, so that card still
    // offers nothing to start.
    ...(channelKey === "limeSolution"
      ? {
        blocked: true,
        footnote: "Lime Solution only runs when the soil pH is outside the crop range and the tank is confirmed.",
        cancelLabel: "OK",
      }
      : {
        footnote: "Start Anyway runs the full manual duration.",
        confirmLabel: "Start Anyway",
        cancelLabel: "Cancel",
      }),
  };
}

// Lime with no pH to judge by: nothing says which solution the row needs, so
// nothing can be confirmed, and the backend holds the line. Said here, rather
// than letting the button look as if it started.
function limeUnreadableAdvisory(row) {
  const channel = irrigationChannelMeta("limeSolution");
  return {
    kind: "irrigation",
    rowKey: row.key,
    channelKey: "limeSolution",
    icon: channel.icon,
    eyebrow: "Manual lime solution",
    title: `${row.label} has no pH reading`,
    message: `The soil pH sensor for ${row.label} is off, not reporting, or out of the soil, `
      + "so there is no way to tell whether the row needs Soil pH Up or Soil pH Down. "
      + "Lime Solution stays off until the pH can be read.",
    metrics: [],
    blocked: true,
    cancelLabel: "OK",
  };
}

// The safety verdict the backend reached for this actuator, or null when it
// has not said anything about it. The backend owns this decision: it is what
// actually switches the relay off, and a second opinion computed here could
// disagree with the machine that acts.
function actuatorSafety(actuatorKey) {
  const safety = SENSOR_AUTOMATION.safety || {};
  const entry = safety[actuatorKey];
  return entry && typeof entry === "object" ? entry : null;
}

// Near the crops' limit, or already past it. Either way the press goes
// through: this names the reading and the limit so the decision is made with
// the numbers in view, rather than taking the control away. "cut" is the
// stronger of the two and says plainly that the limit is already crossed.
function actuatorSafetyWarning(actuatorKey) {
  const entry = actuatorSafety(actuatorKey);
  if (!entry || (entry.state !== "warning" && entry.state !== "cut")) {
    return null;
  }
  const control = SENSOR_ACTUATORS.find((item) => item.key === actuatorKey);
  const unit = String(entry.unit || "");
  const pastLimit = entry.state === "cut";
  return {
    kind: "actuator",
    actuatorKey,
    icon: control?.icon || "zap",
    eyebrow: String(entry.actuator || control?.label || "Control check"),
    title: pastLimit
      ? "This is already past what your crops can take"
      : "This will stop on its own shortly",
    message: pastLimit
      ? `${entry.message || ""} Turning it on now works against the range you set for the crop.`.trim()
      : `${entry.message || ""} It will switch back to Automatic by itself once that limit is reached.`.trim(),
    metrics: [
      { label: "Reading now", value: formatAdvisoryReading(entry.reading, unit) },
      {
        label: entry.bound === "floor" ? "Crop minimum" : "Crop limit",
        value: formatAdvisoryReading(entry.limit, unit),
      },
    ],
    confirmLabel: "Turn On Anyway",
  };
}

function actuatorAdvisory(actuatorKey) {
  const control = SENSOR_ACTUATORS.find((item) => item.key === actuatorKey);
  if (!control) {
    return null;
  }

  if (actuatorKey === "fan") {
    const fan = SENSOR_AUTOMATION.fan || {};
    const humidity = Number.parseFloat(fan.humidity);
    const ceiling = Number.parseFloat(fan.thresholdPercent);
    // Nothing to advise while the board is quiet: a stale reading is not
    // evidence that the air is dry.
    if (!fan.readingFresh || !Number.isFinite(humidity) || !Number.isFinite(ceiling)) {
      return null;
    }
    if (humidity > ceiling) {
      return null;
    }
    // The fan answers to heat as well as to moisture, and this card only knew
    // about moisture. A hot but dry house is exactly the case where the fan is
    // wanted most, and the advisory would have offered to switch it off while
    // quoting a humidity reading that was perfectly fine.
    if (fan.tooHot === true) {
      return null;
    }
    return {
      kind: "actuator",
      actuatorKey,
      icon: control.icon,
      eyebrow: "Exhaust fan",
      title: "The fan is not needed yet",
      message: `Humidity reads ${formatAdvisoryReading(humidity, "%")}, at or below the ${formatAdvisoryReading(ceiling, "%")} ceiling${
        fan.fromCropParameters ? " set for the crop" : ""
      }. Running the fan now dries the air further and spends power the crop gets nothing back from.`,
      metrics: [
        { label: "Humidity now", value: formatAdvisoryReading(humidity, "%") },
        { label: "Fan runs above", value: formatAdvisoryReading(ceiling, "%") },
      ],
      confirmLabel: "Turn On Anyway",
    };
  }

  // Only fan and grow light have automation behind them. Without this guard
  // the function fell through to the temperature branch for every other key,
  // so a misting press would have raised the lamp's warning.
  if (actuatorKey !== "light") {
    return null;
  }

  const light = SENSOR_AUTOMATION.light || {};
  const temperature = Number.parseFloat(light.temperature);
  const floor = Number.parseFloat(light.thresholdC);
  // The light sensor reports dark/not-dark rather than a lux level: the
  // threshold is a trimpot on the HW-072 board, so there is no number to show
  // here and none to compare against. Checked against true explicitly because
  // the field is null when there is no reading at all, and null must not read
  // as "not dark".
  const isDark = light.dark === true;

  // Dark, but the lamp has run its hours for this dark spell, so Automatic
  // has stood the dark half down until the sensor sees daylight again. Saying
  // so keeps a dark house with the lamp off from reading as a fault. A cold
  // house is not this case: the lamp heats it whatever the count says.
  if (light.lightFresh && isDark && light.darkLimitReached === true && light.tooCold !== true) {
    const limit = Number.parseFloat(light.darkLimitHours);
    const used = Number.parseFloat(light.lampHoursThisDark);
    const hours = (value) => `${Math.round(value * 10) / 10} h`;
    return {
      kind: "actuator",
      actuatorKey,
      icon: control.icon,
      eyebrow: "Grow light",
      title: "The grow light has run its hours for now",
      message: `The grow light has already run ${
        Number.isFinite(limit) ? `${Math.round(limit * 10) / 10} hours` : "its hours"
      } since it got dark. Lighting the crops longer shortens their night, and a long day can make leafy crops bolt. It can run again after the light sensor sees daylight.`,
      metrics: [
        ...(Number.isFinite(used) ? [{ label: "Lamp this dark", value: hours(used) }] : []),
        ...(Number.isFinite(limit) ? [{ label: "Limit", value: hours(limit) }] : []),
      ],
      confirmLabel: "Turn On Anyway",
    };
  }

  // The lamp answers to two things now. If the house is dim, running it is the
  // whole point of a grow light, so there is nothing to advise against --
  // whatever the temperature is doing.
  if (light.lightFresh && isDark) {
    return null;
  }

  // Full sun on the crop. The automatic rule stands the heating half down here,
  // so a cold house in real daylight keeps the lamp off -- and without this
  // branch the cold-house bail-out below would leave the card silent about the
  // one case an operator is most likely to question.
  if (light.daylight) {
    return {
      kind: "actuator",
      actuatorKey,
      icon: control.icon,
      eyebrow: "Grow light",
      title: "The sun is already doing this",
      message: `The light sensor reads daylight, so the crop has more light than the lamp can add${
        Number.isFinite(temperature) && Number.isFinite(floor) && temperature < floor
          ? ", and sunlight this strong is already warming the house"
          : ""
      }. Running it now mostly adds heat.`,
      metrics: [
        { label: "Light now", value: "Daylight" },
        ...(Number.isFinite(temperature)
          ? [{ label: "Greenhouse now", value: formatAdvisoryReading(temperature, "°C") }]
          : []),
      ],
      confirmLabel: "Turn On Anyway",
    };
  }

  if (!light.readingFresh || !Number.isFinite(temperature) || !Number.isFinite(floor)) {
    return null;
  }
  if (temperature < floor) {
    return null;
  }
  return {
    kind: "actuator",
    actuatorKey,
    icon: control.icon,
    eyebrow: "Grow light",
    title: "There is enough light and warmth already",
    message: `The greenhouse reads ${formatAdvisoryReading(temperature, "\u00B0C")}, at or above the ${formatAdvisoryReading(floor, "\u00B0C")} floor${
      light.fromCropParameters ? " set for the crop" : ""
    }, and the house is not dim enough to need the lamp. Running it now pushes the temperature past what the crop asked for.`,
    metrics: [
      { label: "Greenhouse now", value: formatAdvisoryReading(temperature, "\u00B0C") },
      { label: "Lamp runs below", value: formatAdvisoryReading(floor, "\u00B0C") },
      ...(light.lightFresh && light.dark !== null && light.dark !== undefined
        ? [{ label: "Light now", value: isDark ? "Dim" : "Daylight" }]
        : []),
    ],
    confirmLabel: "Turn On Anyway",
  };
}

// The alert nothing in the greenhouse can act on itself. The exhaust fan pulls
// damp air out and the lamp only adds heat, so neither can bring the
// temperature down on a hot day: once the air is past the crop's limit the
// remedy is a person opening the house -- there is no relay to send it to.
//
// A dialog in the middle of the screen rather than a banner at the top of one
// page: a banner is easy to scroll past, and this is asking someone to walk
// over and open the greenhouse. The X buys ten minutes' quiet -- see
// GREENHOUSE_ALERT_RETURN_MS -- and the dialog comes back while the reading is
// still over the limit. Once the air is back inside the crop's range it closes
// itself and stays closed.
//
// Ten minutes, not one: at a minute the dialog returned while someone was still
// working the controls underneath it, which reads as the page fighting back. It
// also takes a person longer than a minute to walk to the greenhouse and open
// it, so a shorter wait could only ever repeat a request already being acted on.
function greenhouseAffectedRowsLabel(greenhouse) {
  const labels = (Array.isArray(greenhouse?.affectedRows) ? greenhouse.affectedRows : [])
    .map((row) => String(row?.label || "").trim())
    .filter(Boolean);
  if (greenhouse?.allRowsAffected || !labels.length) {
    return "All Rows";
  }
  if (labels.length === 1) {
    return labels[0];
  }
  if (labels.length === 2) {
    return `${labels[0]} and ${labels[1]}`;
  }
  return `${labels.slice(0, -1).join(", ")}, and ${labels.at(-1)}`;
}

function greenhouseVentAlert() {
  const greenhouse = SENSOR_AUTOMATION.greenhouse || {};
  if (!greenhouse.open || !greenhouse.readingFresh) {
    return null;
  }
  const reason = String(greenhouse.reason || "");
  const humidity = formatAdvisoryReading(greenhouse.humidity, "%");
  const humidityLimit = formatAdvisoryReading(greenhouse.humidityCeiling, "%");
  const temperature = formatAdvisoryReading(greenhouse.temperature, "\u00B0C");
  const temperatureLimit = formatAdvisoryReading(greenhouse.temperatureCeiling, "\u00B0C");
  const affectedRows = greenhouseAffectedRowsLabel(greenhouse);
  const affectedRowsVerb = greenhouse.allRowsAffected || greenhouse.affectedRows?.length > 1 ? "are" : "is";
  const affectedRowsMetric = { label: "Affected Rows", value: affectedRows, wide: true };

  if (reason === "both") {
    return {
      title: "Open the Greenhouse",
      message: `${affectedRows} ${affectedRowsVerb} affected. Humidity is ${humidity}, above the ${humidityLimit} limit, and the temperature is ${temperature}, above the ${temperatureLimit} limit. The shared exhaust fan is already running for every affected row and is pulling the damp air out, but it cannot bring the temperature down on its own. Please open the greenhouse to let the hot air out.`,
      metrics: [
        affectedRowsMetric,
        { label: "Humidity", value: `${humidity} / ${humidityLimit}` },
        { label: "Temperature", value: `${temperature} / ${temperatureLimit}` },
      ],
    };
  }
  if (reason === "temperature") {
    return {
      title: "Open the Greenhouse",
      message: `${affectedRows} ${affectedRowsVerb} affected. The temperature is ${temperature}, above the ${temperatureLimit} limit. Nothing inside can cool the greenhouse: the exhaust fan answers to humidity, not heat, and the grow light only adds more. Please open the greenhouse to let the heat out.`,
      metrics: [affectedRowsMetric, { label: "Temperature", value: `${temperature} / ${temperatureLimit}` }],
    };
  }
  return {
    title: "Open the Greenhouse",
    message: `${affectedRows} ${affectedRowsVerb} affected. Humidity is ${humidity}, above the ${humidityLimit} limit. The shared exhaust fan is already running for every affected row and remains needed until every row is back within its humidity limit. Opening the greenhouse clears the damp air faster. Please open it now.`,
    metrics: [affectedRowsMetric, { label: "Humidity", value: `${humidity} / ${humidityLimit}` }],
  };
}

// How long the X buys. This dialog is the only thing telling anyone the house
// needs opening, so dismissing it pauses the alert rather than ending it -- but
// a minute, not a second: long enough to walk over and open the greenhouse, and
// short enough that forgetting is not an option. Nothing repeats once the
// reading is back to normal.
const GREENHOUSE_ALERT_RETURN_MS = 600000;
let greenhouseAlertSuppressedUntil = 0;
let greenhouseAlertReturnTimer = 0;

function clearGreenhouseAlertReturnTimer() {
  if (greenhouseAlertReturnTimer) {
    window.clearTimeout(greenhouseAlertReturnTimer);
    greenhouseAlertReturnTimer = 0;
  }
}

// The alert to show right now, or null. Reads the dismissal as well as the
// reading. A dismissal runs its full ten minutes even if the air dips back
// inside the range meanwhile: with the fan and lamp's effect on the cards the
// reading can cross the line and back within minutes, and forgetting the X at
// every dip brought the dialog straight back instead of after its timer.
function activeGreenhouseVentAlert() {
  const alert = greenhouseVentAlert();
  if (!alert) {
    return null;
  }
  return Date.now() >= greenhouseAlertSuppressedUntil ? alert : null;
}

function dismissGreenhouseVentAlert() {
  greenhouseAlertSuppressedUntil = Date.now() + GREENHOUSE_ALERT_RETURN_MS;
  clearGreenhouseAlertReturnTimer();
  // Scheduled here rather than left to the next sensor refresh: that refresh
  // runs on its own cadence and would bring the dialog back early or late.
  greenhouseAlertReturnTimer = window.setTimeout(() => {
    greenhouseAlertReturnTimer = 0;
    renderOverlays();
  }, GREENHOUSE_ALERT_RETURN_MS);
  renderOverlays();
}

function greenhouseVentAlertModalTemplate() {
  const alert = activeGreenhouseVentAlert();
  if (!alert) {
    return "";
  }
  return `
    <div class="overlay overlay--center overlay--dialog overlay--passthrough">
      <div
        class="modal modal--sm greenhouse-alert-modal"
        role="alertdialog"
        aria-modal="false"
        aria-labelledby="greenhouse-alert-title"
        aria-describedby="greenhouse-alert-copy"
      >
        <div class="modal__header greenhouse-alert-modal__header">
          <button
            class="icon-button greenhouse-alert-modal__close"
            type="button"
            data-action="close-greenhouse-alert"
            aria-label="Close"
          >
            ${icon("close")}
          </button>
        </div>
        <div class="modal__body greenhouse-alert-modal__body">
          <span class="greenhouse-alert__icon" aria-hidden="true">${icon("alert-triangle")}</span>
          <div class="greenhouse-alert__copy">
            <p class="greenhouse-alert-modal__eyebrow">Greenhouse Alert</p>
            <h3 class="section-title greenhouse-alert__title" id="greenhouse-alert-title">${escapeHtml(alert.title)}</h3>
            <p class="section-copy greenhouse-alert__text" id="greenhouse-alert-copy">${escapeHtml(alert.message)}</p>
          </div>
          <dl class="greenhouse-alert__metrics">
            ${alert.metrics.map((metric) => `
              <div class="greenhouse-alert__metric ${metric.wide ? "greenhouse-alert__metric--wide" : ""}">
                <dt>${escapeHtml(metric.label)}</dt>
                <dd>${escapeHtml(metric.value)}</dd>
              </div>
            `).join("")}
          </dl>
        </div>
      </div>
    </div>
  `;
}

function controlAdvisoryModalTemplate() {
  const advisory = state.controlAdvisory;
  if (!advisory) {
    return "";
  }

  const metrics = Array.isArray(advisory.metrics) ? advisory.metrics : [];
  // The tank card raised on its own keeps returning while a row waits, like
  // the greenhouse alert, so like it it lets clicks through to the page: a
  // blocking card that comes back every few minutes leaves the farm usable
  // only between cards. A card answering a press still blocks.
  const passthrough = advisory.kind === "lime-hold";
  return `
    <div class="overlay overlay--center overlay--dialog${passthrough ? " overlay--passthrough" : ""}">
      <div
        class="modal modal--sm control-advisory-modal"
        role="alertdialog"
        aria-modal="${passthrough ? "false" : "true"}"
        aria-labelledby="control-advisory-title"
        aria-describedby="control-advisory-copy"
      >
        <div class="modal__header control-advisory-modal__header">
          <button
            class="icon-button control-advisory-modal__close"
            type="button"
            data-action="dismiss-control-advisory"
            aria-label="Cancel"
          >
            ${icon("close")}
          </button>
        </div>
        <div class="modal__body control-advisory-modal__body">
          <span class="control-advisory-modal__icon" aria-hidden="true">${icon("alert-triangle")}</span>
          <div class="control-advisory-modal__copy">
            <p class="control-advisory-modal__eyebrow">${escapeHtml(advisory.eyebrow || "Control check")}</p>
            <h3 class="section-title control-advisory-modal__title" id="control-advisory-title">
              ${escapeHtml(advisory.title || "")}
            </h3>
            <p class="section-copy control-advisory-modal__text" id="control-advisory-copy">
              ${escapeHtml(advisory.message || "")}${advisory.footnote ? ` ${escapeHtml(advisory.footnote)}` : ""}
            </p>
          </div>
          ${metrics.length ? `
            <dl class="control-advisory-modal__metrics">
              ${metrics.map((metric) => `
                <div class="control-advisory-modal__metric">
                  <dt>${escapeHtml(metric.label)}</dt>
                  <dd>${escapeHtml(metric.value)}</dd>
                </div>
              `).join("")}
            </dl>
          ` : ""}
          <div class="modal__actions control-advisory-modal__actions">
            ${advisory.blocked ? `
              <button class="button button--primary control-advisory-modal__confirm" type="button" data-action="dismiss-control-advisory">
                ${escapeHtml(advisory.cancelLabel || "OK")}
              </button>
            ` : `
              ${advisory.cancelLabel ? `
                <button class="button button--secondary control-advisory-modal__cancel" type="button" data-action="dismiss-control-advisory">
                  ${escapeHtml(advisory.cancelLabel)}
                </button>
              ` : ""}
              <button class="button button--primary control-advisory-modal__confirm" type="button" data-action="confirm-control-advisory">
                ${icon(advisory.confirmIcon || advisory.icon || "zap")}
                ${escapeHtml(advisory.confirmLabel || "Start Anyway")}
              </button>
            `}
          </div>
        </div>
      </div>
    </div>
  `;
}

function startManualIrrigationRun(rowKey, channelKey) {
  const row = state.irrigationPage.rows.find((item) => item.key === rowKey);
  if (!row?.active || row.mode !== "manual" || !row.channels?.[channelKey]) {
    return;
  }
  const activeRows = normalizeIrrigationChannelRowMap(state.irrigationPage.activeManualRows);
  activeRows[channelKey] = { ...(activeRows[channelKey] || {}), [rowKey]: true };
  markIrrigationManualLineChange(channelKey, rowKey, true);
  applyManualIrrigationRows(activeRows);
  void saveIrrigationStateWithFeedback({
    successMessage: `${irrigationChannelMeta(channelKey).label} started for ${row.label}.`,
  });
}

function applyManualIrrigationRows(activeRows) {
  state.irrigationPage.activeManualRows = activeRows;
  state.irrigationPage.activeManualLines = irrigationLinesFromChannelRows(activeRows);
  state.irrigationPage.activeManualLine = firstActiveIrrigationLine(state.irrigationPage.activeManualLines);
  renderIrrigationPageUpdate();
}

// A timed actuator (misting) does not turn On without a run duration typed in.
// Returns true when the press may go ahead.
function requireActuatorRunDuration(actuatorKey, nextValue) {
  const control = SENSOR_ACTUATORS.find((item) => item.key === actuatorKey);
  if (!control?.timed || nextValue !== "on" || actuatorRunDuration(actuatorKey)) {
    return true;
  }
  pushNotification(
    "warning",
    `Enter a run duration of ${ACTUATOR_MIN_DURATION_SECONDS}-${ACTUATOR_MAX_DURATION_SECONDS} seconds before turning ${control.label} on.`,
  );
  const input = document.querySelector(`[data-actuator-duration="${actuatorKey}"]`);
  if (input instanceof HTMLElement) {
    input.focus();
  }
  return false;
}

function applyActuatorMode(actuatorKey, nextValue) {
  if (!requireActuatorRunDuration(actuatorKey, nextValue)) {
    return;
  }
  const previousValue = state.sensorsPage.actuatorMode[actuatorKey] || "automatic";
  if (previousValue === nextValue) {
    return;
  }
  state.sensorsPage.actuatorMode[actuatorKey] = nextValue;
  writeSensorControlCache(state.sensorsPage);
  if (!updateActuatorCard(actuatorKey)) {
    console.warn(`Actuator control card was not found: ${actuatorKey}`);
  }
  runSensorControlRequest("actuatorMode", actuatorKey, nextValue, {
    confirmedValue: previousValue,
    onRollback: (confirmedValue) => {
      state.sensorsPage.actuatorMode[actuatorKey] = confirmedValue;
      writeSensorControlCache(state.sensorsPage);
      if (!updateActuatorCard(actuatorKey)) {
        console.warn(`Actuator control card was not found during rollback: ${actuatorKey}`);
      }
      const controlLabel = SENSOR_ACTUATORS.find((item) => item.key === actuatorKey)?.label || "control";
      // Say what actually stopped it. "It was reverted" alone left an operator
      // staring at a control that had snapped back with no reason given, and
      // no way to tell a refusal from a bad connection.
      const reason = extractRequestMessage(lastSensorControlError, "");
      pushNotification(
        "warning",
        reason
          ? `Could not save the ${controlLabel} change: ${reason}`
          : `Could not save the ${controlLabel} change. Check the connection and try again.`,
      );
      renderOverlays();
    },
  });
}

function renderOverlays() {
  if (!state.isAuthenticated) {
    document.body.classList.remove("is-dashboard-rows-open");
    if (lastRenderedOverlays.length) {
      elements.overlayRoot.innerHTML = "";
      lastRenderedOverlays = [];
    }
    return;
  }

  document.body.classList.toggle("is-dashboard-rows-open", state.dashboardAllRowsOpen);

  // A row that has just started a cultivation may already be waiting on its
  // tank check; the card has to reach the person wherever they are.
  raisePendingLimeTankAdvisory();

  const overlays = [];
  const selectedSensor = getSelectedSensor();

  if (state.settingsMenuOpen) {
    overlays.push({ key: "settings-menu", markup: settingsMenuTemplate() });
  }

  if (state.settingsOpen) {
    overlays.push({ key: "settings-modal", markup: settingsModalTemplate() });
  }

  if (state.settingsOpen && state.passwordChangeOtpRequested) {
    overlays.push({ key: "password-change-otp-modal", markup: passwordChangeOtpModalTemplate() });
  }

  if (state.dashboardAllRowsOpen) {
    overlays.push({ key: "dashboard-all-rows-modal", markup: dashboardAllRowsModalTemplate() });
  }

  if (state.activeView === "cultivation" && state.cultivation.cropType && state.cultivation.setupOpen) {
    overlays.push({ key: "cultivation-setup-modal", markup: cultivationSetupModalTemplate() });
  }

  if (state.activeView === "cultivation" && state.cultivation.cropType && state.cultivation.setupOpen && state.cultivation.parameterPreviewMode) {
    overlays.push({ key: "cultivation-parameter-preview-modal", markup: cultivationParameterPreviewModalTemplate() });
  }

  if (selectedSensor && state.sensorDraft) {
    overlays.push({ key: "sensor-drawer", markup: sensorDrawerTemplate(selectedSensor) });
  }

  if (state.notificationsOpen) {
    overlays.push({ key: "notification-drawer", markup: notificationDrawerTemplate() });
  }

  if (state.deleteScheduleConfirmOpen) {
    overlays.push({ key: "delete-schedule-confirm-modal", markup: deleteScheduleConfirmModalTemplate() });
  }

  if (state.logoutConfirmOpen) {
    overlays.push({ key: "logout-confirm-modal", markup: logoutConfirmModalTemplate() });
  }

  if (state.controlAdvisory) {
    overlays.push({ key: "control-advisory-modal", markup: controlAdvisoryModalTemplate() });
  }

  if (state.cultivationParametersId) {
    overlays.push({
      key: "cultivation-parameters-modal",
      markup: cultivationParametersModalTemplate(),
    });
  }

  // Last, so it sits over whatever else is open: the greenhouse being past the
  // crop's limit outranks anything a person happens to be doing in here, and
  // the template returns "" whenever the reading is fine or the X is still
  // holding it back.
  overlays.push({ key: "greenhouse-alert-modal", markup: greenhouseVentAlertModalTemplate() });

  applyOverlayRender(overlays.filter((overlay) => overlay.markup.trim()));

  if (state.settingsOpen) {
    updateProfilePreview();
    updateProfileNameValidationUI();
    updateSettingsButtonStates();
    // Change Password lives in this overlay, and only the Add New User modal
    // below was having its toggles synced -- so the eye kept whatever state
    // the markup was built with instead of the field's current one.
    syncPasswordToggleButtons(elements.overlayRoot || document);
  }

  if (state.activeView === "cultivation" && state.cultivation.setupOpen) {
    updateHarvestButtonState();
  }
}

function renderToasts() {
  if (!state.isAuthenticated || state.notificationsOpen) {
    elements.toastRoot.innerHTML = "";
    return;
  }

  // Reuse existing toast DOM nodes by id instead of rebuilding the whole
  // stack every time, so an already-visible toast doesn't replay its
  // entrance animation whenever a sibling toast is added or removed.
  const root = elements.toastRoot;
  const existingNodes = new Map();
  Array.from(root.children).forEach((node) => {
    const id = node instanceof HTMLElement ? node.dataset.toastId : "";
    if (id) {
      existingNodes.set(id, node);
    }
  });

  const seenIds = new Set();
  state.toasts.forEach((notification) => {
    const id = String(notification.id);
    seenIds.add(id);
    const existingNode = existingNodes.get(id);
    if (existingNode) {
      existingNode.classList.toggle("is-exiting", Boolean(notification.exiting));
      return;
    }

    const wrapper = document.createElement("div");
    wrapper.innerHTML = toastTemplate(notification).trim();
    const node = wrapper.firstElementChild;
    if (node instanceof HTMLElement) {
      node.dataset.toastId = id;
      root.appendChild(node);
    }
  });

  existingNodes.forEach((node, id) => {
    if (!seenIds.has(id)) {
      node.remove();
    }
  });
}

function logoutConfirmModalTemplate() {
  return `
    <div class="overlay overlay--center overlay--dialog">
      <div
        class="modal modal--sm logout-confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="logout-confirm-title"
        aria-describedby="logout-confirm-copy"
      >
        <div class="modal__body logout-confirm-modal__body">
          <span class="logout-confirm-modal__icon" aria-hidden="true">${icon("logout")}</span>
          <div class="logout-confirm-modal__copy">
            <p class="logout-confirm-modal__eyebrow">Secure Session</p>
            <h3 class="section-title logout-confirm-modal__title" id="logout-confirm-title">Log out of ICuCrops?</h3>
            <p class="section-copy logout-confirm-modal__text" id="logout-confirm-copy">
              You will be signed out from this device and returned to the login form. You can sign back in again anytime.
            </p>
          </div>
          <div class="modal__actions logout-confirm-modal__actions">
            <button class="button button--secondary button--full" type="button" data-action="close-logout-confirm">
              Cancel
            </button>
            <button class="button button--danger button--full" type="button" data-action="confirm-logout">
              ${icon("logout")}
              <span>Logout</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function getDeleteScheduleTarget() {
  const channelKey = String(state.deleteScheduleTargetChannel || "").trim();
  const activeScheduleLines = normalizeIrrigationRunMap(state.irrigationPage.activeScheduleLines);
  const channel = IRRIGATION_CHANNELS.find((item) => item.key === channelKey);

  if (!channel || !activeScheduleLines[channelKey]) {
    return null;
  }

  return {
    channel,
    channelState: state.irrigationPage.channels?.[channelKey] || {},
  };
}

function deleteScheduleConfirmModalTemplate() {
  const target = getDeleteScheduleTarget();
  if (!target) {
    return "";
  }

  const { channel, channelState } = target;

  return `
    <div class="overlay overlay--center overlay--dialog">
      <div
        class="modal modal--sm delete-schedule-confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-schedule-confirm-title"
        aria-describedby="delete-schedule-confirm-copy"
      >
        <div class="modal__body delete-schedule-confirm-modal__body">
          <span class="delete-schedule-confirm-modal__icon" aria-hidden="true">${icon("trash")}</span>
          <div class="delete-schedule-confirm-modal__copy">
            <p class="delete-schedule-confirm-modal__eyebrow">Irrigation Schedule</p>
            <h3 class="section-title delete-schedule-confirm-modal__title" id="delete-schedule-confirm-title">Remove ${escapeHtml(channel.label)} schedule?</h3>
            <p class="section-copy delete-schedule-confirm-modal__text" id="delete-schedule-confirm-copy">
              This will stop this scheduled irrigation line. Other active schedules will keep running.
            </p>
            <p class="section-copy delete-schedule-confirm-modal__meta">
              ${escapeHtml(irrigationScheduleSummary(channelState))}
            </p>
          </div>
          <div class="modal__actions delete-schedule-confirm-modal__actions">
            <button class="button button--secondary button--full" type="button" data-action="close-delete-schedule-confirm">
              Cancel
            </button>
            <button class="button button--danger button--full" type="button" data-action="confirm-delete-schedule">
              ${icon("trash")}
              <span>Remove Schedule</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function dashboardActiveRows() {
  return IOT_DEVICE_ROWS.filter((row) => activeCultivationForRow(row.key));
}

function dashboardRowsToShow() {
  const activeRows = dashboardActiveRows();
  return (activeRows.length ? activeRows : IOT_DEVICE_ROWS).slice(0, 1);
}

function dashboardInactiveRowCount() {
  return Math.max(0, IOT_DEVICE_ROWS.length - dashboardActiveRows().length);
}

function dashboardRowSummaryTemplate() {
  const activeRows = dashboardActiveRows().length;
  const inactiveRows = dashboardInactiveRowCount();
  return `
    <div class="dashboard-row-summary" aria-label="${escapeHtml(`${activeRows} active rows and ${inactiveRows} inactive rows`)}">
      <span><strong>${escapeHtml(activeRows)}</strong> active</span>
      <span><strong>${escapeHtml(inactiveRows)}</strong> inactive</span>
    </div>
  `;
}

function dashboardRowsToggleButtonTemplate(extraClass = "") {
  const hasHiddenRows = IOT_DEVICE_ROWS.length > dashboardRowsToShow().length;
  if (!hasHiddenRows) {
    return "";
  }

  return `
    <button class="button button--secondary dashboard-panel__action ${extraClass}" type="button" data-action="toggle-dashboard-rows">
      ${icon("dashboard")}
      <span>See All Rows</span>
    </button>
  `;
}

function dashboardAllRowsModalTemplate() {
  return `
    <div class="overlay overlay--center overlay--dashboard-rows">
      <div class="modal dashboard-all-rows-modal" role="dialog" aria-modal="true" aria-labelledby="dashboard-all-rows-title">
        <div class="modal__header">
          <div class="card-head">
            <div>
              <h3 class="section-title" id="dashboard-all-rows-title">All IoT Device Rows</h3>
              <p class="section-copy">Monitor every row without expanding the main dashboard layout.</p>
            </div>
            <button class="icon-button" type="button" data-action="close-dashboard-all-rows" aria-label="Close all rows">
              ${icon("close")}
            </button>
          </div>
        </div>
        <div class="modal__body dashboard-all-rows-modal__body">
          <div class="dashboard-all-rows-grid">
            ${IOT_DEVICE_ROWS.map(iotDashboardRowCardTemplate).join("")}
          </div>
        </div>
      </div>
    </div>
  `;
}

function dashboardClampPercent(value) {
  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.max(0, Math.min(100, Math.round(value)));
}

function dashboardParseDate(value) {
  if (!value) {
    return null;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function dashboardParseDateTime(value) {
  if (!value) {
    return null;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function dashboardActiveCultivationStartDate(cultivations = state.activeCultivations) {
  const dates = (Array.isArray(cultivations) ? cultivations : [])
    .map((item) => dashboardParseDate(item?.plantingDate || item?.planted))
    .filter(Boolean)
    .sort((left, right) => left.getTime() - right.getTime());
  return dates[0] || null;
}

function dashboardGraphRangeOptions(graphKey = "sensor") {
  const normalizedGraphKey = graphKey === "cultivation"
    ? graphKey
    : "sensor";
  if (normalizedGraphKey !== "cultivation") {
    return DASHBOARD_GRAPH_RANGES.filter(
      (option) => !option.plantingBased && !option.cultivationOnly,
    );
  }
  // Every day-based window works here: growth over the window is date
  // arithmetic against the planting and harvest dates, and row health is
  // averaged from the row's daily reading history. Only the sub-day windows
  // are left out -- a crop does not move in Real Time or across 24 hours.
  return DASHBOARD_GRAPH_RANGES.filter(
    (option) => option.plantingBased || Number.isFinite(option.days),
  );
}

function normalizeDashboardGraphRange(value, graphKey = "sensor") {
  const normalized = String(value || "").trim().toLowerCase();
  return dashboardGraphRangeOptions(graphKey).some((option) => option.key === normalized)
    ? normalized
    : graphKey === "cultivation" ? "crop" : DASHBOARD_GRAPH_DEFAULT_RANGE;
}

// The graphs open on "Real Time" and most sessions never leave it, yet the
// dashboard asked for the whole retention window on every load. Against this
// farm's data a month of history took 10.5 s to assemble and a single day
// 0.3 s, so this asks for the widest range actually on screen and nothing more.
const DASHBOARD_HISTORY_MAX_DAYS = 30;
// Long enough for the widest window this dashboard can ask for. Vercel gives
// the function 60s (vercel.json), so this stays inside what the host allows.
const DASHBOARD_HISTORY_REQUEST_TIMEOUT_MS = 45000;

function dashboardHistoryDaysNeeded() {
  const ranges = state.dashboardGraphRanges || {};
  let days = 1;
  for (const graphKey of ["sensor", "cultivation"]) {
    const key = normalizeDashboardGraphRange(ranges[graphKey], graphKey);
    const option = DASHBOARD_GRAPH_RANGES.find((item) => item.key === key);
    if (!option) {
      continue;
    }
    // "Since Planting" has no fixed span, so it has to assume the widest.
    if (option.plantingBased) {
      return DASHBOARD_HISTORY_MAX_DAYS;
    }
    const needed = option.days || (option.hours ? Math.ceil(option.hours / 24) : 1);
    days = Math.max(days, needed);
  }
  return Math.min(DASHBOARD_HISTORY_MAX_DAYS, days);
}

// The dashboard opens on Real Time, but the cultivation graph's "Since
// Planting" default makes dashboardHistoryDaysNeeded() ask for the whole
// retention window on the very first request. Measured on this Pi, that query
// is ~8.8s of database work against ~2.4s for a single day, and nothing at all
// reaches the screen until it returns -- which is why a fresh boot sat on "No
// data" and "Offline", and why Real Time had only the one live point it had
// managed to poll. The first pass asks for the window the live graphs actually
// plot, and the rest is merged in behind the paint.
const DASHBOARD_HISTORY_FIRST_PAINT_DAYS = 1;

function dashboardHistoryDaysToRequest() {
  const needed = dashboardHistoryDaysNeeded();
  if ((state.dashboardSeriesDays || 0) > 0) {
    return needed;
  }
  return Math.min(needed, DASHBOARD_HISTORY_FIRST_PAINT_DAYS);
}

function scheduleDashboardHistoryBackfill() {
  if (dashboardHistoryBackfillPending) {
    return;
  }
  dashboardHistoryBackfillPending = true;
  // One tick later, so the narrow window is on screen before the wide query
  // starts competing with it.
  window.setTimeout(() => {
    dashboardHistoryBackfillPending = false;
    if (!state.isAuthenticated || dashboardHistoryDaysNeeded() <= (state.dashboardSeriesDays || 0)) {
      return;
    }
    void refreshSensors({ render: false }).then(() => {
      if (state.activeView === "dashboard") {
        renderDashboardLiveGraphSections();
        syncDashboardLiveSensorGraph();
      }
    });
  }, 60);
}

function dashboardGraphRangeLabel(rangeKey, graphKey = "sensor") {
  const normalized = normalizeDashboardGraphRange(rangeKey, graphKey);
  return DASHBOARD_GRAPH_RANGES.find((option) => option.key === normalized)?.label || "7 Days";
}

// "Real Time" means the last few *rounds of readings*, not the last few seconds
// of the viewer's clock.
//
// The window used to be a fixed thirty seconds wide. On the kiosk, where the
// browser and the board that stamped the reading are the same machine, that
// always held the data. Everywhere else it had to survive the sync latency on
// the way up *and* whatever difference there is between the Pi's clock -- it
// has no RTC -- and the viewer's, and the boards do not publish every five
// seconds anyway. So one reading landed inside the window, the composite trace
// was one point long, and a path through a single point paints nothing: the
// card drew a lone dot at the right edge and no line at all.
//
// Anchoring the axis on the readings themselves fixes both. Boards publish in
// rounds -- several sensors within a second or two of each other -- so each
// round becomes one slot, evenly spaced, labelled with the time it was
// captured. Seven rounds of history draw seven points and a continuous curve
// whether the farm is publishing every five seconds or every five minutes, and
// nothing on the chart is invented: every point is still a reading that was
// actually recorded.
// How close two readings have to be to count as the same publishing round.
//
// This is a property of the BOARDS, not of how often the browser polls, and it
// was tied to the poll interval only because the two happened to be the same
// number. They are not the same thing: the boards stagger their sensors by a
// second or two within a round, so the gap has to be wide enough to gather
// them and narrow enough that two separate rounds do not merge into one.
//
// 5 s covers the stagger for every board here -- soil samples every 1.5 s,
// RS485 every 2 s, the DHT22 every 2.5 s -- and stays under the 30 s idle
// heartbeat, so a quiet farm still draws one point per beat. Dropping it to
// the poll interval would split one round across several slots the moment the
// kiosk polls faster than the boards publish.
const DASHBOARD_REALTIME_ROUND_GAP_MS = 5000;
const DASHBOARD_REALTIME_MIN_SPAN_MS = DASHBOARD_REALTIME_ROUND_GAP_MS * (DASHBOARD_GRAPH_POINT_LIMIT - 1);
// Past this the axis is no longer a matter of seconds, so the labels stop
// pretending it is and switch to clock time.
const DASHBOARD_REALTIME_CLOCK_LABEL_SPAN_MS = 90 * 1000;

// The points one metric's line is drawn from: the shown row's own board for the
// soil readings, the shared series for the rest.
function dashboardGraphMetricPoints(metricKey, rowKey = "") {
  return rowKey && DASHBOARD_ROW_GRAPH_METRIC_KEYS.includes(metricKey)
    ? state.dashboardSeries?.rowMetrics?.[rowKey]?.[metricKey] || []
    : state.dashboardSeries?.metrics?.[metricKey] || [];
}

// The axis has to come from the same series the line is drawn from. It used to
// take every row's stamps while the line drew only the shown row, so each round
// Rows 2-4 published opened a slot this row had nothing in, and Real Time cut
// the line in two there.
function dashboardRealtimeSeriesLists(graphKey = "sensor") {
  const rowKey = dashboardRowsToShow()[0]?.key || "";
  return DASHBOARD_SENSOR_GRAPH_METRICS.map((metric) => dashboardGraphMetricPoints(metric.key, rowKey));
}

function dashboardRealtimeReadingStamps(graphKey = "sensor") {
  const stamps = new Set();
  for (const points of dashboardRealtimeSeriesLists(graphKey)) {
    for (const point of Array.isArray(points) ? points : []) {
      if (!Number.isFinite(Number.parseFloat(point?.value))) {
        continue;
      }
      const at = Date.parse(point?.capturedAt);
      if (Number.isFinite(at)) {
        stamps.add(at);
      }
    }
  }
  return [...stamps].sort((left, right) => left - right);
}

// One round per burst of publishes. A round is measured from its own first
// stamp, so a steady stream cannot chain every reading it ever took into a
// single round.
function dashboardRealtimeRounds(stamps) {
  const rounds = [];
  for (const at of stamps) {
    const current = rounds[rounds.length - 1];
    if (current && at - current.start < DASHBOARD_REALTIME_ROUND_GAP_MS) {
      current.end = at;
      continue;
    }
    rounds.push({ start: at, end: at });
  }
  return rounds;
}

// Where one slot ends and the next begins: halfway through the quiet stretch
// between two rounds, so every reading falls in exactly one slot and none is
// counted twice.
function dashboardRealtimeSlotBoundary(earlier, later) {
  return Math.ceil((earlier.end + later.start) / 2);
}

function formatDashboardRealtimeBucketLabel(date, spanMs) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
    return "";
  }

  if (Number.isFinite(spanMs) && spanMs > DASHBOARD_REALTIME_CLOCK_LABEL_SPAN_MS) {
    return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  }

  return date.toLocaleTimeString("en-US", { minute: "2-digit", second: "2-digit" });
}

function dashboardRealtimeBuckets(graphKey = "sensor") {
  const rounds = dashboardRealtimeRounds(dashboardRealtimeReadingStamps(graphKey))
    .slice(-DASHBOARD_GRAPH_POINT_LIMIT);
  if (!rounds.length) {
    return [];
  }

  const spanMs = rounds[rounds.length - 1].end - rounds[0].start;
  return rounds.map((round, index) => {
    const previous = rounds[index - 1];
    const next = rounds[index + 1];
    const start = previous ? dashboardRealtimeSlotBoundary(previous, round) : round.start;
    const end = next ? dashboardRealtimeSlotBoundary(round, next) : round.end + 1;
    return {
      start: new Date(start),
      end: new Date(end),
      label: formatDashboardRealtimeBucketLabel(new Date(round.end), spanMs),
    };
  });
}

// The newest capture stamp the graph's series carries, or NaN.
function dashboardNewestReadingStamp(graphKey = "sensor") {
  const stamps = dashboardRealtimeReadingStamps(graphKey);
  return stamps.length ? stamps[stamps.length - 1] : Number.NaN;
}

// A window measured from the viewer's clock empties out the moment the farm's
// newest reading is older than the window itself -- a board that has been down
// for a fortnight, or a Pi whose clock came back wrong after a power cut, since
// it has no RTC. "7 Days" then answered "No backend readings" with a week of
// readings sitting in the series. Slide the window back onto the data instead;
// the axis labels still name the days actually being drawn.
function dashboardWindowEnd(graphKey, spanMs) {
  // The server's clock, not the viewer's: a desktop running 80 minutes slow
  // ended every range 80 minutes ago and cut its own newest readings off.
  const now = new Date(dashboardNowMs());
  const newest = dashboardNewestReadingStamp(graphKey);
  if (!Number.isFinite(newest) || !Number.isFinite(spanMs) || newest >= now.getTime() - spanMs) {
    return now;
  }
  return new Date(newest);
}

function dashboardGraphMeta(rangeKey, graphKey = "sensor") {
  const normalized = normalizeDashboardGraphRange(rangeKey, graphKey);
  const options = dashboardGraphRangeOptions(graphKey);
  const option = options.find((item) => item.key === normalized)
    || options.find((item) => item.key === DASHBOARD_GRAPH_DEFAULT_RANGE);

  if (option?.realtime) {
    const buckets = dashboardRealtimeBuckets(graphKey);
    if (buckets.length) {
      return {
        key: normalized,
        label: dashboardGraphRangeLabel(normalized, graphKey),
        start: buckets[0].start,
        end: buckets[buckets.length - 1].end,
        bucketCount: buckets.length,
        realtime: true,
        buckets,
      };
    }

    // Nothing has been recorded yet. Hold an empty half-minute so the axis
    // still has a shape, and let the card's own empty state do the talking.
    const emptyEnd = new Date(dashboardNowMs());
    return {
      key: normalized,
      label: dashboardGraphRangeLabel(normalized, graphKey),
      start: new Date(emptyEnd.getTime() - DASHBOARD_REALTIME_MIN_SPAN_MS),
      end: emptyEnd,
      bucketCount: DASHBOARD_GRAPH_POINT_LIMIT,
      realtime: true,
      buckets: [],
    };
  }

  const spanMs = Number.isFinite(option?.hours)
    ? option.hours * 60 * 60 * 1000
    : Number.isFinite(option?.days)
      ? option.days * 24 * 60 * 60 * 1000
      : Number.NaN;
  const end = dashboardWindowEnd(graphKey, spanMs);
  let start = null;

  if (option?.plantingBased) {
    start = dashboardActiveCultivationStartDate();
  } else if (Number.isFinite(spanMs)) {
    start = new Date(end.getTime() - spanMs);
  }

  if (!(start instanceof Date) || Number.isNaN(start.getTime())) {
    return dashboardGraphMeta(DASHBOARD_GRAPH_DEFAULT_RANGE === normalized ? "24h" : DASHBOARD_GRAPH_DEFAULT_RANGE, graphKey);
  }

  return {
    key: normalized,
    label: dashboardGraphRangeLabel(normalized, graphKey),
    start,
    end,
    // 24h gets finer buckets than the multi-day ranges because a day is the
    // window where a real outage is still legible. At six buckets each one
    // spanned four hours, so a Pi that was off for an evening collapsed into a
    // single empty slot and the line came back as one short stub near the
    // right edge -- it read as a broken graph rather than as the gap it was.
    // Twelve puts a point every two hours, which shows the shape of a gap and
    // still fits the kiosk's 800px axis without the labels colliding.
    bucketCount: normalized === "24h" ? DASHBOARD_GRAPH_DAY_BUCKETS : DASHBOARD_GRAPH_POINT_LIMIT,
    realtime: false,
  };
}

function formatDashboardGraphBucketLabel(date, rangeKey) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
    return "";
  }

  if (rangeKey === "24h") {
    return date.toLocaleTimeString("en-US", { hour: "numeric" });
  }

  if (rangeKey === "realtime") {
    return formatDashboardRealtimeBucketLabel(date, 0);
  }

  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function dashboardIsRealtimeGraphRange(rangeKey, graphKey = "sensor") {
  return normalizeDashboardGraphRange(rangeKey, graphKey) === "realtime";
}

function dashboardGraphBuckets(meta) {
  // A realtime axis is one slot per round of readings, already measured out by
  // dashboardRealtimeBuckets. Dividing the window evenly instead would drop two
  // rounds into one slot and leave the next one empty whenever the boards
  // published unevenly -- a gap in the curve that nothing on the farm caused.
  if (Array.isArray(meta.buckets) && meta.buckets.length) {
    return meta.buckets;
  }

  const startMs = meta.start.getTime();
  const endMs = Math.max(meta.end.getTime(), startMs + 1);
  const spanMs = Math.max(1, endMs - startMs);

  return Array.from({ length: meta.bucketCount }, (_, index) => {
    const bucketStart = startMs + Math.floor((spanMs * index) / meta.bucketCount);
    const bucketEnd = index === meta.bucketCount - 1
      ? endMs + 1
      : startMs + Math.floor((spanMs * (index + 1)) / meta.bucketCount);
    const labelDate = new Date(Math.max(bucketStart, bucketEnd - 1));
    return {
      start: new Date(bucketStart),
      end: new Date(bucketEnd),
      label: formatDashboardGraphBucketLabel(labelDate, meta.key),
    };
  });
}

function dashboardSeriesDataFromPoints(points, meta, {
  fallbackValue = Number.NaN,
  mapValue = (value) => value,
  allowCarryForward = true,
  allowHistoricalCarry = true,
  // A reading holds through a bucket or two of jitter -- a board that missed
  // one publish has not changed level. Past that it is an assertion about a
  // level nobody measured, and unbounded it painted a dead sensor as a
  // confident flat line all the way to the right edge.
  maxCarryBuckets = 2,
} = {}) {
  const parsedPoints = (Array.isArray(points) ? points : [])
    .map((point) => {
      const value = Number.parseFloat(point?.value);
      const capturedDate = dashboardParseDateTime(point?.capturedAt);
      if (!Number.isFinite(value) || !capturedDate) {
        return null;
      }
      return {
        value,
        capturedAt: String(point?.capturedAt || "").trim(),
        date: capturedDate,
      };
    })
    .filter(Boolean)
    .sort((left, right) => left.date.getTime() - right.date.getTime());

  const filteredPoints = parsedPoints.filter((point) => point.date >= meta.start && point.date <= meta.end);
  const historicalCarry = allowHistoricalCarry
    ? [...parsedPoints].reverse().find((point) => point.date < meta.start) || null
    : null;
  let carryValue = Number.isFinite(historicalCarry?.value) ? historicalCarry.value : Number.NaN;

  if (!filteredPoints.length && !Number.isFinite(carryValue) && !Number.isFinite(fallbackValue)) {
    return {
      labels: [],
      values: [],
      rawValues: [],
      latestRawValue: fallbackValue,
    };
  }

  const labels = [];
  const values = [];
  const rawValues = [];

  let carriedBuckets = 0;
  for (const bucket of dashboardGraphBuckets(meta)) {
    const bucketPoints = filteredPoints.filter((point) => point.date >= bucket.start && point.date < bucket.end);
    if (bucketPoints.length) {
      carryValue = bucketPoints[bucketPoints.length - 1].value;
      carriedBuckets = 0;
    } else if (!allowCarryForward) {
      carryValue = Number.NaN;
    } else if (++carriedBuckets > maxCarryBuckets) {
      carryValue = Number.NaN;
    }

    labels.push(bucket.label);
    rawValues.push(Number.isFinite(carryValue) ? carryValue : null);
    values.push(Number.isFinite(carryValue) ? mapValue(carryValue) : null);
  }

  return {
    labels,
    values,
    rawValues,
    latestRawValue: filteredPoints[filteredPoints.length - 1]?.value ?? fallbackValue,
  };
}

function dashboardGraphRangeSelectTemplate(graphKey) {
  const normalizedGraphKey = graphKey === "cultivation"
    ? graphKey
    : "sensor";
  const selectedRange = normalizeDashboardGraphRange(state.dashboardGraphRanges?.[normalizedGraphKey], normalizedGraphKey);
  const graphLabel = {
    sensor: "Sensor graph",
    cultivation: "Cultivation graph health",
  }[normalizedGraphKey] || "Graph";
  return `
    <label class="dashboard-graph-range">
      <select class="select dashboard-graph-range__select" data-graph-range="${normalizedGraphKey}" aria-label="${escapeHtml(`${graphLabel} history range`)}">
        ${dashboardGraphRangeOptions(normalizedGraphKey).map((option) => `
          <option value="${option.key}" ${selectedRange === option.key ? "selected" : ""}>
            ${escapeHtml(option.label)}
          </option>
        `).join("")}
      </select>
    </label>
  `;
}

function cultivationProgressMeta(cultivation) {
  const startDate = dashboardParseDate(cultivation?.plantingDate || cultivation?.planted);
  const harvestDate = dashboardParseDate(cultivation?.harvestDate || cultivation?.harvest);
  const today = new Date();
  const todayDate = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const msPerDay = 24 * 60 * 60 * 1000;

  if (!startDate || !harvestDate || harvestDate <= startDate) {
    return {
      percent: 0,
      statusLabel: "Schedule pending",
      remainingLabel: cultivation?.remaining || "Schedule pending",
      ready: false,
    };
  }

  const totalDays = Math.max(1, Math.ceil((harvestDate - startDate) / msPerDay));
  const elapsedDays = Math.max(0, Math.floor((todayDate - startDate) / msPerDay));
  const remainingDays = Math.ceil((harvestDate - todayDate) / msPerDay);
  const percent = dashboardClampPercent(((todayDate - startDate) / (harvestDate - startDate)) * 100);

  return {
    percent,
    statusLabel: `${percent}% complete`,
    remainingLabel: remainingDays <= 0
      ? "Ready for harvest"
      : `${remainingDays} day${remainingDays === 1 ? "" : "s"} left`,
    ready: remainingDays <= 0,
    elapsedDays: Math.min(elapsedDays, totalDays),
    totalDays,
  };
}

function dashboardGraphRangeDays(rangeKey) {
  const normalized = normalizeDashboardGraphRange(rangeKey, "cultivation");
  const option = DASHBOARD_GRAPH_RANGES.find((item) => item.key === normalized);
  return Number.isFinite(option?.days) ? option.days : null;
}

function dashboardUtcDayKey(value) {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString().slice(0, 10);
}

// The first day a cultivation range covers, as a UTC day key. Reading history
// is bucketed by the UTC date of its capturedAt stamp, so the window bound has
// to be read the same way or the two disagree about which day a reading is in.
function cultivationRangeStartDayKey(rangeKey, cultivation) {
  const days = dashboardGraphRangeDays(rangeKey);
  if (Number.isFinite(days) && days > 0) {
    return dashboardUtcDayKey(new Date(dashboardNowMs() - ((days - 1) * 24 * 60 * 60 * 1000)));
  }
  return String(cultivation?.plantingDate || cultivation?.planted || "").trim().slice(0, 10);
}

const DASHBOARD_ROW_HEALTH_METRIC_KEYS = ["moisture", "ec", "ph", "temp", "humidity"];

// One entry per day the row has any reading for. Moisture, EC and pH come from
// that row's own daily series; temperature and humidity come from the shared
// DHT22 line, which really is shared across all four rows, folded into the same
// daily buckets so both sides are read the same way.
function dashboardRowDailyReadings(rowKey) {
  const daily = new Map();
  const rowSeries = state.dashboardSeries?.rows?.[rowKey] || {};

  for (const metricKey of ["moisture", "ec", "ph"]) {
    for (const point of rowSeries[metricKey] || []) {
      const dayKey = String(point?.date || "").slice(0, 10);
      const value = Number.parseFloat(point?.value);
      if (!dayKey || !Number.isFinite(value)) {
        continue;
      }
      const bucket = daily.get(dayKey) || {};
      bucket[metricKey] = value;
      daily.set(dayKey, bucket);
    }
  }

  for (const metricKey of ["temp", "humidity"]) {
    const totalsByDay = new Map();
    for (const point of state.dashboardSeries?.metrics?.[metricKey] || []) {
      const dayKey = String(point?.capturedAt || "").slice(0, 10);
      const value = Number.parseFloat(point?.value);
      if (!dayKey || !Number.isFinite(value)) {
        continue;
      }
      const totals = totalsByDay.get(dayKey) || { total: 0, count: 0 };
      totals.total += value;
      totals.count += 1;
      totalsByDay.set(dayKey, totals);
    }
    for (const [dayKey, totals] of totalsByDay) {
      const bucket = daily.get(dayKey) || {};
      bucket[metricKey] = totals.total / totals.count;
      daily.set(dayKey, bucket);
    }
  }

  return daily;
}

// Scores one day the same way the live status pill scores right now: how many
// of the metrics that actually reported sat inside this row's target range.
function dashboardRowHealthScoreFromReadings(row, readings) {
  const available = DASHBOARD_ROW_HEALTH_METRIC_KEYS.filter(
    (metricKey) => Number.isFinite(Number.parseFloat(readings?.[metricKey])),
  );
  if (!available.length) {
    return null;
  }

  const normalCount = available.reduce((count, metricKey) => {
    const range = iotRowMetricRange(row, iotRowMetricConfig(metricKey));
    const value = Number.parseFloat(readings[metricKey]);
    return count + (value >= range.min && value <= range.max ? 1 : 0);
  }, 0);

  return dashboardClampPercent((normalCount / available.length) * 100);
}

// Now, by the server's clock when one has answered. A reading's age is the
// server's timestamp against this, so a browser clock that is wrong by more
// than the 60s tolerance must not decide whether a sensor is live.
function dashboardNowMs() {
  const serverNow = window.ICuCropsAuth?.serverNow;
  return typeof serverNow === "function" ? serverNow() : Date.now();
}

function dashboardReadingIsFresh(capturedAt) {
  const capturedDate = dashboardParseDateTime(capturedAt);
  if (!capturedDate) {
    return false;
  }
  const age = dashboardNowMs() - capturedDate.getTime();
  return age >= -60000 && age <= DASHBOARD_SENSOR_MAX_AGE_MS;
}

// Whether the board behind a reading still sounds alive, which is a shorter
// question than whether its last value is still worth drawing. Keeps the same
// 60s tolerance for a browser clock running behind the Pi's, which has no RTC.
function dashboardReadingIsPresent(capturedAt) {
  const capturedDate = dashboardParseDateTime(capturedAt);
  if (!capturedDate) {
    return false;
  }
  const age = dashboardNowMs() - capturedDate.getTime();
  return age >= -60000 && age <= SENSOR_PRESENCE_MAX_AGE_MS;
}

function dashboardDht22ReadingIsFresh(capturedAt = SHARED_DHT22_METRICS.capturedAt) {
  const capturedDate = dashboardParseDateTime(capturedAt);
  if (!capturedDate) {
    return false;
  }
  const age = dashboardNowMs() - capturedDate.getTime();
  return age >= -60000 && age <= DHT22_LIVE_MAX_AGE_MS;
}

function dashboardRowMetricCapturedAt(row, metricKey) {
  if (metricKey === "temp" || metricKey === "humidity") {
    return SHARED_DHT22_METRICS.capturedAt;
  }
  return metricKey === "moisture"
    ? row?.capturedAt?.moisture
    : row?.capturedAt?.rs485;
}

function dashboardRowMetricHasFreshReading(row, metricKey) {
  const capturedAt = dashboardRowMetricCapturedAt(row, metricKey);
  const readingIsFresh = metricKey === "temp" || metricKey === "humidity"
    ? dashboardDht22ReadingIsFresh(capturedAt)
    : dashboardReadingIsFresh(capturedAt);
  const hasFreshReading = Number.isFinite(Number.parseFloat(iotRowMetricValue(row, metricKey)))
    && readingIsFresh;
  if (metricKey === "temp" || metricKey === "humidity") {
    return hasFreshReading;
  }
  return isRowSensorPoweredOn(row.key, metricKey) && hasFreshReading;
}

function dashboardRowConditionScore(row) {
  const metricKeys = ["moisture", "ec", "ph", "temp", "humidity"];
  const availableMetrics = metricKeys.filter((key) => dashboardRowMetricHasFreshReading(row, key));
  if (!availableMetrics.length) {
    return null;
  }
  const normalCount = availableMetrics.reduce((count, key) => {
    const status = iotRowMetricStatus(row, iotRowMetricConfig(key));
    return count + (status === "normal" ? 1 : 0);
  }, 0);

  return dashboardClampPercent((normalCount / availableMetrics.length) * 100);
}

const DASHBOARD_CULTIVATION_BAR_BOX = {
  // The chart is drawn with preserveAspectRatio="none", so the horizontal
  // scale is (card width / this width). At 1680 the axis text -- which has to
  // be set in viewBox units, not rem -- collapsed to about 4px on the 290px
  // kiosk card and on a phone. A narrower viewBox raises that scale for every
  // card without changing a single coordinate the bars are computed from.
  width: 980,
  height: 360,
  // Wide enough for a right-anchored "100" at the axis font size once the
  // narrow breakpoints scale it up; at the old 52 the label ran off-canvas.
  left: 92,
  right: 56,
  // Room above a finished tower for the percentage that sits on its cap. The
  // narrow breakpoints scale that label up, so this has to clear the largest
  // of them or the label collides with the 100 gridline on the kiosk.
  top: 52,
  bottom: 42,
};

const DASHBOARD_CULTIVATION_HEALTH_MAX_DAYS = 400;
const DASHBOARD_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function dashboardShiftDayKey(dayKey, days) {
  const date = new Date(`${dayKey}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function dashboardDayKeyLabel(dayKey) {
  const parts = String(dayKey || "").split("-");
  const month = Number.parseInt(parts[1], 10);
  const day = Number.parseInt(parts[2], 10);
  if (!Number.isFinite(month) || !Number.isFinite(day)) {
    return "";
  }
  return `${DASHBOARD_MONTH_LABELS[month - 1] || ""} ${day}`;
}

// A day with no reading is not a health verdict, so it gets its own tone rather
// than being folded into "critical" -- the chart draws it as a faded gap.
//
// The row pill's own 80/60 thresholds are deliberately not reused here. With
// five metrics, one of them sitting outside its target range still scores 80,
// which the pill calls normal -- so a row with its pH gone would draw solid
// green on a record whose entire job is to show trouble the moment it starts.
// Here anything short of every metric in range is at least a warning.
function cultivationHealthTone(score) {
  if (!Number.isFinite(score)) {
    return "none";
  }
  if (score >= 100) {
    return "normal";
  }
  if (score >= 60) {
    return "warning";
  }
  return "critical";
}

function cultivationHealthToneLabel(tone) {
  if (tone === "normal") {
    return "Healthy";
  }
  if (tone === "warning") {
    return "Warning";
  }
  if (tone === "critical") {
    return "Critical";
  }
  return "No reading";
}

// One row's record: a point per day from planting (or the start of the window)
// up to today, where the height is how far the crop has come towards harvest
// and the tone is the health its sensors reported that day. Days already drawn
// keep the tone they were recorded with -- the line is a log, not a status
// light, so a red stretch stays red even after the row recovers.
function cultivationHealthTrackForRow(row, rangeKey, todayKey) {
  const cultivation = activeCultivationForRow(row.key);
  if (!cultivation) {
    return null;
  }

  const plantingKey = String(cultivation.plantingDate || cultivation.planted || "").trim().slice(0, 10);
  const harvestKey = String(cultivation.harvestDate || cultivation.harvest || "").trim().slice(0, 10);
  if (!plantingKey || !harvestKey || harvestKey <= plantingKey) {
    return null;
  }

  const windowStartKey = cultivationRangeStartDayKey(rangeKey, cultivation);
  const firstKey = windowStartKey > plantingKey ? windowStartKey : plantingKey;
  const lastKey = todayKey < harvestKey ? todayKey : harvestKey;
  if (!firstKey || !lastKey || lastKey < firstKey) {
    return null;
  }

  const plantingTime = Date.parse(`${plantingKey}T00:00:00Z`);
  const harvestTime = Date.parse(`${harvestKey}T00:00:00Z`);
  const daily = dashboardRowDailyReadings(row.key);
  const liveScore = dashboardRowConditionScore(row);
  const points = [];

  let dayKey = firstKey;
  while (dayKey && dayKey <= lastKey && points.length < DASHBOARD_CULTIVATION_HEALTH_MAX_DAYS) {
    const dayTime = Date.parse(`${dayKey}T00:00:00Z`);
    const progress = dashboardClampPercent(((dayTime - plantingTime) / (harvestTime - plantingTime)) * 100);
    let score = dashboardRowHealthScoreFromReadings(row, daily.get(dayKey));
    // The daily series only closes a day once it is over, so today's point
    // comes from the live readings instead -- that is the end of the line the
    // grower is actually watching move.
    if (!Number.isFinite(score) && dayKey === todayKey) {
      score = liveScore;
    }
    points.push({
      dayKey,
      progress,
      score: Number.isFinite(score) ? score : null,
      tone: cultivationHealthTone(score),
    });
    dayKey = dashboardShiftDayKey(dayKey, 1);
  }

  if (!points.length) {
    return null;
  }

  const latest = points[points.length - 1];
  return {
    row,
    cultivation,
    points,
    latest,
    ready: latest.progress >= 100,
  };
}

function cultivationHealthChartData(rangeKey) {
  const todayKey = dashboardUtcDayKey(new Date(dashboardNowMs()));
  const columns = IOT_DEVICE_ROWS.map((row) => ({
    row,
    track: cultivationHealthTrackForRow(row, rangeKey, todayKey),
  }));

  return {
    columns,
    tracks: columns.map((column) => column.track).filter(Boolean),
    hasMissingDays: columns.some(
      (column) => column.track?.points.some((point) => point.tone === "none"),
    ),
    hasEarlierGrowth: columns.some((column) => column.track?.points[0]?.progress > 0),
  };
}

function cultivationHealthColumnGeometry(columnCount, box) {
  const plotWidth = box.width - box.left - box.right;
  const groupWidth = plotWidth / Math.max(1, columnCount);
  return {
    groupWidth,
    // Reads as a column chart rather than a set of pins: the reference design
    // gives each bar roughly half its slot. The floor matters on the 800x480
    // kiosk, where the plot is narrow and a proportional width alone would
    // render the bar only a couple of dozen pixels across.
    barWidth: Math.min(190, Math.max(64, groupWidth * 0.52)),
    centerAt: (index) => box.left + (groupWidth * index) + (groupWidth / 2),
  };
}

function cultivationHealthChartGridTemplate(columns, box) {
  const values = [100, 75, 50, 25, 0];
  const baseY = box.height - box.bottom;
  const { barWidth, centerAt } = cultivationHealthColumnGeometry(columns.length, box);
  const topY = dashboardChartY(100, box);

  return `
    <g class="cultivation-batch-chart__tracks" aria-hidden="true">
      ${columns.map((column, index) => `
        <rect
          class="cultivation-batch-chart__track"
          x="${Number((centerAt(index) - (barWidth / 2)).toFixed(1))}"
          y="${Number(topY.toFixed(1))}"
          width="${Number(barWidth.toFixed(1))}"
          height="${Number((baseY - topY).toFixed(1))}"
          rx="10"
        ></rect>
      `).join("")}
    </g>
    <g class="cultivation-batch-chart__grid">
      ${values.map((value) => {
        const y = dashboardChartY(value, box);
        return `
          <line x1="${box.left}" y1="${y}" x2="${box.width - box.right}" y2="${y}"></line>
          <text x="${box.left - 12}" y="${y + 4}">${value}</text>
        `;
      }).join("")}
    </g>
    <g class="cultivation-batch-chart__axis">
      <line x1="${box.left}" y1="${baseY}" x2="${box.width - box.right}" y2="${baseY}"></line>
      ${columns.map((column, index) => `
        <text x="${Number(centerAt(index).toFixed(1))}" y="${box.height - 16}">${escapeHtml(column.row.label)}</text>
      `).join("")}
    </g>
  `;
}

// Each row is one tower. A day's slice sits on top of the day before it, so the
// tower rises from planting towards the harvest line at 100 and every slice
// keeps the colour its sensors earned that day -- the stack is the crop's
// record, which is why a red run stays red once green picks up above it.
//
// Consecutive days that earned the same tone are merged into a single band
// before drawing. A month-long cultivation is 30 days, and drawing one rect per
// day made the tower read as fine stripes rather than as the crop's health
// bands -- the run length is the information, not the individual day, and the
// per-day detail survives in each band's <title> tooltip.
function cultivationHealthTowerBands(track) {
  const bands = [];

  track.points.slice(1).forEach((point, pointIndex) => {
    const previous = track.points[pointIndex];
    const open = bands[bands.length - 1];

    // Only merge into the band directly below when it is still the same tone;
    // a tone change starts a new band, which is what keeps the chronology.
    if (open && open.tone === point.tone) {
      open.to = point;
      open.days += 1;
      return;
    }

    bands.push({
      tone: point.tone,
      from: previous,
      to: point,
      days: 1,
      firstDayKey: point.dayKey,
    });
  });

  return bands;
}

function cultivationHealthChartTowersTemplate(columns, box) {
  const { barWidth, centerAt } = cultivationHealthColumnGeometry(columns.length, box);

  return columns.map((column, index) => {
    if (!column.track) {
      return "";
    }

    const { track } = column;
    const x = centerAt(index) - (barWidth / 2);
    // A 3/7/14/30-day window that opens after planting starts the colour
    // bands part-way up the tower. Without this the growth before the window
    // was left empty and the bar floated above the axis, which read as a
    // broken chart the moment the range was changed.
    const opening = track.points[0];
    const earlier = opening && opening.progress > 0
      ? `
        <rect
          class="cultivation-health-chart__slice cultivation-health-chart__slice--earlier"
          x="${Number(x.toFixed(1))}"
          y="${Number(dashboardChartY(opening.progress, box).toFixed(1))}"
          width="${Number(barWidth.toFixed(1))}"
          height="${Number(Math.max(0, dashboardChartY(0, box) - dashboardChartY(opening.progress, box)).toFixed(1))}"
        >
          <title>${escapeHtml(`${track.row.label} before ${dashboardDayKeyLabel(opening.dayKey)}: ${opening.progress}% to harvest, before this range`)}</title>
        </rect>
      `
      : "";
    const slices = earlier + cultivationHealthTowerBands(track).map((band) => {
      const yTop = dashboardChartY(band.to.progress, box);
      const yBottom = dashboardChartY(band.from.progress, box);
      const height = Math.max(0, yBottom - yTop);
      if (height <= 0) {
        return "";
      }

      const spanLabel = band.days > 1
        ? `${dashboardDayKeyLabel(band.firstDayKey)} to ${dashboardDayKeyLabel(band.to.dayKey)} (${band.days} days)`
        : dashboardDayKeyLabel(band.to.dayKey);
      const title = `${track.row.label} ${spanLabel}: ${band.to.progress}% to harvest, ${cultivationHealthToneLabel(band.tone)}${Number.isFinite(band.to.score) ? ` (${band.to.score}%)` : ""}`;

      return `
        <rect
          class="cultivation-health-chart__slice cultivation-health-chart__slice--${band.tone}"
          x="${Number(x.toFixed(1))}"
          y="${Number(yTop.toFixed(1))}"
          width="${Number(barWidth.toFixed(1))}"
          height="${Number(height.toFixed(1))}"
        >
          <title>${escapeHtml(title)}</title>
        </rect>
      `;
    }).join("");

    const capY = dashboardChartY(track.latest.progress, box);
    const baseY = box.height - box.bottom;
    // The stack is rounded as one shape, not per slice: a clip over the whole
    // tower gives the top and bottom their radius while the joins inside stay
    // square, which is what keeps the colour bands reading as one bar.
    const clipId = `cultivation-tower-${index}`;
    const towerHeight = Math.max(0, baseY - capY);

    return `
      <g class="cultivation-health-chart__tower">
        <defs>
          <clipPath id="${clipId}">
            <rect
              x="${Number(x.toFixed(1))}"
              y="${Number(capY.toFixed(1))}"
              width="${Number(barWidth.toFixed(1))}"
              height="${Number(towerHeight.toFixed(1))}"
              rx="${Number(Math.min(10, barWidth / 2, towerHeight / 2).toFixed(1))}"
            ></rect>
          </clipPath>
        </defs>
        <g clip-path="url(#${clipId})">${slices}</g>
        <text
          class="cultivation-health-chart__value"
          x="${Number((x + (barWidth / 2)).toFixed(1))}"
          y="${Number((capY - 14).toFixed(1))}"
        >${escapeHtml(`${track.latest.progress}%`)}</text>
      </g>
    `;
  }).join("");
}

function cultivationHealthLegendTemplate(hasMissingDays, hasEarlierGrowth = false) {
  const items = [
    { tone: "normal", label: "Healthy" },
    { tone: "warning", label: "Warning" },
    { tone: "critical", label: "Critical" },
  ];
  if (hasMissingDays) {
    items.push({ tone: "none", label: "No reading" });
  }
  if (hasEarlierGrowth) {
    items.push({ tone: "earlier", label: "Before range" });
  }

  return `
    <div class="dashboard-graph-legend cultivation-health-legend">
      ${items.map((item) => `
        <span class="dashboard-graph-legend__item">
          <i class="dashboard-graph-legend__swatch cultivation-health-legend__swatch--${item.tone}" aria-hidden="true"></i>
          ${escapeHtml(item.label)}
        </span>
      `).join("")}
    </div>
  `;
}

function cultivationHealthChartTemplate(rangeKey, box = DASHBOARD_CULTIVATION_BAR_BOX) {
  const { columns, tracks, hasMissingDays, hasEarlierGrowth } = cultivationHealthChartData(rangeKey);
  if (!tracks.length) {
    return "";
  }

  return `
    <svg
      class="cultivation-batch-chart cultivation-health-chart"
      viewBox="0 0 ${box.width} ${box.height}"
      preserveAspectRatio="none"
      role="img"
      aria-label="Cultivation health record per row"
    >
      ${cultivationHealthChartGridTemplate(columns, box)}
      ${cultivationHealthChartTowersTemplate(columns, box)}
    </svg>
    ${cultivationHealthLegendTemplate(hasMissingDays, hasEarlierGrowth)}
  `;
}

function cultivationHealthEmptyStateTemplate(extraClass = "") {
  const activeRows = dashboardActiveRows().length;
  return `
    <div class="dashboard-empty-state ${extraClass}">
      <span aria-hidden="true">${icon("sprout")}</span>
      <strong>${activeRows ? "No readings recorded yet" : "No cultivation rows"}</strong>
      <p class="section-copy">
        ${activeRows
          ? "The record starts as soon as the row sensors report."
          : "Start a cultivation setup to record crop health here."}
      </p>
    </div>
  `;
}

function dashboardCultivationBatchGraphTemplate() {
  const rangeKey = normalizeDashboardGraphRange(state.dashboardGraphRanges?.cultivation || "crop", "cultivation");
  const activeCount = dashboardActiveRows().length;
  const chart = cultivationHealthChartTemplate(rangeKey);

  return `
    <article class="glass-card card dashboard-panel dashboard-panel--cultivation-building">
      <div class="card-head dashboard-card-head">
        <div>
          <h3 class="section-title">Cultivation Graph Health</h3>
        </div>
        <div class="dashboard-panel__head-actions">
          ${dashboardGraphRangeSelectTemplate("cultivation")}
          <span class="pill ${activeCount ? "pill--normal" : "pill--warning"}">${escapeHtml(`${activeCount}/${IOT_DEVICE_ROWS.length} Active`)}</span>
        </div>
      </div>
      ${chart
        ? `<div class="dashboard-graph-card dashboard-graph-card--cultivation-batch">${chart}</div>`
        : cultivationHealthEmptyStateTemplate()}
    </article>
  `;
}

function dashboardGraphSectionTemplate() {
  return `
    <div class="dashboard-graph-layout">
      ${dashboardSensorGraphTemplate()}
      ${dashboardCultivationBatchGraphTemplate()}
    </div>
  `;
}

function dashboardConditionTone(score) {
  if (score >= 80) {
    return "normal";
  }
  if (score >= 60) {
    return "warning";
  }
  return "critical";
}

function dashboardConditionLabel(score) {
  if (score >= 80) {
    return "Stable";
  }
  if (score >= 60) {
    return "Needs watch";
  }
  return "Needs action";
}

const DASHBOARD_CHART_BOX = {
  width: 1120,
  height: 360,
  left: 52,
  right: 72,
  top: 14,
  bottom: 42,
};

const DASHBOARD_WIDE_CHART_BOX = {
  width: 1120,
  height: 360,
  left: 52,
  right: 72,
  top: 14,
  bottom: 42,
};

function dashboardChartX(index, count, box = DASHBOARD_CHART_BOX) {
  const pointInset = Number.isFinite(box.pointInset) ? box.pointInset : 0;
  const startX = box.left + pointInset;
  const plotWidth = Math.max(0, box.width - box.left - box.right - (pointInset * 2));
  if (count <= 1) {
    return Number(startX.toFixed(1));
  }

  return Number((startX + (plotWidth / (count - 1)) * index).toFixed(1));
}

function dashboardChartY(value, box = DASHBOARD_CHART_BOX) {
  const plotHeight = box.height - box.top - box.bottom;
  const scaleMin = Number.isFinite(box.scaleMin) ? box.scaleMin : 0;
  const scaleMax = Number.isFinite(box.scaleMax) ? box.scaleMax : 100;
  const scaleSpan = Math.max(1, scaleMax - scaleMin);
  const scaledPercent = dashboardClampPercent(((Number(value) - scaleMin) / scaleSpan) * 100);
  return Number((box.top + plotHeight - (scaledPercent / 100) * plotHeight).toFixed(1));
}

function dashboardAdaptiveChartBox(items, baseBox = DASHBOARD_CHART_BOX) {
  const values = items
    .flatMap((item) => Array.isArray(item?.values) ? item.values : [])
    .map((value) => Number.parseFloat(value))
    .filter(Number.isFinite);

  if (!values.length) {
    return baseBox;
  }

  const dataMin = Math.min(...values);
  const dataMax = Math.max(...values);
  const dataSpan = Math.max(0, dataMax - dataMin);
  const minimumSpan = 24;
  const padding = Math.max(4, dataSpan * 0.16);
  let scaleMin = Math.max(0, dataMin - padding);
  let scaleMax = Math.min(100, dataMax + padding);

  if (scaleMax - scaleMin < minimumSpan) {
    const center = (dataMin + dataMax) / 2;
    scaleMin = Math.max(0, center - (minimumSpan / 2));
    scaleMax = Math.min(100, center + (minimumSpan / 2));
    if (scaleMin === 0) {
      scaleMax = Math.min(100, minimumSpan);
    } else if (scaleMax === 100) {
      scaleMin = Math.max(0, 100 - minimumSpan);
    }
  }

  return {
    ...baseBox,
    scaleMin: Number(scaleMin.toFixed(1)),
    scaleMax: Number(scaleMax.toFixed(1)),
  };
}

function dashboardChartPoints(values, box = DASHBOARD_CHART_BOX) {
  return values.map((value, index) => {
    const numericValue = Number.parseFloat(value);
    if (!Number.isFinite(numericValue)) {
      return null;
    }
    return {
      x: dashboardChartX(index, values.length, box),
      y: dashboardChartY(numericValue, box),
    };
  });
}

// Runs of consecutive readings, split wherever a slot has no value. Dropping
// the gaps and joining what is left -- which is what filter(Boolean) did --
// draws a confident line straight across the missing stretch, which is the
// one shape a chart must never invent.
function dashboardChartSegments(values, box = DASHBOARD_CHART_BOX) {
  const runs = [];
  let run = [];
  dashboardChartPoints(values, box).forEach((point) => {
    if (point) {
      run.push(point);
      return;
    }
    if (run.length) {
      runs.push(run);
      run = [];
    }
  });
  if (run.length) {
    runs.push(run);
  }
  return runs;
}

function dashboardChartRunPath(points) {
  if (!points.length) {
    return "";
  }

  // A lone reading has no line to draw; its dot is what carries it.
  if (points.length === 1) {
    return `M ${points[0].x} ${points[0].y}`;
  }

  return points.slice(0, -1).reduce((path, point, index) => {
    const previousPoint = points[index - 1] || point;
    const nextPoint = points[index + 1];
    const afterNextPoint = points[index + 2] || nextPoint;
    const controlPointOne = {
      x: Number((point.x + (nextPoint.x - previousPoint.x) / 6).toFixed(1)),
      y: Number((point.y + (nextPoint.y - previousPoint.y) / 6).toFixed(1)),
    };
    const controlPointTwo = {
      x: Number((nextPoint.x - (afterNextPoint.x - point.x) / 6).toFixed(1)),
      y: Number((nextPoint.y - (afterNextPoint.y - point.y) / 6).toFixed(1)),
    };
    return `${path} C ${controlPointOne.x} ${controlPointOne.y}, ${controlPointTwo.x} ${controlPointTwo.y}, ${nextPoint.x} ${nextPoint.y}`;
  }, `M ${points[0].x} ${points[0].y}`);
}

function dashboardChartPath(values, box = DASHBOARD_CHART_BOX) {
  return dashboardChartSegments(values, box)
    .map(dashboardChartRunPath)
    .filter(Boolean)
    .join(" ");
}

// The combined dashboard trace uses a smooth cubic between every pair of
// samples. Its controls keep the two endpoint heights, so it passes through
// every real value without the overshoot produced by the old Catmull curve.
function dashboardChartSmoothRunPath(points) {
  if (!points.length) {
    return "";
  }
  return points.slice(1).reduce((path, point, index) => {
    const previous = points[index];
    const third = (point.x - previous.x) / 3;
    return `${path} C ${Number((previous.x + third).toFixed(1))} ${previous.y}, ${Number((point.x - third).toFixed(1))} ${point.y}, ${point.x} ${point.y}`;
  }, `M ${points[0].x} ${points[0].y}`);
}

function dashboardChartSmoothPath(values, box = DASHBOARD_CHART_BOX) {
  return dashboardChartSegments(values, box)
    .map(dashboardChartSmoothRunPath)
    .filter(Boolean)
    .join(" ");
}

function dashboardChartSmoothAreaPath(values, box = DASHBOARD_CHART_BOX) {
  const baseY = box.height - box.bottom;
  return dashboardChartSegments(values, box)
    .filter((run) => run.length > 1)
    .map((run) => `${dashboardChartSmoothRunPath(run)} L ${run[run.length - 1].x} ${baseY} L ${run[0].x} ${baseY} Z`)
    .join(" ");
}

function dashboardChartAreaPath(values, box = DASHBOARD_CHART_BOX) {
  const baseY = box.height - box.bottom;
  // One closed shape per run, so the fill stops at a gap instead of shading
  // across it.
  return dashboardChartSegments(values, box)
    .filter((run) => run.length > 1)
    .map((run) => `${dashboardChartRunPath(run)} L ${run[run.length - 1].x} ${baseY} L ${run[0].x} ${baseY} Z`)
    .join(" ");
}

function dashboardChartGridTemplate(labels, box = DASHBOARD_CHART_BOX) {
  const scaleMin = Number.isFinite(box.scaleMin) ? box.scaleMin : 0;
  const scaleMax = Number.isFinite(box.scaleMax) ? box.scaleMax : 100;
  const values = Array.from({ length: 5 }, (_, index) => {
    const value = scaleMax - (((scaleMax - scaleMin) / 4) * index);
    return Number(value.toFixed(1));
  });
  const baseY = box.height - box.bottom;
  return `
    <rect
      class="dashboard-line-chart__plot"
      x="${box.left}"
      y="${box.top}"
      width="${box.width - box.left - box.right}"
      height="${baseY - box.top}"
      rx="18"
    ></rect>
    <g class="dashboard-line-chart__grid">
      ${values.map((value) => {
        const y = dashboardChartY(value, box);
        return `
          <line x1="${box.left}" y1="${y}" x2="${box.width - box.right}" y2="${y}"></line>
          <text x="${box.left - 12}" y="${y + 4}">${Number.isInteger(value) ? value : value.toFixed(1)}</text>
        `;
      }).join("")}
    </g>
    <g class="dashboard-line-chart__guides">
      ${labels.map((_, index) => `
        <line
          x1="${dashboardChartX(index, labels.length, box)}"
          y1="${box.top}"
          x2="${dashboardChartX(index, labels.length, box)}"
          y2="${baseY}"
        ></line>
      `).join("")}
    </g>
    <g class="dashboard-line-chart__axis">
      <line x1="${box.left}" y1="${box.top}" x2="${box.left}" y2="${baseY}"></line>
      <line x1="${box.left}" y1="${baseY}" x2="${box.width - box.right}" y2="${baseY}"></line>
      ${labels.map((label, index) => {
        const anchor = index === 0 ? "start" : index === labels.length - 1 ? "end" : "middle";
        return `<text x="${dashboardChartX(index, labels.length, box)}" y="${box.height - 12}" style="text-anchor: ${anchor}">${escapeHtml(label)}</text>`;
      }).join("")}
    </g>
  `;
}

function dashboardChartPointTemplate(values, seriesIndex, box = DASHBOARD_CHART_BOX, baseDelay = 120 + (seriesIndex * 120)) {
  const points = dashboardChartPoints(values, box).filter(Boolean);
  return points
    .map((point, pointIndex) => `<circle class="dashboard-chart-point dashboard-chart-intro-dot dashboard-chart-point--${seriesIndex}" cx="${point.x}" cy="${point.y}" r="4.8" style="--chart-delay: ${baseDelay + (pointIndex * 52)}ms;"></circle>`)
    .join("");
}

function dashboardStaticChartPointTemplate(values, seriesIndex, box = DASHBOARD_CHART_BOX) {
  const points = dashboardChartPoints(values, box).filter(Boolean);
  return points
    .map((point) => `<circle class="dashboard-chart-point dashboard-chart-point--static dashboard-chart-point--${seriesIndex}" cx="${point.x}" cy="${point.y}" r="4.2"></circle>`)
    .join("");
}

function cultivationForecastValues(progress, index) {
  const offset = index * 5;
  return [
    0,
    dashboardClampPercent(Math.max(progress * 0.35, 18 + offset)),
    dashboardClampPercent(Math.max(progress * 0.7, 44 + offset)),
    dashboardClampPercent(Math.max(progress, 72 - Math.min(offset, 12))),
    100,
  ];
}

function cultivationChartSeriesTemplate(row, index) {
  const cultivation = activeCultivationForRow(row.key);
  const progress = cultivationProgressMeta(cultivation);
  const values = cultivationForecastValues(progress.percent, index);
  return `
    <path class="dashboard-chart-area dashboard-chart-area--${index}" d="${dashboardChartAreaPath(values)}"></path>
    <path class="dashboard-chart-line dashboard-chart-line--${index}" d="${dashboardChartPath(values)}"></path>
    ${dashboardChartPointTemplate(values, index)}
  `;
}

function cultivationSummaryCardTemplate(row, index) {
  const cultivation = activeCultivationForRow(row.key);
  const progress = cultivationProgressMeta(cultivation);
  const score = dashboardRowConditionScore(row);

  return `
    <article class="cultivation-summary-card">
      <div class="cultivation-summary-card__marker cultivation-summary-card__marker--${index}" aria-hidden="true"></div>
      <div class="cultivation-summary-card__copy">
        <span>${escapeHtml(row.label)}</span>
        <strong>${escapeHtml(cultivation.crop)}</strong>
        <small>${escapeHtml(`${progress.statusLabel} | ${dashboardConditionLabel(score)} ${score}%`)}</small>
      </div>
      <span class="pill ${progress.ready ? "pill--warning" : "pill--normal"}">${escapeHtml(progress.remainingLabel)}</span>
    </article>
  `;
}

// A legend entry is a name and a reading. When the column is narrow the entry
// may wrap between the two, but the reading itself must never split: "0.36" on
// one line and "mS/cm" on the next reads as two different numbers, and a value
// without its unit is not a reading at all.
function dashboardGraphLegendLabel(item) {
  const text = String(item ?? "").trim();
  const parts = text.match(/^(.*?)\s+([-+]?[\d.].*)$/);
  if (!parts) {
    return text;
  }
  return `${parts[1]} ${parts[2].replace(/\s+/g, " ")}`;
}

function dashboardGraphLegendTemplate(items, colors = []) {
  return `
    <div class="dashboard-graph-legend">
      ${items.map((item, index) => {
        // Painted inline from the graph's own palette. The indexed CSS classes
        // stay as the fallback for legends that pass no colours, but they are
        // a second list that drifts from the gradient, so the caller wins.
        const color = colors[index];
        const swatchStyle = color ? ` style="background: ${color};"` : "";
        return `
        <span class="dashboard-graph-legend__item">
          <i class="dashboard-graph-legend__swatch dashboard-graph-legend__swatch--${index}"${swatchStyle} aria-hidden="true"></i>
          ${escapeHtml(dashboardGraphLegendLabel(item))}
        </span>
      `;
      }).join("")}
    </div>
  `;
}

function dashboardLatestFiniteSeriesValue(values) {
  const match = [...(Array.isArray(values) ? values : [])]
    .reverse()
    .find((value) => Number.isFinite(Number.parseFloat(value)));
  const numericValue = Number.parseFloat(match);
  return Number.isFinite(numericValue) ? numericValue : Number.NaN;
}

function dashboardHasFiniteValues(values) {
  return Array.isArray(values) && values.some((value) => Number.isFinite(Number.parseFloat(value)));
}

function dashboardFiniteValueCount(values) {
  return (Array.isArray(values) ? values : [])
    .filter((value) => Number.isFinite(Number.parseFloat(value)))
    .length;
}

// A realtime chart should reach both edges of its box. Leading slots that no
// series has a reading for are not information -- they are the window being
// wider than the data so far -- so drop them and let the readings span the
// box. Every series is trimmed by the same amount, which keeps one shared x
// grid behind the lines, the dots and the hover zones.
function dashboardTrimLeadingEmptySlots(items, labels) {
  const hasValue = (item, index) => Number.isFinite(Number.parseFloat(item?.values?.[index]));
  let firstWithData = -1;
  for (let index = 0; index < labels.length; index += 1) {
    if (items.some((item) => hasValue(item, index))) {
      firstWithData = index;
      break;
    }
  }

  if (firstWithData <= 0) {
    return { items, labels };
  }

  const trim = (value) => (Array.isArray(value) ? value.slice(firstWithData) : value);
  return {
    items: items.map((item) => ({
      ...item,
      values: trim(item.values),
      pointLabels: trim(item.pointLabels),
      rawValues: trim(item.rawValues),
    })),
    labels: labels.slice(firstWithData),
  };
}

function dashboardSampleSeriesValues(values, count) {
  const source = (Array.isArray(values) ? values : [])
    .map((value) => Number.parseFloat(value))
    .filter(Number.isFinite);

  if (!source.length || count <= 0) {
    return [];
  }

  if (count === 1) {
    return [source[source.length - 1]];
  }

  // Fewer readings than slots means fewer readings. Stretching them to fill the
  // axis repeats each value across several slots, and a repeated value draws as
  // a flat run -- three real readings became six identical ones and the chart
  // reported a level nobody measured. Only downsample.
  if (source.length <= count) {
    return [...source];
  }

  return Array.from({ length: count }, (_, index) => {
    const sourceIndex = Math.round(((source.length - 1) * index) / (count - 1));
    return source[sourceIndex];
  });
}

function dashboardLatestFiniteRawValue(values, fallbackValue = Number.NaN) {
  const latest = [...(Array.isArray(values) ? values : [])]
    .reverse()
    .find((value) => Number.isFinite(Number.parseFloat(value)));
  const numericValue = Number.parseFloat(latest);
  return Number.isFinite(numericValue) ? numericValue : fallbackValue;
}

function dashboardLiveMetricRawValues(metricKey, count, fallbackValue, sourceValues = []) {
  const provided = Array.isArray(sourceValues) ? sourceValues : [];

  // A series that already has one entry per slot was measured against this
  // axis, so it goes through untouched. Squeezing its finite values out and
  // re-padding on the left slid a board that only published early in the
  // window over to the right edge, where it read as its newest reading.
  if (provided.length === count) {
    return provided.map((value) => {
      const numericValue = Number.parseFloat(value);
      return Number.isFinite(numericValue) ? numericValue : null;
    });
  }

  const source = provided
    .map((value) => Number.parseFloat(value))
    .filter(Number.isFinite);
  const fallback = Number.parseFloat(fallbackValue);
  const values = source.length
    ? dashboardSampleSeriesValues(source, count)
    : Number.isFinite(fallback) ? [fallback] : [];

  // Gaps, not copies.
  while (values.length < count) {
    values.unshift(null);
  }

  return values.slice(-count);
}

function dashboardShiftLiveMetricRawValues(values, nextValue) {
  const currentValues = Array.isArray(values) ? values : [];
  if (!currentValues.length) {
    return [];
  }

  if (currentValues.length === 1) {
    return [nextValue];
  }

  return [...currentValues.slice(1), nextValue];
}

function dashboardStaticMetricRawValues(metricKey, count, fallbackValue, sourceValues = []) {
  const parsedSource = (Array.isArray(sourceValues) ? sourceValues : [])
    .map((value) => Number.parseFloat(value))
    .filter(Number.isFinite);
  if (parsedSource.length) {
    return parsedSource.slice(-count);
  }
  return Number.isFinite(Number.parseFloat(fallbackValue)) ? [Number.parseFloat(fallbackValue)] : [];
}

function dashboardHasTrendShape(values) {
  const finiteValues = (Array.isArray(values) ? values : [])
    .map((value) => Number.parseFloat(value))
    .filter(Number.isFinite);
  if (finiteValues.length < 2) {
    return false;
  }

  return new Set(finiteValues.map((value) => Math.round(value * 10))).size > 1;
}


function updateDashboardLiveSensorGraph({ render = true } = {}) {
  return false;
}

function renderDashboardLiveGraphSections(graphKey) {
  if (
    !state.isAuthenticated
    || state.activeView !== "dashboard"
    || !elements.pageContent
  ) {
    return;
  }

  let found = false;

  if (!graphKey || graphKey === "sensor") {
    const sensorPanel = elements.pageContent.querySelector(".dashboard-panel--cultivation-graph");
    if (sensorPanel) {
      found = true;
      replaceOuterHTMLPreservingFocus(sensorPanel, dashboardSensorGraphTemplate());
    }

    const mobileSensorPanel = elements.pageContent.querySelector(".mobile-mini-panel--cultivation");
    if (mobileSensorPanel) {
      found = true;
      replaceOuterHTMLPreservingFocus(mobileSensorPanel, mobileCultivationProgressPanelTemplate());
    }
  }

  if (!graphKey || graphKey === "cultivation") {
    const cultivationPanel = elements.pageContent.querySelector(".dashboard-panel--cultivation-building");
    if (cultivationPanel) {
      found = true;
      replaceOuterHTMLPreservingFocus(cultivationPanel, dashboardCultivationBatchGraphTemplate());
    }

    const mobileCultivationPanel = elements.pageContent.querySelector(".mobile-mini-panel--cultivation-batch");
    if (mobileCultivationPanel) {
      found = true;
      replaceOuterHTMLPreservingFocus(mobileCultivationPanel, mobileCultivationBatchPanelTemplate());
    }
  }

  if (!found) {
    console.warn(`Dashboard graph region was not found: ${graphKey || "all"}`);
  }
}

function syncDashboardLiveSensorGraph() {
  if (dashboardLiveSensorGraphTimer) {
    window.clearInterval(dashboardLiveSensorGraphTimer);
    dashboardLiveSensorGraphTimer = 0;
  }
}

function dashboardGraphStatsTemplate(stats) {
  const filtered = (Array.isArray(stats) ? stats : []).filter((item) => item && item.label && item.value);
  if (!filtered.length) {
    return "";
  }

  return `
    <div class="dashboard-graph-stats">
      ${filtered.map((item, index) => `
        <div class="dashboard-graph-stat">
          <i class="dashboard-graph-legend__swatch dashboard-graph-legend__swatch--${index % 5}" aria-hidden="true"></i>
          <div class="dashboard-graph-stat__copy">
            <span>${escapeHtml(item.label)}</span>
            <strong>${escapeHtml(item.value)}</strong>
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

// The loaded history does not yet reach as far back as the range on screen,
// so the graph being empty means the request is still in flight -- not that the
// farm has never recorded anything.
function dashboardGraphHistoryPending() {
  return dashboardHistoryDaysNeeded() > (state.dashboardSeriesDays || 0);
}

function dashboardMetricConfig(metricKey) {
  return IOT_ROW_METRICS.find((metric) => metric.key === metricKey) || null;
}

function dashboardMetricFallbackValue(metricKey, row = null) {
  // The graph's row: its own board or nothing. Falling through to the shared
  // sensor below would put another row's reading back on this row's line.
  if (row && DASHBOARD_ROW_GRAPH_METRIC_KEYS.includes(metricKey)) {
    const rowValue = Number.parseFloat(iotRowMetricValue(row, metricKey));
    return Number.isFinite(rowValue) && dashboardReadingIsFresh(dashboardRowMetricCapturedAt(row, metricKey))
      ? rowValue
      : Number.NaN;
  }

  const dashboardSensor = state.dashboardSensors.find((sensor) => sensor.id === metricKey);
  const value = Number.parseFloat(dashboardSensor?.value);
  const sensorReadingIsFresh = metricKey === "temp" || metricKey === "humidity"
    ? dashboardDht22ReadingIsFresh(dashboardSensor?.capturedAt)
    : dashboardReadingIsFresh(dashboardSensor?.capturedAt);
  if (Number.isFinite(value) && sensorReadingIsFresh) {
    return value;
  }

  if (metricKey === "temp" || metricKey === "humidity") {
    const sharedValue = Number.parseFloat(SHARED_DHT22_METRICS[metricKey]);
    if (Number.isFinite(sharedValue) && dashboardDht22ReadingIsFresh()) {
      return sharedValue;
    }
  }

  return Number.NaN;
}

function dashboardMetricChartPercent(metricKey, value) {
  const metric = dashboardMetricConfig(metricKey);
  const numericValue = Number.parseFloat(value);
  if (!Number.isFinite(numericValue)) {
    // Preserve an empty timeslot as a gap. Turning it into zero draws a fake
    // baseline and makes the first real sample look like a giant spike.
    return null;
  }

  if (!metric || !Number.isFinite(metric.displayMin) || !Number.isFinite(metric.displayMax) || metric.displayMin === metric.displayMax) {
    return dashboardClampPercent(numericValue);
  }

  return dashboardClampPercent(((numericValue - metric.displayMin) / (metric.displayMax - metric.displayMin)) * 100);
}

function dashboardMetricReadingLabel(metricKey, value) {
  const metric = dashboardMetricConfig(metricKey);
  const numericValue = Number.parseFloat(value);
  if (!Number.isFinite(numericValue)) {
    return "No data";
  }

  const formattedValue = Number.isInteger(numericValue) ? String(numericValue) : numericValue.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  return `${formattedValue}${metric?.unit ? ` ${metric.unit}` : ""}`;
}

function dashboardMetricSeriesData(metricKey, rangeKey, rowKey = "") {
  const points = dashboardGraphMetricPoints(metricKey, rowKey);
  const meta = dashboardGraphMeta(rangeKey, "sensor");
  // Real Time is a liveness view: a board that stopped publishing has to leave
  // a gap there rather than a confident flat line, which is why it carries
  // nothing. A day-wide bucket is a different question. The boards do not
  // publish around the clock, so refusing to carry broke every wide range into
  // disconnected fragments -- a line cut into pieces by the gaps between
  // publishes rather than by anything that happened on the farm. Past
  // maxCarryBuckets it stops, so a dead sensor still runs out rather than
  // drawing a level nobody measured all the way to the right edge.
  const carryAcrossBuckets = !meta.realtime;
  return dashboardSeriesDataFromPoints(points, meta, {
    allowCarryForward: carryAcrossBuckets,
    allowHistoricalCarry: carryAcrossBuckets,
    // Carry is counted in buckets, so it has to be set per range or it means a
    // different amount of time in each one. Two buckets is 8 hours on a 7-day
    // range but only 4 on the 24-hour one, and a farm whose Pi is off for an
    // evening leaves a longer hole than that -- the line came back cut into a
    // stub on the left and a dot on the right. A day-wide view of a farm that
    // is powered off overnight should read as one continuous line, so this
    // spans the whole window and lets the level hold across the dark hours.
    maxCarryBuckets: meta.key === "24h" ? DASHBOARD_GRAPH_DAY_BUCKETS : undefined,
    mapValue: (value) => dashboardMetricChartPercent(metricKey, value),
  });
}

function dashboardSensorGraphData() {
  const rangeKey = normalizeDashboardGraphRange(state.dashboardGraphRanges?.sensor, "sensor");
  const graphMeta = dashboardGraphMeta(rangeKey, "sensor");
  const labels = dashboardGraphBuckets(graphMeta).map((bucket) => bucket.label);
  const isRealtime = dashboardIsRealtimeGraphRange(rangeKey, "sensor");
  // The row whose cards sit above this graph, so the two can never disagree.
  // Temp and humidity stay shared: the greenhouse has one DHT22 for every row.
  const graphRow = dashboardRowsToShow()[0] || null;
  const items = DASHBOARD_SENSOR_GRAPH_METRICS
    .map((metric) => {
      const seriesData = dashboardMetricSeriesData(metric.key, rangeKey, graphRow?.key || "");
      const rawValues = isRealtime
        ? dashboardLiveMetricRawValues(
            metric.key,
            labels.length,
            dashboardMetricFallbackValue(metric.key, graphRow),
            seriesData.rawValues,
          )
        : seriesData.rawValues;
      const hasBackendSeries = dashboardHasFiniteValues(rawValues);
      const latestValue = dashboardLatestFiniteRawValue(rawValues);

      return {
        ...metric,
        values: rawValues.map((value) => dashboardMetricChartPercent(metric.key, value)),
        pointLabels: rawValues.map((value) => dashboardMetricReadingLabel(metric.key, value)),
        latestLabel: dashboardMetricReadingLabel(metric.key, latestValue),
        hasLiveData: hasBackendSeries,
      };
    })
    .filter((item) => item.values.some((value) => Number.isFinite(Number.parseFloat(value))));

  // A window is always a little wider than the readings inside it: seven daily
  // readings span six days, so a seven-day axis opens on an empty slot and the
  // trace started a seventh of the way across the box. Drop the empty lead-in
  // and the labels with it, so the axis names the days actually drawn. Only the
  // leading run goes -- a hole in the middle is a real gap and stays one, and
  // the newest reading keeps the right edge either way.
  const trimmed = dashboardTrimLeadingEmptySlots(items, labels);

  return {
    items: trimmed.items,
    labels: trimmed.labels,
    hasLiveData: items.some((item) => item.hasLiveData),
    rangeLabel: dashboardGraphRangeLabel(rangeKey, "sensor"),
    isRealtime,
  };
}

// One palette per graph. The gradient stops, the hover dots and the legend
// swatches all read from here, so a legend entry can never name a colour the
// curve never draws -- the nutrients swatch used to be violet while its stretch
// of the line was teal.
const DASHBOARD_SENSOR_GRAPH_COLORS = ["#52c41a", "#f5a000", "#2997e8", "#b94de8", "#0ba39a"];
function dashboardSensorGraphStroke(index) {
  return DASHBOARD_SENSOR_GRAPH_COLORS[index] || DASHBOARD_SENSOR_GRAPH_COLORS[0];
}

// The reference design is one trace, not one line per reading type. Every
// timeslot becomes the average of the normalized values available in that
// slot. Missing sensors do not zero the curve and one late sensor cannot erase
// the others, while the legend still shows every latest reading separately.
function dashboardCarrySeriesAcrossReportedSlots(values, count, reported) {
  const source = Array.isArray(values) ? values : [];
  const carried = new Array(count).fill(null);
  let last = null;
  for (let index = 0; index < count; index += 1) {
    const value = Number.parseFloat(source[index]);
    if (Number.isFinite(value)) {
      last = value;
    }
    carried[index] = last;
  }

  // A board that only starts reporting part way through the window still has to
  // cover the slots before it, or its arrival alone moves the mean.
  const first = carried.find((value) => Number.isFinite(value));
  if (Number.isFinite(first)) {
    for (let index = 0; index < count; index += 1) {
      if (Number.isFinite(carried[index])) {
        break;
      }
      carried[index] = first;
    }
  }

  // Carrying stops at a slot where nothing reported at all. That is a real hole
  // in the history and the graph is supposed to break there rather than draw a
  // confident line across it.
  return carried.map((value, index) => (reported[index] ? value : null));
}

function dashboardCompositeGraphItem(items, label) {
  const list = Array.isArray(items) ? items : [];
  const count = Math.max(0, ...list.map((item) => item.values?.length || 0));
  const reported = Array.from({ length: count }, (_, index) =>
    list.some((item) => Number.isFinite(Number.parseFloat(item.values?.[index]))));

  // Every slot has to average the same set of readings. The soil boards publish
  // more slowly than this window's buckets, so a slot they missed used to be
  // averaged from the DHT22 alone -- and the trace stepped by twenty points
  // because of which boards happened to report in that second, not because
  // anything on the farm changed.
  const series = list
    .map((item) => dashboardCarrySeriesAcrossReportedSlots(item.values, count, reported))
    .filter((values) => values.some((value) => Number.isFinite(value)));

  const values = Array.from({ length: count }, (_, index) => {
    const available = series.map((entry) => entry[index]).filter(Number.isFinite);
    if (!available.length) {
      return null;
    }
    return Number((available.reduce((sum, value) => sum + value, 0) / available.length).toFixed(2));
  });
  return { label, values };
}

function dashboardCompositeGraphDefsTemplate(id, colors, box = DASHBOARD_CHART_BOX) {
  const stops = colors.map((color, index) => {
    const offset = colors.length <= 1 ? 0 : (index / (colors.length - 1)) * 100;
    return `<stop offset="${offset.toFixed(1)}%" stop-color="${color}"></stop>`;
  }).join("");
  const baseY = box.height - box.bottom;
  return `
    <defs>
      <linearGradient id="icu-${id}-line" gradientUnits="userSpaceOnUse" x1="${box.left}" y1="0" x2="${box.width - box.right}" y2="0">${stops}</linearGradient>
      <linearGradient id="icu-${id}-area" gradientUnits="userSpaceOnUse" x1="${box.left}" y1="0" x2="${box.width - box.right}" y2="0">${stops}</linearGradient>
      <linearGradient id="icu-${id}-fade" gradientUnits="userSpaceOnUse" x1="0" y1="${box.top}" x2="0" y2="${baseY}">
        <stop offset="0%" stop-color="#ffffff" stop-opacity="0.38"></stop>
        <stop offset="58%" stop-color="#ffffff" stop-opacity="0.14"></stop>
        <stop offset="100%" stop-color="#ffffff" stop-opacity="0"></stop>
      </linearGradient>
      <mask id="icu-${id}-area-mask"><rect x="${box.left}" y="${box.top}" width="${box.width - box.left - box.right}" height="${baseY - box.top}" fill="url(#icu-${id}-fade)"></rect></mask>
    </defs>`;
}

function dashboardCompositeGraphSeriesTemplate(item, id, box = DASHBOARD_CHART_BOX) {
  // A run of a single bucket has no line to draw: both smooth path builders
  // return a bare `M x y`, which paints nothing. Only a series that was one
  // point from end to end used to get a dot, so after a gap in the history the
  // newest readings -- the ones the farm actually wants to see -- disappeared
  // from the graph completely. Every isolated run now carries its own dot.
  const singlePoint = dashboardChartSegments(item.values, box)
    .filter((run) => run.length === 1)
    .map((run) => `<circle class="dashboard-chart-composite-point" cx="${run[0].x}" cy="${run[0].y}" r="5" style="fill: url(#icu-${id}-line) !important;"></circle>`)
    .join("");
  return `
    <path class="dashboard-chart-area dashboard-chart-area--composite" d="${dashboardChartSmoothAreaPath(item.values, box)}" mask="url(#icu-${id}-area-mask)" style="fill: url(#icu-${id}-area) !important; opacity: 1 !important; stroke: none !important;"></path>
    <path class="dashboard-chart-line dashboard-chart-line--composite" d="${dashboardChartSmoothPath(item.values, box)}" style="stroke: url(#icu-${id}-line) !important; stroke-width: 4.2 !important; stroke-dasharray: none !important; stroke-dashoffset: 0 !important; opacity: 1 !important; animation: none !important;"></path>
    ${singlePoint}
  `;
}

function dashboardSensorGraphHoverTemplate(items, labels, box = DASHBOARD_CHART_BOX, colorResolver = dashboardSensorGraphStroke) {
  const baseY = box.height - box.bottom;
  const plotWidth = box.width - box.left - box.right;
  const hoverDots = items
    .map((_, index) => `<circle class="dashboard-chart-hover-dot" r="5" visibility="hidden" data-dashboard-hover-dot="${index}"></circle>`)
    .join("");
  const zones = labels.map((label, pointIndex) => {
    const x = dashboardChartX(pointIndex, labels.length, box);
    const previousX = pointIndex === 0
      ? box.left
      : (dashboardChartX(pointIndex - 1, labels.length, box) + x) / 2;
    const nextX = pointIndex === labels.length - 1
      ? box.left + plotWidth
      : (x + dashboardChartX(pointIndex + 1, labels.length, box)) / 2;
    const rows = items
      .map((item, seriesIndex) => {
        const value = Number.parseFloat(item.values[pointIndex]);
        if (!Number.isFinite(value)) {
          return null;
        }

        return {
          label: item.label,
          color: colorResolver(seriesIndex, item),
          value: item.pointLabels?.[pointIndex] || item.latestLabel || "",
          y: dashboardChartY(value, box),
        };
      })
      .filter(Boolean);

    return `
      <rect
        class="dashboard-chart-hover-zone"
        x="${previousX}"
        y="${box.top}"
        width="${Math.max(1, nextX - previousX)}"
        height="${baseY - box.top}"
        data-title="${escapeHtml(label)}"
        data-x="${x}"
        data-rows="${escapeHtml(JSON.stringify(rows))}"
      ></rect>
    `;
  }).join("");

  return `
    <g class="dashboard-chart-hover-layer">
      <line class="dashboard-chart-hover-line" x1="0" y1="${box.top}" x2="0" y2="${baseY}" visibility="hidden"></line>
      ${hoverDots}
      ${zones}
    </g>
  `;
}

function dashboardGraphModeClass(isRealtime, base = "dashboard-graph-card") {
  if (!isRealtime) {
    return `${base}--static`;
  }
  return dashboardGraphSuppressIntro ? `${base}--realtime ${base}--no-intro` : `${base}--realtime`;
}

function dashboardSensorGraphTemplate() {
  const { items, labels, isRealtime } = dashboardSensorGraphData();
  const composite = dashboardCompositeGraphItem(items, "Sensor Overview");
  const chartBox = DASHBOARD_WIDE_CHART_BOX;
  const graphModeClass = dashboardGraphModeClass(isRealtime);
  return `
    <article class="glass-card card dashboard-panel dashboard-panel--cultivation-graph">
      <div class="card-head dashboard-card-head">
        <div>
          <h3 class="section-title">Live Sensor Graph</h3>
        </div>
        <div class="dashboard-panel__head-actions">
          ${dashboardGraphRangeSelectTemplate("sensor")}
        </div>
      </div>
      ${items.length
        ? `
          <div class="dashboard-graph-card dashboard-graph-card--sensors ${graphModeClass}">
            <svg class="dashboard-line-chart dashboard-line-chart--wide" viewBox="0 0 ${chartBox.width} ${chartBox.height}" preserveAspectRatio="none" role="img" aria-label="Live backend sensor readings line chart">
              ${dashboardCompositeGraphDefsTemplate("sensor", DASHBOARD_SENSOR_GRAPH_COLORS, chartBox)}
              ${dashboardChartGridTemplate(labels, chartBox)}
              ${dashboardCompositeGraphSeriesTemplate(composite, "sensor", chartBox)}
              ${dashboardSensorGraphHoverTemplate(items, labels, chartBox)}
            </svg>
            ${dashboardGraphLegendTemplate(items.map((item) => `${item.label} ${item.latestLabel}`), DASHBOARD_SENSOR_GRAPH_COLORS)}
          </div>
        `
        : `
          <div class="dashboard-empty-state">
            <span aria-hidden="true">${icon("activity")}</span>
            <strong>${dashboardGraphHistoryPending() ? "Loading history" : "No backend readings"}</strong>
            <p class="section-copy">${dashboardGraphHistoryPending()
              ? "Fetching the readings for this range from the backend."
              : "The graph will update after sensor readings are recorded."}</p>
          </div>
        `}
    </article>
  `;
}

function mobileCultivationProgressPanelTemplate() {
  const { items, labels, isRealtime } = dashboardSensorGraphData();
  const composite = dashboardCompositeGraphItem(items, "Sensor Overview");
  const chartBox = DASHBOARD_CHART_BOX;
  const chartModeClass = dashboardGraphModeClass(isRealtime, "mobile-line-chart-card");
  return `
    <article class="mobile-mini-panel mobile-mini-panel--chart mobile-mini-panel--cultivation">
      ${mobileGraphPanelHeadTemplate("Sensor Graph", "", "sensor")}
      ${items.length
        ? `
          <div class="mobile-line-chart-card mobile-line-chart-card--sensors ${chartModeClass}">
            <svg class="dashboard-line-chart" viewBox="0 0 ${chartBox.width} ${chartBox.height}" preserveAspectRatio="none" role="img" aria-label="Live backend sensor readings line chart">
              ${dashboardCompositeGraphDefsTemplate("sensor", DASHBOARD_SENSOR_GRAPH_COLORS, chartBox)}
              ${dashboardChartGridTemplate(labels, chartBox)}
              ${dashboardCompositeGraphSeriesTemplate(composite, "sensor", chartBox)}
              ${dashboardSensorGraphHoverTemplate(items, labels, chartBox)}
            </svg>
            ${dashboardGraphLegendTemplate(items.map((item) => `${item.label} ${item.latestLabel}`), DASHBOARD_SENSOR_GRAPH_COLORS)}
          </div>
        `
        : `<p class="section-copy mobile-empty-copy">${dashboardGraphHistoryPending()
          ? "Loading this range from the backend&hellip;"
          : "No backend readings yet."}</p>`}
    </article>
  `;
}

function mobileCultivationBatchPanelTemplate() {
  const rangeKey = normalizeDashboardGraphRange(state.dashboardGraphRanges?.cultivation || "crop", "cultivation");
  const chart = cultivationHealthChartTemplate(rangeKey);

  return `
    <article class="mobile-mini-panel mobile-mini-panel--chart mobile-mini-panel--cultivation-batch">
      ${mobileGraphPanelHeadTemplate("Cultivation Graph Health", "", "cultivation")}
      ${chart
        ? `<div class="mobile-line-chart-card mobile-line-chart-card--cultivation-batch">${chart}</div>`
        : cultivationHealthEmptyStateTemplate("mobile-chart-empty-state")}
    </article>
  `;
}

function mobileGraphPanelHeadTemplate(title, summary, graphKey) {
  return `
    <div class="mobile-mini-panel__head mobile-mini-panel__head--chart">
      <div>
        <strong>${escapeHtml(title)}</strong>
        ${summary ? `<span>${escapeHtml(summary)}</span>` : ""}
      </div>
      ${dashboardGraphRangeSelectTemplate(graphKey)}
    </div>
  `;
}

function dashboardTemplate() {
  const visibleRows = dashboardRowsToShow();
  return `
    <section class="page-stack page-stack--dashboard">
      <article class="glass-card card dashboard-panel dashboard-panel--iot-rows page-stack">
        <div class="card-head dashboard-card-head">
          <div>
            <h3 class="section-title">IoT Device Rows</h3>
            <p class="section-copy">Active grow rows are shown first, with live Normal or Warning status for each monitored value.</p>
          </div>
          <div class="dashboard-panel__head-actions">
            ${dashboardRowSummaryTemplate()}
            ${dashboardRowsToggleButtonTemplate()}
          </div>
        </div>
        <div class="iot-row-dashboard-grid">
          ${visibleRows.map(iotDashboardRowCardTemplate).join("")}
        </div>
      </article>

      ${dashboardGraphSectionTemplate()}
    </section>
  `;
}

function mobileDashboardTemplate() {
  const visibleRows = dashboardRowsToShow();
  return `
    <section class="mobile-dashboard">
      ${dashboardRowsToggleButtonTemplate("mobile-dashboard__row-toggle")}

      <div class="mobile-row-list">
        ${visibleRows.map(mobileIotRowCardTemplate).join("")}
      </div>

      <div class="mobile-dashboard__graphs">
        ${mobileCultivationProgressPanelTemplate()}
        ${mobileCultivationBatchPanelTemplate()}
      </div>

      <article class="glass-card card dashboard-panel dashboard-panel--health mobile-dashboard__health">
        <div class="card-head">
          <div>
            <h3 class="section-title">Sensor Health</h3>
          </div>
        </div>
        <div class="health-grid">
          ${sensorHealthItems().map(healthItemTemplate).join("")}
        </div>
      </article>
    </section>
  `;
}

function mobileDashboardStatTemplate(label, value) {
  return `
    <div class="mobile-dashboard__stat">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function mobileIotRowCardTemplate(row) {
  const tone = iotRowStatusTone(row);
  const cultivation = activeCultivationForRow(row.key);
  const title = cultivation ? cultivation.crop : row.label;
  const activityTone = cultivation ? "normal" : "critical";
  const activityLabel = cultivation ? "Active" : "Not Active";
  return `
    <article class="mobile-row-card mobile-row-card--${tone}">
      <div class="mobile-row-card__head">
        <div>
          <span>${escapeHtml(row.label)}</span>
          <strong>${escapeHtml(title)}</strong>
        </div>
        <div class="mobile-row-card__statuses">
          <span class="mobile-status mobile-status--${activityTone}">${escapeHtml(activityLabel)}</span>
          <span class="mobile-status mobile-status--${tone}">${escapeHtml(iotRowStatusLabel(row))}</span>
        </div>
      </div>
      <div class="mobile-reading-grid">
        ${mobileIotMetricButtonTemplate(row, iotRowMetricConfig("moisture"), "Moisture")}
        ${mobileIotMetricButtonTemplate(row, iotRowMetricConfig("ec"), "Soil Nutrients")}
        ${mobileIotMetricButtonTemplate(row, iotRowMetricConfig("ph"), "Soil pH")}
        ${mobileIotMetricButtonTemplate(row, iotRowMetricConfig("temp"), "Temp")}
        ${mobileIotMetricButtonTemplate(row, iotRowMetricConfig("humidity"), "Humidity")}
      </div>
    </article>
  `;
}

function mobileIotMetricButtonTemplate(row, metric, label) {
  const status = iotRowMetricStatus(row, metric);
  // The sensor's own power switch, not its reading. These read
  // `status !== "critical"` until criticalMargin existed, which was
  // harmless only because no metric could reach "critical" -- every
  // out-of-range reading stopped at "warning", so this was always true.
  // The moment a third level was added, a reading far outside its range
  // started printing "OFF" in place of the number, which is the one
  // thing a critical card most needs to show.
  const poweredOn = isRowSensorPoweredOn(row.key, metric.key);
  const value = iotRowMetricValue(row, metric.key);
  const percentage = iotRowMetricPercentage(row, metric);
  return `
    <button class="mobile-reading mobile-reading--${status}" type="button" data-action="open-sensor-detail" data-id="${row.key}-${metric.key}">
      <span class="mobile-reading__top">
        <span class="mobile-reading__icon">${icon(metric.icon)}</span>
        <span class="mobile-status mobile-status--${status}">${escapeHtml(iotRowMetricStatusLabel(row, metric))}</span>
      </span>
      <span class="mobile-reading__label">${escapeHtml(label)}</span>
      <strong>${poweredOn ? escapeHtml(iotReadingLabel(value, metric.unit)) : "OFF"}</strong>
      <span class="mobile-reading__bar" aria-hidden="true">
        <span style="width: ${percentage}%"></span>
      </span>
    </button>
  `;
}

// Draw the next page when the operator scrolls near the end of the drawn one,
// so the list behaves like the single long list it replaced and the button is
// only ever a fallback. Re-armed after each render because the element it
// watches is rebuilt every time.
let historyTailObserver = null;

function observeHistoryTail() {
  historyTailObserver?.disconnect();
  historyTailObserver = null;

  if (typeof IntersectionObserver !== "function") {
    return;
  }
  const tail = document.querySelector("[data-history-more]");
  if (!tail) {
    return;
  }

  // rootMargin pulls the trigger up so the next page is built before the
  // operator reaches the bottom, rather than after they hit it and wait.
  historyTailObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        showMoreHistory();
      }
    },
    { rootMargin: "320px 0px" },
  );
  historyTailObserver.observe(tail);
}

function showMoreHistory() {
  const limit = state.historyRenderLimit || HISTORY_RENDER_PAGE_SIZE;
  if (limit >= state.notificationHistory.length) {
    return;
  }
  state.historyRenderLimit = limit + HISTORY_RENDER_PAGE_SIZE;
  renderPage();
}

function historyTemplate() {
  const fullHistory = sortedNotificationHistory();
  // Paint a page at a time. This farm had 3,237 notifications and the list was
  // built for every one of them on each render: measured on the kiosk Pi,
  // layout alone costs ~836ms at 429 items and ~1.76s at 1000, so the full
  // history was several seconds of frozen UI every time this view opened.
  // "Show more" raises the cap in place, so nothing is hidden permanently and
  // no history is discarded.
  const history = fullHistory.slice(0, state.historyRenderLimit || HISTORY_RENDER_PAGE_SIZE);
  const remaining = fullHistory.length - history.length;
  const unread = unreadNotificationCount();

  return `
    <section class="page-stack">
      <div class="page-heading">
        <div>
          <h1>Notification History</h1>
          <p>Review all alerts, updates, and recent system activity from your dashboard.</p>
        </div>
        <div class="chip-row">
          <!-- fullHistory, not the paged slice: this counts every alert the
               farm has raised. Reading the slice instead said "50 total" on a
               Pi holding 5,133 of them. -->
          <span class="chip">${fullHistory.length} total</span>
          <span class="chip">${state.notifications.length} active now</span>
          <span class="chip">${unread} unread</span>
        </div>
      </div>

      <article class="glass-card card page-stack">
        <div class="card-head">
          <div>
            <h3 class="section-title">Recent Notifications</h3>
            <p class="section-copy">This page stores the history of your notification alerts.</p>
          </div>
          <div class="notification-history__actions">
            <button
              class="button button--secondary notification-history__action"
              type="button"
              data-action="open-notifications"
              aria-label="Open notification panel"
              title="Open notification panel"
            >
              ${icon("bell")}
              <span class="notification-history__action-label">Open Bell Panel</span>
            </button>
          </div>
        </div>

        ${history.length ? `
          <div class="notification-list notification-list--history">
            ${history.map((notification) => notificationItemTemplate(notification, true)).join("")}
          </div>
          ${remaining > 0 ? `
            <button
              class="button button--secondary button--full"
              type="button"
              data-action="show-more-history"
              data-history-more
            >
              Show ${Math.min(remaining, HISTORY_RENDER_PAGE_SIZE)} more
              (${remaining} remaining)
            </button>
          ` : ""}
        ` : `
          <div class="center-banner">No notification history yet.</div>
        `}
      </article>
    </section>
  `;
}

function sensorsTemplate() {
  return `
    <section class="page-stack">
      <div class="page-heading">
        <div>
          <h1>Sensor Management</h1>
          <p>Turn sensor devices on or off and choose the fan and grow light mode.</p>
        </div>
      </div>

      <article class="glass-card card page-stack">
        <div>
          <h3 class="section-title">Sensor Power</h3>
          <p class="section-copy">Each sensor can be switched On or Off here.</p>
        </div>
        <div class="grid grid--cards sensor-management-grid">
          ${SENSOR_MANAGEMENT_CARDS.map(sensorManagementCardTemplate).join("")}
        </div>
      </article>

      <article class="glass-card card page-stack">
        <div>
          <h3 class="section-title">Greenhouse Controls</h3>
          <p class="section-copy">Choose how the fan, grow light, and misting line should run.</p>
        </div>
        <div class="grid grid--three sensor-actuator-grid">
          ${SENSOR_ACTUATORS.map(actuatorControlCardTemplate).join("")}
        </div>
      </article>
    </section>
  `;
}

function irrigationTemplate() {
  const rows = Array.isArray(state.irrigationPage.rows) ? state.irrigationPage.rows : [];
  const activeRows = rows.filter((row) => row.active);
  const requestedRowKey = String(state.irrigationPage.selectedRowKey || "").trim();
  const selectedRow = activeRows.find((row) => row.key === requestedRowKey) || activeRows[0] || null;
  if (selectedRow && selectedRow.key !== requestedRowKey) {
    state.irrigationPage.selectedRowKey = selectedRow.key;
    writeIrrigationSelectedRowKey(selectedRow.key);
  }

  return `
    <section class="page-stack">
      <div class="page-heading">
        <div>
          <h1>Irrigation Control</h1>
          <p>Control water, fertilizer, and lime solution independently for every cultivation row.</p>
        </div>
      </div>

      <article class="glass-card card irrigation-row-overview">
        <div class="irrigation-row-overview__icon">${icon("droplets")}</div>
        <div>
          <h3 class="section-title">Select Active Row</h3>
          <p class="section-copy">Choose one active cultivation row, then set its own irrigation mode and solutions.</p>
        </div>
        <label class="irrigation-row-picker" for="irrigation-active-row-select">
          <span>Active Row</span>
          <select class="select irrigation-row-select" id="irrigation-active-row-select" ${activeRows.length ? "" : "disabled"}>
            ${activeRows.length ? activeRows.map((row) => `
              <option value="${escapeHtml(row.key)}" ${row.key === selectedRow?.key ? "selected" : ""}>
                ${escapeHtml(`${row.label} — ${row.crop} (${row.mode})`)}
              </option>
            `).join("") : `<option value="">No active rows</option>`}
          </select>
        </label>
        <span class="irrigation-row-count">${escapeHtml(`${activeRows.length} of ${rows.length} active`)}</span>
      </article>

      <div class="irrigation-row-controller-grid" data-irrigation-mode-region data-irrigation-mode="${escapeHtml(selectedRow?.mode || "")}">
        ${selectedRow ? irrigationRowControllerTemplate(selectedRow) : `
          <article class="glass-card card irrigation-row-empty">
            ${icon("lock")}
            <div>
              <h3 class="section-title">No active cultivation row</h3>
              <p class="section-copy">Add a crop in Cultivation before configuring irrigation.</p>
            </div>
          </article>
        `}
      </div>
    </section>
  `;
}

function irrigationModeContentTemplate() {
  const rows = (state.irrigationPage.rows || []).filter((row) => row.active);
  const selectedRow = rows.find((row) => row.key === state.irrigationPage.selectedRowKey) || rows[0];
  if (selectedRow && selectedRow.key !== state.irrigationPage.selectedRowKey) {
    state.irrigationPage.selectedRowKey = selectedRow.key;
    writeIrrigationSelectedRowKey(selectedRow.key);
  }
  return selectedRow ? irrigationRowControllerTemplate(selectedRow) : "";
}

function irrigationRowModeButtonTemplate(row, value, label, iconName) {
  const active = row.mode === value;
  return `
    <button
      class="irrigation-row-mode ${active ? "is-active" : ""}"
      type="button"
      data-action="set-row-irrigation-mode"
      data-row="${escapeHtml(row.key)}"
      data-mode="${value}"
      aria-pressed="${String(active)}"
      ${row.active ? "" : "disabled"}
    >
      ${icon(iconName)}
      <span>${escapeHtml(label)}</span>
    </button>
  `;
}

function irrigationRowChannelTemplate(row, channel) {
  const settings = row.channels?.[channel.key] || initialIrrigationChannels()[channel.key];
  const manualRunning = Boolean(state.irrigationPage.activeManualRows?.[channel.key]?.[row.key]);
  const scheduleRunning = Boolean(state.irrigationPage.activeScheduleRows?.[channel.key]?.[row.key]);
  const scheduleArmed = Boolean(state.irrigationPage.scheduleArmedRows?.[row.key]);
  const automaticRunning = Boolean(state.irrigationPage.activeAutomaticRows?.[channel.key]?.[row.key]);
  const sensorAvailable = Boolean(row.sensorAvailable?.[channel.key]);
  const needsSolution = Boolean(row.needs?.[channel.key]);
  let controls = "";

  if (row.mode === "automatic") {
    controls = `
      <label class="irrigation-option-toggle">
        <input type="checkbox" ${settings.automaticEnabled ? "checked" : ""}
          data-irrigation-row="${escapeHtml(row.key)}"
          data-irrigation-channel="${channel.key}"
          data-irrigation-field="automaticEnabled" />
        <span>Enable automatic ${escapeHtml(channel.label.toLowerCase())}</span>
      </label>
      <div class="field">
        <div class="field__hint">Starts when the live reading is critically low and stops as soon as it is back in the normal range.</div>
      </div>
      <div class="irrigation-status ${automaticRunning ? "is-active" : ""}">
        ${automaticRunning
          ? "Running automatically"
          : !settings.automaticEnabled
            ? "Automatic solution disabled"
            : !sensorAvailable
              ? "Waiting for live sensor"
              : needsSolution ? "Below crop minimum" : "Within crop target"}
      </div>
    `;
  } else if (row.mode === "schedule") {
    controls = `
      <label class="irrigation-option-toggle">
        <input type="checkbox" ${settings.scheduleEnabled ? "checked" : ""} ${scheduleRunning ? "disabled" : ""}
          data-irrigation-row="${escapeHtml(row.key)}"
          data-irrigation-channel="${channel.key}"
          data-irrigation-field="scheduleEnabled" />
        <span>Include in this row's schedule</span>
      </label>
      <div class="irrigation-row-fields">
        <div class="field">
          <label class="field__label">Start time</label>
          <input class="input" type="time" value="${escapeHtml(settings.scheduleStartTime)}"
            data-irrigation-row="${escapeHtml(row.key)}" data-irrigation-channel="${channel.key}"
            data-irrigation-field="scheduleStartTime" />
        </div>
        <div class="field">
          <label class="field__label">Duration (seconds)</label>
          <input class="input" type="number" min="1" value="${escapeHtml(settings.scheduleDuration)}"
            data-irrigation-row="${escapeHtml(row.key)}" data-irrigation-channel="${channel.key}"
            data-irrigation-field="scheduleDuration" />
        </div>
      </div>
      <div class="field">
        <label class="field__label">Frequency</label>
        <select class="select" data-irrigation-row="${escapeHtml(row.key)}"
          data-irrigation-channel="${channel.key}" data-irrigation-field="scheduleFrequency">
          ${IRRIGATION_FREQUENCIES.map((option) => `
            <option value="${option.value}" ${settings.scheduleFrequency === option.value ? "selected" : ""}>
              ${escapeHtml(option.label)}
            </option>
          `).join("")}
        </select>
      </div>
      <div class="irrigation-status ${scheduleRunning ? "is-active" : ""}">
        ${scheduleRunning
          ? "Running now — duration counted from the configured start time"
          : !settings.scheduleEnabled
            ? "Not included"
            : scheduleArmed ? "Waiting for configured start time" : "Schedule not started"}
      </div>
    `;
  } else {
    controls = `
      <div class="field">
        <label class="field__label">Run duration (seconds)</label>
        <input class="input" type="number" min="1" value="${escapeHtml(settings.manualDuration)}"
          data-irrigation-row="${escapeHtml(row.key)}"
          data-irrigation-channel="${channel.key}"
          data-irrigation-field="manualDuration" />
      </div>
      <div class="irrigation-status ${manualRunning ? "is-active" : ""}">
        ${manualRunning ? `Running on ${escapeHtml(row.label)}` : `Ready for ${escapeHtml(row.label)}`}
      </div>
      <button class="button ${manualRunning ? "button--danger" : "button--primary"} button--full"
        type="button" data-action="toggle-row-manual-irrigation"
        data-row="${escapeHtml(row.key)}" data-channel="${channel.key}">
        ${manualRunning ? `Stop ${escapeHtml(channel.label)}` : `Start ${escapeHtml(channel.label)}`}
      </button>
    `;
  }

  return irrigationTypeCardTemplate(channel, controls, automaticRunning || scheduleRunning || manualRunning);
}

// Shown on any row whose lime line is held for its tank check, whatever its
// mode: a manual Start is refused by the backend too until it is answered.
function limeTankHoldTemplate(row) {
  const pending = pendingLimeTankCheck(row);
  if (!pending) {
    return "";
  }
  return `
    <div class="lime-tank-hold" role="status">
      <span class="lime-tank-hold__icon" aria-hidden="true">${icon("alert-triangle")}</span>
      <div class="lime-tank-hold__copy">
        <strong>Lime Solution on hold</strong>
        <span>${escapeHtml(`Needs ${pending.label}. Confirm the tank to let it run.`)}</span>
      </div>
      <button class="button button--secondary lime-tank-hold__action" type="button"
        data-action="review-lime-tank" data-row="${escapeHtml(row.key)}">
        Check Tank
      </button>
    </div>
  `;
}

function irrigationRowControllerTemplate(row) {
  const scheduleArmed = Boolean(state.irrigationPage.scheduleArmedRows?.[row.key]);
  return `
    <article class="glass-card card page-stack irrigation-row-controller ${row.active ? "is-active" : "is-inactive"}">
      <div class="irrigation-row-controller__head">
        <div>
          <div class="irrigation-row-controller__title">
            <h3 class="section-title">${escapeHtml(row.label)}</h3>
            <span class="pill ${row.active ? "pill--normal" : ""}">${row.active ? "Active" : "Inactive"}</span>
          </div>
          <p class="section-copy">${escapeHtml(row.active ? row.crop : "No active cultivation. Add this row in Cultivation to unlock irrigation.")}</p>
        </div>
        ${row.active ? `<span class="irrigation-row-controller__mode">${escapeHtml(row.mode)}</span>` : ""}
      </div>

      <div class="irrigation-row-modes" aria-label="${escapeHtml(`${row.label} irrigation mode`)}">
        ${irrigationRowModeButtonTemplate(row, "automatic", "Automatic", "droplets")}
        ${irrigationRowModeButtonTemplate(row, "schedule", "Schedule", "calendar")}
        ${irrigationRowModeButtonTemplate(row, "manual", "Manual", "hand")}
      </div>

      ${row.active ? `
        ${limeTankHoldTemplate(row)}
        <div class="irrigation-type-grid irrigation-type-grid--row">
          ${IRRIGATION_CHANNELS.map((channel) => irrigationRowChannelTemplate(row, channel)).join("")}
        </div>
        ${row.mode === "schedule" ? `
          <div class="center-banner"><strong>Schedule:</strong> Starting it only arms the timer. Each enabled solution runs separately at its own start time.</div>
          <button class="button ${scheduleArmed ? "button--danger" : "button--primary"} button--full"
            type="button" data-action="toggle-row-schedule-irrigation" data-row="${escapeHtml(row.key)}">
            ${scheduleArmed ? `Stop ${escapeHtml(row.label)} Schedule` : `Start ${escapeHtml(row.label)} Schedule`}
          </button>
        ` : ""}
      ` : `
        <div class="irrigation-row-locked">
          ${icon("lock")}
          <span>Irrigation is safety-locked while this row has no active crop.</span>
        </div>
      `}
    </article>
  `;
}

function cultivationCropSelectTemplate(cropKeys, selectedCropType) {
  return `
    <select class="select cultivation-crop-select" id="cultivation-crop-type-select">
      <option value="">Select crop type</option>
      ${cropKeys.map((value) => {
        const label = CROP_LABELS[value];
        const meta = cropGrowthPeriodLabel(value);

        return `
          <option value="${value}" ${selectedCropType === value ? "selected" : ""}>
            ${escapeHtml(`${label} (${meta})`)}
          </option>
        `;
      }).join("")}
    </select>
  `;
}

function cultivationRowLabel(rowKey) {
  const selectedRow = CULTIVATION_ROW_OPTIONS.find((row) => row.key === rowKey);
  return selectedRow?.label || "Unassigned Row";
}

function activeCultivationForRow(rowKey, cultivations = state.activeCultivations) {
  if (!rowKey) {
    return null;
  }

  return cultivations.find((item) => item.rowKey === rowKey) || null;
}

function cultivationRowSelectTemplate(selectedRowKey, id = "cultivation-row-select") {
  return `
    <select class="select cultivation-crop-select" id="${id}">
      <option value="">Select planting row</option>
      ${CULTIVATION_ROW_OPTIONS.map((row) => {
        const assignedCultivation = activeCultivationForRow(row.key);
        const pendingRequest = assignedCultivation ? null : pendingCultivationRequestForRow(row.key);
        const occupied = Boolean(assignedCultivation || pendingRequest) && row.key !== selectedRowKey;
        const optionLabel = assignedCultivation
          ? `${row.label} - ${assignedCultivation.crop}${occupied ? " (In use)" : ""}`
          : pendingRequest
            ? `${row.label} - ${pendingRequest.cropName} (Waiting for approval)`
            : row.label;

        return `
          <option value="${row.key}" ${selectedRowKey === row.key ? "selected" : ""} ${occupied ? "disabled" : ""}>
            ${escapeHtml(optionLabel)}
          </option>
        `;
      }).join("")}
    </select>
  `;
}

function cultivationTemplate() {
  const {
    cropType,
    rowKey,
    plantingDate,
    harvestDate,
    daysToHarvest,
    successMessage,
  } = state.cultivation;
  const hasCultivationResult = Boolean(successMessage && cropType && plantingDate && harvestDate && daysToHarvest);
  return `
    <section class="page-stack cultivation-page">
      <div class="page-heading">
        <div>
          <h1>Cultivation Planning</h1>
          <p>Choose a crop and a row, and send the request. It is planted on the day an administrator approves it.</p>
        </div>
      </div>

      ${hasCultivationResult ? "" : `
        <article class="glass-card card page-stack cultivation-panel cultivation-panel--setup">
          <div class="card-head">
            <div class="inline-copy">
              <div class="spot-icon">${icon("sprout")}</div>
              <h3 class="section-title">Set New Cultivation</h3>
            </div>
          </div>

          <div class="input-grid input-grid--two cultivation-picker-grid">
            <div class="field">
              <label class="field__label">Crop Type</label>
              ${cultivationCropSelectTemplate(USER_CULTIVATION_CROP_KEYS, cropType)}
            </div>
            ${cultivationPlantingDateTemplate("planting-date-input")}
          </div>

          <div class="field">
            <label class="field__label" for="cultivation-row-select">Planting Row</label>
            ${cultivationRowSelectTemplate(rowKey)}
          </div>

          <button class="button button--primary button--full" type="button" data-action="calculate-harvest">
            Request Cultivation
          </button>
        </article>
      `}

      ${hasCultivationResult
        ? `
          ${cultivationResultsTemplate(
            cropType,
            plantingDate,
            harvestDate,
            daysToHarvest,
            recommendedCultivationParameters(state.cultivation),
          )}
        `
        : ""}

      <article class="glass-card card page-stack cultivation-panel cultivation-panel--active">
        ${activeCultivationsPanelContentTemplate()}
      </article>
    </section>
  `;
}

function cultivationSetupModalTemplate() {
  const {
    cropType,
    rowKey,
  } = state.cultivation;
  const hasRecommendedProfile = supportsRecommendedCultivation(cropType);
  const cropName = selectedCultivationName() || "Cultivation";
  const growthDaysLabel = cropGrowthPeriodLabel(cropType);

  return `
    <div class="overlay overlay--center">
      <div class="modal modal--cultivation">
        <div class="modal__header">
          <div class="card-head">
            <div>
              <h3 class="section-title cultivation-modal__title">${escapeHtml(cropName)} Setup</h3>
              <p class="section-copy">Review the crop details below, then send the request. It starts once an administrator approves it.</p>
            </div>
            <button class="icon-button" type="button" data-action="close-cultivation-setup">
              ${icon("close")}
            </button>
          </div>
        </div>

        <div class="modal__body page-stack cultivation-modal__body">
          <div class="center-banner cultivation-inline-banner">
            ${hasRecommendedProfile
              ? `Recommended harvest window for ${escapeHtml(cropName)} is ${escapeHtml(growthDaysLabel)}.`
              : "Recommended cultivation setup is available for preset crops only."}
          </div>

          <div class="input-grid input-grid--two cultivation-modal__fields">
            ${cultivationPlantingDateTemplate("planting-date-input-modal")}
            <div class="field">
              <label class="field__label">Selected Crop</label>
              <div class="center-banner cultivation-selected-crop">${escapeHtml(cropName)}</div>
            </div>
          </div>

          <div class="field">
            <label class="field__label" for="cultivation-row-select-modal">Planting Row</label>
            ${cultivationRowSelectTemplate(rowKey, "cultivation-row-select-modal")}
          </div>

          <div class="page-stack cultivation-mode-panel">
            <div>
              <h4 class="section-title">Recommended Parameters</h4>
              <p class="section-copy">User accounts use the Department of Agriculture reference range only.</p>
            </div>

            <div class="cultivation-parameter-selection is-selected">
              <div class="cultivation-parameter-selection__header">
                <strong>Recommended Selected</strong>
                <div class="cultivation-parameter-selection__actions">
                  <span class="cultivation-parameter-selection__tag">${escapeHtml(cropName)} Target Range</span>
                  <button
                    class="button button--secondary cultivation-parameter-selection__button"
                    type="button"
                    data-action="open-cultivation-parameter-preview"
                  >
                    Review
                  </button>
                </div>
              </div>
              <p class="section-copy">
                ${escapeHtml(cropName)} will use the Department of Agriculture reference range. Click Review if you want to check the values again.
              </p>
            </div>
          </div>

          <div class="modal__actions cultivation-modal__actions">
            <button class="button button--secondary" type="button" data-action="close-cultivation-setup">Cancel</button>
            <button
              class="button button--primary"
              type="button"
              data-action="calculate-harvest"
              ${!canCalculateCultivation() ? "disabled" : ""}
            >
              Send Request
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function cultivationParameterPreviewModalTemplate() {
  const { cropType, parameterPreviewMode } = state.cultivation;

  if (parameterPreviewMode !== "recommended" || !supportsRecommendedCultivation(cropType)) {
    return "";
  }

  const cropName = selectedCultivationName() || CROP_LABELS[cropType] || "Cultivation";
  const displayedParameters = recommendedCultivationParameters(state.cultivation);
  const previewTitle = "Recommended Parameters";
  const previewCopy = `Department of Agriculture reference range for ${cropName}.`;

  return `
    <div class="overlay overlay--center overlay--cultivation-preview">
      <div class="modal modal--cultivation cultivation-preview-modal">
        <div class="modal__header">
          <div class="card-head">
            <div>
              <p class="cultivation-preview-modal__eyebrow">${escapeHtml(cropName)} Target Range</p>
              <h3 class="section-title cultivation-modal__title">${previewTitle}</h3>
              <p class="section-copy">${escapeHtml(previewCopy)}</p>
            </div>
          </div>
        </div>

        <div class="modal__body page-stack cultivation-preview-modal__body">
          <div class="cultivation-da-reference cultivation-da-reference--preview">
            <img
              class="cultivation-da-reference__logo"
              src="${DA_LOGO_PATH}"
              alt="Department of Agriculture logo"
            />
            <div>
              <h5 class="cultivation-da-reference__title">Department of Agriculture Reference Profile</h5>
              <p class="section-copy">
                The recommended values below will be used as the active monitoring range for ${escapeHtml(cropName)}.
              </p>
            </div>
          </div>

          <div class="grid cultivation-parameter-grid">
            ${CULTIVATION_PARAMETER_FIELDS.map((field) =>
              cultivationRecommendedParameterCardTemplate(field, displayedParameters[field.key], cropName),
            ).join("")}
          </div>

          <div class="modal__actions cultivation-modal__actions cultivation-preview-modal__actions">
            <button class="button button--danger" type="button" data-action="close-cultivation-parameter-preview">
              Cancel
            </button>
            <button class="button button--primary" type="button" data-action="confirm-cultivation-parameter-preview">
              Confirm
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function loginTemplate() {
  return `
    <section class="login-screen">
      <article class="glass-card login-card">
        <div class="login-card__brand">
          <img class="login-card__logo" src="${LOGO_PATH}" alt="ICuCrops Logo" />
          <h1 class="login-card__title">Login to ICuCrops</h1>
          <p class="login-card__copy">Sign in to access your monitoring dashboard.</p>
        </div>

        <form class="login-form" id="login-form">
          <label class="field">
            <span class="field__label">Email</span>
            <div class="login-input">
              <span class="login-input__icon" aria-hidden="true">${icon("mail")}</span>
              <input
                class="input login-input__control"
                id="login-email-input"
                type="email"
                inputmode="email"
                autocomplete="email"
                placeholder="Enter your email"
                value="${escapeHtml(state.loginForm.email)}"
                required
              />
            </div>
          </label>

          <label class="field">
            <span class="field__label">Password</span>
            <div class="login-input login-input--password">
              <span class="login-input__icon" aria-hidden="true">${icon("lock")}</span>
              <input
                class="input login-input__control login-input__control--password"
                id="login-password-input"
                type="password"
                autocomplete="current-password"
                placeholder="Enter your password"
                value="${escapeHtml(state.loginForm.password)}"
                required
              />
              <button
                class="login-input__toggle"
                type="button"
                data-action="toggle-password-visibility"
                data-target="login-password-input"
                aria-label="Show password"
              >
                <span class="login-input__toggle-icon" data-password-icon aria-hidden="true">${icon("eye-off")}</span>
              </button>
            </div>
          </label>

          <div class="login-form__meta">
            <button class="login-link" type="button" data-action="forgot-password">Forgot Password?</button>
          </div>

          <button class="button button--primary button--full" type="submit" data-action="submit-login">
            Login
          </button>
        </form>
      </article>
    </section>
  `;
}

function sensorCardTemplate(sensor) {
  const displayStatus = effectiveSensorStatus(sensor);
  const statusLabel = effectiveSensorStatusLabel(sensor);
  const currentValue = effectiveSensorValue(sensor);
  const currentUnit = effectiveSensorUnit(sensor);
  const progressValue = effectiveSensorPercentage(sensor);
  return `
    <article class="glass-card card sensor-card sensor-card--compact ${glowClass(displayStatus)}" data-action="open-sensor-detail" data-id="${sensor.id}">
      <div class="sensor-card__top">
        <div class="sensor-card__icon">${icon(sensor.icon)}</div>
        <div class="pill ${pillClass(displayStatus)}">
          ${icon(statusIconName(displayStatus), "icon")}
          <span>${escapeHtml(statusLabel)}</span>
        </div>
      </div>
      <div>
        <div class="sensor-card__name">${escapeHtml(sensor.name)}</div>
        <p class="sensor-card__value">${escapeHtml(currentValue)}${currentUnit ? ` <span>${escapeHtml(currentUnit)}</span>` : ""}</p>
      </div>
      <div class="progress-track">
        <div class="progress-fill ${progressClass(displayStatus)}" style="width: ${progressValue}%"></div>
      </div>
    </article>
  `;
}

function sensorHealthItems() {
  return SENSOR_HEALTH.map((item) => ({
    name: item.name,
    ...sensorHealthStatus(item.key),
  }));
}

// True/false once the backend has ever tracked the owning ESP32 board's MQTT
// status (its Last Will fires "offline" the instant that board's connection
// drops, so this is immediate); null before that, meaning no board has ever
// reported in and the caller should fall back to judging the last reading's
// age instead.
function metricConnectionState(row, metricKey) {
  if (metricKey === "temp" || metricKey === "humidity") {
    return typeof SHARED_DHT22_METRICS.connected === "boolean" ? SHARED_DHT22_METRICS.connected : null;
  }
  const connectionField = metricKey === "moisture" ? "moisture" : "rs485";
  const value = row?.connected?.[connectionField];
  return typeof value === "boolean" ? value : null;
}

function sensorHealthStatus(sensorKey) {
  if (sensorKey === "dht22") {
    const hasReading = [SHARED_DHT22_METRICS.temp, SHARED_DHT22_METRICS.humidity]
      .some((value) => Number.isFinite(Number.parseFloat(value)));
    const connected = metricConnectionState(null, "temp");
    const online = connected === null ? hasReading && dashboardDht22ReadingIsFresh() : connected;
    if (online) {
      return { status: "online", detail: "Fresh shared reading", badge: "Online" };
    }
    return {
      status: "offline",
      detail: hasReading ? "DHT22 board is offline" : "No DHT22 reading",
      badge: "Offline",
    };
  }
  // Exactly the verdict the row cards reach, through the same helper: prefer
  // the board's MQTT status -- its Last Will lands within seconds of the cable
  // or the power going -- and fall back to the presence window, never to the
  // fifteen-minute window that only decides whether a value is worth drawing.
  // This panel used to consult that longer one on its own, which is how a
  // board could read "Offline" on its row card and "Online" here at once.
  const availableCount = IOT_DEVICE_ROWS.filter((row) => {
    if (!isRowSensorPoweredOn(row.key, sensorKey)) {
      return false;
    }
    const metricKeys = sensorKey === "moisture" ? ["moisture"] : ["ec", "ph"];
    if (!metricKeys.some((metricKey) => Number.isFinite(Number.parseFloat(iotRowMetricValue(row, metricKey))))) {
      return false;
    }
    return metricKeys.some((metricKey) => !iotRowMetricIsOffline(row, iotRowMetricConfig(metricKey)));
  }).length;
  if (availableCount === IOT_DEVICE_ROWS.length) {
    return { status: "online", detail: `${availableCount}/${IOT_DEVICE_ROWS.length} rows online`, badge: "Online" };
  }
  if (availableCount === 0) {
    return { status: "offline", detail: "No rows online", badge: "Offline" };
  }
  return { status: "partial", detail: `${availableCount}/${IOT_DEVICE_ROWS.length} rows online`, badge: "Partial" };
}

function iotRowMetricConfig(metricKey) {
  return IOT_ROW_METRICS.find((metric) => metric.key === metricKey) || IOT_ROW_METRICS[0];
}

function rowSensorPowerStorageKey(rowKey, metricKey) {
  if (metricKey === "temp" || metricKey === "humidity" || metricKey === "dht22") {
    return "dht22";
  }

  if (metricKey === "ec" || metricKey === "ph" || metricKey === "rs485") {
    return `${rowKey}-rs485`;
  }

  return `${rowKey}-${metricKey}`;
}

function rowSensorPowerMode(rowKey, metricKey) {
  const storageKey = rowSensorPowerStorageKey(rowKey, metricKey);
  if (storageKey === "dht22") {
    return state.sensorsPage.sensorPower.dht22 || state.sensorsPage.rowSensorPower.dht22 || "on";
  }
  return state.sensorsPage.rowSensorPower[storageKey] || "on";
}

function isRowSensorPoweredOn(rowKey, metricKey) {
  return rowSensorPowerMode(rowKey, metricKey) === "on";
}

function iotRowMetricValue(row, metricKey) {
  if (metricKey === "temp" || metricKey === "humidity") {
    return SHARED_DHT22_METRICS[metricKey];
  }

  return row[metricKey];
}

function iotRowMetricRange(row, metric) {
  const cultivation = activeCultivationForRow(row.key);
  const configured = cultivation?.parameters?.[metric.key];
  const minimum = Number.parseFloat(configured?.min);
  const maximum = Number.parseFloat(configured?.max);
  if (Number.isFinite(minimum) && Number.isFinite(maximum) && minimum < maximum) {
    return { min: minimum, max: maximum };
  }
  return { min: metric.normalMin, max: metric.normalMax };
}

// What the drawer needs to show the range a reading is being judged against,
// and to offer the shortcut to where that range is set. A row with no active
// cultivation has no parameters at all, which is a different thing from one
// left on the recommended preset -- the drawer says so rather than showing a
// range nobody chose.
function sensorParameterContext(rowKey, metricKey) {
  const field = CULTIVATION_PARAMETER_FIELDS.find((item) => item.sensorId === metricKey);
  if (!field) {
    return null;
  }

  const cultivation = activeCultivationForRow(rowKey);
  if (!cultivation) {
    return { field, cultivation: null, mode: "", range: null, isCustom: false };
  }

  const isCustom = String(cultivation.parameterMode || "").trim().toLowerCase() === "custom";
  const configured = cultivation.parameters && typeof cultivation.parameters === "object"
    ? cultivation.parameters[metricKey]
    : null;
  const minimum = Number.parseFloat(configured?.min);
  const maximum = Number.parseFloat(configured?.max);
  const range = Number.isFinite(minimum) && Number.isFinite(maximum) && minimum < maximum
    ? { min: minimum, max: maximum }
    : null;

  return {
    field,
    cultivation,
    mode: isCustom ? "custom" : "recommended",
    range,
    isCustom,
  };
}

function soilReadingAtBoardPrecision(value, decimals) {
  return Number(Number.parseFloat(value).toFixed(decimals));
}

function iotReadingLabel(value, unit = "") {
  const numericValue = Number.parseFloat(value);
  if (!Number.isFinite(numericValue)) {
    return "No data";
  }
  return `${numericValue}${unit ? ` ${unit}` : ""}`;
}

// Prefers the board's actual MQTT status (instant: its Last Will fires the
// moment the connection drops) over the last reading's age, which only ever
// caught up to the truth up to DASHBOARD_SENSOR_MAX_AGE_MS (15 minutes) later.
function iotRowMetricIsOffline(row, metric) {
  const connected = metricConnectionState(row, metric.key);
  if (connected !== null) {
    return !connected;
  }
  return !dashboardReadingIsPresent(dashboardRowMetricCapturedAt(row, metric.key));
}

function iotRowMetricStatus(row, metric) {
  if (!isRowSensorPoweredOn(row.key, metric.key)) {
    return "critical";
  }

  const value = iotRowMetricValue(row, metric.key);
  const numericValue = Number.parseFloat(value);
  if (!Number.isFinite(numericValue)) {
    return "warning";
  }
  if (iotRowMetricIsOffline(row, metric)) {
    return "warning";
  }
  const range = iotRowMetricRange(row, metric);
  // Three levels, not two. This used to return "warning" for anything outside
  // the range no matter how far outside, so every out-of-range card on the
  // dashboard was the same amber and nothing was ever red -- a pH of 6.9 read
  // exactly like a pH of 9, and a farm looking at a screen full of amber has
  // no way to tell which row needs them now.
  //
  // The margin is per metric because the ranges are not comparable: 15 points
  // of moisture is a real swing, 15 pH does not exist. Inside the margin is
  // the "medyo lampas" band and stays amber; past it the reading is far enough
  // outside that the crop is actually in trouble.
  const margin = iotRowMetricCriticalMargin(metric);
  if (numericValue < range.min - margin || numericValue > range.max + margin) {
    return "critical";
  }
  if (numericValue < range.min || numericValue > range.max) {
    return "warning";
  }

  return "normal";
}

// How far past its range a reading has to be before the card turns red.
// Falls back to a fifth of the metric's own display span, so a metric added
// without a margin still gets a proportionate one rather than never going
// critical at all.
function iotRowMetricCriticalMargin(metric) {
  const configured = Number.parseFloat(metric?.criticalMargin);
  if (Number.isFinite(configured) && configured > 0) {
    return configured;
  }
  const span = Number.parseFloat(metric?.displayMax) - Number.parseFloat(metric?.displayMin);
  return Number.isFinite(span) && span > 0 ? span / 5 : 0;
}

function iotRowMetricStatusLabel(row, metric) {
  if (!isRowSensorPoweredOn(row.key, metric.key)) {
    return "Off";
  }
  if (!Number.isFinite(Number.parseFloat(iotRowMetricValue(row, metric.key)))) {
    return "No data";
  }
  if (iotRowMetricIsOffline(row, metric)) {
    return "Offline";
  }
  const status = iotRowMetricStatus(row, metric);
  if (status === "critical") {
    // Which side it is out on, not just that it is out. "Critical" alone
    // leaves the farm to open the card to find out whether to water a row or
    // stop watering it, and those are opposite actions.
    //
    // "critical" had no branch here at all until recently, so a red card
    // carried the word "Normal" -- the colour said one thing, the label the
    // other.
    //
    // A warning stays plain "Warning". It is the level that does not need
    // acting on yet, so naming the side there only adds words to four cards
    // out of five and makes the one that does matter harder to pick out.
    const value = Number.parseFloat(iotRowMetricValue(row, metric.key));
    const range = iotRowMetricRange(row, metric);
    if (Number.isFinite(value)) {
      return value < range.min ? "Critical Low" : "Critical High";
    }
    return "Critical";
  }
  if (status === "warning") {
    return "Warning";
  }
  return "Normal";
}

function iotRowMetricPercentage(row, metric) {
  if (!isRowSensorPoweredOn(row.key, metric.key)) {
    return 0;
  }

  const value = iotRowMetricValue(row, metric.key);
  if (!Number.isFinite(Number.parseFloat(value))) {
    return 0;
  }
  if (!dashboardReadingIsFresh(dashboardRowMetricCapturedAt(row, metric.key))) {
    return 0;
  }
  const span = metric.displayMax - metric.displayMin;
  if (!span) {
    return 0;
  }

  const percent = ((value - metric.displayMin) / span) * 100;
  return Math.max(0, Math.min(100, percent));
}

function iotRowWarningCount(row) {
  return IOT_ROW_METRICS.filter((metric) => iotRowMetricStatus(row, metric) === "warning").length;
}

// A switched-off sensor also reports "critical"; that is the Off badge's job,
// not a reading out of range, so only powered sensors count here.
function iotRowCriticalCount(row) {
  return IOT_ROW_METRICS.filter((metric) =>
    isRowSensorPoweredOn(row.key, metric.key) && iotRowMetricStatus(row, metric) === "critical").length;
}

function iotMonitorGroupStatus(row, metricKeys) {
  const statuses = metricKeys.map((metricKey) => iotRowMetricStatus(row, iotRowMetricConfig(metricKey)));
  if (statuses.every((status) => status === "critical")) {
    return "critical";
  }
  if (statuses.includes("critical") || statuses.includes("warning")) {
    return "warning";
  }
  return "normal";
}

function iotMonitorGroupPercentage(row, metricKeys) {
  return Math.max(...metricKeys.map((metricKey) => iotRowMetricPercentage(row, iotRowMetricConfig(metricKey))));
}

// Same ladder as iotRowMetricStatusLabel, for a card that fronts several metrics
// sharing one board: it only reads "Offline" when every powered metric on that
// board is offline, so a live ESP32 with an out-of-range reading still says
// "Warning".
function iotMonitorGroupStatusLabel(row, metricKeys) {
  const powered = metricKeys
    .map((metricKey) => iotRowMetricConfig(metricKey))
    .filter((metric) => isRowSensorPoweredOn(row.key, metric.key));
  if (!powered.length) {
    return "Off";
  }
  if (powered.every((metric) => !Number.isFinite(Number.parseFloat(iotRowMetricValue(row, metric.key))))) {
    return "No data";
  }
  if (powered.every((metric) => iotRowMetricIsOffline(row, metric))) {
    return "Offline";
  }
  return iotMonitorGroupStatus(row, metricKeys) === "warning" ? "Warning" : "Normal";
}

function iotRowStatusTone(row) {
  const statuses = IOT_ROW_METRICS.map((metric) => iotRowMetricStatus(row, metric));
  if (statuses.every((status) => status === "critical")) {
    return "critical";
  }
  if (statuses.includes("critical") || statuses.includes("warning")) {
    return "warning";
  }
  return "normal";
}

function iotRowStatusLabel(row) {
  const activeCount = IOT_ROW_METRICS.filter((metric) => isRowSensorPoweredOn(row.key, metric.key)).length;
  if (!activeCount) {
    return "All Off";
  }

  // Criticals were never counted here, so a row with four red cards carried
  // "Normal" in its header -- the one place a farmer glances first.
  const criticals = iotRowCriticalCount(row);
  if (criticals) {
    return `${criticals} Critical`;
  }

  const warnings = iotRowWarningCount(row);
  if (warnings) {
    return `${warnings} Warning${warnings > 1 ? "s" : ""}`;
  }

  return "Normal";
}

function iotRowSensorDetail(row, metricKey) {
  const metric = iotRowMetricConfig(metricKey);
  const range = iotRowMetricRange(row, metric);
  return {
    id: `${row.key}-${metric.key}`,
    name: metric.label,
    deviceName: metric.shared ? `${row.label} Shared DHT22` : `${row.label} ${metric.deviceName}`,
    powerKey: rowSensorPowerStorageKey(row.key, metric.key),
    value: iotRowMetricValue(row, metric.key),
    unit: metric.unit,
    icon: metric.icon,
    status: iotRowMetricStatus(row, metric),
    percentage: iotRowMetricPercentage(row, metric),
    min: range.min,
    max: range.max,
    alertMode: DEFAULT_ALERT_MODE,
    rowKey: row.key,
    rowLabel: row.label,
    parameter: sensorParameterContext(row.key, metric.key),
  };
}

function iotRowRs485Detail(row) {
  const ecMetric = iotRowMetricConfig("ec");
  const phMetric = iotRowMetricConfig("ph");
  const ecRange = iotRowMetricRange(row, ecMetric);
  return {
    id: `${row.key}-rs485`,
    name: "RS485 Multi Sensor",
    deviceName: `${row.label} RS485 Multi Sensor`,
    powerKey: rowSensorPowerStorageKey(row.key, "rs485"),
    value: row.ec,
    unit: ecMetric.unit,
    heroValue: `Nutrients ${iotReadingLabel(row.ec, ecMetric.unit)}  |  pH ${iotReadingLabel(row.ph, phMetric.unit)}`,
    icon: "activity",
    status: iotMonitorGroupStatus(row, ["ec", "ph"]),
    percentage: iotMonitorGroupPercentage(row, ["ec", "ph"]),
    min: ecRange.min,
    max: ecRange.max,
    alertMode: DEFAULT_ALERT_MODE,
    rowKey: row.key,
    rowLabel: row.label,
    // The RS485 board reports two metrics, so the drawer lists both ranges.
    parameters: [
      sensorParameterContext(row.key, "ec"),
      sensorParameterContext(row.key, "ph"),
    ].filter(Boolean),
    detailMetrics: [
      { label: "Soil Nutrients", value: iotReadingLabel(row.ec, ecMetric.unit) },
      { label: "Soil pH", value: iotReadingLabel(row.ph, phMetric.unit) },
    ],
  };
}

function findIotRowSensorById(sensorId) {
  const row = IOT_DEVICE_ROWS.find((item) => sensorId.startsWith(`${item.key}-`));
  if (!row) {
    return null;
  }

  const metricKey = sensorId.slice(`${row.key}-`.length);
  if (metricKey === "rs485") {
    return iotRowRs485Detail(row);
  }

  if (!IOT_ROW_METRICS.some((metric) => metric.key === metricKey)) {
    return null;
  }

  return iotRowSensorDetail(row, metricKey);
}

function findDashboardSensorById(sensorId) {
  return state.dashboardSensors.find((item) => item.id === sensorId) || findIotRowSensorById(sensorId);
}

function iotDashboardMetricTemplate(row, metric) {
  const status = iotRowMetricStatus(row, metric);
  // The sensor's own power switch, not its reading. These read
  // `status !== "critical"` until criticalMargin existed, which was
  // harmless only because no metric could reach "critical" -- every
  // out-of-range reading stopped at "warning", so this was always true.
  // The moment a third level was added, a reading far outside its range
  // started printing "OFF" in place of the number, which is the one
  // thing a critical card most needs to show.
  const poweredOn = isRowSensorPoweredOn(row.key, metric.key);
  const value = iotRowMetricValue(row, metric.key);
  const percentage = iotRowMetricPercentage(row, metric);
  return `
    <article class="metric-card iot-monitor-card ${glowClass(status)} ${poweredOn ? "" : "iot-monitor-card--off"}" data-action="open-sensor-detail" data-id="${row.key}-${metric.key}">
      <div class="sensor-card__top iot-monitor-card__top">
        <span class="sensor-card__icon iot-row-metric__icon">${icon(metric.icon)}</span>
        <span class="pill ${pillClass(status)}">${escapeHtml(iotRowMetricStatusLabel(row, metric))}</span>
      </div>
      <div>
        <div class="sensor-card__name">${escapeHtml(metric.label)}</div>
        <p class="sensor-card__value iot-monitor-card__value">
        ${poweredOn ? escapeHtml(iotReadingLabel(value, metric.unit)) : "OFF"}
        </p>
      </div>
      <div class="progress-track">
        <div class="progress-fill ${progressClass(status)}" style="width: ${percentage}%"></div>
      </div>
      <div class="section-copy iot-monitor-card__source">${escapeHtml(metric.shared ? "Shared DHT22 Monitor" : metric.cardSource || metric.deviceName)}</div>
    </article>
  `;
}

function iotDashboardRowCardTemplate(row) {
  const tone = iotRowStatusTone(row);
  const warnings = iotRowWarningCount(row) + iotRowCriticalCount(row);
  const cultivation = activeCultivationForRow(row.key);
  const title = cultivation ? cultivation.crop : row.label;
  const activityLabel = cultivation ? "Active" : "Not Active";
  const activityPillClass = cultivation ? "pill--normal" : "pill--critical";
  const cultivationCopy = cultivation
    ? `${row.label} is active and currently growing ${cultivation.crop}.`
    : `${row.label} is not active right now.`;
  return `
    <article class="glass-card card page-stack iot-row-card ${glowClass(tone)}">
      <div class="card-head iot-row-card__head">
        <div>
          <div class="iot-row-card__eyebrow">${escapeHtml(row.label)}</div>
          <h3 class="section-title">${escapeHtml(title)}</h3>
          <p class="section-copy iot-row-card__subcopy">
            ${escapeHtml(cultivationCopy)}
            ${" "}
            ${escapeHtml(warnings ? `${warnings} metric warning${warnings > 1 ? "s" : ""} detected in this row.` : "All monitored values are within the normal range.")}
          </p>
        </div>
        <div class="iot-row-card__summary">
          <span class="pill ${activityPillClass}">${escapeHtml(activityLabel)}</span>
          <span class="pill ${pillClass(tone)}">${escapeHtml(iotRowStatusLabel(row))}</span>
        </div>
      </div>
      <div class="iot-row-card__metrics">
        ${iotDashboardMetricTemplate(row, iotRowMetricConfig("moisture"))}
        ${iotDashboardMetricTemplate(row, iotRowMetricConfig("ec"))}
        ${iotDashboardMetricTemplate(row, iotRowMetricConfig("ph"))}
        ${iotDashboardMetricTemplate(row, iotRowMetricConfig("temp"))}
        ${iotDashboardMetricTemplate(row, iotRowMetricConfig("humidity"))}
      </div>
    </article>
  `;
}

function sensorPowerKey(sensorOrKey) {
  if (typeof sensorOrKey === "object" && sensorOrKey) {
    return sensorOrKey.powerKey || sensorOrKey.id || "";
  }
  return sensorOrKey === "temp" || sensorOrKey === "humidity" ? "dht22" : String(sensorOrKey || "");
}

function sensorPowerMode(sensorOrKey) {
  const key = sensorPowerKey(sensorOrKey);
  return state.sensorsPage.sensorPower[key] || state.sensorsPage.rowSensorPower?.[key] || "on";
}

function isSensorPoweredOn(sensorOrKey, useDirectKey = false) {
  const key = useDirectKey ? String(sensorOrKey || "") : sensorPowerKey(sensorOrKey);
  return sensorPowerMode(key) === "on";
}

function effectiveSensorHasFreshReading(sensor) {
  const readingIsFresh = sensor?.id === "temp" || sensor?.id === "humidity"
    ? dashboardDht22ReadingIsFresh(sensor?.capturedAt)
    : dashboardReadingIsFresh(sensor?.capturedAt);
  return Number.isFinite(Number.parseFloat(sensor?.value)) && readingIsFresh;
}

function effectiveSensorStatus(sensor) {
  if (!isSensorPoweredOn(sensor)) {
    return "critical";
  }
  return effectiveSensorHasFreshReading(sensor) ? sensor.status : "warning";
}

function effectiveSensorStatusLabel(sensor) {
  if (!isSensorPoweredOn(sensor)) {
    return "Off";
  }
  if (!Number.isFinite(Number.parseFloat(sensor.value))) {
    return "No data";
  }
  return effectiveSensorHasFreshReading(sensor) ? capitalize(sensor.status) : "Offline";
}

function effectiveSensorValue(sensor) {
  return isSensorPoweredOn(sensor) ? iotReadingLabel(sensor.value) : "OFF";
}

function effectiveSensorUnit(sensor) {
  return isSensorPoweredOn(sensor) && Number.isFinite(Number.parseFloat(sensor.value)) ? sensor.unit : "";
}

function effectiveSensorPercentage(sensor) {
  return isSensorPoweredOn(sensor) && effectiveSensorHasFreshReading(sensor) ? sensor.percentage : 0;
}

function currentSensorReadingMarkup(sensor, readingLabel) {
  if (!sensor) {
    return "Unavailable";
  }

  if (!isSensorPoweredOn(sensor)) {
    return "Sensor is off";
  }

  if (!effectiveSensorHasFreshReading(sensor)) {
    return "Waiting for a fresh sensor reading";
  }

  return `${escapeHtml(readingLabel)}: ${escapeHtml(iotReadingLabel(sensor.value, sensor.unit))}`;
}

function sensorManagementCardTemplate(config) {
  const sensor = state.dashboardSensors.find((item) => item.id === config.sensorId);
  const powerMode = sensorPowerMode(config.powerKey);
  const poweredOn = powerMode === "on";

  return `
    <article class="glass-card card page-stack sensor-management-card" data-sensor-card="${escapeHtml(config.sensorId)}">
      <div class="card-head sensor-management-card__head">
        <div class="inline-copy sensor-management-card__copy">
          <div class="sensor-card__icon sensor-management-card__icon">${icon(config.icon)}</div>
          <div class="sensor-management-card__meta">
            <h3 class="section-title sensor-management-card__title">${escapeHtml(config.deviceName)}</h3>
            <p class="section-copy sensor-management-card__reading">${currentSensorReadingMarkup(sensor, config.readingLabel)}</p>
          </div>
        </div>
        <span class="pill ${poweredOn ? "pill--normal" : "pill--critical"} sensor-management-card__pill">${poweredOn ? "On" : "Off"}</span>
      </div>
      <div class="field sensor-management-card__field">
        <label class="field__label" for="sensor-power-${config.sensorId}">Sensor Power</label>
        <select class="select sensor-management-card__select" id="sensor-power-${config.sensorId}" data-sensor-power="${config.powerKey}">
          <option value="on" ${powerMode === "on" ? "selected" : ""}>On</option>
          <option value="off" ${powerMode === "off" ? "selected" : ""}>Off</option>
        </select>
      </div>
      <div class="timeline-card sensor-management-card__state">
        <div class="section-copy">Current State</div>
        <p class="sensor-management-card__state-value" style="color: ${poweredOn ? "var(--green-800)" : "var(--red-500)"};">
          ${poweredOn ? "Running" : "Disabled"}
        </p>
      </div>
    </article>
  `;
}

function actuatorModeLabel(mode) {
  if (mode === "automatic") {
    return "Automatic";
  }
  if (mode === "on") {
    return "On";
  }
  return "Off";
}

function actuatorModeButtonTemplate(control, value, label, iconName) {
  // With no mode yet, the actuator's own resting mode: Off for misting.
  const mode = state.sensorsPage.actuatorMode[control.key]
    || control.restingMode
    || "automatic";
  const active = mode === value;
  return `
    <button
      class="actuator-mode-button ${active ? "is-active" : ""}"
      type="button"
      data-action="set-actuator-mode"
      data-actuator="${escapeHtml(control.key)}"
      data-mode="${value}"
      aria-pressed="${String(active)}"
    >
      ${icon(iconName)}
      <span>${escapeHtml(label)}</span>
    </button>
  `;
}

function actuatorRunDuration(actuatorKey) {
  // Empty is a real answer, not a missing one: it means "stay on until I press
  // Off". Substituting a default here made clearing the box impossible -- the
  // setter stored 0 correctly and the next render put 30 straight back, so the
  // field claimed a timer the operator had deliberately removed.
  const stored = Number.parseInt(state.sensorsPage.actuatorDuration?.[actuatorKey], 10);
  if (Number.isFinite(stored) && stored > 0) {
    return String(Math.min(ACTUATOR_MAX_DURATION_SECONDS, Math.max(ACTUATOR_MIN_DURATION_SECONDS, stored)));
  }
  return "";
}

function setActuatorRunDuration(actuatorKey, rawValue) {
  if (!state.sensorsPage.actuatorDuration) {
    state.sensorsPage.actuatorDuration = {};
  }
  const parsed = Number.parseInt(rawValue, 10);
  // An empty or unreadable box means "stay on until I press Off", which is
  // what this control did before it had a duration at all.
  state.sensorsPage.actuatorDuration[actuatorKey] =
    Number.isFinite(parsed) && parsed > 0
      ? Math.min(ACTUATOR_MAX_DURATION_SECONDS, Math.max(ACTUATOR_MIN_DURATION_SECONDS, parsed))
      : 0;
  writeSensorControlCache(state.sensorsPage);
}

function actuatorControlCardTemplate(control) {
  // With no mode yet, the actuator's own resting mode: Off for misting.
  const mode = state.sensorsPage.actuatorMode[control.key]
    || control.restingMode
    || "automatic";

  return `
    <article class="glass-card card page-stack sensor-management-card sensor-management-card--actuator" data-actuator-card="${escapeHtml(control.key)}">
      <div class="card-head sensor-management-card__head">
        <div class="inline-copy sensor-management-card__copy">
          <div class="sensor-card__icon sensor-management-card__icon">${icon(control.icon)}</div>
          <div class="sensor-management-card__meta">
            <h3 class="section-title sensor-management-card__title">${escapeHtml(control.label)}</h3>
            <p class="section-copy sensor-management-card__reading">${escapeHtml(control.copy)}</p>
          </div>
        </div>
        <span class="pill ${mode === "off" ? "pill--critical" : "pill--normal"} sensor-management-card__pill">${escapeHtml(actuatorModeLabel(mode))}</span>
      </div>
      ${control.pendingHardware
        ? `<p class="section-copy sensor-management-card__pending">${icon("info")}<span>No controller wired yet. The mode is saved and applies once the hardware is installed.</span></p>`
        : ""}
      <div class="field sensor-management-card__field">
        <span class="field__label">Mode</span>
        <div class="actuator-mode-group">
          ${actuatorModeButtonTemplate(control, "automatic", "Automatic", "activity")}
          ${actuatorModeButtonTemplate(control, "on", "On", "zap")}
          ${actuatorModeButtonTemplate(control, "off", "Off", "x-circle")}
        </div>
      </div>
      ${control.timed ? `
      <div class="field sensor-management-card__field">
        <label class="field__label">Run duration (seconds)</label>
        <input class="input" type="number" min="${ACTUATOR_MIN_DURATION_SECONDS}"
          max="${ACTUATOR_MAX_DURATION_SECONDS}"
          placeholder="${ACTUATOR_DURATION_PLACEHOLDER_SECONDS}"
          value="${escapeHtml(actuatorRunDuration(control.key))}"
          data-actuator-duration="${escapeHtml(control.key)}" />
      </div>` : ""}
      <div class="timeline-card sensor-management-card__state">
        <div class="section-copy">Current Mode</div>
        <p class="sensor-management-card__state-value" style="color: ${mode === "off" ? "var(--red-500)" : "var(--green-800)"};">
          ${escapeHtml(actuatorModeLabel(mode))}
        </p>
      </div>
    </article>
  `;
}

function healthItemTemplate(sensor) {
  const online = sensor.status === "online";
  const partial = sensor.status === "partial";
  const pillTone = partial ? "pill--warning" : online ? "pill--normal" : "pill--critical";
  const dotClass = partial ? "status-dot--warning" : online ? "status-dot--online" : "status-dot--offline";
  const iconColor = partial ? "var(--amber-500)" : online ? "var(--green-600)" : "var(--red-500)";
  return `
    <div class="health-item">
      <div class="health-item__meta">
        <span class="nav-button__icon" style="color: ${iconColor}">${icon(online || partial ? "wifi" : "wifi-off")}<span class="status-dot ${dotClass}"></span></span>
        <div>
          <strong>${escapeHtml(sensor.name)}</strong>
          <div class="section-copy">${escapeHtml(sensor.detail)}</div>
        </div>
      </div>
      <span class="pill ${pillTone}">${escapeHtml(sensor.badge)}</span>
    </div>
  `;
}

function mobileHealthChipTemplate(sensor) {
  const tone = sensor.status === "online" ? "normal" : sensor.status === "partial" ? "warning" : "critical";
  return `
    <div class="mobile-health-chip mobile-health-chip--${tone}">
      <span>${escapeHtml(sensor.name)}</span>
      <strong>${escapeHtml(sensor.badge)}</strong>
    </div>
  `;
}

function soilAutomaticTemplate() {
  return `
    <div class="input-grid input-grid--two">
      <div class="field">
        <label class="field__label">Min Threshold (%)</label>
        <input class="input" type="number" value="45" />
      </div>
      <div class="field">
        <label class="field__label">Max Threshold (%)</label>
        <input class="input" type="number" value="70" />
      </div>
    </div>
  `;
}

function soilScheduleTemplate() {
  return `
    <div class="input-grid input-grid--two">
      <div class="field">
        <label class="field__label">Start Time</label>
        <input class="input" type="time" value="06:00" />
      </div>
      <div class="field">
        <label class="field__label">Duration (seconds)</label>
        <input class="input" type="number" value="45" />
      </div>
    </div>
  `;
}

function ecAutomaticTemplate() {
  return `
    <div class="input-grid input-grid--two">
      <div class="field">
        <label class="field__label">Min Soil Nutrients (mS/cm)</label>
        <input class="input" type="number" value="1.0" step="0.1" />
      </div>
      <div class="field">
        <label class="field__label">Max Soil Nutrients (mS/cm)</label>
        <input class="input" type="number" value="2.5" step="0.1" />
      </div>
    </div>
  `;
}

function modeCardTemplate(value, label, copy, iconName, currentMode) {
  return `
    <button
      class="mode-card ${value === currentMode ? "is-active" : ""}"
      type="button"
      data-action="set-irrigation-mode"
      data-mode="${value}"
      aria-pressed="${String(value === currentMode)}"
    >
      <div class="mode-card__icon">${icon(iconName)}</div>
      <strong>${escapeHtml(label)}</strong>
      <p class="section-copy">${escapeHtml(copy)}</p>
    </button>
  `;
}

function irrigationChannelMeta(channelKey) {
  return IRRIGATION_CHANNELS.find((channel) => channel.key === channelKey) || IRRIGATION_CHANNELS[0];
}

function irrigationFrequencyLabel(value) {
  return IRRIGATION_FREQUENCIES.find((option) => option.value === value)?.label || IRRIGATION_FREQUENCIES[0].label;
}

function formatTimeDisplay(value) {
  if (!value) {
    return "--:--";
  }

  const [hours = "0", minutes = "00"] = value.split(":");
  const date = new Date();
  date.setHours(Number(hours), Number(minutes), 0, 0);
  return date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
}

function irrigationScheduleSummary(channelState) {
  const duration = channelState.scheduleDuration || "0";
  const durationUnit = Number(duration) === 1 ? "second" : "seconds";
  return `${irrigationFrequencyLabel(channelState.scheduleFrequency).toLowerCase()} at ${formatTimeDisplay(channelState.scheduleStartTime)} for ${duration} ${durationUnit}`;
}

function irrigationRowNeedLabels(row) {
  return IRRIGATION_CHANNELS
    .filter((channel) => Boolean(row?.needs?.[channel.key]))
    .map((channel) => channel.label);
}

function irrigationRowsTemplate(mode) {
  const automatic = mode === "automatic";
  const targetRows = normalizeIrrigationRowMap(state.irrigationPage.targetRows);
  const rows = Array.isArray(state.irrigationPage.rows) ? state.irrigationPage.rows : [];
  const activeCount = rows.filter((row) => row.active).length;
  const selectedCount = automatic ? activeCount : Object.keys(targetRows).length;

  return `
    <article class="glass-card card page-stack irrigation-row-panel">
      <div class="card-head">
        <div>
          <h3 class="section-title">${automatic ? "Automatic Row Monitoring" : "Target Rows"}</h3>
          <p class="section-copy">
            ${automatic
              ? "Only active cultivation rows are evaluated. The system starts a solution only when its sensor is below the crop minimum."
              : "Choose the active rows that should receive the selected solution. Inactive rows are safety-locked."}
          </p>
        </div>
        <span class="irrigation-row-count">${escapeHtml(`${selectedCount} ${automatic ? "active" : "selected"}`)}</span>
      </div>
      <div class="irrigation-row-grid">
        ${rows.map((row) => {
          const selected = automatic ? Boolean(row.active) : Boolean(targetRows[row.key]);
          const needLabels = irrigationRowNeedLabels(row);
          const availableSensorCount = Object.values(row.sensorAvailable || {}).filter(Boolean).length;
          const status = !row.active
            ? "Inactive"
            : automatic
              ? needLabels.length
                ? `Needs ${needLabels.join(", ")}`
                : availableSensorCount
                  ? "Within target"
                  : "Waiting for live sensors"
              : selected ? "Selected" : "Available";
          return `
            <button
              class="irrigation-row-card ${row.active ? "is-active-row" : "is-inactive"} ${selected ? "is-selected" : ""}"
              type="button"
              data-action="${automatic ? "noop" : "toggle-irrigation-target-row"}"
              data-row="${escapeHtml(row.key)}"
              aria-pressed="${String(selected)}"
              ${row.active ? "" : "disabled"}
            >
              <span class="irrigation-row-card__top">
                <strong>${escapeHtml(row.label)}</strong>
                <span class="irrigation-row-card__status">${escapeHtml(status)}</span>
              </span>
              <span class="irrigation-row-card__crop">${escapeHtml(row.active ? row.crop : "No active cultivation")}</span>
              ${automatic && row.active ? `
                <span class="irrigation-row-card__metrics">
                  <small>Moisture ${row.readings?.water ?? "--"}%</small>
                  <small>Nutrients ${row.readings?.fertilizer ?? "--"}</small>
                  <small>pH ${row.readings?.limeSolution ?? "--"}</small>
                </span>
              ` : ""}
            </button>
          `;
        }).join("")}
      </div>
    </article>
  `;
}

function irrigationTypeCardTemplate(channel, bodyMarkup, active = false) {
  return `
    <div class="irrigation-type-card ${active ? "is-active" : ""}">
      <div class="irrigation-type-card__head">
        <div class="irrigation-type-card__icon">${icon(channel.icon)}</div>
        <div>
          <h4 class="irrigation-type-card__title">${escapeHtml(channel.label)}</h4>
          <p class="irrigation-type-card__copy">${escapeHtml(channel.description)}</p>
        </div>
      </div>
      ${bodyMarkup}
    </div>
  `;
}

function irrigationAutomaticTemplate(autoEnabled, channels) {
  const activeAutomaticRows = normalizeIrrigationChannelRowMap(state.irrigationPage.activeAutomaticRows);
  const bannerCopy = autoEnabled
    ? "Automatic mode is monitoring active rows. A line starts when a reading is critically low and stops as soon as it is back to normal. Use Manual for a reading that is only low."
    : "Automatic mode is off. Turn the switch on to control irrigation from the live crop parameters.";

  return `
    <article class="glass-card card page-stack">
      <div class="card-head">
        <div>
          <h3 class="section-title">Automatic Settings</h3>
          <p class="section-copy">Choose which solutions follow the live crop parameters</p>
        </div>
        <button
          class="switch ${autoEnabled ? "is-on" : ""}"
          type="button"
          data-action="toggle-auto-irrigation"
          aria-pressed="${String(autoEnabled)}"
        >
          <span class="switch__thumb"></span>
        </button>
      </div>
      <div class="irrigation-type-grid">
        ${IRRIGATION_CHANNELS.map((channel) => {
          const automaticRows = Object.keys(activeAutomaticRows[channel.key] || {});
          const channelEnabled = Boolean(channels[channel.key].automaticEnabled);
          return irrigationTypeCardTemplate(
            channel,
            `
              <label class="irrigation-option-toggle">
                <input
                  type="checkbox"
                  ${channelEnabled ? "checked" : ""}
                  data-irrigation-channel="${channel.key}"
                  data-irrigation-field="automaticEnabled"
                />
                <span>Allow automatic ${escapeHtml(channel.label.toLowerCase())}</span>
              </label>
              <div class="field__hint">Starts below the configured minimum and stops when the reading returns to normal.</div>
              <div class="irrigation-status ${automaticRows.length ? "is-active" : ""}">
                ${!autoEnabled
                  ? "Automatic off"
                  : !channelEnabled
                    ? "Solution disabled"
                    : automaticRows.length
                      ? `Running: ${automaticRows.map(cultivationRowLabel).join(", ")}`
                      : "Monitoring active rows"}
              </div>
            `,
            automaticRows.length > 0,
          );
        }).join("")}
      </div>
      <div class="center-banner"><strong>Automatic mode:</strong> ${escapeHtml(bannerCopy)}</div>
    </article>
  `;
}

function irrigationScheduleTemplate(channels) {
  const activeScheduleLines = normalizeIrrigationRunMap(state.irrigationPage.activeScheduleLines);
  const scheduleIsActive = IRRIGATION_CHANNELS.some((channel) => activeScheduleLines[channel.key]);
  const scheduleIsArmed = Object.keys(normalizeIrrigationRowMap(state.irrigationPage.scheduleArmedRows)).length > 0;
  return `
    <section class="page-stack">
      <div class="irrigation-type-grid">
        ${IRRIGATION_CHANNELS.map((channel) => {
          const isActive = Boolean(activeScheduleLines[channel.key]);
          const scheduleEnabled = Boolean(channels[channel.key].scheduleEnabled);
          return irrigationTypeCardTemplate(
            channel,
            `
              <label class="irrigation-option-toggle">
                <input
                  type="checkbox"
                  ${scheduleEnabled ? "checked" : ""}
                  data-irrigation-channel="${channel.key}"
                  data-irrigation-field="scheduleEnabled"
                  ${isActive ? "disabled" : ""}
                />
                <span>Include ${escapeHtml(channel.label.toLowerCase())}</span>
              </label>
              <div class="field">
                <label class="field__label">Start Time</label>
                <input
                  class="input"
                  type="time"
                  value="${escapeHtml(channels[channel.key].scheduleStartTime)}"
                  data-irrigation-channel="${channel.key}"
                  data-irrigation-field="scheduleStartTime"
                />
              </div>
              <div class="field">
                <label class="field__label">Duration (seconds)</label>
                <input
                  class="input"
                  type="number"
                  min="1"
                  value="${escapeHtml(channels[channel.key].scheduleDuration)}"
                  data-irrigation-channel="${channel.key}"
                  data-irrigation-field="scheduleDuration"
                />
              </div>
              <div class="field">
                <label class="field__label">Frequency</label>
                <select
                  class="select"
                  data-irrigation-channel="${channel.key}"
                  data-irrigation-field="scheduleFrequency"
                >
                  ${IRRIGATION_FREQUENCIES.map(
                    (option) => `
                      <option value="${option.value}" ${channels[channel.key].scheduleFrequency === option.value ? "selected" : ""}>
                        ${escapeHtml(option.label)}
                      </option>
                    `,
                  ).join("")}
                </select>
              </div>
              <div class="center-banner"><strong>Scheduled run:</strong> ${escapeHtml(irrigationScheduleSummary(channels[channel.key]))}</div>
            `,
            isActive,
          );
        }).join("")}
      </div>
      <div class="center-banner">
        <strong>Schedule status:</strong> ${scheduleIsActive ? "A scheduled solution is running now" : scheduleIsArmed ? "Armed and waiting for each configured start time" : "Ready to schedule selected rows"}
      </div>
      <button
        class="button ${scheduleIsArmed ? "button--danger" : "button--primary"} button--full"
        type="button"
        data-action="toggle-schedule-irrigation"
      >
        ${scheduleIsArmed ? "Stop Schedule" : "Start Schedule"}
      </button>
    </section>
  `;
}

function irrigationManualTemplate(activeManualLines, channels) {
  const activeLines = normalizeIrrigationRunMap(activeManualLines);
  const activeChannels = IRRIGATION_CHANNELS.filter((channel) => activeLines[channel.key]);
  const activeManualRows = normalizeIrrigationChannelRowMap(state.irrigationPage.activeManualRows);
  const statusLabel = activeChannels.length
    ? activeChannels.map((channel) => {
        const rows = Object.keys(activeManualRows[channel.key] || {}).map(cultivationRowLabel);
        return `${channel.label}${rows.length ? ` → ${rows.join(", ")}` : ""}`;
      }).join(" • ")
    : "Idle";
  const statusCopy = activeChannels.length
    ? "Press any active button below to stop only that line. Other running lines will stay open."
    : "Choose a line below, set the duration, and start the manual run when needed.";

  return `
    <section class="page-stack">
      <div class="timeline-card">
        <div class="section-copy">Current Status</div>
        <p class="sensor-card__value" style="margin-top: 0.4rem; color: var(--green-800)">
          ${escapeHtml(statusLabel)}
        </p>
        <div class="field__hint">${escapeHtml(statusCopy)}</div>
      </div>
      <div class="irrigation-type-grid">
        ${IRRIGATION_CHANNELS.map((channel) => {
          const isActive = Boolean(activeLines[channel.key]);
          return irrigationTypeCardTemplate(
            channel,
            `
              <div class="field">
                <label class="field__label">Duration (seconds)</label>
                <input
                  class="input"
                  type="number"
                  min="1"
                  value="${escapeHtml(channels[channel.key].manualDuration)}"
                  data-irrigation-channel="${channel.key}"
                  data-irrigation-field="manualDuration"
                />
              </div>
              <div class="irrigation-status ${isActive ? "is-active" : ""}">
                ${isActive ? "Running now" : "Ready to start"}
              </div>
              <button
                class="button ${isActive ? "button--danger" : "button--primary"} button--full"
                type="button"
                data-action="toggle-manual-irrigation"
                data-channel="${channel.key}"
              >
                ${isActive ? `Stop ${escapeHtml(channel.label)}` : `Start ${escapeHtml(channel.label)}`}
              </button>
            `,
            isActive,
          );
        }).join("")}
      </div>
    </section>
  `;
}

function irrigationControlModalTemplate() {
  const { overlayMode, activeManualLines, channels } = state.irrigationPage;
  const isSchedule = overlayMode === "schedule";
  const title = isSchedule ? "Schedule Control" : "Manual Control";
  const copy = isSchedule
    ? "Separate time-based settings open here instead of appearing in the page section below."
    : "Manual controls open in their own transparent card so they stay separate from the automatic section.";
  const bodyMarkup = isSchedule
    ? irrigationScheduleTemplate(channels)
    : irrigationManualTemplate(activeManualLines, channels);

  return `
    <div class="overlay overlay--center">
      <div class="modal irrigation-modal">
        <div class="modal__header">
          <div class="card-head">
            <div>
              <h3 class="section-title">${escapeHtml(title)}</h3>
              <p class="section-copy">${escapeHtml(copy)}</p>
            </div>
            <button class="icon-button" type="button" data-action="close-irrigation-overlay">
              ${icon("close")}
            </button>
          </div>
        </div>
        <div class="modal__body page-stack irrigation-modal__body">
          ${bodyMarkup}
        </div>
      </div>
    </div>
  `;
}

function metricCardTemplate(label, value) {
  return `
    <div class="metric-card">
      <div class="metric-label">${escapeHtml(label)}</div>
      <p class="metric-value">${escapeHtml(value)}</p>
    </div>
  `;
}

function cultivationParameterCardTemplate(field, values) {
  return `
    <div class="metric-card page-stack cultivation-parameter-card">
      <div class="inline-copy">
        <span class="nav-button__icon" style="color: var(--green-600)">${icon(field.icon)}</span>
        <div>
          <div class="metric-label">${escapeHtml(field.label)}</div>
          <p class="section-copy">Editable target range</p>
        </div>
      </div>
      <div class="input-grid input-grid--two">
        <div class="field">
          <label class="field__label" for="cultivation-${field.key}-min">Min</label>
          <input
            class="input"
            id="cultivation-${field.key}-min"
            type="text"
            inputmode="decimal"
            autocomplete="off"
            data-cultivation-field="${field.key}"
            data-cultivation-bound="min"
            value="${escapeHtml(values.min)}"
          />
        </div>
        <div class="field">
          <label class="field__label" for="cultivation-${field.key}-max">Max</label>
          <input
            class="input"
            id="cultivation-${field.key}-max"
            type="text"
            inputmode="decimal"
            autocomplete="off"
            data-cultivation-field="${field.key}"
            data-cultivation-bound="max"
            value="${escapeHtml(values.max)}"
          />
        </div>
      </div>
      <div class="field__hint">Unit: ${escapeHtml(field.unit)}</div>
    </div>
  `;
}

function cultivationRecommendedParameterCardTemplate(field, values, cropName) {
  return `
    <div class="metric-card page-stack cultivation-parameter-card cultivation-parameter-card--recommended">
      <div class="inline-copy">
        <span class="nav-button__icon" style="color: var(--green-600)">${icon(field.icon)}</span>
        <div>
          <div class="metric-label">${escapeHtml(field.label)}</div>
          <p class="section-copy">Reference range for ${escapeHtml(cropName)}</p>
        </div>
      </div>
      <div class="cultivation-parameter-static">
        <div class="cultivation-parameter-static__item">
          <span>Min</span>
          <strong>${escapeHtml(values.min)}</strong>
        </div>
        <div class="cultivation-parameter-static__item">
          <span>Max</span>
          <strong>${escapeHtml(values.max)}</strong>
        </div>
      </div>
      <div class="field__hint">Unit: ${escapeHtml(field.unit)}</div>
    </div>
  `;
}

function cultivationParameterSummaryCardTemplate(field, values) {
  return `
    <div class="metric-card">
      <div class="inline-copy">
        <span class="nav-button__icon" style="color: var(--green-600)">${icon(field.icon)}</span>
        <div class="metric-label">${escapeHtml(field.label)}</div>
      </div>
      <p class="metric-value" style="font-size: 1.35rem; margin-top: 0.8rem;">
        ${escapeHtml(values.min)} - ${escapeHtml(values.max)} <span>${escapeHtml(field.unit)}</span>
      </p>
    </div>
  `;
}

function cultivationResultsTemplate(cropType, plantingDate, harvestDate, daysToHarvest, parameters) {
  const cropName = selectedCultivationName({
    cropType,
    customPlantName: state.cultivation.customPlantName,
  });
  const rowLabel = cultivationRowLabel(state.cultivation.rowKey);
  return `
    <article class="glass-card card page-stack">
      <div>
        <h3 class="section-title">Cultivation Timeline</h3>
        <p class="section-copy">Selected crop: ${escapeHtml(cropName)}${state.cultivation.rowKey ? ` • ${escapeHtml(rowLabel)}` : ""}</p>
      </div>
      <div class="grid grid--cards">
        <div class="timeline-card">
          <div class="inline-copy">
            <span class="nav-button__icon" style="color: var(--green-800)">${icon("calendar")}</span>
            <strong>Planting Date</strong>
          </div>
          <p class="sensor-card__value" style="font-size: 1.35rem; margin-top: 0.8rem; color: var(--green-800)">
            ${escapeHtml(formatLongDate(plantingDate))}
          </p>
        </div>
        <div class="timeline-card timeline-card--green">
          <div class="inline-copy">
            <span class="nav-button__icon" style="color: var(--green-600)">${icon("clock")}</span>
            <strong>Growth Period</strong>
          </div>
          <p class="sensor-card__value" style="font-size: 1.35rem; margin-top: 0.8rem; color: var(--green-600)">
            ${escapeHtml(daysToHarvest)} days
          </p>
        </div>
        <div class="timeline-card timeline-card--amber">
          <div class="inline-copy">
            <span class="nav-button__icon" style="color: var(--amber-500)">${icon("sprout")}</span>
            <strong>Estimated Harvest</strong>
          </div>
          <p class="sensor-card__value" style="font-size: 1.35rem; margin-top: 0.8rem; color: var(--amber-500)">
            ${escapeHtml(formatLongDate(harvestDate))}
          </p>
        </div>
      </div>
      <div class="timeline-bar">
        <div class="timeline-bar__track">
          <div class="timeline-bar__fill"></div>
        </div>
        <div class="timeline-bar__labels">
          <div>
            <div class="timeline-bar__marker timeline-bar__marker--start"></div>
            <span>Start</span>
          </div>
          <div class="text-right">
            <div class="timeline-bar__marker timeline-bar__marker--end"></div>
            <span>Harvest</span>
          </div>
        </div>
      </div>
      <div class="center-banner">
        Dashboard monitoring ranges are now using the cultivation parameters for ${escapeHtml(cropName)}${state.cultivation.rowKey ? ` in ${escapeHtml(rowLabel)}` : ""}.
      </div>
    </article>

    <article class="glass-card card page-stack">
      <div>
        <h3 class="section-title">Applied Parameters</h3>
        <p class="section-copy">Current operating range for your selected cultivation</p>
      </div>
      <div class="grid grid--cards">
        ${CULTIVATION_PARAMETER_FIELDS.map((field) =>
          cultivationParameterSummaryCardTemplate(field, parameters[field.key]),
        ).join("")}
      </div>
    </article>
  `;
}

// The target range a row is actually being judged against, and the two dates
// its timeline is drawn from. Both are chosen once in the setup flow and were
// never shown again -- so a week later there was no way to answer "what is row
// 2 set to?" without deleting and re-planting it.
//
// A hand-set range can also be corrected here. A recommended one cannot: those
// five numbers are the Department of Agriculture reference for the crop, and
// there is nothing to hand-edit in a reference. That row still shows its dates,
// it simply has no Edit Parameters to press.
function openCultivationParameters(cultivationId) {
  const normalized = String(cultivationId || "").trim();
  if (!normalized) {
    return;
  }
  state.cultivationParametersId = normalized;
  state.cultivationParametersEdit = null;
  state.cultivationParametersSaving = false;
  renderOverlays();
}

// The shortcut from a sensor drawer to the range that sensor is judged against.
// Navigation has to land first: the parameters dialog is an overlay over the
// Cultivation page, and opening it while the dashboard is still mounted would
// put it over the wrong page and leave it there when the route caught up.
function openSensorRowParameters(rowKey) {
  const normalized = String(rowKey || "").trim();
  if (!normalized) {
    return;
  }

  const cultivation = activeCultivationForRow(normalized);
  closeSensorDetail(false);
  navigateTo("cultivation");

  // No cultivation means there is no range to edit; the page itself is still
  // the right place to land, so the user can plant one. A recommended range
  // has no editor either -- the drawer offers no shortcut for one, and this
  // agrees with it in case the action is reached some other way.
  if (!cultivation || !cultivationParametersAreEditable(cultivation)) {
    renderOverlays();
    return;
  }

  // navigateTo animates the route out before the hash changes, so wait for the
  // page underneath to be the one this dialog belongs to.
  window.setTimeout(() => {
    openCultivationParameters(String(cultivation.id));
  }, PAGE_TRANSITION_EXIT_MS + 30);
}

function closeCultivationParameters() {
  if (!state.cultivationParametersId || state.cultivationParametersSaving) {
    return;
  }
  state.cultivationParametersId = "";
  state.cultivationParametersEdit = null;
  renderOverlays();
}

// Only a range someone set by hand, and only one that actually stored values:
// a cultivation from before parameters travelled has nothing to seed an editor
// with, and the dialog says so instead.
function cultivationParametersAreEditable(cultivation) {
  return String(cultivation?.parameterMode || "").trim().toLowerCase() === "custom"
    && Boolean(cultivation?.parameters && typeof cultivation.parameters === "object");
}

function beginCultivationParametersEdit() {
  const cultivation = getCultivationParametersTarget();
  if (!cultivation || !cultivationParametersAreEditable(cultivation)) {
    return;
  }

  state.cultivationParametersEdit = {
    plantingDate: String(cultivation.plantingDate || "").trim(),
    harvestDate: String(cultivation.harvestDate || "").trim(),
    // Strings, like every other form field here: a half-typed "1." has to
    // survive until Save, which is where the numbers are checked.
    parameters: Object.fromEntries(CULTIVATION_PARAMETER_FIELDS.map((field) => {
      const values = cultivation.parameters?.[field.key] || {};
      return [field.key, {
        min: values.min === undefined || values.min === null ? "" : String(values.min),
        max: values.max === undefined || values.max === null ? "" : String(values.max),
      }];
    })),
  };
  state.cultivationParametersSaving = false;
  renderOverlays();
}

function cancelCultivationParametersEdit() {
  if (!state.cultivationParametersEdit || state.cultivationParametersSaving) {
    return;
  }
  state.cultivationParametersEdit = null;
  renderOverlays();
}

async function saveCultivationParameters() {
  const cultivation = getCultivationParametersTarget();
  const draft = state.cultivationParametersEdit;
  if (!cultivation || !draft || state.cultivationParametersSaving) {
    return;
  }

  const plantingDate = String(draft.plantingDate || "").trim();
  const harvestDate = String(draft.harvestDate || "").trim();

  if (!cultivationDateIsInCurrentYear(plantingDate)) {
    pushNotification("warning", `Planting date must be a real date within ${CULTIVATION_CURRENT_YEAR}.`);
    return;
  }
  if (!cultivationDateIsInCurrentYear(harvestDate)) {
    pushNotification("warning", `Harvest date must be a real date within ${CULTIVATION_CURRENT_YEAR}.`);
    return;
  }

  const daysToHarvest = Math.round(
    (parseDateInput(harvestDate).getTime() - parseDateInput(plantingDate).getTime()) / 86400000,
  );
  if (daysToHarvest <= 0) {
    pushNotification("warning", "The harvest date has to come after the planting date.");
    return;
  }

  const parameters = normalizeCultivationParameters(draft.parameters);
  if (!parameters) {
    pushNotification("warning", cultivationParameterProblem(draft.parameters));
    return;
  }

  const requestJson = window.ICuCropsAuth?.requestJson;
  if (typeof requestJson !== "function") {
    applyCultivationParametersEditLocally(cultivation.id, {
      plantingDate,
      harvestDate,
      daysToHarvest,
      parameters,
    });
    state.cultivationParametersEdit = null;
    applyCultivationParametersToSensors(parameters);
    renderPage();
    renderOverlays();
    pushNotification("success", `${cultivation.crop} parameters were updated.`);
    return;
  }

  state.cultivationParametersSaving = true;
  renderOverlays();

  try {
    const response = await requestJson(`/api/cultivations/${encodeURIComponent(cultivation.id)}`, {
      method: "PATCH",
      body: {
        plantingDate,
        harvestDate,
        daysToHarvest,
        parameters,
      },
    });
    state.activeCultivations = mapActiveCultivations(response.cultivations);
    // A changed range is a changed control input -- the backend has already
    // recomputed what each line should be doing, and this is the same reply
    // starting and deleting a cultivation hand back.
    applyIrrigationResponse(response.irrigation || {});
    await refreshNotifications({ render: false });
    state.cultivationParametersEdit = null;
    state.cultivationParametersSaving = false;
    applyCultivationParametersToSensors(parameters);
    renderHeader();
    renderPage();
    renderOverlays();
    pushNotification("success", response.message || `${cultivation.crop} parameters were updated.`);
  } catch (error) {
    state.cultivationParametersSaving = false;
    renderOverlays();
    pushNotification("warning", extractRequestMessage(error, "Unable to save the parameters right now."));
  }
}

// Standalone mode has no backend to write to, so the list is corrected in
// place. normalizeActiveCultivation redraws "planted", "harvest" and the days
// remaining from the new dates, exactly as a reply from the API would.
function applyCultivationParametersEditLocally(cultivationId, changes) {
  state.activeCultivations = state.activeCultivations.map((item) => (
    String(item.id) === String(cultivationId)
      ? normalizeActiveCultivation({ ...item, ...changes })
      : item
  ));
}

function getCultivationParametersTarget() {
  const id = String(state.cultivationParametersId || "").trim();
  if (!id) {
    return null;
  }
  return state.activeCultivations.find((item) => String(item.id) === id) || null;
}

function cultivationParametersModalTemplate() {
  const cultivation = getCultivationParametersTarget();
  if (!cultivation) {
    return "";
  }

  // A cultivation saved before parameters travelled, or one whose row arrived
  // through a sync, can have none. Say so rather than rendering five blanks.
  const parameters = cultivation.parameters && typeof cultivation.parameters === "object"
    ? cultivation.parameters
    : null;
  const isRecommended = String(cultivation.parameterMode || "").trim().toLowerCase() !== "custom";
  const cropName = String(cultivation.crop || "Cultivation").trim();
  const rowLabel = String(cultivation.rowLabel || cultivationRowLabel(cultivation.rowKey) || "").trim();
  const draft = state.cultivationParametersEdit;
  const isEditing = Boolean(draft);
  const isSaving = Boolean(state.cultivationParametersSaving);
  const canEdit = cultivationParametersAreEditable(cultivation);
  const plantingDate = isEditing ? draft.plantingDate : String(cultivation.plantingDate || "").trim();
  const harvestDate = isEditing ? draft.harvestDate : String(cultivation.harvestDate || "").trim();
  const shownParameters = isEditing ? draft.parameters : parameters;

  return `
    <div class="overlay overlay--center overlay--dialog">
      <div
        class="modal modal--cultivation cultivation-parameters-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cultivation-parameters-title"
      >
        <div class="modal__header">
          <div class="card-head">
            <div>
              <p class="cultivation-parameters-modal__eyebrow">${escapeHtml(rowLabel)} &middot; ${escapeHtml(cropName)}</p>
              <div class="cultivation-parameters-modal__heading">
                <h3 class="section-title cultivation-modal__title" id="cultivation-parameters-title">
                  ${isRecommended ? "Recommended Parameters" : "Custom Parameters"}
                </h3>
                ${canEdit && !isEditing ? `
                  <button
                    class="cultivation-parameters-modal__edit"
                    type="button"
                    data-action="edit-cultivation-parameters"
                  >
                    ${icon("pencil")}Edit Parameters
                  </button>
                ` : ""}
              </div>
              <p class="section-copy">
                ${isRecommended
                  ? `Department of Agriculture reference range, in use for ${escapeHtml(cropName)}.`
                  : isEditing
                    ? `Change the dates or the target range for ${escapeHtml(cropName)}, then save.`
                    : `The target range set by hand for ${escapeHtml(cropName)}.`}
              </p>
            </div>
            <button
              class="icon-button"
              type="button"
              data-action="close-cultivation-parameters"
              aria-label="Close"
              ${isSaving ? "disabled" : ""}
            >
              ${icon("close")}
            </button>
          </div>
        </div>

        <div class="modal__body page-stack cultivation-parameters-modal__body">
          ${cultivationParametersDatesTemplate({ plantingDate, harvestDate, isEditing })}

          ${shownParameters ? `
            <div class="grid cultivation-parameter-grid">
              ${CULTIVATION_PARAMETER_FIELDS.map((field) => (isEditing
                ? cultivationParameterEditCardTemplate(field, shownParameters[field.key])
                : cultivationParameterReadingTemplate(field, shownParameters[field.key]))).join("")}
            </div>
          ` : `
            <div class="center-banner">No target range was stored for this cultivation.</div>
          `}

          ${isEditing ? `
            <div class="modal__actions cultivation-modal__actions cultivation-parameters-modal__actions">
              <button
                class="button button--secondary"
                type="button"
                data-action="cancel-cultivation-parameters-edit"
                ${isSaving ? "disabled" : ""}
              >
                Cancel
              </button>
              <button
                class="button button--primary"
                type="button"
                data-action="save-cultivation-parameters"
                ${isSaving ? "disabled" : ""}
              >
                ${isSaving ? "Saving..." : "Save Changes"}
              </button>
            </div>
          ` : ""}
        </div>
      </div>
    </div>
  `;
}

// When it was planted and when it comes out, which is what the row's card and
// the countdown on it are both drawn from. Shown whichever range is in force.
function cultivationParametersDatesTemplate({ plantingDate, harvestDate, isEditing }) {
  return `
    <div class="cultivation-parameters-dates">
      ${cultivationParametersDateTemplate({
        key: "planting",
        label: "Planting Date",
        value: plantingDate,
        isEditing,
      })}
      <span class="cultivation-parameters-dates__arrow" aria-hidden="true">&rarr;</span>
      ${cultivationParametersDateTemplate({
        key: "harvest",
        label: "Expected Harvest",
        value: harvestDate,
        isEditing,
      })}
    </div>
  `;
}

function cultivationParametersDateTemplate({ key, label, value, isEditing }) {
  const inputId = `cultivation-parameters-${key}-date`;

  if (!isEditing) {
    return `
      <div class="cultivation-parameter-static__item cultivation-parameters-dates__item">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(cultivationDateIsInCurrentYear(value) ? formatLongDate(value) : "--")}</strong>
      </div>
    `;
  }

  return `
    <div class="field cultivation-parameters-dates__field">
      <label class="field__label" for="${inputId}">${escapeHtml(label)}</label>
      <div class="date-picker-control">
        <input
          class="input"
          id="${inputId}"
          type="date"
          lang="en-US"
          min="${CULTIVATION_DATE_MIN}"
          max="${CULTIVATION_DATE_MAX}"
          value="${escapeHtml(value)}"
          data-cultivation-parameters-date="${key}"
        />
      </div>
    </div>
  `;
}

// The setup flow's card with its own data attributes: both dialogs can be in
// the DOM at once, and the setup one writes straight into state.cultivation.
function cultivationParameterEditCardTemplate(field, values) {
  const min = values && values.min !== undefined && values.min !== null ? String(values.min) : "";
  const max = values && values.max !== undefined && values.max !== null ? String(values.max) : "";
  return `
    <div class="metric-card page-stack cultivation-parameter-card">
      <div class="inline-copy">
        <span class="nav-button__icon" style="color: var(--green-600)">${icon(field.icon)}</span>
        <div>
          <div class="metric-label">${escapeHtml(field.label)}</div>
          <p class="section-copy">Target range</p>
        </div>
      </div>
      <div class="input-grid input-grid--two">
        <div class="field">
          <label class="field__label" for="cultivation-parameters-${field.key}-min">Min</label>
          <input
            class="input"
            id="cultivation-parameters-${field.key}-min"
            type="text"
            inputmode="decimal"
            autocomplete="off"
            data-cultivation-parameters-field="${field.key}"
            data-cultivation-parameters-bound="min"
            value="${escapeHtml(min)}"
          />
        </div>
        <div class="field">
          <label class="field__label" for="cultivation-parameters-${field.key}-max">Max</label>
          <input
            class="input"
            id="cultivation-parameters-${field.key}-max"
            type="text"
            inputmode="decimal"
            autocomplete="off"
            data-cultivation-parameters-field="${field.key}"
            data-cultivation-parameters-bound="max"
            value="${escapeHtml(max)}"
          />
        </div>
      </div>
      <div class="field__hint">Unit: ${escapeHtml(field.unit)}</div>
    </div>
  `;
}

function cultivationParameterReadingTemplate(field, values) {
  const min = values && values.min !== undefined && values.min !== null ? String(values.min) : "--";
  const max = values && values.max !== undefined && values.max !== null ? String(values.max) : "--";
  return `
    <div class="metric-card page-stack cultivation-parameter-card cultivation-parameter-card--recommended">
      <div class="inline-copy">
        <span class="nav-button__icon" style="color: var(--green-600)">${icon(field.icon)}</span>
        <div>
          <div class="metric-label">${escapeHtml(field.label)}</div>
          <p class="section-copy">Target range</p>
        </div>
      </div>
      <div class="cultivation-parameter-static">
        <div class="cultivation-parameter-static__item">
          <span>Min</span>
          <strong>${escapeHtml(min)}</strong>
        </div>
        <div class="cultivation-parameter-static__item">
          <span>Max</span>
          <strong>${escapeHtml(max)}</strong>
        </div>
      </div>
      <div class="field__hint">Unit: ${escapeHtml(field.unit)}</div>
    </div>
  `;
}

function activeCultivationTemplate(item) {
  return `
    <div class="cultivation-item">
      <div class="cultivation-item__meta">
        <div class="cultivation-item__icon" aria-hidden="true">
          ${icon("sprout")}
        </div>
        <div>
          <p class="user-row__name">${escapeHtml(item.crop)}</p>
          <p class="section-copy">${escapeHtml(item.rowLabel || cultivationRowLabel(item.rowKey))}</p>
          <p class="section-copy">Planted: ${escapeHtml(item.planted)}</p>
        </div>
      </div>
      <div class="cultivation-item__right">
        <div class="text-right cultivation-item__summary">
          <p class="user-row__name" style="color: ${item.remainingColor}; margin: 0;">${escapeHtml(item.remaining)}</p>
          <p class="section-copy">Harvest: ${escapeHtml(item.harvest)}</p>
        </div>
        <button
          class="icon-button cultivation-item__view"
          type="button"
          data-action="view-cultivation-parameters"
          data-id="${escapeHtml(item.id)}"
          aria-label="View ${escapeHtml(item.crop)} parameters"
          title="View parameters"
        >
          ${icon("eye")}
        </button>
      </div>
    </div>
  `;
}

function userRowTemplate(user) {
  const isAdmin = user.role === "admin";
  const roleLabel = isAdmin ? "Administrator" : "User";
  return `
    <div class="user-row">
      <div class="user-row__meta">
        <div class="user-row__avatar">${escapeHtml(user.name.charAt(0).toUpperCase())}</div>
        <div>
          <p class="user-row__name">
            ${escapeHtml(user.name)}
            ${isAdmin ? `<span class="role-badge">${icon("shield", "icon")}${roleLabel}</span>` : ""}
          </p>
          <p class="user-row__email">
            <span class="nav-button__icon">${icon("mail")}</span>
            ${escapeHtml(user.email)}
          </p>
        </div>
      </div>
      <button
        class="icon-button icon-button--danger"
        type="button"
        data-action="delete-user"
        data-id="${user.id}"
        ${isAdmin ? "disabled aria-disabled=\"true\"" : ""}
      >
        ${icon("trash")}
      </button>
    </div>
  `;
}

function settingsModalTemplate() {
  const activeSection = SETTINGS_SECTIONS.find((section) => section.key === state.activeSettingsTab) || SETTINGS_SECTIONS[0];

  return `
    <div class="overlay overlay--center">
      <div class="modal modal--settings">
        <div class="modal__header">
          <div class="card-head">
            <div>
              <p class="section-eyebrow">Settings</p>
              <h3 class="section-title">${activeSection.label}</h3>
            </div>
            <button class="icon-button" type="button" data-action="close-settings">
              ${icon("close")}
            </button>
          </div>
        </div>
        <div class="modal__body">
          ${state.activeSettingsTab === "profile" ? settingsProfileTemplate() : ""}
          ${state.activeSettingsTab === "about" ? settingsAboutTemplate() : ""}
          ${state.activeSettingsTab === "guide" ? settingsGuideTemplate() : ""}
          ${state.activeSettingsTab === "developers" ? settingsDevelopersTemplate() : ""}
        </div>
      </div>
    </div>
  `;
}

function settingsMenuTemplate() {
  const position = state.settingsMenuPosition || { top: 16, left: 16 };

  return `
    <div class="settings-menu-shell">
      <div
        class="settings-menu"
        role="menu"
        aria-label="Settings sections"
        style="top: ${position.top}px; left: ${position.left}px;"
      >
        <div class="settings-menu__list">
          ${SETTINGS_SECTIONS.map((section) => settingsMenuButton(section)).join("")}
        </div>
      </div>
    </div>
  `;
}

function settingsMenuButton(section) {
  return `
    <button
      class="settings-menu__button"
      type="button"
      role="menuitem"
      data-action="open-settings-section"
      data-section="${section.key}"
    >
      <span class="nav-button__icon" aria-hidden="true">${icon(section.icon)}</span>
      <span>${section.label}</span>
    </button>
  `;
}

function passwordChangeOtpModalTemplate() {
  const otpInputs = state.otpCode
    .map((digit, index) => `
      <input
        class="otp-input"
        id="otp-${index}"
        type="text"
        inputmode="numeric"
        autocomplete="${index === 0 ? "one-time-code" : "off"}"
        maxlength="1"
        value="${escapeHtml(digit)}"
      />
    `)
    .join("");

  return `
    <div class="overlay overlay--center overlay--dialog">
      <div class="modal modal--sm password-otp-modal">
        <div class="modal__header">
          <div class="card-head">
            <div>
              <h3 class="section-title">OTP Verification</h3>
              <p class="section-copy">Enter the 6-digit code to confirm your new password.</p>
            </div>
            <button class="icon-button" type="button" data-action="cancel-password-change-otp">
              ${icon("close")}
            </button>
          </div>
        </div>
        <div class="modal__body password-otp-modal__body">
          <article class="glass-card card password-otp-card">
            <div class="password-otp-card__copy">
              <span class="spot-icon">${icon("mail")}</span>
              <div>
                <h4 class="section-title">Verification Code</h4>
                <p class="section-copy">Complete all 6 digits. It will apply automatically once the code is complete.</p>
              </div>
            </div>
            <div class="otp-row otp-row--modal">
              ${otpInputs}
            </div>
          </article>
          <div class="modal__actions password-otp-modal__actions">
            <button class="button button--secondary button--full" type="button" data-action="cancel-password-change-otp">
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function settingsTabButton(tab, label, iconName) {
  return `
    <button class="tab-button ${state.activeSettingsTab === tab ? "is-active" : ""}" type="button" data-tab="${tab}">
      <span class="nav-button__icon">${icon(iconName)}</span>
      <span>${label}</span>
    </button>
  `;
}

function openSettings(tab = "profile") {
  closeNotificationsDrawer();
  closeSettingsMenu(false);
  closeDeleteScheduleConfirm(false);
  const normalizedTab = tab === "contact" ? "guide" : tab;
  state.profileName = state.savedProfileName;
  state.profileNameError = "";
  state.settingsOpen = true;
  state.activeSettingsTab = SETTINGS_SECTIONS.some((section) => section.key === normalizedTab) ? normalizedTab : "profile";
  if (state.activeSettingsTab === "guide") {
    state.activeGuideStep = typeof normalizeGuideStep === "function" ? normalizeGuideStep(0) : 0;
  }
  resetPasswordChangeState();
  renderOverlays();
}

function openSettingsMenu(anchorElement) {
  if (!(anchorElement instanceof HTMLElement)) {
    return;
  }

  closeNotificationsDrawer();

  const rect = anchorElement.getBoundingClientRect();
  // A first guess, only good enough to render with. The real size is measured
  // below, because this one was wrong: 252px was assumed for a menu that is
  // actually 308px tall with its four sections. On the old 800x480 panel the
  // error was hidden -- the menu still landed inside the screen -- but the
  // 1024x600 one places it lower, and 26px of it hung off the bottom edge.
  const estimatedWidth = 252;
  const estimatedHeight = 252;
  const top = Math.max(
    16,
    Math.min(rect.top + rect.height / 2 - estimatedHeight / 2, window.innerHeight - estimatedHeight - 16),
  );
  const left = Math.max(16, Math.min(rect.right + 14, window.innerWidth - estimatedWidth - 16));

  state.settingsOpen = false;
  state.settingsMenuOpen = true;
  state.settingsMenuPosition = {
    top: Math.round(top),
    left: Math.round(left),
  };

  startSettingsMenuWatcher();
  renderOverlays();
  // Now that it exists, place it by what it measures rather than what it was
  // guessed to be. Sizing depends on the panel's font scale and on how many
  // sections there are, so no constant here can stay correct -- this is what
  // stops the next display, or the next menu entry, breaking it again.
  fitSettingsMenuToViewport();
}

// Clamp the open menu inside the viewport using its real measured box.
function fitSettingsMenuToViewport() {
  if (!state.settingsMenuOpen) {
    return;
  }

  const menu = document.querySelector(".settings-menu");
  if (!(menu instanceof HTMLElement)) {
    return;
  }

  const margin = 16;
  const bounds = menu.getBoundingClientRect();
  const current = state.settingsMenuPosition || { top: margin, left: margin };

  // A menu taller than the panel is pinned to the top and scrolls; anything
  // shorter is simply pushed back inside. The same for width.
  const maxTop = Math.max(margin, window.innerHeight - bounds.height - margin);
  const maxLeft = Math.max(margin, window.innerWidth - bounds.width - margin);
  const top = Math.min(Math.max(margin, current.top), maxTop);
  const left = Math.min(Math.max(margin, current.left), maxLeft);

  if (top === current.top && left === current.left) {
    return;
  }

  state.settingsMenuPosition = { top: Math.round(top), left: Math.round(left) };
  menu.style.top = `${Math.round(top)}px`;
  menu.style.left = `${Math.round(left)}px`;
}

function openLogoutConfirm() {
  closeNotificationsDrawer(false, false);
  closeSettingsMenu(false);
  state.settingsOpen = false;
  state.deleteScheduleConfirmOpen = false;
  state.deleteScheduleTargetChannel = "";
  closeSensorDetail(false);
  state.logoutConfirmOpen = true;
  renderOverlays();
  document.querySelector('[data-action="confirm-logout"]')?.focus();
}

function closeLogoutConfirm(shouldRender = true) {
  state.logoutConfirmOpen = false;
  if (shouldRender) {
    renderOverlays();
  }
}

function openDeleteScheduleConfirm(channelKey) {
  const normalizedChannel = String(channelKey || "").trim();
  const activeScheduleLines = normalizeIrrigationRunMap(state.irrigationPage.activeScheduleLines);
  if (!normalizedChannel || !state.irrigationPage.channels[normalizedChannel] || !activeScheduleLines[normalizedChannel]) {
    return;
  }

  closeNotificationsDrawer(false, false);
  closeSettingsMenu(false);
  state.settingsOpen = false;
  state.logoutConfirmOpen = false;
  closeSensorDetail(false);
  state.deleteScheduleConfirmOpen = true;
  state.deleteScheduleTargetChannel = normalizedChannel;
  renderOverlays();
  document.querySelector('[data-action="confirm-delete-schedule"]')?.focus();
}

function closeDeleteScheduleConfirm(shouldRender = true) {
  state.deleteScheduleConfirmOpen = false;
  state.deleteScheduleTargetChannel = "";
  if (shouldRender) {
    renderOverlays();
  }
}

async function confirmDeleteSchedule() {
  const target = getDeleteScheduleTarget();
  if (!target) {
    closeDeleteScheduleConfirm();
    return;
  }

  const activeScheduleLines = normalizeIrrigationRunMap(state.irrigationPage.activeScheduleLines);
  delete activeScheduleLines[target.channel.key];
  state.irrigationPage.activeScheduleLines = activeScheduleLines;
  delete state.irrigationPage.activeScheduleRows[target.channel.key];
  closeDeleteScheduleConfirm(false);
  renderPage();
  renderOverlays();
  await saveIrrigationStateWithFeedback({
    warningMessage: `${target.channel.label} schedule removed.`,
  });
}

function closeSettingsMenu(shouldRender = true) {
  state.settingsMenuOpen = false;
  state.settingsMenuPosition = null;
  stopSettingsMenuWatcher();

  if (shouldRender) {
    renderOverlays();
  }
}

function closeSettings() {
  state.profileName = state.savedProfileName;
  state.profileNameError = "";
  state.settingsOpen = false;
  closeSettingsMenu(false);
  resetPasswordChangeState();
  renderOverlays();
}

function navigateTo(view) {
  if (!view) {
    return;
  }

  closeNotificationsDrawer(false, false);
  closeSettingsMenu(false);
  closeDeleteScheduleConfirm(false);
  // The sensor drawer is an overlay, not a view: leaving it open meant
  // "Open Sensor Management" changed the page underneath and then covered it,
  // which read as the button doing nothing at all.
  closeSensorDetail(false);

  const nextHash = VIEW_HASHES[view] || VIEW_HASHES.dashboard;
  if (window.location.hash === nextHash) {
    syncViewFromHash();
    return;
  }

  window.clearTimeout(routeTransitionTimer);

  if (!primeRouteExitAnimation(view)) {
    window.location.hash = nextHash;
    return;
  }

  routeTransitionTimer = window.setTimeout(() => {
    window.location.hash = nextHash;
  }, PAGE_TRANSITION_EXIT_MS);
}

function openSensorDetail(sensorId) {
  const sensor = findDashboardSensorById(sensorId);
  if (!sensor) {
    return;
  }

  closeNotificationsDrawer();
  state.selectedSensorId = sensorId;
  state.sensorDraft = {
    min: sensor.min,
    max: sensor.max,
    alertMode: normalizeAlertMode(sensor.alertMode),
  };
  renderOverlays();
}

function closeSensorDetail(shouldRender = true) {
  state.selectedSensorId = null;
  state.sensorDraft = null;
  if (shouldRender) {
    renderOverlays();
  }
}

function openNotificationsDrawer() {
  state.settingsOpen = false;
  state.settingsMenuOpen = false;
  state.settingsMenuPosition = null;
  state.showAddUserModal = false;
  closeSensorDetail(false);
  clearAllNotificationTimers();
  state.notificationsOpen = true;
  markAllNotificationsRead(false);
  renderNotificationHeaderState();
  renderOverlays();
  renderToasts();
  if (state.activeView === "history") {
    renderPage();
  }
}

function closeNotificationsDrawer(shouldRender = true, shouldRestartTimers = shouldRender) {
  if (!state.notificationsOpen) {
    return;
  }

  state.notificationsOpen = false;

  if (shouldRender) {
    renderNotificationHeaderState();
    renderOverlays();
    renderToasts();
  }

  if (shouldRestartTimers) {
    restartDashboardNotificationTimers();
  }
}

// A typed bound, read the way a person means it. The fields are text with a
// decimal keypad rather than type="number": a phone keyboard that puts a comma
// on its decimal key makes a number field report "" for "6,5", so the value
// was lost before this code ever saw it and the only answer was an alert that
// named no field. Spaces are ignored and a comma is a decimal point; anything
// still not a plain number is NaN.
function parseCultivationBound(value) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : Number.NaN;
  }
  const text = String(value ?? "").replace(/\s+/g, "").replace(",", ".");
  if (!/^[-+]?(\d+\.?\d*|\.\d+)$/.test(text)) {
    return Number.NaN;
  }
  return Number(text);
}

// What is wrong with a set of ranges, naming the field, or "" when nothing is.
function cultivationParameterProblem(parameters) {
  for (const field of CULTIVATION_PARAMETER_FIELDS) {
    const values = parameters?.[field.key];
    const min = parseCultivationBound(values?.min);
    const max = parseCultivationBound(values?.max);
    if (!Number.isFinite(min)) {
      return `${field.label}: enter a number for Min.`;
    }
    if (!Number.isFinite(max)) {
      return `${field.label}: enter a number for Max.`;
    }
    if (min >= max) {
      return `${field.label}: Min (${min}) has to be lower than Max (${max}).`;
    }
  }
  return "";
}

function normalizeCultivationParameters(parameters) {
  if (cultivationParameterProblem(parameters)) {
    return null;
  }
  const normalized = {};
  for (const field of CULTIVATION_PARAMETER_FIELDS) {
    normalized[field.key] = {
      min: parseCultivationBound(parameters[field.key].min),
      max: parseCultivationBound(parameters[field.key].max),
    };
  }
  return normalized;
}

function applyCultivationParametersToSensors(parameters) {
  state.dashboardSensors = state.dashboardSensors.map((sensor) => {
    const field = CULTIVATION_PARAMETER_FIELDS.find((item) => item.sensorId === sensor.id);
    if (!field) {
      return sensor;
    }

    return {
      ...sensor,
      min: parameters[field.key].min,
      max: parameters[field.key].max,
    };
  });
}

function syncCultivationPlantingDate(input) {
  const chosen = syncPlantingDateField(input);
  if (!chosen) {
    return;
  }
  state.cultivation.plantingDate = chosen;
  state.cultivation.harvestDate = "";
  state.cultivation.daysToHarvest = 0;
  state.cultivation.successMessage = "";
  state.cultivation.successOpen = false;
  updateHarvestButtonState();
}

function syncCultivationRowSelection(value) {
  state.cultivation.rowKey = value;
  state.cultivation.harvestDate = "";
  state.cultivation.daysToHarvest = 0;
  state.cultivation.successMessage = "";
  state.cultivation.successOpen = false;
  updateHarvestButtonState();
}

async function calculateHarvest() {
  const cropType = state.cultivation.cropType;
  // The chosen day while it is still this month, otherwise today. The server
  // keeps it if the request is approved within the same month, and plants on
  // the day of approval otherwise.
  const plantingDate = effectivePlantingDate();

  if (!supportsRecommendedCultivation(cropType)) {
    window.alert("Please select a crop type first.");
    return;
  }

  if (!state.cultivation.rowKey) {
    window.alert("Please choose a planting row.");
    return;
  }

  const existingCultivation = activeCultivationForRow(state.cultivation.rowKey);
  if (existingCultivation) {
    window.alert(`${cultivationRowLabel(state.cultivation.rowKey)} already has ${existingCultivation.crop}. Choose another row.`);
    return;
  }
  const pendingRequest = pendingCultivationRequestForRow(state.cultivation.rowKey);
  if (pendingRequest) {
    window.alert(`${cultivationRowLabel(state.cultivation.rowKey)} already has a request for ${pendingRequest.cropName} waiting for approval. Choose another row.`);
    return;
  }

  state.cultivation.cropType = cropType;
  state.cultivation.plantingDate = plantingDate;
  state.cultivation.parameterMode = "recommended";
  const selectedParameterMode = effectiveCultivationParameterMode(state.cultivation);
  if (!isCultivationParameterModeAvailable(selectedParameterMode, state.cultivation)) {
    window.alert("Recommended parameters are required for this account.");
    return;
  }

  const parameters = normalizeCultivationParameters(recommendedCultivationParameters(state.cultivation));
  if (!parameters) {
    window.alert("Recommended cultivation parameters are not available right now.");
    return;
  }

  const growthDays = selectedCultivationGrowthDays();
  const planting = parseDateInput(plantingDate);
  let harvest;

  harvest = new Date(planting);
  harvest.setDate(harvest.getDate() + growthDays);

  // A grower asks; an administrator plants. The request carries the crop,
  // row and dates only -- on approval the administrator's side applies the
  // recommended range for the crop, so nothing here can set the numbers.
  const requestJson = window.ICuCropsAuth?.requestJson;
  if (typeof requestJson !== "function") {
    pushNotification("warning", "The farm server is not reachable. Try again in a moment.");
    renderOverlays();
    return;
  }
  if (state.cultivationRequestSending) {
    return;
  }

  state.cultivationRequestSending = true;
  try {
    const response = await requestJson("/api/cultivations/requests", {
      method: "POST",
      body: {
        rowKey: state.cultivation.rowKey,
        cropType: state.cultivation.cropType,
        cropName: selectedCultivationName(),
        plantingDate: state.cultivation.plantingDate,
        harvestDate: formatDateInput(harvest),
        daysToHarvest: growthDays,
      },
    });
    state.cultivationRequests = mapCultivationRequests(response.requests);
    // Clear the row so the same request cannot be sent twice; the crop and
    // date stay for asking about another row.
    state.cultivation.rowKey = "";
    state.cultivation.harvestDate = "";
    state.cultivation.daysToHarvest = 0;
    state.cultivation.successMessage = "";
    state.cultivation.successOpen = false;
    state.cultivation.setupOpen = false;
    state.cultivation.parameterPreviewMode = "";
    await refreshNotifications({ render: false });
    pushNotification("success", response.message || "Request sent. An administrator will review it.");
    renderPage();
    renderOverlays();
  } catch (error) {
    if (Array.isArray(error?.payload?.requests)) {
      state.cultivationRequests = mapCultivationRequests(error.payload.requests);
    }
    pushNotification("warning", extractRequestMessage(error, "Unable to send the request right now."));
    renderOverlays();
  } finally {
    state.cultivationRequestSending = false;
  }
}

function selectCultivationCrop(cropType) {
  if (!supportsRecommendedCultivation(cropType)) {
    return;
  }

  state.cultivation.cropType = cropType;
  state.cultivation.harvestDate = "";
  state.cultivation.daysToHarvest = 0;
  state.cultivation.successMessage = "";
  state.cultivation.parameterMode = "recommended";
  state.cultivation.parameterPreviewMode = "";
  state.cultivation.setupOpen = true;
  state.cultivation.successOpen = false;
  renderPage();
  renderOverlays();
}

function resetViewState(view) {
  switch (view) {
    case "dashboard":
      restoreDashboardGraphRangesFromCache();
      return;
    case "history":
      // Back to one page on each visit. Leaving an expanded cap in place would
      // mean a later visit silently paints thousands of rows again, which is
      // the cost this paging exists to avoid.
      state.historyRenderLimit = HISTORY_RENDER_PAGE_SIZE;
      return;
    case "sensors":
      state.sensorsPage = sensorsPageStateWithCachedControls(state.sensorsPage);
      return;
    case "irrigation":
      state.irrigationPage = {
        ...state.irrigationPage,
        overlayMode: "",
      };
      return;
    case "cultivation":
      state.cultivation = initialCultivationState();
      return;
    case "reports":
      // The counts belong to the range that is on screen, so they are fetched
      // when the page opens rather than cached from the last visit.
      state.reports.downloadError = "";
      void refreshReportPreview();
      return;
    default:
      return;
  }
}

function syncViewFromHash(force = false) {
  const nextView = viewFromHash();
  window.clearTimeout(routeTransitionTimer);
  routeTransitionTimer = 0;

  if (!state.isAuthenticated) {
    state.activeView = nextView;
    state.notificationsOpen = false;
    closeSensorDetail(false);
    renderSidebar();
    renderHeader();
    renderPage();
    renderOverlays();
    renderToasts();
    return;
  }

  if (!force && nextView === state.activeView) {
    renderSidebar();
    renderHeader();
    renderPage();
    renderOverlays();
    renderToasts();
    restartDashboardNotificationTimers();
    return;
  }

  clearAllNotificationTimers();

  if (nextView === "history") {
    markAllNotificationsRead(false);
  }

  if (!pendingRouteTransition) {
    setPendingRouteTransition(state.activeView, nextView);
  }

  state.notificationsOpen = false;
  if (nextView === "irrigation" && state.activeView !== "irrigation") {
    clearLimeTankDeferrals();
  }
  state.activeView = nextView;
  resetViewState(nextView);
  closeSensorDetail(false);
  renderSidebar();
  renderHeader();
  renderPage();
  renderOverlays();
  renderToasts();
  restartDashboardNotificationTimers();
}

function viewFromHash() {
  const hash = window.location.hash.replace(/^#\/?/, "");
  if (!hash) {
    return "dashboard";
  }

  const legacyPiAliases = {
    controls: "dashboard",
    control: "dashboard",
    rows: "dashboard",
    row: "dashboard",
    tanks: "dashboard",
    tank: "dashboard",
  };
  const normalizedHash = legacyPiAliases[hash.toLowerCase()] || hash;
  return NAV_ITEMS.some((item) => item.view === normalizedHash) ? normalizedHash : "dashboard";
}

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
}

function viewIndex(view) {
  return VIEW_INDEX[view] ?? 0;
}

function routeTransitionDirection(fromView, toView) {
  return viewIndex(toView) >= viewIndex(fromView) ? "forward" : "backward";
}

function setPendingRouteTransition(fromView, toView) {
  if (!state.isAuthenticated || prefersReducedMotion() || fromView === toView) {
    pendingRouteTransition = null;
    return null;
  }

  pendingRouteTransition = {
    direction: routeTransitionDirection(fromView, toView),
  };
  return pendingRouteTransition;
}

function primeRouteExitAnimation(nextView) {
  const transition = setPendingRouteTransition(state.activeView, nextView);
  if (!transition || !elements.pageContent) {
    return false;
  }

  const currentScene = elements.pageContent.querySelector(".page-scene") || elements.pageContent.firstElementChild;
  if (!currentScene) {
    return false;
  }

  elements.pageContent.classList.remove(
    "page-content--transition-out",
    "page-content--transition-forward",
    "page-content--transition-backward"
  );

  void elements.pageContent.offsetWidth;

  elements.pageContent.classList.add(
    "page-content--transition-out",
    `page-content--transition-${transition.direction}`
  );

  return true;
}

function renderPageSceneMarkup(content, view) {
  const transition = pendingRouteTransition;
  const sceneClasses = ["page-scene"];

  if (transition) {
    sceneClasses.push("page-scene--incoming", `page-scene--${transition.direction}`);
  }

  return `
    <div class="${sceneClasses.join(" ")}" data-scene-view="${view}">
      ${content}
    </div>
  `;
}

function finalizeRouteTransition() {
  if (!elements.pageContent) {
    pendingRouteTransition = null;
    return;
  }

  elements.pageContent.classList.remove(
    "page-content--transition-out",
    "page-content--transition-forward",
    "page-content--transition-backward"
  );

  const scene = elements.pageContent.querySelector(".page-scene--incoming");
  if (!scene) {
    pendingRouteTransition = null;
    return;
  }

  window.requestAnimationFrame(() => {
    scene.classList.add("page-scene--ready");
  });

  pendingRouteTransition = null;
}

function updateProfilePreview() {
  const preview = document.getElementById("settings-avatar-preview");
  if (preview) {
    syncProfileAvatarElement(preview, "avatar-circle settings-profile-avatar");
  }
}

function hasExcessiveConsecutiveLetters(value) {
  return /(\p{L})\1{3}/iu.test(String(value || ""));
}

function profileNameValidationMessage(value) {
  const name = String(value || "");
  if (name.length > PROFILE_NAME_MAX_LENGTH) {
    return `Name cannot exceed ${PROFILE_NAME_MAX_LENGTH} characters.`;
  }
  if (hasExcessiveConsecutiveLetters(name)) {
    return "A letter cannot repeat more than 3 times in a row.";
  }

  const trimmedLength = name.trim().length;
  if (!trimmedLength) {
    return "Name is required.";
  }
  if (trimmedLength < PROFILE_NAME_MIN_LENGTH) {
    return `Name must contain at least ${PROFILE_NAME_MIN_LENGTH} characters.`;
  }
  return "";
}

function updateProfileNameValidationUI() {
  const input = document.getElementById("profile-name-input");
  const error = document.getElementById("profile-name-error");
  const message = state.profileNameError || profileNameValidationMessage(state.profileName);
  if (input instanceof HTMLInputElement) {
    input.setAttribute("aria-invalid", message ? "true" : "false");
  }
  if (error instanceof HTMLElement) {
    error.textContent = message;
    error.hidden = !message;
  }

  const saveButton = document.querySelector('[data-action="save-profile"]');
  if (saveButton instanceof HTMLButtonElement) {
    saveButton.disabled = Boolean(profileNameValidationMessage(state.profileName));
  }
}

// Built once here so the settings template draws the very same <img> the
// sync below would: when the two agree, the overlay morph finds nothing to
// change and the element that is already showing the photo stays put.
function profileAvatarMarkup(displayedName) {
  if (state.profilePhotoDataUrl) {
    return `<img src="${escapeHtml(state.profilePhotoDataUrl)}" alt="Profile photo" />`;
  }
  return escapeHtml((String(displayedName || "").trim() || "J").charAt(0).toUpperCase());
}

const profileImagesWithFallback = new WeakSet();

// Uploading a photo re-renders the header and the settings overlay four or
// five times. Each pass used to throw the <img> away and build a new one, and
// on a phone a new element for a remote photo paints blank until it decodes,
// so the avatar -- and the cards around it -- blinked on every pass. Keep the
// element; point it at a new URL only when the photo actually changed, which
// leaves the old picture on screen until the new one has loaded.
function syncProfileAvatarElement(element, baseClassName) {
  if (!(element instanceof HTMLElement)) {
    return;
  }

  const className = baseClassName || element.className;
  if (element.className !== className) {
    element.className = className;
  }
  const displayedName = element.id === "settings-avatar-preview" ? state.profileName : state.savedProfileName;
  const initial = (displayedName.trim() || "J").charAt(0).toUpperCase();
  const photoUrl = state.profilePhotoDataUrl;

  if (photoUrl) {
    let profileImage = element.querySelector("img");
    if (!(profileImage instanceof HTMLImageElement)) {
      element.innerHTML = profileAvatarMarkup(displayedName);
      profileImage = element.querySelector("img");
    } else if (profileImage.getAttribute("src") !== photoUrl) {
      profileImage.setAttribute("src", photoUrl);
    }
    if (element.getAttribute("aria-label") !== "Profile photo") {
      element.setAttribute("aria-label", "Profile photo");
    }
    if (profileImage && !profileImagesWithFallback.has(profileImage)) {
      profileImagesWithFallback.add(profileImage);
      profileImage.addEventListener("error", () => {
        if (!profileImage.isConnected || profileImage.getAttribute("src") !== state.profilePhotoDataUrl) {
          return;
        }
        state.profilePhotoDataUrl = "";
        element.textContent = initial;
        element.setAttribute("aria-label", "Profile initial");
      });
    }
    return;
  }

  if (element.querySelector("img") || element.textContent.trim() !== initial) {
    element.textContent = initial;
  }
  if (element.getAttribute("aria-label") !== "Profile initial") {
    element.setAttribute("aria-label", "Profile initial");
  }
}

function updateSettingsButtonStates() {
  const newPasswordInput = document.getElementById("new-password-input");
  const passwordError = document.getElementById("profile-password-error");
  const showPasswordError = Boolean(state.newPassword) && !isValidNewPassword(state.newPassword);
  if (newPasswordInput instanceof HTMLInputElement) {
    newPasswordInput.setAttribute("aria-invalid", showPasswordError ? "true" : "false");
  }
  if (passwordError instanceof HTMLElement) {
    passwordError.textContent = showPasswordError ? PASSWORD_POLICY_MESSAGE : "";
    passwordError.hidden = !showPasswordError;
  }

  const passwordButton = document.querySelector('[data-action="change-password"]');
  if (passwordButton) {
    passwordButton.disabled = state.passwordChangeSubmitting
      || !state.currentPassword
      || !isValidNewPassword(state.newPassword);
  }

  const verifyButton = document.querySelector('[data-action="verify-otp"]');
  if (verifyButton) {
    verifyButton.disabled = state.passwordChangeSubmitting || state.otpCode.some((digit) => !digit);
  }
}

function updateLoginButtonState() {
  const button = document.querySelector('[data-action="submit-login"]');
  if (button) {
    button.disabled = !state.loginForm.email.trim() || !state.loginForm.password;
  }
}

function togglePasswordVisibility(targetId) {
  if (!targetId) {
    return;
  }

  const input = document.getElementById(targetId);
  if (!(input instanceof HTMLInputElement)) {
    return;
  }

  input.type = input.type === "password" ? "text" : "password";
  syncPasswordToggleButtons(input.closest(".page-content") || document);
  input.focus({ preventScroll: true });
  const valueLength = input.value.length;
  if (typeof input.setSelectionRange === "function") {
    input.setSelectionRange(valueLength, valueLength);
  }
}

function syncPasswordToggleButtons(root = document) {
  const scope = root instanceof Element || root instanceof Document ? root : document;
  scope.querySelectorAll("[data-action='toggle-password-visibility']").forEach((button) => {
    const targetId = button.dataset.target;
    if (!targetId) {
      return;
    }

    const input = document.getElementById(targetId);
    if (!(input instanceof HTMLInputElement)) {
      return;
    }

    const visible = input.type === "text";
    button.setAttribute("aria-label", visible ? "Hide password" : "Show password");
    const iconSlot = button.querySelector("[data-password-icon]");
    if (iconSlot) {
      replaceInnerMarkupIfChanged(iconSlot, passwordEyeIconMarkup(visible));
    }
  });
}

// settings-profile.js draws the eye into the change-password field itself,
// because the settings overlay is rendered as one string before any of its
// buttons exist for syncPasswordToggleButtons to reach. The administrator
// shell has always had this; the user shell did not, so opening Edit Profile
// threw a ReferenceError mid-render and no modal ever appeared.
function passwordEyeIconMarkup(visible) {
  const paths = visible
    ? '<path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"></path><circle cx="12" cy="12" r="3"></circle>'
    : '<path d="m3 3 18 18"></path><path d="M10.58 10.58a2 2 0 0 0 2.83 2.83"></path><path d="M9.88 5.08A10.94 10.94 0 0 1 12 5c6 0 10 7 10 7a18.74 18.74 0 0 1-3.04 3.81"></path><path d="M6.61 6.61A18.7 18.7 0 0 0 2 12s4 7 10 7a9.76 9.76 0 0 0 5.39-1.61"></path>';
  return `<svg class="icon password-eye-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
}

function updateHarvestButtonState() {
  const buttons = document.querySelectorAll('[data-action="calculate-harvest"]');
  buttons.forEach((button) => {
    button.disabled = !canCalculateCultivation();
  });
}

function loginUser() {
  const email = state.loginForm.email.trim();
  const password = state.loginForm.password;
  if (!email || !password) {
    updateLoginButtonState();
    return;
  }

  state.isAuthenticated = true;
  state.loginForm.password = "";
  state.settingsOpen = false;
  state.notificationsOpen = false;
  state.showAddUserModal = false;
  closeSensorDetail(false);
  navigateTo("dashboard");
}

function logoutUser() {
  state.logoutConfirmOpen = false;
  releaseProfilePhotoObjectUrl();
  window.ICuCropsAuth?.clearSession?.();
  window.sessionStorage.removeItem("arugula.user.isAuthenticated");
  window.sessionStorage.removeItem("arugula.user.postLoginHash");
  const logoutUrl = new URL("./dashboard.html", window.location.href);
  logoutUrl.search = window.location.search;
  logoutUrl.searchParams.set("logout", "1");
  window.location.replace(logoutUrl.toString());
}

function requestPasswordReset() {
  if (!state.loginForm.email.trim()) {
    window.alert("Enter your email first before resetting your password.");
    return;
  }

  window.alert(`Password reset link sent to ${state.loginForm.email.trim()}.`);
}

function applyProfilePhotoFile(input, file) {
  // Hand the picked file to the same validation path a native selection takes,
  // so the size and type rules live in one place.
  try {
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
  } catch (error) {
    // DataTransfer is missing in a few embedded builds; the selection handler
    // only ever reads .files, so a stand-in carries the same information.
    handleProfilePhotoSelection({ files: [file], value: "" });
    return;
  }

  handleProfilePhotoSelection(input);
}

function handleProfilePhotoSelection(input) {
  const [file] = Array.from(input.files || []);
  if (!file) {
    return;
  }

  if (!file.type.startsWith("image/")) {
    input.value = "";
    pushNotification("warning", "Please choose a valid image file.");
    return;
  }

  if (file.size > MAX_PROFILE_PHOTO_BYTES) {
    input.value = "";
    pushNotification("warning", "Profile photo must be 5 MB or smaller.");
    return;
  }

  releaseProfilePhotoObjectUrl();
  state.selectedProfilePhotoFile = file;
  state.profilePhotoObjectUrl = URL.createObjectURL(file);
  state.profilePhotoDataUrl = state.profilePhotoObjectUrl;
  renderHeader();
  renderOverlays();
  pushNotification("success", "Photo selected. Uploading now...");
  void saveProfile({ includePhoto: true, includeName: false, successMessage: "Profile photo saved successfully." });
  input.value = "";
}

async function saveProfile(options = {}) {
  const requestJson = window.ICuCropsAuth?.requestJson;
  const userId = await resolveAuthenticatedSessionUserId();
  const includeName = options.includeName !== false;
  const displayName = (includeName ? state.profileName : state.savedProfileName).trim();
  const includePhoto = options.includePhoto !== false;
  const successMessage = String(options.successMessage || "Profile updated successfully.");

  const validationMessage = profileNameValidationMessage(displayName);
  if (validationMessage) {
    state.profileNameError = validationMessage;
    updateProfileNameValidationUI();
    return;
  }

  if (!userId || typeof requestJson !== "function") {
    pushNotification("warning", "Profile could not be saved because the backend session is missing.");
    return;
  }

  const formData = new FormData();
  formData.set("display_name", displayName);
  if (includePhoto && state.selectedProfilePhotoFile instanceof File) {
    formData.set("profile_photo", state.selectedProfilePhotoFile);
  }

  // The backend bumps the profile version as soon as it stores the change, and
  // on a phone the upload can still be in flight for seconds after that. Mark
  // the mutation up front, or the realtime poll treats this very save as a
  // remote edit and repaints the header and the overlay mid-upload.
  window.icuCropsRealtimeSync?.markLocalMutation?.("profile", PROFILE_SAVE_SYNC_SUPPRESS_MS);

  try {
    const response = await requestJson(`/api/profile/${encodeURIComponent(userId)}`, {
      method: "POST",
      body: formData,
    });
    const user = response.user || {};
    state.savedProfileName = String(user.displayName || displayName).trim() || displayName;
    if (includeName) {
      state.profileName = state.savedProfileName;
      state.profileNameError = "";
    }
    state.profileRole = String(user.roleLabel || state.profileRole).trim() || state.profileRole;
    state.selectedProfilePhotoFile = null;
    releaseProfilePhotoObjectUrl();
    state.profilePhotoDataUrl = String(user.profilePhotoUrl || "").trim();
    syncAuthenticatedProfileSession(user);
    window.icuCropsRealtimeSync?.markLocalMutation?.("profile");
    renderHeader();
    renderOverlays();
    pushNotification("success", response.message || successMessage);
  } catch (error) {
    window.icuCropsRealtimeSync?.markLocalMutation?.("profile", 0);
    pushNotification("warning", extractRequestMessage(error, "Unable to save the profile right now."));
    renderOverlays();
  }
}

async function requestPasswordChange() {
  if (!state.currentPassword || !state.newPassword) {
    updateSettingsButtonStates();
    return;
  }

  if (!isValidNewPassword(state.newPassword)) {
    pushNotification("warning", PASSWORD_POLICY_MESSAGE);
    updateSettingsButtonStates();
    return;
  }

  // Recover the id rather than refusing outright: the session may be valid and
  // simply missing it, which is what an older stored session looks like.
  const userId = await resolveAuthenticatedSessionUserId();
  const requestJson = window.ICuCropsAuth?.requestJson;
  if (!userId || typeof requestJson !== "function") {
    pushNotification("warning", "Logged-in account could not be detected.");
    return;
  }

  state.passwordChangeSubmitting = true;
  updateSettingsButtonStates();

  try {
    const response = await requestJson(`/api/profile/${encodeURIComponent(userId)}/password/request-otp`, {
      method: "POST",
      timeoutMs: PASSWORD_OTP_REQUEST_TIMEOUT_MS,
      body: {
        currentPassword: state.currentPassword,
        newPassword: state.newPassword,
      },
    });

    state.passwordChangeChallengeId = String(response.challengeId || "").trim();
    state.passwordChangeOtpRequested = Boolean(state.passwordChangeChallengeId);
    state.otpCode = initialOtpCode();
    state.passwordChangeSubmitting = false;
    renderOverlays();
    pushNotification("success", response.message || "OTP sent to your logged-in Gmail.");
  } catch (error) {
    state.passwordChangeSubmitting = false;
    pushNotification("warning", extractRequestMessage(error, "Unable to send OTP right now."));
    renderOverlays();
    updateSettingsButtonStates();
    return;
  }

  const firstOtpInput = document.getElementById("otp-0");
  if (firstOtpInput instanceof HTMLInputElement) {
    firstOtpInput.focus();
  }
}

async function completePasswordChange() {
  if (
    state.passwordChangeSubmitting
    || !state.passwordChangeOtpRequested
    || !state.passwordChangeChallengeId
    || state.otpCode.some((digit) => !digit)
  ) {
    updateSettingsButtonStates();
    return;
  }

  // Recover the id rather than refusing outright: the session may be valid and
  // simply missing it, which is what an older stored session looks like.
  const userId = await resolveAuthenticatedSessionUserId();
  const requestJson = window.ICuCropsAuth?.requestJson;
  if (!userId || typeof requestJson !== "function") {
    pushNotification("warning", "Logged-in account could not be detected.");
    return;
  }

  state.passwordChangeSubmitting = true;
  updateSettingsButtonStates();

  try {
    const response = await requestJson(`/api/profile/${encodeURIComponent(userId)}/password/confirm`, {
      method: "POST",
      timeoutMs: PASSWORD_CONFIRM_TIMEOUT_MS,
      body: {
        challengeId: state.passwordChangeChallengeId,
        otp: state.otpCode.join(""),
        newPassword: state.newPassword,
      },
    });
    resetPasswordChangeState();
    window.icuCropsRealtimeSync?.markLocalMutation?.("profile");
    renderOverlays();
    pushNotification("success", response.message || "Password changed successfully.");
  } catch (error) {
    state.passwordChangeSubmitting = false;
    state.otpCode = initialOtpCode();
    pushNotification("warning", extractRequestMessage(error, "Unable to change password right now."));
    renderOverlays();
    updateSettingsButtonStates();
  }
}

function handleOtpInput(target) {
  const index = Number(target.id.split("-")[1]);
  const sanitized = target.value.replace(/\D/g, "").slice(0, 1);
  const wasEmpty = !state.otpCode[index];
  target.value = sanitized;
  state.otpCode[index] = sanitized;

  // Backspace on the Pi panel, whose keyboard sends only "input": a box that
  // held a digit is cleared and keeps the caret; an already-empty box clears
  // the one before it and moves there. See handleNewUserOtpInput.
  if (!sanitized && wasEmpty && index > 0) {
    state.otpCode[index - 1] = "";
    const previous = document.getElementById(`otp-${index - 1}`);
    if (previous instanceof HTMLInputElement) {
      previous.value = "";
      previous.focus();
    }
  }
  updateSettingsButtonStates();

  if (state.passwordChangeOtpRequested && state.otpCode.every(Boolean)) {
    completePasswordChange();
    return;
  }

  if (sanitized && index < state.otpCode.length - 1) {
    const next = document.getElementById(`otp-${index + 1}`);
    next?.focus();
  }
}

function resetPasswordChangeState(clearPasswords = true) {
  if (clearPasswords) {
    state.currentPassword = "";
    state.newPassword = "";
  }

  state.otpCode = initialOtpCode();
  state.passwordChangeOtpRequested = false;
  state.passwordChangeChallengeId = "";
  state.passwordChangeSubmitting = false;
}

function glowClass(status) {
  if (status === "warning") {
    return "glow-warning";
  }
  if (status === "critical") {
    return "glow-critical";
  }
  return "glow-normal";
}

function pillClass(status) {
  if (status === "warning") {
    return "pill--warning";
  }
  if (status === "critical") {
    return "pill--critical";
  }
  return "pill--normal";
}

function progressClass(status) {
  if (status === "warning") {
    return "progress-fill--warning";
  }
  if (status === "critical") {
    return "progress-fill--critical";
  }
  return "";
}

function statusIconName(status) {
  if (status === "warning") {
    return "trending-down";
  }
  if (status === "critical") {
    return "trending-up";
  }
  return "minus";
}

function toastIconName(type) {
  // Critical and warning are the same kind of thing -- something is wrong --
  // and differ only in degree, so they share the warning triangle and are
  // told apart by colour: red for critical, amber for warning. The tone is
  // already set by .notification-item--critical / --warning, so the shape does
  // not have to carry that difference as well.
  //
  // Critical used to be an x-circle, which reads as "cancelled", "closed" or
  // "failed to happen" -- the same glyph the dismiss and close buttons use.
  // A soil-moisture reading below its minimum is not a cancelled anything, and
  // pairing the X with the check-circle beside it turned the list into a
  // yes/no column instead of a severity one.
  if (type === "warning" || type === "critical") {
    return "alert-triangle";
  }
  return "check-circle";
}

function notificationPillClass(type) {
  if (type === "warning") {
    return "pill--warning";
  }
  if (type === "critical") {
    return "pill--critical";
  }
  return "pill--normal";
}

function cultivationDateIsInCurrentYear(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || "").trim());
  if (!match || Number.parseInt(match[1], 10) !== CULTIVATION_CURRENT_YEAR) {
    return false;
  }
  const parsed = parseDateInput(value);
  return !Number.isNaN(parsed.getTime())
    && parsed.getFullYear() === CULTIVATION_CURRENT_YEAR
    && parsed.getMonth() === Number.parseInt(match[2], 10) - 1
    && parsed.getDate() === Number.parseInt(match[3], 10);
}

function parseDateInput(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatDateInput(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatLongDate(value) {
  const date = parseDateInput(value);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

// A crop is planted this month. The farm asked for the month and year to be
// locked -- a planting set in the wrong month or year threw off the countdown,
// the harvest check and the schedules -- while the day stays choosable. The
// calendar only offers this month's days, and the server holds the same rule
// by its own clock (a request approved in a later month is planted that day).
function todayPlantingDate() {
  return formatDateInput(new Date());
}

function currentPlantingMonthBounds() {
  const now = new Date();
  return {
    min: formatDateInput(new Date(now.getFullYear(), now.getMonth(), 1)),
    max: formatDateInput(new Date(now.getFullYear(), now.getMonth() + 1, 0)),
  };
}

function plantingDateInCurrentMonth(value) {
  const { min, max } = currentPlantingMonthBounds();
  const text = String(value || "");
  return /^\d{4}-\d{2}-\d{2}$/.test(text) && text >= min && text <= max;
}

// The chosen day while it is still in this month, otherwise today.
function effectivePlantingDate() {
  return plantingDateInCurrentMonth(state.cultivation.plantingDate)
    ? state.cultivation.plantingDate
    : todayPlantingDate();
}

function cultivationPlantingDateTemplate(id) {
  const { min, max } = currentPlantingMonthBounds();
  return `
    <div class="field">
      <label class="field__label" for="${id}">Planting Date</label>
      <div class="date-picker-control">
        <input
          class="input"
          id="${id}"
          type="date"
          min="${min}"
          max="${max}"
          value="${effectivePlantingDate()}"
          data-planting-month="${min}"
        />
      </div>
    </div>
  `;
}

// A day typed outside this month is put back rather than taken.
function syncPlantingDateField(input) {
  if (plantingDateInCurrentMonth(input.value)) {
    return input.value;
  }
  input.value = effectivePlantingDate();
  return "";
}

// Keeps the calendar on the current month: a form left open into a new month
// moves its bounds, and a day from the old month becomes today.
function refreshPlantingMonthFields() {
  const { min, max } = currentPlantingMonthBounds();
  document.querySelectorAll("[data-planting-month]").forEach((element) => {
    if (element.dataset.plantingMonth !== min) {
      element.dataset.plantingMonth = min;
      element.min = min;
      element.max = max;
      element.value = effectivePlantingDate();
    }
  });
}

window.setInterval(refreshPlantingMonthFields, 30000);

function cultivationRemainingDays(harvestDate) {
  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const diffMs = parseDateInput(harvestDate).getTime() - startOfToday.getTime();
  return Math.ceil(diffMs / 86400000);
}

function cultivationRemainingLabel(days) {
  if (days <= 0) {
    return "Ready for harvest";
  }

  return `${days} day${days === 1 ? "" : "s"} remaining`;
}

function cultivationRemainingColor(days) {
  if (days <= 3) {
    return "var(--amber-500)";
  }

  return "var(--green-600)";
}

function buildActiveCultivationEntry({ crop, rowKey, plantingDate, harvestDate }) {
  const remainingDays = cultivationRemainingDays(harvestDate);
  return {
    id: `active-cultivation-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    rowKey: String(rowKey || "").trim(),
    rowLabel: cultivationRowLabel(rowKey),
    crop: String(crop || "").trim() || "Cultivation",
    accent: "var(--green-500)",
    plantingDate,
    planted: formatLongDate(plantingDate),
    remaining: cultivationRemainingLabel(remainingDays),
    harvestDate,
    harvest: formatLongDate(harvestDate),
    remainingColor: cultivationRemainingColor(remainingDays),
  };
}

function formatNotificationTimestamp(value) {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function capitalize(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function icon(name, className = "icon") {
  const iconName = Object.prototype.hasOwnProperty.call(ICONS, name) ? name : "info";
  const iconRef = `${ICON_SPRITE_PATH}#icon-${iconName}`;
  return `<svg class="${className}" viewBox="0 0 24 24" aria-hidden="true"><use href="${iconRef}" xlink:href="${iconRef}"></use></svg>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function preloadExternalTemplates() {
  const sections = Object.entries(window.settingsSectionRegistry || {});
  await Promise.all(
    sections.map(async ([key, section]) => {
      const template = await readExternalTemplate(section.path);
      if (template) {
        externalTemplateCache.set(key, template);
      }
    }),
  );
}

async function readExternalTemplate(path) {
  try {
    const response = await fetch(path, { cache: "no-store" });
    if (response.ok) {
      return await response.text();
    }
  } catch (error) {
    const fallback = readExternalTemplateSync(path);
    if (fallback) {
      return fallback;
    }
    console.warn(`Unable to fetch external template: ${path}`, error);
  }

  return "";
}

function readExternalTemplateSync(path) {
  try {
    const request = new XMLHttpRequest();
    request.open("GET", path, false);
    request.send(null);

    if ((request.status >= 200 && request.status < 300) || request.status === 0) {
      return request.responseText;
    }
  } catch (error) {
    console.warn(`Unable to synchronously load external template: ${path}`, error);
  }

  return "";
}

function renderExternalTemplate(sectionKey) {
  const section = window.settingsSectionRegistry?.[sectionKey];
  if (!section) {
    return `
      <div class="center-banner">
        This settings section is not available right now.
      </div>
    `;
  }

  let template = externalTemplateCache.get(sectionKey);
  if (!template) {
    template = readExternalTemplateSync(section.path);
    if (template) {
      externalTemplateCache.set(sectionKey, template);
    }
  }

  if (!template) {
    return `
      <div class="center-banner">
        Unable to load the ${escapeHtml(sectionKey)} section template.
      </div>
    `;
  }

  return section.render(template);
}

function replaceTemplateTokens(template, tokens) {
  return Object.entries(tokens).reduce(
    (markup, [token, value]) => markup.replaceAll(`{{${token}}}`, value ?? ""),
    template,
  );
}

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

function initialReportsState() {
  const today = new Date();
  const start = new Date(today);
  start.setDate(start.getDate() - 29);

  return {
    startDate: toDateInputValue(start),
    endDate: toDateInputValue(today),
    preset: "30d",
    rowKey: "",
    format: "pdf",
    // Every dataset is on by default: the common case is a full record, and a
    // farmer who wants a narrower one unticks rather than hunts.
    sections: REPORT_DATA_SECTIONS.map((section) => section.key),
    preview: null,
    previewLoading: false,
    previewError: "",
    downloading: "",
    downloadError: "",
    recent: readRecentReports(),
  };
}

function toDateInputValue(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function readRecentReports() {
  // The download list is a convenience, not a record. It lives in this browser
  // so it survives a reload without the backend having to store per-user files
  // it would then have to expire.
  try {
    const raw = window.localStorage.getItem(REPORTS_RECENT_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed.filter((item) => item?.format === "pdf").slice(0, 6)
      : [];
  } catch (error) {
    return [];
  }
}

function rememberRecentReport(entry) {
  const recent = [entry, ...state.reports.recent.filter((item) => item.id !== entry.id)].slice(0, 6);
  state.reports.recent = recent;
  try {
    window.localStorage.setItem(REPORTS_RECENT_KEY, JSON.stringify(recent));
  } catch (error) {
    // A full or blocked storage quota must not stop the download itself.
  }
}

function reportRangeLabel() {
  const { startDate, endDate } = state.reports;
  const start = parseDateInputValue(startDate);
  const end = parseDateInputValue(endDate);
  if (!start || !end) {
    return "Choose a date range";
  }
  const sameYear = start.getFullYear() === end.getFullYear();
  const startText = `${REPORT_MONTHS[start.getMonth()]} ${start.getDate()}${sameYear ? "" : `, ${start.getFullYear()}`}`;
  const endText = `${REPORT_MONTHS[end.getMonth()]} ${end.getDate()}, ${end.getFullYear()}`;
  return `${startText} to ${endText}`;
}



function parseDateInputValue(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || "").trim());
  if (!match) {
    return null;
  }
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

function applyReportPreset(presetKey) {
  const preset = REPORT_RANGE_PRESETS.find((item) => item.key === presetKey);
  if (!preset) {
    return;
  }

  const today = new Date();
  state.reports.preset = preset.key;
  state.reports.endDate = toDateInputValue(today);

  if (preset.key === "planting") {
    // "Since Planting" means the oldest planting date still on the farm, so the
    // report covers this cycle rather than an arbitrary number of days.
    const plantingDates = (state.activeCultivations || [])
      .map((cultivation) => parseDateInputValue(cultivation.plantingDate))
      .filter(Boolean)
      .sort((left, right) => left - right);
    const earliest = plantingDates[0];
    if (earliest) {
      state.reports.startDate = toDateInputValue(earliest);
    } else {
      const fallback = new Date(today);
      fallback.setDate(fallback.getDate() - 29);
      state.reports.startDate = toDateInputValue(fallback);
      pushNotification("info", "No planting date on record yet, so the last 30 days were used.");
    }
  } else {
    const start = new Date(today);
    start.setDate(start.getDate() - preset.days);
    state.reports.startDate = toDateInputValue(start);
  }

  renderPage();
  void refreshReportPreview();
}

function toggleReportSection(sectionKey) {
  const hadSections = state.reports.sections.length > 0;
  const selected = new Set(state.reports.sections);
  if (selected.has(sectionKey)) {
    selected.delete(sectionKey);
  } else {
    selected.add(sectionKey);
  }
  state.reports.sections = REPORT_DATA_SECTIONS
    .map((section) => section.key)
    .filter((key) => selected.has(key));
  // The preview counts the period, not the tick boxes: the backend echoes
  // `sections` straight back and never queries on it. Refetching here spent a
  // full round trip -- on the hosted site, seconds of it against the report
  // tables -- to redraw numbers that cannot have changed, and every toggle
  // blanked the tiles while it ran. Only the range and row filter need one.
  //
  // Emptying the list still has to clear the tiles, and ticking the first one
  // back has to bring them in: that is the one thing the removed refresh was
  // still carrying, and refreshReportPreview() returns early without a request
  // in both directions, so ask for it only when the list crosses empty.
  if (!state.reports.sections.length) {
    state.reports.preview = null;
    state.reports.previewError = "";
    renderPage();
    return;
  }
  if (!hadSections) {
    renderPage();
    void refreshReportPreview();
    return;
  }
  renderPage();
}

function reportRequestPayload() {
  return {
    startDate: state.reports.startDate,
    endDate: state.reports.endDate,
    rowKey: state.reports.rowKey,
    sections: state.reports.sections,
    // The server stores timestamps in UTC. Sending the viewer's offset is what
    // makes a 6:00 AM irrigation run read as 6:00 AM in the report.
    timezoneOffsetMinutes: -new Date().getTimezoneOffset(),
  };
}

let reportPreviewToken = 0;

async function refreshReportPreview() {
  const requestJson = window.ICuCropsAuth?.requestJson;
  if (typeof requestJson !== "function") {
    return;
  }
  if (!state.reports.sections.length) {
    state.reports.preview = null;
    state.reports.previewError = "";
    renderPage();
    return;
  }

  const token = ++reportPreviewToken;
  state.reports.previewLoading = true;
  state.reports.previewError = "";
  renderPage();

  try {
    const response = await requestJson("/api/reports/preview", {
      method: "POST",
      body: reportRequestPayload(),
      // The hosted backend cold-starts and reads across the network, which the
      // 10s default deadline cut off before the first answer arrived.
      timeoutMs: REPORT_PREVIEW_TIMEOUT_MS,
    });
    // A slower earlier request must not overwrite a newer answer.
    if (token !== reportPreviewToken || state.activeView !== "reports") {
      return;
    }
    state.reports.preview = response;
    state.reports.previewLoading = false;
    renderPage();
  } catch (error) {
    if (token !== reportPreviewToken) {
      return;
    }
    state.reports.previewLoading = false;
    state.reports.preview = null;
    state.reports.previewError = extractRequestMessage(
      error,
      "Unable to read the farm records right now.",
    );
    renderPage();
  }
}

async function downloadReport(format) {
  const normalizedFormat = "pdf";
  if (state.reports.downloading) {
    return;
  }
  if (!state.reports.sections.length) {
    pushNotification("warning", "Choose at least one dataset before downloading.");
    return;
  }

  state.reports.downloading = normalizedFormat;
  state.reports.downloadError = "";
  renderPage();

  try {
    const blob = await requestReportFile({ ...reportRequestPayload(), format: normalizedFormat });
    await saveReportBlob(blob.content, blob.filename);
    rememberRecentReport({
      id: `${Date.now()}-${normalizedFormat}`,
      name: reportDisplayName(),
      format: normalizedFormat,
      filename: blob.filename,
      createdAt: new Date().toISOString(),
      createdBy: state.profileName || "Administrator",
    });
    pushNotification(
      "success",
      "PDF report download started.",
    );
  } catch (error) {
    state.reports.downloadError = extractRequestMessage(
      error,
      "The report could not be generated. Please try again.",
    );
    pushNotification("warning", state.reports.downloadError);
  } finally {
    state.reports.downloading = "";
    renderPage();
  }
}

function reportDisplayName() {
  return `Farm Report (${reportRangeLabel()})`;
}

async function requestReportFile(payload) {
  // The download goes through the shared auth helper so it resolves the API
  // base exactly the way every other call does. Building a URL from
  // ICuCropsRuntimeConfig.apiBase alone pointed at a fixed port, which is the
  // wrong host on the Pi and on any dev server that is not on that port.
  const requestBlob = window.ICuCropsAuth?.requestBlob;
  if (typeof requestBlob !== "function") {
    throw new Error("This browser session cannot download files. Please sign in again.");
  }

  const result = await requestBlob("/api/reports/export", {
    method: "POST",
    body: payload,
    // A month of readings takes the server longer to assemble than a normal
    // API call, and timing out mid-build would leave nothing to show for it.
    timeoutMs: REPORT_EXPORT_TIMEOUT_MS,
  });

  return {
    content: result.blob,
    filename: result.filename
      || "ICuCrops-Report.pdf",
  };
}

async function saveReportBlob(blob, filename) {
  if (!(blob instanceof Blob) || blob.size <= 0) {
    throw new Error("The server returned an empty report file. Please try again.");
  }

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  link.hidden = true;
  document.body.appendChild(link);
  try {
    link.click();
  } catch (error) {
    link.remove();
    URL.revokeObjectURL(url);
    throw error;
  }
  // Keep both the anchor and its object URL alive long enough for Chrome to
  // consume them. A zero-delay revoke raced the browser's download service and
  // could show a success notice without ever creating a file.
  //
  // Sixty seconds was far longer than that hand-off needs, and an object URL
  // pins the whole file in memory until it is revoked: three exports in a row
  // held three PDFs at once, which on a farm with over a million readings is
  // tens of megabytes of live blob and a tab that crawls until they expire.
  // That is why clearing the list appeared to fix it -- the wait had simply
  // run out by then. A few seconds covers the hand-off with room to spare.
  window.setTimeout(() => {
    link.remove();
    URL.revokeObjectURL(url);
  }, REPORT_BLOB_RELEASE_MS);
  return "browser-download";
}

function reportsTemplate() {
  const reports = state.reports;
  const preview = reports.preview;
  const counts = preview?.counts || {};

  // A count the backend stopped early is shown as "10,000+": presenting a
  // capped number plainly would read as the exact total and be wrong.
  const tileCount = (value, capped = false) => {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      return "0";
    }
    return `${number.toLocaleString()}${capped ? "+" : ""}`;
  };

  const summaryTiles = [
    {
      label: "Sensor readings",
      value: tileCount(counts.readings, counts.readingsCapped),
      icon: "activity",
    },
    { label: "Irrigation runs", value: tileCount(counts.irrigationRuns), icon: "droplets" },
    { label: "Alerts raised", value: tileCount(counts.alerts), icon: "bell" },
    { label: "Cultivations", value: tileCount(counts.cultivations), icon: "sprout" },
  ];

  return `
    <section class="page-stack reports-page">
      <div class="page-heading">
        <div>
          <h1>Reports</h1>
          <p>Export a printable PDF built from your farm records and sensor readings.</p>
        </div>
        <div class="chip-row">
          <span class="chip">${escapeHtml(reportRangeLabel())}</span>
          <span class="chip">${reports.sections.length} of ${REPORT_DATA_SECTIONS.length} datasets</span>
        </div>
      </div>

      <article class="glass-card card page-stack report-builder">
        <div class="card-head">
          <div>
            <h3 class="section-title">Build Your Report</h3>
            <p class="section-copy">Pick the period. The PDF covers every row and uses the readings recorded in that range.</p>
          </div>
        </div>

        <div class="report-presets" role="group" aria-label="Quick date ranges">
          ${REPORT_RANGE_PRESETS.map((preset) => `
            <button
              class="report-preset${reports.preset === preset.key ? " is-active" : ""}"
              type="button"
              data-action="report-preset"
              data-id="${preset.key}"
              aria-pressed="${reports.preset === preset.key ? "true" : "false"}"
            >${escapeHtml(preset.label)}</button>
          `).join("")}
        </div>
      </article>

      <div class="grid report-grid">
        <article class="glass-card card page-stack report-datasets">
          <div>
            <h3 class="section-title">Include in Report</h3>
            <p class="section-copy">Untick anything you do not need. The file shrinks with it.</p>
          </div>
          <div class="report-dataset-list">
            ${REPORT_DATA_SECTIONS.map((section) => {
              const checked = reports.sections.includes(section.key);
              return `
                <button
                  class="report-dataset${checked ? " is-checked" : ""}"
                  type="button"
                  role="checkbox"
                  aria-checked="${checked ? "true" : "false"}"
                  data-action="report-toggle-section"
                  data-id="${section.key}"
                >
                  <span class="report-dataset__box" aria-hidden="true">${checked ? icon("check-circle") : ""}</span>
                  <span class="report-dataset__copy">
                    <span class="report-dataset__label">${escapeHtml(section.label)}</span>
                    <span class="report-dataset__hint">${escapeHtml(section.hint)}</span>
                  </span>
                </button>
              `;
            }).join("")}
          </div>
        </article>

        <article class="glass-card card page-stack report-summary">
          <div>
            <h3 class="section-title">What This Covers</h3>
            <p class="section-copy">${escapeHtml(reportRangeLabel())}</p>
          </div>

          ${reports.previewError ? `
            <div class="report-notice report-notice--warning">${escapeHtml(reports.previewError)}</div>
          ` : ""}

          <div class="report-summary-grid">
            ${summaryTiles.map((tile) => `
              <div class="report-summary-tile">
                <span class="report-summary-tile__icon" aria-hidden="true">${icon(tile.icon)}</span>
                <span class="report-summary-tile__value">${
                  reports.previewLoading || !preview
                    ? '<span class="report-skeleton" aria-hidden="true"></span>'
                    : escapeHtml(tile.value)
                }</span>
                <span class="report-summary-tile__label">${escapeHtml(tile.label)}</span>
              </div>
            `).join("")}
          </div>

          ${!reports.sections.length ? `
            <div class="report-notice">Choose at least one dataset to export.</div>
          ` : ""}

          <div class="report-actions">
            <button
              class="button button--primary report-download"
              type="button"
              data-action="report-download"
              data-id="pdf"
              ${reports.downloading || !reports.sections.length ? "disabled" : ""}
            >
              ${icon("download")}
              <span>${
                reports.downloading === "pdf"
                  ? "Preparing file..."
                  : "Download PDF"
              }</span>
            </button>
          </div>
        </article>
      </div>

      ${preview?.rowHealth?.length ? `
        <article class="glass-card card page-stack report-rows">
          <div>
            <h3 class="section-title">Row Health in This Period</h3>
            <p class="section-copy">Scored on how much of each row's readings sat inside its crop targets.</p>
          </div>
          <div class="report-row-grid">
            ${preview.rowHealth.map((row) => `
              <div class="report-row-card">
                <div class="report-row-card__head">
                  <span class="report-row-card__label">${escapeHtml(row.label)}</span>
                  <span class="report-row-card__crop">${escapeHtml(row.crop)}</span>
                </div>
                <div class="report-row-card__score">
                  <span class="report-row-card__value">${row.score === null ? "n/a" : `${escapeHtml(String(row.score))}%`}</span>
                  <span class="report-grade report-grade--${escapeHtml(reportGradeTone(row.grade))}">${escapeHtml(row.grade)}</span>
                </div>
                <span class="report-row-card__trend">${escapeHtml(row.trend)}</span>
              </div>
            `).join("")}
          </div>
        </article>
      ` : ""}

      <article class="glass-card card page-stack report-recent">
        <div class="card-head">
          <div>
            <h3 class="section-title">Recent Downloads</h3>
            <p class="section-copy">Files you exported from this device.</p>
          </div>
          ${reports.recent.length ? `
            <button
              class="button button--secondary"
              type="button"
              data-action="report-clear-recent"
            >
              ${icon("trash")}
              <span>Clear List</span>
            </button>
          ` : ""}
        </div>

        ${reports.recent.length ? `
          <div class="report-recent-list">
            ${reports.recent.map((item) => `
              <div class="report-recent-item">
                <span class="report-recent-item__icon" aria-hidden="true">${icon("file-text")}</span>
                <span class="report-recent-item__copy">
                  <span class="report-recent-item__name">${escapeHtml(item.name)}</span>
                  <span class="report-recent-item__meta">${escapeHtml(formatReportTimestamp(item.createdAt))} &middot; ${escapeHtml(item.createdBy)}</span>
                </span>
                <span class="report-recent-item__tag report-recent-item__tag--pdf">
                  PDF
                </span>
              </div>
            `).join("")}
          </div>
        ` : `
          <div class="center-banner">No reports downloaded from this device yet.</div>
        `}
      </article>
    </section>
  `;
}

function clearRecentReports() {
  state.reports.recent = [];
  try {
    window.localStorage.removeItem(REPORTS_RECENT_KEY);
  } catch (error) {
    // Nothing to clear if storage is unavailable.
  }
  renderPage();
}

function reportGradeTone(grade) {
  const normalized = String(grade || "").toLowerCase();
  if (normalized === "excellent" || normalized === "good") {
    return "good";
  }
  if (normalized === "fair") {
    return "fair";
  }
  if (normalized === "needs care") {
    return "poor";
  }
  return "muted";
}

function formatReportTimestamp(value) {
  const moment = new Date(value);
  if (Number.isNaN(moment.getTime())) {
    return "";
  }
  const hours = moment.getHours() % 12 || 12;
  const minutes = String(moment.getMinutes()).padStart(2, "0");
  const meridiem = moment.getHours() < 12 ? "AM" : "PM";
  return `${REPORT_MONTHS[moment.getMonth()]} ${moment.getDate()}, ${moment.getFullYear()}, ${hours}:${minutes} ${meridiem}`;
}
