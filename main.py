from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import io
import ipaddress
import math
import json
import os
import platform
import queue
import re
import secrets
import smtplib
import socket
import sqlite3
import ssl
import statistics
import subprocess
import sys
import contextlib
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from http import HTTPStatus
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from flask import Flask, Response, g, has_request_context, jsonify, redirect, request as flask_request, send_from_directory
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.exceptions import BadRequest
from werkzeug.serving import run_simple
from werkzeug.utils import secure_filename

import icucrops_reports


# Global paths, limits, and defaults shared by the API server and CLI helpers.
WORKSPACE_DIR = Path(__file__).resolve().parent

# The only file types the static route may hand to a browser. The workspace
# root is the repository, so anything outside this set -- source, databases,
# secrets, configs -- must never be served. Default-deny: add a suffix here
# only when the front-end genuinely needs to load that asset type.
# Source maps are deliberately absent: a .map hands DevTools the original
# commented source for every asset. Nothing in the front end references one
# (no bundler runs here, and no file carries a sourceMappingURL), so serving
# them only widened what a visitor could read.
SERVABLE_STATIC_SUFFIXES = frozenset({
    ".html", ".htm", ".css", ".js", ".mjs",
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".webmanifest", ".woff", ".woff2", ".ttf", ".otf", ".eot",
})
ENV_FILE = WORKSPACE_DIR / ".env"


# Minimal `.env` reader so the project can boot locally without extra packages.
def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ[key] = value


load_env_file(ENV_FILE)


def running_on_managed_host() -> bool:
    """True when the backend runs on a managed cloud host rather than the Pi.

    Managed hosts block outbound SMTP and give the process no durable disk, so
    OTP mail uses a direct HTTPS provider and durable data lives in Postgres.
    No single host is hard-coded: a platform either sets its own marker below,
    or ICUCROPS_MANAGED_HOST is set explicitly.
    """
    for environment_key in ("ICUCROPS_MANAGED_HOST", "VERCEL"):
        if os.getenv(environment_key, "").strip().lower() in {"1", "true", "yes"}:
            return True
    return False


def detect_application_release_id() -> str:
    for environment_key in ("ICUCROPS_RELEASE_ID", "VERCEL_GIT_COMMIT_SHA"):
        configured_release = os.getenv(environment_key, "").strip()
        if configured_release:
            return configured_release

    # The Windows double-click launcher may not inherit Git on PATH. Reading
    # HEAD directly keeps /api/release useful without making Git a runtime
    # dependency. A managed host supplies its own commit variable above.
    git_directory = WORKSPACE_DIR / ".git"
    try:
        head_value = (git_directory / "HEAD").read_text(encoding="utf-8").strip()
        if head_value.startswith("ref:"):
            reference = head_value.split(":", 1)[1].strip()
            reference_value = (git_directory / reference).read_text(encoding="utf-8").strip()
            if reference_value:
                return reference_value
        elif head_value:
            return head_value
    except OSError:
        pass

    try:
        return subprocess.check_output(
            ["git", "-C", str(WORKSPACE_DIR), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "development"


APPLICATION_RELEASE_ID = detect_application_release_id()

def configured_path(environment_key: str, default: Path) -> Path:
    """Path from the environment, falling back to the checked-out location.

    A managed host mounts the application directory read-only and offers only a
    temporary directory for writes, so every path the backend writes to has to
    be movable. On a desktop or the Raspberry Pi nothing is set and the paths
    stay next to the code, exactly as before.
    """
    override = os.getenv(environment_key, "").strip()
    return Path(override).expanduser() if override else default


def configured_int(environment_key: str, default: int) -> int:
    """Integer from the environment, ignoring an unset or unusable value.

    A hosting dashboard makes it easy to leave a variable listed but empty, and
    int("") raises - which would abort the whole application at import time with
    a stack trace that says nothing about the blank field that caused it.
    """
    try:
        return int(os.getenv(environment_key, "").strip())
    except ValueError:
        return default


def configured_float(environment_key: str, default: float) -> float:
    try:
        return float(os.getenv(environment_key, "").strip())
    except ValueError:
        return default


WRITABLE_DIR = configured_path("ICUCROPS_WRITABLE_DIR", WORKSPACE_DIR)
DATA_DIR = configured_path("ICUCROPS_DATA_DIR", WRITABLE_DIR / ".icucrops-data")
DATABASE_PATH = configured_path("ICUCROPS_DATABASE_PATH", WRITABLE_DIR / "crops_db.sqlite")
STORAGE_DIR = configured_path("ICUCROPS_STORAGE_DIR", WRITABLE_DIR / "Storage")
PROFILE_PHOTOS_DIR = STORAGE_DIR / "profile_photos"
DATABASE_BACKEND = os.getenv("ICUCROPS_DATABASE_BACKEND", "postgres").strip().lower() or "postgres"
# The Supabase (PostgreSQL) connection string, used when the backend mode is
# `postgres`. Everything needed to reach the database is in this one value -
# there is no anon key and no REST endpoint, because the browser never talks
# to the database directly.
POSTGRES_URL = os.getenv("ICUCROPS_POSTGRES_URL", "").strip()
PASSWORD_ITERATIONS = 310_000
OTP_ITERATIONS = 120_000
OTP_LENGTH = 6
OTP_MAX_ATTEMPTS = 5
OTP_EXPIRY_MINUTES = 10
ADMIN_LOGIN_MAX_ATTEMPTS = 5
ADMIN_LOGIN_LOCK_MINUTES = 5
# A second, per-account backstop. The address lockout above stops the common
# case, but a spread of many source addresses could still grind one account.
# This caps total guesses per account regardless of where they come from. The
# threshold is deliberately higher than the address one so an ordinary user who
# fat-fingers a password is never locked out by it, while a distributed guesser
# is still bounded to a handful of tries per cooldown window.
ADMIN_LOGIN_ACCOUNT_MAX_ATTEMPTS = 20
ADMIN_LOGIN_ACCOUNT_LOCK_MINUTES = 15
# Cap the request body so a single oversized upload cannot exhaust memory.
# Room for the 5 MB profile photo plus multipart overhead; everything else is
# small JSON. Werkzeug answers 413 before buffering anything larger.
MAX_REQUEST_BODY_BYTES = 8 * 1024 * 1024
# OTP requests are expensive -- a PBKDF2 hash and an email each -- and the reset
# endpoint is public, so bound how often one email address or one caller can ask
# for a code before a short cooldown. Keeps the endpoint from being turned into
# a CPU drain or an email-flood amplifier.
OTP_REQUEST_EMAIL_MAX = 3
OTP_REQUEST_IP_MAX = 15
OTP_REQUEST_WINDOW_MINUTES = 10
DEFAULT_API_FALLBACK_PORT = "8080"
AUTH_SESSION_TTL_SECONDS = max(
    900,
    min(86_400, int(os.getenv("ICUCROPS_AUTH_SESSION_TTL_SECONDS", "28800"))),
)
# DATA_DIR, not WORKSPACE_DIR. These are created on first use, and a managed
# host's application directory is read-only -- so the write raised, and every
# request that needed the token answered 500 instead of the 401 it meant. On the
# Pi, WRITABLE_DIR defaults to WORKSPACE_DIR, so both paths are unchanged there.
AUTH_SESSION_SECRET_PATH = DATA_DIR / "session-secret"
DEVICE_TOKEN_PATH = DATA_DIR / "device-token"
AUTH_SESSION_SECRET_LOCK = threading.Lock()
AUTH_SESSION_SECRET: bytes | None = None
# A database that has not answered in this long is not going to answer within
# any request the browser is still waiting on. Kept below every client timeout
# (10s default, 30s report preview) so the backend reports the failure itself
# rather than being cut off mid-connect.
POSTGRES_CONNECT_TIMEOUT_SECONDS = max(
    3,
    min(20, int(os.getenv("ICUCROPS_POSTGRES_CONNECT_TIMEOUT_SECONDS", "8"))),
)

AUTH_SESSION_USER_CACHE_TTL_SECONDS = 15
AUTH_SESSION_USER_CACHE_LOCK = threading.Lock()
AUTH_SESSION_USER_CACHE: dict[str, tuple[float, dict[str, str], str, str]] = {}
DEVICE_TOKEN_LOCK = threading.Lock()
DEVICE_TOKEN: str | None = None
LOCAL_HTTPS_HEALTH_LOCK = threading.Lock()
LOCAL_HTTPS_HEALTHY = False
LOCAL_HTTPS_HEALTH_EXPIRES_AT = 0.0
REALTIME_VERSIONS_LOCK = threading.Lock()
REALTIME_LOCAL_VERSIONS: dict[str, str] = {}
# The version poll is the most frequent request the API serves -- every open
# dashboard asks several times a second, and each ask ran the fingerprint query
# against the database. Holding the answer for a moment lets concurrent pollers
# share one read instead of each paying for their own. Kept well under the poll
# interval so no change waits noticeably longer to be noticed; local revisions
# are not cached at all, so this process still sees its own writes at once.
REALTIME_DATABASE_VERSION_CACHE_SECONDS = max(
    0.0, float(os.getenv("ICUCROPS_REALTIME_VERSION_CACHE_SECONDS", "0.5"))
)
REALTIME_DATABASE_VERSION_CACHE_LOCK = threading.Lock()
REALTIME_DATABASE_VERSION_CACHE: dict[str, str] = {}
REALTIME_DATABASE_VERSION_CACHE_EXPIRES_AT = 0.0
DEFAULT_ALLOWED_ORIGINS = {
    "https://icucrops.vercel.app",
}
CONFIGURED_ALLOWED_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.getenv("ICUCROPS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
}
ALLOWED_CORS_ORIGINS = DEFAULT_ALLOWED_ORIGINS | CONFIGURED_ALLOWED_ORIGINS
MAX_PROFILE_PHOTO_BYTES = 5 * 1024 * 1024
# One photo over HTTPS, on the account sync's own poll. Short enough that a
# slow or unreachable host cannot hold that pass open, since the name beside
# it has already been applied and only the image is still outstanding.
PROFILE_PHOTO_FETCH_TIMEOUT_SECONDS = 10.0
PROFILE_PHOTO_OUTPUT_SIZE = 512
MAX_PROFILE_PHOTO_PIXELS = 40_000_000
ALLOWED_PROFILE_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
PROFILE_NAME_MIN_LENGTH = 2
PROFILE_NAME_MAX_LENGTH = 30
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 64
PASSWORD_POLICY_MESSAGE = (
    "Password must be 8–64 characters and include uppercase, lowercase, number, and special character."
)
VALID_CULTIVATION_ROWS = ("row1", "row2", "row3", "row4")
VALID_CULTIVATION_PARAMETER_MODES = {"recommended", "custom"}
VALID_NOTIFICATION_SCOPES = {"all", "admin", "user"}
PLACEHOLDER_SMTP_VALUES = {
    "yourrealgmail@gmail.com",
    "yourgmail@gmail.com",
    "abcdefghijklmnop",
    "your-google-app-password",
}
VALID_SENSOR_POWER_STATES = {"on", "off"}
VALID_ACTUATOR_MODES = {"automatic", "on", "off"}
# Where an actuator rests when no usable mode is stored for it. Misting is a
# water line, so it rests Off; the fan and the lamp rest on their rules.
#
# Misting takes all three modes since 2026-10-07 (asked for from the farm):
#   * Automatic -- the mist runs alongside water irrigation and closes with it
#     (build_relay_desired_state), and only on a water run that started while
#     every planted row was below its minimum moisture (misting_rows_all_low):
#     one mist line covers the whole house, so a row that is already wet
#     enough keeps it shut.
#   * On -- a timed run from the card, as before: a duration is required and
#     capped at MISTING_MAX_DURATION_SECONDS, and it ends in Off.
#   * Off -- off, water irrigation or not.
# From 2026-10-05 until then it had On and Off only and followed the water
# line whatever the mode said, so there was no way to water without mist.
ACTUATOR_RESTING_MODES = {"misting": "off"}
# Every greenhouse actuator the website can set a mode for. All three reach a
# relay. Keeping them in one list means the overview payload and the control
# gate cannot drift apart.
ENVIRONMENT_ACTUATOR_KEYS = ("fan", "light", "misting")
# The subset that actually reaches a relay -- now every one of them. A key with
# no relay in the bitmap would be an actuator index nothing owns.
#
# A key can hold more than one relay. "light" holds two: the grow light on
# soil-node-4/relay3/in8 and its cooling fan on in5, which share the key so the
# lamp can never run without airflow over it. "fan" holds the two extractor
# groups on in7 and in6. Misting holds soil-node-1/relay2/in6.
#
# The channel numbers here were transposed before -- this read that the light
# held in6 beside fan groups on in8 and in7, which is the wrong way round.
# RELAY_HARDWARE_LAYOUT is the authority; this comment is a summary of it.
RELAY_BACKED_ACTUATOR_KEYS = ("fan", "light", "misting")
# The subset that an automatic rule can decide for itself. Having a relay and
# having a rule are different things: misting reaches a relay but no sensor
# rule computes an On for it -- its Automatic follows the water line instead,
# decided in build_relay_desired_state. automatic_actuator_guidance emits an
# entry for these keys only, and reading it for any other key raises KeyError.
AUTOMATIC_ACTUATOR_KEYS = ("fan", "light")
VALID_IRRIGATION_MODES = {"automatic", "schedule", "manual"}
VALID_IRRIGATION_FREQUENCIES = {"daily", "every-2-days", "every-3-days", "weekly"}
REMOTE_HARDWARE_COMMAND_PREFIX = "hardware_command:"
REMOTE_HARDWARE_COMMAND_APPLIED_PREFIX = "hardware_command_applied:"
REMOTE_HARDWARE_COMMAND_TYPES = {
    "irrigation",
    "sensorControl",
    "notificationDelete",
    "notificationDeleteAll",
    # A deletion mark for an account or a cultivation. Carried here so a
    # removal made on the hosted dashboard still reaches the farm when the
    # Postgres path the edge sync normally uses is blocked by the network.
    "syncTombstone",
    # An account created or edited on the hosted dashboard. Carried here so
    # registration still reaches the farm when the Pi was off or offline while
    # it happened, and when the Postgres path the edge sync normally uses is
    # blocked by the network.
    "syncAccount",
    # A cultivation started or edited on the hosted dashboard. Deletions had an
    # HTTPS door and additions did not, so a crop removed online vanished from
    # the kiosk within seconds while one planted online never appeared there.
    "syncCultivation",
    # History entries recorded on the hosted dashboard (accounts, plantings,
    # harvests made there), stored on the Pi with their own created_at.
    "syncNotifications",
}
# Relay commands that are safe to apply twice and arrive in bulk. They leave no
# applied marker: the History deletion feed alone wrote 7,321 of them in one
# afternoon, each a row the realtime fingerprint and the sync then had to read.
UNMARKED_REMOTE_COMMAND_PREFIXES = ("notification_sync_", "notifications_down_")
IRRIGATION_CHANNEL_SENSOR_METRICS = {
    "water": ("moisture", "moisture"),
    "fertilizer": ("rs485", "ec"),
    "limeSolution": ("rs485", "ph"),
}
IRRIGATION_SENSOR_MAX_AGE_MINUTES = 15
# The RS485 pH probe is noisy on a scale of seconds, not of frames: on
# 2026-09-25 row 2 read 7.0, 3.7 and 6.8 inside ninety seconds with nothing
# running, and row 1 swung 4.3 to 5.8 every two to four seconds. Soil pH cannot
# move like that, but the lime line was judged on the newest single reading, so
# one dip past critical started Automatic. Automatic lime now starts only when
# the time-weighted median of this window is critical as well. Seconds.
IRRIGATION_PH_SETTLE_SECONDS = max(
    10, int(os.getenv("ICUCROPS_IRRIGATION_PH_SETTLE_SECONDS", "120") or 120)
)
# After a lime run on a row ends, however it ended, Automatic does not start
# lime on that row again for this long. The solution needs time to spread
# through the soil; right after a dose the probe reads the local transient, and
# re-dosing on it is the up-down-up loop the farm saw. Minutes; 0 turns it off.
IRRIGATION_LIME_REST_MINUTES = max(
    0, int(os.getenv("ICUCROPS_IRRIGATION_LIME_REST_MINUTES", "10") or 0)
)
# The shortest run the system will honour, and the floor every saved duration
# is clamped to.
#
# Durations are seconds rather than minutes because the supply lines here
# deliver far faster than the original design assumed -- a row is watered in
# well under a minute, so a one-minute floor made the shortest possible run
# longer than most runs should be.
#
# One second, which is to say: whatever was entered is what runs. A ten-second
# floor was tried and withdrawn. It was defensible on transport grounds -- a
# command reaches the relay over MQTT and the coil takes time to pull in, so a
# very short run is a poor approximation of itself -- but the person setting
# the duration is standing at the row and can see the water. Silently running
# longer than they asked is the worse failure, and rounding their number up
# without their say is not the system's call to make. Short runs are inexact
# by nature; that is the operator's trade to make, not ours.
IRRIGATION_MIN_DURATION_SECONDS = 1
# The misting line is the one actuator with no sensor rule -- nothing computes
# an On for it from a reading, so an On stayed on until somebody came back and
# switched it off. A mist left running raises the humidity the
# fan is working to remove, and the person who started it is usually elsewhere
# by then.
#
# It gets a duration instead, the way irrigation has: On for N seconds, and the
# backend closes it. The bounds are wide because misting is used for very
# different things -- a few seconds to settle dust, several minutes to bring a
# dry house up -- but not unbounded, so a typo cannot leave it on all night.
#
# Since 2026-10-01 the farm's rule is stricter: On needs a duration typed in
# (no number, no mist -- an empty box used to mean "on until Off"), and no
# run is longer than 50 seconds.
MISTING_MIN_DURATION_SECONDS = 1
MISTING_MAX_DURATION_SECONDS = max(
    MISTING_MIN_DURATION_SECONDS,
    int(os.getenv("ICUCROPS_MISTING_MAX_DURATION_SECONDS", "50")),
)
MISTING_DEFAULT_DURATION_SECONDS = 30
# Where the deadline lives. system_state rather than a new column: it is one
# value for one actuator, it is derived state rather than a setting, and the
# sync already carries this table.
MISTING_DEADLINE_STATE_KEY = "actuator.misting_off_at"
# The irrigation line the mist runs alongside while its mode is Automatic.
# See build_relay_desired_state.
MISTING_FOLLOWS_CHANNEL_KEY = "water"
# Irrigation schedule times are farm-local times. A fixed UTC+8 offset keeps
# Raspberry Pi and managed-host calculations identical and matches Philippine
# Standard Time, which has no daylight-saving changes.
IRRIGATION_LOCAL_TIMEZONE = timezone(timedelta(hours=8))
VALID_SENSOR_ALERT_MODES = {"website only", "disabled"}
DEFAULT_SENSOR_ALERT_MODE = "Website Only"
DASHBOARD_SERIES_METRICS = (
    {"key": "moisture", "sensor_key": "moisture", "metric_key": "value"},
    {"key": "ph", "sensor_key": "ph", "metric_key": "value"},
    {"key": "ec", "sensor_key": "ec", "metric_key": "value"},
    {"key": "temp", "sensor_key": "dht22", "metric_key": "temp"},
    {"key": "humidity", "sensor_key": "dht22", "metric_key": "humidity"},
)
DEFAULT_SENSOR_DEFINITIONS = (
    {
        "definition_key": "dashboard-moisture",
        "display_name": "Dashboard Soil Moisture",
        "category": "dashboard",
        "default_device_name": "Soil Capacitive Sensor",
        "default_row_key": "",
        "default_power_state": "on",
        "default_actuator_mode": "",
        "metric_keys": ["value"],
        "metadata": {"scope": "dashboard", "unit": "%"},
    },
    {
        "definition_key": "dashboard-ph",
        "display_name": "Dashboard pH Level",
        "category": "dashboard",
        "default_device_name": "Soil pH RS485 Multi Sensor",
        "default_row_key": "",
        "default_power_state": "on",
        "default_actuator_mode": "",
        "metric_keys": ["value"],
        "metadata": {"scope": "dashboard", "unit": "pH"},
    },
    {
        "definition_key": "dashboard-ec",
        "display_name": "Dashboard Soil Nutrients",
        "category": "dashboard",
        "default_device_name": "Soil Nutrients RS485 Multi Sensor",
        "default_row_key": "",
        "default_power_state": "on",
        "default_actuator_mode": "",
        "metric_keys": ["value"],
        "metadata": {"scope": "dashboard", "unit": "mS/cm"},
    },
    {
        "definition_key": "shared-dht22",
        "display_name": "Shared DHT22",
        "category": "shared",
        "default_device_name": "DHT22",
        "default_row_key": "",
        "default_power_state": "on",
        "default_actuator_mode": "",
        "metric_keys": ["temp", "humidity"],
        "metadata": {"scope": "shared", "unit": "mixed"},
    },
    {
        "definition_key": "light-level",
        "display_name": "Light Level",
        "category": "shared",
        # An HW-072 LDR module on ESP32 #5, not the BH1750 this used to be.
        # The part reports a threshold crossing set by a trimpot rather than a
        # light level, so the metric is a boolean and there is no unit: "dark"
        # is true or false and nothing in between.
        "default_device_name": "HW-072",
        "default_row_key": "",
        "default_power_state": "on",
        "default_actuator_mode": "",
        "metric_keys": ["dark"],
        "metadata": {"scope": "shared", "unit": "boolean"},
    },
    {
        "definition_key": "fan-actuator",
        "display_name": "Exhaust Fan Actuator",
        "category": "actuator",
        "default_device_name": "Exhaust Fan",
        "default_row_key": "",
        "default_power_state": "on",
        "default_actuator_mode": "automatic",
        "metric_keys": [],
        "metadata": {"scope": "actuator"},
    },
    {
        "definition_key": "light-actuator",
        "display_name": "Light Actuator",
        "category": "actuator",
        "default_device_name": "Grow Light",
        "default_row_key": "",
        "default_power_state": "on",
        "default_actuator_mode": "automatic",
        "metric_keys": [],
        "metadata": {"scope": "actuator"},
    },
    {
        "definition_key": "misting-actuator",
        "display_name": "Misting Actuator",
        "category": "actuator",
        "default_device_name": "Misting Line",
        "default_row_key": "",
        "default_power_state": "on",
        # Off is the resting state for a water line -- see
        # ACTUATOR_RESTING_MODES. Automatic is chosen on the card.
        "default_actuator_mode": "off",
        "metric_keys": [],
        "metadata": {"scope": "actuator"},
    },
    {
        "definition_key": "row-moisture",
        "display_name": "Row Soil Moisture",
        "category": "row",
        "default_device_name": "Soil Capacitive Sensor",
        "default_row_key": "",
        "default_power_state": "on",
        "default_actuator_mode": "",
        "metric_keys": ["moisture"],
        "metadata": {"scope": "row", "deviceGroup": "moisture", "unit": "%"},
    },
    {
        "definition_key": "row-rs485",
        "display_name": "Row RS485 Multi Sensor",
        "category": "row-group",
        "default_device_name": "RS485 Multi Sensor",
        "default_row_key": "",
        "default_power_state": "on",
        "default_actuator_mode": "",
        "metric_keys": ["ec", "ph"],
        "metadata": {"scope": "row", "deviceGroup": "rs485"},
    },
)
DEFAULT_SENSOR_BACKENDS = (
    {
        "backend_key": "http-api",
        "display_name": "HTTP Sensor Ingest API",
        "ingest_path": "/api/sensors/readings",
        "protocol": "http",
        "source_type": "api",
        "hardware_identifier_prefix": "",
        "is_active": True,
        "metadata": {"description": "POST sensor readings directly to the Flask backend."},
    },
    {
        "backend_key": "mqtt-bridge",
        "display_name": "ICuCrops MQTT Bridge",
        "ingest_path": "/api/sensors/readings",
        "protocol": "mqtt",
        "source_type": "mqtt",
        "hardware_identifier_prefix": "mqtt-",
        "is_active": True,
        "metadata": {"description": "Live ESP32 readings forwarded by the Raspberry Pi MQTT bridge."},
    },
)
DEFAULT_SENSOR_REGISTRY = (
    {
        "sensor_key": "moisture",
        "definition_key": "dashboard-moisture",
        "backend_key": "mqtt-bridge",
        "display_name": "Soil Moisture",
        "device_name": "Soil Capacitive Sensor",
        "row_key": "",
        "category": "dashboard",
        "power_state": "on",
        "actuator_mode": "",
        "alert_mode": DEFAULT_SENSOR_ALERT_MODE,
        "hardware_identifier": "",
        "metric_keys": ["value"],
        "metadata": {"scope": "dashboard", "unit": "%"},
    },
    {
        "sensor_key": "ph",
        "definition_key": "dashboard-ph",
        "backend_key": "mqtt-bridge",
        "display_name": "pH Level",
        "device_name": "Soil pH RS485 Multi Sensor",
        "row_key": "",
        "category": "dashboard",
        "power_state": "on",
        "actuator_mode": "",
        "alert_mode": DEFAULT_SENSOR_ALERT_MODE,
        "hardware_identifier": "",
        "metric_keys": ["value"],
        "metadata": {"scope": "dashboard", "unit": "pH"},
    },
    {
        "sensor_key": "ec",
        "definition_key": "dashboard-ec",
        "backend_key": "mqtt-bridge",
        "display_name": "Soil Nutrients",
        "device_name": "Soil Nutrients RS485 Multi Sensor",
        "row_key": "",
        "category": "dashboard",
        "power_state": "on",
        "actuator_mode": "",
        "alert_mode": DEFAULT_SENSOR_ALERT_MODE,
        "hardware_identifier": "",
        "metric_keys": ["value"],
        "metadata": {"scope": "dashboard", "unit": "mS/cm"},
    },
    {
        "sensor_key": "dht22",
        "definition_key": "shared-dht22",
        "backend_key": "mqtt-bridge",
        "display_name": "DHT22",
        "device_name": "DHT22",
        "row_key": "",
        "category": "shared",
        "power_state": "on",
        "actuator_mode": "",
        "alert_mode": DEFAULT_SENSOR_ALERT_MODE,
        "hardware_identifier": "",
        "metric_keys": ["temp", "humidity"],
        "metadata": {"scope": "shared", "unit": "mixed"},
    },
    {
        "sensor_key": "light-level",
        "definition_key": "light-level",
        "backend_key": "mqtt-bridge",
        "display_name": "Light Level",
        # HW-072 LDR module on ESP32 #5. See the light-level definition above
        # for why the metric is a boolean rather than lux.
        "device_name": "HW-072",
        "row_key": "",
        "category": "shared",
        "power_state": "on",
        "actuator_mode": "",
        "alert_mode": DEFAULT_SENSOR_ALERT_MODE,
        "hardware_identifier": "",
        "metric_keys": ["dark"],
        "metadata": {"scope": "shared", "unit": "boolean"},
    },
    {
        "sensor_key": "fan",
        "definition_key": "fan-actuator",
        "backend_key": "mqtt-bridge",
        "display_name": "Exhaust Fan",
        "device_name": "Exhaust Fan",
        "row_key": "",
        "category": "actuator",
        "power_state": "on",
        "actuator_mode": "automatic",
        "alert_mode": "",
        "hardware_identifier": "",
        "metric_keys": [],
        "metadata": {"scope": "actuator"},
    },
    {
        "sensor_key": "light",
        "definition_key": "light-actuator",
        "backend_key": "mqtt-bridge",
        "display_name": "Light",
        "device_name": "Grow Light",
        "row_key": "",
        "category": "actuator",
        "power_state": "on",
        "actuator_mode": "automatic",
        "alert_mode": "",
        "hardware_identifier": "",
        "metric_keys": [],
        "metadata": {"scope": "actuator"},
    },
    {
        "sensor_key": "misting",
        "definition_key": "misting-actuator",
        "backend_key": "mqtt-bridge",
        "display_name": "Misting",
        "device_name": "Misting Line",
        "row_key": "",
        "category": "actuator",
        "power_state": "on",
        "actuator_mode": "off",
        "alert_mode": "",
        "hardware_identifier": "",
        "metric_keys": [],
        "metadata": {"scope": "actuator"},
    },
    *(
        {
            "sensor_key": f"{row_key}-moisture",
            "definition_key": "row-moisture",
            "backend_key": "mqtt-bridge",
            "display_name": f"Row {row_key.removeprefix('row')} Soil Moisture",
            "device_name": "Soil Capacitive Sensor",
            "row_key": row_key,
            "category": "row",
            "power_state": "on",
            "actuator_mode": "",
            "alert_mode": DEFAULT_SENSOR_ALERT_MODE,
            "hardware_identifier": "",
            "metric_keys": ["moisture"],
            "metadata": {"scope": "row", "deviceGroup": "moisture"},
        }
        for row_key in VALID_CULTIVATION_ROWS
    ),
    *(
        {
            "sensor_key": f"{row_key}-rs485",
            "definition_key": "row-rs485",
            "backend_key": "mqtt-bridge",
            "display_name": f"Row {row_key.removeprefix('row')} RS485 Multi Sensor",
            "device_name": "RS485 Multi Sensor",
            "row_key": row_key,
            "category": "row-group",
            "power_state": "on",
            "actuator_mode": "",
            "alert_mode": DEFAULT_SENSOR_ALERT_MODE,
            "hardware_identifier": "",
            "metric_keys": ["ec", "ph"],
            "metadata": {"scope": "row", "deviceGroup": "rs485"},
        }
        for row_key in VALID_CULTIVATION_ROWS
    ),
)
DEFAULT_IRRIGATION_CHANNELS = (
    {
        "channel_key": "water",
        "label": "Water",
        "automatic_duration_seconds": 900,
        "manual_duration_seconds": 900,
        "schedule_start_time": "06:00",
        "schedule_duration_seconds": 1200,
        "schedule_frequency": "daily",
    },
    {
        "channel_key": "fertilizer",
        "label": "Fertilizer",
        "automatic_duration_seconds": 600,
        "manual_duration_seconds": 600,
        "schedule_start_time": "06:15",
        "schedule_duration_seconds": 900,
        "schedule_frequency": "every-2-days",
    },
    {
        "channel_key": "limeSolution",
        "label": "Lime Solution",
        "automatic_duration_seconds": 480,
        "manual_duration_seconds": 480,
        "schedule_start_time": "06:30",
        "schedule_duration_seconds": 600,
        "schedule_frequency": "weekly",
    },
)
# Both actuators answer to a live reading judged against the crop parameters,
# and each to the one it can actually move:
#
#   fan     humidity. Air that is too wet is what the extractor can do
#           something about, and it is what rots a leaf crop.
#   light   temperature. A cold house turns the lamp on, against the crop's own
#           temperature floor: its waste heat is what the greenhouse actually
#           has. A heater was specified for this relay once but never
#           installed, so the lamp holds it again.
#
# The fallbacks only apply while no cultivation is active. Once one is, its own
# parameters are the thresholds - which is the point of asking for them.
FAN_AUTO_FALLBACK_ON_HUMIDITY = float(os.getenv("ICUCROPS_FAN_AUTO_ON_HUMIDITY", "80"))
LIGHT_AUTO_FALLBACK_ON_C = float(os.getenv("ICUCROPS_LIGHT_AUTO_ON_C", "18"))
# ICUCROPS_LIGHT_AUTO_ON_LUX and ICUCROPS_LIGHT_DAYLIGHT_LUX were removed here
# when the BH1750 gave way to an HW-072 LDR module on ESP32 #5. Setting either
# env var now does nothing, and the constants are gone rather than left unused
# so that nobody tunes a number the code no longer reads.
#
# What they were, because it is worth keeping if a lux part ever returns. They
# were measured in this greenhouse rather than taken from a table: published
# daylight figures (1000-2000 lx overcast, tens of thousands in direct sun)
# describe an unobstructed sensor outdoors, while the BH1750 sat under dusty
# greenhouse plastic and read a couple of hundred lux with the house plainly
# bright. The pair went 2000 -> 60/80 -> 10/15 across three revisions; at 2000
# every working daylight hour counted as "dark" and the lamp ran straight
# through it. The final 5 lx gap between them was the anti-flap margin.
#
# None of that transfers to the HW-072. It reports one bit -- dark or not --
# against a threshold set by a trimpot on the sensor board, which the server
# cannot read or change. Turning that screw is now the only way to adjust what
# counts as dark, and the firmware's 2 s debounce is what the 5 lx gap used to
# do. The two thresholds also collapsed into one: dark and daylight are exact
# opposites now, with no band in between where the lamp holds its state.
# The light sensor is on ESP32 #5, alongside the DHT22. The key is unchanged
# from when a BH1750 on #3 published it: the backend keys readings by sensor
# rather than by node, which is what let the part and the board both change
# without the graphs or the automation losing their history.
#
# Its reading has to be fresh for the same reason the DHT22's does: a silent
# sensor is not evidence the greenhouse is dark.
LIGHT_SENSOR_KEY = "light-level"
# The dark half of the lamp rule has a limit per dark spell. When the HW-072
# reads dark the lamp runs, but for at most this many hours of lamp; once the
# sensor reads daylight again (for GROW_LIGHT_RESET_MINUTES straight) the count
# starts over. So the lamp covers the first hours after sunset and a cloudy
# spell during the day, and never burns through the whole night. 4 h is the
# extra lighting after 6 pm that was best for mustard in a tropical greenhouse
# and, on a 12-hour day, brings the crops to the 16 h that suited lettuce (the
# RRL in paper works/). The cold half is not limited: the lamp is the only
# heater.
GROW_LIGHT_DARK_LIMIT_HOURS = float(os.getenv("ICUCROPS_GROW_LIGHT_DARK_LIMIT_HOURS", "4"))
# Daylight has to hold this long before the limit resets. Headlights, a
# lightning flash or a torch on the sensor would otherwise hand the lamp a
# fresh 4 hours in the middle of the night.
GROW_LIGHT_RESET_MINUTES = float(os.getenv("ICUCROPS_GROW_LIGHT_RESET_MINUTES", "10"))
# A gap longer than this between control cycles is time nothing was running
# (the Pi is switched off at the wall) and is credited to nothing.
GROW_LIGHT_MAX_TICK_SECONDS = 120.0
# A file, like greenhouse-response.json: a SQLite write wakes the sync daemon,
# and this changes every cycle. Rewritten at most once a minute (SD wear), and
# kept so a power cut in the night does not hand the lamp another 4 hours.
GROW_LIGHT_LIMIT_FILE = DATA_DIR / "grow-light-limit.json"
GROW_LIGHT_LIMIT_SAVE_SECONDS = 60.0
# Nothing in the greenhouse can cool it: the fan moves humidity, the lamp only
# adds heat. Above this, the only remedy is a person opening it, so the
# dashboards say so instead of pretending a relay will handle it.
GREENHOUSE_VENT_FALLBACK_C = float(os.getenv("ICUCROPS_GREENHOUSE_VENT_C", "32"))

# How far past the strictest crop's bound the shared air may drift before the
# dashboards count it as past help. Since 2026-09-24 this no longer delays the
# relays -- see AUTOMATIC_TEMP_LEAD_C below -- it is the first step towards the
# "open the greenhouse" alert, which sits a further alert margin beyond it.
#
# What it used to be:
#
# One DHT22 serves four rows, so every automatic decision is made on one number
# for the whole house. The rule takes the lowest ceiling and the highest floor
# of the four, which is the only choice that cannot under-serve a crop -- but
# it also means the single most sensitive row decides for all of them. A row
# whose ceiling is 26C against three at 30C had the fan running from 26.1C, for
# air that three quarters of the greenhouse was comfortable in.
#
# These bands are what "medyo ok lang kahit may lampas, wag lang sobra-sobra"
# is in numbers. They are deliberately small: the strictest crop is still the
# one being protected, it is simply allowed to sit a little outside its band
# before the whole house is run for it. Widen them and that crop stops being
# protected at all, which is why they are not a per-crop setting.
GREENHOUSE_SHARED_TEMP_TOLERANCE_C = max(
    0.0, float(os.getenv("ICUCROPS_GREENHOUSE_TEMP_TOLERANCE_C", "2"))
)
GREENHOUSE_SHARED_HUMIDITY_TOLERANCE = max(
    0.0, float(os.getenv("ICUCROPS_GREENHOUSE_HUMIDITY_TOLERANCE", "5"))
)

# How far past the fan's own trigger the house has to go before anyone is told
# to open it by hand.
#
# The alert used to fire at exactly the point the fan started, so every warm
# afternoon produced a notification asking a person to come and open a
# greenhouse the fan was already dealing with -- and an alert that arrives when
# nothing needs doing is one people learn to close without reading. By the time
# the house is genuinely beyond help, that is the habit it has to beat.
#
# These put real distance between "the fan is working on it" and "the fan is
# not winning". The fan gets the first band to itself; only past the second is
# a person told, and by then the reading has been outside the crop's range for
# that entire margin with the fan running the whole time.
GREENHOUSE_ALERT_TEMP_MARGIN_C = max(
    0.0, float(os.getenv("ICUCROPS_GREENHOUSE_ALERT_TEMP_MARGIN_C", "3"))
)
GREENHOUSE_ALERT_HUMIDITY_MARGIN = max(
    0.0, float(os.getenv("ICUCROPS_GREENHOUSE_ALERT_HUMIDITY_MARGIN", "8"))
)

# Where the fan and the lamp answer on Automatic: a little *inside* the crops'
# range, so the air is turned round before the cards go amber, and held until
# it is a further deadband inside, so the relay does not chatter on the DHT22's
# own noise at one exact number.
#
# These replaced the tolerance-plus-alert-margin trigger. That put the fan's
# start at ceiling + 5 C -- past the card's critical line at ceiling + 4 C -- so
# on Automatic the house was already red before anything moved, which is what
# the farm saw ("may naging critical high at warning high pa rin"). The lamp on
# a bright day waited for floor - 5 C the same way.
#
# The fan still cannot cool below the air it draws in, so a house hotter than
# outside at noon can still go past its ceiling; the cards and the alert say so.
AUTOMATIC_TEMP_LEAD_C = max(0.0, float(os.getenv("ICUCROPS_AUTOMATIC_TEMP_LEAD_C", "1")))
AUTOMATIC_TEMP_DEADBAND_C = max(0.0, float(os.getenv("ICUCROPS_AUTOMATIC_TEMP_DEADBAND_C", "1.5")))
AUTOMATIC_HUMIDITY_LEAD = max(0.0, float(os.getenv("ICUCROPS_AUTOMATIC_HUMIDITY_LEAD", "3")))
AUTOMATIC_HUMIDITY_DEADBAND = max(0.0, float(os.getenv("ICUCROPS_AUTOMATIC_HUMIDITY_DEADBAND", "5")))

# Which automatic reasons the relays are running for right now, written only by
# the environment control cycle (the one place the relays are decided) and read
# back by it and by the dashboard payload. It is what lets a reason hold through
# its deadband: without it every cycle would decide from the reading alone and a
# fan at the start point would switch on and off with each poll.
AUTOMATIC_ACTUATOR_RUNNING: dict[str, bool] = {}

# The DHT22's own trend, over this window. It shapes how fast the greenhouse
# response moves the cards (a reading already coming back on its own needs less
# push). It no longer moves the relays' start points: the farm asked for the
# fan to wait for critical, and a trend starting it early would run it through
# warning.
AUTOMATIC_TREND_WINDOW_S = max(60.0, float(os.getenv("ICUCROPS_AUTOMATIC_TREND_WINDOW_S", "300")))
# Too short a span says more about the DHT22's noise than about the air.
AUTOMATIC_TREND_MIN_SPAN_S = 60.0
# (monotonic seconds, temperature, humidity), recorded only by the environment
# control cycle from a fresh DHT22 reading.
AUTOMATIC_CLIMATE_SAMPLES: list[tuple[float, float | None, float | None]] = []

# The greenhouse response: a signed offset on top of the DHT22 that the cards
# show and the automatic rules act on (see greenhouse_response_step). The
# control cycle is the only writer; the database keeps the DHT22 as measured,
# and the Shared DHT22 sensor card shows it.
#
# Rates are per minute. On Automatic a critical reading is brought back inside
# every row's range, faster the further out it is and faster again past the
# critical margin, then held there; warning starts nothing. A manual-On fan
# keeps bringing both down to its limits. With nothing on Automatic and no fan
# running, the offset wears off slowly towards the sensor rather than jumping.
GREENHOUSE_RESPONSE_RATES = {
    "temp": {"outside": 0.3, "gain": 0.1, "criticalGain": 0.2, "inside": 0.3, "recoverMin": 0.05},
    "humidity": {"outside": 1.0, "gain": 0.15, "criticalGain": 0.25, "inside": 1.0, "recoverMin": 0.2},
}
# The card's own critical margins, so "stronger when critical" means the same
# point the card turns red.
GREENHOUSE_RESPONSE_CRITICAL_MARGIN = {"temp": 4.0, "humidity": 15.0}
# On Automatic a card sitting in the warning band is eased back inside every
# row's range at this rate per minute, and the fan is not started for it. The
# farm asked for warnings to go away, but not quickly ("dapat ay mawawala yan
# pero hindi mabilis"), and for one or two warnings to leave the fan off: a
# degree takes ten minutes, ten points of humidity twenty.
GREENHOUSE_RESPONSE_WARNING_EASE = {"temp": 0.1, "humidity": 0.5}
# How far inside the range the response settles when it brings a card back:
# the same deadband the fan holds to, so the fan stops as the card arrives.
GREENHOUSE_RESPONSE_INSET = {"temp": AUTOMATIC_TEMP_DEADBAND_C, "humidity": AUTOMATIC_HUMIDITY_DEADBAND}
# And above the floor, where the lamp's cold rule lets go (its lead plus its
# deadband), so the lamp stops as the card arrives.
GREENHOUSE_RESPONSE_INSET_UP = {
    "temp": AUTOMATIC_TEMP_LEAD_C + AUTOMATIC_TEMP_DEADBAND_C,
    "humidity": AUTOMATIC_HUMIDITY_DEADBAND,
}
# A fan on a manual On stops bringing humidity down this far above the crops'
# floor. At the floor itself the safety limit (ACTUATOR_SAFETY_RULES) would cut
# the fan the farm asked to keep running.
GREENHOUSE_RESPONSE_FAN_HUMIDITY_MARGIN = 1.0
# How long a stopped actuator's effect takes to wear off (time constant).
GREENHOUSE_RESPONSE_RECOVER_MINUTES = max(
    1.0, float(os.getenv("ICUCROPS_GREENHOUSE_RESPONSE_RECOVER_MINUTES", "30"))
)
# A reading already falling (or rising, for the lamp) on its own needs less
# push: at this trend per minute the push is down to its floor share.
GREENHOUSE_RESPONSE_TREND_SCALE = {"temp": 0.5, "humidity": 2.0}
GREENHOUSE_RESPONSE_TREND_FLOOR = 0.3
# Longer than this since the control cycle last stepped the model, and the
# dashboards show the DHT22 as measured rather than a stale effect.
GREENHOUSE_RESPONSE_STALE_SECONDS = 60.0
# Set to 0 to turn the whole response off and run on the DHT22 alone.
GREENHOUSE_RESPONSE_ENABLED = os.getenv("ICUCROPS_GREENHOUSE_RESPONSE", "1").strip().lower() not in {
    "0", "false", "no", "off"
}
GREENHOUSE_RESPONSE_LOCK = threading.Lock()
# {"fan": {"temp": e, "humidity": e}, "light": {"temp": e}, "at": monotonic}
GREENHOUSE_RESPONSE_STATE: dict[str, object] = {}

# Physical relay wiring. Irrigation output labels follow the farm convention:
# W = water, F = fertilizer, LS = lime solution, followed by the row number.
RELAY_HARDWARE_LAYOUT = (
    {"node_id": "soil-node-1", "module_id": "relay1", "input": 1, "label": "LS1", "channel_key": "limeSolution", "row_key": "row1"},
    {"node_id": "soil-node-1", "module_id": "relay1", "input": 2, "label": "LS2", "channel_key": "limeSolution", "row_key": "row2"},
    {"node_id": "soil-node-1", "module_id": "relay1", "input": 3, "label": "LS3", "channel_key": "limeSolution", "row_key": "row3"},
    {"node_id": "soil-node-1", "module_id": "relay1", "input": 4, "label": "LS4", "channel_key": "limeSolution", "row_key": "row4"},
    {"node_id": "soil-node-1", "module_id": "relay1", "input": 5, "label": "W1", "channel_key": "water", "row_key": "row1"},
    # Row 2 and row 4's water lines were transposed here until the pumps were
    # checked in the greenhouse: pressing water on row 4 ran row 2's line and
    # the reverse. IN6 feeds row 4 and IN8 feeds row 2. Only the row each
    # channel waters changed -- the entries keep their order, because bit N of
    # soil-node-2's bitmap is entry N of its RELAY_PINS, so the board needs no
    # reflash for the fix to take effect.
    {"node_id": "soil-node-2", "module_id": "relay1", "input": 6, "label": "W4", "channel_key": "water", "row_key": "row4"},
    {"node_id": "soil-node-2", "module_id": "relay1", "input": 7, "label": "W3", "channel_key": "water", "row_key": "row3"},
    {"node_id": "soil-node-2", "module_id": "relay1", "input": 8, "label": "W2", "channel_key": "water", "row_key": "row2"},
    {"node_id": "soil-node-2", "module_id": "relay2", "input": 1, "label": "F4", "channel_key": "fertilizer", "row_key": "row4"},
    {"node_id": "soil-node-2", "module_id": "relay2", "input": 2, "label": "F3", "channel_key": "fertilizer", "row_key": "row3"},
    # F1 and F2 moved off ESP32 #3, which gave up its relays because it reboots
    # about every 1.4 s and could not hold an output steady. Only the node
    # driving each one changed; the fertilizer wiring downstream did not move.
    #
    # The two channel numbers were transposed here until the boards were checked
    # against the physical modules: F1 read IN5 and F2 read IN3, when the wiring
    # is F1 on IN3 and F2 on IN5. Pressing fertilizer row 1 switched the misting
    # line instead, because IN5 sits next to the mist output on that module.
    # Each board's NodeConfig.h carries the same correction.
    {"node_id": "soil-node-2", "module_id": "relay2", "input": 5, "label": "F2", "channel_key": "fertilizer", "row_key": "row2"},
    {"node_id": "soil-node-1", "module_id": "relay2", "input": 3, "label": "F1", "channel_key": "fertilizer", "row_key": "row1"},
    # Seven extractor fans on two relay channels, not seven.
    #
    # They were seven separate entries here, but every one of them carried the
    # same actuator_key, so the fan actuator has only ever switched all of them
    # together -- there was never a control that could run Fan 3 without Fan 5.
    # Seven channels were spending pins on a distinction nothing expressed.
    #
    # The fans are ganged at the contactor into two groups and each group is one
    # relay channel -- in7 and in6, with the grow light beside them on in8. That
    # is what freed the pins F1 and F2 needed. The dashboard shows two rows where
    # it showed seven; pressing the fan actuator still turns on all seven fans.
    #
    # Both groups are on ESP32 #4 rather than split across two boards, so every
    # fan is on one MQTT bitmap: they cannot end up half-on because one board
    # lost its connection while the other kept it.
    {"node_id": "soil-node-4", "module_id": "relay3", "input": 8, "label": "Grow Light", "channel_key": "", "row_key": "", "actuator_key": "light"},
    # The grow light's own cooling fan, on actuator_key "light" rather than
    # "fan". It is not one of the seven extractor fans and must never be
    # switched with them: it exists to keep the lamp from cooking itself, so it
    # has to run exactly when the lamp runs and stop when the lamp stops.
    #
    # Sharing the light's actuator_key is what guarantees that. Every entry with
    # the same key gets the same is_on above, in all three modes -- on, off, and
    # automatic, where the lamp follows the Pi's 06:00-18:00 schedule. The fan
    # therefore cannot drift out of step with the lamp by so much as one pass,
    # which a separate key or a second rule could not promise.
    #
    # It is listed immediately after the lamp so the two stay together in the
    # bitmap. Bit order here is the firmware's RELAY_PINS order on ESP32 #4.
    {"node_id": "soil-node-4", "module_id": "relay3", "input": 5, "label": "Grow Light Fan", "channel_key": "", "row_key": "", "actuator_key": "light"},
    {"node_id": "soil-node-4", "module_id": "relay3", "input": 7, "label": "Fans 1-4", "channel_key": "", "row_key": "", "actuator_key": "fan"},
    {"node_id": "soil-node-4", "module_id": "relay3", "input": 6, "label": "Fans 5-7", "channel_key": "", "row_key": "", "actuator_key": "fan"},
    # The misting line sits on GPIO32 driving relay2/in6. It moved from ESP32
    # #3 to ESP32 #1 keeping both the pin and the relay channel, so only the
    # node driving it changed.
    {"node_id": "soil-node-1", "module_id": "relay2", "input": 6, "label": "Misting", "channel_key": "", "row_key": "", "actuator_key": "misting"},
)
PI_EDGE_SYNC_QUEUE: queue.Queue[list[tuple[str, str, object | None]]] = queue.Queue()
PI_EDGE_SYNC_WORKER_LOCK = threading.Lock()
PI_EDGE_SYNC_WORKER: threading.Thread | None = None
DATABASE_INITIALIZATION_LOCK = threading.Lock()
DATABASE_INITIALIZED = False
LOCAL_SCHEMA_READY = False
IRRIGATION_CONTROL_INTERVAL_SECONDS = max(
    2.0,
    float(os.getenv("ICUCROPS_IRRIGATION_CONTROL_INTERVAL_SECONDS", "10")),
)
IRRIGATION_CONTROL_MIN_CYCLE_SECONDS = max(
    0.25,
    float(os.getenv("ICUCROPS_IRRIGATION_CONTROL_MIN_CYCLE_SECONDS", "0.25")),
)
IRRIGATION_CONTROL_WORKER_LOCK = threading.Lock()
IRRIGATION_CONTROL_WORKER: threading.Thread | None = None
IRRIGATION_CONTROL_TRIGGER = threading.Event()
# The last control surface each worker saw, so a change written by something
# other than this process is still announced to the browsers. The edge sync
# daemon is a separate process: when it pulls a row mode or an actuator switch
# down from Supabase, nothing in this process asked for the write, and the
# within-cycle comparison the workers already do cannot see it -- both halves
# of that comparison are read after the change landed. Comparing across cycles
# instead is what lets a press on one device reach every other.
CONTROL_SURFACE_LOCK = threading.Lock()
LAST_IRRIGATION_CONTROL_SURFACE: str | None = None
LAST_ENVIRONMENT_CONTROL_SURFACE: str | None = None
# Whether the greenhouse was last seen needing to be opened. The condition is
# read every cycle but is only worth an alert when it *changes*: a house that
# stays humid for an hour is one notification, not three hundred and sixty.
LAST_GREENHOUSE_VENT_REASON: str | None = None
# The last out-of-range state seen for each row's own crop parameters, keyed
# "row1:moisture". Same edge-trigger reasoning as the vent alert above: a row
# that sits below its moisture minimum all afternoon is one notification, not
# one per control cycle. The value stored is the direction ("low"/"high") so a
# reading that crosses from below the minimum to above the maximum is announced
# again -- that is a different problem with different remedy.
LAST_READING_ALERT_STATES: dict[str, str] = {}
# Serializes API Start/Stop/Mode commits with the periodic reconciler. Without
# it the worker can read the previous SQLite value after the immediate MQTT ON
# snapshot but before the transaction commits, briefly forcing the relay OFF.
IRRIGATION_STATE_TRANSITION_LOCK = threading.RLock()
ENVIRONMENT_CONTROL_INTERVAL_SECONDS = max(
    2.0,
    float(os.getenv("ICUCROPS_ENVIRONMENT_CONTROL_INTERVAL_SECONDS", "10")),
)
ENVIRONMENT_CONTROL_MIN_CYCLE_SECONDS = max(
    0.25,
    float(os.getenv("ICUCROPS_ENVIRONMENT_CONTROL_MIN_CYCLE_SECONDS", "0.25")),
)
ENVIRONMENT_CONTROL_WORKER_LOCK = threading.Lock()
ENVIRONMENT_CONTROL_WORKER: threading.Thread | None = None
ENVIRONMENT_CONTROL_TRIGGER = threading.Event()
RELAY_DESIRED_STATE_LOCK = threading.Lock()
RELAY_DESIRED_STATE_CACHE: dict[str, object] | None = None
RELAY_IRRIGATION_STATE_CACHE: dict[str, object] = {}
# Seeded from the relay-backed keys so rewiring an actuator onto a relay does
# not leave a cache still keyed on the one it replaced.
RELAY_ACTUATOR_MODE_CACHE: dict[str, str] = {
    # Each at its resting mode until the registry has been read. Misting must
    # not start out Automatic: a water run in that gap would open the mist on
    # a farm that has it switched Off.
    key: ACTUATOR_RESTING_MODES.get(key, "automatic")
    for key in RELAY_BACKED_ACTUATOR_KEYS
}
# A local ON/OFF/Automatic command must win while its database write is
# still being persisted. A periodic registry refresh may read the previous value
# during that window; without this guard it makes every relay-backed actuator
# oscillate between the requested mode and the stale stored mode.
RELAY_ACTUATOR_PENDING_MODE_CACHE: dict[str, str] = {}
# Whether the mist goes with the water run in progress. Decided once, when the
# run starts, and kept until the water stops -- see build_relay_desired_state.
RELAY_MIST_WITH_WATER_LATCH: dict[str, object] = {}
RELAY_ACTUATOR_AUTO_CACHE: dict[str, bool] = {
    key: False for key in AUTOMATIC_ACTUATOR_KEYS
}
RELAY_SENSOR_POWER_CACHE: dict[str, str] = {
    # light-level is listed explicitly because normalize_sensor_power_state()
    # falls back to "off" for anything it has never seen, and an unlisted
    # sensor would show as powered down on the node card from first boot.
    "moisture": "on", "ec": "on", "ph": "on", "dht22": "on", "light-level": "on",
    **{
        f"{row_key}-{sensor_type}": "on"
        for row_key in VALID_CULTIVATION_ROWS
        for sensor_type in ("moisture", "rs485")
    },
}
RELAY_SENSOR_PENDING_POWER_CACHE: dict[str, str] = {}
RELAY_TRIGGER_HOST = os.getenv("ICUCROPS_RELAY_TRIGGER_HOST", "127.0.0.1").strip() or "127.0.0.1"
RELAY_TRIGGER_PORT = max(
    1,
    min(65_535, int(os.getenv("ICUCROPS_RELAY_TRIGGER_PORT", "45831"))),
)
UTC_TIMESTAMP_LOCK = threading.Lock()
LAST_UTC_TIMESTAMP: datetime | None = None
OTP_EMAIL_RELAY_INTERVAL_SECONDS = max(
    2.0,
    float(os.getenv("ICUCROPS_OTP_RELAY_INTERVAL_SECONDS", "3")),
)
OTP_EMAIL_RELAY_WORKER_LOCK = threading.Lock()
OTP_EMAIL_RELAY_WORKER: threading.Thread | None = None
OTP_EMAIL_RELAY_WORKER_ID = secrets.token_urlsafe(12)








def supabase_display_target() -> str:
    """The Postgres host, with the password stripped, safe for health output."""
    if not POSTGRES_URL:
        return ""
    host = POSTGRES_URL.rpartition("@")[2]
    return f"postgresql://{host}" if host else "postgresql://(configured)"


def postgres_backend_enabled() -> bool:
    """Whether the SQL path should run against Supabase rather than the file.

    Having a connection string is what decides this, not the mode name. Each
    host carries its own environment, and one of them keeping a stale
    ICUCROPS_DATABASE_BACKEND from the Firebase era should not quietly send
    that host somewhere else - on a managed host with no durable disk, the
    SQLite fallback is an empty database on every cold start.

    `sqlite` is the one explicit opt-out, for an installation that is meant to
    stay local: the Pi running offline.
    """
    if DATABASE_BACKEND == "sqlite":
        return False
    return bool(POSTGRES_URL)


def sqlite_backend_enabled() -> bool:
    return not postgres_backend_enabled()




DEFAULT_HOST = (
    os.getenv("ICUCROPS_HOST", "").strip()
    or os.getenv("ARUGULA_HOST", "").strip()
    or "127.0.0.1"
)
DEFAULT_PORT = configured_int(
    "ICUCROPS_PORT",
    configured_int("ARUGULA_PORT", int(DEFAULT_API_FALLBACK_PORT)),
)
LEGACY_DEMO_USER_EMAILS = (
    "procysarate@gmail.com",
    "user1@gmail.com",
    "user2@gmail.com",
)
# SQLite schema for authentication, cultivation tracking, and notification history.
SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    password_iterations INTEGER NOT NULL DEFAULT 310000,
    is_active INTEGER NOT NULL DEFAULT 1,
    profile_photo_path TEXT NOT NULL DEFAULT '',
    profile_photo_mime TEXT NOT NULL DEFAULT '',
    profile_photo_data BLOB,
    profile_photo_version TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS login_challenges (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    otp_hash TEXT NOT NULL,
    otp_salt TEXT NOT NULL,
    otp_iterations INTEGER NOT NULL DEFAULT 120000,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS account_creation_challenges (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    password_iterations INTEGER NOT NULL DEFAULT 310000,
    otp_hash TEXT NOT NULL,
    otp_salt TEXT NOT NULL,
    otp_iterations INTEGER NOT NULL DEFAULT 120000,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS admin_login_attempts (
    scope_key TEXT PRIMARY KEY,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    user_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cultivations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    row_key TEXT NOT NULL UNIQUE,
    crop_type TEXT NOT NULL,
    custom_plant_name TEXT NOT NULL DEFAULT '',
    crop_name TEXT NOT NULL,
    planting_date TEXT NOT NULL,
    harvest_date TEXT NOT NULL,
    days_to_harvest INTEGER NOT NULL,
    parameter_mode TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    created_by_user_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (created_by_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CHECK (row_key IN ('row1', 'row2', 'row3', 'row4')),
    CHECK (parameter_mode IN ('recommended', 'custom'))
);

-- What actually came out of each row, kept after the row is replanted.
--
-- This cannot be a status column on cultivations: row_key is UNIQUE there, so
-- a finished crop left in place would block the next planting. A harvest is a
-- different kind of record anyway -- append-only history rather than current
-- state, owning no slot.
--
-- days_grown and on_schedule are derived once, when the harvest is recorded,
-- and stored. Computing them later needs "today", which is not stable across a
-- re-run of the same report. parameters_json is copied for the same reason:
-- the record has to stay readable after its cultivation is gone.
--
-- created_at carries the *cultivation's* created_at, not this row's. That is
-- what cultivation_sync_key() hashes, so keeping it lets a harvest be matched
-- to the tombstone that removed the cultivation it came from.
CREATE TABLE IF NOT EXISTS cultivation_harvests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    row_key TEXT NOT NULL,
    crop_type TEXT NOT NULL,
    custom_plant_name TEXT NOT NULL DEFAULT '',
    crop_name TEXT NOT NULL,
    planting_date TEXT NOT NULL,
    harvest_date TEXT NOT NULL,
    days_to_harvest INTEGER NOT NULL,
    parameter_mode TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    harvested_at TEXT NOT NULL,
    days_grown INTEGER NOT NULL DEFAULT 0,
    on_schedule INTEGER NOT NULL DEFAULT 1,
    -- How the cultivation ended. 'harvested' is the check button, 'removed'
    -- the bin. A removal used to DELETE the row and leave nothing behind, so
    -- the report could not say a crop had been scrapped, only that it was no
    -- longer growing -- and a farm that pulled a failed row looked identical
    -- to one that never planted it. Both endings are the same shape of fact,
    -- so they share a table and are told apart by this column.
    outcome TEXT NOT NULL DEFAULT 'harvested'
        CHECK (outcome IN ('harvested', 'removed')),
    planted_by_user_id INTEGER,
    harvested_by_user_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (planted_by_user_id) REFERENCES users (id) ON DELETE SET NULL,
    FOREIGN KEY (harvested_by_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CHECK (row_key IN ('row1', 'row2', 'row3', 'row4'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL CHECK (scope IN ('all', 'admin', 'user')),
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT '',
    source_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    -- Also added to older databases by ensure_notification_delete_schema.
    -- Declared here too because the realtime fingerprint reads it, and a
    -- query that fails there silently stops every page from repainting.
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS notification_reads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    read_at TEXT NOT NULL,
    FOREIGN KEY (notification_id) REFERENCES notifications (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (notification_id, user_id)
);

CREATE TABLE IF NOT EXISTS sensor_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_key TEXT NOT NULL UNIQUE,
    -- Nullable, matching Supabase, where this is a foreign key into
    -- sensor_definitions. A registry row for a sensor with no matching
    -- definition stores NULL; "" would be a key that references nothing, which
    -- is what Postgres rejected with
    --   Key (definition_key)=() is not present in table "sensor_definitions"
    -- and is why ensure_sensor_registry_record() writes `definition_key or
    -- None`. This column was NOT NULL here while that code sent NULL, so every
    -- reading from an unregistered sensor raised IntegrityError on SQLite --
    -- on the Pi, which is the only place SQLite is authoritative.
    definition_key TEXT DEFAULT NULL,
    backend_key TEXT NOT NULL DEFAULT '',
    display_name TEXT NOT NULL,
    device_name TEXT NOT NULL DEFAULT '',
    row_key TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'sensor',
    power_state TEXT NOT NULL DEFAULT 'on',
    actuator_mode TEXT NOT NULL DEFAULT '',
    alert_mode TEXT NOT NULL DEFAULT '',
    hardware_identifier TEXT NOT NULL DEFAULT '',
    metric_keys_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sensor_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    definition_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'sensor',
    default_device_name TEXT NOT NULL DEFAULT '',
    default_row_key TEXT NOT NULL DEFAULT '',
    default_power_state TEXT NOT NULL DEFAULT 'on',
    default_actuator_mode TEXT NOT NULL DEFAULT '',
    metric_keys_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sensor_backends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backend_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    ingest_path TEXT NOT NULL DEFAULT '',
    protocol TEXT NOT NULL DEFAULT 'http',
    source_type TEXT NOT NULL DEFAULT 'api',
    hardware_identifier_prefix TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_key TEXT NOT NULL,
    reading_payload_json TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'api',
    source_identifier TEXT NOT NULL DEFAULT '',
    captured_at TEXT NOT NULL,
    FOREIGN KEY (sensor_key) REFERENCES sensor_registry (sensor_key) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_state (
    state_key TEXT PRIMARY KEY,
    state_value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS irrigation_settings (
    channel_key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    automatic_enabled INTEGER NOT NULL DEFAULT 1,
    automatic_duration_seconds INTEGER NOT NULL DEFAULT 0,
    manual_duration_seconds INTEGER NOT NULL DEFAULT 0,
    schedule_enabled INTEGER NOT NULL DEFAULT 1,
    schedule_start_time TEXT NOT NULL DEFAULT '06:00',
    schedule_duration_seconds INTEGER NOT NULL DEFAULT 0,
    schedule_frequency TEXT NOT NULL DEFAULT 'daily',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS irrigation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_key TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    requested_by_user_id INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (requested_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS irrigation_row_settings (
    cultivation_id INTEGER NOT NULL,
    row_key TEXT NOT NULL,
    channel_key TEXT NOT NULL,
    automatic_enabled INTEGER NOT NULL DEFAULT 1,
    automatic_duration_seconds INTEGER NOT NULL DEFAULT 900,
    manual_duration_seconds INTEGER NOT NULL DEFAULT 900,
    schedule_enabled INTEGER NOT NULL DEFAULT 1,
    schedule_start_time TEXT NOT NULL DEFAULT '06:00',
    schedule_duration_seconds INTEGER NOT NULL DEFAULT 1200,
    schedule_frequency TEXT NOT NULL DEFAULT 'daily',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (cultivation_id, channel_key),
    UNIQUE (row_key, channel_key),
    CHECK (row_key IN ('row1', 'row2', 'row3', 'row4')),
    FOREIGN KEY (cultivation_id) REFERENCES cultivations (id) ON DELETE CASCADE,
    FOREIGN KEY (channel_key) REFERENCES irrigation_settings (channel_key) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS irrigation_row_controls (
    cultivation_id INTEGER PRIMARY KEY,
    row_key TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL DEFAULT 'automatic',
    is_enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    CHECK (row_key IN ('row1', 'row2', 'row3', 'row4')),
    CHECK (mode IN ('automatic', 'schedule', 'manual')),
    FOREIGN KEY (cultivation_id) REFERENCES cultivations (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS irrigation_run_rows (
    irrigation_run_id INTEGER NOT NULL,
    cultivation_id INTEGER,
    row_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    PRIMARY KEY (irrigation_run_id, row_key),
    CHECK (row_key IN ('row1', 'row2', 'row3', 'row4')),
    FOREIGN KEY (irrigation_run_id) REFERENCES irrigation_runs (id) ON DELETE CASCADE,
    FOREIGN KEY (cultivation_id) REFERENCES cultivations (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sync_tombstones (
    entity TEXT NOT NULL,
    natural_key TEXT NOT NULL,
    deleted_at TEXT NOT NULL,
    PRIMARY KEY (entity, natural_key)
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_login_challenges_user_id ON login_challenges (user_id);
CREATE INDEX IF NOT EXISTS idx_login_challenges_expires_at ON login_challenges (expires_at);
CREATE INDEX IF NOT EXISTS idx_account_creation_challenges_email ON account_creation_challenges (email);
CREATE INDEX IF NOT EXISTS idx_account_creation_challenges_expires_at ON account_creation_challenges (expires_at);
CREATE INDEX IF NOT EXISTS idx_admin_login_attempts_locked_until ON admin_login_attempts (locked_until);
CREATE INDEX IF NOT EXISTS idx_cultivations_row_key ON cultivations (row_key);
CREATE INDEX IF NOT EXISTS idx_cultivation_harvests_harvested_at ON cultivation_harvests (harvested_at DESC);
CREATE INDEX IF NOT EXISTS idx_cultivation_harvests_row_key ON cultivation_harvests (row_key);
-- The natural key the sync and the HTTPS relay both use. A unique index rather
-- than a table constraint, so it also lands on databases that already exist,
-- and so INSERT OR IGNORE is a true no-op: both transports may carry the same
-- harvest and neither has a durable ack, so replaying a pass has to be safe.
-- A row holds one crop at a time, so a planting is named by (row_key,
-- planting_date); harvested_at separates a replant-and-harvest on the same day.
CREATE UNIQUE INDEX IF NOT EXISTS cultivation_harvests_natural_key
    ON cultivation_harvests (row_key, planting_date, harvested_at);
CREATE INDEX IF NOT EXISTS idx_notifications_scope_created_at ON notifications (scope, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notification_reads_user_id ON notification_reads (user_id);
CREATE INDEX IF NOT EXISTS idx_sensor_registry_row_key ON sensor_registry (row_key);
CREATE INDEX IF NOT EXISTS idx_sensor_registry_hardware_identifier ON sensor_registry (hardware_identifier);
CREATE INDEX IF NOT EXISTS idx_sensor_definitions_definition_key ON sensor_definitions (definition_key);
CREATE INDEX IF NOT EXISTS idx_sensor_backends_backend_key ON sensor_backends (backend_key);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_key_captured_at ON sensor_readings (sensor_key, captured_at DESC);
-- The composite index above leads with sensor_key, so it cannot answer a
-- bare MAX(captured_at): SQLite walks every entry instead. The realtime
-- fingerprint asks for exactly that on every poll. Supabase already has the
-- equivalent index from supabase/migrations/0001_initial_schema.sql.
CREATE INDEX IF NOT EXISTS idx_sensor_readings_captured_at ON sensor_readings (captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_irrigation_runs_channel_key_started_at ON irrigation_runs (channel_key, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_irrigation_row_settings_row_key ON irrigation_row_settings (row_key);
CREATE INDEX IF NOT EXISTS idx_irrigation_row_settings_channel_key ON irrigation_row_settings (channel_key);
CREATE INDEX IF NOT EXISTS idx_irrigation_row_controls_mode ON irrigation_row_controls (mode);
CREATE INDEX IF NOT EXISTS idx_irrigation_run_rows_cultivation_id ON irrigation_run_rows (cultivation_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_run_rows_row_key_status ON irrigation_run_rows (row_key, status);
"""


class MailConfigurationError(RuntimeError):
    """Raised when Gmail SMTP credentials are missing or invalid."""


# Shared UTC helpers keep backend timestamps consistent for the dashboard and history views.
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    # Windows and some Pi kernels can return the same wall-clock timestamp for
    # several rapid events. Keep generated timestamps strictly increasing so a
    # sensor reading received immediately after irrigation completion is still
    # recognized as new.
    global LAST_UTC_TIMESTAMP
    with UTC_TIMESTAMP_LOCK:
        timestamp = utc_now()
        if LAST_UTC_TIMESTAMP is not None and timestamp <= LAST_UTC_TIMESTAMP:
            timestamp = LAST_UTC_TIMESTAMP + timedelta(microseconds=1)
        LAST_UTC_TIMESTAMP = timestamp
        return timestamp.isoformat()


def write_private_secret(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary_path.write_text(value, encoding="utf-8")
    try:
        temporary_path.chmod(0o600)
    except OSError:
        pass
    temporary_path.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_or_create_private_secret(path: Path, configured_value: str, *, byte_count: int = 32) -> str:
    configured = configured_value.strip()
    if configured:
        return configured

    try:
        existing = path.read_text(encoding="utf-8").strip()
    except OSError:
        existing = ""
    if existing:
        return existing

    generated = secrets.token_urlsafe(byte_count)
    try:
        write_private_secret(path, generated)
    except OSError as error:
        raise RuntimeError(f"Could not create private runtime secret at {path}.") from error
    return generated


def auth_session_secret() -> bytes:
    global AUTH_SESSION_SECRET
    with AUTH_SESSION_SECRET_LOCK:
        if AUTH_SESSION_SECRET is None:
            secret = load_or_create_private_secret(
                AUTH_SESSION_SECRET_PATH,
                os.getenv("ICUCROPS_SESSION_SECRET", ""),
                byte_count=48,
            )
            AUTH_SESSION_SECRET = secret.encode("utf-8")
        return AUTH_SESSION_SECRET


def device_api_token() -> str:
    global DEVICE_TOKEN
    with DEVICE_TOKEN_LOCK:
        if DEVICE_TOKEN is None:
            DEVICE_TOKEN = load_or_create_private_secret(
                DEVICE_TOKEN_PATH,
                os.getenv("ICUCROPS_DEVICE_TOKEN", ""),
                byte_count=32,
            )
        return DEVICE_TOKEN


def base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def normalize_auth_client_id(value: object) -> str:
    client_id = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", client_id):
        return ""
    return client_id


def issue_auth_session(user: dict[str, object], *, client_id: str = "") -> dict[str, str]:
    issued_at = int(utc_now().timestamp())
    expires_at = issued_at + AUTH_SESSION_TTL_SECONDS
    role = normalize_role(user.get("role"))
    claims = {
        "v": 1,
        "sub": str(user.get("id") or "").strip(),
        "name": str(user.get("displayName") or "").strip(),
        "email": normalize_email(user.get("email")),
        "role": role,
        "iat": issued_at,
        "exp": expires_at,
        "jti": secrets.token_urlsafe(18),
        "cid": normalize_auth_client_id(client_id),
    }
    encoded_claims = base64url_encode(
        json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        auth_session_secret(),
        encoded_claims.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return {
        "accessToken": f"{encoded_claims}.{base64url_encode(signature)}",
        "expiresAt": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
        "tokenType": "Bearer",
        "jti": claims["jti"],
    }


def verify_auth_session(token: str) -> dict[str, str] | None:
    normalized_token = str(token or "").strip()
    if not normalized_token or len(normalized_token) > 4096:
        return None

    try:
        encoded_claims, encoded_signature = normalized_token.split(".", 1)
        signature = base64url_decode(encoded_signature)
        expected_signature = hmac.new(
            auth_session_secret(),
            encoded_claims.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected_signature):
            return None
        raw_claims = json.loads(base64url_decode(encoded_claims).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        return None

    if not isinstance(raw_claims, dict) or raw_claims.get("v") != 1:
        return None

    user_id = str(raw_claims.get("sub") or "").strip()
    role = str(raw_claims.get("role") or "").strip().lower()
    try:
        issued_at = int(raw_claims.get("iat"))
        expires_at = int(raw_claims.get("exp"))
    except (TypeError, ValueError):
        return None

    now = int(utc_now().timestamp())
    if (
        not user_id.isdigit()
        or role not in {"admin", "user"}
        or issued_at > now + 60
        or expires_at <= now
        or expires_at - issued_at > AUTH_SESSION_TTL_SECONDS
    ):
        return None

    return {
        "id": user_id,
        "displayName": str(raw_claims.get("name") or "").strip(),
        "email": normalize_email(raw_claims.get("email")),
        "role": role,
        "roleLabel": role_label(role),
        "jti": str(raw_claims.get("jti") or "").strip(),
        "clientId": normalize_auth_client_id(raw_claims.get("cid")),
    }


def claim_active_auth_session(
    user_id: str, session_jti: str, client_id: str
) -> None:
    """Record this login as the account's one live session.

    active_user_for_auth_session_details already refuses a token whose jti is
    not the stored one -- that is how "only one device at a time" is meant to
    work. Nothing ever wrote the column, though, so it stayed empty and the
    check short-circuited on `if active_jti`: every session stayed valid and
    the rule was silently off on every backend.

    The client id is stored alongside so the same browser re-logging in (a
    reload, a second tab, an expired token replaced) is not treated as a
    different device and does not sign itself out.

    updated_at is deliberately left alone. The session columns never travel
    (they are per host), but updated_at is what both syncs compare, newest
    wins, over the whole account -- password included. A login stamping it
    made the account "newer" than a password changed on the other side, so
    the old password won: a change made at the kiosk was refused online and
    then pulled back down over the kiosk's own new password.
    """
    normalized_id = str(user_id or "").strip()
    normalized_jti = str(session_jti or "").strip()
    if not normalized_id.isdigit() or not normalized_jti:
        return

    try:
        with connect_database() as connection:
            connection.execute(
                """
                UPDATE users
                SET active_session_jti = ?,
                    active_session_client_id = ?,
                    active_session_issued_at = ?
                WHERE id = ?
                """,
                (
                    normalized_jti,
                    normalize_auth_client_id(client_id),
                    utc_now_iso(),
                    int(normalized_id),
                ),
            )
    except (sqlite3.Error, RuntimeError, OSError) as error:
        # A login that cannot record its claim is still a valid login. Refusing
        # it here would lock people out of the farm over a database hiccup; the
        # cost is that the previous session survives until the next write.
        print(f"ICuCrops: could not claim the active session ({error})")
        return

    # The verifier caches the stored jti for a few seconds. Without this the
    # new login is judged against the previous one and signs itself out.
    invalidate_auth_session_user_cache(normalized_id)


AUTH_SESSION_DEVICE_STATE_PREFIX = "auth.session_device:"


def describe_login_device(
    user_agent: str,
    *,
    hints: object = None,
    farm_kiosk: bool = False,
) -> str:
    """A human name for the device a login came from, as exact as the browser allows.

    Shown to the device that was signed out, so its owner can tell whether it
    was a colleague on the kiosk, their own phone, or someone they do not
    expect. `hints` is what the login page read from Chromium's client hints:
    an Android phone's exact model (SM-A155F reads "Samsung Galaxy A15") and
    each platform's version. No browser gives a computer's name, and Safari
    gives no iPhone model -- those stop at the kind of device and its version.
    Never an address.
    """
    if farm_kiosk:
        return "Farm kiosk (Raspberry Pi screen)"
    agent = str(user_agent or "")
    lowered = agent.lower()
    hint = hints if isinstance(hints, dict) else {}
    model = re.sub(r"[^A-Za-z0-9 _+().-]", "", str(hint.get("model") or "")).strip()[:60]
    platform_version = re.sub(r"[^0-9.]", "", str(hint.get("platformVersion") or ""))[:20]
    major = platform_version.split(".", 1)[0] if platform_version else ""

    os_name = ""
    if "iphone" in lowered or "ipad" in lowered:
        device = "iPad" if "ipad" in lowered else "iPhone"
        found = re.search(r"os (\d+)[_.](\d+)", lowered)
        os_name = f"iOS {found.group(1)}.{found.group(2)}" if found else "iOS"
    elif "android" in lowered:
        device = named_phone_model(model) or ("Android phone" if "mobile" in lowered else "Android tablet")
        found = re.search(r"android (\d+)", lowered)
        version = major or (found.group(1) if found else "")
        os_name = f"Android {version}" if version else "Android"
    elif "windows" in lowered:
        device = "Windows computer"
        if major.isdigit():
            os_name = "Windows 11" if int(major) >= 13 else "Windows 10"
    elif "cros" in lowered:
        device = "Chromebook"
    elif "macintosh" in lowered or "mac os x" in lowered:
        device = "Mac"
        os_name = f"macOS {major}" if major.isdigit() and int(major) >= 11 else ""
    elif "linux" in lowered and ("aarch64" in lowered or "armv7" in lowered or "raspbian" in lowered):
        device = "Raspberry Pi"
    elif "linux" in lowered:
        device = "Linux computer"
    else:
        device = "Unknown device"

    if "edg/" in lowered or "edga/" in lowered or "edgios/" in lowered:
        browser = "Edge"
    elif "samsungbrowser/" in lowered:
        browser = "Samsung Internet"
    elif "opr/" in lowered or "opera" in lowered:
        browser = "Opera"
    elif "firefox/" in lowered or "fxios/" in lowered:
        browser = "Firefox"
    elif "crios/" in lowered or "chrome/" in lowered or "chromium/" in lowered:
        browser = "Chrome"
    elif "safari/" in lowered:
        browser = "Safari"
    else:
        browser = ""
    return " · ".join(part for part in (device, os_name, browser) if part)


# Model codes as Android reports them, to the name on the box. Samsung's A and
# M series follow a rule (SM-A155F is the A15, SM-M146B the M14), and the S
# flagships another (SM-S921 is the S24, 6 the Plus, 8 the Ultra). Other
# makers' codes are only given their brand; the code itself stays in brackets
# so nothing is guessed past what the phone said.
_ANDROID_BRAND_PREFIXES = (
    ("SM-", "Samsung"),
    ("CPH", "OPPO"),
    ("RMX", "realme"),
    ("Pixel", "Google"),
)


def named_phone_model(model: str) -> str:
    code = str(model or "").strip()
    if not code or code.upper() == "K":
        # "K" is what a reduced User-Agent leaves where the model used to be.
        return ""
    series = re.match(r"^SM-([AM])(\d{2})\d", code, re.IGNORECASE)
    if series:
        return f"Samsung Galaxy {series.group(1).upper()}{series.group(2)} ({code})"
    flagship = re.match(r"^SM-S9(\d)(\d)", code, re.IGNORECASE)
    if flagship:
        tier = {"6": " Plus", "7": " Plus", "8": " Ultra"}.get(flagship.group(2), "")
        return f"Samsung Galaxy S{22 + int(flagship.group(1))}{tier} ({code})"
    for prefix, brand in _ANDROID_BRAND_PREFIXES:
        if code.upper().startswith(prefix.upper()):
            return code if brand == "Google" else f"{brand} {code}"
    if re.match(r"^V2\d{3}", code):
        return f"vivo {code}"
    if re.match(r"^\d{4,5}[A-Z0-9]{3,}$", code):
        return f"Xiaomi {code}"
    return code


def remember_auth_session_device(user_id: str, label: str) -> None:
    """Note which device holds the account's live session, on this host only.

    system_state keys outside irrigation.* and mqtt_node_status:* never sync,
    which is right: the session columns are per host too.
    """
    normalized_id = str(user_id or "").strip()
    if not normalized_id.isdigit():
        return
    try:
        with connect_database() as connection:
            set_system_state_value(
                connection,
                key=f"{AUTH_SESSION_DEVICE_STATE_PREFIX}{normalized_id}",
                value=json.dumps({"label": str(label or "")[:140], "signedInAt": utc_now_iso()}),
            )
    except (sqlite3.Error, RuntimeError, OSError) as error:
        # Only a courtesy for the signed-out device; never fail a login on it.
        print(f"ICuCrops: could not note the signed-in device ({error})")


def auth_session_device(user_id: str) -> dict[str, str] | None:
    """The device that took over the account, as remember_auth_session_device left it."""
    normalized_id = str(user_id or "").strip()
    if not normalized_id.isdigit():
        return None
    try:
        with connect_database() as connection:
            row = connection.execute(
                "SELECT state_value FROM system_state WHERE state_key = ?",
                (f"{AUTH_SESSION_DEVICE_STATE_PREFIX}{normalized_id}",),
            ).fetchone()
    except (sqlite3.Error, RuntimeError, OSError):
        return None
    try:
        stored = json.loads(str(row["state_value"])) if row else None
    except (TypeError, ValueError):
        return None
    if not isinstance(stored, dict) or not str(stored.get("label") or "").strip():
        return None
    return {
        "label": str(stored.get("label") or "").strip(),
        "signedInAt": str(stored.get("signedInAt") or "").strip(),
    }


def invalidate_auth_session_user_cache(user_id: int | str) -> None:
    with AUTH_SESSION_USER_CACHE_LOCK:
        AUTH_SESSION_USER_CACHE.pop(str(user_id).strip(), None)


def request_is_farm_kiosk() -> bool:
    """True for a request from the Pi's own screen, the shared farm kiosk.

    The kiosk is exempt from "one device at a time": it is a shared terminal
    anyone may sign in to with any account, even one open on a phone or
    online. It neither signs other devices out nor gets signed out itself.
    Phones on the farm network reach the same Pi but not from its own
    address, so they keep the rule.
    """
    if not has_request_context():
        return False
    try:
        return server_is_raspberry_pi() and request_is_from_server_device()
    except Exception:  # noqa: BLE001 - never let the check itself refuse a session
        return False


def active_user_for_auth_session_details(session_user: dict[str, str]) -> tuple[dict[str, str] | None, str]:
    """Returns (user, reason). reason is "" on success, "superseded" when a
    newer login elsewhere replaced this session, or "revoked" otherwise."""
    user_id = str(session_user.get("id") or "").strip()
    session_email = normalize_email(session_user.get("email"))
    session_jti = str(session_user.get("jti") or "").strip()
    session_client_id = normalize_auth_client_id(session_user.get("clientId"))
    if not user_id.isdigit() or not session_email:
        return None, "revoked"

    now = time.monotonic()
    with AUTH_SESSION_USER_CACHE_LOCK:
        cached = AUTH_SESSION_USER_CACHE.get(user_id)
        if cached and cached[0] > now:
            active_user, active_jti, active_client_id = cached[1], cached[2], cached[3]
            if active_user["email"] != session_email:
                return None, "revoked"
            same_client = bool(
                active_client_id
                and session_client_id
                and hmac.compare_digest(active_client_id, session_client_id)
            )
            # The cache may only confirm a session, never supersede one. On
            # Vercel each warm instance holds its own copy, and a login only
            # invalidates the instance that served it. Another instance still
            # held the previous login's jti for up to the TTL and judged the
            # NEW login superseded, so the device that just signed in was
            # shown "You have been signed out" too. A mismatch re-reads the
            # stored claim below, which decides which session really lost.
            if (
                not active_jti
                or not session_jti
                or hmac.compare_digest(active_jti, session_jti)
                or same_client
                or request_is_farm_kiosk()
            ):
                return dict(active_user), ""
        AUTH_SESSION_USER_CACHE.pop(user_id, None)

    try:
        with connect_database() as connection:
            row = find_user_by_id(connection, int(user_id))
            record = dict(row) if row else None
    except (sqlite3.Error, RuntimeError, OSError) as error:
        # The database being slow or unreachable says nothing about whether
        # this session is valid. Reporting "revoked" here signed people out
        # for a network hiccup -- and because the browser clears its stored
        # session on any 401, one blocked Postgres connection during a report
        # download ended the login entirely. Say the backend is unavailable
        # instead, so the caller answers 503 and the session survives.
        print(f"ICuCrops: auth session lookup failed ({error})")
        return None, "backend-unavailable"

    if not record or not bool(int(record.get("is_active") or 0)):
        return None, "revoked"

    active_user = {
        "id": str(record.get("id") or "").strip(),
        "displayName": str(record.get("display_name") or "").strip(),
        "email": normalize_email(record.get("email")),
        "role": normalize_role(record.get("role")),
        "roleLabel": role_label(record.get("role")),
    }
    if active_user["id"] != user_id or active_user["email"] != session_email:
        return None, "revoked"

    # Single active session per account: a newer login, on this device or any
    # other, overwrites active_session_jti and signs the older session out on
    # its next request. This used to run only on the Firebase backend; the
    # three active_session_* columns were carried into Postgres so that it
    # keeps working rather than quietly lapsing with the backend swap.
    active_jti = str(record.get("active_session_jti") or "").strip()
    active_client_id = normalize_auth_client_id(record.get("active_session_client_id"))
    same_client = bool(
        active_client_id
        and session_client_id
        and hmac.compare_digest(active_client_id, session_client_id)
    )
    if (
        active_jti
        and session_jti
        and not hmac.compare_digest(active_jti, session_jti)
        and not same_client
        and not request_is_farm_kiosk()
    ):
        return None, "superseded"

    with AUTH_SESSION_USER_CACHE_LOCK:
        AUTH_SESSION_USER_CACHE[user_id] = (
            now + AUTH_SESSION_USER_CACHE_TTL_SECONDS,
            dict(active_user),
            active_jti,
            active_client_id,
        )
    return active_user, ""


def active_user_for_auth_session(session_user: dict[str, str]) -> dict[str, str] | None:
    """Return the active account while retaining the revoke reason per request.

    Keeping this public helper's original user-or-None contract also lets test
    and deployment hooks replace it safely without causing tuple-unpack errors.
    """
    user, reason = active_user_for_auth_session_details(session_user)
    if has_request_context():
        g.auth_session_revoke_reason = reason
    return user


def request_bearer_token() -> str:
    authorization = str(flask_request.headers.get("Authorization") or "").strip()
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer":
        return ""
    return token.strip()


def authenticated_request_user() -> dict[str, str] | None:
    user = getattr(g, "authenticated_user", None)
    return user if isinstance(user, dict) else None


def request_user_is_admin() -> bool:
    return normalize_role((authenticated_request_user() or {}).get("role")) == "admin"


def request_user_can_access(user_id: str) -> bool:
    user = authenticated_request_user() or {}
    return request_user_is_admin() or hmac.compare_digest(
        str(user.get("id") or ""),
        str(user_id or "").strip(),
    )


def request_has_valid_device_token() -> bool:
    supplied = str(flask_request.headers.get("X-ICUCROPS-Device-Token") or "").strip()
    return bool(supplied) and hmac.compare_digest(supplied, device_api_token())


def realtime_scopes_for_api_mutation(path: str) -> set[str]:
    normalized_path = str(path or "").strip().lower()
    if normalized_path.startswith("/api/auth/"):
        if normalized_path.endswith("/reset"):
            return {"profile", "users"}
        return set()
    if normalized_path in {
        "/api/hardware/sync/tombstones",
        "/api/hardware/sync/accounts",
        "/api/hardware/sync/cultivations",
    }:
        return set()
    if normalized_path == "/api/hardware/sync/harvests":
        # A harvest the Pi carried up changes the report and the cultivation
        # history, nothing else.
        return {"cultivations"}
    if normalized_path.startswith("/api/reports"):
        # A report only reads. It is a POST so the section list and the date
        # range travel in a body rather than a URL, and publishing a change for
        # it would rebuild every open dashboard each time someone exports.
        return set()
    if normalized_path in {"/api/hardware/node-status", "/api/hardware/sync"}:
        # A board's status heartbeat only changes whether its sensors read as
        # connected. Falling through to "system" below made every one of them
        # -- four boards, every fifteen seconds -- refresh all six scopes and
        # rebuild the page in every open browser.
        return {"sensors"}
    if normalized_path == "/api/sensors/control":
        return {"sensors", "notifications"}
    if normalized_path.startswith("/api/sensors"):
        return {"sensors"}
    if normalized_path.startswith("/api/irrigation"):
        return {"irrigation", "sensors", "notifications"}
    if normalized_path.startswith("/api/cultivations"):
        return {"cultivations", "irrigation", "sensors", "notifications"}
    if normalized_path.startswith("/api/users"):
        return {"users", "notifications"}
    if normalized_path.startswith("/api/profile"):
        return {"profile", "users", "notifications"}
    if normalized_path.startswith("/api/notifications"):
        return {"notifications"}
    return {"system"}


def publish_realtime_change(scopes: set[str], *, source_path: str = "") -> dict[str, str]:
    normalized_scopes = sorted({str(scope or "").strip().lower() for scope in scopes if str(scope or "").strip()})
    if not normalized_scopes:
        return {}

    revision = f"{time.time_ns()}-{secrets.token_urlsafe(8)}"
    updates = {scope: revision for scope in normalized_scopes}
    with REALTIME_VERSIONS_LOCK:
        REALTIME_LOCAL_VERSIONS.update(updates)

    # The Pi UI and MQTT bridge must never wait for internet access. Its local
    # version map is authoritative while on the edge; sensor/control records
    # are queued separately for background cloud synchronization.
    return updates


REALTIME_DATABASE_VERSION_QUERY = """
SELECT
    (
        -- The photo version and the name lengths are here for changes that
        -- arrive from the other side of the sync. Those keep the author's own
        -- updated_at, which need not be the newest in the table, and a photo
        -- can arrive on its own with no updated_at change at all -- so a
        -- picture or a name set on the website never repainted the kiosk.
        SELECT CAST(COUNT(*) AS TEXT) || ':'
            || COALESCE(CAST(MAX(id) AS TEXT), '') || ':'
            || COALESCE(MAX(updated_at), '') || ':'
            || COALESCE(MAX(profile_photo_version), '') || ':'
            || CAST(COALESCE(SUM(LENGTH(display_name)), 0) AS TEXT)
        FROM users
    ) AS users,
    (
        SELECT CAST(COUNT(*) AS TEXT) || ':'
            || COALESCE(CAST(MAX(id) AS TEXT), '') || ':'
            || COALESCE(MAX(updated_at), '')
        FROM cultivations
    ) AS cultivations,
    (
        -- Two aggregates in one SELECT defeat the MIN/MAX index optimisation on
        -- both SQLite and Postgres, so this scanned every row of the largest
        -- table in the database -- 120ms and climbing on the Pi, three times a
        -- second behind the kiosk's realtime poll. One aggregate per scalar
        -- subquery is the same fingerprint, read from the index instead.
        SELECT COALESCE(CAST((SELECT MAX(id) FROM sensor_readings) AS TEXT), '') || ':'
            || COALESCE((SELECT MAX(captured_at) FROM sensor_readings), '')
    ) || ':' || (
        SELECT CAST(COUNT(*) AS TEXT) || ':' || COALESCE(MAX(updated_at), '')
        FROM sensor_registry
    ) AS sensors,
    (
        SELECT CAST(COUNT(*) AS TEXT) || ':' || COALESCE(MAX(updated_at), '')
        FROM irrigation_settings
    ) || ':' || (
        SELECT CAST(COUNT(*) AS TEXT) || ':' || COALESCE(MAX(updated_at), '')
        FROM irrigation_row_settings
    ) || ':' || (
        SELECT CAST(COUNT(*) AS TEXT) || ':' || COALESCE(MAX(updated_at), '')
        FROM irrigation_row_controls
    ) || ':' || (
        -- Only the irrigation keys. Over the whole table this moved every time a
        -- board reported in or the sync advanced its cursor, and each move sent
        -- every open Irrigation page back for the full irrigation payload.
        SELECT CAST(COUNT(*) AS TEXT) || ':' || COALESCE(MAX(updated_at), '')
        FROM system_state
        WHERE state_key LIKE 'irrigation.%'
    ) AS irrigation,
    (
        -- A deletion is a mark on a row that is already counted, so without
        -- the deleted_at terms a History entry removed on the other side never
        -- repainted an open History page: nothing here moved.
        SELECT CAST(COUNT(*) AS TEXT) || ':'
            || COALESCE(CAST(MAX(id) AS TEXT), '') || ':'
            || COALESCE(MAX(created_at), '') || ':'
            || CAST(COUNT(deleted_at) AS TEXT) || ':'
            || COALESCE(MAX(deleted_at), '')
        FROM notifications
    ) || ':' || (
        SELECT CAST(COUNT(*) AS TEXT) || ':'
            || COALESCE(CAST(MAX(id) AS TEXT), '') || ':'
            || COALESCE(MAX(read_at), '')
        FROM notification_reads
    ) AS notifications
"""


def read_database_realtime_versions() -> dict[str, str]:
    """Fingerprint shared state so writes from the Pi wake cloud browsers.

    The local revision dictionary only covers mutations handled by this Python
    process.  The Pi-to-Supabase daemon writes through a different process, and
    Vercel can also serve consecutive polls from different instances.  These
    compact aggregate fingerprints make those database changes visible without
    returning any farm data or scanning the append-only sensor history.
    """
    try:
        with connect_database() as connection:
            row = connection.execute(REALTIME_DATABASE_VERSION_QUERY).fetchone()
    except Exception:
        # Realtime detection is an accelerator. Normal API refreshes and local
        # revisions must keep working during a transient database outage.
        return {}

    if row is None:
        return {}
    versions = {
        scope: str(row[scope] or "")
        for scope in ("users", "cultivations", "sensors", "irrigation", "notifications")
    }
    versions["profile"] = versions["users"]
    return versions


def cached_database_realtime_versions() -> dict[str, str]:
    """The database fingerprint, at most once per cache window.

    An empty result means the query failed, and that is deliberately not cached:
    a transient database error must not pin the fingerprint to nothing for the
    whole window, because an empty mapping compares unequal to every real one
    and would make every poller re-render.
    """
    global REALTIME_DATABASE_VERSION_CACHE, REALTIME_DATABASE_VERSION_CACHE_EXPIRES_AT

    if REALTIME_DATABASE_VERSION_CACHE_SECONDS <= 0:
        return read_database_realtime_versions()

    now = time.monotonic()
    with REALTIME_DATABASE_VERSION_CACHE_LOCK:
        if REALTIME_DATABASE_VERSION_CACHE_EXPIRES_AT > now:
            return dict(REALTIME_DATABASE_VERSION_CACHE)

    versions = read_database_realtime_versions()
    if versions:
        with REALTIME_DATABASE_VERSION_CACHE_LOCK:
            REALTIME_DATABASE_VERSION_CACHE = dict(versions)
            REALTIME_DATABASE_VERSION_CACHE_EXPIRES_AT = (
                time.monotonic() + REALTIME_DATABASE_VERSION_CACHE_SECONDS
            )
    return versions


def read_realtime_versions() -> dict[str, str]:
    with REALTIME_VERSIONS_LOCK:
        local_versions = dict(REALTIME_LOCAL_VERSIONS)

    database_versions = cached_database_realtime_versions()
    return {
        scope: f"{database_versions.get(scope, '')}|{local_versions.get(scope, '')}"
        for scope in sorted(set(database_versions) | set(local_versions))
    }


def local_https_is_ready() -> bool:
    global LOCAL_HTTPS_HEALTHY, LOCAL_HTTPS_HEALTH_EXPIRES_AT
    now = utc_now().timestamp()
    with LOCAL_HTTPS_HEALTH_LOCK:
        if LOCAL_HTTPS_HEALTH_EXPIRES_AT > now:
            return LOCAL_HTTPS_HEALTHY

        healthy = False
        try:
            with urlopen("https://localhost/api/health", timeout=1.0) as response:  # nosec B310 - URL is fixed/localhost/Brevo or operator config, never attacker-controlled
                healthy = 200 <= response.status < 300
        except (OSError, URLError):
            healthy = False

        LOCAL_HTTPS_HEALTHY = healthy
        LOCAL_HTTPS_HEALTH_EXPIRES_AT = now + 3
        return healthy


def parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_email(value: object) -> str:
    return str(value or "").strip().lower()


def normalize_role(value: object) -> str:
    role = str(value or "").strip().lower()
    return role if role in {"admin", "user"} else "user"


def role_label(role: str) -> str:
    return "Administrator" if normalize_role(role) == "admin" else "User"


def normalize_notification_scope(value: object) -> str:
    scope = str(value or "").strip().lower()
    return scope if scope in VALID_NOTIFICATION_SCOPES else "all"


def normalize_sensor_key(value: object) -> str:
    return str(value or "").strip()


def normalize_sensor_power_state(value: object) -> str:
    state = str(value or "").strip().lower()
    return state if state in VALID_SENSOR_POWER_STATES else "off"


def normalize_actuator_mode(value: object, actuator_key: str = "") -> str:
    """The stored mode for this actuator, or its resting mode when there is none.

    Every actuator takes Automatic, On and Off. A missing or unreadable mode
    falls back to Automatic, except where ACTUATOR_RESTING_MODES says
    otherwise: the misting line falls back to Off, the safe state for a water
    line, so it never starts following the water without being asked to.
    """
    mode = str(value or "").strip().lower()
    if mode in VALID_ACTUATOR_MODES:
        return mode
    return ACTUATOR_RESTING_MODES.get(normalize_sensor_key(actuator_key), "automatic")


def normalize_sensor_alert_mode(value: object, *, allow_empty: bool = False) -> str:
    mode = str(value or "").strip()
    if not mode:
        return "" if allow_empty else DEFAULT_SENSOR_ALERT_MODE

    normalized = mode.lower()
    if normalized in {"disabled", "off", "none", "no alerts"}:
        return "Disabled"
    if normalized in VALID_SENSOR_ALERT_MODES:
        return "Website Only" if normalized == "website only" else "Disabled"
    if normalized in {
        "web only",
        "website",
        "web",
        "in-app",
        "in app",
        "in-app only",
        "web notification",
        "web notifications",
        "email only",
        "email",
        "sms only",
        "sms + email",
        "sms",
    }:
        return "Website Only"
    return "" if allow_empty else DEFAULT_SENSOR_ALERT_MODE


def normalize_irrigation_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in VALID_IRRIGATION_MODES else "automatic"


def normalize_irrigation_frequency(value: object) -> str:
    frequency = str(value or "").strip().lower()
    return frequency if frequency in VALID_IRRIGATION_FREQUENCIES else "daily"


def normalize_bool_flag(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)

    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def normalize_irrigation_duration(*candidates: object) -> int:
    """First candidate that actually carries a number, clamped to the floor.

    The old form was ``int(incoming.get(key) or existing.get(key) or default)``,
    which reads "or" as "was not supplied". It is not: ``""`` and ``"0"`` are
    both falsy, so clearing a field to retype it silently reinstated the stored
    duration and the typed value never landed. Only a missing key or a value
    that is not a number should fall through to the next candidate.
    """
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).strip()
        if not text:
            continue
        try:
            seconds = int(float(text))
        except (TypeError, ValueError):
            continue
        return max(IRRIGATION_MIN_DURATION_SECONDS, seconds)

    return IRRIGATION_MIN_DURATION_SECONDS


def normalize_irrigation_line_map(value: object, fallback_line: object = "") -> dict[str, bool]:
    valid_channels = {str(channel["channel_key"]).strip() for channel in DEFAULT_IRRIGATION_CHANNELS}
    lines: dict[str, bool] = {}
    raw_value = value

    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if stripped.startswith("{"):
            raw_value = parse_json_object(stripped)
        elif stripped in valid_channels:
            raw_value = {stripped: True}

    if isinstance(raw_value, dict):
        for key, is_active in raw_value.items():
            channel_key = str(key).strip()
            if channel_key in valid_channels and normalize_bool_flag(is_active, default=False):
                lines[channel_key] = True

    fallback = str(fallback_line or "").strip()
    if fallback in valid_channels:
        lines[fallback] = True

    return lines


def first_active_irrigation_line(lines: dict[str, bool]) -> str:
    for channel in DEFAULT_IRRIGATION_CHANNELS:
        channel_key = str(channel["channel_key"]).strip()
        if lines.get(channel_key):
            return channel_key
    return ""


def normalize_irrigation_row_map(value: object) -> dict[str, bool]:
    rows: dict[str, bool] = {}
    raw_value = value
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if stripped.startswith("{"):
            raw_value = parse_json_object(stripped)
        elif stripped in VALID_CULTIVATION_ROWS:
            raw_value = {stripped: True}
    if isinstance(raw_value, (list, tuple, set)):
        raw_value = {str(item).strip(): True for item in raw_value}
    if isinstance(raw_value, dict):
        for key, is_selected in raw_value.items():
            row_key = str(key).strip().lower()
            if row_key in VALID_CULTIVATION_ROWS and normalize_bool_flag(is_selected, default=False):
                rows[row_key] = True
    return rows


def normalize_irrigation_channel_row_map(value: object) -> dict[str, dict[str, bool]]:
    valid_channels = {str(channel["channel_key"]).strip() for channel in DEFAULT_IRRIGATION_CHANNELS}
    raw_value = parse_json_object(value) if isinstance(value, str) else value
    if not isinstance(raw_value, dict):
        return {}
    return {
        str(channel_key).strip(): normalized_rows
        for channel_key, rows in raw_value.items()
        if str(channel_key).strip() in valid_channels
        and (normalized_rows := normalize_irrigation_row_map(rows))
    }


def normalize_irrigation_row_mode_map(value: object) -> dict[str, str]:
    raw_value = parse_json_object(value) if isinstance(value, str) else value
    if not isinstance(raw_value, dict):
        return {}
    return {
        str(row_key).strip().lower(): normalize_irrigation_mode(mode)
        for row_key, mode in raw_value.items()
        if str(row_key).strip().lower() in VALID_CULTIVATION_ROWS
    }


def irrigation_lines_from_row_map(channel_rows: dict[str, dict[str, bool]]) -> dict[str, bool]:
    return {
        str(channel["channel_key"]).strip(): True
        for channel in DEFAULT_IRRIGATION_CHANNELS
        if channel_rows.get(str(channel["channel_key"]).strip())
    }


def relay_irrigation_active_rows(
    irrigation: dict[str, object],
) -> dict[str, set[str]]:
    """Return only relay rows that are valid for their current control mode.

    Manual and schedule commands are user-controlled. Automatic rows are a
    derived backend result based on the latest crop readings and thresholds;
    a stale automatic snapshot must never survive a switch to manual mode.
    """
    active_rows: dict[str, set[str]] = {
        str(channel["channel_key"]): set()
        for channel in DEFAULT_IRRIGATION_CHANNELS
    }
    row_modes = normalize_irrigation_row_mode_map(irrigation.get("rowModes"))
    global_mode = (
        normalize_irrigation_mode(irrigation.get("mode"))
        if "mode" in irrigation
        else ""
    )
    automatic_globally_enabled = normalize_bool_flag(
        irrigation.get("autoEnabled"),
        default=True,
    )
    incoming_row_channels = (
        irrigation.get("rowChannels")
        if isinstance(irrigation.get("rowChannels"), dict)
        else {}
    )

    def automatic_channel_enabled(row_key: str, channel_key: str) -> bool:
        row_settings = incoming_row_channels.get(row_key)
        if isinstance(row_settings, dict):
            channel_settings = row_settings.get(channel_key)
            if isinstance(channel_settings, dict) and "automaticEnabled" in channel_settings:
                return normalize_bool_flag(channel_settings.get("automaticEnabled"), default=True)
        rows_payload = irrigation.get("rows")
        for row in rows_payload if isinstance(rows_payload, list) else []:
            if not isinstance(row, dict) or str(row.get("key") or "").strip().lower() != row_key:
                continue
            row_channel_settings = row.get("channels")
            channel_settings = (
                row_channel_settings.get(channel_key)
                if isinstance(row_channel_settings, dict)
                else None
            )
            if isinstance(channel_settings, dict) and "automaticEnabled" in channel_settings:
                return normalize_bool_flag(channel_settings.get("automaticEnabled"), default=True)
        return True

    mode_sources = (
        ("activeManualRows", "manual"),
        ("activeScheduleRows", "schedule"),
        ("activeAutomaticRows", "automatic"),
    )
    for state_key, expected_mode in mode_sources:
        if expected_mode == "automatic" and not automatic_globally_enabled:
            continue
        for channel_key, rows in normalize_irrigation_channel_row_map(
            irrigation.get(state_key)
        ).items():
            for row_key in rows:
                configured_mode = row_modes.get(row_key) or global_mode
                if configured_mode and configured_mode != expected_mode:
                    continue
                if (
                    expected_mode == "automatic"
                    and not automatic_channel_enabled(row_key, channel_key)
                ):
                    continue
                active_rows.setdefault(channel_key, set()).add(row_key)
    return active_rows


def refresh_relay_output_hold(output: dict[str, object], now_ms: int) -> None:
    """Set holdMs from holdUntilMs, and switch off an output whose time is up.

    holdMs is what travels to the board as "ON:<ms>", and it has to be true at
    the moment it is sent -- not when the snapshot was built, which may be many
    seconds earlier. A timed output past its deadline is off: the board has
    already closed that valve on its own clock, and a snapshot still saying ON
    reopened it untimed the next time the bridge sent its heartbeat, then kept
    it open until the backend's own expiry got through.
    """
    deadline_ms = output.get("holdUntilMs")
    if isinstance(deadline_ms, bool) or not isinstance(deadline_ms, (int, float)):
        output.pop("holdMs", None)
        return
    remaining_ms = int(deadline_ms) - int(now_ms)
    if output.get("on") is True and remaining_ms > 0:
        output["holdMs"] = remaining_ms
        return
    output["on"] = False
    output.pop("holdMs", None)
    output.pop("holdUntilMs", None)


def refresh_relay_hold_times(desired: dict[str, object]) -> dict[str, object]:
    """Bring every timed output in a relay snapshot up to the current time."""
    now_ms = epoch_ms(utc_now())
    nodes = desired.get("nodes")
    if isinstance(nodes, dict):
        for node in nodes.values():
            outputs = node.get("outputs") if isinstance(node, dict) else None
            for output in outputs if isinstance(outputs, list) else []:
                if isinstance(output, dict):
                    refresh_relay_output_hold(output, now_ms)
    return desired


def misting_rows_all_low(irrigation: dict[str, object]) -> bool:
    """True when every planted row's soil moisture is below its minimum.

    The condition the farm chose for the mist in Automatic (2026-10-07). The
    misting line is one line over every row, so opening it for one dry row
    wets the rows that did not need it; it goes with the water only when all
    of them are low. Low is the row payload's own `needs` -- below the crop's
    minimum -- not the critical margin Automatic irrigation starts at.

    Read from the rows already in the irrigation payload, so it is judged on
    the same readings as the water run it accompanies. A row with nothing
    planted is not counted, and neither is one whose moisture sensor is off,
    stale or missing: a dead probe would otherwise keep the mist shut for
    good. With no row left to judge there is no mist.
    """
    rows = irrigation.get("rows")
    judged = 0
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("active"):
            continue
        available = row.get("sensorAvailable")
        if not isinstance(available, dict) or not available.get(MISTING_FOLLOWS_CHANNEL_KEY):
            continue
        needs = row.get("needs")
        if not isinstance(needs, dict) or not needs.get(MISTING_FOLLOWS_CHANNEL_KEY):
            return False
        judged += 1
    return judged > 0


def build_relay_desired_state(
    irrigation: dict[str, object],
    actuator_modes: dict[str, object] | None = None,
    actuator_auto_states: dict[str, object] | None = None,
    sensor_power: dict[str, object] | None = None,
    mist_latch: dict[str, object] | None = None,
) -> dict[str, object]:
    """Translate website irrigation runs into physical Raspberry Pi relay commands.

    mist_latch, when given, is where the mist's verdict for the water run in
    progress is kept between calls (RELAY_MIST_WITH_WATER_LATCH for the cached
    snapshot). Without it the verdict is taken afresh on every call.
    """
    active_rows = relay_irrigation_active_rows(irrigation)
    # When each timed run ends. build_irrigation_payload puts this in the
    # payload so the command can carry the remaining time to the board, which
    # then closes the valve on its own clock rather than waiting for a second
    # command to cross the network.
    #
    # The wall-clock deadline is what is kept, and the remaining time is worked
    # out from it here and again each time the bridge reads the snapshot
    # (refresh_relay_hold_times). This state is rebuilt from a cached payload
    # whenever a fan, lamp or sensor switch changes, and a remaining time
    # copied from that cache handed a half-finished run its whole duration
    # again. A payload without the wall-clock map (an older caller) still
    # works: its remaining times are taken as counting from now.
    now_ms = epoch_ms(utc_now())

    def deadline_map(absolute_key: str, relative_key: str) -> dict[str, object]:
        absolute = irrigation.get(absolute_key)
        if isinstance(absolute, dict):
            return {"absolute": absolute}
        relative = irrigation.get(relative_key)
        return {"relative": relative if isinstance(relative, dict) else {}}

    def as_deadline(value: object, *, absolute: bool) -> int | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if absolute:
            return int(value)
        return now_ms + int(value) if value > 0 else None

    run_deadlines: dict[str, dict[str, int]] = {}
    source = deadline_map("runDeadlinesAtMs", "runDeadlinesMs")
    for kind, channels in source.items():
        if not isinstance(channels, dict):
            continue
        for channel, rows in channels.items():
            if not isinstance(rows, dict):
                continue
            for row, value in rows.items():
                deadline = as_deadline(value, absolute=kind == "absolute")
                if deadline is not None:
                    run_deadlines.setdefault(str(channel), {})[str(row)] = deadline
    # Same thing for an actuator that is on a timer -- misting is the only one.
    actuator_deadlines: dict[str, int] = {}
    source = deadline_map("actuatorDeadlinesAtMs", "actuatorDeadlinesMs")
    for kind, keys in source.items():
        if not isinstance(keys, dict):
            continue
        for key, value in keys.items():
            deadline = as_deadline(value, absolute=kind == "absolute")
            if deadline is not None:
                actuator_deadlines[str(key)] = deadline

    # The misting line in Automatic follows the water line (asked for from the
    # farm, 2026-10-05; made a mode of its own on 2026-10-07): whenever any
    # row's water valve is open -- manual, scheduled or automatic -- the mist
    # is open too, and it closes with the last of them. With the mist switched
    # Off the water runs without it, and an On is the card's own timed run,
    # which the water neither starts, lengthens nor cuts short. It is decided
    # here, in the same snapshot as the valves, so both
    # commands leave in one publish and carry the same deadline; the boards
    # then close them on their own clocks at the same moment.
    #
    # A water row past its deadline is already closed on its board, so it does
    # not hold the mist open. A water row with no deadline (Automatic has no
    # timer) leaves the mist untimed as well: it stays on until the snapshot
    # that closes the valve closes it too.
    water_running = False
    water_untimed = False
    water_deadline_ms = 0
    for water_row in active_rows.get(MISTING_FOLLOWS_CHANNEL_KEY, set()):
        row_deadline = run_deadlines.get(MISTING_FOLLOWS_CHANNEL_KEY, {}).get(water_row)
        if not row_deadline:
            water_running = True
            water_untimed = True
        elif int(row_deadline) > now_ms:
            water_running = True
            water_deadline_ms = max(water_deadline_ms, int(row_deadline))

    # Whether this water run takes the mist with it: only when every planted
    # row is low (misting_rows_all_low). The verdict is taken once, on the
    # first snapshot of a water run, and held until the water stops. Judged
    # again on every snapshot, the row being watered would cross its minimum
    # mid-run and a reading hovering at the line would click the relay open
    # and shut; held, the mist either runs the whole water run or none of it.
    mist_with_water = False
    if water_running:
        held = mist_latch.get("verdict") if mist_latch is not None else None
        held_until = mist_latch.get("untilMs") if mist_latch is not None else None
        # A timed run whose time is up has ended, whether or not a snapshot
        # was built in between to see it stop. What runs now is a new one.
        same_run = isinstance(held, bool) and (
            held_until is None or now_ms <= int(held_until)
        )
        mist_with_water = held if same_run else misting_rows_all_low(irrigation)
        if mist_latch is not None:
            mist_latch["verdict"] = mist_with_water
            mist_latch["untilMs"] = None if water_untimed else water_deadline_ms
    elif mist_latch is not None:
        mist_latch.clear()

    nodes: dict[str, dict[str, object]] = {}
    for connection in RELAY_HARDWARE_LAYOUT:
        node_id = str(connection["node_id"])
        channel_key = str(connection["channel_key"])
        row_key = str(connection["row_key"])
        actuator_key = str(connection.get("actuator_key") or "")
        follows_water = False
        if actuator_key:
            actuator_mode = normalize_actuator_mode(
                (actuator_modes or {}).get(actuator_key), actuator_key
            )
            is_on = actuator_mode == "on" or (
                actuator_mode == "automatic"
                # A rule's verdict counts only for an actuator that has a
                # rule. Misting in Automatic answers to the water line alone.
                and actuator_key in AUTOMATIC_ACTUATOR_KEYS
                and normalize_bool_flag((actuator_auto_states or {}).get(actuator_key))
            )
            follows_water = (
                actuator_key == "misting"
                and actuator_mode == "automatic"
                and water_running
                and mist_with_water
            )
            is_on = is_on or follows_water
        else:
            is_on = bool(
                channel_key
                and row_key
                and row_key in active_rows.get(channel_key, set())
            )
        node = nodes.setdefault(node_id, {"nodeId": node_id, "outputs": []})
        outputs = node["outputs"]
        assert isinstance(outputs, list)
        output: dict[str, object] = {
            "moduleId": str(connection["module_id"]),
            "input": int(connection["input"]),
            "label": str(connection["label"]),
            "on": is_on,
        }
        # Only an irrigation row carries a duration. An actuator (fan, lamp,
        # mist) is on until a person or a rule says otherwise, and giving it a
        # deadline would switch it off behind their back.
        if is_on and not actuator_key:
            deadline_ms = run_deadlines.get(channel_key, {}).get(row_key)
            if deadline_ms:
                output["holdUntilMs"] = int(deadline_ms)
        elif is_on and actuator_key:
            # An actuator with a timed run gets the same treatment. Misting is
            # the one that has one: a duration entered on the card arms
            # MISTING_DEADLINE_STATE_KEY, and until now the close travelled
            # back through the environment worker and this bridge, so a short
            # mist overran for exactly the reason a short irrigation run did.
            #
            # An actuator with no deadline still gets a bare ON and stays on
            # until a person or a rule says otherwise.
            deadline_ms = actuator_deadlines.get(actuator_key)
            if follows_water:
                # Open for exactly as long as the water is. A deadline left
                # over from an earlier press of the card is not this run's.
                deadline_ms = None if water_untimed else water_deadline_ms
            if deadline_ms:
                output["holdUntilMs"] = int(deadline_ms)
        refresh_relay_output_hold(output, now_ms)
        outputs.append(output)

    power = sensor_power or {}

    def sensor_is_on(sensor_key: str) -> bool:
        return normalize_sensor_power_state(power.get(sensor_key)) == "on"

    # ESP32 #3 is gone, and row 3's sensors were split across the boards that
    # had pins free rather than moved to one of them. A board has only three
    # spare ADC1 channels once its own row is wired -- ADC2 is unusable while
    # Wi-Fi is up -- so row 3's three capacitive probes could not land anywhere
    # as a set: probe a is on #1, b on #2, c on #4. The RS485 probe could not be
    # split at all, being one Modbus slave on one pair, so it went to #2 whole.
    #
    # row3-moisture therefore appears under three nodes. That is what makes the
    # website's per-row sensor switch work: coms_mqtt.py publishes
    # icucrops/devices/<node>/sensors/<key>/set once per (node, sensor) pair
    # here, and all three boards have to be told before row 3 actually stops
    # reading. Dropping any one of them leaves a probe publishing after the
    # switch is off, and the Pi still averages it into the row.
    #
    # The readings themselves need no mapping: each probe publishes its own
    # component key (row3-moisture-a/b/c) and coms_mqtt.py reassembles the row
    # by row key, not by node.
    sensor_layout = {
        "soil-node-1": (
            ("row1-moisture", "soil"),
            ("row1-rs485", "rs485"),
            ("row3-moisture", "soil"),
        ),
        "soil-node-2": (
            ("row2-moisture", "soil"),
            ("row2-rs485", "rs485"),
            ("row3-moisture", "soil"),
            ("row3-rs485", "rs485"),
        ),
        "soil-node-4": (
            ("row4-moisture", "soil"),
            ("row4-rs485", "rs485"),
            ("row3-moisture", "soil"),
        ),
        # Both shared greenhouse sensors live on ESP32 #5, which drives no
        # relays and polls no slow bus -- the two things that made the DHT22
        # unreliable on #4 and then on #3.
        "soil-node-5": (("dht22", "dht22"), ("light-level", "light")),
    }
    for node_id, sensors in sensor_layout.items():
        node = nodes.setdefault(node_id, {"nodeId": node_id, "outputs": []})
        node_sensors: list[dict[str, object]] = []
        for sensor_key, sensor_type in sensors:
            if sensor_type == "soil":
                is_on = sensor_is_on("moisture") and sensor_is_on(sensor_key)
            elif sensor_type == "rs485":
                is_on = sensor_is_on(sensor_key) and (
                    sensor_is_on("ec") or sensor_is_on("ph")
                )
            else:
                # dht22 and light-level are each their own switch. This used to
                # read sensor_is_on("dht22") for everything that was not soil
                # or RS485, which was correct only while the DHT22 was the sole
                # entry here -- adding the light sensor to that branch would
                # have made the lamp's light input follow the DHT22's switch.
                is_on = sensor_is_on(sensor_key)
            node_sensors.append({"key": sensor_key, "type": sensor_type, "on": is_on})
        node["sensors"] = node_sensors

    return {
        "generatedAt": utc_now_iso(),
        "commandTimeoutSeconds": 30,
        "nodes": nodes,
    }


def cache_relay_desired_state(irrigation: dict[str, object]) -> dict[str, object]:
    global RELAY_DESIRED_STATE_CACHE, RELAY_IRRIGATION_STATE_CACHE
    with RELAY_DESIRED_STATE_LOCK:
        RELAY_IRRIGATION_STATE_CACHE = json.loads(
            json.dumps(irrigation, separators=(",", ":"))
        )
        desired = build_relay_desired_state(
            RELAY_IRRIGATION_STATE_CACHE,
            RELAY_ACTUATOR_MODE_CACHE,
            RELAY_ACTUATOR_AUTO_CACHE,
            RELAY_SENSOR_POWER_CACHE,
            RELAY_MIST_WITH_WATER_LATCH,
        )
        RELAY_DESIRED_STATE_CACHE = desired
    return desired


def cache_relay_actuator_modes(
    actuator_modes: object,
    *,
    local_command: bool = False,
) -> dict[str, object]:
    global RELAY_DESIRED_STATE_CACHE
    raw_modes = actuator_modes if isinstance(actuator_modes, dict) else {}
    with RELAY_DESIRED_STATE_LOCK:
        for actuator_key in RELAY_BACKED_ACTUATOR_KEYS:
            if actuator_key in raw_modes:
                incoming_mode = normalize_actuator_mode(raw_modes[actuator_key], actuator_key)
                if local_command:
                    RELAY_ACTUATOR_PENDING_MODE_CACHE[actuator_key] = incoming_mode
                else:
                    pending_mode = RELAY_ACTUATOR_PENDING_MODE_CACHE.get(actuator_key)
                    if pending_mode and incoming_mode != pending_mode:
                        # Ignore a stale periodic refresh until persistence can
                        # observe and acknowledge the local command.
                        continue
                    if pending_mode == incoming_mode:
                        RELAY_ACTUATOR_PENDING_MODE_CACHE.pop(actuator_key, None)
                RELAY_ACTUATOR_MODE_CACHE[actuator_key] = incoming_mode
        desired = build_relay_desired_state(
            RELAY_IRRIGATION_STATE_CACHE,
            RELAY_ACTUATOR_MODE_CACHE,
            RELAY_ACTUATOR_AUTO_CACHE,
            RELAY_SENSOR_POWER_CACHE,
            RELAY_MIST_WITH_WATER_LATCH,
        )
        RELAY_DESIRED_STATE_CACHE = desired
    return desired


def cache_relay_automatic_states(auto_states: object) -> dict[str, object]:
    global RELAY_DESIRED_STATE_CACHE
    raw_states = auto_states if isinstance(auto_states, dict) else {}
    with RELAY_DESIRED_STATE_LOCK:
        # Only the keys a sensor rule decides. Misting has a relay but no such
        # rule, so it never appears here: its Automatic follows the water line,
        # which build_relay_desired_state reads straight from the snapshot.
        for actuator_key in AUTOMATIC_ACTUATOR_KEYS:
            if actuator_key in raw_states:
                RELAY_ACTUATOR_AUTO_CACHE[actuator_key] = normalize_bool_flag(
                    raw_states[actuator_key]
                )
        desired = build_relay_desired_state(
            RELAY_IRRIGATION_STATE_CACHE,
            RELAY_ACTUATOR_MODE_CACHE,
            RELAY_ACTUATOR_AUTO_CACHE,
            RELAY_SENSOR_POWER_CACHE,
            RELAY_MIST_WITH_WATER_LATCH,
        )
        RELAY_DESIRED_STATE_CACHE = desired
    return desired


def cache_relay_sensor_power(
    sensor_power: object,
    *,
    local_command: bool = False,
) -> dict[str, object]:
    global RELAY_DESIRED_STATE_CACHE
    raw_power = sensor_power if isinstance(sensor_power, dict) else {}
    with RELAY_DESIRED_STATE_LOCK:
        for sensor_key, power_state in raw_power.items():
            normalized_key = normalize_sensor_key(sensor_key)
            if normalized_key in RELAY_SENSOR_POWER_CACHE:
                incoming_power = normalize_sensor_power_state(power_state)
                if local_command:
                    RELAY_SENSOR_PENDING_POWER_CACHE[normalized_key] = incoming_power
                else:
                    pending_power = RELAY_SENSOR_PENDING_POWER_CACHE.get(normalized_key)
                    if pending_power and incoming_power != pending_power:
                        continue
                    if pending_power == incoming_power:
                        RELAY_SENSOR_PENDING_POWER_CACHE.pop(normalized_key, None)
                RELAY_SENSOR_POWER_CACHE[normalized_key] = incoming_power
        desired = build_relay_desired_state(
            RELAY_IRRIGATION_STATE_CACHE,
            RELAY_ACTUATOR_MODE_CACHE,
            RELAY_ACTUATOR_AUTO_CACHE,
            RELAY_SENSOR_POWER_CACHE,
            RELAY_MIST_WITH_WATER_LATCH,
        )
        RELAY_DESIRED_STATE_CACHE = desired
    return desired


def cache_relay_control_request(
    payload: dict[str, object],
    *,
    pressed_at: datetime | None = None,
) -> dict[str, object] | None:
    """Apply a validated hardware-facing sensor/actuator command immediately.

    A misting press also sets the line's deadline in the cached snapshot, as
    update_sensor_control is about to store it: pressed_at plus the duration,
    or none at all. Left alone, the cache still held the previous run's
    deadline, which is already past -- so a new press read as off until the
    next control pass refreshed it.
    """
    control_type = str(payload.get("controlType") or "").strip()
    control_key = normalize_sensor_key(payload.get("key"))
    if misting_on_without_duration(payload):
        return None  # refused: never cache an untimed mist as on
    if control_type == "actuatorMode" and control_key in RELAY_BACKED_ACTUATOR_KEYS:
        if control_key == "misting" and pressed_at is not None:
            mode = normalize_actuator_mode(payload.get("value"), control_key)
            duration_seconds = normalize_misting_duration(payload.get("durationSeconds"))
            with RELAY_DESIRED_STATE_LOCK:
                deadlines = RELAY_IRRIGATION_STATE_CACHE.get("actuatorDeadlinesAtMs")
                deadlines = dict(deadlines) if isinstance(deadlines, dict) else {}
                if mode == "on" and duration_seconds:
                    deadlines["misting"] = epoch_ms(
                        pressed_at + timedelta(seconds=int(duration_seconds))
                    )
                else:
                    deadlines.pop("misting", None)
                RELAY_IRRIGATION_STATE_CACHE["actuatorDeadlinesAtMs"] = deadlines
        return cache_relay_actuator_modes(
            {control_key: normalize_actuator_mode(payload.get("value"), control_key)},
            local_command=True,
        )
    if control_type in {"sensorPower", "rowSensorPower"} and control_key in RELAY_SENSOR_POWER_CACHE:
        return cache_relay_sensor_power(
            {control_key: normalize_sensor_power_state(payload.get("value"))},
            local_command=True,
        )
    return None


def trigger_local_relay_publish() -> bool:
    """Wake the local MQTT bridge without putting cloud I/O in the control path."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as trigger_socket:
            trigger_socket.sendto(b"publish", (RELAY_TRIGGER_HOST, RELAY_TRIGGER_PORT))
        return True
    except OSError:
        # The bridge still has a periodic poll as a fail-safe during restarts.
        return False


def cache_and_trigger_relay_publish(irrigation: dict[str, object]) -> dict[str, object]:
    """Replace the relay snapshot, then wake MQTT for that exact final state.

    A request can optimistically clear or start a manual line before SQLite is
    touched, but Automatic is derived from the row's live sensor value and crop
    parameters during reconciliation.  Waking only for the optimistic snapshot
    leaves that final Automatic result waiting for the bridge's fallback poll.
    """
    desired = cache_relay_desired_state(irrigation)
    trigger_local_relay_publish()
    return desired


def provisional_manual_duration_seconds(
    irrigation: dict[str, object],
    payload: dict[str, object],
    channel_key: str,
    row_key: str,
) -> int:
    """The manual duration update_irrigation_state will give this row's run.

    Read in the same order it reads them -- the row's own setting, then the
    channel's, then the channel default -- with the request's values ahead of
    the cached ones, because the request is what is about to be stored.
    """

    def row_setting(source: object) -> object:
        if not isinstance(source, dict):
            return None
        row_channels = source.get(row_key)
        channel = row_channels.get(channel_key) if isinstance(row_channels, dict) else None
        return channel.get("manualDuration") if isinstance(channel, dict) else None

    def channel_setting(source: object) -> object:
        channel = source.get(channel_key) if isinstance(source, dict) else None
        return channel.get("manualDuration") if isinstance(channel, dict) else None

    cached_row_channels: dict[str, object] = {}
    for row in irrigation.get("rows") if isinstance(irrigation.get("rows"), list) else []:
        if isinstance(row, dict) and str(row.get("key") or "").strip().lower() == row_key:
            cached_row_channels = {row_key: row.get("channels")}
            break
    default_seconds = next(
        (
            channel["manual_duration_seconds"]
            for channel in DEFAULT_IRRIGATION_CHANNELS
            if str(channel["channel_key"]).strip() == channel_key
        ),
        None,
    )
    return normalize_irrigation_duration(
        row_setting(payload.get("rowChannels")),
        row_setting(cached_row_channels),
        channel_setting(payload.get("channels")),
        channel_setting(irrigation.get("channels")),
        default_seconds,
    )


def cache_relay_irrigation_request(
    payload: dict[str, object],
    *,
    pressed_at: datetime | None = None,
) -> dict[str, object]:
    """Merge user-controlled irrigation fields into the local MQTT snapshot.

    Automatic and schedule run maps are deliberately excluded because both are
    derived by the backend. Trusting the browser's previous snapshot can leave
    a pump on after a mode change, or turn every scheduled solution on while a
    user is only arming its future start time.

    With pressed_at, a manual line this request starts is given its deadline
    here too -- pressed_at plus its duration, the same instant the stored run
    will end, because update_irrigation_state opens that run at pressed_at.
    This snapshot is published before the database is touched, and without a
    deadline it went to the board as a bare ON: the run then ended only when a
    second command got through, and any stall in between was extra watering.
    """
    with RELAY_DESIRED_STATE_LOCK:
        irrigation = json_safe_copy(RELAY_IRRIGATION_STATE_CACHE)
    previous_manual_rows = normalize_irrigation_channel_row_map(
        irrigation.get("activeManualRows")
    )
    # A line whose deadline has passed is over, whether or not the control
    # worker has written that down yet; the board has already closed it.
    cached_deadlines = irrigation.get("runDeadlinesAtMs")
    cached_deadlines = cached_deadlines if isinstance(cached_deadlines, dict) else {}
    checked_ms = epoch_ms(pressed_at or utc_now())
    for channel_key in list(previous_manual_rows):
        channel_deadlines = cached_deadlines.get(channel_key)
        channel_deadlines = channel_deadlines if isinstance(channel_deadlines, dict) else {}
        for row_key in list(previous_manual_rows[channel_key]):
            deadline_ms = channel_deadlines.get(row_key)
            if (
                isinstance(deadline_ms, (int, float))
                and not isinstance(deadline_ms, bool)
                and int(deadline_ms) <= checked_ms
            ):
                previous_manual_rows[channel_key].pop(row_key, None)
        if not previous_manual_rows[channel_key]:
            previous_manual_rows.pop(channel_key, None)
    manual_line_changes = normalize_manual_line_changes(payload.get("manualLineChanges"))
    scope_rows: set[str] | None = None
    if isinstance(payload.get("scopeRows"), list):
        scope_rows = {
            str(row_key).strip() for row_key in payload["scopeRows"] if str(row_key).strip()
        }
    for state_key in (
        "activeManualRows",
        "activeManualLines",
        "targetRows",
        "scheduleArmedRows",
        "rowModes",
        "rowChannels",
        "channels",
        "mode",
        "autoEnabled",
    ):
        if manual_line_changes is not None and state_key in {
            "activeManualRows",
            "activeManualLines",
        }:
            # Only the pressed lines move; the sender's copy of the rest can
            # hold a run that has already ended, and taking it here switched
            # that valve back on for its whole duration.
            continue
        if state_key not in payload:
            continue
        incoming = json_safe_copy(payload.get(state_key))
        if scope_rows is not None and state_key == "activeManualRows":
            # A scoped press speaks only for its own rows, the same rule
            # update_irrigation_state applies. The sender's copy of the other
            # rows can be seconds old, and taking it here switched their valves
            # for the moment before the stored state corrected it.
            incoming = merge_scoped_channel_rows(
                previous_manual_rows,
                normalize_irrigation_channel_row_map(incoming),
                scope_rows,
            )
        elif scope_rows is not None and state_key in {"rowModes", "rowChannels"}:
            # The page sends these for the pressed rows only. Replacing the
            # cached map with them dropped every other row's mode, which then
            # fell back to the global one for this publish.
            merged = irrigation.get(state_key)
            merged = dict(merged) if isinstance(merged, dict) else {}
            if isinstance(incoming, dict):
                merged.update(incoming)
            incoming = merged
        irrigation[state_key] = incoming

    if manual_line_changes is not None:
        pressed_rows = apply_manual_line_changes(previous_manual_rows, manual_line_changes)
        irrigation["activeManualRows"] = pressed_rows
        irrigation["activeManualLines"] = irrigation_lines_from_row_map(pressed_rows)

    if pressed_at is not None:
        deadlines = irrigation.get("runDeadlinesAtMs")
        deadlines = json_safe_copy(deadlines) if isinstance(deadlines, dict) else {}
        started_ms = epoch_ms(pressed_at)
        for channel_key, rows in normalize_irrigation_channel_row_map(
            irrigation.get("activeManualRows")
        ).items():
            for row_key in rows:
                if row_key in previous_manual_rows.get(channel_key, {}):
                    # Already running: it keeps the deadline it was given.
                    continue
                seconds = provisional_manual_duration_seconds(
                    irrigation, payload, channel_key, row_key
                )
                channel_deadlines = deadlines.get(channel_key)
                if not isinstance(channel_deadlines, dict):
                    channel_deadlines = {}
                    deadlines[channel_key] = channel_deadlines
                channel_deadlines[row_key] = started_ms + seconds * 1000
        irrigation["runDeadlinesAtMs"] = deadlines
    return cache_relay_desired_state(irrigation)


def cached_relay_desired_state() -> dict[str, object] | None:
    with RELAY_DESIRED_STATE_LOCK:
        if RELAY_DESIRED_STATE_CACHE is None:
            return None
        desired = json.loads(json.dumps(RELAY_DESIRED_STATE_CACHE, separators=(",", ":")))
    # Worked out at the moment the bridge reads it, so the "ON:<ms>" it sends
    # is the time actually left, and a run whose time is up reads as off even
    # if the control worker has not got round to expiring it yet.
    return refresh_relay_hold_times(desired)


def active_cultivation_row_map(cultivations: list[sqlite3.Row] | list[dict[str, object]]) -> dict[str, object]:
    return {
        str(cultivation["row_key"]).strip().lower(): cultivation
        for cultivation in cultivations
        if str(cultivation["row_key"]).strip().lower() in VALID_CULTIVATION_ROWS
    }


def filter_active_irrigation_rows(
    rows: object,
    cultivations: list[sqlite3.Row] | list[dict[str, object]],
) -> dict[str, bool]:
    active_rows = active_cultivation_row_map(cultivations)
    return {
        row_key: True
        for row_key in normalize_irrigation_row_map(rows)
        if row_key in active_rows
    }


def filter_active_irrigation_channel_rows(
    channel_rows: object,
    cultivations: list[sqlite3.Row] | list[dict[str, object]],
) -> dict[str, dict[str, bool]]:
    return {
        channel_key: filtered_rows
        for channel_key, rows in normalize_irrigation_channel_row_map(channel_rows).items()
        if (filtered_rows := filter_active_irrigation_rows(rows, cultivations))
    }


def irrigation_payload_without_row(payload: dict[str, object], row_key: str) -> dict[str, object]:
    normalized_row = str(row_key or "").strip().lower()
    target_rows = normalize_irrigation_row_map(payload.get("targetRows"))
    target_rows.pop(normalized_row, None)
    schedule_armed_rows = normalize_irrigation_row_map(payload.get("scheduleArmedRows"))
    schedule_armed_rows.pop(normalized_row, None)
    cleaned: dict[str, object] = {
        "targetRows": target_rows,
        "scheduleArmedRows": schedule_armed_rows,
    }
    field_pairs = (
        ("activeManualRows", "activeManualLines"),
        ("activeScheduleRows", "activeScheduleLines"),
        ("activeAutomaticRows", "activeAutomaticLines"),
    )
    for row_field, line_field in field_pairs:
        channel_rows = normalize_irrigation_channel_row_map(payload.get(row_field))
        for channel_key in list(channel_rows):
            channel_rows[channel_key].pop(normalized_row, None)
            if not channel_rows[channel_key]:
                del channel_rows[channel_key]
        cleaned[row_field] = channel_rows
        cleaned[line_field] = irrigation_lines_from_row_map(channel_rows)
    cleaned["activeManualLine"] = first_active_irrigation_line(cleaned["activeManualLines"])
    return cleaned


# Current account creation flow only accepts Gmail addresses, so validation stays strict.
def is_valid_gmail_address(email: str) -> bool:
    local_part, separator, domain = email.partition("@")
    if separator != "@":
        return False
    if not local_part or not domain:
        return False
    if domain != "gmail.com":
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._%+-")
    return all(character in allowed for character in local_part)


def mask_email(email: str) -> str:
    local_part, separator, domain = email.partition("@")
    if separator != "@":
        return email

    if len(local_part) <= 2:
        masked_local = f"{local_part[:1]}*"
    else:
        masked_local = f"{local_part[:2]}{'*' * max(2, len(local_part) - 2)}"

    return f"{masked_local}@{domain}"


def apply_sqlite_concurrency_pragmas(connection: sqlite3.Connection) -> None:
    """Let the web app, the MQTT bridge and the sync daemon share one file.

    Three processes hold this database open on the Pi. In SQLite's default
    rollback-journal mode a single writer blocks every reader for the whole
    transaction, so a sync pass pushing thousands of readings made the
    dashboard's own queries fail with "database is locked" -- which the UI
    shows as stale or missing data even though the farm is reporting fine.

    WAL lets readers run while a writer commits, and busy_timeout makes the
    writers queue for a few seconds instead of failing instantly. WAL is a
    property of the file, so setting it once from any connection is enough;
    it is re-asserted here because a restored or migrated database comes back
    in the default mode. On a managed host the file lives on a temp disk that
    may not support WAL, so a refusal is not fatal.
    """
    # busy_timeout is set first on purpose: changing journal_mode needs a
    # moment with no other writer, and without the timeout the switch fails
    # instantly on a busy Pi and the file stays in rollback-journal mode.
    try:
        connection.execute("PRAGMA busy_timeout = 10000")
    except sqlite3.Error:
        return
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        # Bound the WAL: the default autocheckpoint waits for a moment
        # with no reader, and this database always has one.
        connection.execute("PRAGMA wal_autocheckpoint = 400")
    except sqlite3.Error:
        pass


def connect_database() -> sqlite3.Connection:
    if postgres_backend_enabled():
        # Imported here rather than at module scope so an installation running
        # on SQLite - the Pi in offline mode - does not need psycopg present.
        import icucrops_pg

        # Shorter than any client deadline on purpose. The browser's own
        # timeout was also 30s, so an unreachable database raced it and the
        # browser almost always won -- the page showed "the server took too
        # long" and never the real reason. Giving up first lets the backend
        # answer with what actually went wrong.
        return icucrops_pg.connect(POSTGRES_URL, timeout=POSTGRES_CONNECT_TIMEOUT_SECONDS)

    # On a managed host the database lives in a temporary directory that is
    # wiped between cold starts, so the folder itself may be gone. SQLite will
    # not create a file inside a missing directory - it raises "unable to open
    # database file", which surfaces as a bare 500 on every request that reads
    # or writes anything at all.
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    apply_sqlite_concurrency_pragmas(connection)
    return connection


def hash_secret(secret: str, salt: str, *, iterations: int) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return derived.hex()


def create_secret_hash(secret: str, *, iterations: int) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = hash_secret(secret, salt, iterations=iterations)
    return salt, digest


def verify_secret(secret: str, *, salt: str, digest: str, iterations: int) -> bool:
    candidate = hash_secret(secret, salt, iterations=iterations)
    return hmac.compare_digest(candidate, digest)


_TIMING_EQUALIZER_HASH: tuple[str, str] | None = None


def burn_password_verification(iterations: int = PASSWORD_ITERATIONS) -> None:
    """Spend the same work a real password/OTP check costs.

    When an email matches no account the code path is otherwise much shorter
    than a wrong-password path, and the difference is measurable because the
    real path runs a slow PBKDF2. Running an equivalent throwaway hash makes a
    missing account and a wrong password take the same time, so response timing
    cannot be used to tell which emails are registered.
    """
    global _TIMING_EQUALIZER_HASH
    if _TIMING_EQUALIZER_HASH is None:
        _TIMING_EQUALIZER_HASH = create_secret_hash("timing-equalizer", iterations=iterations)
    salt, digest = _TIMING_EQUALIZER_HASH
    verify_secret("timing-equalizer-probe", salt=salt, digest=digest, iterations=iterations)


def ensure_local_database_schema() -> None:
    """Create and migrate the SQLite file. Local only - never touches the network.

    Kept separate from ensure_database() so a managed host can prepare its
    empty disk on start-up without a network round trip in front of the very
    first request of every cold start. On Supabase this is a no-op - the
    schema lives in supabase/migrations/.
    """
    global LOCAL_SCHEMA_READY
    if LOCAL_SCHEMA_READY:
        return

    if postgres_backend_enabled():
        # Supabase owns its schema through supabase/migrations/, and the
        # PRAGMA table_info() migrations below are SQLite-only anyway.
        LOCAL_SCHEMA_READY = True
        return

    with DATABASE_INITIALIZATION_LOCK:
        if LOCAL_SCHEMA_READY:
            return

        PROFILE_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
        with connect_database() as connection:
            # These migrations rewrite whole tables, and on the Pi they run
            # while the sync daemon is writing readings every couple of
            # seconds. The ordinary busy_timeout is tuned for a request and
            # is not enough here: the de-duplicating DELETE below timed out,
            # main.py exited, and the updater read that as a failed release
            # and rolled the whole deploy back. Startup happens once, so it
            # can afford to wait properly for its turn.
            try:
                connection.execute("PRAGMA busy_timeout = 120000")
            except sqlite3.Error:
                pass
            connection.executescript(SCHEMA_SQL)
            ensure_users_profile_schema(connection)
            ensure_admin_login_attempt_schema(connection)
            ensure_notification_delete_schema(connection)
            ensure_sensor_management_schema(connection)
            ensure_sensor_catalog_seed(connection)
            ensure_sensor_backend_seed(connection)
            cleanup_legacy_demo_sensor_data(connection)
            # Before the seed, not after: the seed INSERTs into
            # irrigation_settings by column name, and on a database created
            # before durations became seconds those columns are still the
            # minute ones. Running the seed first fails the whole bootstrap
            # with "no column named automatic_duration_seconds".
            migrate_irrigation_durations_to_seconds(connection)
            ensure_irrigation_backend_seed(connection)
            ensure_irrigation_row_schema(connection)
            cleanup_legacy_sensor_alert_modes(connection)
            ensure_cultivation_outcome_schema(connection)
            cleanup_legacy_demo_users(connection)
            cleanup_stale_login_challenges(connection)
            cleanup_stale_account_creation_challenges(connection)
            cleanup_applied_hardware_command_markers(connection)
        LOCAL_SCHEMA_READY = True


def ensure_database() -> None:
    # Database bootstrapping also performs small compatibility and cleanup tasks on startup.
    global DATABASE_INITIALIZED
    if DATABASE_INITIALIZED:
        return

    with DATABASE_INITIALIZATION_LOCK:
        if DATABASE_INITIALIZED:
            return

    ensure_local_database_schema()

    with DATABASE_INITIALIZATION_LOCK:
        if DATABASE_INITIALIZED:
            return
        # The control loops belong to the Pi, which drives the relays. On a
        # managed host they did harm: a serverless instance is frozen the
        # moment its response is sent, and a loop caught mid-transaction
        # stayed "idle in transaction" on a Supabase pool connection for
        # minutes. A handful of frozen instances used up the whole pool, and
        # every request on the site -- /api/health and every login included --
        # waited out Vercel's 60 seconds. The hosted endpoints reconcile
        # irrigation and the environment inline on every read and write, so
        # nothing there waits on these loops.
        #
        # ICUCROPS_CONTROL_WORKERS=0 is for the test suites only. The loops
        # cannot be stopped once started and follow whatever DATABASE_PATH is
        # current, so in a test process they wrote real alerts into the next
        # suite's database mid-test. Nothing on the Pi sets it.
        if not running_on_managed_host() and control_workers_enabled():
            start_environment_control_worker()
            start_irrigation_control_worker()
        DATABASE_INITIALIZED = True


def control_workers_enabled() -> bool:
    return os.getenv("ICUCROPS_CONTROL_WORKERS", "").strip() != "0"


def ensure_users_profile_schema(connection: sqlite3.Connection) -> None:
    if postgres_backend_enabled():
        # These are SQLite-era ALTER TABLE migrations guarded by PRAGMA
        # table_info. Supabase already has every column from
        # supabase/migrations/, and PRAGMA returns nothing there, so without
        # this the guard reads "column missing" and the ALTER fails.
        return

    columns = {str(row["name"]).strip().lower() for row in connection.execute("PRAGMA table_info(users)").fetchall()}
    if "profile_photo_path" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN profile_photo_path TEXT NOT NULL DEFAULT ''")
    if "profile_photo_mime" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN profile_photo_mime TEXT NOT NULL DEFAULT ''")
    if "profile_photo_data" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN profile_photo_data BLOB")
    if "profile_photo_version" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN profile_photo_version TEXT NOT NULL DEFAULT ''")
    if "preferences" not in columns:
        # Legacy column. Account-level UI preferences (theme, dashboard graph
        # range) are no longer synced -- they are device-local now -- so nothing
        # reads or writes this any more. It is kept only so existing databases
        # keep the column they were created with; dropping it would mean
        # rebuilding the table for no benefit.
        connection.execute("ALTER TABLE users ADD COLUMN preferences TEXT NOT NULL DEFAULT '{}'")
    # Single-session enforcement. Supabase has carried these three since its
    # first migration; the SQLite schema never grew them, so a Pi running
    # standalone had nowhere to record which session is the live one.
    if "active_session_jti" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN active_session_jti TEXT NOT NULL DEFAULT ''")
    if "active_session_client_id" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN active_session_client_id TEXT NOT NULL DEFAULT ''")
    if "active_session_issued_at" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN active_session_issued_at TEXT NOT NULL DEFAULT ''")


def ensure_admin_login_attempt_schema(connection: sqlite3.Connection) -> None:
    """Add admin_login_attempts.user_id, which the failure counter already writes.

    Supabase has had this column since its first migration, but the SQLite
    schema never grew it, so on the one path that uses SQLite -- a Pi running
    standalone, or a managed host's temporary database after a cold start --
    the first wrong password raised "table admin_login_attempts has no column
    named user_id" and the login returned 500 rather than rejecting the
    attempt or locking the account.
    """
    if postgres_backend_enabled():
        return

    columns = {
        str(row["name"]).strip().lower()
        for row in connection.execute("PRAGMA table_info(admin_login_attempts)").fetchall()
    }
    if "user_id" not in columns:
        # No REFERENCES clause: SQLite cannot add a column with one to an
        # existing table. New databases get the constraint from SCHEMA_SQL.
        connection.execute("ALTER TABLE admin_login_attempts ADD COLUMN user_id INTEGER")


def ensure_cultivation_outcome_schema(connection: sqlite3.Connection) -> None:
    """Add cultivation_harvests.outcome to a database that predates it.

    Every row already in the table got there through the harvest path, because
    that was the only path that wrote one -- a removal deleted the cultivation
    and recorded nothing. So the existing rows are harvests, which is exactly
    what the column's DEFAULT says, and no backfill is needed.
    """
    if postgres_backend_enabled():
        return

    columns = {
        str(row["name"]).strip().lower()
        for row in connection.execute("PRAGMA table_info(cultivation_harvests)").fetchall()
    }
    if "outcome" not in columns:
        # No CHECK clause: SQLite cannot add a constrained column to an
        # existing table. New databases get the constraint from SCHEMA_SQL,
        # and normalize_cultivation_outcome guards every write either way.
        connection.execute(
            "ALTER TABLE cultivation_harvests ADD COLUMN outcome TEXT NOT NULL DEFAULT 'harvested'"
        )


def ensure_notification_delete_schema(connection: sqlite3.Connection) -> None:
    """Add notifications.deleted_at, the column that lets a delete travel.

    A row that is simply gone cannot be distinguished from a row that never
    arrived, so a plain DELETE on one device looks identical to "the other
    device has something new" and the sync puts it straight back. Marking the
    row instead leaves something for the sync to carry.
    """
    if postgres_backend_enabled():
        return

    columns = {
        str(row["name"]).strip().lower()
        for row in connection.execute("PRAGMA table_info(notifications)").fetchall()
    }
    if "deleted_at" not in columns:
        connection.execute("ALTER TABLE notifications ADD COLUMN deleted_at TEXT")

    # The sync identifies a notification by these six fields, so two runs
    # overlapping - a timer firing into a manual run - could each decide the
    # other side was missing the row and both insert it. Making the key unique
    # turns the second insert into a no-op rather than a copy.
    connection.execute(
        """
        DELETE FROM notifications WHERE id > (
            SELECT MIN(other.id) FROM notifications AS other
            WHERE other.scope = notifications.scope
              AND other.type = notifications.type
              AND other.message = notifications.message
              AND other.source_type = notifications.source_type
              AND other.source_id = notifications.source_id
              AND other.created_at = notifications.created_at
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS notifications_natural_key
        ON notifications (scope, type, message, source_type, source_id, created_at)
        """
    )


def ensure_sensor_management_schema(connection: sqlite3.Connection) -> None:
    if postgres_backend_enabled():
        # These are SQLite-era ALTER TABLE migrations guarded by PRAGMA
        # table_info. Supabase already has every column from
        # supabase/migrations/, and PRAGMA returns nothing there, so without
        # this the guard reads "column missing" and the ALTER fails.
        return

    table_info = connection.execute("PRAGMA table_info(sensor_registry)").fetchall()
    columns = {str(row["name"]).strip().lower() for row in table_info}
    if "definition_key" not in columns:
        connection.execute("ALTER TABLE sensor_registry ADD COLUMN definition_key TEXT DEFAULT NULL")
    if "backend_key" not in columns:
        connection.execute("ALTER TABLE sensor_registry ADD COLUMN backend_key TEXT NOT NULL DEFAULT ''")

    relax_sensor_registry_definition_key(connection, table_info)

    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_sensor_registry_definition_key ON sensor_registry (definition_key);
        CREATE INDEX IF NOT EXISTS idx_sensor_registry_backend_key ON sensor_registry (backend_key);
        """
    )


def relax_sensor_registry_definition_key(
    connection: sqlite3.Connection,
    table_info: list[sqlite3.Row],
) -> None:
    """SQLite-only: let definition_key be NULL, as Supabase already does.

    ensure_sensor_registry_record() writes `definition_key or None`, because on
    Supabase this is a foreign key and "" references nothing. SQLite had the
    column as NOT NULL, so that NULL raised IntegrityError and every reading
    from a sensor with no matching definition was rejected -- on the Pi, which
    is where SQLite is the authoritative store.

    SQLite cannot drop a NOT NULL with ALTER, so the table is rebuilt. That is
    worth doing once rather than papering over it by writing "" instead: the
    empty string is what Postgres rejected, and making the two stores disagree
    about that again is how this returns.
    """
    for row in table_info:
        if str(row["name"]).strip().lower() != "definition_key":
            continue
        if not int(row["notnull"] or 0):
            return  # Already nullable.
        break
    else:
        return  # No such column; nothing built yet.

    # Empty strings become NULL on the way across: they mean the same thing
    # here ("no definition") and only one of them is a valid foreign key.
    connection.executescript(
        """
        PRAGMA foreign_keys = OFF;

        CREATE TABLE sensor_registry_migrated AS
            SELECT * FROM sensor_registry;

        DROP TABLE sensor_registry;

        CREATE TABLE sensor_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_key TEXT NOT NULL UNIQUE,
            definition_key TEXT DEFAULT NULL,
            backend_key TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL,
            device_name TEXT NOT NULL DEFAULT '',
            row_key TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'sensor',
            power_state TEXT NOT NULL DEFAULT 'on',
            actuator_mode TEXT NOT NULL DEFAULT '',
            alert_mode TEXT NOT NULL DEFAULT '',
            hardware_identifier TEXT NOT NULL DEFAULT '',
            metric_keys_json TEXT NOT NULL DEFAULT '[]',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        INSERT INTO sensor_registry (
            id, sensor_key, definition_key, backend_key, display_name,
            device_name, row_key, category, power_state, actuator_mode,
            alert_mode, hardware_identifier, metric_keys_json, metadata_json,
            created_at, updated_at
        )
        SELECT
            id, sensor_key, NULLIF(definition_key, ''), backend_key,
            display_name, device_name, row_key, category, power_state,
            actuator_mode, alert_mode, hardware_identifier, metric_keys_json,
            metadata_json, created_at, updated_at
        FROM sensor_registry_migrated;

        DROP TABLE sensor_registry_migrated;

        PRAGMA foreign_keys = ON;
        """
    )


def ensure_irrigation_row_schema(connection: sqlite3.Connection) -> None:
    """Bring the per-row irrigation tables up to date for this cultivation set.

    Two jobs that used to be one, and had to be separated: the ALTER TABLE
    migrations are SQLite-era and must not run on Supabase, but the seeding
    below has to run on **both**. Skipping the whole function on Postgres
    meant a cultivation created from the hosted dashboard got no
    irrigation_row_controls row at all -- and update_irrigation_state only
    ever UPDATEs that table, so changing the row's mode in the cloud silently
    did nothing.
    """
    if not postgres_backend_enabled():
        ensure_irrigation_row_columns(connection)
    purge_orphaned_irrigation_row_rows(connection)
    seed_irrigation_rows_for_cultivations(connection)


def purge_orphaned_irrigation_row_rows(connection: sqlite3.Connection) -> None:
    """Clear control rows whose cultivation is already gone.

    Both tables declare ON DELETE CASCADE, so nothing that deletes a
    cultivation through the backend can leave one of these behind. The sync
    tool could: it opened SQLite on its own connection, and SQLite enforces
    foreign keys per connection, off by default. Every cultivation the sync
    deleted on the Pi -- which is every deletion made from the hosted
    dashboard -- therefore left its irrigation_row_controls row in place.

    That orphan is not merely stale. row_key is UNIQUE on
    irrigation_row_controls and (row_key, channel_key) is UNIQUE on
    irrigation_row_settings, so the dead row holds the slot: the INSERT OR
    IGNORE below is ignored for the next planting in that row, which then has
    no control row of its own. update_irrigation_state only ever UPDATEs that
    table, so switching the new cultivation to Schedule or Manual matched zero
    rows and silently snapped back to Automatic.

    Counted before deleting. On Supabase these tables carry AFTER STATEMENT
    notify triggers that fire even when the statement touched nothing, and an
    unconditional DELETE here would wake the sync daemon on every payload
    build.
    """
    orphans = connection.execute(
        """
        SELECT
            (SELECT count(*) FROM irrigation_row_controls
             WHERE cultivation_id NOT IN (SELECT id FROM cultivations))
            + (SELECT count(*) FROM irrigation_row_settings
               WHERE cultivation_id NOT IN (SELECT id FROM cultivations))
        """
    ).fetchone()
    if not orphans or not int(orphans[0] or 0):
        return
    connection.execute(
        "DELETE FROM irrigation_row_controls"
        " WHERE cultivation_id NOT IN (SELECT id FROM cultivations)"
    )
    connection.execute(
        "DELETE FROM irrigation_row_settings"
        " WHERE cultivation_id NOT IN (SELECT id FROM cultivations)"
    )


def ensure_irrigation_row_columns(connection: sqlite3.Connection) -> None:
    """SQLite-only: the columns Supabase already has from its migrations.

    Guarded by PRAGMA table_info, which returns nothing on Postgres -- the
    guard would read "column missing" and the ALTER would fail.
    """
    columns = {
        str(row["name"]).strip().lower()
        for row in connection.execute("PRAGMA table_info(irrigation_settings)").fetchall()
    }
    if "automatic_enabled" not in columns:
        connection.execute("ALTER TABLE irrigation_settings ADD COLUMN automatic_enabled INTEGER NOT NULL DEFAULT 1")
    if "schedule_enabled" not in columns:
        connection.execute("ALTER TABLE irrigation_settings ADD COLUMN schedule_enabled INTEGER NOT NULL DEFAULT 1")

    row_setting_columns = {
        str(row["name"]).strip().lower()
        for row in connection.execute("PRAGMA table_info(irrigation_row_settings)").fetchall()
    }
    row_setting_additions = (
        ("automatic_duration_seconds", "INTEGER NOT NULL DEFAULT 900"),
        ("manual_duration_seconds", "INTEGER NOT NULL DEFAULT 900"),
        ("schedule_start_time", "TEXT NOT NULL DEFAULT '06:00'"),
        ("schedule_duration_seconds", "INTEGER NOT NULL DEFAULT 1200"),
        ("schedule_frequency", "TEXT NOT NULL DEFAULT 'daily'"),
    )
    for column_name, column_definition in row_setting_additions:
        if column_name not in row_setting_columns:
            connection.execute(
                f"ALTER TABLE irrigation_row_settings ADD COLUMN {column_name} {column_definition}"
            )

    migrate_irrigation_durations_to_seconds(connection)


def migrate_irrigation_durations_to_seconds(connection: sqlite3.Connection) -> None:
    """SQLite-only: rename the minute columns to seconds and convert the values.

    Supabase gets this from migration 0005. Here it has to be done by hand,
    and it has to be idempotent: ensure_schema() runs on every start-up, and
    the Pi restarts often.

    The rename is what makes that safe. Once a table has the seconds column it
    has no minutes column left, so the presence of the old name is the whole
    test for whether this still needs doing -- there is no flag to keep in step
    and no way to multiply the same value by 60 twice.

    Guarded by PRAGMA table_info, which returns nothing on Postgres, so this is
    a no-op there rather than a failed ALTER.
    """
    renames = (
        (
            "irrigation_settings",
            (
                ("automatic_duration", "automatic_duration_seconds"),
                ("manual_duration", "manual_duration_seconds"),
                ("schedule_duration", "schedule_duration_seconds"),
            ),
        ),
        (
            "irrigation_row_settings",
            (
                ("automatic_duration", "automatic_duration_seconds"),
                ("manual_duration", "manual_duration_seconds"),
                ("schedule_duration", "schedule_duration_seconds"),
            ),
        ),
        (
            "irrigation_runs",
            (("duration_minutes", "duration_seconds"),),
        ),
    )

    for table, column_pairs in renames:
        existing = {
            str(row["name"]).strip().lower()
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if not existing:
            # Postgres, or a table that does not exist yet. Either way there is
            # nothing here to rename.
            continue

        converted: list[str] = []
        for old_name, new_name in column_pairs:
            if old_name not in existing or new_name in existing:
                continue
            connection.execute(
                f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}"
            )
            converted.append(new_name)

        if converted:
            # Existing values were minutes, so they are multiplied here rather
            # than left to be read as seconds. A saved 20-minute schedule that
            # silently became 20 seconds would be a real change to how much
            # water a row gets, arriving with no sign that anything happened.
            assignments = ", ".join(f"{name} = {name} * 60" for name in converted)
            connection.execute(f"UPDATE {table} SET {assignments}")


def seed_irrigation_rows_for_cultivations(connection: sqlite3.Connection) -> None:
    """Give every cultivation its control row and its per-channel settings.

    INSERT OR IGNORE, so it is safe to call on every cultivation creation and
    on every start-up. icucrops_pg translates that to ON CONFLICT DO NOTHING,
    which is why this one works unchanged against both stores.

    is_enabled is written as the TRUE keyword rather than SQLite's 1. Both
    engines accept TRUE, and PostgreSQL rejects the integer outright --
    `column "is_enabled" is of type boolean but expression is of type
    integer`. icucrops_pg coerces 1/0 for *bound parameters* only, and this is
    a literal inside the SELECT, so nothing was there to catch it: the whole
    statement failed, which took every /api/irrigation call on the hosted
    dashboard down with it and left it showing no active rows while the Pi
    had four.
    """
    timestamp = utc_now_iso()
    legacy_mode_row = connection.execute(
        "SELECT state_value FROM system_state WHERE state_key = 'irrigation.mode'"
    ).fetchone()
    legacy_mode = normalize_irrigation_mode(legacy_mode_row["state_value"] if legacy_mode_row else "automatic")
    connection.execute(
        """
        INSERT OR IGNORE INTO irrigation_row_controls (
            cultivation_id,
            row_key,
            mode,
            is_enabled,
            updated_at
        )
        SELECT id, row_key, ?, TRUE, ?
        FROM cultivations
        """,
        (legacy_mode, timestamp),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO irrigation_row_settings (
            cultivation_id,
            row_key,
            channel_key,
            automatic_enabled,
            automatic_duration_seconds,
            manual_duration_seconds,
            schedule_enabled,
            schedule_start_time,
            schedule_duration_seconds,
            schedule_frequency,
            updated_at
        )
        SELECT
            cultivations.id,
            cultivations.row_key,
            irrigation_settings.channel_key,
            irrigation_settings.automatic_enabled,
            irrigation_settings.automatic_duration_seconds,
            irrigation_settings.manual_duration_seconds,
            irrigation_settings.schedule_enabled,
            irrigation_settings.schedule_start_time,
            irrigation_settings.schedule_duration_seconds,
            irrigation_settings.schedule_frequency,
            ?
        FROM cultivations
        CROSS JOIN irrigation_settings
        """,
        (timestamp,),
    )


def cleanup_legacy_sensor_alert_modes(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT sensor_key, category, alert_mode
        FROM sensor_registry
        """
    ).fetchall()
    for row in rows:
        raw_alert_mode = str(row["alert_mode"] or "").strip()
        allow_empty = str(row["category"] or "").strip().lower() == "actuator" and not raw_alert_mode
        normalized = normalize_sensor_alert_mode(raw_alert_mode, allow_empty=allow_empty)
        if normalized == raw_alert_mode:
            continue
        connection.execute(
            """
            UPDATE sensor_registry
            SET alert_mode = ?, updated_at = ?
            WHERE sensor_key = ?
            """,
            (
                normalized,
                utc_now_iso(),
                str(row["sensor_key"]).strip(),
            ),
        )


def json_dumps_compact(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def ensure_system_state_value(connection: sqlite3.Connection, *, key: str, value: object) -> None:
    connection.execute(
        """
        INSERT INTO system_state (state_key, state_value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(state_key) DO NOTHING
        """,
        (str(key).strip(), str(value), utc_now_iso()),
    )


def ensure_sensor_catalog_seed(connection: sqlite3.Connection) -> None:
    timestamp = utc_now_iso()

    for definition in DEFAULT_SENSOR_DEFINITIONS:
        connection.execute(
            """
            INSERT INTO sensor_definitions (
                definition_key,
                display_name,
                category,
                default_device_name,
                default_row_key,
                default_power_state,
                default_actuator_mode,
                metric_keys_json,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(definition_key) DO NOTHING
            """,
            (
                str(definition["definition_key"]).strip(),
                str(definition["display_name"]).strip(),
                str(definition["category"]).strip(),
                str(definition["default_device_name"]).strip(),
                str(definition["default_row_key"]).strip(),
                str(definition["default_power_state"]).strip(),
                str(definition["default_actuator_mode"]).strip(),
                json_dumps_compact(definition["metric_keys"]),
                json_dumps_compact(definition["metadata"]),
                timestamp,
                timestamp,
            ),
        )

    for backend in DEFAULT_SENSOR_BACKENDS:
        connection.execute(
            """
            INSERT INTO sensor_backends (
                backend_key,
                display_name,
                ingest_path,
                protocol,
                source_type,
                hardware_identifier_prefix,
                is_active,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(backend_key) DO NOTHING
            """,
            (
                str(backend["backend_key"]).strip(),
                str(backend["display_name"]).strip(),
                str(backend["ingest_path"]).strip(),
                str(backend["protocol"]).strip(),
                str(backend["source_type"]).strip(),
                str(backend["hardware_identifier_prefix"]).strip(),
                1 if bool(backend["is_active"]) else 0,
                json_dumps_compact(backend["metadata"]),
                timestamp,
                timestamp,
            ),
        )


def ensure_sensor_backend_seed(connection: sqlite3.Connection) -> None:
    timestamp = utc_now_iso()

    for sensor in DEFAULT_SENSOR_REGISTRY:
        connection.execute(
            """
            INSERT INTO sensor_registry (
                sensor_key,
                definition_key,
                backend_key,
                display_name,
                device_name,
                row_key,
                category,
                power_state,
                actuator_mode,
                alert_mode,
                hardware_identifier,
                metric_keys_json,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sensor_key) DO NOTHING
            """,
            (
                str(sensor["sensor_key"]).strip(),
                str(sensor["definition_key"] or "").strip(),
                str(sensor["backend_key"] or "").strip(),
                str(sensor["display_name"]).strip(),
                str(sensor["device_name"]).strip(),
                str(sensor["row_key"]).strip(),
                str(sensor["category"]).strip(),
                str(sensor["power_state"]).strip(),
                str(sensor["actuator_mode"]).strip(),
                str(sensor["alert_mode"]).strip(),
                str(sensor["hardware_identifier"]).strip(),
                json_dumps_compact(sensor["metric_keys"]),
                json_dumps_compact(sensor["metadata"]),
                timestamp,
                timestamp,
            ),
        )

        connection.execute(
            """
            UPDATE sensor_registry
            SET
                definition_key = CASE
                    WHEN TRIM(COALESCE(definition_key, '')) = '' THEN ?
                    ELSE definition_key
                END,
                backend_key = CASE
                    WHEN TRIM(COALESCE(backend_key, '')) = '' THEN ?
                    ELSE backend_key
                END,
                updated_at = CASE
                    WHEN TRIM(COALESCE(definition_key, '')) = '' OR TRIM(COALESCE(backend_key, '')) = '' THEN ?
                    ELSE updated_at
                END
            WHERE sensor_key = ?
            """,
            (
                str(sensor["definition_key"] or "").strip(),
                str(sensor["backend_key"] or "").strip(),
                timestamp,
                str(sensor["sensor_key"]).strip(),
            ),
        )

def cleanup_legacy_demo_sensor_data(connection: sqlite3.Connection) -> None:
    """Remove only old simulator readings while preserving live/API history."""
    timestamp = utc_now_iso()
    connection.execute(
        """
        DELETE FROM sensor_readings
        WHERE LOWER(TRIM(COALESCE(source_type, ''))) IN ('seed', 'hybrid-sync-test')
           OR LOWER(TRIM(COALESCE(source_identifier, ''))) IN (
                'default-backfill',
                'seed-simulator'
           )
        """
    )
    connection.execute(
        """
        UPDATE sensor_registry
        SET backend_key = 'mqtt-bridge', updated_at = ?
        WHERE backend_key = 'seed-simulator'
        """,
        (timestamp,),
    )
    mqtt_backend = next(
        backend for backend in DEFAULT_SENSOR_BACKENDS
        if str(backend["backend_key"]).strip() == "mqtt-bridge"
    )
    connection.execute(
        """
        UPDATE sensor_backends
        SET display_name = ?, ingest_path = ?, protocol = 'mqtt', source_type = 'mqtt',
            hardware_identifier_prefix = ?, is_active = TRUE, metadata_json = ?, updated_at = ?
        WHERE backend_key = 'mqtt-bridge'
        """,
        (
            str(mqtt_backend["display_name"]),
            str(mqtt_backend["ingest_path"]),
            str(mqtt_backend["hardware_identifier_prefix"]),
            json_dumps_compact(mqtt_backend["metadata"]),
            timestamp,
        ),
    )
    connection.execute("DELETE FROM sensor_backends WHERE backend_key = 'seed-simulator'")


def ensure_irrigation_backend_seed(connection: sqlite3.Connection) -> None:
    timestamp = utc_now_iso()
    ensure_system_state_value(connection, key="irrigation.mode", value="automatic")
    ensure_system_state_value(connection, key="irrigation.auto_enabled", value="1")
    ensure_system_state_value(connection, key="irrigation.active_manual_line", value="")
    ensure_system_state_value(connection, key="irrigation.active_manual_lines", value="{}")
    ensure_system_state_value(connection, key="irrigation.active_schedule_lines", value="{}")
    ensure_system_state_value(connection, key="irrigation.active_automatic_lines", value="{}")
    ensure_system_state_value(connection, key="irrigation.target_rows", value="{}")
    ensure_system_state_value(connection, key="irrigation.schedule_armed_rows", value="{}")
    ensure_system_state_value(connection, key="irrigation.active_manual_rows", value="{}")
    ensure_system_state_value(connection, key="irrigation.active_schedule_rows", value="{}")
    ensure_system_state_value(connection, key="irrigation.active_automatic_rows", value="{}")

    for channel in DEFAULT_IRRIGATION_CHANNELS:
        connection.execute(
            """
            INSERT INTO irrigation_settings (
                channel_key,
                label,
                automatic_duration_seconds,
                manual_duration_seconds,
                schedule_start_time,
                schedule_duration_seconds,
                schedule_frequency,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel_key) DO NOTHING
            """,
            (
                str(channel["channel_key"]).strip(),
                str(channel["label"]).strip(),
                int(channel["automatic_duration_seconds"]),
                int(channel["manual_duration_seconds"]),
                str(channel["schedule_start_time"]).strip(),
                int(channel["schedule_duration_seconds"]),
                str(channel["schedule_frequency"]).strip(),
                timestamp,
            ),
        )


def cleanup_legacy_demo_users(connection: sqlite3.Connection) -> None:
    placeholders = ", ".join("?" for _ in LEGACY_DEMO_USER_EMAILS)
    connection.execute(
        f"DELETE FROM users WHERE email IN ({placeholders})",  # nosec B608 - only '?' placeholders / module constants interpolated; values are bound parameters
        tuple(normalize_email(email) for email in LEGACY_DEMO_USER_EMAILS),
    )


# How long an applied-command marker is kept. These exist only so a command
# replayed by the relay is not applied twice; once the hosted side has seen the
# result there is nothing left to deduplicate against. A day is far longer than
# any retry window and short enough that they cannot accumulate.
HARDWARE_COMMAND_MARKER_RETENTION_DAYS = 1


def cleanup_applied_hardware_command_markers(connection: sqlite3.Connection) -> None:
    """Drop idempotency markers left behind by remote hardware commands.

    One row is written per remote command and none were ever removed, so this
    farm's system_state had grown to 3,182 rows of which 3,161 -- 99% -- were
    spent markers going back to 2026-08-21. Every press of an on/off control
    adds another.

    The table is read by the realtime fingerprint several times a second, and
    is carried by the edge sync, so letting it grow without bound costs work on
    both the kiosk and the uplink for rows nothing will ever read again.
    """
    cutoff = (utc_now() - timedelta(days=HARDWARE_COMMAND_MARKER_RETENTION_DAYS)).isoformat()
    connection.execute(
        "DELETE FROM system_state WHERE state_key LIKE ? AND updated_at < ?",
        (f"{REMOTE_HARDWARE_COMMAND_APPLIED_PREFIX}%", cutoff),
    )


# Process-local, like the heartbeat throttle: the cleanup above used to run
# only when the backend started, so a Pi that stayed up kept every marker from
# a bulk delete -- 15,000 of them in two hours on the farm.
_LAST_COMMAND_MARKER_PRUNE_MONOTONIC: float | None = None
COMMAND_MARKER_PRUNE_INTERVAL_SECONDS = 3600.0


def prune_applied_command_markers_if_due(connection: sqlite3.Connection) -> None:
    global _LAST_COMMAND_MARKER_PRUNE_MONOTONIC
    now = time.monotonic()
    if (
        _LAST_COMMAND_MARKER_PRUNE_MONOTONIC is not None
        and now - _LAST_COMMAND_MARKER_PRUNE_MONOTONIC < COMMAND_MARKER_PRUNE_INTERVAL_SECONDS
    ):
        return
    _LAST_COMMAND_MARKER_PRUNE_MONOTONIC = now
    cleanup_applied_hardware_command_markers(connection)


def cleanup_stale_login_challenges(connection: sqlite3.Connection) -> None:
    now = utc_now_iso()
    connection.execute(
        """
        DELETE FROM login_challenges
        WHERE consumed_at IS NOT NULL
           OR expires_at <= ?
        """,
        (now,),
    )


def cleanup_stale_account_creation_challenges(connection: sqlite3.Connection) -> None:
    now = utc_now_iso()
    connection.execute(
        """
        DELETE FROM account_creation_challenges
        WHERE consumed_at IS NOT NULL
           OR expires_at <= ?
        """,
        (now,),
    )


def trusted_proxy_hop_count() -> int:
    """How many reverse proxies in front of the app may be believed.

    Only the value a trusted proxy itself appended to X-Forwarded-For can be
    trusted; every entry to the left of that is supplied by the caller and can
    be forged. A managed host (Vercel) puts exactly one edge proxy in front of
    us. On the Pi, a desktop, or any direct bind there is none, so the header is
    ignored entirely and the real TCP peer is used. Override with
    ICUCROPS_TRUSTED_PROXY_HOPS when a deployment inserts a different number.
    """
    raw = os.getenv("ICUCROPS_TRUSTED_PROXY_HOPS", "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return 1 if running_on_managed_host() else 0


def client_ip_address() -> str:
    """The caller's address for rate-limiting, resistant to header spoofing.

    The login lockout is keyed on this value, so it must not be attacker
    controlled. X-Forwarded-For is honoured only for as many hops as a trusted
    proxy actually added, counting from the right; anything further left is
    caller-supplied. With no trusted proxy the header is ignored and the TCP
    peer address stands, which a client cannot forge.
    """
    remote_address = str(flask_request.remote_addr or "").strip()
    hops = trusted_proxy_hop_count()
    if hops > 0:
        forwarded_for = str(flask_request.headers.get("X-Forwarded-For") or "").strip()
        if forwarded_for:
            chain = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
            # With `hops` trusted proxies, the real client is the hops-th entry
            # from the right. A shorter chain means the request did not pass the
            # expected proxies, so fall back to the peer address instead.
            if len(chain) >= hops:
                candidate = chain[-hops]
                if candidate:
                    return candidate

    return remote_address or "unknown"


def admin_login_scope_key(client_address: str) -> str:
    return f"admin:{client_address.strip() or 'unknown'}"


def admin_login_account_scope_key(email: str) -> str:
    """Lockout scope tied to the targeted account rather than the caller.

    Keyed by the normalised email so failures aimed at one account accumulate
    across every source address. Empty when there is no valid address to aim at,
    which is when only the per-address lockout should apply.
    """
    normalized = normalize_email(email)
    if not normalized or not is_valid_gmail_address(normalized):
        return ""
    return f"acct:{normalized}"


def register_login_failure_across_scopes(
    connection: sqlite3.Connection,
    ip_scope_key: str,
    account_scope_key: str,
    failure_message: str,
    *,
    user_id: int | None = None,
) -> dict[str, object]:
    """Count one failed sign-in against both the address and the account.

    The address scope keeps its tight threshold; the account scope uses the
    higher backstop threshold. A lock produced by either scope takes precedence
    over a plain failure so the caller is turned away as soon as one trips.
    """
    ip_payload = register_admin_login_failure(
        connection, ip_scope_key, failure_message, user_id=user_id
    )
    account_payload: dict[str, object] | None = None
    if account_scope_key:
        account_payload = register_admin_login_failure(
            connection,
            account_scope_key,
            failure_message,
            user_id=user_id,
            max_attempts=ADMIN_LOGIN_ACCOUNT_MAX_ATTEMPTS,
            lock_minutes=ADMIN_LOGIN_ACCOUNT_LOCK_MINUTES,
        )

    if ip_payload.get("code") == "ADMIN_LOGIN_LOCKED":
        return ip_payload
    if account_payload and account_payload.get("code") == "ADMIN_LOGIN_LOCKED":
        return account_payload
    return ip_payload


def otp_request_throttle_scopes(email: str, client_address: str) -> list[tuple[str, int]]:
    """Rate-limit scopes for an OTP request: one per target email, one per caller."""
    scopes: list[tuple[str, int]] = []
    normalized = normalize_email(email)
    if normalized and is_valid_gmail_address(normalized):
        scopes.append((f"otp:{normalized}", OTP_REQUEST_EMAIL_MAX))
    scopes.append((f"otp-ip:{client_address.strip() or 'unknown'}", OTP_REQUEST_IP_MAX))
    return scopes


def check_otp_request_throttle(
    connection: sqlite3.Connection, email: str, client_address: str
) -> dict[str, object] | None:
    """Bound how often an OTP code can be requested.

    Returns a 429 payload when the caller or the target email has already spent
    its allowance for the window; otherwise records this request and returns
    None. Checked before the expensive hash and the email send so a flood is
    turned away cheaply. Reuses the generic attempt-lock table with distinct
    scope keys so the counting and expiry are the same tested code path.
    """
    scopes = otp_request_throttle_scopes(email, client_address)
    for scope_key, _ in scopes:
        lock = get_admin_login_lock(connection, scope_key)
        if lock:
            retry = int(lock.get("retryAfterSeconds") or 60)
            minutes = max(1, (retry + 59) // 60)
            return {
                "code": "OTP_REQUEST_THROTTLED",
                "message": f"Too many OTP requests. Please wait about {minutes} minute(s) before asking for another code.",
                "retryAfterSeconds": retry,
            }
    for scope_key, max_hits in scopes:
        register_admin_login_failure(
            connection,
            scope_key,
            "otp-request",
            max_attempts=max_hits,
            lock_minutes=OTP_REQUEST_WINDOW_MINUTES,
        )
    return None


def admin_login_lock_payload(
    *,
    message: str,
    remaining_attempts: int,
    locked_until: str = "",
    retry_after_seconds: int = 0,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "message": message,
        "code": "ADMIN_LOGIN_LOCKED" if retry_after_seconds > 0 else "ADMIN_LOGIN_FAILED",
        "remainingAttempts": max(0, int(remaining_attempts)),
    }

    if retry_after_seconds > 0:
        payload["lockedUntil"] = locked_until
        payload["retryAfterSeconds"] = int(retry_after_seconds)

    return payload


def get_admin_login_lock(connection: sqlite3.Connection, scope_key: str) -> dict[str, object] | None:
    row = connection.execute(
        """
        SELECT scope_key, attempt_count, locked_until, updated_at
        FROM admin_login_attempts
        WHERE scope_key = ?
        """,
        (scope_key,),
    ).fetchone()
    if not row:
        return None

    locked_until = str(row["locked_until"] or "").strip()
    if not locked_until:
        return None

    now = utc_now()
    expires_at = parse_iso_datetime(locked_until)
    if expires_at <= now:
        connection.execute("DELETE FROM admin_login_attempts WHERE scope_key = ?", (scope_key,))
        return None

    retry_after_seconds = max(1, int((expires_at - now).total_seconds()))
    return admin_login_lock_payload(
        message=f"Login is locked for {retry_after_seconds} more second(s). Please wait 5 minutes before trying again.",
        remaining_attempts=0,
        locked_until=locked_until,
        retry_after_seconds=retry_after_seconds,
    )


def clear_admin_login_attempts(connection: sqlite3.Connection, scope_key: str) -> None:
    connection.execute("DELETE FROM admin_login_attempts WHERE scope_key = ?", (scope_key,))


def register_admin_login_failure(
    connection: sqlite3.Connection,
    scope_key: str,
    failure_message: str,
    *,
    user_id: int | None = None,
    max_attempts: int = ADMIN_LOGIN_MAX_ATTEMPTS,
    lock_minutes: int = ADMIN_LOGIN_LOCK_MINUTES,
) -> dict[str, object]:
    """Count a failed sign-in against its scope.

    The scope is the client address, not the account, because most failures
    arrive for addresses that match no user at all - which is exactly when a
    lockout matters. user_id records which account was aimed at when the email
    did resolve, so a targeted attempt can be told apart from noise. It stays
    NULL when the email is unknown.
    """
    row = connection.execute(
        """
        SELECT attempt_count, locked_until
        FROM admin_login_attempts
        WHERE scope_key = ?
        """,
        (scope_key,),
    ).fetchone()

    now = utc_now()
    attempts = 0
    if row:
        locked_until = str(row["locked_until"] or "").strip()
        if locked_until and parse_iso_datetime(locked_until) > now:
            retry_after_seconds = max(1, int((parse_iso_datetime(locked_until) - now).total_seconds()))
            return admin_login_lock_payload(
                message=f"Login is locked for {retry_after_seconds} more second(s). Please wait 5 minutes before trying again.",
                remaining_attempts=0,
                locked_until=locked_until,
                retry_after_seconds=retry_after_seconds,
            )
        attempts = int(row["attempt_count"] or 0)

    attempts += 1
    updated_at = now.isoformat()
    remaining_attempts = max(0, max_attempts - attempts)

    if attempts >= max_attempts:
        locked_until = (now + timedelta(minutes=lock_minutes)).isoformat()
        connection.execute(
            """
            INSERT INTO admin_login_attempts (scope_key, attempt_count, locked_until, updated_at, user_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(scope_key) DO UPDATE SET
                attempt_count = excluded.attempt_count,
                locked_until = excluded.locked_until,
                updated_at = excluded.updated_at,
                user_id = COALESCE(excluded.user_id, admin_login_attempts.user_id)
            """,
            (scope_key, attempts, locked_until, updated_at, user_id),
        )
        retry_after_seconds = lock_minutes * 60
        return admin_login_lock_payload(
            message=f"Login is locked for {lock_minutes} minutes after {max_attempts} failed attempts.",
            remaining_attempts=0,
            locked_until=locked_until,
            retry_after_seconds=retry_after_seconds,
        )

    connection.execute(
        """
        INSERT INTO admin_login_attempts (scope_key, attempt_count, locked_until, updated_at, user_id)
        VALUES (?, ?, NULL, ?, ?)
        ON CONFLICT(scope_key) DO UPDATE SET
            attempt_count = excluded.attempt_count,
            locked_until = excluded.locked_until,
            updated_at = excluded.updated_at,
            user_id = COALESCE(excluded.user_id, admin_login_attempts.user_id)
        """,
        (scope_key, attempts, updated_at, user_id),
    )
    return admin_login_lock_payload(
        message=failure_message,
        remaining_attempts=remaining_attempts,
    )


def list_users(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT id, display_name, email, role, is_active, profile_photo_path, profile_photo_version,
               length(profile_photo_data) AS profile_photo_bytes
        FROM users
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()


def find_user_by_email(connection: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, display_name, email, role, password_hash, password_salt, password_iterations,
               is_active, profile_photo_path, profile_photo_version,
               length(profile_photo_data) AS profile_photo_bytes
        FROM users
        WHERE email = ?
        """,
        (email,),
    ).fetchone()


def find_user_by_id(connection: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, display_name, email, role, password_hash, password_salt, password_iterations,
               is_active, profile_photo_path, profile_photo_version,
               length(profile_photo_data) AS profile_photo_bytes,
               -- The session verifier reads these three off this row. They were
               -- missing from the projection, so active_session_jti came back
               -- as None on every request and the single-session check
               -- short-circuited on `if active_jti` -- which is why two devices
               -- could hold the same account with the rule apparently in place.
               active_session_jti, active_session_client_id, active_session_issued_at
        FROM users
        WHERE id = ?
        """,
        (int(user_id),),
    ).fetchone()


def authenticate_user(connection: sqlite3.Connection, email: str, password: str) -> sqlite3.Row | None:
    user = find_user_by_email(connection, email)
    if not user or int(user["is_active"]) != 1:
        return None

    if not verify_secret(
        password,
        salt=user["password_salt"],
        digest=user["password_hash"],
        iterations=int(user["password_iterations"]),
    ):
        return None

    return user


def generate_otp_code(length: int = OTP_LENGTH) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def is_valid_password(password: str) -> bool:
    value = str(password or "")
    return (
        PASSWORD_MIN_LENGTH <= len(value) <= PASSWORD_MAX_LENGTH
        and any(character.isupper() for character in value)
        and any(character.islower() for character in value)
        and any(character.isdigit() for character in value)
        and any(not character.isalnum() and not character.isspace() for character in value)
    )


def validate_user_account_fields(
    *,
    display_name: object,
    email: object,
    role: object,
    password: object,
    confirm_password: object | None = None,
) -> tuple[str, str, str, str]:
    normalized_display_name = str(display_name or "").strip()
    normalized_email = normalize_email(email)
    normalized_role = normalize_role(role)
    normalized_password = str(password or "")
    normalized_confirm_password = normalized_password if confirm_password is None else str(confirm_password or "")

    if not normalized_display_name:
        raise ValueError("Please enter the user's name.")

    if not normalized_email:
        raise ValueError("Please enter the user's Gmail address.")

    if not is_valid_gmail_address(normalized_email):
        raise ValueError("Use a valid Gmail address.")

    if not normalized_password:
        raise ValueError("Please enter the user's password.")

    if normalized_password != normalized_confirm_password:
        raise ValueError("Passwords do not match.")

    if not is_valid_password(normalized_password):
        raise ValueError(PASSWORD_POLICY_MESSAGE)

    return normalized_display_name, normalized_email, normalized_role, normalized_password


def optional_row_value(user: sqlite3.Row, key: str, default: str = "") -> str:
    return str(user[key]) if key in user.keys() and user[key] is not None else default


def normalize_profile_photo_path(value: object) -> str:
    raw_path = str(value or "").strip().replace("\\", "/")
    if not raw_path:
        return ""

    try:
        target = (WORKSPACE_DIR / raw_path).resolve()
        target.relative_to(WORKSPACE_DIR.resolve())
    except ValueError:
        return ""

    if not target.exists() or not target.is_file():
        return ""

    return target.relative_to(WORKSPACE_DIR).as_posix()


def profile_photo_url(storage_path: str) -> str:
    normalized = normalize_profile_photo_path(storage_path)
    if not normalized:
        return ""
    return "/" + "/".join(quote(part) for part in normalized.split("/"))


def delete_profile_photo_file(storage_path: str) -> None:
    normalized = normalize_profile_photo_path(storage_path)
    if not normalized:
        return

    target = (WORKSPACE_DIR / normalized).resolve()
    try:
        target.relative_to(STORAGE_DIR.resolve())
    except ValueError:
        return

    if target.exists() and target.is_file():
        target.unlink()


def read_profile_photo_upload(uploaded_file) -> tuple[bytes, str]:
    filename = secure_filename(uploaded_file.filename or "")
    if not filename:
        raise ValueError("Please choose a valid image file.")

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_PROFILE_PHOTO_EXTENSIONS:
        raise ValueError("Profile photo must be a JPG, PNG, GIF, or WebP image.")

    uploaded_file.stream.seek(0)
    photo_data = uploaded_file.stream.read(MAX_PROFILE_PHOTO_BYTES + 1)
    uploaded_file.stream.seek(0)
    if not photo_data:
        raise ValueError("Please choose a valid image file.")
    if len(photo_data) > MAX_PROFILE_PHOTO_BYTES:
        raise ValueError("Profile photo must be 5 MB or smaller.")

    detected_mime = ""
    if photo_data.startswith(b"\xff\xd8\xff"):
        detected_mime = "image/jpeg"
    elif photo_data.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_mime = "image/png"
    elif photo_data.startswith((b"GIF87a", b"GIF89a")):
        detected_mime = "image/gif"
    elif len(photo_data) >= 12 and photo_data[:4] == b"RIFF" and photo_data[8:12] == b"WEBP":
        detected_mime = "image/webp"

    extension_mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }[suffix]
    if not detected_mime or detected_mime != extension_mime:
        raise ValueError("The selected file is not a valid JPG, PNG, GIF, or WebP image.")

    uploaded_mime = str(getattr(uploaded_file, "mimetype", "") or "").lower()
    if uploaded_mime and uploaded_mime not in {detected_mime, "application/octet-stream"}:
        raise ValueError("The selected image type does not match its file contents.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(photo_data)) as uploaded_image:
                if uploaded_image.width * uploaded_image.height > MAX_PROFILE_PHOTO_PIXELS:
                    raise ValueError("Profile photo dimensions are too large.")

                # Decode the first frame, honor phone-camera EXIF rotation, and create one
                # predictable square asset for the database, the web app, and the Pi.
                uploaded_image.seek(0)
                uploaded_image.load()
                oriented = ImageOps.exif_transpose(uploaded_image)
                if oriented.mode in {"RGBA", "LA"} or "transparency" in oriented.info:
                    rgba_image = oriented.convert("RGBA")
                    rgb_image = Image.new("RGB", rgba_image.size, "#f7faf5")
                    rgb_image.paste(rgba_image, mask=rgba_image.getchannel("A"))
                else:
                    rgb_image = oriented.convert("RGB")

                # A slightly upper-centered portrait crop generally keeps faces in frame;
                # landscape photos remain horizontally centered. ImageOps.fit guarantees
                # an exact square without stretching the source.
                normalized = ImageOps.fit(
                    rgb_image,
                    (PROFILE_PHOTO_OUTPUT_SIZE, PROFILE_PHOTO_OUTPUT_SIZE),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.38),
                )
                output = io.BytesIO()
                normalized.save(output, format="JPEG", quality=88, optimize=True, progressive=True)
    except ValueError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError):
        raise ValueError("The selected file is not a readable image.") from None

    normalized_data = output.getvalue()
    if not normalized_data or len(normalized_data) > MAX_PROFILE_PHOTO_BYTES:
        raise ValueError("The selected image could not be optimized below 5 MB.")

    return normalized_data, "image/jpeg"


def profile_photo_record_url(user: object) -> str:
    version = optional_row_value(user, "profile_photo_version")
    # A version marker can outlive its image when a photo write is rolled back or a
    # restored backup arrives without the blob. Linking it only yields a guaranteed
    # 404, so fall through to the initial-letter avatar when the bytes are gone.
    stored_bytes = optional_row_value(user, "profile_photo_bytes")
    if stored_bytes.isdigit() and int(stored_bytes) <= 0:
        version = ""
    if version:
        return f"/profile-photo/{quote(str(user['id']))}?v={quote(version)}"

    return profile_photo_url(optional_row_value(user, "profile_photo_path"))


def local_profile_photo_record(storage_path: str) -> tuple[bytes, str] | None:
    normalized = normalize_profile_photo_path(storage_path)
    if not normalized:
        return None

    target = (WORKSPACE_DIR / normalized).resolve()
    suffix = target.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "")
    if not mime:
        return None

    data = target.read_bytes()
    if not data or len(data) > MAX_PROFILE_PHOTO_BYTES:
        return None
    return data, mime


ALLOWED_DASHBOARD_GRAPH_RANGES = {"realtime", "24h", "7d", "14d", "30d"}
ALLOWED_CULTIVATION_GRAPH_RANGES = {"24h", "7d", "14d", "30d", "crop"}


# Row-to-JSON helpers keep the frontend payload format stable even if storage changes internally.
def build_user_payload(user: sqlite3.Row) -> dict[str, str]:
    role = normalize_role(user["role"])
    return {
        "id": str(user["id"]),
        "displayName": str(user["display_name"]),
        "email": normalize_email(user["email"]),
        "role": role,
        "roleLabel": role_label(role),
        "profilePhotoUrl": profile_photo_record_url(user),
    }


def cultivation_row_label(row_key: str) -> str:
    normalized = str(row_key or "").strip().lower()
    if normalized in VALID_CULTIVATION_ROWS:
        return f"Row {normalized.removeprefix('row')}"
    return "Unassigned Row"


def cultivation_date_value(value: object, *, label: str = "Cultivation date") -> date:
    """A YYYY-MM-DD date from a request, as a date; its year is not checked."""
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{label} is required.")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as error:
        raise ValueError("Cultivation dates must use YYYY-MM-DD format.") from error


def normalize_cultivation_date(value: object, *, label: str = "Cultivation date") -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Cultivation date is required.")

    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("Cultivation dates must use YYYY-MM-DD format.") from error

    current_year = datetime.now().year
    if parsed.year != current_year:
        raise ValueError(f"{label} must be within {current_year}.")

    return raw


def normalize_cultivation_parameters(parameters: object) -> dict[str, dict[str, float]]:
    if not isinstance(parameters, dict) or not parameters:
        raise ValueError("Cultivation parameters are required.")

    normalized: dict[str, dict[str, float]] = {}
    for key, value in parameters.items():
        if not isinstance(value, dict):
            raise ValueError("Cultivation parameters are invalid.")

        try:
            minimum = float(value.get("min"))
            maximum = float(value.get("max"))
        except (TypeError, ValueError) as error:
            raise ValueError("Cultivation parameters are invalid.") from error

        if minimum >= maximum:
            raise ValueError("Cultivation parameter minimum must be lower than maximum.")

        normalized[str(key).strip()] = {
            "min": minimum,
            "max": maximum,
        }

    return normalized


def build_cultivation_payload(cultivation: sqlite3.Row) -> dict[str, object]:
    row_key = str(cultivation["row_key"]).strip()
    # parse_json_object rather than json.loads: parameters_json is jsonb in
    # Postgres, so the driver hands back a dict already. str() on that yields a
    # Python repr with single quotes, which json.loads rejects at column 2.
    # SQLite still returns the raw string. The helper takes either.
    parameters = parse_json_object(cultivation["parameters_json"])
    return {
        "id": str(cultivation["id"]),
        "rowKey": row_key,
        "rowLabel": cultivation_row_label(row_key),
        "cropType": str(cultivation["crop_type"]).strip(),
        "customPlantName": str(cultivation["custom_plant_name"] or "").strip(),
        "crop": str(cultivation["crop_name"]).strip(),
        "plantingDate": str(cultivation["planting_date"]).strip(),
        "harvestDate": str(cultivation["harvest_date"]).strip(),
        "daysToHarvest": int(cultivation["days_to_harvest"]),
        "parameterMode": str(cultivation["parameter_mode"]).strip(),
        "parameters": parameters,
        "createdByUserId": str(cultivation["created_by_user_id"] or "").strip(),
        "createdAt": str(cultivation["created_at"]).strip(),
        "updatedAt": str(cultivation["updated_at"]).strip(),
    }


def build_harvest_payload(harvest: sqlite3.Row) -> dict[str, object]:
    """One completed crop, for the dashboard and the report.

    Deliberately the same shape as build_cultivation_payload where the fields
    overlap, so a harvest can be rendered by the code that already knows how to
    show a cultivation, and parse_json_object for the same jsonb-vs-TEXT reason
    documented there.
    """
    row_key = str(harvest["row_key"]).strip()
    return {
        "id": str(harvest["id"]),
        "rowKey": row_key,
        "rowLabel": cultivation_row_label(row_key),
        "cropType": str(harvest["crop_type"]).strip(),
        "customPlantName": str(harvest["custom_plant_name"] or "").strip(),
        "crop": str(harvest["crop_name"]).strip(),
        "plantingDate": str(harvest["planting_date"]).strip(),
        "harvestDate": str(harvest["harvest_date"]).strip(),
        "daysToHarvest": int(harvest["days_to_harvest"]),
        "parameterMode": str(harvest["parameter_mode"]).strip(),
        "parameters": parse_json_object(harvest["parameters_json"]),
        "harvestedAt": str(harvest["harvested_at"]).strip(),
        "daysGrown": int(harvest["days_grown"] or 0),
        # bool() rather than the raw column: INTEGER on SQLite, boolean on
        # Postgres. The browser should never have to know which store answered.
        "onSchedule": bool(harvest["on_schedule"]),
        "createdAt": str(harvest["created_at"]).strip(),
    }


def build_notification_payload(notification: sqlite3.Row) -> dict[str, object]:
    return {
        "id": str(notification["id"]),
        "scope": normalize_notification_scope(notification["scope"]),
        "type": str(notification["type"]).strip() or "success",
        "message": str(notification["message"]).strip(),
        "sourceType": str(notification["source_type"] or "").strip(),
        "sourceId": str(notification["source_id"] or "").strip(),
        "createdAt": str(notification["created_at"]).strip(),
        "read": bool(int(notification["is_read"] or 0)),
    }


def parse_json_object(raw_value: object, *, fallback: dict[str, object] | None = None) -> dict[str, object]:
    if isinstance(raw_value, dict):
        return raw_value

    if raw_value is None or raw_value == "":
        return dict(fallback or {})

    try:
        parsed = json.loads(str(raw_value))
    except (TypeError, ValueError):
        return dict(fallback or {})

    return parsed if isinstance(parsed, dict) else dict(fallback or {})


def parse_json_string_list(raw_value: object) -> list[str]:
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]

    if raw_value is None or raw_value == "":
        return []

    try:
        parsed = json.loads(str(raw_value))
    except (TypeError, ValueError):
        return []

    if not isinstance(parsed, list):
        return []

    return [str(item).strip() for item in parsed if str(item).strip()]


def normalize_numeric_value(value: object) -> float | None:
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def average_numeric(values: list[float | None]) -> float | None:
    numbers = [value for value in values if value is not None]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 2)


def parse_sensor_reading_payload(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        payload = value
    else:
        payload = parse_json_object(value)

    normalized: dict[str, object] = {}
    for key, item in payload.items():
        numeric = normalize_numeric_value(item)
        normalized[str(key).strip()] = numeric if numeric is not None else item
    return normalized


def reading_text_value(reading: sqlite3.Row | None, metric_key: str) -> str:
    """A non-numeric field from a reading payload, such as a probe's status.

    parse_sensor_reading_payload keeps values it cannot make a number of, so a
    sensor can say what is wrong with it in the same payload it would have sent
    a measurement in.
    """
    if not reading:
        return ""
    payload = parse_sensor_reading_payload(reading["reading_payload_json"])
    value = payload.get(metric_key)
    return str(value).strip() if isinstance(value, str) else ""


# --------------------------------------------------------------- Bench fit ---
# The greenhouse DHT22 reads high, and this maps what it reports onto what the
# crops are judged against. It is a field correction for one failing part, not
# a calibration, and it lives here rather than in the firmware because the
# board has no idea what is planted -- the bounds come from the crop
# parameters and move by themselves when a row is replanted.
#
# Why not a slope or an offset. Both cap the scale. The -25 %RH offset this
# replaces meant a genuinely saturated greenhouse could never read above
# 75 %RH, and a humidity that cannot reach 100 is not a humidity reading -- it
# also hid a sensor that had stopped moving at all, because 74.9 looked
# ordinary. A multiplier has the same fault at the top end.
#
# So the map is piecewise and pinned at both ends. 0 stays 0, 100 stays 100,
# and one interior point is moved: whatever the part reads now is placed at the
# middle of the crops' own range. Below that point the scale is stretched, above
# it compressed, and nothing is clamped -- so a real rise still carries the
# reading up through the warning band and into critical, and a real fall can
# still reach critical low. The alerts stay reachable in both directions, which
# is the whole reason not to use a cap.
#
# The anchor is deliberately a constant rather than a running average of the
# sensor. A correction that followed the reading would cancel every change the
# reading made, which is the one thing this must not do.
#
# This is a stopgap for a part that sat above its range too long. The honest
# fix is a salt-jar capture (tools/calibrate_dht22.py, NaCl = 75 %RH, six hours
# sealed), or an SHT31/SHT41, which does not fail this way. Setting
# DHT22_BENCH_HUMIDITY to 0 turns the whole thing off and publishes raw.
DHT22_BENCH_HUMIDITY = float(os.getenv("ICUCROPS_DHT22_BENCH_HUMIDITY", "95"))
# Zero means "do not fit". This part's thermometer is accurate -- measured 28.8C
# on the bench while its humidity read 95 -- so temperature publishes raw.
DHT22_BENCH_TEMP_C = float(os.getenv("ICUCROPS_DHT22_BENCH_TEMP_C", "0"))


def bench_fit_reading(
    raw: float | None, observed: float, floor: float | None, ceiling: float | None
) -> float | None:
    """Move ``observed`` to the middle of the crops' range, keeping 0 and 100.

    Returns ``raw`` unchanged when there is nothing to fit against: no crops
    planted, no observation configured, or an observation already inside the
    range. Doing nothing is the right answer in all three -- a correction with
    no reference behind it is an invention.
    """
    if raw is None or observed <= 0 or observed >= 100:
        return raw
    if floor is None or ceiling is None or ceiling <= floor:
        return raw

    target = (float(floor) + float(ceiling)) / 2.0
    # Already where it should be; a fit here would only add error.
    if abs(observed - target) < 0.05:
        return raw

    if raw <= observed:
        # Stretch 0..observed onto 0..target. Zero stays zero, so a genuinely
        # dry house still reaches critical low.
        return raw * (target / observed)
    # Compress observed..100 onto target..100. One hundred stays one hundred,
    # so a genuinely saturated house still reaches critical high.
    return target + (raw - observed) * (100.0 - target) / (100.0 - observed)


def bench_fitted_humidity(raw: float | None) -> float | None:
    """The greenhouse humidity as the dashboard, alerts and rules should see it."""
    if raw is None or DHT22_BENCH_HUMIDITY <= 0:
        return raw
    floor, ceiling = _bench_fit_humidity_bounds()
    return _bench_fit_rounded(bench_fit_reading(raw, DHT22_BENCH_HUMIDITY, floor, ceiling))


def bench_fitted_temperature(raw: float | None) -> float | None:
    """The same treatment for temperature, off unless a bench figure is set.

    Off by default, and deliberately so: this part's thermometer measures
    correctly. Its raw temperature read 28.8C on the bench against a plausible
    greenhouse figure, while its humidity read 95 %RH -- the polymer is the
    half that sat above its range, not the thermistor. Fitting a channel that
    is already right would only add error.

    The hook is here because the same failure could reach temperature later,
    and because the two should be corrected the same way if it does. Set
    ICUCROPS_DHT22_BENCH_TEMP_C to whatever the part reads when the house is
    genuinely at the middle of the crops' range, and it behaves exactly like
    the humidity fit: the ends stay put, nothing is clamped, and critical high
    and low both stay reachable.
    """
    if raw is None or DHT22_BENCH_TEMP_C <= 0:
        return raw
    floor, ceiling = _bench_fit_temp_bounds()
    return _bench_fit_rounded(bench_fit_reading(raw, DHT22_BENCH_TEMP_C, floor, ceiling))


def _bench_fit_rounded(value: float | None) -> float | None:
    """Back to the one decimal the DHT22 publishes.

    The fit is a ratio, so it hands back binary-float noise: 82.4 came out as
    82.39999999999999 and the kiosk printed every digit of it on the card.
    The part only resolves 0.1, so nothing past that is a measurement.
    """
    return None if value is None else round(value, 1)


# The crops' bounds the fit is judged against, for the duration of one request.
#
# Deliberately a context manager rather than a module-level cache that
# list_cultivations refreshes. That was the first shape, and it was wrong in a
# way the test suite caught immediately: the bounds outlived whatever set them,
# so a reading looked up after one crop had been loaded was fitted against
# another crop's range. In a test run that showed up as one file's crops
# changing a different file's actuator decisions; in the running service it is
# the same hazard between one request and the next, and a fan cut by bounds
# belonging to a row that is not being asked about is far worse than no fit.
#
# So it is scoped, empty by default, and a reading looked up outside a scope is
# simply not fitted. Nothing silently inherits a previous caller's crops.
_bench_fit_bounds = threading.local()


def _bench_fit_humidity_bounds() -> tuple[float | None, float | None]:
    return getattr(_bench_fit_bounds, "humidity", (None, None))


def _bench_fit_temp_bounds() -> tuple[float | None, float | None]:
    return getattr(_bench_fit_bounds, "temp", (None, None))


@contextlib.contextmanager
def bench_fit_scope(cultivations: list[sqlite3.Row] | list[dict[str, object]]):
    """Fit greenhouse readings against these crops for the duration of the block."""
    previous_humidity = getattr(_bench_fit_bounds, "humidity", (None, None))
    previous_temp = getattr(_bench_fit_bounds, "temp", (None, None))
    try:
        _bench_fit_bounds.humidity = crop_parameter_bounds(cultivations, "humidity")
        _bench_fit_bounds.temp = crop_parameter_bounds(cultivations, "temp")
    except Exception:  # noqa: BLE001 - a bad row must not break every reading
        _bench_fit_bounds.humidity = (None, None)
        _bench_fit_bounds.temp = (None, None)
    try:
        yield
    finally:
        # Restored rather than cleared, so nesting one scope inside another
        # leaves the outer one intact.
        _bench_fit_bounds.humidity = previous_humidity
        _bench_fit_bounds.temp = previous_temp


def reading_metric_value(reading: sqlite3.Row | None, metric_key: str) -> float | None:
    if not reading:
        return None

    payload = parse_sensor_reading_payload(reading["reading_payload_json"])
    if metric_key in payload:
        value = normalize_numeric_value(payload.get(metric_key))
    elif "value" in payload:
        value = normalize_numeric_value(payload.get("value"))
    else:
        return None

    # The greenhouse DHT22's humidity is fitted here, on the way out, so the
    # database keeps what the sensor actually said. Every consumer -- the
    # cards, the alerts, the automatic rules, the reports -- reads through this
    # one function, so they cannot disagree about which number they are using.
    # report_field, not reading["sensor_key"]: a sqlite3.Row raises rather than
    # returning None for a column it does not have, and plenty of callers build
    # a reading without one. Reaching for it directly turned every such lookup
    # into a KeyError -- the fit has to be invisible to readings it does not
    # apply to, not fatal to them.
    if str(report_field(reading, "sensor_key", "") or "").strip() == "dht22":
        if metric_key == "humidity":
            return bench_fitted_humidity(value)
        if metric_key == "temp":
            return bench_fitted_temperature(value)
    return value


def reading_captured_at(reading: sqlite3.Row | None) -> str:
    return str(reading["captured_at"]).strip() if reading else ""


def list_sensor_definitions(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            id,
            definition_key,
            display_name,
            category,
            default_device_name,
            default_row_key,
            default_power_state,
            default_actuator_mode,
            metric_keys_json,
            metadata_json,
            created_at,
            updated_at
        FROM sensor_definitions
        ORDER BY definition_key ASC
        """
    ).fetchall()


def find_sensor_definition_by_key(connection: sqlite3.Connection, definition_key: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            id,
            definition_key,
            display_name,
            category,
            default_device_name,
            default_row_key,
            default_power_state,
            default_actuator_mode,
            metric_keys_json,
            metadata_json,
            created_at,
            updated_at
        FROM sensor_definitions
        WHERE definition_key = ?
        LIMIT 1
        """,
        (normalize_sensor_key(definition_key),),
    ).fetchone()


def build_sensor_definition_payload(definition: sqlite3.Row) -> dict[str, object]:
    return {
        "id": str(definition["id"]),
        "definitionKey": str(definition["definition_key"]).strip(),
        "displayName": str(definition["display_name"]).strip(),
        "category": str(definition["category"]).strip(),
        "defaultDeviceName": str(definition["default_device_name"]).strip(),
        "defaultRowKey": str(definition["default_row_key"]).strip(),
        "defaultPowerState": normalize_sensor_power_state(definition["default_power_state"]),
        "defaultActuatorMode": normalize_actuator_mode(definition["default_actuator_mode"])
        if str(definition["default_actuator_mode"]).strip()
        else "",
        "metricKeys": parse_json_string_list(definition["metric_keys_json"]),
        "metadata": parse_json_object(definition["metadata_json"]),
        "createdAt": str(definition["created_at"]).strip(),
        "updatedAt": str(definition["updated_at"]).strip(),
    }


def list_sensor_backends(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            id,
            backend_key,
            display_name,
            ingest_path,
            protocol,
            source_type,
            hardware_identifier_prefix,
            is_active,
            metadata_json,
            created_at,
            updated_at
        FROM sensor_backends
        ORDER BY backend_key ASC
        """
    ).fetchall()


def find_sensor_backend_by_key(connection: sqlite3.Connection, backend_key: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            id,
            backend_key,
            display_name,
            ingest_path,
            protocol,
            source_type,
            hardware_identifier_prefix,
            is_active,
            metadata_json,
            created_at,
            updated_at
        FROM sensor_backends
        WHERE backend_key = ?
        LIMIT 1
        """,
        (normalize_sensor_key(backend_key),),
    ).fetchone()


def build_sensor_backend_payload(backend: sqlite3.Row) -> dict[str, object]:
    return {
        "id": str(backend["id"]),
        "backendKey": str(backend["backend_key"]).strip(),
        "displayName": str(backend["display_name"]).strip(),
        "ingestPath": str(backend["ingest_path"]).strip(),
        "protocol": str(backend["protocol"]).strip(),
        "sourceType": str(backend["source_type"]).strip(),
        "hardwareIdentifierPrefix": str(backend["hardware_identifier_prefix"]).strip(),
        "isActive": bool(int(backend["is_active"] or 0)),
        "metadata": parse_json_object(backend["metadata_json"]),
        "createdAt": str(backend["created_at"]).strip(),
        "updatedAt": str(backend["updated_at"]).strip(),
    }


def list_sensor_registry(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            id,
            sensor_key,
            definition_key,
            backend_key,
            display_name,
            device_name,
            row_key,
            category,
            power_state,
            actuator_mode,
            alert_mode,
            hardware_identifier,
            metric_keys_json,
            metadata_json,
            created_at,
            updated_at
        FROM sensor_registry
        ORDER BY row_key ASC, sensor_key ASC
        """
    ).fetchall()


def find_sensor_registry_by_key(connection: sqlite3.Connection, sensor_key: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            id,
            sensor_key,
            definition_key,
            backend_key,
            display_name,
            device_name,
            row_key,
            category,
            power_state,
            actuator_mode,
            alert_mode,
            hardware_identifier,
            metric_keys_json,
            metadata_json,
            created_at,
            updated_at
        FROM sensor_registry
        WHERE sensor_key = ?
        LIMIT 1
        """,
        (normalize_sensor_key(sensor_key),),
    ).fetchone()


def find_sensor_registry_by_hardware_identifier(
    connection: sqlite3.Connection,
    hardware_identifier: str,
) -> sqlite3.Row | None:
    identifier = str(hardware_identifier or "").strip()
    if not identifier:
        return None

    return connection.execute(
        """
        SELECT
            id,
            sensor_key,
            definition_key,
            backend_key,
            display_name,
            device_name,
            row_key,
            category,
            power_state,
            actuator_mode,
            alert_mode,
            hardware_identifier,
            metric_keys_json,
            metadata_json,
            created_at,
            updated_at
        FROM sensor_registry
        WHERE hardware_identifier = ?
        LIMIT 1
        """,
        (identifier,),
    ).fetchone()


def latest_sensor_readings_by_key(connection: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = connection.execute(
        """
        SELECT
            reading.id,
            reading.sensor_key,
            reading.reading_payload_json,
            reading.source_type,
            reading.source_identifier,
            reading.captured_at
        FROM sensor_registry AS sensor
        INNER JOIN sensor_readings AS reading
            ON reading.id = (
                SELECT candidate.id
                FROM sensor_readings AS candidate
                WHERE candidate.sensor_key = sensor.sensor_key
                  AND LOWER(TRIM(COALESCE(candidate.source_type, ''))) NOT IN (
                      'seed',
                      'hybrid-sync-test'
                  )
                  AND LOWER(TRIM(COALESCE(candidate.source_identifier, ''))) NOT IN (
                      'default-backfill',
                      'seed-simulator'
                  )
                ORDER BY candidate.captured_at DESC, candidate.id DESC
                LIMIT 1
            )
        ORDER BY reading.sensor_key ASC
        """
    ).fetchall()
    return {str(row["sensor_key"]).strip(): row for row in rows}


def clamp_percentage(value: object) -> float:
    numeric = normalize_numeric_value(value)
    if numeric is None:
        return 0.0
    return round(max(0.0, min(100.0, numeric)), 2)


def format_liters(value: float) -> str:
    formatted = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{formatted}L"


DASHBOARD_SERIES_HISTORY_LIMIT = 900
DASHBOARD_SERIES_RETENTION_DAYS = 30
DASHBOARD_SERIES_RECENT_MINUTES = 15
DASHBOARD_SERIES_ARCHIVE_BUCKET_SECONDS = 60 * 60


def dashboard_series_sensor_keys() -> list[str]:
    keys = [str(metric["sensor_key"]).strip() for metric in DASHBOARD_SERIES_METRICS]
    keys.extend(f"{row_key}-moisture" for row_key in VALID_CULTIVATION_ROWS)
    keys.extend(f"{row_key}-rs485" for row_key in VALID_CULTIVATION_ROWS)
    return list(dict.fromkeys(key for key in keys if key))


def list_sensor_reading_history_by_key(
    connection: sqlite3.Connection,
    sensor_keys: list[str],
    *,
    limit: int = DASHBOARD_SERIES_HISTORY_LIMIT,
    retention_days: int | None = None,
) -> dict[str, list[sqlite3.Row]]:
    """Bucketed reading history per sensor, over the window the caller will draw.

    The cap used to be applied by the loop at the bottom, which meant every
    bucket-rank-1 row inside the retention window crossed the wire first and was
    then thrown away -- thirty days of hourly buckets plus the recent window,
    for every charted sensor, on a request the dashboards repeat constantly.
    `capped_history` drops them in the database instead, so only the rows that
    survive are ever transferred.

    `retention_days` narrows how far back the scan goes. Cost is close to linear
    in the window: measured against thirty days of readings from this farm's
    fifteen charted sensors, a full month took 10.5 s and a single day 0.3 s. The
    dashboard opens on the Real Time range, so asking for a month to draw the
    last few minutes was most of what a reload spent waiting.
    """
    normalized_keys = list(dict.fromkeys(normalize_sensor_key(key) for key in sensor_keys if normalize_sensor_key(key)))
    if not normalized_keys:
        return {}

    placeholders = ", ".join("?" for _ in normalized_keys)
    now = utc_now()
    recent_cutoff = (now - timedelta(minutes=DASHBOARD_SERIES_RECENT_MINUTES)).isoformat()
    window_days = (
        DASHBOARD_SERIES_RETENTION_DAYS
        if retention_days is None
        else max(1, min(DASHBOARD_SERIES_RETENTION_DAYS, int(retention_days)))
    )
    retention_cutoff = (now - timedelta(days=window_days)).isoformat()
    # Two passes, one per half of the series, instead of one window over
    # everything.
    #
    # This used to run a single ROW_NUMBER() over every row in the retention
    # window and then keep one per hourly bucket. The window function cannot be
    # evaluated until the whole set is materialised and sorted, so the planner
    # read the lot: Supabase's own EXPLAIN showed a Parallel Seq Scan of 944,828
    # rows -- 35% of the table -- to produce about 10,800. Each run took 29-45
    # seconds, and the sort spilled to temporary files, which is where the
    # "could not write to file ... No space left on device" errors came from.
    #
    # Splitting it lets each half use idx_sensor_readings_sensor_key_captured_at:
    #
    #   recent   a short, bounded range per sensor -- an index range scan.
    #   archive  one row per hourly bucket, chosen with MIN(id) over a grouped
    #            scan rather than by ranking every row and discarding the rest.
    #
    # The result is identical: newest-first, one row per bucket outside the
    # recent window, every row inside it, capped per sensor. Only the amount of
    # data read to get there changes.
    recent_rows = connection.execute(
        f"""
        SELECT
            id,
            sensor_key,
            reading_payload_json,
            source_type,
            source_identifier,
            captured_at
        FROM sensor_readings
        WHERE sensor_key IN ({placeholders})
          AND captured_at >= ?
          AND LOWER(TRIM(COALESCE(source_type, ''))) NOT IN ('seed', 'hybrid-sync-test')
          AND LOWER(TRIM(COALESCE(source_identifier, ''))) NOT IN (
              'default-backfill',
              'seed-simulator'
          )
        ORDER BY sensor_key ASC, captured_at DESC, id DESC
        """,  # nosec B608 - only '?' placeholders interpolated; values are bound parameters
        (*normalized_keys, recent_cutoff),
    ).fetchall()

    # One row per sensor per hourly bucket, for the part of the window older
    # than the recent cutoff. GROUP BY lets the database discard duplicates as
    # it scans instead of carrying every row into a sort.
    #
    # The row kept is the newest by captured_at, not MAX(id). On the Pi id grows
    # with captured_at, but Supabase numbers rows in the order the sync
    # delivered them, so MAX(id) there picked a different reading out of the
    # same hour -- and the kiosk and the website drew different 24 Hours and
    # 7 Days lines from identical data. captured_at is the same on both.
    archive_rows = connection.execute(
        f"""
        SELECT
            r.id,
            r.sensor_key,
            r.reading_payload_json,
            r.source_type,
            r.source_identifier,
            r.captured_at
        FROM sensor_readings AS r
        JOIN (
            SELECT sensor_key, MAX(captured_at) AS captured_at
            FROM sensor_readings
            WHERE sensor_key IN ({placeholders})
              AND captured_at >= ?
              AND captured_at < ?
              AND LOWER(TRIM(COALESCE(source_type, ''))) NOT IN ('seed', 'hybrid-sync-test')
              AND LOWER(TRIM(COALESCE(source_identifier, ''))) NOT IN (
                  'default-backfill',
                  'seed-simulator'
              )
            GROUP BY
                sensor_key,
                CAST(
                    CAST(strftime('%s', captured_at) AS INTEGER)
                    / {DASHBOARD_SERIES_ARCHIVE_BUCKET_SECONDS}
                    AS INTEGER
                )
        ) AS picked ON picked.sensor_key = r.sensor_key AND picked.captured_at = r.captured_at
        WHERE LOWER(TRIM(COALESCE(r.source_type, ''))) NOT IN ('seed', 'hybrid-sync-test')
          AND LOWER(TRIM(COALESCE(r.source_identifier, ''))) NOT IN (
              'default-backfill',
              'seed-simulator'
          )
        ORDER BY r.sensor_key ASC, r.captured_at DESC, r.id DESC
        """,  # nosec B608 - only '?' placeholders / module constants interpolated; values are bound parameters
        (*normalized_keys, retention_cutoff, recent_cutoff),
    ).fetchall()
    # Two rows stored with the same stamp would both match the join; keep one.
    seen_archive: set[tuple[str, str]] = set()
    unique_archive = []
    for row in archive_rows:
        identity = (str(row["sensor_key"]), str(row["captured_at"]))
        if identity not in seen_archive:
            seen_archive.add(identity)
            unique_archive.append(row)
    archive_rows = unique_archive

    # Recent first, then archive, and both already newest-first within a
    # sensor -- so concatenating them keeps the whole series newest-first, which
    # is what the per-sensor limit below relies on to keep the NEWEST rows when
    # it truncates. Sorting again here would mean materialising every row a
    # second time in Python for an order the database already produced.
    rows = list(recent_rows) + list(archive_rows)

    # The per-sensor cap is applied here, not in SQL.
    #
    # The old query ranked and capped in the database, which is part of why it
    # had to materialise everything. Doing it here costs one pass over rows that
    # are already the only ones read, and it keeps the two halves in the right
    # relationship: recent rows are appended first, so if a sensor has more than
    # `limit` rows in the recent window alone, the newest are the ones kept and
    # the archive tail is dropped -- which is the correct trade for a graph that
    # reads newest-first.
    history: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        sensor_key = str(row["sensor_key"]).strip()
        bucket = history.setdefault(sensor_key, [])
        if len(bucket) < limit:
            bucket.append(row)

    # Reversed so each series runs oldest-first, which is the order a chart
    # plots. The rows arrived newest-first because that is the order the cap
    # above needs.
    return {key: list(reversed(items)) for key, items in history.items()}


def sensor_series_points(
    readings: list[sqlite3.Row] | list[dict[str, object]],
    *,
    metric_key: str,
    value_of=None,
) -> list[dict[str, object]]:
    points: list[dict[str, object]] = []
    for reading in readings:
        value = value_of(reading) if value_of else reading_metric_value(reading, metric_key)
        if value is None:
            continue
        points.append(
            {
                "value": round(value, 2),
                "capturedAt": reading_captured_at(reading),
            }
        )
    return points


def aggregate_row_sensor_series_points(
    history_by_key: dict[str, list[sqlite3.Row]] | dict[str, list[dict[str, object]]],
    *,
    sensor_keys: list[str],
    metric_key: str,
) -> list[dict[str, object]]:
    buckets: dict[int, dict[str, object]] = {}
    for sensor_key in sensor_keys:
        for reading in history_by_key.get(sensor_key, []):
            value = reading_metric_value(reading, metric_key)
            captured_at = reading_captured_at(reading)
            if value is None or not captured_at:
                continue
            try:
                bucket_key = int(parse_iso_datetime(captured_at).timestamp() // 10)
            except ValueError:
                continue
            bucket = buckets.setdefault(bucket_key, {"values": [], "capturedAt": captured_at})
            values = bucket["values"]
            assert isinstance(values, list)
            values.append(value)
            if captured_at > str(bucket["capturedAt"]):
                bucket["capturedAt"] = captured_at

    # fsum, not sum: it does not depend on the order the rows arrived in. The Pi
    # and Supabase return a bucket's rows in different orders, and a plain sum
    # rounded 5.975 to 5.97 on one and 5.98 on the other.
    return [
        {
            "value": round(math.fsum(bucket["values"]) / len(bucket["values"]), 2),
            "capturedAt": str(bucket["capturedAt"]),
        }
        for _, bucket in sorted(buckets.items())
        if isinstance(bucket["values"], list) and bucket["values"]
    ]


DASHBOARD_ROW_DAILY_SERIES_DAYS = 30
DASHBOARD_ROW_DAILY_SERIES_SOURCES = (
    # (metric key, row sensor suffix, key to read out of the stored payload)
    ("moisture", "moisture", "moisture"),
    ("ec", "rs485", "ec"),
    ("ph", "rs485", "ph"),
)


def build_row_daily_series(
    history_by_key: dict[str, list[sqlite3.Row]] | dict[str, list[dict[str, object]]],
) -> dict[str, object]:
    """Per-row daily averages, for the cultivation graph's Row Health bars.

    Every other series in this payload is a single shared line, so none of them
    can say anything about one row in particular. The per-row history is already
    loaded here for the aggregate fallback above, so the only cost is folding it
    down to one point per calendar day: roughly thirty small points per metric
    instead of the nine hundred raw readings a full series would push to the
    kiosk and to every phone on each refresh.
    """
    rows: dict[str, object] = {}
    for row_key in VALID_CULTIVATION_ROWS:
        metrics: dict[str, list[dict[str, object]]] = {}
        for metric_key, sensor_suffix, reading_key in DASHBOARD_ROW_DAILY_SERIES_SOURCES:
            buckets: dict[str, list[float]] = {}
            for reading in history_by_key.get(f"{row_key}-{sensor_suffix}", []):
                value = reading_metric_value(reading, reading_key)
                captured_at = reading_captured_at(reading)
                if value is None or len(captured_at) < 10:
                    continue
                buckets.setdefault(captured_at[:10], []).append(value)
            metrics[metric_key] = [
                # fsum: order-free, so the kiosk and the website agree.
                {"date": day, "value": round(math.fsum(values) / len(values), 2)}
                for day, values in sorted(buckets.items())
                if values
            ][-DASHBOARD_ROW_DAILY_SERIES_DAYS:]
        rows[row_key] = metrics
    return rows


def build_sensor_series_payload(
    history_by_key: dict[str, list[sqlite3.Row]] | dict[str, list[dict[str, object]]],
    latest_readings: dict[str, sqlite3.Row] | dict[str, dict[str, object]],
    greenhouse_bounds: dict[str, tuple[float, float]] | None = None,
) -> dict[str, object]:
    metrics: dict[str, list[dict[str, object]]] = {}

    for metric in DASHBOARD_SERIES_METRICS:
        sensor_key = str(metric["sensor_key"]).strip()
        readings = list(history_by_key.get(sensor_key, []))
        if not readings and sensor_key in latest_readings:
            readings = [latest_readings[sensor_key]]
        metric_key = str(metric["key"])
        reading_key = str(metric["metric_key"])
        # The greenhouse air as the cards showed it, the same number the live
        # poll appends for that reading (greenhouse_card_value_at_capture).
        value_of = (
            (lambda reading, reading_key=reading_key: greenhouse_card_value_at_capture(
                reading, reading_key, greenhouse_bounds
            ))
            if sensor_key == "dht22"
            else None
        )
        points = sensor_series_points(readings, metric_key=reading_key, value_of=value_of)
        if not points and metric_key in {"moisture", "ec", "ph"}:
            sensor_suffix = "moisture" if metric_key == "moisture" else "rs485"
            points = aggregate_row_sensor_series_points(
                history_by_key,
                sensor_keys=[f"{row_key}-{sensor_suffix}" for row_key in VALID_CULTIVATION_ROWS],
                metric_key="moisture" if metric_key == "moisture" else metric_key,
            )
        metrics[metric_key] = points

    return {
        "metrics": metrics,
        "rows": build_row_daily_series(history_by_key),
        "rowMetrics": build_row_metric_series(history_by_key),
    }


def build_row_metric_series(
    history_by_key: dict[str, list[sqlite3.Row]] | dict[str, list[dict[str, object]]],
) -> dict[str, object]:
    """Each row's own moisture, EC and pH trace, for the dashboard graph.

    The dashboard shows one row's cards, but its graph drew the shared
    `metrics` lines, which average every row's boards together -- a row whose
    probe read 0% sat above a graph reading 28%, because the other rows were
    wet. The history is already loaded per row key for the aggregate, so this
    costs no extra read; it only stops throwing the row apart away.
    """
    rows: dict[str, object] = {}
    for row_key in VALID_CULTIVATION_ROWS:
        metrics: dict[str, list[dict[str, object]]] = {}
        for metric_key, sensor_suffix, reading_key in DASHBOARD_ROW_DAILY_SERIES_SOURCES:
            points = sensor_series_points(
                history_by_key.get(f"{row_key}-{sensor_suffix}", []),
                metric_key=reading_key,
            )
            metrics[metric_key] = [point for point in points if point["capturedAt"]]
        rows[row_key] = metrics
    return rows


# A percentage and the word for its opposite, jammed together, reads as a
# contradiction on every card that is not actually full -- and it once hid a
# real calibration fault for weeks, because nobody could tell whether the probe
# or the label was wrong. A level gets a name of its own, and "Full" is
# reserved for something that measures full.
def build_sensor_registry_payload(sensor: sqlite3.Row) -> dict[str, object]:
    raw_alert_mode = str(sensor["alert_mode"]).strip()
    return {
        "id": str(sensor["id"]),
        "sensorKey": str(sensor["sensor_key"]).strip(),
        "definitionKey": str(sensor["definition_key"] or "").strip(),
        "backendKey": str(sensor["backend_key"] or "").strip(),
        "displayName": str(sensor["display_name"]).strip(),
        "deviceName": str(sensor["device_name"]).strip(),
        "rowKey": str(sensor["row_key"]).strip(),
        "category": str(sensor["category"]).strip(),
        "powerState": normalize_sensor_power_state(sensor["power_state"]),
        "actuatorMode": normalize_actuator_mode(sensor["actuator_mode"], str(sensor["sensor_key"])),
        "alertMode": normalize_sensor_alert_mode(raw_alert_mode, allow_empty=not raw_alert_mode),
        "hardwareIdentifier": str(sensor["hardware_identifier"]).strip(),
        "metricKeys": parse_json_string_list(sensor["metric_keys_json"]),
        "metadata": parse_json_object(sensor["metadata_json"]),
        "createdAt": str(sensor["created_at"]).strip(),
        "updatedAt": str(sensor["updated_at"]).strip(),
    }


def sensor_control_state(sensor_registry: dict[str, sqlite3.Row], sensor_key: str, default: str = "on") -> str:
    sensor = sensor_registry.get(sensor_key)
    if not sensor:
        return default
    return normalize_sensor_power_state(sensor["power_state"])


def actuator_control_state(
    sensor_registry: dict[str, sqlite3.Row], sensor_key: str, default: str = ""
) -> str:
    """This actuator's stored mode, in a mode the actuator actually has.

    The fallback runs the key through normalize_actuator_mode rather than
    returning a bare "automatic". A manual-only actuator has no Automatic, and
    build_relay_desired_state resolves Automatic to off for it -- so a missing
    registry row used to cache a mode that reads as an automation and leaves
    the line dead. The environment refresh does this every cycle, which is
    enough to overwrite a fresh On press.
    """
    sensor = sensor_registry.get(sensor_key)
    if not sensor:
        return normalize_actuator_mode(default, sensor_key)
    return normalize_actuator_mode(sensor["actuator_mode"], sensor_key)


def hardware_sensor_power_states(
    sensor_registry: dict[str, sqlite3.Row] | dict[str, dict[str, object]],
) -> dict[str, str]:
    sensor_keys = ["moisture", "ec", "ph", "dht22"]
    sensor_keys.extend(
        f"{row_key}-{sensor_type}"
        for row_key in VALID_CULTIVATION_ROWS
        for sensor_type in ("moisture", "rs485")
    )
    return {
        sensor_key: sensor_control_state(sensor_registry, sensor_key)
        for sensor_key in sensor_keys
    }


def hardware_identifier_for(sensor_registry: dict[str, sqlite3.Row], sensor_key: str) -> str:
    sensor = sensor_registry.get(sensor_key)
    return str(sensor["hardware_identifier"]).strip() if sensor else ""


def dashboard_metric_value(latest_readings: dict[str, sqlite3.Row], metric_key: str) -> float | None:
    direct_sensor_map = {
        "moisture": "moisture",
        "ph": "ph",
        "ec": "ec",
    }
    if metric_key in direct_sensor_map:
        direct_value = reading_metric_value(latest_readings.get(direct_sensor_map[metric_key]), "value")
        if direct_value is not None:
            return direct_value

    if metric_key in {"temp", "humidity"}:
        return reading_metric_value(latest_readings.get("dht22"), metric_key)

    if metric_key == "moisture":
        return average_numeric(
            [reading_metric_value(latest_readings.get(f"{row_key}-moisture"), "moisture") for row_key in VALID_CULTIVATION_ROWS]
        )

    if metric_key in {"ec", "ph"}:
        return average_numeric(
            [reading_metric_value(latest_readings.get(f"{row_key}-rs485"), metric_key) for row_key in VALID_CULTIVATION_ROWS]
        )

    return None


def latest_sensor_capture_for_keys(
    latest_readings: dict[str, sqlite3.Row] | dict[str, dict[str, object]],
    sensor_keys: list[str],
) -> str:
    captured_values = [
        reading_captured_at(latest_readings.get(sensor_key))
        for sensor_key in sensor_keys
    ]
    parsed_values: list[tuple[datetime, str]] = []
    for value in captured_values:
        if not value:
            continue
        try:
            parsed_values.append((parse_iso_datetime(value), value))
        except ValueError:
            continue
    if not parsed_values:
        return ""
    return max(parsed_values, key=lambda item: item[0])[1]


def build_sensor_overview_payload(
    connection: sqlite3.Connection,
    *,
    include_history: bool = True,
    include_catalog: bool = True,
    history_days: int | None = None,
) -> dict[str, object]:
    """The dashboard payload, built with the greenhouse fit in force.

    The cards, the history series and the alert evaluation inside all read the
    greenhouse DHT22 through reading_metric_value, so they are built inside one
    scope. Otherwise the number on the card and the number an alert fired on
    would be different, which is the specific failure the fit exists to avoid.
    """
    with bench_fit_scope(list_cultivations(connection)):
        return _build_sensor_overview_payload(
            connection,
            include_history=include_history,
            include_catalog=include_catalog,
            history_days=history_days,
        )


def _build_sensor_overview_payload(
    connection: sqlite3.Connection,
    *,
    include_history: bool = True,
    include_catalog: bool = True,
    history_days: int | None = None,
) -> dict[str, object]:
    registry_rows = list_sensor_registry(connection)
    sensor_registry = {str(row["sensor_key"]).strip(): row for row in registry_rows}
    latest_readings = latest_sensor_readings_by_key(connection)
    mqtt_status = mqtt_node_status_map(connection)
    climate_bounds = greenhouse_climate_bounds(list_cultivations(connection))
    covered_days = (
        DASHBOARD_SERIES_RETENTION_DAYS
        if history_days is None
        else max(1, min(DASHBOARD_SERIES_RETENTION_DAYS, int(history_days)))
    )
    if include_history:
        history_by_key = list_sensor_reading_history_by_key(
            connection,
            dashboard_series_sensor_keys(),
            limit=DASHBOARD_SERIES_HISTORY_LIMIT,
            retention_days=covered_days,
        )
        series = build_sensor_series_payload(history_by_key, latest_readings, climate_bounds)
    else:
        series = {"metrics": {}, "rows": {}}

    controls = {
        "sensorPower": {
            "moisture": sensor_control_state(sensor_registry, "moisture"),
            "ph": sensor_control_state(sensor_registry, "ph"),
            "ec": sensor_control_state(sensor_registry, "ec"),
            "dht22": sensor_control_state(sensor_registry, "dht22"),
        },
        "rowSensorPower": {
            **{
                f"{row_key}-moisture": sensor_control_state(sensor_registry, f"{row_key}-moisture")
                for row_key in VALID_CULTIVATION_ROWS
            },
            **{
                f"{row_key}-rs485": sensor_control_state(sensor_registry, f"{row_key}-rs485")
                for row_key in VALID_CULTIVATION_ROWS
            },
            "dht22": sensor_control_state(sensor_registry, "dht22"),
        },
        "actuatorMode": {
            # Every actuator here reaches a relay, and its mode is stored and
            # served so the choice survives a reload.
            key: actuator_control_state(sensor_registry, key)
            for key in ENVIRONMENT_ACTUATOR_KEYS
        },
    }

    # The greenhouse air as the rules see it (DHT22 plus the fan and lamp's
    # effect) for the cards, and the DHT22 as measured for the sensor card.
    # Hosted, the effect is the Pi's own as the relay last delivered it.
    relayed = relayed_greenhouse_response(connection)
    climate = greenhouse_climate_values(
        latest_readings,
        relayed=relayed,
        bounds=climate_bounds,
    )
    # What the cards show: the kiosk's own eased numbers when there are some,
    # on the Pi and (relayed) on the website alike. The alerts and rules keep
    # reading `climate`, exactly as before.
    shown = greenhouse_display_values(latest_readings, relayed)
    card_climate = {**climate, **shown} if shown else climate
    sensors = {
        "moisture": {
            "value": dashboard_metric_value(latest_readings, "moisture"),
            "capturedAt": latest_sensor_capture_for_keys(
                latest_readings,
                ["moisture", *[f"{row_key}-moisture" for row_key in VALID_CULTIVATION_ROWS]],
            ),
            "hardwareIdentifier": hardware_identifier_for(sensor_registry, "moisture"),
            "alertMode": normalize_sensor_alert_mode(sensor_registry["moisture"]["alert_mode"]) if "moisture" in sensor_registry else DEFAULT_SENSOR_ALERT_MODE,
        },
        "ph": {
            "value": dashboard_metric_value(latest_readings, "ph"),
            "capturedAt": latest_sensor_capture_for_keys(
                latest_readings,
                ["ph", *[f"{row_key}-rs485" for row_key in VALID_CULTIVATION_ROWS]],
            ),
            "hardwareIdentifier": hardware_identifier_for(sensor_registry, "ph"),
            "alertMode": normalize_sensor_alert_mode(sensor_registry["ph"]["alert_mode"]) if "ph" in sensor_registry else DEFAULT_SENSOR_ALERT_MODE,
        },
        "ec": {
            "value": dashboard_metric_value(latest_readings, "ec"),
            "capturedAt": latest_sensor_capture_for_keys(
                latest_readings,
                ["ec", *[f"{row_key}-rs485" for row_key in VALID_CULTIVATION_ROWS]],
            ),
            "hardwareIdentifier": hardware_identifier_for(sensor_registry, "ec"),
            "alertMode": normalize_sensor_alert_mode(sensor_registry["ec"]["alert_mode"]) if "ec" in sensor_registry else DEFAULT_SENSOR_ALERT_MODE,
        },
        "temp": {
            "value": card_climate["temp"],
            # The graph's point for this reading. The card above is eased and
            # moves between readings; this is fixed per reading, and matches
            # the history series exactly.
            "seriesValue": greenhouse_card_value_at_capture(
                latest_readings.get("dht22"), "temp", climate_bounds
            ),
            "capturedAt": reading_captured_at(latest_readings.get("dht22")),
            "hardwareIdentifier": hardware_identifier_for(sensor_registry, "dht22"),
            "alertMode": normalize_sensor_alert_mode(sensor_registry["dht22"]["alert_mode"]) if "dht22" in sensor_registry else DEFAULT_SENSOR_ALERT_MODE,
        },
        "humidity": {
            "value": card_climate["humidity"],
            # The graph's point for this reading. The card above is eased and
            # moves between readings; this is fixed per reading, and matches
            # the history series exactly.
            "seriesValue": greenhouse_card_value_at_capture(
                latest_readings.get("dht22"), "humidity", climate_bounds
            ),
            "capturedAt": reading_captured_at(latest_readings.get("dht22")),
            "hardwareIdentifier": hardware_identifier_for(sensor_registry, "dht22"),
            "alertMode": normalize_sensor_alert_mode(sensor_registry["dht22"]["alert_mode"]) if "dht22" in sensor_registry else DEFAULT_SENSOR_ALERT_MODE,
        },
    }

    # One read for the whole payload rather than one per card.
    pi_alive = pi_heartbeat_is_fresh(connection)

    rows: list[dict[str, object]] = []
    for row_key in VALID_CULTIVATION_ROWS:
        moisture_sensor_key = f"{row_key}-moisture"
        rs485_sensor_key = f"{row_key}-rs485"
        rows.append(
            {
                "key": row_key,
                "label": cultivation_row_label(row_key),
                "moisture": reading_metric_value(latest_readings.get(moisture_sensor_key), "moisture"),
                "ec": reading_metric_value(latest_readings.get(rs485_sensor_key), "ec"),
                "ph": reading_metric_value(latest_readings.get(rs485_sensor_key), "ph"),
                "capturedAt": {
                    "moisture": reading_captured_at(latest_readings.get(moisture_sensor_key)),
                    "rs485": reading_captured_at(latest_readings.get(rs485_sensor_key)),
                },
                "hardwareIdentifiers": {
                    "moisture": hardware_identifier_for(sensor_registry, moisture_sensor_key),
                    "rs485": hardware_identifier_for(sensor_registry, rs485_sensor_key),
                },
                # True/False when the owning ESP32's MQTT status is tracked;
                # None when it never has been, so the frontend falls back to
                # judging the last reading's age instead.
                "connected": {
                    "moisture": sensor_key_connection_state(
                        mqtt_status, moisture_sensor_key, latest_readings, pi_alive
                    ),
                    "rs485": sensor_key_connection_state(
                        mqtt_status, rs485_sensor_key, latest_readings, pi_alive
                    ),
                },
            }
        )

    shared_metrics = {
        "temp": card_climate["temp"],
        "humidity": card_climate["humidity"],
        "measured": climate["measured"],
        # True when the Pi's control cycle is modelling the fan and lamp's
        # effect; the dashboards then show these numbers as they are rather
        # than running their own copy of the model.
        "modelled": climate["modelled"],
        # True when these numbers are the Pi's control cycle's (on the Pi, or
        # relayed to the hosted API): the dashboards show them as they are,
        # modelled or not, instead of stepping a copy of the model per browser.
        "authoritative": climate["authoritative"],
        # True when temp/humidity are the kiosk's eased cards: shown exactly as
        # sent, with no easing of their own (greenhouse_display_step).
        "eased": shown is not None,
        "capturedAt": reading_captured_at(latest_readings.get("dht22")),
        "connected": sensor_key_connection_state(
            mqtt_status, "dht22", latest_readings, pi_alive
        ),
    }

    response: dict[str, object] = {
        "live": not include_history,
        # What the series actually covers, so a dashboard switching to a longer
        # graph range knows whether it already holds the rows or has to ask.
        "historyDays": covered_days if include_history else 0,
        "sensors": sensors,
        "rows": rows,
        "sharedMetrics": shared_metrics,
        "controls": controls,
        # The thresholds the automatic fan and grow light rules are judged against.
        # The sensors page needs them to tell someone reaching for a manual On
        # that the greenhouse is already inside its target.
        "automation": build_actuator_automation_payload(
            list_cultivations(connection), latest_readings, climate=climate
        ),
    }
    if include_history:
        response["series"] = series
    if include_catalog:
        response.update(
            {
                "definitions": [build_sensor_definition_payload(row) for row in list_sensor_definitions(connection)],
                "backends": [build_sensor_backend_payload(row) for row in list_sensor_backends(connection)],
                "registry": [build_sensor_registry_payload(row) for row in registry_rows],
            }
        )
    return response


def list_irrigation_settings(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            channel_key,
            label,
            automatic_enabled,
            automatic_duration_seconds,
            manual_duration_seconds,
            schedule_enabled,
            schedule_start_time,
            schedule_duration_seconds,
            schedule_frequency,
            updated_at
        FROM irrigation_settings
        ORDER BY channel_key ASC
        """
    ).fetchall()


def list_irrigation_row_settings(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    ensure_irrigation_row_schema(connection)
    return connection.execute(
        """
        SELECT
            cultivation_id,
            row_key,
            channel_key,
            automatic_enabled,
            automatic_duration_seconds,
            manual_duration_seconds,
            schedule_enabled,
            schedule_start_time,
            schedule_duration_seconds,
            schedule_frequency,
            updated_at
        FROM irrigation_row_settings
        ORDER BY row_key ASC, channel_key ASC
        """
    ).fetchall()


def list_irrigation_row_controls(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    ensure_irrigation_row_schema(connection)
    return connection.execute(
        """
        SELECT cultivation_id, row_key, mode, is_enabled, updated_at
        FROM irrigation_row_controls
        ORDER BY row_key ASC
        """
    ).fetchall()


def irrigation_run_deadline_times(connection: sqlite3.Connection) -> dict[str, dict[str, datetime]]:
    """When each active timed run ends, keyed channel -> row.

    Automatic runs are excluded, the same as in the function below: they end on
    a moisture reading, not on a clock, so there is no deadline to send and a
    board must not invent one. A run already due is left out too; the ordinary
    expiry closes it.
    """
    now = utc_now()
    deadlines: dict[str, dict[str, datetime]] = {}
    for run in connection.execute(
        """
        SELECT id, channel_key, mode, duration_seconds, started_at
        FROM irrigation_runs
        WHERE status = 'active'
        """
    ).fetchall():
        if normalize_irrigation_mode(run["mode"]) == "automatic":
            continue
        duration_seconds = max(
            IRRIGATION_MIN_DURATION_SECONDS, int(run["duration_seconds"] or 0)
        )
        try:
            ends_at = parse_iso_datetime(run["started_at"]) + timedelta(seconds=duration_seconds)
        except (TypeError, ValueError):
            # Handled by the ordinary sweep; it must not stop the others from
            # being timed accurately.
            continue
        if ends_at <= now:
            # Already due. Sending 0 would read as "no deadline" on the board,
            # which is the opposite of what is meant, so leave it out and let
            # the ordinary expiry close it.
            continue
        channel_key = str(run["channel_key"]).strip()
        rows = deadlines.setdefault(channel_key, {})
        for row in connection.execute(
            "SELECT row_key FROM irrigation_run_rows WHERE irrigation_run_id = ? AND status = 'active'",
            (int(run["id"]),),
        ).fetchall():
            row_key = str(row["row_key"]).strip()
            # Two runs on one row: the sooner ending wins. Holding the valve
            # for the longer of them is the failure this whole path exists to
            # prevent.
            if row_key not in rows or ends_at < rows[row_key]:
                rows[row_key] = ends_at
    return {channel: rows for channel, rows in deadlines.items() if rows}


def epoch_ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def irrigation_run_deadlines_ms(connection: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Milliseconds left on each active timed run, keyed channel -> row.

    The relay commands built from this carry the remaining time with them, so
    the ESP32 holding the valve closes it on its own clock. Everything between
    the deadline and the coil -- the control worker, SQLite, the MQTT bridge,
    the network -- then stops being able to make a run longer than it was
    asked to be. On this farm that mattered: a blocked Postgres port was
    stalling the backend for up to 169 seconds at a time, and a two second run
    measured almost seven.
    """
    now = utc_now()
    deadlines: dict[str, dict[str, int]] = {}
    for channel_key, rows in irrigation_run_deadline_times(connection).items():
        for row_key, ends_at in rows.items():
            remaining_ms = int((ends_at - now).total_seconds() * 1000)
            if remaining_ms > 0:
                deadlines.setdefault(channel_key, {})[row_key] = remaining_ms
    return deadlines


def irrigation_run_deadlines_at_ms(connection: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """The same deadlines as wall-clock epoch milliseconds.

    The remaining time above is only true at the instant it was computed, and
    the relay snapshot is rebuilt from a cached copy of this payload whenever a
    fan, lamp or sensor switch changes. Rebuilt from the old remaining time, a
    ten second run halfway through was handed another full ten seconds and the
    board restarted its countdown. An absolute deadline cannot go stale: the
    remaining time is worked out from it at the moment the command is sent.
    """
    return {
        channel_key: {row_key: epoch_ms(ends_at) for row_key, ends_at in rows.items()}
        for channel_key, rows in irrigation_run_deadline_times(connection).items()
    }


def seconds_until_next_irrigation_deadline(connection: sqlite3.Connection) -> float | None:
    """Seconds until the soonest timed run is due to stop, or None if none are.

    The control worker otherwise only looks every
    IRRIGATION_CONTROL_INTERVAL_SECONDS, so a run shorter than that interval
    keeps the relay open until the next sweep happens to notice -- a five
    second run could hold the valve for fifteen. Polling faster would cost a
    Pi core all day to catch the few seconds a run is actually ending, so the
    worker instead asks when to wake up next and sleeps exactly that long.

    Automatic runs are excluded for the same reason expire_due_irrigation_runs
    skips them: they end on a moisture reading, not on a clock.
    """
    now = utc_now()
    soonest: float | None = None
    for run in connection.execute(
        """
        SELECT mode, duration_seconds, started_at
        FROM irrigation_runs
        WHERE status = 'active'
        """
    ).fetchall():
        if normalize_irrigation_mode(run["mode"]) == "automatic":
            continue
        duration_seconds = max(
            IRRIGATION_MIN_DURATION_SECONDS, int(run["duration_seconds"] or 0)
        )
        try:
            ends_at = parse_iso_datetime(run["started_at"]) + timedelta(seconds=duration_seconds)
        except (TypeError, ValueError):
            # An unreadable timestamp is handled by the ordinary sweep; it must
            # not stop the others from being timed accurately.
            continue
        remaining = (ends_at - now).total_seconds()
        if soonest is None or remaining < soonest:
            soonest = remaining

    if soonest is None:
        return None
    # Already due -- the caller should come straight back rather than sleep.
    return max(0.0, soonest)


def expire_due_irrigation_runs(connection: sqlite3.Connection) -> None:
    now = utc_now()
    active_runs = connection.execute(
        """
        SELECT id, channel_key, mode, duration_seconds, started_at
        FROM irrigation_runs
        WHERE status = 'active'
        ORDER BY started_at ASC, id ASC
        """
    ).fetchall()
    expired: list[sqlite3.Row] = []
    for run in active_runs:
        # Automatic irrigation is controlled by the live crop parameter, not
        # by a timer. It stays active while the reading is below the configured
        # minimum and is stopped by reconciliation as soon as that minimum is
        # reached. Manual and scheduled runs remain duration-based.
        if normalize_irrigation_mode(run["mode"]) == "automatic":
            continue
        duration_seconds = max(
            IRRIGATION_MIN_DURATION_SECONDS, int(run["duration_seconds"] or 0)
        )
        if parse_iso_datetime(run["started_at"]) + timedelta(seconds=duration_seconds) <= now:
            expired.append(run)
    if not expired:
        return

    timestamp = utc_now_iso()
    state_values = system_state_map(connection)
    mode_rows = {
        "manual": normalize_irrigation_channel_row_map(state_values.get("irrigation.active_manual_rows")),
        "schedule": normalize_irrigation_channel_row_map(state_values.get("irrigation.active_schedule_rows")),
        "automatic": normalize_irrigation_channel_row_map(state_values.get("irrigation.active_automatic_rows")),
    }
    for run in expired:
        run_id = int(run["id"])
        run_mode = normalize_irrigation_mode(run["mode"])
        channel_key = str(run["channel_key"]).strip()
        expired_rows = [
            str(row["row_key"]).strip()
            for row in connection.execute(
                "SELECT row_key FROM irrigation_run_rows WHERE irrigation_run_id = ? AND status = 'active'",
                (run_id,),
            ).fetchall()
        ]
        connection.execute(
            "UPDATE irrigation_runs SET status = 'completed', ended_at = ?, notes = ? WHERE id = ?",
            (timestamp, f"{run_mode.title()} irrigation completed its duration.", run_id),
        )
        connection.execute(
            """
            UPDATE irrigation_run_rows
            SET status = 'completed', ended_at = ?
            WHERE irrigation_run_id = ? AND status = 'active'
            """,
            (timestamp, run_id),
        )
        channel_rows = mode_rows[run_mode].get(channel_key, {})
        for row_key in expired_rows:
            channel_rows.pop(row_key, None)
        if channel_rows:
            mode_rows[run_mode][channel_key] = channel_rows
        else:
            mode_rows[run_mode].pop(channel_key, None)

    for run_mode, channel_rows in mode_rows.items():
        set_system_state_value(
            connection,
            key=f"irrigation.active_{run_mode}_rows",
            value=json_dumps_compact(channel_rows),
        )
        set_system_state_value(
            connection,
            key=f"irrigation.active_{run_mode}_lines",
            value=json_dumps_compact(irrigation_lines_from_row_map(channel_rows)),
        )
    set_system_state_value(
        connection,
        key="irrigation.active_manual_line",
        value=first_active_irrigation_line(irrigation_lines_from_row_map(mode_rows["manual"])),
    )


def irrigation_parameter_range(cultivation: object, metric_key: str) -> dict[str, float] | None:
    if cultivation is None:
        return None
    raw_parameters = cultivation["parameters_json"]
    parameters = parse_json_object(raw_parameters)
    metric_range = parameters.get(metric_key)
    if not isinstance(metric_range, dict):
        return None
    minimum = normalize_numeric_value(metric_range.get("min"))
    maximum = normalize_numeric_value(metric_range.get("max"))
    if minimum is None or maximum is None or minimum >= maximum:
        return None
    return {"min": round(minimum, 2), "max": round(maximum, 2)}


def irrigation_row_sensor_value(
    latest_readings: dict[str, sqlite3.Row] | dict[str, dict[str, object]],
    row_key: str,
    channel_key: str,
) -> float | None:
    sensor_suffix, metric_key = IRRIGATION_CHANNEL_SENSOR_METRICS[channel_key]
    return reading_metric_value(latest_readings.get(f"{row_key}-{sensor_suffix}"), metric_key)


def rs485_probe_out_of_soil(reading: sqlite3.Row | dict[str, object] | None) -> bool:
    """True when the soil board says this RS485 probe is not in soil.

    The firmware's soil-present gate publishes pH 0.0 and EC 0.0 for a probe
    lifted out of the row. pH 0 is battery acid, never soil, so it is the
    marker and not a reading. Read as one, it was "far below the crop's
    minimum": the tank card asked for pH Up on a probe lying on the bench, and
    a confirmed tank would have dosed a row nothing was measuring. The EC it
    zeroes with it would call for fertilizer the same way.
    """
    ph = reading_metric_value(reading, "ph")
    return ph is not None and ph <= 0.0


def irrigation_sensor_reading_is_fresh(reading: sqlite3.Row | dict[str, object] | None) -> bool:
    if reading is None:
        return False
    if str(reading["source_type"] or "").strip().lower() == "seed":
        return False
    captured_at = reading_captured_at(reading)
    if not captured_at:
        return False
    try:
        age = utc_now() - parse_iso_datetime(captured_at)
    except ValueError:
        return False
    return timedelta(minutes=-1) <= age <= timedelta(minutes=IRRIGATION_SENSOR_MAX_AGE_MINUTES)


def time_weighted_median(
    samples: list[tuple[datetime, float]], start: datetime, end: datetime
) -> float | None:
    """The value the series held for half of [start, end], each sample counted
    for as long as it stood.

    Weighted by time, not by count, because the board publishes on change: a
    noisy minute sends a reading every two seconds and a steady one sends one
    every thirty, so counting rows would let the noise outvote the soil. The
    newest sample before ``start`` is what the series held when the window
    opened. ``samples`` must be oldest first.
    """
    if not samples or end <= start:
        return None
    segments: list[tuple[float, float]] = []
    carried: float | None = None
    cursor = start
    for captured, value in samples:
        if captured <= start:
            carried = value
            continue
        if captured > end:
            break
        if carried is not None:
            segments.append((carried, (captured - cursor).total_seconds()))
        carried = value
        cursor = captured
    if carried is None:
        return None
    segments.append((carried, (end - cursor).total_seconds()))
    total = sum(weight for _value, weight in segments)
    if total <= 0:
        return carried
    ordered = sorted(segments, key=lambda segment: segment[0])
    running = 0.0
    for value, weight in ordered:
        running += weight
        if running >= total / 2.0:
            return value
    return ordered[-1][0]


# Supabase bills every byte a read returns, and the hosted site rebuilds the
# irrigation payload on a 3 s poll. The Pi reads its own file and never caches.
_SETTLED_PH_CACHE: dict[str, object] = {"at": 0.0, "value": {}}
_SETTLED_PH_CACHE_LOCK = threading.Lock()
SETTLED_PH_POSTGRES_CACHE_SECONDS = 30.0


def settled_rs485_ph_by_row(connection: sqlite3.Connection) -> dict[str, float]:
    """Each row's soil pH as the median of the last IRRIGATION_PH_SETTLE_SECONDS.

    What an automatic lime start is checked against, besides the latest
    reading. Nothing else reads it: the stored readings, the cards, the graphs
    and the Irrigation page all keep exactly what the probe sent. A row with
    nothing inside the window is absent, and the latest reading decides alone.
    """
    use_cache = postgres_backend_enabled()
    if use_cache:
        with _SETTLED_PH_CACHE_LOCK:
            if time.monotonic() - float(_SETTLED_PH_CACHE["at"]) < SETTLED_PH_POSTGRES_CACHE_SECONDS:
                return dict(_SETTLED_PH_CACHE["value"])  # type: ignore[arg-type]
    now = utc_now()
    window_start = (now - timedelta(seconds=IRRIGATION_PH_SETTLE_SECONDS)).isoformat()
    sensor_keys = [f"{row_key}-rs485" for row_key in VALID_CULTIVATION_ROWS]
    placeholders = ", ".join("?" for _ in sensor_keys)
    live_only = """
          AND LOWER(TRIM(COALESCE(source_type, ''))) NOT IN ('seed', 'hybrid-sync-test')
          AND LOWER(TRIM(COALESCE(source_identifier, ''))) NOT IN (
              'default-backfill',
              'seed-simulator'
          )"""
    rows = list(connection.execute(
        f"""
        SELECT sensor_key, reading_payload_json, captured_at
        FROM sensor_readings
        WHERE sensor_key IN ({placeholders})
          AND captured_at >= ?{live_only}
        ORDER BY sensor_key ASC, captured_at ASC
        """,  # nosec B608 - only '?' placeholders and a constant interpolated
        (*sensor_keys, window_start),
    ).fetchall())
    # And the reading each probe stood at when the window opened, however long
    # ago it arrived. Without it a lone reading just inside the window -- the
    # first after a quiet spell or a restart -- would be its own median, and one
    # dip could start Automatic again.
    for sensor_key in sensor_keys:
        standing = connection.execute(
            f"""
            SELECT sensor_key, reading_payload_json, captured_at
            FROM sensor_readings
            WHERE sensor_key = ?
              AND captured_at < ?{live_only}
            ORDER BY captured_at DESC
            LIMIT 1
            """,  # nosec B608 - only a constant interpolated
            (sensor_key, window_start),
        ).fetchone()
        if standing is not None:
            rows.append(standing)
    samples: dict[str, list[tuple[datetime, float]]] = {}
    for row in rows:
        payload = parse_sensor_reading_payload(row["reading_payload_json"])
        # The probe's own pH: a row stored before 2026-10-02 may carry an
        # eased one under "ph" (SOIL_DOSE_MEASURED_KEYS).
        value =normalize_numeric_value(payload.get(SOIL_DOSE_MEASURED_KEYS["ph"], payload.get("ph")))
        if value is None:
            continue
        try:
            captured = parse_iso_datetime(str(row["captured_at"]))
        except ValueError:
            continue
        samples.setdefault(str(row["sensor_key"]).strip(), []).append((captured, float(value)))
    settled: dict[str, float] = {}
    for sensor_key, series in samples.items():
        series.sort(key=lambda sample: sample[0])
        # A board clock ahead of this one must not leave its newest reading
        # outside the window.
        end = max(now, series[-1][0])
        value = time_weighted_median(
            series, end - timedelta(seconds=IRRIGATION_PH_SETTLE_SECONDS), end
        )
        if value is not None:
            settled[sensor_key[: -len("-rs485")]] = round(value, 2)
    if use_cache:
        with _SETTLED_PH_CACHE_LOCK:
            _SETTLED_PH_CACHE["at"] = time.monotonic()
            _SETTLED_PH_CACHE["value"] = dict(settled)
    return settled


def lime_resting_rows(connection: sqlite3.Connection) -> set[str]:
    """Rows whose last lime run ended within IRRIGATION_LIME_REST_MINUTES."""
    if IRRIGATION_LIME_REST_MINUTES <= 0:
        return set()
    cutoff = (utc_now() - timedelta(minutes=IRRIGATION_LIME_REST_MINUTES)).isoformat()
    rows = connection.execute(
        """
        SELECT DISTINCT run_row.row_key
        FROM irrigation_run_rows AS run_row
        INNER JOIN irrigation_runs AS run ON run.id = run_row.irrigation_run_id
        WHERE run.channel_key = 'limeSolution'
          AND COALESCE(run_row.ended_at, run.ended_at) IS NOT NULL
          AND COALESCE(run_row.ended_at, run.ended_at) >= ?
        """,
        (cutoff,),
    ).fetchall()
    return {str(row["row_key"]).strip() for row in rows}


# Until 2026-10-02 the Pi eased the shown EC and pH after a fertilizer or lime
# run and kept the probe's own beside them under these keys. The farm had that
# taken out: a card stood more than a pH unit from its probe for 25 minutes
# and read as a broken calibration. Every soil row is now stored as the board
# sent it. Rows from those days still carry the keys, so they stay listed.
SOIL_DOSE_MEASURED_KEYS = {"ec": "measuredEc", "ph": "measuredPh"}
SOIL_DOSE_FIELDS = frozenset(
    (
        *SOIL_DOSE_MEASURED_KEYS.values(),
        # Stored by the per-line hold (8fad1ae to 21f20c2, removed 2026-10-02).
        # They are not sensor metrics either.
        "measuredMoisture",
        "heldMoisture",
        "heldEc",
        "heldPh",
        "smoothMoisture",
        "smoothEc",
        "smoothPh",
    )
)


def soil_measured_metric_value(reading, metric_key: str) -> float | None:
    """The RS485 probe's own EC or pH, also on a row stored while they were eased."""
    measured_key = SOIL_DOSE_MEASURED_KEYS.get(metric_key)
    if reading and measured_key:
        payload = parse_sensor_reading_payload(reading["reading_payload_json"])
        if measured_key in payload:
            value = normalize_numeric_value(payload.get(measured_key))
            if value is not None:
                return value
    return reading_metric_value(reading, metric_key)


def actuator_schedule_minute(value: object, fallback: str) -> int:
    raw = str(value or fallback).strip()
    try:
        hour_text, minute_text = raw.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        hour, minute = (int(part) for part in fallback.split(":", 1))
    if hour not in range(24) or minute not in range(60):
        hour, minute = (int(part) for part in fallback.split(":", 1))
    return hour * 60 + minute


def crop_parameter_bounds(
    cultivations: list[sqlite3.Row] | list[dict[str, object]], metric_key: str
) -> tuple[float | None, float | None]:
    """The tightest floor and ceiling every active crop can live with.

    Several rows can be growing different crops off one greenhouse, and only
    one air. The floor is therefore the *highest* minimum any of them asks for
    and the ceiling the *lowest* maximum -- satisfy those and every crop is
    inside its own range. Returns (None, None) when nothing is planted.
    """
    ranges = [
        metric_range
        for cultivation in cultivations
        if (metric_range := irrigation_parameter_range(cultivation, metric_key)) is not None
    ]
    if not ranges:
        return None, None
    return (
        max(float(item["min"]) for item in ranges),
        min(float(item["max"]) for item in ranges),
    )


def crop_ceiling_rows(
    cultivations: list[sqlite3.Row] | list[dict[str, object]],
    metric_key: str,
    fallback_ceiling: float,
) -> list[dict[str, object]]:
    """Return every active row and the ceiling the shared air must satisfy.

    Fan and ventilation hardware serve the whole greenhouse, so a row without
    a custom bound still needs the installation fallback rather than silently
    dropping out of the shared decision. Keeping the rows in physical order
    also gives the dashboard a stable, useful affected-row list.
    """
    cultivation_by_row = active_cultivation_row_map(cultivations)
    rows: list[dict[str, object]] = []
    for row_key in VALID_CULTIVATION_ROWS:
        cultivation = cultivation_by_row.get(row_key)
        if cultivation is None:
            continue
        metric_range = irrigation_parameter_range(cultivation, metric_key)
        ceiling = (
            float(metric_range["max"])
            if metric_range is not None
            else float(fallback_ceiling)
        )
        rows.append(
            {
                "key": row_key,
                "label": cultivation_row_label(row_key),
                "ceiling": round(ceiling, 2),
                "fromCropParameters": metric_range is not None,
            }
        )
    return rows


# How close to a crop's own limit counts as "nearly there". A fraction of the
# band rather than a fixed number of degrees or percent, so it scales with each
# crop's range instead of being wrong for the narrow ones.
ACTUATOR_SAFETY_WARN_FRACTION = max(
    0.01, min(0.5, configured_float("ICUCROPS_ACTUATOR_WARN_FRACTION", 0.1))
)

# Which parameter stops each actuator, and which way. "ceiling" cuts when the
# reading rises above the crops' maximum; "floor" cuts when it falls below the
# minimum. Every bound comes from the active crops' own parameters, so a farm
# that edits its crop ranges moves these limits with it.
ACTUATOR_SAFETY_RULES = {
    "light": {
        "metric": "temp",
        "bound": "ceiling",
        "unit": "\u00b0C",
        "label": "Grow light",
        "reading": "temperature",
        "cut": "The greenhouse is already at the highest temperature your crops can take.",
        "warn": "The greenhouse is close to the highest temperature your crops can take.",
    },
    "misting": {
        "metric": "humidity",
        "bound": "ceiling",
        "unit": "%",
        "label": "Misting line",
        "reading": "humidity",
        "cut": "The air is already as humid as your crops can take.",
        "warn": "The air is close to the highest humidity your crops can take.",
    },
    "fan": {
        "metric": "humidity",
        "bound": "floor",
        "unit": "%",
        "label": "Exhaust fan",
        "reading": "humidity",
        "cut": "The air is already as dry as your crops can take.",
        "warn": "The air is close to the driest your crops can take.",
    },
}


def actuator_reading_phrase(value: float, limit: float, rule: dict) -> str:
    """The numbers behind the decision, in the operator's own units."""
    unit = str(rule["unit"])
    separator = "" if unit == "%" else " "
    word = "limit" if rule["bound"] == "ceiling" else "minimum"
    return (
        f"Now {value:.1f}{separator}{unit}, against your crops' "
        f"{limit:.1f}{separator}{unit} {word}."
    )


def actuator_safety_status(
    cultivations,
    latest_readings,
) -> dict:
    """Whether each actuator may run right now, judged against crop parameters.

    Running a grow light in an already-hot house, or a misting line in already
    saturated air, damages the crop, and nothing here can undo it: the
    greenhouse has no cooling and no dehumidifier. Someone who presses On has
    no way to keep watching, so the limit has to be enforced where the relays
    are decided rather than in a browser.

    The rule is deliberately not a timer. How long an actuator may safely run
    depends on the air, not the clock: inside the crops' range it can run all
    day, and past the limit even a minute is too long. So the bound is the
    crops' own parameter, and a farm that edits its crop ranges moves these
    limits with it. Nothing here is hardcoded per crop.

    Three states, matching what an operator needs to know:
      ok      - inside the range, run normally
      warning - near the limit, still allowed, but say so
      cut     - past the limit, refuse On and stop what is running

    A stale or missing reading is never treated as permission to cut. The rest
    of this system is fail-closed for the same reason: a silent board is not
    evidence the house is fine, and cutting on no evidence would strand the
    crop with the operator unable to see why.
    """
    dht_reading = latest_readings.get("dht22")
    reading_fresh = irrigation_sensor_reading_is_fresh(dht_reading)
    values = {
        "temperature": reading_metric_value(dht_reading, "temp"),
        "humidity": reading_metric_value(dht_reading, "humidity"),
    }

    status: dict = {}
    for actuator_key, rule in ACTUATOR_SAFETY_RULES.items():
        floor, ceiling = crop_parameter_bounds(cultivations, str(rule["metric"]))
        limit = ceiling if rule["bound"] == "ceiling" else floor
        value = values[str(rule["reading"])]

        entry: dict = {
            "state": "ok",
            "actuator": rule["label"],
            "unit": rule["unit"],
            "metric": rule["metric"],
            "bound": rule["bound"],
            "reading": value,
            "limit": None if limit is None else round(float(limit), 2),
            "readingFresh": reading_fresh,
            "message": "",
            # True only when a crop supplied the bound. With nothing planted
            # there is no parameter to enforce and nothing is ever cut.
            "fromCropParameters": limit is not None,
        }

        if not reading_fresh:
            entry["state"] = "unknown"
            entry["message"] = (
                f"{rule['label']} safety limits are paused: the greenhouse sensor "
                "is not reporting, so its readings cannot be checked."
            )
            status[actuator_key] = entry
            continue

        if limit is None or value is None:
            status[actuator_key] = entry
            continue

        span = None
        if floor is not None and ceiling is not None and ceiling > floor:
            span = float(ceiling) - float(floor)

        # Without both bounds there is no band to take a fraction of, so the
        # warning zone falls back to a share of the limit itself.
        warn_margin = (
            span * ACTUATOR_SAFETY_WARN_FRACTION
            if span is not None
            else abs(float(limit)) * ACTUATOR_SAFETY_WARN_FRACTION
        )

        numeric = float(value)
        boundary = float(limit)
        if rule["bound"] == "ceiling":
            past_limit = numeric >= boundary
            near_limit = numeric >= boundary - warn_margin
        else:
            past_limit = numeric <= boundary
            near_limit = numeric <= boundary + warn_margin

        if past_limit:
            entry["state"] = "cut"
            entry["message"] = f"{rule['cut']} {actuator_reading_phrase(numeric, boundary, rule)}"
        elif near_limit:
            entry["state"] = "warning"
            entry["message"] = f"{rule['warn']} {actuator_reading_phrase(numeric, boundary, rule)}"

        status[actuator_key] = entry

    return status


def build_actuator_automation_payload(cultivations, latest_readings, *, climate=None) -> dict:
    """The automation thresholds plus the safety verdict, in one payload.

    Both come from the same readings and the same crop parameters, and the
    sensors page draws them together, so they are assembled together. Deriving
    the verdict here rather than in JavaScript is what keeps the card and the
    relay agreeing: the browser cannot reach a different conclusion from the
    control cycle when neither is doing the arithmetic.
    """
    climate = (
        climate
        if climate is not None
        else greenhouse_climate_values(latest_readings, bounds=greenhouse_climate_bounds(cultivations))
    )
    guidance = automatic_actuator_guidance(
        cultivations,
        latest_readings,
        running=dict(AUTOMATIC_ACTUATOR_RUNNING),
        climate=climate,
        light_limit=grow_light_limit_snapshot(),
    )
    guidance["safety"] = actuator_safety_status(
        cultivations, greenhouse_card_readings(latest_readings, climate)
    )
    return guidance


def record_climate_sample(latest_readings, *, now: float | None = None) -> None:
    """Remember this cycle's DHT22 reading for climate_trend_per_minute().

    Only a fresh reading is kept, and a stale one clears the history: a trend
    drawn across a silent board would be a line between two unrelated days.
    """
    moment = time.monotonic() if now is None else float(now)
    reading = latest_readings.get("dht22")
    if not irrigation_sensor_reading_is_fresh(reading):
        AUTOMATIC_CLIMATE_SAMPLES.clear()
        return
    temperature = reading_metric_value(reading, "temp")
    humidity = reading_metric_value(reading, "humidity")
    if temperature is None and humidity is None:
        return
    AUTOMATIC_CLIMATE_SAMPLES.append((moment, temperature, humidity))
    cutoff = moment - AUTOMATIC_TREND_WINDOW_S
    while AUTOMATIC_CLIMATE_SAMPLES and AUTOMATIC_CLIMATE_SAMPLES[0][0] < cutoff:
        AUTOMATIC_CLIMATE_SAMPLES.pop(0)


def climate_trend_per_minute(
    samples: list[tuple[float, float | None, float | None]] | None = None,
) -> dict[str, float | None]:
    """The DHT22's rate of change over the trend window, per minute.

    A least-squares slope rather than first-minus-last, so one noisy reading at
    either end does not decide it. None for a metric with too few samples or
    too short a span to say anything.
    """
    rows = list(AUTOMATIC_CLIMATE_SAMPLES if samples is None else samples)
    result: dict[str, float | None] = {"temp": None, "humidity": None}
    for index, key in ((1, "temp"), (2, "humidity")):
        points = [(row[0], float(row[index])) for row in rows if row[index] is not None]
        if len(points) < 3 or points[-1][0] - points[0][0] < AUTOMATIC_TREND_MIN_SPAN_S:
            continue
        mean_t = sum(point[0] for point in points) / len(points)
        mean_v = sum(point[1] for point in points) / len(points)
        spread = sum((point[0] - mean_t) ** 2 for point in points)
        if spread <= 0:
            continue
        slope = sum((point[0] - mean_t) * (point[1] - mean_v) for point in points) / spread
        result[key] = slope * 60.0
    return result


def greenhouse_climate_bounds(
    cultivations: list[sqlite3.Row] | list[dict[str, object]],
) -> dict[str, tuple[float, float]]:
    """The floor and ceiling the shared air is held to, per metric.

    The same numbers automatic_actuator_guidance answers to: the strictest
    crop bound across the active rows, or the installation fallback where no
    row sets one. The humidity floor falls back to 15 points under the ceiling
    when no crop gives one.
    """
    temp_floor, _unused = crop_parameter_bounds(cultivations, "temp")
    humidity_floor, _unused = crop_parameter_bounds(cultivations, "humidity")
    humidity_rows = crop_ceiling_rows(cultivations, "humidity", FAN_AUTO_FALLBACK_ON_HUMIDITY)
    temperature_rows = crop_ceiling_rows(cultivations, "temp", GREENHOUSE_VENT_FALLBACK_C)
    temp_ceiling = (
        min(float(row["ceiling"]) for row in temperature_rows)
        if temperature_rows else GREENHOUSE_VENT_FALLBACK_C
    )
    humidity_ceiling = (
        min(float(row["ceiling"]) for row in humidity_rows)
        if humidity_rows else FAN_AUTO_FALLBACK_ON_HUMIDITY
    )
    temp_floor = float(temp_floor) if temp_floor is not None else float(LIGHT_AUTO_FALLBACK_ON_C)
    humidity_floor = (
        float(humidity_floor) if humidity_floor is not None else float(humidity_ceiling) - 15.0
    )
    return {
        "temp": (temp_floor, float(temp_ceiling)),
        "humidity": (humidity_floor, float(humidity_ceiling)),
    }


def greenhouse_response_step(
    previous: dict[str, object] | None,
    *,
    actual: dict[str, float | None],
    bounds: dict[str, tuple[float, float]],
    fan_automatic: bool,
    light_automatic: bool,
    fan_running: bool,
    lamp_warming: bool,
    trend: dict[str, float | None] | None,
    elapsed_seconds: float,
) -> dict[str, object]:
    """One control cycle of the greenhouse response on the cards.

    Pure: the previous offsets in, the next ones out. ``actual`` is the DHT22
    as measured; what the cards show and the rules act on is actual + offset,
    so a real change at the sensor still moves it one-for-one.

    ``bounds`` is every active row's range at once (the highest floor, the
    lowest ceiling), so a card brought inside it is normal on every row. The
    farm's rule on Automatic:

      warning        nothing is started; the card alone is eased back
                     inside, slowly (GREENHOUSE_RESPONSE_WARNING_EASE), and
                     held there only while the sensor itself stays short
                     of critical.
      critical high  the card is brought down -- the fan starts at the same
                     point -- until it is a deadband inside the ceiling
                     (never past the middle), then held there.
      critical low   the card is brought up to the same deadband inside the
                     floor, then held: temperature with the lamp on
                     Automatic, humidity with the fan on Automatic.
      lamp warming   the lamp's cold rule running brings temperature up too.
      fan running    whatever it runs for, it brings anything above that
                     deadband down with it: the fan holds until both are in.

    Held means the offset stays while the sensor moves the card, but never
    takes the card past where it settled, and none is left once the sensor is
    back inside by itself. Faster the further out, stronger past the critical margin, and
    gentler when the sensor is already moving the right way by itself.

    With nothing on Automatic a manual-On fan keeps bringing both down, to
    the middle of the temperature range and just above the humidity floor,
    and otherwise the offset wears off towards the sensor with
    GREENHOUSE_RESPONSE_RECOVER_MINUTES.
    """
    minutes = max(0.0, min(float(elapsed_seconds), 30.0)) / 60.0
    trend = trend or {}
    previous = previous or {}
    before = dict(previous.get("offset") or {})
    if not before and previous:
        before = {metric: greenhouse_response_effect(previous, metric) for metric in ("temp", "humidity")}
    directions_before = dict(previous.get("adjusting") or {})
    # Why each offset exists: "critical" when the fan or lamp brought the card
    # back, "warning" when only the warning ease did.
    sources_before = dict(previous.get("source") or {})
    automatic = bool(fan_automatic or light_automatic)
    offsets: dict[str, float] = {}
    directions: dict[str, str | None] = {}
    sources: dict[str, str | None] = {}

    def recovered(offset: float, metric: str) -> float:
        if offset == 0:
            return 0.0
        rates = GREENHOUSE_RESPONSE_RATES[metric]
        speed = max(rates["recoverMin"], abs(offset) / GREENHOUSE_RESPONSE_RECOVER_MINUTES)
        step = min(abs(offset), speed * minutes)
        return offset - step if offset > 0 else offset + step

    def push_rate(metric: str, beyond: float) -> float:
        rates = GREENHOUSE_RESPONSE_RATES[metric]
        if beyond <= 0:
            return rates["inside"]
        margin = GREENHOUSE_RESPONSE_CRITICAL_MARGIN[metric]
        return (
            rates["outside"]
            + rates["gain"] * min(beyond, margin)
            + rates["criticalGain"] * max(0.0, beyond - margin)
        )

    def trend_share(metric: str, helping: object) -> float:
        # `helping` is how fast the reading is already moving the way the card
        # is being moved. Moving that way on its own needs less push.
        if not isinstance(helping, (int, float)) or helping <= 0:
            return 1.0
        scale = GREENHOUSE_RESPONSE_TREND_SCALE[metric]
        return max(GREENHOUSE_RESPONSE_TREND_FLOOR, 1.0 - float(helping) / scale)

    for metric in ("temp", "humidity"):
        value = actual.get(metric)
        if value is None:
            offsets[metric] = 0.0
            directions[metric] = None
            sources[metric] = None
            continue
        floor, ceiling = bounds[metric]
        if floor > ceiling:
            # Rows that share no range at all: aim for between them.
            floor = ceiling = (floor + ceiling) / 2.0
        middle = (floor + ceiling) / 2.0
        margin = GREENHOUSE_RESPONSE_CRITICAL_MARGIN[metric]
        half = (ceiling - floor) / 2.0
        stop_down = ceiling - min(GREENHOUSE_RESPONSE_INSET[metric], half)
        stop_up = floor + min(GREENHOUSE_RESPONSE_INSET_UP[metric], half)
        offset = float(before.get(metric) or 0.0)
        direction = directions_before.get(metric)
        source = sources_before.get(metric) if offset else None
        shown = value + offset
        rate = trend.get(metric)
        rate = float(rate) if isinstance(rate, (int, float)) else None

        if automatic:
            # The warning ease only ever covers a sensor that is itself in the
            # warning band. Once the sensor is critical it is dropped, so the
            # card shows it and the fan starts: a slow real rise must not be
            # held at "normal" all the way past critical.
            if source == "warning" and not (floor - margin <= value <= ceiling + margin):
                offset, direction, source = 0.0, None, None
            shown = value + offset
            if fan_running and shown > stop_down:
                direction = "down"
            if fan_automatic and shown > ceiling + margin:
                direction = "down"
            may_raise = light_automatic if metric == "temp" else fan_automatic
            if may_raise and shown < floor - margin:
                direction = "up"
            if metric == "temp" and lamp_warming and shown < stop_up:
                direction = "up"
            if direction in ("down", "up"):
                source = "critical"
            elif direction is None and offset == 0:
                # A warning nothing has touched yet: ease it back, slowly,
                # without starting anything.
                if fan_automatic and ceiling < shown <= ceiling + margin:
                    direction, source = "ease-down", "warning"
                elif may_raise and floor - margin <= shown < floor:
                    direction, source = "ease-up", "warning"
            if direction == "ease-down" and not fan_automatic:
                direction = None
            elif direction == "ease-up" and not may_raise:
                direction = None
            if direction == "ease-down":
                offset -= GREENHOUSE_RESPONSE_WARNING_EASE[metric] * minutes
                if value + offset <= stop_down:
                    offset = min(0.0, stop_down - value)
                    direction = None
            elif direction == "ease-up":
                offset += GREENHOUSE_RESPONSE_WARNING_EASE[metric] * minutes
                if value + offset >= stop_up:
                    offset = max(0.0, stop_up - value)
                    direction = None
            elif direction == "down":
                speed = push_rate(metric, shown - stop_down) * trend_share(
                    metric, -rate if rate is not None else None
                )
                offset -= speed * minutes
                if value + offset <= stop_down:
                    offset = stop_down - value
                    direction = None
            elif direction == "up":
                speed = push_rate(metric, stop_up - shown) * trend_share(metric, rate)
                offset += speed * minutes
                if value + offset >= stop_up:
                    offset = stop_up - value
                    direction = None
            if direction is None:
                # Held, but never hiding a sensor that is itself back inside:
                # a held cooling cannot take the card below where it settled,
                # and none is left once the sensor is there by itself.
                if offset < 0:
                    offset = max(offset, min(0.0, stop_down - value))
                elif offset > 0:
                    offset = min(offset, max(0.0, stop_up - value))
                # A card Automatic has brought back stays normal through the
                # sensor's own wander in the warning band -- warning starts
                # nothing, so it would otherwise sit amber until critical.
                # With these four rows only 20 C is normal for all of them,
                # and a 0.3 C tick of the DHT22 turned Pechay amber. Critical
                # still shows, and starts the fan. A card Automatic never
                # touched is eased back instead (GREENHOUSE_RESPONSE_WARNING_EASE).
                if offset != 0:
                    card = value + offset
                    if ceiling < card <= ceiling + margin:
                        offset = ceiling - value
                    elif floor - margin <= card < floor:
                        offset = floor - value
        elif fan_running:
            limit = (
                middle
                if metric == "temp"
                else min(floor + GREENHOUSE_RESPONSE_FAN_HUMIDITY_MARGIN, middle)
            )
            speed = push_rate(metric, shown - ceiling) * trend_share(
                metric, -rate if rate is not None else None
            )
            offset = min(0.0, max(offset - speed * minutes, min(0.0, limit - value)))
            direction = None
        else:
            offset = recovered(offset, metric)
            direction = None
        offsets[metric] = offset
        directions[metric] = direction
        sources[metric] = source if offset else None

    return {"offset": offsets, "adjusting": directions, "source": sources}


def greenhouse_response_effect(state: dict[str, object] | None, metric: str) -> float:
    if not state:
        return 0.0
    if isinstance(state.get("offset"), dict):
        return float(state["offset"].get(metric) or 0.0)
    fan = (state.get("fan") or {}).get(metric) or 0.0
    lamp = (state.get("light") or {}).get(metric) or 0.0
    return float(fan) + float(lamp)


def advance_greenhouse_response(
    cultivations,
    latest_readings,
    *,
    trend: dict[str, float | None] | None = None,
    now: float | None = None,
) -> None:
    """Step the model once, from what the relays were doing since last cycle.

    Called only by the environment control cycle. The relay states read here
    are the ones that ran through the interval just gone, which is what moved
    the air in it; this cycle's decision moves it in the next.
    """
    moment = time.monotonic() if now is None else float(now)
    reading = latest_readings.get("dht22")
    fresh = irrigation_sensor_reading_is_fresh(reading)
    with GREENHOUSE_RESPONSE_LOCK:
        previous = dict(GREENHOUSE_RESPONSE_STATE)
        if not GREENHOUSE_RESPONSE_ENABLED or not fresh:
            # Nothing measured to put an effect on. Start again from the
            # sensor when it comes back rather than resuming a stale effect.
            GREENHOUSE_RESPONSE_STATE.clear()
            return
        last = previous.get("at")
        elapsed = moment - float(last) if isinstance(last, (int, float)) else 0.0
        fan_mode = RELAY_ACTUATOR_MODE_CACHE.get("fan", "automatic")
        light_mode = RELAY_ACTUATOR_MODE_CACHE.get("light", "automatic")
        fan_running = fan_mode == "on" or (
            fan_mode == "automatic" and bool(RELAY_ACTUATOR_AUTO_CACHE.get("fan"))
        )
        lamp_running = light_mode == "automatic" and bool(RELAY_ACTUATOR_AUTO_CACHE.get("light"))
        effects = greenhouse_response_step(
            previous,
            actual={
                "temp": reading_metric_value(reading, "temp"),
                "humidity": reading_metric_value(reading, "humidity"),
            },
            bounds=greenhouse_climate_bounds(cultivations),
            fan_automatic=fan_mode == "automatic",
            light_automatic=light_mode == "automatic",
            fan_running=fan_running,
            lamp_warming=lamp_running and bool(AUTOMATIC_ACTUATOR_RUNNING.get("lightCold")),
            trend=trend,
            elapsed_seconds=elapsed,
        )
        # How fast the effect is moving, per minute, so a stored row can carry
        # it (with_greenhouse_card_effect) and the cards keep moving smoothly
        # between DHT22 publishes instead of stepping once per reading.
        rate = {
            metric: (
                (greenhouse_response_effect(effects, metric) - greenhouse_response_effect(previous, metric))
                / elapsed * 60.0
            ) if elapsed > 0 else float((previous.get("rate") or {}).get(metric) or 0.0)
            for metric in ("temp", "humidity")
        }
        GREENHOUSE_RESPONSE_STATE.clear()
        GREENHOUSE_RESPONSE_STATE.update({**effects, "rate": rate, "at": moment})


# The fan and lamp's effect, stored on each DHT22 row as the Pi's control cycle
# had it when the reading arrived. Beside the measured temp and humidity, never
# in place of them: the row still says what the part measured, and these say
# what the cards add to it. Every path that carries a reading -- the Postgres
# sync and the HTTPS relay alike -- carries these with it, so the website
# applies exactly the kiosk's effect to exactly the kiosk's reading.
#
# This replaced two sources that took turns. The website used the effect the
# relay last posted while it was under a minute old, and each browser's own
# model otherwise; whenever a relay pass ran late the cards swapped between the
# two and blinked, and the greenhouse alert flipped with them.
GREENHOUSE_CARD_EFFECT_KEYS = {"temp": "cardEffectTemp", "humidity": "cardEffectHumidity"}
# And how fast that effect was moving, per minute. The DHT22 publishes every
# 30 s; a card holding one effect per row would step by up to half a degree at
# each reading, which is exactly the visible auto-adjust the farm asked not to
# see. Both the kiosk and the website carry the effect forward from the row's
# own captured_at at this rate, so they move together and in 0.1 steps.
GREENHOUSE_CARD_EFFECT_RATE_KEYS = {"temp": "cardEffectTempRate", "humidity": "cardEffectHumidityRate"}
# No further than this past the row: about two DHT22 publishes. A missed
# reading must not let the effect run on unchecked.
GREENHOUSE_CARD_EFFECT_CARRY_SECONDS = 60.0
# 1 when Automatic has brought that card back and is holding it there. The
# stored effect was worked out against the reading before this one, so a new
# reading lands up to a few tenths off where the card was held; with these
# rows only 20 C normal for all four, that was enough to flash a row amber for
# the 30 s until the next reading. A held card is kept inside the range on
# display, exactly as greenhouse_response_step keeps it on the Pi.
GREENHOUSE_CARD_HOLD_KEYS = {"temp": "cardHoldTemp", "humidity": "cardHoldHumidity"}
GREENHOUSE_CARD_FIELDS = frozenset(
    (
        *GREENHOUSE_CARD_EFFECT_KEYS.values(),
        *GREENHOUSE_CARD_EFFECT_RATE_KEYS.values(),
        *GREENHOUSE_CARD_HOLD_KEYS.values(),
    )
)


def greenhouse_live_effect(*, now: float | None = None) -> tuple[dict[str, float], dict[str, float]]:
    """The control cycle's current effect and its rate per minute, or zeros."""
    moment = time.monotonic() if now is None else float(now)
    with GREENHOUSE_RESPONSE_LOCK:
        state = dict(GREENHOUSE_RESPONSE_STATE)
    at = state.get("at")
    zero = {"temp": 0.0, "humidity": 0.0}
    if not state or not isinstance(at, (int, float)) or moment - float(at) > GREENHOUSE_RESPONSE_STALE_SECONDS:
        return zero, dict(zero)
    rate = state.get("rate") or {}
    return (
        {metric: greenhouse_response_effect(state, metric) for metric in ("temp", "humidity")},
        {metric: float(rate.get(metric) or 0.0) for metric in ("temp", "humidity")},
    )


def with_greenhouse_card_effect(sensor_key: str, reading_payload: dict[str, object]) -> dict[str, object]:
    """The DHT22 payload to store on the Pi: as measured, plus the card effect.

    Only on the Pi, where the control cycle runs; the hosted API stores what the
    Pi sent, fields included. Zeros are stored too -- they tell the website the
    Pi is showing the reading as measured, so it must not model its own.
    """
    if (
        sensor_key != "dht22"
        or postgres_backend_enabled()
        or not GREENHOUSE_RESPONSE_ENABLED
        or any(key in reading_payload for key in GREENHOUSE_CARD_FIELDS)
    ):
        return reading_payload
    effect, rate = greenhouse_live_effect()
    with GREENHOUSE_RESPONSE_LOCK:
        adjusting = dict(GREENHOUSE_RESPONSE_STATE.get("adjusting") or {})
    stored = dict(reading_payload)
    for metric, key in GREENHOUSE_CARD_EFFECT_KEYS.items():
        if metric in reading_payload:
            stored[key] = round(float(effect[metric]), 3)
            stored[GREENHOUSE_CARD_EFFECT_RATE_KEYS[metric]] = round(float(rate[metric]), 4)
            held = bool(effect[metric]) and adjusting.get(metric) is None
            stored[GREENHOUSE_CARD_HOLD_KEYS[metric]] = 1.0 if held else 0.0
    return stored


def stored_greenhouse_hold(reading) -> dict[str, bool]:
    """Which cards the Pi was holding normal when this DHT22 row was stored."""
    if not reading:
        return {}
    payload = parse_sensor_reading_payload(reading["reading_payload_json"])
    return {
        metric: payload.get(key) in (1, 1.0, True)
        for metric, key in GREENHOUSE_CARD_HOLD_KEYS.items()
    }


def hold_card_inside(value: float, metric: str, bounds: tuple[float, float]) -> float:
    """A held card that has wandered into warning, put back at the range's edge.

    Critical is left as it is: that is the point the fan starts again.
    """
    floor, ceiling = bounds
    if floor > ceiling:
        floor = ceiling = (floor + ceiling) / 2.0
    margin = GREENHOUSE_RESPONSE_CRITICAL_MARGIN[metric]
    if ceiling < value <= ceiling + margin:
        return ceiling
    if floor - margin <= value < floor:
        return floor
    return value


def stored_greenhouse_effect(reading, *, now: datetime | None = None) -> dict[str, float] | None:
    """The card effect stored on a DHT22 row, carried forward to now.

    None for a row without one. The stored rate carries the effect forward from
    the row's captured_at for up to GREENHOUSE_CARD_EFFECT_CARRY_SECONDS, never
    across zero: an effect wearing off stops at the reading, it does not turn
    into the opposite effect.
    """
    if not reading:
        return None
    payload = parse_sensor_reading_payload(reading["reading_payload_json"])

    def number(key: str) -> float | None | bool:
        value = payload.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return False
        if abs(float(value)) > 100:
            return False
        return float(value)

    try:
        captured = parse_iso_datetime(reading_captured_at(reading))
        age = ((now or utc_now()) - captured).total_seconds()
    except (TypeError, ValueError):
        age = 0.0
    carry_minutes = max(0.0, min(age, GREENHOUSE_CARD_EFFECT_CARRY_SECONDS)) / 60.0

    effect: dict[str, float] = {}
    for metric, key in GREENHOUSE_CARD_EFFECT_KEYS.items():
        value = number(key)
        if value is None:
            continue
        rate = number(GREENHOUSE_CARD_EFFECT_RATE_KEYS[metric])
        if value is False or rate is False:
            return None
        carried = value + (rate or 0.0) * carry_minutes
        if value and carried * value < 0:
            carried = 0.0
        effect[metric] = carried
    return effect or None


def greenhouse_climate_values(
    latest_readings,
    *,
    now: float | None = None,
    relayed: dict[str, object] | None = None,
    live: bool = False,
    bounds: dict[str, tuple[float, float]] | None = None,
) -> dict[str, object]:
    """The greenhouse temperature and humidity as the dashboards and rules see them.

    DHT22 as measured, plus the fan and lamp's effect when the control cycle
    has stepped it recently. ``measured`` is always the DHT22 itself, for the
    sensor card and for anything that must judge the part rather than the air.

    Off the Pi (the hosted API) no cycle runs and the state is empty. There
    ``relayed`` is the Pi's own effect as the HTTPS relay last delivered it
    (relayed_greenhouse_response), applied to the same DHT22 reading so the
    website shows the kiosk's number rather than one each browser works out
    for itself. ``authoritative`` says the numbers came from the Pi's cycle,
    modelled or not, so a dashboard must not run its own copy of the model.
    """
    reading = latest_readings.get("dht22")
    measured = {
        "temp": reading_metric_value(reading, "temp"),
        "humidity": reading_metric_value(reading, "humidity"),
    }
    moment = time.monotonic() if now is None else float(now)
    with GREENHOUSE_RESPONSE_LOCK:
        state = dict(GREENHOUSE_RESPONSE_STATE)
    at = state.get("at")
    active = bool(
        state
        and isinstance(at, (int, float))
        and moment - float(at) <= GREENHOUSE_RESPONSE_STALE_SECONDS
        and irrigation_sensor_reading_is_fresh(reading)
    )
    authoritative = not postgres_backend_enabled()
    stored = None if live else stored_greenhouse_effect(reading)
    held: dict[str, bool] = {}
    if stored is not None and irrigation_sensor_reading_is_fresh(reading):
        held = stored_greenhouse_hold(reading)
        # What the cards show, on the kiosk and the website alike: the effect
        # the Pi stored on this very reading. The live state still decides the
        # relays (live=True); this is at most one reading behind it.
        authoritative = True
        active = any(stored.values())
        state = {"fan": stored}
    elif not active and relayed:
        authoritative = True
        if relayed.get("modelled") and irrigation_sensor_reading_is_fresh(reading):
            active = True
            state = {"fan": relayed.get("effect") or {}}
    values: dict[str, object] = {
        "measured": measured,
        "modelled": active,
        "authoritative": authoritative,
    }
    for metric in ("temp", "humidity"):
        value = measured[metric]
        if value is None or not active:
            values[metric] = value
            continue
        effect = greenhouse_response_effect(state, metric)
        shown = value + effect if effect else value
        if effect and held.get(metric) and bounds and metric in bounds:
            shown = hold_card_inside(shown, metric, bounds[metric])
        values[metric] = round(shown, 1) if effect else value
    return values


def greenhouse_card_value_at_capture(
    reading,
    metric: str,
    bounds: dict[str, tuple[float, float]] | None = None,
) -> float | None:
    """What the card stood at for one DHT22 row: measured plus its stored effect.

    The Live Sensor Graph's temp and humidity points. They used to come from two
    places: the history reload plotted the DHT22 as measured, and the live poll
    plotted the card, eased, under the same captured_at. Whichever a browser
    fetched last won that slot, so two dashboards open side by side drew
    different lines (27 C from history on one, 20 C from the live poll on the
    other). This is a function of the stored row alone, not carried forward and
    not eased, so the history and the live poll give the same number for the
    same reading on every screen.
    """
    value = reading_metric_value(reading, metric)
    if value is None:
        return None
    try:
        captured = parse_iso_datetime(reading_captured_at(reading))
    except (TypeError, ValueError):
        captured = None
    effect = (stored_greenhouse_effect(reading, now=captured) or {}).get(metric) or 0.0
    if not effect:
        return value
    shown = value + effect
    if bounds and metric in bounds and stored_greenhouse_hold(reading).get(metric):
        shown = hold_card_inside(shown, metric, bounds[metric])
    return round(shown, 1)


# The greenhouse cards eased on the Pi, so every screen shows the kiosk's number.
#
# The small correction when a new DHT22 reading lands used to be spread over a
# few polls in each browser (easeToward in icucrops-climate-response.js). Each
# screen then eased from its own history: a page just opened showed the target
# at once while the kiosk was still on its way there, and the kiosk -- polling
# every second -- rounded each 0.03 C step back to where it was, so its
# temperature barely moved while the website's did. The website ran ahead of
# the Pi. Now the control cycle eases once, here, the kiosk shows the result
# as it is, and the relay carries the same number to the website.
GREENHOUSE_DISPLAY_EASE_PER_3S = {"temp": 0.1, "humidity": 0.5}
# Past this the control cycle has stopped stepping; show the target instead.
GREENHOUSE_DISPLAY_MAX_AGE_SECONDS = 30.0
GREENHOUSE_DISPLAY_LOCK = threading.Lock()
GREENHOUSE_DISPLAY_STATE: dict[str, object] = {}


def greenhouse_display_step(
    target: dict[str, object], *, fresh: bool, now: float | None = None
) -> dict[str, float | None]:
    """One control-cycle step of the cards toward ``target``, as easeToward did.

    The unrounded position is kept between steps and only the result is
    rounded, so a short step still adds up instead of rounding back to where it
    started. A stale DHT22 resets it: the next fresh reading is shown as it is.
    """
    moment = time.monotonic() if now is None else float(now)
    with GREENHOUSE_DISPLAY_LOCK:
        previous = dict(GREENHOUSE_DISPLAY_STATE)
        before_values = previous.get("exact") if fresh and previous.get("fresh") else None
        at = previous.get("at")
        elapsed = max(0.0, moment - float(at)) if isinstance(at, (int, float)) else None
        exact: dict[str, float | None] = {}
        for metric, per_3s in GREENHOUSE_DISPLAY_EASE_PER_3S.items():
            raw = target.get(metric)
            goal = (
                float(raw)
                if isinstance(raw, (int, float)) and not isinstance(raw, bool) and math.isfinite(float(raw))
                else None
            )
            before = (before_values or {}).get(metric)
            if goal is None or before is None or elapsed is None:
                exact[metric] = goal
                continue
            limit = per_3s * min(elapsed, 30.0) / 3.0
            moved = float(before) + max(-limit, min(limit, goal - float(before)))
            exact[metric] = goal if abs(goal - moved) < 1e-9 else moved
        GREENHOUSE_DISPLAY_STATE.clear()
        GREENHOUSE_DISPLAY_STATE.update({"exact": exact, "at": moment, "fresh": bool(fresh)})
    return {metric: None if value is None else round(value, 1) for metric, value in exact.items()}


def greenhouse_display_values(
    latest_readings,
    relayed: dict[str, object] | None = None,
    *,
    now: float | None = None,
) -> dict[str, float] | None:
    """The temp and humidity the kiosk is showing, or None to show the climate.

    On the Pi, the control cycle's eased cards while it is stepping them. On
    the hosted API, the same numbers as the relay last delivered them.
    """
    if not irrigation_sensor_reading_is_fresh(latest_readings.get("dht22")):
        return None
    if postgres_backend_enabled():
        shown = (relayed or {}).get("shown")
    else:
        moment = time.monotonic() if now is None else float(now)
        with GREENHOUSE_DISPLAY_LOCK:
            state = dict(GREENHOUSE_DISPLAY_STATE)
        at = state.get("at")
        if (
            not state.get("fresh")
            or not isinstance(at, (int, float))
            or moment - float(at) > GREENHOUSE_DISPLAY_MAX_AGE_SECONDS
        ):
            return None
        shown = {
            metric: None if value is None else round(float(value), 1)
            for metric, value in (state.get("exact") or {}).items()
        }
    if not isinstance(shown, dict):
        return None
    values = {
        metric: float(shown[metric])
        for metric in ("temp", "humidity")
        if isinstance(shown.get(metric), (int, float)) and not isinstance(shown.get(metric), bool)
    }
    return values if len(values) == 2 else None


# The Pi's fan-and-lamp effect, carried to the hosted API by the HTTPS relay.
# The Pi's control cycle writes the file; the relay reads it and posts it with
# the readings; the hosted backend keeps it under the system_state key below,
# which the sync deliberately does not carry back down (sync_system_state only
# moves irrigation.* and mqtt_node_status:*).
#
# Before this, the hosted dashboards stepped their own copy of the model in
# every browser, from whenever that page happened to load. The kiosk showed
# 20 C while the website showed 32 C off the same DHT22, and each reload or
# tab gave another number.
GREENHOUSE_RESPONSE_RELAY_FILE = DATA_DIR / "greenhouse-response.json"
GREENHOUSE_RESPONSE_RELAY_STATE_KEY = "greenhouse_response"
# The relay keepalive is 12s; this allows several lost posts before the website
# stops trusting the Pi's effect and falls back to its own model.
GREENHOUSE_RESPONSE_RELAY_MAX_AGE_SECONDS = 60.0
# The file is rewritten when the effect moves, and at least this often so the
# relay can tell a live cycle from a dead one.
GREENHOUSE_RESPONSE_SNAPSHOT_REFRESH_SECONDS = 15.0
_greenhouse_response_snapshot_last: dict[str, object] = {}


def write_greenhouse_response_snapshot(
    climate: dict[str, object],
    *,
    now: float | None = None,
    shown: dict[str, float | None] | None = None,
) -> None:
    """Record the effect the control cycle just computed, for the HTTPS relay.

    A small JSON file rather than a database row: the sync daemon wakes on every
    SQLite write, and this changes every cycle. Best effort -- a failed write
    only means the website falls back to its own model for a while.
    """
    if postgres_backend_enabled():
        return
    moment = time.monotonic() if now is None else float(now)
    with GREENHOUSE_RESPONSE_LOCK:
        state = dict(GREENHOUSE_RESPONSE_STATE)
    modelled = bool(climate.get("modelled"))
    effect = {
        metric: round(greenhouse_response_effect(state, metric), 3) if modelled else 0.0
        for metric in ("temp", "humidity")
    }
    # The cards exactly as the kiosk shows them (greenhouse_display_step).
    shown_values = (
        {metric: shown[metric] for metric in ("temp", "humidity")}
        if shown and all(isinstance(shown.get(metric), (int, float)) for metric in ("temp", "humidity"))
        else None
    )
    last = _greenhouse_response_snapshot_last
    if (
        last.get("effect") == effect
        and last.get("modelled") == modelled
        and last.get("shown") == shown_values
        and moment - float(last.get("written") or 0.0) < GREENHOUSE_RESPONSE_SNAPSHOT_REFRESH_SECONDS
    ):
        return
    snapshot = {"effect": effect, "modelled": modelled, "at": utc_now_iso()}
    if shown_values:
        snapshot["shown"] = shown_values
    try:
        GREENHOUSE_RESPONSE_RELAY_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = GREENHOUSE_RESPONSE_RELAY_FILE.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(snapshot), encoding="utf-8")
        os.replace(temporary, GREENHOUSE_RESPONSE_RELAY_FILE)
    except OSError:
        return
    last.update({"effect": effect, "modelled": modelled, "shown": shown_values, "written": moment})


def normalize_relayed_greenhouse_response(raw: object) -> dict[str, object] | None:
    """The relayed effect, or None when it is missing or malformed."""
    if not isinstance(raw, dict):
        return None
    effect_raw = raw.get("effect")
    if not isinstance(effect_raw, dict):
        return None
    effect: dict[str, float] = {}
    for metric in ("temp", "humidity"):
        value = effect_raw.get(metric, 0.0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        # Far beyond anything the model can produce: not a reading to show.
        if not math.isfinite(number) or abs(number) > 100:
            return None
        effect[metric] = number
    normalized: dict[str, object] = {"effect": effect, "modelled": raw.get("modelled") is True}
    # The kiosk's shown cards, from a Pi new enough to send them. A malformed
    # one is dropped on its own; the effect above still stands.
    shown_raw = raw.get("shown")
    if isinstance(shown_raw, dict):
        shown: dict[str, float] = {}
        for metric in ("temp", "humidity"):
            value = shown_raw.get(metric)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                break
            number = float(value)
            if not math.isfinite(number) or not -60.0 <= number <= 150.0:
                break
            shown[metric] = number
        else:
            normalized["shown"] = shown
    return normalized


def relayed_greenhouse_response(connection: sqlite3.Connection) -> dict[str, object] | None:
    """The Pi's effect as last relayed, when it is recent enough to show. Hosted only."""
    if not postgres_backend_enabled():
        return None
    try:
        row = connection.execute(
            "SELECT state_value, updated_at FROM system_state WHERE state_key = ?",
            (GREENHOUSE_RESPONSE_RELAY_STATE_KEY,),
        ).fetchone()
    except Exception:  # noqa: BLE001 - a display refinement must not break the page
        return None
    if row is None:
        return None
    try:
        age = (utc_now() - parse_iso_datetime(str(row["updated_at"] or ""))).total_seconds()
    except (TypeError, ValueError):
        return None
    if not -GREENHOUSE_RESPONSE_RELAY_MAX_AGE_SECONDS <= age <= GREENHOUSE_RESPONSE_RELAY_MAX_AGE_SECONDS:
        return None
    try:
        return normalize_relayed_greenhouse_response(json.loads(str(row["state_value"] or "")))
    except (TypeError, ValueError):
        return None


def greenhouse_card_readings(latest_readings, climate: dict[str, object] | None = None):
    """latest_readings with the DHT22 row reading as the cards show it.

    For everything the farm asked to follow the cards -- the crop-parameter
    alerts and the actuator safety limits -- rather than the part itself. The
    row keeps its captured_at, so freshness is judged exactly as before, and it
    drops its sensor_key so reading_metric_value does not bench-fit a number
    that has been fitted already. With no effect running the original row is
    passed through untouched.
    """
    climate = climate if climate is not None else greenhouse_climate_values(latest_readings)
    reading = latest_readings.get("dht22")
    if not reading or not climate.get("modelled"):
        return latest_readings
    payload = {
        metric: climate[metric]
        for metric in ("temp", "humidity")
        if isinstance(climate.get(metric), (int, float))
    }
    return {
        **latest_readings,
        "dht22": {
            "source_type": report_field(reading, "source_type", ""),
            "captured_at": reading_captured_at(reading),
            "reading_payload_json": json.dumps(payload),
        },
    }


GROW_LIGHT_LIMIT_LOCK = threading.Lock()
# The dark-spell count (GROW_LIGHT_DARK_LIMIT_HOURS). Kept by the Pi's control
# cycle only; "tick" and "bright" describe the last cycle and are not saved.
GROW_LIGHT_LIMIT_STATE: dict[str, object] = {}


def _load_grow_light_limit() -> dict[str, object]:
    """The saved count, or {} when there is none or it cannot be trusted."""
    try:
        raw = json.loads(GROW_LIGHT_LIMIT_FILE.read_text(encoding="utf-8"))
        seconds = {key: float(raw[key]) for key in ("lampSeconds", "brightSeconds")}
    except (OSError, ValueError, TypeError, KeyError):
        return {}
    if not all(math.isfinite(value) and 0.0 <= value <= 7 * 86400.0 for value in seconds.values()):
        return {}
    return seconds


def _save_grow_light_limit(state: dict[str, object], moment: float) -> None:
    saved = {key: float(state.get(key) or 0.0) for key in ("lampSeconds", "brightSeconds")}
    try:
        GROW_LIGHT_LIMIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = GROW_LIGHT_LIMIT_FILE.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(saved), encoding="utf-8")
        os.replace(temporary, GROW_LIGHT_LIMIT_FILE)
    except OSError:
        return
    state["savedAt"] = moment


def _grow_light_limit_summary(state: dict[str, object]) -> dict[str, object]:
    lamp_hours = float(state.get("lampSeconds") or 0.0) / 3600.0
    return {
        "lampHours": round(lamp_hours, 3),
        "limitHours": GROW_LIGHT_DARK_LIMIT_HOURS,
        "spent": bool(lamp_hours >= GROW_LIGHT_DARK_LIMIT_HOURS),
    }


def advance_grow_light_limit(latest_readings, *, now: float | None = None) -> dict[str, object] | None:
    """Count the lamp's hours in this dark spell, and reset them at daylight.

    Called once per control cycle, before the rules. The interval just gone is
    credited to what was true in it: the sensor's answer at the last cycle, and
    the lamp as the relays ran it (Automatic's last decision, or a manual On).
    Lamp time counts while the sensor does not read daylight; daylight held for
    GROW_LIGHT_RESET_MINUTES puts the count back to zero. No clock is read, so
    a Pi whose clock is wrong still counts right.

    Hosted keeps no count -- the Pi decides the relays -- and returns None,
    which the rule reads as "no limit known".
    """
    if postgres_backend_enabled():
        return None
    moment = time.monotonic() if now is None else float(now)
    reading = latest_readings.get(LIGHT_SENSOR_KEY)
    dark_value = reading_metric_value(reading, "dark")
    # Only a fresh "not dark" is daylight. A silent sensor resets nothing.
    bright = bool(
        irrigation_sensor_reading_is_fresh(reading)
        and dark_value is not None
        and not bool(dark_value)
    )
    light_mode = RELAY_ACTUATOR_MODE_CACHE.get("light", "automatic")
    lamp = light_mode == "on" or (
        light_mode == "automatic" and bool(RELAY_ACTUATOR_AUTO_CACHE.get("light"))
    )
    with GROW_LIGHT_LIMIT_LOCK:
        state = GROW_LIGHT_LIMIT_STATE
        if not state.get("loaded"):
            state.clear()
            state.update(_load_grow_light_limit())
            state["loaded"] = True
        last_tick = state.get("tick")
        if isinstance(last_tick, (int, float)):
            elapsed = moment - float(last_tick)
            if 0.0 < elapsed <= GROW_LIGHT_MAX_TICK_SECONDS:
                if state.get("bright"):
                    state["brightSeconds"] = float(state.get("brightSeconds") or 0.0) + elapsed
                    if float(state["brightSeconds"]) >= GROW_LIGHT_RESET_MINUTES * 60.0:
                        state["lampSeconds"] = 0.0
                else:
                    state["brightSeconds"] = 0.0
                    if lamp:
                        state["lampSeconds"] = float(state.get("lampSeconds") or 0.0) + elapsed
        state["tick"] = moment
        state["bright"] = bright
        saved_at = state.get("savedAt")
        if not isinstance(saved_at, (int, float)) or moment - float(saved_at) >= GROW_LIGHT_LIMIT_SAVE_SECONDS:
            _save_grow_light_limit(state, moment)
        return _grow_light_limit_summary(state)


def grow_light_limit_snapshot() -> dict[str, object] | None:
    """The count as the last control cycle left it, without advancing it."""
    if postgres_backend_enabled():
        return None
    with GROW_LIGHT_LIMIT_LOCK:
        if not GROW_LIGHT_LIMIT_STATE.get("loaded"):
            return None
        return _grow_light_limit_summary(dict(GROW_LIGHT_LIMIT_STATE))


def automatic_actuator_guidance(
    cultivations: list[sqlite3.Row] | list[dict[str, object]],
    latest_readings: dict[str, sqlite3.Row] | dict[str, dict[str, object]],
    *,
    local_now: datetime | None = None,
    running: dict[str, bool] | None = None,
    climate: dict[str, object] | None = None,
    light_limit: dict[str, object] | None = None,
) -> dict[str, dict[str, object]]:
    """What the automatic controller would do, plus the numbers behind it.

    The relays only need the answer; the dashboards need the reasoning. Someone
    reaching for the fan while the air is already dry enough is shown the
    reading and the threshold before the switch moves, and the sentence on
    screen has to quote the same numbers the controller acted on. Deriving both
    here rather than restating the rule in JavaScript is what keeps them from
    disagreeing -- these thresholds come from the crop parameters, so a
    hardcoded copy in the browser would be wrong on every farm.
    """
    dht_reading = latest_readings.get("dht22")
    reading_fresh = irrigation_sensor_reading_is_fresh(dht_reading)
    temperature = reading_metric_value(dht_reading, "temp")
    humidity = reading_metric_value(dht_reading, "humidity")
    # The greenhouse as greenhouse_climate_values() sees it: the DHT22 plus
    # what the running fan and lamp have done to the air. Deciding on this is
    # what lets an automatic fan stop once the house is back inside the range.
    if climate:
        if isinstance(climate.get("temp"), (int, float)):
            temperature = float(climate["temp"])
        if isinstance(climate.get("humidity"), (int, float)):
            humidity = float(climate["humidity"])

    light_reading = latest_readings.get(LIGHT_SENSOR_KEY)
    light_fresh = irrigation_sensor_reading_is_fresh(light_reading)
    # The HW-072 reports a threshold crossing, not a level: "dark" is a boolean
    # the sensor's own trimpot decides. reading_metric_value() returns it as
    # 1.0 or 0.0 because float(True) is 1.0, so None still means "no reading at
    # all" and is distinguishable from a real False -- which matters, because
    # False is exactly the value that must not be read as a missing sensor.
    dark_value = reading_metric_value(light_reading, "dark")
    is_dark = None if dark_value is None else bool(dark_value)

    temperature_floor, _temperature_ceiling = crop_parameter_bounds(cultivations, "temp")
    humidity_rows = crop_ceiling_rows(
        cultivations, "humidity", FAN_AUTO_FALLBACK_ON_HUMIDITY
    )
    temperature_rows = crop_ceiling_rows(
        cultivations, "temp", GREENHOUSE_VENT_FALLBACK_C
    )

    # Each bound is the strictest of the four rows, then relaxed by the shared
    # tolerance. See GREENHOUSE_SHARED_TEMP_TOLERANCE_C: one sensor decides for
    # four crops, and without the band the single most sensitive row ran the
    # whole greenhouse. A ceiling is relaxed upward and a floor downward, so
    # both move in the direction of "leave it alone a little longer".
    #
    # The displayed limit on the card stays the crop's own number, not this
    # one. What the band changes is when the relay answers, not what the crop
    # is understood to want.
    # The crops' own bounds. These are what the cards show and what the
    # advisory sentences quote, because they are what the crop actually wants.
    light_threshold = (
        temperature_floor if temperature_floor is not None else LIGHT_AUTO_FALLBACK_ON_C
    )
    fan_threshold = (
        min(float(row["ceiling"]) for row in humidity_rows)
        if humidity_rows else FAN_AUTO_FALLBACK_ON_HUMIDITY
    )
    vent_threshold = (
        min(float(row["ceiling"]) for row in temperature_rows)
        if temperature_rows else GREENHOUSE_VENT_FALLBACK_C
    )

    # Critical low as the cards draw it: the crops' floor minus the card's own
    # critical margin. The one point where daylight no longer holds the lamp
    # off -- the sun is plainly not keeping the house warm.
    light_critical_threshold = float(light_threshold) - GREENHOUSE_RESPONSE_CRITICAL_MARGIN["temp"]
    # Where damp air joins the lamp's cold rule (humid_and_cold): a tolerance
    # band and then an alert margin past the humidity ceiling.
    fan_act_threshold = (
        fan_threshold + GREENHOUSE_SHARED_HUMIDITY_TOLERANCE + GREENHOUSE_ALERT_HUMIDITY_MARGIN
    )

    # The farm's rule for the exhaust fan, judged against every active row's
    # parameters at once: the highest floor and the lowest ceiling, so the air
    # that meets them meets every row, custom ranges included ("ang
    # masusunod ay yung mas mababa para tumama lahat").
    #
    #   warning high   nothing. The fan stays off and nothing is announced.
    #   critical high  temperature or humidity past that lowest ceiling by the
    #                  card's own critical margin: the fan starts, and runs
    #                  until both are back inside every row's range -- a
    #                  deadband inside the ceiling, never past the middle --
    #                  and then stops.
    #
    # The start used to sit a lead *inside* the range, moved earlier still by
    # a rising trend. The farm asked for warning to mean "leave it", so both
    # are gone; the trend now only shapes how fast the cards move.
    fan_floor, _fan_ceiling_unused = crop_parameter_bounds(cultivations, "humidity")
    temp_floor_value = float(light_threshold)
    temp_ceiling_value = float(vent_threshold)
    humidity_ceiling_value = float(fan_threshold)
    humidity_floor_value = (
        float(fan_floor) if fan_floor is not None else humidity_ceiling_value - 15.0
    )

    def inset(floor: float, ceiling: float, deadband: float) -> float:
        # A deadband inside the ceiling, but never past the middle: rows whose
        # ranges only just overlap (18-20 C beside 20-30 C) leave no room.
        return min(deadband, max(0.0, ceiling - floor) / 2.0)

    fan_heat_start = temp_ceiling_value + GREENHOUSE_RESPONSE_CRITICAL_MARGIN["temp"]
    fan_heat_stop = temp_ceiling_value - inset(
        temp_floor_value, temp_ceiling_value, AUTOMATIC_TEMP_DEADBAND_C
    )
    fan_humidity_start = humidity_ceiling_value + GREENHOUSE_RESPONSE_CRITICAL_MARGIN["humidity"]
    fan_humidity_stop = humidity_ceiling_value - inset(
        humidity_floor_value, humidity_ceiling_value, AUTOMATIC_HUMIDITY_DEADBAND
    )
    # The lamp's cold half keeps its lead above the floor and deadband, never
    # past the middle of the range.
    temperature_middle = (
        (temp_floor_value + temp_ceiling_value) / 2.0
        if temp_floor_value <= temp_ceiling_value
        else None
    )
    lamp_heat_start = temp_floor_value + AUTOMATIC_TEMP_LEAD_C
    lamp_heat_stop = lamp_heat_start + AUTOMATIC_TEMP_DEADBAND_C
    if temperature_middle is not None:
        lamp_heat_start = min(lamp_heat_start, temperature_middle)
        lamp_heat_stop = min(lamp_heat_stop, temperature_middle)
    held = running or {}

    # Started by either reading at critical; once running, held until both are
    # back inside. The reasons report which reading still keeps it on. Both
    # read the same DHT22 and both are gated on it being fresh, so a silent
    # board starts nothing and holds nothing.
    fan_started = bool(
        reading_fresh
        and (
            (temperature is not None and temperature > fan_heat_start)
            or (humidity is not None and humidity > fan_humidity_start)
        )
    )
    fan_holding = bool(
        reading_fresh
        and (held.get("fanHeat") or held.get("fanHumidity"))
        and (
            (temperature is not None and temperature > fan_heat_stop)
            or (humidity is not None and humidity > fan_humidity_stop)
        )
    )
    fan_running_now = fan_started or fan_holding
    fan_too_hot = bool(
        fan_running_now and temperature is not None and temperature > fan_heat_stop
    )
    fan_too_humid = bool(
        fan_running_now and humidity is not None and humidity > fan_humidity_stop
    )
    # Two reasons to run the lamp, and either one is enough:
    #
    #   too dim   the light sensor says the sun is not doing the job. This is
    #             the grow light's actual purpose.
    #   too cold  the house is near the crop's temperature floor. The lamp's
    #             waste heat is the only heating the greenhouse has.
    #
    # Each half needs its own sensor to be fresh. A dead light sensor must not
    # read as darkness and leave the lamp on all day, and a dead DHT22 must not
    # read as cold -- so each condition is gated on the reading that justifies
    # it.
    #
    # The dark half stops once the lamp has run GROW_LIGHT_DARK_LIMIT_HOURS in
    # this dark spell, and starts again after daylight resets the count
    # (advance_grow_light_limit). Without a count -- the hosted API, or a
    # caller that passes none -- nothing is limited.
    dark_limit_reached = bool(light_limit and light_limit.get("spent"))
    light_too_dim = bool(is_dark is True and light_fresh and not dark_limit_reached)
    # The farm's rule for the cold half, against every row's parameters:
    #
    #   dark, near or below the floor   the lamp warms the house (it starts a
    #                                   lead inside the floor, as before).
    #   daylight, warning low           off. The sun is on the crop and a grow
    #                                   light through a bright morning is what
    #                                   "bumubukas kahit maliwanag" looked like.
    #   critical low, dark or daylight  on. The sun is plainly not keeping up.
    #
    # Once on for the cold it holds until the house is back inside the range
    # (the deadband above the floor), daylight or not, so it finishes the job
    # rather than stopping at warning low. A missing or stale light sensor is
    # not daylight, so a cold house with a dead light sensor still gets its lamp.
    #
    # The HW-072 has one threshold, a screw on the board, so dark and daylight
    # are exact opposites; the firmware's 2 s debounce absorbs the flapping.
    daylight = bool(is_dark is False and light_fresh)
    light_critically_cold = bool(
        temperature is not None
        and reading_fresh
        and temperature < light_critical_threshold
    )
    light_too_cold = bool(
        temperature is not None
        and reading_fresh
        and (
            (
                temperature < lamp_heat_start
                and (not daylight or light_critically_cold)
            )
            or (held.get("lightCold") and temperature < lamp_heat_stop)
        )
    )
    # Damp air in a cold house is the case the lamp is most worth running for.
    # It is not a third way to switch the lamp on -- a humid house that is
    # already warm needs the fan, not more heat -- and with the lamp now
    # starting at the floor even in daylight it is covered by light_too_cold;
    # it stays so the reason is still reported the same way.
    humid_and_cold = bool(
        temperature is not None
        and humidity is not None
        and reading_fresh
        and (not daylight or light_critically_cold)
        and humidity > fan_act_threshold
        and temperature_floor is not None
        and temperature < float(temperature_floor)
    )
    # Warning high and above: the lamp is not run for heat. It still runs for
    # the dark: the farm asked for "pag nag dark bubuhay", and with crop
    # ceilings of 20-23 C a greenhouse at 28 C every night meant the lamp
    # never came on at all. The dark half is bounded by its own limit instead
    # (GROW_LIGHT_DARK_LIMIT_HOURS); the heat half cannot fire in a hot house
    # anyway, so this only ever stood the dark half down.
    light_too_hot = bool(
        temperature is not None and reading_fresh and temperature > float(vent_threshold)
    )
    light_on = bool(light_too_dim or ((light_too_cold or humid_and_cold) and not light_too_hot))

    # The fan's own floor. It moves humidity out of the house and cannot put it
    # back, so at the crops' minimum it must stop rather than keep drying the
    # row out. It cuts the humidity reason only, never the heat one: a dry 38C
    # house has humidity below the crops' floor by definition, and cutting
    # there switched off the one actuator that could help.
    fan_cut_by_parameters = bool(
        fan_floor is not None
        and reading_fresh
        and humidity is not None
        and humidity <= float(fan_floor)
        and not fan_too_hot
    )
    if fan_cut_by_parameters:
        fan_too_humid = False
    fan_on = bool(fan_too_humid or fan_too_hot)

    humidity_affected_rows = [
        row for row in humidity_rows
        if humidity is not None and reading_fresh and humidity > float(row["ceiling"])
    ]
    temperature_affected_rows = [
        row for row in temperature_rows
        if temperature is not None and reading_fresh and temperature > float(row["ceiling"])
    ]
    humidity_affected_keys = {str(row["key"]) for row in humidity_affected_rows}
    temperature_affected_keys = {str(row["key"]) for row in temperature_affected_rows}
    affected_rows = [
        {
            "key": row_key,
            "label": cultivation_row_label(row_key),
            "reasons": [
                reason
                for reason, keys in (
                    ("humidity", humidity_affected_keys),
                    ("temperature", temperature_affected_keys),
                )
                if row_key in keys
            ],
        }
        for row_key in VALID_CULTIVATION_ROWS
        if row_key in humidity_affected_keys or row_key in temperature_affected_keys
    ]
    active_row_keys = {
        str(row["key"])
        for row in (*humidity_rows, *temperature_rows)
    }

    # Two conditions, one remedy. The fan can pull humidity down but cannot
    # cool the house, and above the crop's ceiling there is no actuator left --
    # so the alert names which one is out and asks for the one thing that
    # helps, rather than leaving a relay to look like it is coping.
    # Named for the conditions themselves, not for whether the fan is running.
    # These used to read too_humid = fan_on, which was the same thing only
    # while humidity was the fan's sole trigger -- with the heat half added, a
    # hot but perfectly dry house would otherwise report its reason as "both"
    # and the alert would ask the operator to fix humidity that is fine.
    # The same critical points the fan answers at, not a further margin beyond
    # them. These used to be the crop's own bounds, so the alert fired the
    # moment a reading went a fraction out of range -- every warm afternoon
    # asked someone to come and open a greenhouse that was fine, and an alert
    # that arrives when nothing needs doing is one people stop reading.
    #
    # Critical is the right point for both because the fan is the only thing
    # that can answer and it is already running: the house being critical IS
    # the case where a person may have to open it. Asking later would mean
    # nobody is told until the crop is past saving.
    #
    # Critical as the cards draw it -- the lowest ceiling plus the card's own
    # critical margin, the same point the fan now starts at. The humidity half
    # used to fire at ceiling + 13 %, inside the card's amber band, and the
    # farm asked for nothing to be announced at warning.
    too_humid = bool(
        humidity is not None and reading_fresh and humidity > fan_humidity_start
    )
    too_hot = bool(
        temperature is not None and reading_fresh and temperature > fan_heat_start
    )
    if too_hot and too_humid:
        vent_reason = "both"
    elif too_hot:
        vent_reason = "temperature"
    elif too_humid:
        vent_reason = "humidity"
    else:
        vent_reason = ""

    return {
        "fan": {
            "on": fan_on,
            "humidity": humidity,
            "readingFresh": reading_fresh,
            "thresholdPercent": round(float(fan_threshold), 2),
            # Which half asked for it, the way the light entry below reports
            # its own two halves. Without these the card had only humidity to
            # go on, so a fan running because the house was hot looked like a
            # fan running for no reason -- and the advisory would offer to
            # switch it off, quoting a humidity reading that was perfectly
            # fine. Both thresholds travel with it so the copy can quote the
            # crops' own number rather than restating a rule in JavaScript.
            "tooHumid": fan_too_humid,
            "tooHot": fan_too_hot,
            "temperature": temperature,
            "thresholdCelsius": round(float(vent_threshold), 2),
            "affectedRows": [
                {"key": row["key"], "label": row["label"]}
                for row in humidity_affected_rows
            ],
            "servedRows": [
                {"key": row["key"], "label": row["label"]}
                for row in humidity_rows
            ],
            # True when the threshold came from a crop's own parameters rather
            # than the installation-wide fallback, so the copy can say which.
            "fromCropParameters": any(
                bool(row["fromCropParameters"]) for row in humidity_rows
            ),
        },
        "light": {
            "on": light_on,
            "temperature": temperature,
            "readingFresh": reading_fresh,
            # Which half asked for it, so the card can say why rather than
            # leaving the operator to guess between the two.
            #
            # "dark" replaced "lux" when the BH1750 gave way to the HW-072.
            # There is no level to report any more and no threshold to report
            # with it -- the threshold is a trimpot on the sensor board, which
            # the server cannot read. The cards say "dim" or "daylight" instead
            # of a number, and "luxThreshold"/"daylightThreshold" are gone
            # rather than sent as nulls that the frontend would have to guard.
            "dark": is_dark,
            "lightFresh": light_fresh,
            "tooDim": light_too_dim,
            # The lamp's hours in this dark spell against its limit. The card
            # needs them to explain a lamp that is off in a dark house.
            "darkLimitReached": dark_limit_reached,
            "lampHoursThisDark": light_limit.get("lampHours") if light_limit else None,
            "darkLimitHours": GROW_LIGHT_DARK_LIMIT_HOURS,
            "tooCold": light_too_cold,
            # True while the sun is doing the heating the lamp would otherwise
            # be run for. The card needs it to explain a cold house with the
            # lamp off, which otherwise reads as the rule failing.
            "daylight": daylight,
            # Warning high or above: not run for heat (the dark still runs it).
            "tooHot": light_too_hot,
            # Critical low, where daylight stops holding the lamp off.
            "criticalC": round(float(light_critical_threshold), 2),
            "thresholdC": round(float(light_threshold), 2),
            "fromCropParameters": temperature_floor is not None,
        },
        "greenhouse": {
            "open": bool(vent_reason),
            "reason": vent_reason,
            "humidity": humidity,
            "temperature": temperature,
            "humidityCeiling": round(float(fan_threshold), 2),
            "temperatureCeiling": round(float(vent_threshold), 2),
            "affectedRows": affected_rows,
            "allRowsAffected": bool(vent_reason) and (
                not active_row_keys
                or {str(row["key"]) for row in affected_rows} == active_row_keys
            ),
            "activeRowCount": len(active_row_keys),
            "readingFresh": reading_fresh,
            "fromCropParameters": any(
                bool(row["fromCropParameters"])
                for row in (*humidity_rows, *temperature_rows)
            ),
        },
    }


def automatic_actuator_states(
    cultivations: list[sqlite3.Row] | list[dict[str, object]],
    latest_readings: dict[str, sqlite3.Row] | dict[str, dict[str, object]],
    *,
    local_now: datetime | None = None,
) -> dict[str, bool]:
    guidance = automatic_actuator_guidance(cultivations, latest_readings, local_now=local_now)
    # "greenhouse" is advice for a person, not a relay, so it is not returned
    # here: build_relay_desired_state would look for an output to drive.
    return {key: bool(guidance[key]["on"]) for key in AUTOMATIC_ACTUATOR_KEYS}


def build_irrigation_rows_payload(
    cultivations: list[sqlite3.Row] | list[dict[str, object]],
    latest_readings: dict[str, sqlite3.Row] | dict[str, dict[str, object]],
    sensor_registry: dict[str, sqlite3.Row] | dict[str, dict[str, object]],
    row_settings: list[sqlite3.Row] | list[dict[str, object]],
    row_controls: list[sqlite3.Row] | list[dict[str, object]],
    settled_ph: dict[str, float] | None = None,
) -> list[dict[str, object]]:
    """One entry per row, with every line's reading, range and need.

    settled_ph (settled_rs485_ph_by_row), when given, is a second opinion on
    the lime line's critical need only. The reading shown, `needs` and the
    tank card's direction stay on the latest reading, so the page keeps pace
    with the probe; Automatic just will not start lime on one noisy sample.
    """
    cultivation_by_row = active_cultivation_row_map(cultivations)
    # Keyed by the cultivation that owns the setting, never by row_key.
    # row_key is UNIQUE on both control tables, so a row left behind by a
    # cultivation that is already gone still holds its slot -- and keying on
    # row_key handed that dead row's mode straight back to the planting that
    # replaced it. purge_orphaned_irrigation_row_rows clears those; this makes
    # sure one can never be read even before it does.
    settings_by_cultivation_channel = {
        (str(setting["cultivation_id"]), str(setting["channel_key"]).strip()): setting
        for setting in row_settings
    }
    controls_by_cultivation = {
        str(control["cultivation_id"]): control
        for control in row_controls
    }
    rows: list[dict[str, object]] = []

    for row_key in VALID_CULTIVATION_ROWS:
        cultivation = cultivation_by_row.get(row_key)
        active = cultivation is not None
        cultivation_key = str(cultivation["id"]) if cultivation is not None else ""
        # What the page shows...
        readings = {
            channel_key: irrigation_row_sensor_value(latest_readings, row_key, channel_key)
            for channel_key in IRRIGATION_CHANNEL_SENSOR_METRICS
        }
        # ...and what every decision below is made on. The two are the same
        # probe reading, except on a row stored before 2026-10-02 whose shown
        # EC or pH was eased (SOIL_DOSE_MEASURED_KEYS).
        measured_readings = {
            channel_key: soil_measured_metric_value(
                latest_readings.get(f"{row_key}-{IRRIGATION_CHANNEL_SENSOR_METRICS[channel_key][0]}"),
                IRRIGATION_CHANNEL_SENSOR_METRICS[channel_key][1],
            )
            for channel_key in IRRIGATION_CHANNEL_SENSOR_METRICS
        }
        captured_at = {
            channel_key: reading_captured_at(
                latest_readings.get(f"{row_key}-{IRRIGATION_CHANNEL_SENSOR_METRICS[channel_key][0]}")
            )
            for channel_key in IRRIGATION_CHANNEL_SENSOR_METRICS
        }
        thresholds = {
            "water": irrigation_parameter_range(cultivation, "moisture"),
            "fertilizer": irrigation_parameter_range(cultivation, "ec"),
            "limeSolution": irrigation_parameter_range(cultivation, "ph"),
        }
        sensor_power = {
            "water": sensor_control_state(sensor_registry, f"{row_key}-moisture"),
            "fertilizer": sensor_control_state(sensor_registry, f"{row_key}-rs485"),
            "limeSolution": sensor_control_state(sensor_registry, f"{row_key}-rs485"),
        }
        needs: dict[str, bool] = {}
        critical_needs: dict[str, bool] = {}
        availability: dict[str, bool] = {}
        automatic_enabled: dict[str, bool] = {}
        row_channels: dict[str, dict[str, object]] = {}
        lime_solution_needed: str | None = None

        for channel_key in IRRIGATION_CHANNEL_SENSOR_METRICS:
            value = measured_readings[channel_key]
            threshold = thresholds[channel_key]
            sensor_suffix, _metric_key = IRRIGATION_CHANNEL_SENSOR_METRICS[channel_key]
            sensor_reading = latest_readings.get(f"{row_key}-{sensor_suffix}")
            available = (
                active
                and sensor_power[channel_key] == "on"
                and value is not None
                and threshold is not None
                and irrigation_sensor_reading_is_fresh(sensor_reading)
                # pH 0 is what the board sends for a probe out of the soil.
                # For fertilizer it stays "no reading": EC 0 there is not a
                # hungry row. For lime it is kept as a reading, as the farm
                # asked: the row still has to be corrected before planting, so
                # it asks for pH Up. The tank card holds the line until someone
                # confirms, so nothing doses unasked.
                and not (
                    sensor_suffix == "rs485"
                    and channel_key != "limeSolution"
                    and rs485_probe_out_of_soil(sensor_reading)
                )
            )
            availability[channel_key] = available
            margin = irrigation_channel_critical_margin(channel_key)
            if channel_key == "limeSolution":
                critical_needs[channel_key] = bool(
                    available
                    and (
                        value < float(threshold["min"]) - margin
                        or value > float(threshold["max"]) + margin
                    )
                )
                settled = settled_ph.get(row_key) if settled_ph else None
                if critical_needs[channel_key] and settled is not None:
                    # The settled pH has to be critical on the same side too.
                    # One dip of this probe reaches critical on soil that is
                    # fine; two minutes of it being there does not.
                    if value < float(threshold["min"]):
                        critical_needs[channel_key] = float(settled) < float(threshold["min"]) - margin
                    else:
                        critical_needs[channel_key] = float(settled) > float(threshold["max"]) + margin
            else:
                critical_needs[channel_key] = bool(
                    available and value < float(threshold["min"]) - margin
                )
            if channel_key == "limeSolution":
                # Either direction is a real need: too acidic calls for pH Up,
                # too alkaline for pH Down. The other channels only ever add,
                # so for them "below the minimum" remains the whole story.
                needs[channel_key] = bool(
                    available
                    and (value < float(threshold["min"]) or value > float(threshold["max"]))
                )
                lime_solution_needed = (
                    None
                    if not needs[channel_key]
                    else ("up" if value < float(threshold["min"]) else "down")
                )
            else:
                needs[channel_key] = bool(available and value < float(threshold["min"]))
            setting = (
                settings_by_cultivation_channel.get((cultivation_key, channel_key))
                if active else None
            )
            automatic_enabled[channel_key] = bool(int(setting["automatic_enabled"] or 0)) if setting else True
            default_channel = next(
                channel for channel in DEFAULT_IRRIGATION_CHANNELS
                if str(channel["channel_key"]).strip() == channel_key
            )
            row_channels[channel_key] = {
                "automaticEnabled": automatic_enabled[channel_key],
                "automaticDuration": str(
                    int(setting["automatic_duration_seconds"])
                    if setting else int(default_channel["automatic_duration_seconds"])
                ),
                "manualDuration": str(
                    int(setting["manual_duration_seconds"])
                    if setting else int(default_channel["manual_duration_seconds"])
                ),
                "scheduleEnabled": bool(int(setting["schedule_enabled"] or 0)) if setting else True,
                "scheduleStartTime": str(
                    setting["schedule_start_time"]
                    if setting else default_channel["schedule_start_time"]
                ).strip(),
                "scheduleDuration": str(
                    int(setting["schedule_duration_seconds"])
                    if setting else int(default_channel["schedule_duration_seconds"])
                ),
                "scheduleFrequency": normalize_irrigation_frequency(
                    setting["schedule_frequency"]
                    if setting else default_channel["schedule_frequency"]
                ),
            }

        control = controls_by_cultivation.get(cultivation_key) if active else None

        rows.append(
            {
                "key": row_key,
                "label": cultivation_row_label(row_key),
                "active": active,
                "cultivationId": str(cultivation["id"]) if cultivation is not None else "",
                "crop": str(cultivation["crop_name"]).strip() if cultivation is not None else "",
                "scheduleAnchorDate": str(cultivation["planting_date"]).strip() if cultivation is not None else "",
                "mode": normalize_irrigation_mode(control["mode"]) if control is not None else "automatic",
                "controllerEnabled": bool(int(control["is_enabled"] or 0)) if control is not None else active,
                "readings": readings,
                "capturedAt": captured_at,
                "thresholds": thresholds,
                "sensorAvailable": availability,
                "needs": needs,
                # Past the critical margin on the side the line corrects: the
                # point at which Automatic starts. `needs` (outside the range
                # at all) is what keeps it running once it has started, so it
                # stops as soon as the reading is back to normal.
                "criticalNeeds": critical_needs,
                # "up", "down", or None. Which solution the lime tank has to be
                # holding for this row right now; the card in the browser names
                # it, and an automatic lime run waits until it is acknowledged.
                "limeSolutionNeeded": lime_solution_needed,
                "automaticEnabled": automatic_enabled,
                "channels": row_channels,
            }
        )

    return rows


def cut_irrigation_rows_at_target(
    active_rows: dict[str, dict[str, bool]],
    rows: list[dict[str, object]],
) -> dict[str, dict[str, bool]]:
    """Drop any line whose sensor says the row has reached its crop parameter.

    Automatic irrigation has always stopped this way -- it has no timer at all,
    and runs until the reading comes up to the configured minimum. Scheduled
    runs did not: they ran out their duration whatever the soil said, because
    the duration was the only thing that could stop them.

    A schedule fires on the clock with nobody standing there, and the supply
    lines are fast enough to overshoot inside one window: a row can reach its
    target part-way through a 45-second schedule window, and nothing would have
    closed the valve until the window ended. So the target is a ceiling on
    scheduled runs. The duration still decides how long a run may last; this
    decides when it must stop early.

    Manual runs do not pass through here. They did from September 24 until the
    farm asked for the lock to come off (2026-10-05): a manual press now starts
    on any reading and runs the duration that was typed.

    Only a positive "this row no longer needs it" cuts a line. A row whose
    sensor is missing, unpowered, stale, or has no crop parameter reports
    needs=False for want of evidence, not because the target was met, and
    cutting on that would make a dead sensor look like a satisfied row -- so
    those keep running on their timer, which is the behaviour they had before
    any of this. sensorAvailable is what tells the two cases apart.
    """
    rows_by_key = {str(row.get("key") or ""): row for row in rows}
    cut: dict[str, dict[str, bool]] = {}
    for channel_key, row_map in active_rows.items():
        kept: dict[str, bool] = {}
        for row_key, is_on in row_map.items():
            if not is_on:
                continue
            row = rows_by_key.get(row_key)
            if row is None:
                kept[row_key] = True
                continue
            available = bool((row.get("sensorAvailable") or {}).get(channel_key))
            needs = bool((row.get("needs") or {}).get(channel_key))
            if available and not needs:
                # Measured, in range: this row has had enough.
                continue
            kept[row_key] = True
        if kept:
            cut[channel_key] = kept
    return cut


def lime_tank_acknowledgement_key(row_key: str, solution_key: str, cultivation_id: object = "") -> str:
    """Names one answer to the tank card: this row, this planting, this solution.

    The cultivation is part of the key because an answer belongs to the crop it
    was given for. Keyed on the row alone, a "pH Up is loaded" from the last
    planting carried straight over to the next one, so starting a cultivation
    switched the lime line on at once -- before anyone had been asked which
    solution the new crop needed.
    """
    cultivation = str(cultivation_id or "").strip()
    if cultivation:
        return f"{row_key}:{cultivation}:{solution_key}"
    return f"{row_key}:{solution_key}"


def lime_tank_row_acknowledgement_key(row: dict[str, object]) -> str:
    """The key this row's tank card is answered under, or "" when none is asked."""
    solution_key = str(row.get("limeSolutionNeeded") or "").strip()
    if not solution_key:
        return ""
    return lime_tank_acknowledgement_key(
        str(row.get("key") or ""), solution_key, row.get("cultivationId")
    )


def relevant_lime_tank_acknowledgements(
    rows: list[dict[str, object]],
    acknowledged: dict[str, bool],
) -> dict[str, bool]:
    """The answers that still belong to a row's current planting.

    An answer is kept while its row grows the same cultivation and does not
    need the opposite solution -- including while the pH is back inside the
    range. It used to be kept only while the row was out of range right now,
    and the RS485 pH swings in and out of range by itself, so a confirmed
    tank was forgotten on the next in-range reading and asked for again a
    moment later. A new planting still drops it (the cultivation is in the
    key), and so does the row needing the other solution.
    """
    relevant: dict[str, bool] = {}
    rows_by_key = {str(row.get("key") or ""): row for row in rows}
    for ack_key, answered in acknowledged.items():
        if not answered:
            continue
        row_key, _, rest = str(ack_key).partition(":")
        row = rows_by_key.get(row_key)
        if row is None or not row.get("active", True):
            continue
        cultivation, _, solution = rest.rpartition(":")
        if solution not in ("up", "down"):
            continue
        if cultivation != str(row.get("cultivationId") or "").strip():
            continue
        needed = str(row.get("limeSolutionNeeded") or "").strip()
        if needed and needed != solution:
            continue
        relevant[str(ack_key)] = True
    return relevant


def hold_unconfirmed_lime_runs(
    run_rows: dict[str, dict[str, bool]],
    rows: list[dict[str, object]],
    acknowledged: dict[str, bool],
) -> dict[str, dict[str, bool]]:
    """Drop every lime run whose row is still waiting on the tank card.

    Automatic, scheduled and manual runs all pass through this. A schedule
    fires on the clock and nobody is standing there when it does, so it needed
    the same hold automatic already had; manual is held here too so a client
    that skipped the card still cannot dose the wrong solution.
    """
    lime_rows = run_rows.get("limeSolution")
    if not lime_rows:
        return run_rows
    rows_by_key = {str(row.get("key") or ""): row for row in rows}
    kept: dict[str, bool] = {}
    for row_key, is_on in lime_rows.items():
        if not is_on:
            continue
        row = rows_by_key.get(row_key)
        ack_key = lime_tank_row_acknowledgement_key(row) if row is not None else ""
        # No key means no pH Up or pH Down need was detected -- the pH is in
        # range, or its probe is off, stale or out of the soil. Either way
        # nobody can have confirmed the right solution, so the line does not
        # run. It used to, on its timer, whenever the pH could not be read.
        if not ack_key or not acknowledged.get(ack_key):
            continue
        kept[row_key] = True
    held = {
        channel: dict(row_map)
        for channel, row_map in run_rows.items()
        if channel != "limeSolution"
    }
    if kept:
        held["limeSolution"] = kept
    return held


def acknowledged_lime_tank_solutions(state_values: dict[str, str]) -> dict[str, bool]:
    """Which row/solution pairs someone has confirmed the tank holds.

    Written by the browser when the tank card is accepted. Stored per row and
    per direction: confirming pH Up for row 1 says nothing about row 2, and
    nothing about row 1 once it needs pH Down instead -- that is a different
    solution physically in the tank, so it has to be checked again.
    """
    parsed = parse_json_object(state_values.get("irrigation.lime_tank_ack") or "{}")
    return {
        str(key).strip(): normalize_bool_flag(value)
        for key, value in parsed.items()
        if str(key).strip()
    }


def irrigation_channel_critical_margin(channel_key: str) -> float:
    """How far past the crop range a line's reading must be to be critical.

    The same margin the reading alerts use (READING_ALERT_RULES), so the page's
    "Critical Low" and the point Automatic starts at are one and the same.
    """
    metric = IRRIGATION_CHANNEL_SENSOR_METRICS.get(channel_key, ("", ""))[1]
    for rule in READING_ALERT_RULES:
        if rule["metric"] == metric and not rule.get("shared"):
            return float(rule.get("criticalMargin") or 0.0)
    return 0.0


def automatic_irrigation_row_map(
    rows: list[dict[str, object]],
    channels: dict[str, dict[str, object]],
    *,
    mode: str,
    auto_enabled: bool,
    lime_tank_acknowledged: dict[str, bool] | None = None,
    running_rows: dict[str, dict[str, bool]] | None = None,
) -> dict[str, dict[str, bool]]:
    """Which lines Automatic runs now.

    A line starts only when its reading is critical -- past the crop range by
    the critical margin -- and, once running, keeps going until the reading is
    back inside the range. A reading that is merely low (warning) does not
    start it: Automatic is the unattended safety net, and topping up a row that
    is only slightly low is what over-watered, over-fed and over-corrected
    rows. Manual is how an operator answers a warning.

    running_rows is what Automatic was already running (the stored
    irrigation.active_automatic_rows). Without it a run would stop the moment
    the reading left the critical band, well short of normal.
    """
    if not auto_enabled:
        return {}
    acknowledged = lime_tank_acknowledged or {}
    running = running_rows or {}
    automatic_rows: dict[str, dict[str, bool]] = {}
    for channel in DEFAULT_IRRIGATION_CHANNELS:
        channel_key = str(channel["channel_key"]).strip()
        matching_rows: dict[str, bool] = {}
        for row in rows:
            row_key = str(row["key"])
            if not (
                bool(row.get("active"))
                and bool(row.get("controllerEnabled"))
                and normalize_irrigation_mode(row.get("mode")) == "automatic"
                and bool((row.get("automaticEnabled") or {}).get(channel_key))
                and bool((row.get("needs") or {}).get(channel_key))
            ):
                continue
            already_running = bool(running.get(channel_key, {}).get(row_key))
            if not already_running and not bool(
                (row.get("criticalNeeds") or {}).get(channel_key)
            ):
                continue
            if channel_key == "limeSolution":
                if not already_running and bool(row.get("limeResting")):
                    # A dose went in minutes ago; let it spread before the
                    # probe is believed again.
                    continue
            if channel_key == "limeSolution":
                # The tank holds pH Up or pH Down, never both, and dosing the
                # wrong one drives the pH further from target. Hold the run
                # until someone confirms which solution is actually loaded.
                ack_key = lime_tank_row_acknowledgement_key(row)
                if not ack_key or not acknowledged.get(ack_key):
                    continue
            matching_rows[row_key] = True
        if matching_rows:
            automatic_rows[channel_key] = matching_rows
    return automatic_rows


def irrigation_local_now() -> datetime:
    return datetime.now(IRRIGATION_LOCAL_TIMEZONE)


def irrigation_frequency_days(value: object) -> int:
    return {
        "daily": 1,
        "every-2-days": 2,
        "every-3-days": 3,
        "weekly": 7,
    }[normalize_irrigation_frequency(value)]


def scheduled_irrigation_row_windows(
    rows: list[dict[str, object]],
    armed_rows: dict[str, bool],
    *,
    local_now: datetime | None = None,
) -> dict[str, dict[str, tuple[datetime, datetime]]]:
    """Today's schedule window, start and end, for every armed schedule line."""
    now = local_now or irrigation_local_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=IRRIGATION_LOCAL_TIMEZONE)
    else:
        now = now.astimezone(IRRIGATION_LOCAL_TIMEZONE)

    windows: dict[str, dict[str, tuple[datetime, datetime]]] = {}
    for row in rows:
        row_key = str(row.get("key") or "").strip().lower()
        if not (
            armed_rows.get(row_key)
            and bool(row.get("active"))
            and bool(row.get("controllerEnabled"))
            and normalize_irrigation_mode(row.get("mode")) == "schedule"
        ):
            continue

        anchor_text = str(row.get("scheduleAnchorDate") or "").strip()
        try:
            anchor_date = datetime.strptime(anchor_text, "%Y-%m-%d").date()
        except ValueError:
            anchor_date = now.date()
        days_since_anchor = (now.date() - anchor_date).days

        for channel in DEFAULT_IRRIGATION_CHANNELS:
            channel_key = str(channel["channel_key"]).strip()
            settings = (row.get("channels") or {}).get(channel_key) or {}
            if not normalize_bool_flag(settings.get("scheduleEnabled"), default=True):
                continue
            frequency_days = irrigation_frequency_days(settings.get("scheduleFrequency"))
            if days_since_anchor < 0 or days_since_anchor % frequency_days != 0:
                continue

            start_minute = actuator_schedule_minute(
                settings.get("scheduleStartTime"),
                str(channel["schedule_start_time"]),
            )
            try:
                duration_seconds = max(
                    IRRIGATION_MIN_DURATION_SECONDS,
                    int(settings.get("scheduleDuration") or 0),
                )
            except (TypeError, ValueError):
                duration_seconds = max(
                    IRRIGATION_MIN_DURATION_SECONDS,
                    int(channel["schedule_duration_seconds"]),
                )
            scheduled_start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
                minutes=start_minute
            )
            scheduled_end = scheduled_start + timedelta(seconds=duration_seconds)
            windows.setdefault(channel_key, {})[row_key] = (scheduled_start, scheduled_end)

    return windows


def scheduled_irrigation_row_map(
    rows: list[dict[str, object]],
    armed_rows: dict[str, bool],
    *,
    local_now: datetime | None = None,
) -> dict[str, dict[str, bool]]:
    """Return only schedule lines whose own start/duration window is active."""
    now = local_now or irrigation_local_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=IRRIGATION_LOCAL_TIMEZONE)
    else:
        now = now.astimezone(IRRIGATION_LOCAL_TIMEZONE)

    active_rows: dict[str, dict[str, bool]] = {}
    for channel_key, row_windows in scheduled_irrigation_row_windows(
        rows, armed_rows, local_now=now
    ).items():
        for row_key, (scheduled_start, scheduled_end) in row_windows.items():
            if scheduled_start <= now < scheduled_end:
                active_rows.setdefault(channel_key, {})[row_key] = True

    return active_rows


def seconds_until_next_schedule_start(
    rows: list[dict[str, object]],
    armed_rows: dict[str, bool],
) -> float | None:
    """Seconds until the next armed schedule window opens today, if any.

    The control worker otherwise notices a window only on its next pass, up to
    IRRIGATION_CONTROL_INTERVAL_SECONDS late, and the line then waters that much
    less than the schedule says, because the window still closes on time.
    """
    now = irrigation_local_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=IRRIGATION_LOCAL_TIMEZONE)
    soonest: float | None = None
    for row_windows in scheduled_irrigation_row_windows(rows, armed_rows, local_now=now).values():
        for scheduled_start, _scheduled_end in row_windows.values():
            wait = (scheduled_start - now).total_seconds()
            if wait > 0 and (soonest is None or wait < soonest):
                soonest = wait
    return soonest


def system_state_map(connection: sqlite3.Connection) -> dict[str, str]:
    """Every state value the controllers read, without the command markers.

    The hardware_command rows are one per hosted press, kept only so a replay
    is recognised; nothing that calls this reads them. On the farm Pi they were
    15,000 rows (a bulk notification delete queues one command per entry) and
    reading them made every irrigation read take a quarter of a second -- a
    Start then queued behind the page's refreshes for 4 to 10 seconds, the
    page's 10 second request timeout fired, and the retried press switched the
    line on a second time.
    """
    rows = connection.execute(
        """
        SELECT state_key, state_value
        FROM system_state
        WHERE state_key NOT LIKE 'hardware_command%'
        """
    ).fetchall()
    return {str(row["state_key"]).strip(): str(row["state_value"]).strip() for row in rows}


def build_irrigation_payload(connection: sqlite3.Connection) -> dict[str, object]:
    settings = list_irrigation_settings(connection)
    state_values = system_state_map(connection)
    channels: dict[str, dict[str, str]] = {}

    for row in settings:
        channels[str(row["channel_key"]).strip()] = {
            "automaticEnabled": bool(int(row["automatic_enabled"] or 0)),
            "automaticDuration": str(int(row["automatic_duration_seconds"])),
            "manualDuration": str(int(row["manual_duration_seconds"])),
            "scheduleEnabled": bool(int(row["schedule_enabled"] or 0)),
            "scheduleStartTime": str(row["schedule_start_time"]).strip(),
            "scheduleDuration": str(int(row["schedule_duration_seconds"])),
            "scheduleFrequency": normalize_irrigation_frequency(row["schedule_frequency"]),
        }

    cultivations = list_cultivations(connection)
    row_settings = list_irrigation_row_settings(connection)
    row_controls = list_irrigation_row_controls(connection)
    registry_rows = list_sensor_registry(connection)
    latest_readings = latest_sensor_readings_by_key(connection)
    sensor_registry = {str(row["sensor_key"]).strip(): row for row in registry_rows}
    irrigation_rows = build_irrigation_rows_payload(
        cultivations,
        latest_readings,
        sensor_registry,
        row_settings,
        row_controls,
        settled_ph=settled_rs485_ph_by_row(connection),
    )
    resting = lime_resting_rows(connection)
    for row in irrigation_rows:
        row["limeResting"] = str(row.get("key") or "") in resting
    target_rows = filter_active_irrigation_rows(
        state_values.get("irrigation.target_rows"),
        cultivations,
    )
    schedule_armed_rows = filter_active_irrigation_rows(
        state_values.get("irrigation.schedule_armed_rows"),
        cultivations,
    )
    lime_tank_acknowledged = relevant_lime_tank_acknowledgements(
        irrigation_rows, acknowledged_lime_tank_solutions(state_values)
    )
    # Manual is not cut at the crop target: a person pressed Start and typed
    # the duration, and that duration is what ends the run. Only the lime tank
    # confirmation still stands between a manual press and the valve.
    active_manual_rows = hold_unconfirmed_lime_runs(
        filter_active_irrigation_channel_rows(
            state_values.get("irrigation.active_manual_rows"),
            cultivations,
        ),
        irrigation_rows,
        lime_tank_acknowledged,
    )
    active_schedule_rows = hold_unconfirmed_lime_runs(
        cut_irrigation_rows_at_target(
            drop_finished_schedule_windows(
                scheduled_irrigation_row_map(irrigation_rows, schedule_armed_rows),
                finished_schedule_windows(
                    connection,
                    scheduled_irrigation_row_windows(irrigation_rows, schedule_armed_rows),
                ),
            ),
            irrigation_rows,
        ),
        irrigation_rows,
        lime_tank_acknowledged,
    )
    computed_automatic_rows = automatic_irrigation_row_map(
        irrigation_rows,
        channels,
        mode=state_values.get("irrigation.mode", "automatic"),
        auto_enabled=normalize_bool_flag(state_values.get("irrigation.auto_enabled"), default=True),
        lime_tank_acknowledged=lime_tank_acknowledged,
        running_rows=filter_active_irrigation_channel_rows(
            state_values.get("irrigation.active_automatic_rows"), cultivations
        ),
    )
    active_manual_lines = normalize_irrigation_line_map(
        state_values.get("irrigation.active_manual_lines"),
        state_values.get("irrigation.active_manual_line", ""),
    )
    active_schedule_lines = irrigation_lines_from_row_map(active_schedule_rows)
    active_automatic_lines = normalize_irrigation_line_map(state_values.get("irrigation.active_automatic_lines"))

    return {
        # How much longer each timed run has, so the board holding the valve can
        # close it on its own clock instead of waiting for a second command.
        # See irrigation_run_deadlines_ms for why that matters.
        "runDeadlinesMs": irrigation_run_deadlines_ms(connection),
        # The misting line is the one actuator that can be on a timer, and its
        # close travelled the same slow path a run's did.
        "actuatorDeadlinesMs": actuator_deadlines_ms(connection),
        # The same two deadlines as wall-clock times. The relay snapshot is
        # built from these, because the remaining times above are stale the
        # moment this payload is cached.
        "runDeadlinesAtMs": irrigation_run_deadlines_at_ms(connection),
        "actuatorDeadlinesAtMs": actuator_deadlines_at_ms(connection),
        "mode": normalize_irrigation_mode(state_values.get("irrigation.mode")),
        "autoEnabled": normalize_bool_flag(state_values.get("irrigation.auto_enabled"), default=True),
        "activeManualLine": first_active_irrigation_line(active_manual_lines),
        "activeManualLines": active_manual_lines,
        "activeScheduleLines": active_schedule_lines,
        "activeAutomaticLines": irrigation_lines_from_row_map(computed_automatic_rows) or active_automatic_lines,
        "targetRows": target_rows,
        "scheduleArmedRows": schedule_armed_rows,
        "activeManualRows": active_manual_rows,
        "activeScheduleRows": active_schedule_rows,
        "activeAutomaticRows": computed_automatic_rows,
        "rowModes": {
            str(row["key"]): str(row["mode"])
            for row in irrigation_rows
            if bool(row.get("active"))
        },
        "rows": irrigation_rows,
        # The tank cards already answered, so a second screen -- the phone,
        # the panel -- does not ask again for a row someone has confirmed.
        "limeTankAcknowledged": lime_tank_acknowledged,
        "overlayMode": "",
        "channels": channels,
    }


# A row that is simply gone cannot be told apart from one that never arrived,
# so a plain DELETE on one device reads to the other as "you are missing
# something" and comes straight back on the next sync. sync_notifications
# solved that with a deleted_at column on the row itself, which works there
# because nothing is unique per row.
#
# cultivations and users cannot take the same treatment: cultivations.row_key
# and users.email are UNIQUE, so a tombstoned row would occupy the slot and
# block ever planting row1 again or re-registering an address. The mark lives
# beside the table instead.
#
# The key names the individual record, not the slot it sat in: replanting row1
# or re-registering an address creates a different record, and its own newer
# created_at is what keeps an old tombstone from reaching it.
CULTIVATION_TOMBSTONE = "cultivation"
USER_TOMBSTONE = "user"


def cultivation_sync_key(row_key: object, created_at: object) -> str:
    return f"{str(row_key or '').strip()}|{str(created_at or '').strip()}"


def user_sync_key(email: object, created_at: object) -> str:
    return f"{normalize_email(email)}|{str(created_at or '').strip()}"


def harvest_sync_key(row_key: object, planting_date: object, harvested_at: object) -> str:
    """Names one completed crop, for both transports to agree on.

    A row holds one crop at a time, so (row_key, planting_date) already names a
    planting; harvested_at separates the pathological case of replanting and
    harvesting the same row on the same day. Unlike cultivation_sync_key this
    is not a tombstone key -- harvests are never deleted -- it is the identity
    the sync and the HTTPS relay both use to recognise a record they already
    hold, so replaying either pass inserts nothing.
    """
    return (
        f"{str(row_key or '').strip()}"
        f"|{str(planting_date or '').strip()}"
        f"|{str(harvested_at or '').strip()}"
    )


def record_sync_tombstone(connection: sqlite3.Connection, *, entity: str, natural_key: str) -> None:
    """Mark a record as deliberately deleted, so the sync carries the removal.

    Written in the same transaction as the DELETE it accompanies, so the sync
    can never observe the gap without also observing the reason for it.
    """
    key = str(natural_key or "").strip()
    if not key.strip("|"):
        return
    connection.execute(
        """
        INSERT INTO sync_tombstones (entity, natural_key, deleted_at)
        VALUES (?, ?, ?)
        ON CONFLICT(entity, natural_key) DO UPDATE SET deleted_at = excluded.deleted_at
        """,
        (str(entity), key, utc_now_iso()),
    )


def set_system_state_value(connection: sqlite3.Connection, *, key: str, value: object) -> None:
    connection.execute(
        """
        INSERT INTO system_state (state_key, state_value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(state_key) DO UPDATE SET
            state_value = excluded.state_value,
            updated_at = excluded.updated_at
        """,
        (str(key).strip(), str(value), utc_now_iso()),
    )


def remote_hardware_command_expiry(command_type: str, payload: dict[str, object]) -> datetime:
    """Expire stale ON commands quickly while retaining configuration changes.

    A delayed manual pump/fan ON command must not start hours after the person
    pressed it.  OFF, Automatic, schedule, and sensor-power configuration is
    safe and useful to deliver after a longer internet outage.

    The short window used to be two minutes, which this farm's link cannot
    meet: a TLS handshake from the Pi to the hosted API has been measured
    stalling for 49 seconds, and consecutive polls fail outright during a
    stall. An ON press routinely expired in the queue before the Pi could ever
    collect it, so the button did nothing and there was no error to see. Ten
    minutes clears a stall with room to spare and is still far short of "hours
    later", which is what this limit exists to prevent.
    """
    short_lived = False
    if command_type == "sensorControl":
        short_lived = (
            str(payload.get("controlType") or "").strip() == "actuatorMode"
            and normalize_actuator_mode(
                payload.get("value"), normalize_sensor_key(payload.get("key"))
            )
            == "on"
        )
    elif command_type == "irrigation":
        changes = normalize_manual_line_changes(payload.get("manualLineChanges"))
        short_lived = any(
            is_on for rows in (changes or {}).values() for is_on in rows.values()
        ) or bool(
            normalize_irrigation_line_map(
                payload.get("activeManualLines"), payload.get("activeManualLine")
            )
            or normalize_irrigation_channel_row_map(payload.get("activeManualRows"))
        )
    return utc_now() + timedelta(minutes=10 if short_lived else 24 * 60)


def enqueue_remote_hardware_command(
    connection: sqlite3.Connection,
    *,
    command_type: str,
    payload: dict[str, object],
) -> dict[str, object] | None:
    """Queue an authenticated hosted control for the Raspberry Pi edge.

    The managed host cannot reach the farm's private MQTT broker.  It writes a
    durable command into shared Postgres instead; the Pi consumes it using its
    private device token and records an acknowledgement in the same row.
    """
    if not running_on_managed_host():
        return None
    normalized_type = str(command_type or "").strip()
    if normalized_type not in REMOTE_HARDWARE_COMMAND_TYPES:
        raise ValueError("Unsupported remote hardware command type.")

    request_user = authenticated_request_user() or {}
    command_id = secrets.token_urlsafe(24)
    requested_at = utc_now_iso()
    command = {
        "id": command_id,
        "type": normalized_type,
        "payload": json_safe_copy(payload),
        "status": "pending",
        "requestedAt": requested_at,
        "expiresAt": remote_hardware_command_expiry(normalized_type, payload).isoformat(),
        "requestedByUserId": str(request_user.get("id") or ""),
        "statusUpdatedAt": requested_at,
    }
    set_system_state_value(
        connection,
        key=f"{REMOTE_HARDWARE_COMMAND_PREFIX}{command_id}",
        value=json_dumps_compact(command),
    )
    return {
        "id": command_id,
        "status": "pending",
        "requestedAt": requested_at,
        "expiresAt": command["expiresAt"],
    }


def remote_hardware_command_record(
    connection: sqlite3.Connection, command_id: str
) -> dict[str, object] | None:
    normalized_id = str(command_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", normalized_id):
        return None
    row = connection.execute(
        "SELECT state_value FROM system_state WHERE state_key = ?",
        (f"{REMOTE_HARDWARE_COMMAND_PREFIX}{normalized_id}",),
    ).fetchone()
    if row is None:
        return None
    try:
        command = json.loads(str(row["state_value"]))
    except (TypeError, json.JSONDecodeError):
        return None
    return command if isinstance(command, dict) else None


# Each ESP32 board already connects to the broker with a genuine MQTT Last Will
# -- see esp32_CODE/*/src/main.cpp: mqttClient.connect(clientId, statusTopic, 1,
# true, "offline") -- so the broker itself publishes a retained "offline" for
# icucrops/devices/<nodeId>/status the instant that board's TCP connection
# drops, with no firmware change needed. The bridge (coms_mqtt.py) forwards
# that message here so sensor status can be reported as an actual connection
# state instead of only inferred from how old the last reading is.
# Row 3 has no node of its own any more. ESP32 #3 was removed and its sensors
# were spread over the boards with spare pins: capacitive probe a to #1, b to
# #2, c to #4, and the single RS485 probe to #2 whole (one Modbus slave on one
# pair cannot be split).
#
# This map is what turns a board's MQTT Last Will into "these sensors are
# offline", so row 3 is listed against every board that carries a piece of it.
# The consequence is deliberate and worth knowing: if ESP32 #1 drops, row 3 is
# marked offline even though two of its three probes are still reporting
# through #2 and #4. That is the honest reading -- the row average is then
# built from two probes instead of three -- and it fails closed, which is what
# irrigation needs.
MQTT_NODE_SENSOR_KEYS: dict[str, tuple[str, ...]] = {
    "soil-node-1": ("row1-moisture", "row1-rs485", "row3-moisture"),
    "soil-node-2": (
        "row2-moisture",
        "row2-rs485",
        "row3-moisture",
        "row3-rs485",
    ),
    "soil-node-4": ("row4-moisture", "row4-rs485", "row3-moisture"),
    # soil-node-5 carries both shared greenhouse sensors and nothing else, so
    # it publishes the temperature/humidity and light readings that the fan,
    # lamp and irrigation freshness rules all read.
    #
    # They have moved twice. #4 -> #3 because three relay coils on #4's 5 V
    # rail tripped its brownout detector mid-conversion; #3 -> #5 because #3
    # still runs row 3's RS485 stack, and a Modbus cycle blocks its loop for
    # the better part of a second. #5 drives nothing and polls nothing slow.
    #
    # Moving them again means keeping three things in step: this entry, the
    # DHT22 library in the boards' platformio.ini, and ICUCROPS_HAS_DHT22 in
    # their NodeConfig.h. The library is what makes a board able to publish it.
    "soil-node-5": ("dht22", "light-level"),
}
MQTT_NODE_STATUS_STATE_KEY_PREFIX = "mqtt_node_status:"
# The firmware's status heartbeat republishes every 15s while connected
# (NodeConfig::STATUS_PUBLISH_MS), so a genuinely connected node refreshes this
# well inside 45s. The margin also covers the one case the LWT itself cannot:
# the Pi losing power, which takes the broker down with every board's
# connection at once and leaves no chance for any LWT to fire.
MQTT_NODE_STATUS_MAX_AGE_SECONDS = 45


def record_mqtt_node_status(connection: sqlite3.Connection, node_id: str, state: str) -> None:
    set_system_state_value(
        connection,
        key=f"{MQTT_NODE_STATUS_STATE_KEY_PREFIX}{node_id}",
        value=state,
    )


def mqtt_node_status_map(connection: sqlite3.Connection) -> dict[str, dict[str, str]]:
    keys = [f"{MQTT_NODE_STATUS_STATE_KEY_PREFIX}{node_id}" for node_id in MQTT_NODE_SENSOR_KEYS]
    placeholders = ",".join("?" for _ in keys)
    rows = connection.execute(
        f"SELECT state_key, state_value, updated_at FROM system_state WHERE state_key IN ({placeholders})",  # nosec B608 - only '?' placeholders / module constants interpolated; values are bound parameters
        keys,
    ).fetchall()
    status: dict[str, dict[str, str]] = {}
    for row in rows:
        node_id = str(row["state_key"])[len(MQTT_NODE_STATUS_STATE_KEY_PREFIX):]
        status[node_id] = {"state": str(row["state_value"]), "updatedAt": str(row["updated_at"])}
    return status


def mqtt_node_is_online(status_map: dict[str, dict[str, str]], node_id: str) -> bool | None:
    """True/False when this host can judge the node, None when it cannot.

    The age check only means something where the status is written: the Pi's
    MQTT bridge refreshes these rows as the boards report, so a row that has
    stopped moving there is a board that has stopped talking.

    Off the Pi it measures the wrong thing entirely. `updated_at` arrives
    through the edge sync, which pushes node status only when the *value*
    changes -- deliberately, because rewriting an unchanged "online" every pass
    fires the table's notify trigger and wakes the daemon into a loop. A farm
    that has simply been up all day therefore holds a five-hour-old "online"
    in Supabase, which this read as "offline" and which turned every sensor
    card on the hosted and mobile dashboards grey while the kiosk showed them
    all live.

    So off the Pi a stale heartbeat is no opinion rather than a verdict, and
    sensor_key_connection_state falls through to the reading age. That is the
    better signal there anyway: readings reach Supabase within seconds, and if
    the Pi loses power they simply stop, so the cards go grey on their own
    within SENSOR_READING_STALE_SECONDS. An "offline" still travels promptly,
    because that is a value change and the sync pushes it at once.
    """
    entry = status_map.get(node_id)
    if not entry:
        return False
    try:
        updated_at = parse_iso_datetime(entry.get("updatedAt", ""))
    except (TypeError, ValueError):
        updated_at = None

    # Off the Pi, a stale row is no opinion -- in EITHER direction.
    #
    # This used to return False for a stored "offline" before looking at the
    # age at all, while a stored "online" of the same age was correctly
    # ignored. The asymmetry mattered because node status reaches Supabase only
    # when its value changes: an "offline" written once, when a board was
    # unplugged or restarted, stayed there for as long as nothing else moved,
    # and the hosted dashboard kept reporting it long after the board was back.
    # A stale "online" could never persist that way, so only one half of the
    # rule ever showed the bug.
    #
    # The Pi keeps the old behaviour in both directions: its bridge rewrites
    # these rows as boards report, so a row that has stopped moving there is a
    # board that has stopped talking.
    stale = (
        updated_at is None
        or (utc_now() - updated_at).total_seconds() > MQTT_NODE_STATUS_MAX_AGE_SECONDS
    )
    if stale and not server_is_raspberry_pi():
        return None
    if entry.get("state") != "online":
        return False
    if updated_at is None:
        return False
    return not stale


# A board's heartbeat proves the ESP32 is on the broker. It proves nothing about
# the sensor bolted to that board. The DHT22 went silent for stretches of up to
# 21 hours while soil-node-3 never once dropped its MQTT connection, and because
# the connection state was read from the node alone, the dashboard showed the
# card online the whole time, next to a temperature from the previous evening.
# A sensor is only connected when its own readings are still arriving.
#
# The window has to be tight enough that "connected" means the number on screen
# is the number the probe is measuring now. Three minutes was not: a wedged
# DHT22 kept its card green, next to a temperature from three minutes ago, for
# most of the time it was actually out. Every sensor publishes every 2.5-3 s,
# and the longest silence the firmware will produce on purpose is the 30 s
# RS485 backoff -- so a sensor quiet for 75 s has stopped, not paused.
SENSOR_READING_STALE_SECONDS = 75


def sensor_reading_is_recent(
    reading: sqlite3.Row | dict[str, object] | None,
    max_age_seconds: int = SENSOR_READING_STALE_SECONDS,
) -> bool | None:
    """True/False when the reading's age can be judged, None when it cannot.

    None means there is no usable timestamp to judge -- a sensor that has never
    published, or a row with an unparseable captured_at -- and leaves the
    decision to the caller rather than inventing a verdict.
    """
    if reading is None:
        return None
    captured_at = reading_captured_at(reading)
    if not captured_at:
        return None
    try:
        age = (utc_now() - parse_iso_datetime(captured_at)).total_seconds()
    except (TypeError, ValueError):
        return None
    # A timestamp slightly in the future is a clock that drifted, not a sensor
    # that stopped, so only the upper bound decides.
    return age <= max_age_seconds


def sensor_key_connection_state(
    status_map: dict[str, dict[str, str]],
    sensor_key: str,
    latest_readings: dict[str, object] | None = None,
    pi_alive: bool | None = None,
) -> bool | None:
    """True/False when this sensor's state can be established, None when it
    cannot.

    None asks the caller to fall back to judging the last reading's age: a
    system that predates status tracking has no history yet, and a node can be
    genuinely online for a while before its first heartbeat lands after a
    restart.

    Pass latest_readings to have the sensor's own publishing rate count too,
    which is the only way a dead sensor on a live board reads as disconnected.
    """
    # A sensor key can belong to more than one board. Row 3 has no board of its
    # own since ESP32 #3 was removed: its three capacitive probes were split
    # across #1, #2 and #4, so "row3-moisture" is carried by all three.
    #
    # A split sensor is online while ANY of its boards is, not only while all of
    # them are. The board heartbeat is a coarse signal here -- it says a board
    # is on the broker, not that this row's probe on it is publishing -- and
    # requiring every board made row 3 three times as likely to read Offline as
    # any other row: one board pausing its heartbeat for 45 s greyed out a row
    # that was still reporting real moisture from the other two, and was
    # observed doing exactly that with a probe that answered wet and dry
    # correctly the whole time.
    #
    # What actually decides it is the reading freshness check below. Every probe
    # feeds one aggregate row key, coms_mqtt.py republishes that row whenever at
    # least two components are live, and if the row genuinely stops arriving the
    # reading ages out within SENSOR_READING_STALE_SECONDS and this returns
    # False regardless of what the heartbeats say. That is the honest signal for
    # a split row, and it is the one that fails closed.
    #
    # Any board reporting offline while the row keeps publishing is a degraded
    # row, not a disconnected one: the average is built from two probes instead
    # of three. The row average itself is what irrigation reads, and
    # coms_mqtt.py refuses to emit one below two components, so the degraded
    # case cannot reach a watering decision as a single-probe number.
    # A live Pi heartbeat settles it on its own.
    #
    # The heartbeat is the farm controller saying "I am up" on a timer, which is
    # a stronger statement than anything derived from a sensor: readings only
    # arrive when a board has something to send, and the ESP32 node statuses
    # only travel to Supabase when their value CHANGES. That last one is what
    # produced live temperature and humidity beside a row of Offline badges --
    # an "offline" written once sat in the cloud unchanged while fresh readings
    # kept arriving next to it.
    #
    # So when the Pi is beating, the farm is online and the dashboard says so.
    # The cost of this is deliberate and worth stating plainly: a board that has
    # genuinely stopped publishing still reads as connected for as long as the
    # Pi is up. The reading's own age is what shows that, on the card itself.
    #
    # None means no heartbeat has ever been written here -- a Pi on older code
    # or a fresh database -- and falls through to the checks below rather than
    # declaring anything.
    if pi_alive is True:
        return True

    node_online: bool | None = None
    for node_id, keys in MQTT_NODE_SENSOR_KEYS.items():
        if sensor_key not in keys or node_id not in status_map:
            continue
        this_node = mqtt_node_is_online(status_map, node_id)
        if this_node is True:
            node_online = True
            break
        if this_node is False and node_online is None:
            node_online = False

    if node_online is False:
        return False
    if latest_readings is None:
        return node_online

    reading_recent = sensor_reading_is_recent(latest_readings.get(sensor_key))
    if reading_recent is False:
        # The board is up but this sensor has gone quiet: a wedged DHT22, a
        # silent RS485 bus, or a capacitive probe whose ADC is railed and is
        # therefore no longer published at all.
        return False
    if node_online is None:
        return reading_recent
    return node_online


def upsert_sensor_definition(connection: sqlite3.Connection, payload: dict[str, object]) -> sqlite3.Row:
    definition_key = normalize_sensor_key(payload.get("definitionKey"))
    if not definition_key:
        raise ValueError("Sensor definition key is required.")

    existing = find_sensor_definition_by_key(connection, definition_key)
    existing_metadata = parse_json_object(existing["metadata_json"]) if existing else {}
    incoming_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    existing_metadata.update(incoming_metadata)

    metric_keys = payload.get("metricKeys")
    normalized_metric_keys = (
        [str(item).strip() for item in metric_keys if str(item).strip()]
        if isinstance(metric_keys, list)
        else parse_json_string_list(existing["metric_keys_json"]) if existing else []
    )

    timestamp = utc_now_iso()
    if existing:
        connection.execute(
            """
            UPDATE sensor_definitions
            SET
                display_name = ?,
                category = ?,
                default_device_name = ?,
                default_row_key = ?,
                default_power_state = ?,
                default_actuator_mode = ?,
                metric_keys_json = ?,
                metadata_json = ?,
                updated_at = ?
            WHERE definition_key = ?
            """,
            (
                str(payload.get("displayName") or existing["display_name"]).strip() or str(existing["display_name"]).strip(),
                str(payload.get("category") or existing["category"]).strip() or str(existing["category"]).strip(),
                str(payload.get("defaultDeviceName") or existing["default_device_name"]).strip(),
                str(payload.get("defaultRowKey") or existing["default_row_key"]).strip().lower(),
                normalize_sensor_power_state(payload.get("defaultPowerState") or existing["default_power_state"]),
                normalize_actuator_mode(payload.get("defaultActuatorMode") or existing["default_actuator_mode"])
                if str(payload.get("defaultActuatorMode") or existing["default_actuator_mode"]).strip()
                else "",
                json_dumps_compact(normalized_metric_keys),
                json_dumps_compact(existing_metadata),
                timestamp,
                definition_key,
            ),
        )
    else:
        connection.execute(
            """
            INSERT INTO sensor_definitions (
                definition_key,
                display_name,
                category,
                default_device_name,
                default_row_key,
                default_power_state,
                default_actuator_mode,
                metric_keys_json,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                definition_key,
                str(payload.get("displayName") or definition_key).strip(),
                str(payload.get("category") or "sensor").strip(),
                str(payload.get("defaultDeviceName") or "").strip(),
                str(payload.get("defaultRowKey") or "").strip().lower(),
                normalize_sensor_power_state(payload.get("defaultPowerState") or "on"),
                normalize_actuator_mode(payload.get("defaultActuatorMode"))
                if str(payload.get("defaultActuatorMode") or "").strip()
                else "",
                json_dumps_compact(normalized_metric_keys),
                json_dumps_compact(existing_metadata),
                timestamp,
                timestamp,
            ),
        )

    return find_sensor_definition_by_key(connection, definition_key)


def upsert_sensor_backend(connection: sqlite3.Connection, payload: dict[str, object]) -> sqlite3.Row:
    backend_key = normalize_sensor_key(payload.get("backendKey"))
    if not backend_key:
        raise ValueError("Sensor backend key is required.")

    existing = find_sensor_backend_by_key(connection, backend_key)
    existing_metadata = parse_json_object(existing["metadata_json"]) if existing else {}
    incoming_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    existing_metadata.update(incoming_metadata)

    timestamp = utc_now_iso()
    if existing:
        connection.execute(
            """
            UPDATE sensor_backends
            SET
                display_name = ?,
                ingest_path = ?,
                protocol = ?,
                source_type = ?,
                hardware_identifier_prefix = ?,
                is_active = ?,
                metadata_json = ?,
                updated_at = ?
            WHERE backend_key = ?
            """,
            (
                str(payload.get("displayName") or existing["display_name"]).strip() or str(existing["display_name"]).strip(),
                str(payload.get("ingestPath") or existing["ingest_path"]).strip(),
                str(payload.get("protocol") or existing["protocol"]).strip() or str(existing["protocol"]).strip(),
                str(payload.get("sourceType") or existing["source_type"]).strip() or str(existing["source_type"]).strip(),
                str(payload.get("hardwareIdentifierPrefix") or existing["hardware_identifier_prefix"]).strip(),
                1 if normalize_bool_flag(payload.get("isActive"), default=bool(int(existing["is_active"] or 0))) else 0,
                json_dumps_compact(existing_metadata),
                timestamp,
                backend_key,
            ),
        )
    else:
        connection.execute(
            """
            INSERT INTO sensor_backends (
                backend_key,
                display_name,
                ingest_path,
                protocol,
                source_type,
                hardware_identifier_prefix,
                is_active,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                backend_key,
                str(payload.get("displayName") or backend_key).strip(),
                str(payload.get("ingestPath") or "").strip(),
                str(payload.get("protocol") or "http").strip(),
                str(payload.get("sourceType") or "api").strip(),
                str(payload.get("hardwareIdentifierPrefix") or "").strip(),
                1 if normalize_bool_flag(payload.get("isActive"), default=True) else 0,
                json_dumps_compact(existing_metadata),
                timestamp,
                timestamp,
            ),
        )

    return find_sensor_backend_by_key(connection, backend_key)


# The registry this build ships, keyed for lookup. ensure_sensor_registry_record
# uses it so a row it has to create is a real record rather than a blank one.
DEFAULT_SENSOR_REGISTRY_BY_KEY = {
    str(entry["sensor_key"]): entry for entry in DEFAULT_SENSOR_REGISTRY
}


def sensor_definition_exists(connection: sqlite3.Connection, definition_key: str) -> bool:
    """Whether sensor_definitions actually carries this key.

    sensor_registry.definition_key references it on Supabase, so a key that is
    not there cannot be written. The Pi has no such constraint, which is why an
    unmatched key only ever failed on the hosted site.
    """
    if not definition_key:
        return False
    row = connection.execute(
        "SELECT 1 FROM sensor_definitions WHERE definition_key = ?",
        (definition_key,),
    ).fetchone()
    return row is not None


def placeholder_sensor_display_name(sensor_key: str) -> str:
    cleaned = normalize_sensor_key(sensor_key).replace("-", " ").replace("_", " ")
    return " ".join(part.capitalize() for part in cleaned.split()) or "Sensor"


def ensure_sensor_registry_record(
    connection: sqlite3.Connection,
    *,
    sensor_key: str,
    definition_key: str = "",
    backend_key: str = "",
    display_name: str = "",
    device_name: str = "",
    row_key: str = "",
    category: str = "sensor",
    power_state: str = "on",
    actuator_mode: str = "",
    alert_mode: str = DEFAULT_SENSOR_ALERT_MODE,
    hardware_identifier: str = "",
    metric_keys: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> sqlite3.Row:
    existing = find_sensor_registry_by_key(connection, sensor_key)
    if existing:
        return existing

    # A key this build already knows about is created from its own defaults
    # rather than as a blank. definition_key is a foreign key into
    # sensor_definitions on Supabase, and inserting "" there raises
    # ForeignKeyViolation, which escaped as a 500 and reverted the press: this
    # is what "Could not save the Grow Light Control change" was. SQLite does not
    # enforce the reference, so the same insert passed on the Pi.
    known = DEFAULT_SENSOR_REGISTRY_BY_KEY.get(normalize_sensor_key(sensor_key))
    if known is not None:
        definition_key = definition_key or str(known.get("definition_key") or "")
        backend_key = backend_key or str(known.get("backend_key") or "")
        display_name = display_name or str(known.get("display_name") or "")
        device_name = device_name or str(known.get("device_name") or "")
        row_key = row_key or str(known.get("row_key") or "")
        category = str(known.get("category") or category)
        actuator_mode = actuator_mode or str(known.get("actuator_mode") or "")
        if not metric_keys:
            metric_keys = list(known.get("metric_keys") or [])
        if metadata is None:
            metadata = dict(known.get("metadata") or {})

    # Whatever the caller asked for, the reference has to resolve. An unknown
    # definition is dropped to NULL, which the column allows, instead of the
    # empty string that has no matching row.
    definition_key = normalize_sensor_key(definition_key)
    if definition_key and not sensor_definition_exists(connection, definition_key):
        definition_key = ""

    timestamp = utc_now_iso()
    connection.execute(
        """
        INSERT INTO sensor_registry (
            sensor_key,
            definition_key,
            backend_key,
            display_name,
            device_name,
            row_key,
            category,
            power_state,
            actuator_mode,
            alert_mode,
            hardware_identifier,
            metric_keys_json,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            normalize_sensor_key(sensor_key),
            definition_key or None,  # NULL, never "": the column is a foreign key
            normalize_sensor_key(backend_key),
            str(display_name or placeholder_sensor_display_name(sensor_key)).strip(),
            str(device_name or display_name or placeholder_sensor_display_name(sensor_key)).strip(),
            str(row_key).strip().lower(),
            str(category or "sensor").strip(),
            normalize_sensor_power_state(power_state),
            normalize_actuator_mode(actuator_mode) if actuator_mode else "",
            normalize_sensor_alert_mode(alert_mode, allow_empty=not str(alert_mode or "").strip()),
            str(hardware_identifier).strip(),
            json_dumps_compact(metric_keys or []),
            json_dumps_compact(metadata or {}),
            timestamp,
            timestamp,
        ),
    )
    return find_sensor_registry_by_key(connection, sensor_key)


def update_sensor_registry_record(connection: sqlite3.Connection, payload: dict[str, object]) -> sqlite3.Row:
    sensor_key = normalize_sensor_key(payload.get("sensorKey"))
    if not sensor_key:
        raise ValueError("Sensor key is required.")

    definition_key = normalize_sensor_key(payload.get("definitionKey"))
    backend_key = normalize_sensor_key(payload.get("backendKey"))
    definition = find_sensor_definition_by_key(connection, definition_key) if definition_key else None
    backend = find_sensor_backend_by_key(connection, backend_key) if backend_key else None
    if definition_key and not definition:
        raise ValueError("Unknown sensor definition key.")
    if backend_key and not backend:
        raise ValueError("Unknown sensor backend key.")

    existing = ensure_sensor_registry_record(
        connection,
        sensor_key=sensor_key,
        definition_key=definition_key,
        backend_key=backend_key,
        display_name=str(payload.get("displayName") or (definition["display_name"] if definition else "")).strip(),
        device_name=str(payload.get("deviceName") or (definition["default_device_name"] if definition else "")).strip(),
        row_key=str(payload.get("rowKey") or (definition["default_row_key"] if definition else "")).strip().lower(),
        category=str(payload.get("category") or (definition["category"] if definition else "sensor")).strip(),
        power_state=str(payload.get("powerState") or (definition["default_power_state"] if definition else "on")).strip(),
        actuator_mode=str(payload.get("actuatorMode") or (definition["default_actuator_mode"] if definition else "")).strip(),
        alert_mode=normalize_sensor_alert_mode(payload.get("alertMode")),
        hardware_identifier=str(payload.get("hardwareIdentifier") or "").strip(),
        metric_keys=[
            str(item).strip()
            for item in (payload.get("metricKeys") if isinstance(payload.get("metricKeys"), list) else [])
            if str(item).strip()
        ]
        or (parse_json_string_list(definition["metric_keys_json"]) if definition else []),
        metadata={
            **(parse_json_object(definition["metadata_json"]) if definition else {}),
            **(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}),
        },
    )

    metadata = parse_json_object(existing["metadata_json"])
    incoming_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    metadata.update(incoming_metadata)

    metric_keys = payload.get("metricKeys")
    normalized_metric_keys = (
        [str(item).strip() for item in metric_keys if str(item).strip()]
        if isinstance(metric_keys, list)
        else parse_json_string_list(existing["metric_keys_json"])
        or (parse_json_string_list(definition["metric_keys_json"]) if definition else [])
    )

    updated_values = {
        "definition_key": definition_key or str(existing["definition_key"] or "").strip(),
        "backend_key": backend_key or str(existing["backend_key"] or "").strip(),
        "display_name": str(payload.get("displayName") or existing["display_name"]).strip() or str(existing["display_name"]).strip(),
        "device_name": str(payload.get("deviceName") or existing["device_name"] or (definition["default_device_name"] if definition else "")).strip()
        or str(existing["device_name"]).strip(),
        "row_key": str(payload.get("rowKey") or existing["row_key"] or (definition["default_row_key"] if definition else "")).strip().lower(),
        "category": str(payload.get("category") or existing["category"] or (definition["category"] if definition else "sensor")).strip()
        or str(existing["category"]).strip(),
        "power_state": normalize_sensor_power_state(
            payload.get("powerState") or existing["power_state"] or (definition["default_power_state"] if definition else "on")
        ),
        "actuator_mode": normalize_actuator_mode(
            payload.get("actuatorMode") or existing["actuator_mode"] or (definition["default_actuator_mode"] if definition else ""),
            str(existing["sensor_key"]),
        )
        if str(payload.get("actuatorMode") or existing["actuator_mode"] or (definition["default_actuator_mode"] if definition else "")).strip()
        else "",
        "alert_mode": normalize_sensor_alert_mode(
            payload.get("alertMode") or existing["alert_mode"] or DEFAULT_SENSOR_ALERT_MODE,
            allow_empty=not str(payload.get("alertMode") or existing["alert_mode"] or "").strip(),
        ),
        "hardware_identifier": str(payload.get("hardwareIdentifier") or existing["hardware_identifier"]).strip(),
        "metric_keys_json": json_dumps_compact(normalized_metric_keys),
        "metadata_json": json_dumps_compact(metadata),
        "updated_at": utc_now_iso(),
    }

    connection.execute(
        """
        UPDATE sensor_registry
        SET
            definition_key = ?,
            backend_key = ?,
            display_name = ?,
            device_name = ?,
            row_key = ?,
            category = ?,
            power_state = ?,
            actuator_mode = ?,
            alert_mode = ?,
            hardware_identifier = ?,
            metric_keys_json = ?,
            metadata_json = ?,
            updated_at = ?
        WHERE sensor_key = ?
        """,
        (
            updated_values["definition_key"],
            updated_values["backend_key"],
            updated_values["display_name"],
            updated_values["device_name"],
            updated_values["row_key"],
            updated_values["category"],
            updated_values["power_state"],
            updated_values["actuator_mode"],
            updated_values["alert_mode"],
            updated_values["hardware_identifier"],
            updated_values["metric_keys_json"],
            updated_values["metadata_json"],
            updated_values["updated_at"],
            sensor_key,
        ),
    )

    return find_sensor_registry_by_key(connection, sensor_key)


def normalize_sensor_reading_input(payload: dict[str, object]) -> dict[str, object]:
    if isinstance(payload.get("readings"), dict):
        return parse_sensor_reading_payload(payload["readings"])

    if isinstance(payload.get("readings"), list):
        normalized: dict[str, object] = {}
        for item in payload["readings"]:
            if not isinstance(item, dict):
                continue
            metric_key = str(item.get("metricKey") or item.get("key") or "").strip()
            if not metric_key:
                continue
            numeric = normalize_numeric_value(item.get("value"))
            normalized[metric_key] = numeric if numeric is not None else item.get("value")
        return normalized

    numeric = normalize_numeric_value(payload.get("value"))
    if numeric is not None:
        metric_key = str(payload.get("metricKey") or payload.get("key") or "value").strip() or "value"
        return {metric_key: numeric}

    raise ValueError("At least one reading value is required.")


def drop_pinned_humidity(
    reading_payload: dict[str, object], metadata: dict[str, object] | object
) -> dict[str, object]:
    """Discard a humidity the board has told us is not a measurement.

    A DHT22's polymer saturates and stops coming down. Once it does, the part
    reports its own 100 %RH rail forever, through any real change in the air.
    The firmware detects this and sets `humidityPinned` in the payload's
    metadata -- it still sends the value, because a board should report what it
    read and let the server decide, and because the raw number is what makes
    the fault diagnosable.

    This is where that decision is made. A pinned reading is dropped rather
    than stored, so:

      * the automatic rules see no humidity from this sensor at all, which they
        already handle -- every one of them is written to do nothing when the
        reading is missing. Storing 99.9 instead would hold the exhaust fan
        open forever against a number that cannot come down.
      * the dashboard's freshness check turns the humidity card stale, which is
        what a sensor that is not measuring should look like.

    Only humidity is dropped. The same part's temperature is still accurate --
    the failure is in the humidity polymer alone -- and the fan's heat rule
    depends on it, so taking the whole reading out would disable the one
    actuator that still works.

    Nothing else on the board is affected, and a part that starts tracking
    again clears its own flag, so this reverses itself without a deploy.
    """
    if not isinstance(metadata, dict) or metadata.get("humidityPinned") is not True:
        return reading_payload
    if "humidity" not in reading_payload:
        return reading_payload
    return {key: value for key, value in reading_payload.items() if key != "humidity"}


def record_sensor_reading(connection: sqlite3.Connection, payload: dict[str, object]) -> sqlite3.Row:
    sensor_key = normalize_sensor_key(payload.get("sensorKey"))
    definition_key = normalize_sensor_key(payload.get("definitionKey"))
    backend_key = normalize_sensor_key(payload.get("backendKey"))
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    hardware_identifier = str(payload.get("hardwareIdentifier") or "").strip()
    source_type = str(payload.get("sourceType") or "api").strip().lower() or "api"
    source_identifier = str(payload.get("sourceIdentifier") or hardware_identifier).strip()
    captured_at_raw = str(payload.get("capturedAt") or "").strip()
    captured_at = parse_iso_datetime(captured_at_raw).isoformat() if captured_at_raw else utc_now_iso()
    definition = find_sensor_definition_by_key(connection, definition_key) if definition_key else None
    backend = find_sensor_backend_by_key(connection, backend_key) if backend_key else None
    if definition_key and not definition:
        raise ValueError("Unknown sensor definition key.")
    if backend_key and not backend:
        raise ValueError("Unknown sensor backend key.")

    sensor = find_sensor_registry_by_key(connection, sensor_key) if sensor_key else None
    if not sensor and hardware_identifier:
        sensor = find_sensor_registry_by_hardware_identifier(connection, hardware_identifier)
        if sensor:
            sensor_key = str(sensor["sensor_key"]).strip()

    if not sensor_key:
        raise ValueError("Sensor key or hardware identifier is required.")

    reading_payload = drop_pinned_humidity(normalize_sensor_reading_input(payload), metadata)
    sensor = ensure_sensor_registry_record(
        connection,
        sensor_key=sensor_key,
        definition_key=definition_key,
        backend_key=backend_key,
        display_name=str(payload.get("displayName") or (definition["display_name"] if definition else "")).strip(),
        device_name=str(payload.get("deviceName") or (definition["default_device_name"] if definition else "")).strip(),
        row_key=str(payload.get("rowKey") or (definition["default_row_key"] if definition else "")).strip().lower(),
        category=str(payload.get("category") or (definition["category"] if definition else "sensor")).strip(),
        hardware_identifier=hardware_identifier,
        metric_keys=[
            key for key in reading_payload
            if key not in GREENHOUSE_CARD_FIELDS and key not in SOIL_DOSE_FIELDS
        ],
        power_state=str(payload.get("powerState") or (definition["default_power_state"] if definition else "on")).strip(),
        actuator_mode=str(payload.get("actuatorMode") or (definition["default_actuator_mode"] if definition else "")).strip(),
        metadata={
            **(parse_json_object(definition["metadata_json"]) if definition else {}),
            "identifiedLater": not bool(hardware_identifier),
        },
    )

    if (
        hardware_identifier
        and str(sensor["hardware_identifier"]).strip() != hardware_identifier
        or backend_key
        and str(sensor["backend_key"] or "").strip() != backend_key
        or definition_key
        and str(sensor["definition_key"] or "").strip() != definition_key
    ):
        connection.execute(
            """
            UPDATE sensor_registry
            SET
                hardware_identifier = ?,
                definition_key = CASE
                    WHEN ? <> '' THEN ?
                    ELSE definition_key
                END,
                backend_key = CASE
                    WHEN ? <> '' THEN ?
                    ELSE backend_key
                END,
                updated_at = ?
            WHERE sensor_key = ?
            """,
            (
                hardware_identifier or str(sensor["hardware_identifier"]).strip(),
                definition_key,
                definition_key,
                backend_key,
                backend_key,
                utc_now_iso(),
                sensor_key,
            ),
        )

    cursor = connection.execute(
        """
        INSERT INTO sensor_readings (
            sensor_key,
            reading_payload_json,
            source_type,
            source_identifier,
            captured_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            sensor_key,
            # The DHT22 row also carries the card effect the Pi applied to it
            # (GREENHOUSE_CARD_EFFECT_KEYS); every other row, the soil probes
            # included, is stored as sent.
            json_dumps_compact(with_greenhouse_card_effect(sensor_key, reading_payload)),
            source_type,
            source_identifier,
            captured_at,
        ),
    )

    # Read the row back by the id the insert just handed out rather than
    # calling last_insert_rowid(), which only exists in SQLite. Both drivers
    # populate cursor.lastrowid, so this works on either backend.
    return connection.execute(
        """
        SELECT
            id,
            sensor_key,
            reading_payload_json,
            source_type,
            source_identifier,
            captured_at
        FROM sensor_readings
        WHERE id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()


def misting_on_without_duration(payload: dict[str, object]) -> bool:
    """True for a misting On that carries no usable duration.

    Refused everywhere: the API answers 400 before the relay cache is touched,
    the relay cache ignores it, and update_sensor_control raises. Without a
    duration the line would stay on until someone came back to press Off.
    """
    return (
        str(payload.get("controlType") or "").strip() == "actuatorMode"
        and normalize_sensor_key(payload.get("key")) == "misting"
        and normalize_actuator_mode(payload.get("value"), "misting") == "on"
        and not normalize_misting_duration(payload.get("durationSeconds"))
    )


MISTING_DURATION_REQUIRED_MESSAGE = (
    f"Enter a misting run duration of {MISTING_MIN_DURATION_SECONDS}-"
    f"{MISTING_MAX_DURATION_SECONDS} seconds before turning it on."
)


def normalize_misting_duration(value: object) -> int:
    """Seconds for a timed misting run, or 0 for "on until told otherwise".

    A missing or unreadable value is 0 rather than the default duration: a
    caller that sent no duration is asking for the old behaviour, and turning
    that into a timed run would switch the line off under them.
    """
    text = str(value if value is not None else "").strip()
    if not text:
        return 0
    try:
        seconds = int(float(text))
    except (TypeError, ValueError):
        return 0
    if seconds <= 0:
        return 0
    return max(
        MISTING_MIN_DURATION_SECONDS, min(MISTING_MAX_DURATION_SECONDS, seconds)
    )


def actuator_deadlines_ms(connection: sqlite3.Connection) -> dict[str, int]:
    """Milliseconds left on each timed actuator run, keyed by actuator.

    Misting is the only actuator that can be timed. The relay command built
    from this carries the remaining time, so the board closes the line on its
    own clock instead of waiting for expire_due_misting_run to notice and for
    that decision to cross the environment worker, SQLite, the MQTT bridge and
    the network -- the same path that made a two second irrigation run water
    for almost seven.

    An actuator with no deadline is absent from this map and gets a bare ON,
    which keeps meaning "on until a person or a rule says otherwise".
    """
    remaining = seconds_until_misting_deadline(connection)
    if remaining is None or remaining <= 0:
        return {}
    return {"misting": int(remaining * 1000)}


def actuator_deadlines_at_ms(connection: sqlite3.Connection) -> dict[str, int]:
    """The misting deadline as epoch milliseconds, for the same reason as
    irrigation_run_deadlines_at_ms: a remaining time goes stale in the cache."""
    state_values = system_state_map(connection)
    raw_deadline = str(state_values.get(MISTING_DEADLINE_STATE_KEY) or "").strip()
    if not raw_deadline:
        return {}
    try:
        ends_at = parse_iso_datetime(raw_deadline)
    except (TypeError, ValueError):
        return {}
    if ends_at <= utc_now():
        return {}
    return {"misting": epoch_ms(ends_at)}


def seconds_until_misting_deadline(connection: sqlite3.Connection) -> float | None:
    """Seconds until the misting line is due to close, or None if it is not.

    The environment worker otherwise only looks every
    ENVIRONMENT_CONTROL_INTERVAL_SECONDS, so a run shorter than that interval
    holds the line open until the next sweep happens to notice.
    """
    state_values = system_state_map(connection)
    raw_deadline = str(state_values.get(MISTING_DEADLINE_STATE_KEY) or "").strip()
    if not raw_deadline:
        return None
    try:
        ends_at = parse_iso_datetime(raw_deadline)
    except (TypeError, ValueError):
        return None
    return max(0.0, (ends_at - utc_now()).total_seconds())


def expire_due_misting_run(connection: sqlite3.Connection) -> bool:
    """Switch the misting line off once its timed run is up. True if it did.

    Runs from the environment control cycle, which is also what publishes the
    relay state, so the close reaches the hardware on the same pass that
    notices it. A deadline with the line already off -- somebody pressed Off
    early -- is cleared without a write to the registry.
    """
    state_values = system_state_map(connection)
    raw_deadline = str(state_values.get(MISTING_DEADLINE_STATE_KEY) or "").strip()
    if not raw_deadline:
        return False
    try:
        ends_at = parse_iso_datetime(raw_deadline)
    except (TypeError, ValueError):
        # Unreadable: clear it rather than leaving the line armed against a
        # deadline nothing can evaluate.
        set_system_state_value(connection, key=MISTING_DEADLINE_STATE_KEY, value="")
        return False
    if ends_at > utc_now():
        return False

    set_system_state_value(connection, key=MISTING_DEADLINE_STATE_KEY, value="")
    registry = {
        str(row["sensor_key"]).strip(): row for row in list_sensor_registry(connection)
    }
    if actuator_control_state(registry, "misting") != "on":
        return False

    connection.execute(
        """
        UPDATE sensor_registry
        SET actuator_mode = ?, updated_at = ?
        WHERE sensor_key = ?
        """,
        ("off", utc_now_iso(), "misting"),
    )
    create_notification_record(
        connection,
        scope="all",
        type="success",
        message="Misting line finished its timed run and switched off.",
        source_type="actuator",
        source_id="misting",
    )
    return True


def update_sensor_control(
    connection: sqlite3.Connection,
    payload: dict[str, object],
    *,
    pressed_at: datetime | None = None,
) -> None:
    control_type = str(payload.get("controlType") or "").strip()
    control_key = normalize_sensor_key(payload.get("key"))
    value = payload.get("value")
    duration_seconds = normalize_misting_duration(payload.get("durationSeconds"))

    if not control_type:
        raise ValueError("Control type is required.")
    if not control_key:
        raise ValueError("Control key is required.")
    if misting_on_without_duration(payload):
        raise ValueError(MISTING_DURATION_REQUIRED_MESSAGE)

    existing = ensure_sensor_registry_record(connection, sensor_key=control_key)
    timestamp = utc_now_iso()

    if control_type in {"sensorPower", "rowSensorPower"}:
        normalized_value = normalize_sensor_power_state(value)
        connection.execute(
            """
            UPDATE sensor_registry
            SET power_state = ?, updated_at = ?
            WHERE sensor_key = ?
            """,
            (normalized_value, timestamp, control_key),
        )
        return

    if control_type == "actuatorMode":
        normalized_mode = normalize_actuator_mode(value, control_key)
        connection.execute(
            """
            UPDATE sensor_registry
            SET actuator_mode = ?, updated_at = ?
            WHERE sensor_key = ?
            """,
            (normalized_mode, timestamp, control_key),
        )
        if control_key == "misting":
            # On with a duration arms the deadline; anything else clears it.
            # Off obviously, and Automatic too: there the mist takes the water
            # run's deadline, and a leftover one from a previous timed run
            # must not be read as its own.
            if normalized_mode == "on" and duration_seconds:
                # From pressed_at when there is one: the same instant the
                # relay snapshot was already given, so the two agree exactly.
                ends_at = (pressed_at or utc_now()) + timedelta(seconds=int(duration_seconds))
                set_system_state_value(
                    connection,
                    key=MISTING_DEADLINE_STATE_KEY,
                    value=ends_at.isoformat(),
                )
            else:
                set_system_state_value(
                    connection, key=MISTING_DEADLINE_STATE_KEY, value=""
                )
        return

    raise ValueError(f"Unsupported control type: {control_type}")


def close_active_irrigation_run(
    connection: sqlite3.Connection,
    channel_key: str,
    *,
    mode: str = "",
    status: str,
    notes: str = "",
    row_key: str = "",
) -> None:
    normalized_row = str(row_key or "").strip().lower()
    query = """
        SELECT irrigation_runs.id
        FROM irrigation_runs
    """
    if normalized_row:
        query += """
        INNER JOIN irrigation_run_rows
            ON irrigation_run_rows.irrigation_run_id = irrigation_runs.id
        """
    query += """
        WHERE irrigation_runs.channel_key = ?
          AND irrigation_runs.status = 'active'
    """
    params: list[object] = [channel_key]
    if mode:
        query += " AND irrigation_runs.mode = ?"
        params.append(normalize_irrigation_mode(mode))
    if normalized_row:
        query += " AND irrigation_run_rows.row_key = ? AND irrigation_run_rows.status = 'active'"
        params.append(normalized_row)
    query += """
        ORDER BY irrigation_runs.started_at DESC, irrigation_runs.id DESC
        LIMIT 1
    """
    active_run = connection.execute(query, params).fetchone()
    if not active_run:
        return

    timestamp = utc_now_iso()
    if normalized_row:
        connection.execute(
            """
            UPDATE irrigation_run_rows
            SET status = ?, ended_at = ?
            WHERE irrigation_run_id = ?
              AND row_key = ?
              AND status = 'active'
            """,
            (status, timestamp, int(active_run["id"]), normalized_row),
        )
        remaining = connection.execute(
            """
            SELECT COUNT(*)
            FROM irrigation_run_rows
            WHERE irrigation_run_id = ? AND status = 'active'
            """,
            (int(active_run["id"]),),
        ).fetchone()[0]
        if int(remaining) > 0:
            return
    else:
        connection.execute(
            """
            UPDATE irrigation_run_rows
            SET status = ?, ended_at = ?
            WHERE irrigation_run_id = ?
              AND status = 'active'
            """,
            (status, timestamp, int(active_run["id"])),
        )
    connection.execute(
        """
        UPDATE irrigation_runs
        SET status = ?, ended_at = ?, notes = ?
        WHERE id = ?
        """,
        (status, timestamp, notes, int(active_run["id"])),
    )


def open_irrigation_run(
    connection: sqlite3.Connection,
    *,
    channel_key: str,
    mode: str = "manual",
    duration_seconds: int,
    requested_by_user_id: int | None = None,
    notes: str = "",
    target_rows: object = None,
    started_at: datetime | None = None,
) -> None:
    cursor = connection.execute(
        """
        INSERT INTO irrigation_runs (
            channel_key,
            mode,
            status,
            duration_seconds,
            started_at,
            requested_by_user_id,
            notes
        )
        VALUES (?, ?, 'active', ?, ?, ?, ?)
        """,
        (
            channel_key,
            normalize_irrigation_mode(mode),
            max(0, int(duration_seconds)),
            started_at.isoformat() if started_at is not None else utc_now_iso(),
            requested_by_user_id,
            notes,
        ),
    )
    run_id = int(cursor.lastrowid)
    cultivation_by_row = active_cultivation_row_map(list_cultivations(connection))
    timestamp = utc_now_iso()
    for row_key in filter_active_irrigation_rows(target_rows, list(cultivation_by_row.values())):
        cultivation = cultivation_by_row[row_key]
        connection.execute(
            """
            INSERT INTO irrigation_run_rows (
                irrigation_run_id,
                cultivation_id,
                row_key,
                status,
                started_at
            )
            VALUES (?, ?, ?, 'active', ?)
            """,
            (run_id, int(cultivation["id"]), row_key, timestamp),
        )


def active_irrigation_run_keys(connection: sqlite3.Connection) -> set[tuple[str, str, str]]:
    """(mode, channel, row) for every line that has an active run behind it."""
    return {
        (
            normalize_irrigation_mode(row["mode"]),
            str(row["channel_key"]).strip(),
            str(row["row_key"]).strip().lower(),
        )
        for row in connection.execute(
            """
            SELECT irrigation_runs.mode AS mode,
                   irrigation_runs.channel_key AS channel_key,
                   irrigation_run_rows.row_key AS row_key
            FROM irrigation_runs
            INNER JOIN irrigation_run_rows
                ON irrigation_run_rows.irrigation_run_id = irrigation_runs.id
            WHERE irrigation_runs.status = 'active'
              AND irrigation_run_rows.status = 'active'
            """
        ).fetchall()
    }


def timed_lines_without_a_run(
    connection: sqlite3.Connection,
    manual_rows: dict[str, dict[str, bool]],
    schedule_rows: dict[str, dict[str, bool]],
) -> dict[str, dict[str, set[str]]]:
    """Manual and schedule lines that are on but have no run to time them.

    A run is opened when a line turns on here. A line can also arrive already
    on -- the irrigation.* state is synced both ways, so a Start pressed on the
    hosted dashboard can reach the Pi as stored state before, or instead of,
    its command -- and then it never "turned on" on this side and got no run.
    With no run there is no deadline to send the board and nothing to expire,
    so the line watered until the hosted side happened to clear it.

    Only the controller that drives the relays answers for this; the hosted
    copy keeps its own runs as it always has.
    """
    if running_on_managed_host():
        return {}
    if not any(manual_rows.values()) and not any(schedule_rows.values()):
        return {}
    active_keys = active_irrigation_run_keys(connection)
    missing: dict[str, dict[str, set[str]]] = {}
    for run_mode, channel_rows in (("manual", manual_rows), ("schedule", schedule_rows)):
        for channel_key, rows in channel_rows.items():
            for row_key in rows:
                if (run_mode, channel_key, row_key) not in active_keys:
                    missing.setdefault(run_mode, {}).setdefault(channel_key, set()).add(row_key)
    return missing


IRRIGATION_SETTING_COLUMNS = (
    "automatic_enabled, automatic_duration_seconds, manual_duration_seconds,"
    " schedule_enabled, schedule_start_time, schedule_duration_seconds, schedule_frequency"
)


def irrigation_setting_differs(stored: object, values: tuple[object, ...]) -> bool:
    """Whether a settings row would change, compared as values, not as types.

    SQLite hands back 1 where Supabase hands back True, so the booleans (the
    first and fourth columns) are compared by truth and the rest as text.
    """
    if stored is None:
        return True
    for index, value in enumerate(values):
        if index in (0, 3):
            if bool(stored[index]) != bool(value):
                return True
        elif str(stored[index] if stored[index] is not None else "") != str(value):
            return True
    return False


def merge_scoped_channel_rows(
    current: dict[str, dict[str, bool]],
    incoming: dict[str, dict[str, bool]],
    scope_rows: set[str],
) -> dict[str, dict[str, bool]]:
    """Current runs for rows outside the scope, the request's for rows inside it."""
    merged: dict[str, dict[str, bool]] = {}
    for channel_key in set(current) | set(incoming):
        rows = {
            row_key: True
            for row_key in current.get(channel_key, {})
            if row_key not in scope_rows
        }
        rows.update(
            {row_key: True for row_key in incoming.get(channel_key, {}) if row_key in scope_rows}
        )
        if rows:
            merged[channel_key] = rows
    return merged


def normalize_manual_line_changes(value: object) -> dict[str, dict[str, bool]] | None:
    """The Start and Stop presses a request carries, channel -> row -> on/off.

    None when the request does not carry any (an older page), so the caller can
    fall back to reading its whole activeManualRows map.
    """
    if not isinstance(value, dict):
        return None
    valid_channels = {str(channel["channel_key"]).strip() for channel in DEFAULT_IRRIGATION_CHANNELS}
    changes: dict[str, dict[str, bool]] = {}
    for channel_key, rows in value.items():
        channel = str(channel_key).strip()
        if channel not in valid_channels or not isinstance(rows, dict):
            continue
        for row_key, is_on in rows.items():
            row = str(row_key).strip().lower()
            if row in VALID_CULTIVATION_ROWS:
                changes.setdefault(channel, {})[row] = normalize_bool_flag(is_on)
    return changes


def apply_manual_line_changes(
    current: dict[str, dict[str, bool]],
    changes: dict[str, dict[str, bool]],
) -> dict[str, dict[str, bool]]:
    """What is running now, with only the pressed lines switched.

    A page's own copy of the running lines is always a little behind: a 2
    second run has usually ended on the Pi before the page hears of it. Taking
    that copy as the new state meant any save from the row -- Start on another
    line, a duration edit, a tank confirmation -- carried the finished line
    back as "on", and the Pi opened it again for its whole duration. Starting
    from what this backend holds, and applying only what was pressed, a line
    that was not pressed cannot change: Start on a running line and Stop on a
    finished one are both no-ops.
    """
    result = {channel_key: dict(rows) for channel_key, rows in current.items()}
    for channel_key, rows in changes.items():
        for row_key, is_on in rows.items():
            if is_on:
                result.setdefault(channel_key, {})[row_key] = True
            else:
                result.get(channel_key, {}).pop(row_key, None)
    return {channel_key: rows for channel_key, rows in result.items() if rows}


def finished_schedule_windows(
    connection: sqlite3.Connection,
    windows: dict[str, dict[str, tuple[datetime, datetime]]],
) -> dict[str, set[str]]:
    """Schedule lines whose run for today's window has already ended.

    A scheduled run is stamped with its window's start. Once that run is over
    -- cut because the row reached its crop parameter, or stopped -- the window
    is spent: the reading drifting back under the minimum a minute later, still
    inside the window, used to open a second run, so the line switched on
    twice from one schedule.

    Only a stopped run spends the window. A completed one ran to the window's
    end, so its window is already closed -- and if the duration has since been
    lengthened, the longer window is what was asked for.
    """
    # The same clock scheduled_irrigation_row_map opens windows by. Only windows
    # open right now can be asked to run, so only they need the lookup; outside
    # a window this costs no query at all.
    now = irrigation_local_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=IRRIGATION_LOCAL_TIMEZONE)
    starts = {
        (channel_key, row_key): window[0].astimezone(timezone.utc)
        for channel_key, rows in windows.items()
        for row_key, window in rows.items()
        if window[0] <= now < window[1]
    }
    if not starts:
        return {}
    finished: dict[str, set[str]] = {}
    for run in connection.execute(
        """
        SELECT irrigation_runs.channel_key AS channel_key,
               irrigation_run_rows.row_key AS row_key,
               irrigation_runs.started_at AS started_at
        FROM irrigation_runs
        INNER JOIN irrigation_run_rows
            ON irrigation_run_rows.irrigation_run_id = irrigation_runs.id
        WHERE irrigation_runs.mode = 'schedule'
          AND irrigation_run_rows.status = 'stopped'
        ORDER BY irrigation_runs.id DESC
        LIMIT 200
        """
    ).fetchall():
        key = (str(run["channel_key"]).strip(), str(run["row_key"]).strip().lower())
        window_start = starts.get(key)
        if window_start is None:
            continue
        try:
            started_at = parse_iso_datetime(str(run["started_at"]))
        except (TypeError, ValueError):
            continue
        if abs((started_at - window_start).total_seconds()) < 1:
            finished.setdefault(key[0], set()).add(key[1])
    return finished


def drop_finished_schedule_windows(
    schedule_rows: dict[str, dict[str, bool]],
    finished: dict[str, set[str]],
) -> dict[str, dict[str, bool]]:
    kept: dict[str, dict[str, bool]] = {}
    for channel_key, rows in schedule_rows.items():
        remaining = {
            row_key: True
            for row_key in rows
            if row_key not in finished.get(channel_key, set())
        }
        if remaining:
            kept[channel_key] = remaining
    return kept


def lime_tank_ask_is_due(row: dict[str, object], automatic_rows: object = None) -> bool:
    """Whether this row's tank card should be raised now.

    Manual and schedule rows ask as soon as the pH is outside the crop range
    (warning), because that is when they may run. Automatic only acts at
    critical, so it asks only then -- or while it is already correcting, when
    the answer is still needed. Asking at warning told the farm to change the
    tank for a correction Automatic was not going to make.
    """
    if normalize_irrigation_mode(row.get("mode")) != "automatic":
        return True
    if bool((row.get("criticalNeeds") or {}).get("limeSolution")):
        return True
    running = normalize_irrigation_channel_row_map(automatic_rows)
    return bool(running.get("limeSolution", {}).get(str(row.get("key") or "")))


def update_irrigation_state(
    connection: sqlite3.Connection,
    payload: dict[str, object],
    *,
    pressed_at: datetime | None = None,
) -> dict[str, object]:
    """Store an irrigation request and open or close the runs it implies.

    pressed_at is when the request's relay snapshot was already published
    (cache_relay_irrigation_request). A manual run this request starts is
    stamped with it rather than with the time this write gets round to it, so
    the stored run ends at the same instant as the deadline the board was sent.
    """
    expire_due_irrigation_runs(connection)
    stored_state_values = system_state_map(connection)
    current = build_irrigation_payload(connection)
    cultivations = list_cultivations(connection)
    active_cultivations = active_cultivation_row_map(cultivations)
    current_row_modes = normalize_irrigation_row_mode_map(current.get("rowModes"))
    incoming_row_modes = normalize_irrigation_row_mode_map(payload.get("rowModes"))
    # The rows this request is about, when the page says so. A press on one row
    # used to carry the sender's whole snapshot -- every row's mode and every
    # running manual line -- and a phone whose copy was a few seconds behind the
    # Pi put the other rows back to what it last saw. Row 1's Manual press
    # turned row 2 back to Automatic, which then started watering on its own.
    # Scoped, only the named rows are taken from the request; every other row
    # keeps what this backend already holds.
    scope_rows: set[str] | None = None
    if isinstance(payload.get("scopeRows"), list):
        scope_rows = {
            str(row_key).strip() for row_key in payload["scopeRows"] if str(row_key).strip()
        }
        incoming_row_modes = {
            row_key: row_mode
            for row_key, row_mode in incoming_row_modes.items()
            if row_key in scope_rows
        }
    row_modes = {
        row_key: incoming_row_modes.get(row_key, current_row_modes.get(row_key, "automatic"))
        for row_key in active_cultivations
    }
    mode = normalize_irrigation_mode(payload.get("mode") if "mode" in payload else current["mode"])
    auto_enabled = normalize_bool_flag(
        payload.get("autoEnabled") if "autoEnabled" in payload else current["autoEnabled"],
        default=bool(current["autoEnabled"]),
    )
    requested_manual_lines = normalize_irrigation_line_map(
        payload.get("activeManualLines") if "activeManualLines" in payload else current.get("activeManualLines"),
        payload.get("activeManualLine") if "activeManualLine" in payload else current.get("activeManualLine", ""),
    )
    target_rows = filter_active_irrigation_rows(
        payload.get("targetRows") if "targetRows" in payload else current.get("targetRows"),
        cultivations,
    )
    active_manual_rows = filter_active_irrigation_channel_rows(
        payload.get("activeManualRows") if "activeManualRows" in payload else current.get("activeManualRows"),
        cultivations,
    )
    schedule_armed_rows = filter_active_irrigation_rows(
        payload.get("scheduleArmedRows") if "scheduleArmedRows" in payload else current.get("scheduleArmedRows"),
        cultivations,
    )
    for channel_key in requested_manual_lines:
        if channel_key not in active_manual_rows and target_rows:
            active_manual_rows[channel_key] = dict(target_rows)
    active_manual_rows = {
        channel_key: rows
        for channel_key, rows in active_manual_rows.items()
        if channel_key in requested_manual_lines
    }
    manual_line_changes = normalize_manual_line_changes(payload.get("manualLineChanges"))
    if manual_line_changes is not None:
        # The page says exactly which lines were pressed. Everything else
        # stays as this backend holds it -- see apply_manual_line_changes. A
        # row without a planting is dropped by the row-mode filter below.
        active_manual_rows = apply_manual_line_changes(
            filter_active_irrigation_channel_rows(current.get("activeManualRows"), cultivations),
            manual_line_changes,
        )
    elif scope_rows is not None:
        active_manual_rows = merge_scoped_channel_rows(
            filter_active_irrigation_channel_rows(current.get("activeManualRows"), cultivations),
            active_manual_rows,
            scope_rows,
        )
    if scope_rows is not None:
        current_armed_rows = filter_active_irrigation_rows(
            current.get("scheduleArmedRows"), cultivations
        )
        schedule_armed_rows = {
            **{row_key: True for row_key in current_armed_rows if row_key not in scope_rows},
            **{row_key: True for row_key in schedule_armed_rows if row_key in scope_rows},
        }
    active_manual_rows = {
        channel_key: {
            row_key: True
            for row_key in rows
            if row_modes.get(row_key) == "manual"
        }
        for channel_key, rows in active_manual_rows.items()
    }
    active_manual_rows = {key: rows for key, rows in active_manual_rows.items() if rows}
    schedule_armed_rows = {
        row_key: True
        for row_key in schedule_armed_rows
        if row_modes.get(row_key) == "schedule"
    }

    def write_state(*, key: str, value: object) -> None:
        # A request writes what it says, even an unchanged value: it is a
        # person's instruction and has to be the newest thing the sync sees.
        # The reconcile pass sends no request at all, and only an actual change
        # may come out of it -- re-stamping an unchanged value made the Pi's
        # stale copy outrank a phone's newer press in the sync, which then
        # carried the old state back up over it.
        if payload or stored_state_values.get(key) != str(value):
            set_system_state_value(connection, key=key, value=value)

    requested_by_user_id_raw = str(payload.get("requestedByUserId") or "").strip()
    requested_by_user_id = None
    if requested_by_user_id_raw.isdigit():
        candidate_user_id = int(requested_by_user_id_raw)
        if find_user_by_id(connection, candidate_user_id):
            requested_by_user_id = candidate_user_id

    channels_payload = payload.get("channels") if isinstance(payload.get("channels"), dict) else {}
    current_channels = current["channels"] if isinstance(current.get("channels"), dict) else {}
    timestamp = utc_now_iso()

    for channel in DEFAULT_IRRIGATION_CHANNELS:
        channel_key = str(channel["channel_key"]).strip()
        incoming = channels_payload.get(channel_key) if isinstance(channels_payload.get(channel_key), dict) else {}
        existing = current_channels.get(channel_key, {})
        automatic_enabled = normalize_bool_flag(
            incoming.get("automaticEnabled") if "automaticEnabled" in incoming else existing.get("automaticEnabled"),
            default=True,
        )
        automatic_duration_seconds = normalize_irrigation_duration(
            incoming.get("automaticDuration"), existing.get("automaticDuration"), channel["automatic_duration_seconds"]
        )
        manual_duration_seconds = normalize_irrigation_duration(
            incoming.get("manualDuration"), existing.get("manualDuration"), channel["manual_duration_seconds"]
        )
        schedule_enabled = normalize_bool_flag(
            incoming.get("scheduleEnabled") if "scheduleEnabled" in incoming else existing.get("scheduleEnabled"),
            default=True,
        )
        schedule_start_time = str(incoming.get("scheduleStartTime") or existing.get("scheduleStartTime") or channel["schedule_start_time"]).strip()
        schedule_duration_seconds = normalize_irrigation_duration(
            incoming.get("scheduleDuration"), existing.get("scheduleDuration"), channel["schedule_duration_seconds"]
        )
        schedule_frequency = normalize_irrigation_frequency(
            incoming.get("scheduleFrequency") or existing.get("scheduleFrequency") or channel["schedule_frequency"]
        )

        stored_channel = connection.execute(
            f"SELECT {IRRIGATION_SETTING_COLUMNS} FROM irrigation_settings WHERE channel_key = ?",
            (channel_key,),
        ).fetchone()
        if not irrigation_setting_differs(
            stored_channel,
            (
                automatic_enabled,
                automatic_duration_seconds,
                manual_duration_seconds,
                schedule_enabled,
                schedule_start_time or "06:00",
                schedule_duration_seconds,
                schedule_frequency,
            ),
        ):
            continue
        connection.execute(
            """
            UPDATE irrigation_settings
            SET
                automatic_enabled = ?,
                automatic_duration_seconds = ?,
                manual_duration_seconds = ?,
                schedule_enabled = ?,
                schedule_start_time = ?,
                schedule_duration_seconds = ?,
                schedule_frequency = ?,
                updated_at = ?
            WHERE channel_key = ?
            """,
            (
                1 if automatic_enabled else 0,
                automatic_duration_seconds,
                manual_duration_seconds,
                1 if schedule_enabled else 0,
                schedule_start_time or "06:00",
                schedule_duration_seconds,
                schedule_frequency,
                timestamp,
                channel_key,
            ),
        )
    current_rows = {
        str(row["key"]): row
        for row in list(current.get("rows") or [])
        if isinstance(row, dict)
    }
    row_channels_payload = payload.get("rowChannels") if isinstance(payload.get("rowChannels"), dict) else {}
    for row_key, cultivation in active_cultivations.items():
        # Written only when it changes. The reconcile pass calls this with an
        # empty request every few seconds, and an unconditional write stamped
        # every row's mode with "now" each time -- so the Pi's copy, even when
        # it had not yet heard of a phone's newer choice, always looked like
        # the latest edit to the sync, and sent the old mode back up over it.
        stored_control = connection.execute(
            "SELECT mode, is_enabled FROM irrigation_row_controls WHERE cultivation_id = ?",
            (int(cultivation["id"]),),
        ).fetchone()
        if (
            stored_control is None
            or str(stored_control["mode"] or "") != row_modes[row_key]
            or not stored_control["is_enabled"]
        ):
            connection.execute(
                """
                UPDATE irrigation_row_controls
                SET mode = ?, is_enabled = TRUE, updated_at = ?
                WHERE cultivation_id = ?
                """,
                (row_modes[row_key], timestamp, int(cultivation["id"])),
            )
        incoming_row_channels = (
            row_channels_payload.get(row_key)
            if isinstance(row_channels_payload.get(row_key), dict)
            else {}
        )
        existing_row_channels = (
            current_rows.get(row_key, {}).get("channels")
            if isinstance(current_rows.get(row_key, {}).get("channels"), dict)
            else {}
        )
        for channel in DEFAULT_IRRIGATION_CHANNELS:
            channel_key = str(channel["channel_key"]).strip()
            incoming = (
                incoming_row_channels.get(channel_key)
                if isinstance(incoming_row_channels.get(channel_key), dict)
                else {}
            )
            existing = (
                existing_row_channels.get(channel_key)
                if isinstance(existing_row_channels.get(channel_key), dict)
                else {}
            )
            row_values = (
                    1 if normalize_bool_flag(
                        incoming.get("automaticEnabled")
                        if "automaticEnabled" in incoming
                        else existing.get("automaticEnabled"),
                        default=True,
                    ) else 0,
                    normalize_irrigation_duration(
                        incoming.get("automaticDuration"), existing.get("automaticDuration"), channel["automatic_duration_seconds"]
                    ),
                    normalize_irrigation_duration(
                        incoming.get("manualDuration"), existing.get("manualDuration"), channel["manual_duration_seconds"]
                    ),
                    1 if normalize_bool_flag(
                        incoming.get("scheduleEnabled")
                        if "scheduleEnabled" in incoming
                        else existing.get("scheduleEnabled"),
                        default=True,
                    ) else 0,
                    str(incoming.get("scheduleStartTime") or existing.get("scheduleStartTime") or channel["schedule_start_time"]).strip() or "06:00",
                    normalize_irrigation_duration(
                        incoming.get("scheduleDuration"), existing.get("scheduleDuration"), channel["schedule_duration_seconds"]
                    ),
                    normalize_irrigation_frequency(
                        incoming.get("scheduleFrequency")
                        or existing.get("scheduleFrequency")
                        or channel["schedule_frequency"]
                    ),
            )
            stored_row_setting = connection.execute(
                f"SELECT {IRRIGATION_SETTING_COLUMNS} FROM irrigation_row_settings"
                " WHERE cultivation_id = ? AND channel_key = ?",
                (int(cultivation["id"]), channel_key),
            ).fetchone()
            if not irrigation_setting_differs(stored_row_setting, row_values):
                continue
            connection.execute(
                """
                UPDATE irrigation_row_settings
                SET
                    automatic_enabled = ?,
                    automatic_duration_seconds = ?,
                    manual_duration_seconds = ?,
                    schedule_enabled = ?,
                    schedule_start_time = ?,
                    schedule_duration_seconds = ?,
                    schedule_frequency = ?,
                    updated_at = ?
                WHERE cultivation_id = ? AND channel_key = ?
                """,
                row_values + (timestamp, int(cultivation["id"]), channel_key),
            )

    latest_payload = build_irrigation_payload(connection)
    latest_channels = latest_payload["channels"]
    latest_rows = {
        str(row["key"]): row
        for row in list(latest_payload.get("rows") or [])
        if isinstance(row, dict)
    }
    # The same target ceiling build_irrigation_payload() applies to schedules,
    # applied again here because this is where run rows are actually opened and
    # closed. The payload cut alone stops the relay bitmap but leaves the run
    # row active, so the dashboard would show a finished line against a run
    # still counting down -- and the next reconcile pass would reopen it.
    # Manual rows are left alone: they run out the duration that was typed.
    latest_row_list = list(latest_payload.get("rows") or [])
    schedule_windows = scheduled_irrigation_row_windows(latest_row_list, schedule_armed_rows)
    active_schedule_rows = cut_irrigation_rows_at_target(
        drop_finished_schedule_windows(
            scheduled_irrigation_row_map(latest_row_list, schedule_armed_rows),
            finished_schedule_windows(connection, schedule_windows),
        ),
        latest_row_list,
    )
    # The browser sends the tank confirmations it holds; merge them over what
    # is stored so a second page cannot wipe the first one's answer.
    lime_tank_acknowledged = acknowledged_lime_tank_solutions(stored_state_values)
    incoming_ack = payload.get("limeTankAcknowledged")
    if isinstance(incoming_ack, dict):
        for ack_key, ack_value in incoming_ack.items():
            cleaned = str(ack_key).strip()
            if cleaned:
                lime_tank_acknowledged[cleaned] = normalize_bool_flag(ack_value)

    # An acknowledgement covers its row's current planting and solution. It
    # outlives the pH coming back into range (the probe swings in and out by
    # itself), but not a new planting or the row needing the other solution.
    lime_tank_acknowledged = relevant_lime_tank_acknowledgements(
        latest_row_list, lime_tank_acknowledged
    )
    # Nothing doses lime for a row still waiting on its tank card, whichever
    # mode asked for it.
    active_manual_rows = hold_unconfirmed_lime_runs(
        active_manual_rows, latest_row_list, lime_tank_acknowledged
    )
    active_schedule_rows = hold_unconfirmed_lime_runs(
        active_schedule_rows, latest_row_list, lime_tank_acknowledged
    )

    # Tell the farm which solution the tank has to hold, once per row and
    # direction. Recorded only when the ask is new -- the acknowledgement map
    # above is the record of what has already been raised, so a row waiting
    # across many saves does not repeat the alert on each one.
    previously_pending = parse_json_object(
        stored_state_values.get("irrigation.lime_tank_pending") or "{}"
    )
    pending_now: dict[str, bool] = {}
    for row in latest_row_list:
        solution_key = str(row.get("limeSolutionNeeded") or "").strip()
        ack_key = lime_tank_row_acknowledgement_key(row)
        if not ack_key:
            continue
        row_key = str(row.get("key") or "")
        if lime_tank_acknowledged.get(ack_key):
            continue
        if not lime_tank_ask_is_due(
            row, stored_state_values.get("irrigation.active_automatic_rows")
        ):
            # Automatic at warning: it will not dose yet, so it does not ask
            # yet. Left out of pending_now so the alert fires when it does.
            continue
        pending_now[ack_key] = True
        if previously_pending.get(ack_key):
            continue
        solution_label = "pH Up" if solution_key == "up" else "pH Down"
        create_notification_record(
            connection,
            scope="all",
            type="warning",
            message=(
                f"{cultivation_row_label(row_key)} needs {solution_label}. "
                f"Make sure the lime solution tank holds {solution_label} solution, "
                "then confirm it on the Irrigation page before the line runs."
            ),
            source_type="irrigation",
            source_id="limeSolution",
        )
    write_state(
        key="irrigation.lime_tank_pending",
        value=json_dumps_compact(pending_now),
    )
    write_state(
        key="irrigation.lime_tank_ack",
        value=json_dumps_compact(lime_tank_acknowledged),
    )

    # A line that is on but has no run behind it gets one below, the same as a
    # line turning on. Only lines that were already on count -- one turning on
    # now is opened by the ordinary transition anyway.
    def already_on(
        channel_rows: dict[str, dict[str, bool]], state_key: str
    ) -> dict[str, dict[str, bool]]:
        stored = filter_active_irrigation_channel_rows(
            stored_state_values.get(state_key), cultivations
        )
        return {
            channel_key: {
                row_key: True for row_key in rows if row_key in stored.get(channel_key, {})
            }
            for channel_key, rows in channel_rows.items()
        }

    missing_timed_runs = timed_lines_without_a_run(
        connection,
        already_on(active_manual_rows, "irrigation.active_manual_rows"),
        already_on(active_schedule_rows, "irrigation.active_schedule_rows"),
    )
    # A manual line whose press is older than its own duration is already
    # over; opening a fresh run for it now would water a row nobody asked to
    # water again. It is switched off instead.
    if missing_timed_runs.get("manual"):
        stamp_row = connection.execute(
            "SELECT updated_at FROM system_state WHERE state_key = ?",
            ("irrigation.active_manual_rows",),
        ).fetchone()
        try:
            pressed_stamp = (
                parse_iso_datetime(str(stamp_row["updated_at"])) if stamp_row else None
            )
        except (TypeError, ValueError):
            pressed_stamp = None
        if pressed_stamp is not None:
            checked_at = utc_now()
            for channel_key, rows in missing_timed_runs["manual"].items():
                default_seconds = next(
                    (
                        item["manual_duration_seconds"]
                        for item in DEFAULT_IRRIGATION_CHANNELS
                        if str(item["channel_key"]).strip() == channel_key
                    ),
                    None,
                )
                for row_key in sorted(rows):
                    row_channel = (
                        (latest_rows.get(row_key, {}).get("channels") or {}).get(channel_key)
                        or latest_channels.get(channel_key, {})
                    )
                    seconds = normalize_irrigation_duration(
                        row_channel.get("manualDuration"),
                        latest_channels.get(channel_key, {}).get("manualDuration"),
                        default_seconds,
                    )
                    if pressed_stamp + timedelta(seconds=seconds) > checked_at:
                        continue
                    rows.discard(row_key)
                    channel_active = active_manual_rows.get(channel_key, {})
                    channel_active.pop(row_key, None)
                    if not channel_active:
                        active_manual_rows.pop(channel_key, None)

    active_automatic_rows = automatic_irrigation_row_map(
        latest_row_list,
        latest_channels,
        mode=mode,
        auto_enabled=auto_enabled,
        lime_tank_acknowledged=lime_tank_acknowledged,
        running_rows=filter_active_irrigation_channel_rows(
            stored_state_values.get("irrigation.active_automatic_rows"), cultivations
        ),
    )
    active_manual_lines = irrigation_lines_from_row_map(active_manual_rows)
    active_schedule_lines = irrigation_lines_from_row_map(active_schedule_rows)
    active_automatic_lines = irrigation_lines_from_row_map(active_automatic_rows)

    previous_run_rows = {
        # Read from stored state, like the other two, not from the computed
        # payload. The payload now cuts a manual line the moment its row
        # reaches the crop parameter, so `current` already reflects the cut --
        # previous and next would both be empty, the transition would be
        # invisible, and the run row would never be closed. Stored state is
        # what the relay was last told, which is what "previous" has to mean.
        "manual": filter_active_irrigation_channel_rows(
            stored_state_values.get("irrigation.active_manual_rows"),
            cultivations,
        ),
        "schedule": filter_active_irrigation_channel_rows(
            stored_state_values.get("irrigation.active_schedule_rows"),
            cultivations,
        ),
        "automatic": filter_active_irrigation_channel_rows(
            stored_state_values.get("irrigation.active_automatic_rows"),
            cultivations,
        ),
    }
    next_run_rows = {
        "manual": active_manual_rows,
        "schedule": active_schedule_rows,
        "automatic": active_automatic_rows,
    }
    duration_fields = {
        "manual": "manualDuration",
        "schedule": "scheduleDuration",
    }

    for run_mode, previous_channels in previous_run_rows.items():
        next_channels = next_run_rows[run_mode]
        for channel in DEFAULT_IRRIGATION_CHANNELS:
            channel_key = str(channel["channel_key"]).strip()
            previous_rows = previous_channels.get(channel_key, {})
            next_rows = next_channels.get(channel_key, {})
            for row_key in sorted(set(previous_rows) - set(next_rows)):
                close_active_irrigation_run(
                    connection,
                    channel_key,
                    mode=run_mode,
                    status="stopped",
                    notes=f"{run_mode.title()} irrigation stopped for {row_key}.",
                    row_key=row_key,
                )
                create_notification_record(
                    connection,
                    scope="all",
                    type="warning",
                    message=f"{channel_key} {run_mode} irrigation stopped for {row_key}.",
                    source_type="irrigation",
                    source_id=channel_key,
                )
            starting_rows = set(next_rows) - set(previous_rows)
            unrun_rows = (
                missing_timed_runs.get(run_mode, {}).get(channel_key, set()) & set(next_rows)
            )
            for row_key in sorted(starting_rows | unrun_rows):
                row_channel = (
                    (latest_rows.get(row_key, {}).get("channels") or {}).get(channel_key)
                    or latest_channels.get(channel_key, {})
                )
                # Zero records that an automatic run has no timer. Its live
                # sensor value decides when the relay stops.
                #
                # Only automatic may be zero. A manual or scheduled run whose
                # duration did not arrive -- a blank field, a row that has no
                # per-row override, a channel added since the last save -- used
                # to fall through `or 0` and open a run with no timer at all,
                # which reads downstream as "automatic" and never closes on the
                # clock. The row then watered until someone pressed Stop, which
                # looked like the timer being ignored rather than never set.
                #
                # normalize_irrigation_duration falls back through the row's
                # value, the channel default and finally the one second floor,
                # so a timed run always carries a real deadline.
                run_started_at = pressed_at if run_mode == "manual" else None
                if run_mode == "automatic":
                    duration_seconds = 0
                else:
                    duration_seconds = normalize_irrigation_duration(
                        row_channel.get(duration_fields[run_mode]),
                        latest_channels.get(channel_key, {}).get(
                            duration_fields[run_mode]
                        ),
                        channel[f"{run_mode}_duration_seconds"],
                    )
                window = (
                    schedule_windows.get(channel_key, {}).get(row_key)
                    if run_mode == "schedule"
                    else None
                )
                if window is not None:
                    # A scheduled run is its window: it starts when the window
                    # opens, not when this pass happened to notice, and it is
                    # exactly as long as the window. Its deadline -- which the
                    # board is sent and closes the valve on -- is then the
                    # window's end. Stamped with the time it was noticed, the
                    # board's deadline fell after the window closed, so the
                    # stop had to come from the backend over the network.
                    run_started_at = window[0].astimezone(timezone.utc)
                    duration_seconds = max(
                        IRRIGATION_MIN_DURATION_SECONDS,
                        int(round((window[1] - window[0]).total_seconds())),
                    )
                open_irrigation_run(
                    connection,
                    channel_key=channel_key,
                    mode=run_mode,
                    duration_seconds=duration_seconds,
                    requested_by_user_id=requested_by_user_id,
                    notes=f"{run_mode.title()} irrigation started for {row_key}.",
                    target_rows={row_key: True},
                    started_at=run_started_at,
                )
                if row_key not in starting_rows:
                    # Already announced wherever it was started.
                    continue
                create_notification_record(
                    connection,
                    scope="all",
                    type="success",
                    message=f"{channel_key} {run_mode} irrigation started for {row_key}.",
                    source_type="irrigation",
                    source_id=channel_key,
                )

    write_state(key="irrigation.mode", value=mode)
    write_state(key="irrigation.auto_enabled", value="1" if auto_enabled else "0")
    write_state(key="irrigation.active_manual_line", value=first_active_irrigation_line(active_manual_lines))
    write_state(key="irrigation.active_manual_lines", value=json_dumps_compact(active_manual_lines))
    write_state(key="irrigation.active_schedule_lines", value=json_dumps_compact(active_schedule_lines))
    write_state(key="irrigation.active_automatic_lines", value=json_dumps_compact(active_automatic_lines))
    write_state(key="irrigation.target_rows", value=json_dumps_compact(target_rows))
    write_state(key="irrigation.schedule_armed_rows", value=json_dumps_compact(schedule_armed_rows))
    write_state(key="irrigation.active_manual_rows", value=json_dumps_compact(active_manual_rows))
    write_state(key="irrigation.active_schedule_rows", value=json_dumps_compact(active_schedule_rows))
    write_state(key="irrigation.active_automatic_rows", value=json_dumps_compact(active_automatic_rows))
    return build_irrigation_payload(connection)


def reconcile_irrigation_state(connection: sqlite3.Connection) -> dict[str, object]:
    expire_due_irrigation_runs(connection)
    stored_state_values = system_state_map(connection)
    payload = build_irrigation_payload(connection)
    cultivations = list_cultivations(connection)
    stored_automatic_rows = filter_active_irrigation_channel_rows(
        stored_state_values.get("irrigation.active_automatic_rows"),
        cultivations,
    )
    computed_automatic_rows = filter_active_irrigation_channel_rows(
        payload.get("activeAutomaticRows"),
        cultivations,
    )
    stored_schedule_rows = filter_active_irrigation_channel_rows(
        stored_state_values.get("irrigation.active_schedule_rows"),
        cultivations,
    )
    computed_schedule_rows = filter_active_irrigation_channel_rows(
        payload.get("activeScheduleRows"),
        cultivations,
    )
    # Manual is compared too, which it was not before. Manual lines used to be
    # whatever the stored state said, so the computed payload could never
    # disagree with it and there was nothing to reconcile. Now the payload cuts
    # a manual line as soon as its row reaches the crop parameter, and if that
    # cut is not noticed here the relay keeps its valve open until the timer
    # runs out -- which is exactly the overshoot the cut exists to prevent.
    stored_manual_rows = filter_active_irrigation_channel_rows(
        stored_state_values.get("irrigation.active_manual_rows"),
        cultivations,
    )
    computed_manual_rows = filter_active_irrigation_channel_rows(
        payload.get("activeManualRows"),
        cultivations,
    )
    if (
        stored_automatic_rows != computed_automatic_rows
        or stored_schedule_rows != computed_schedule_rows
        or stored_manual_rows != computed_manual_rows
        or timed_lines_without_a_run(connection, computed_manual_rows, computed_schedule_rows)
    ):
        return update_irrigation_state(connection, {})
    return payload


def list_cultivations(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = connection.execute(
        """
        SELECT
            id,
            row_key,
            crop_type,
            custom_plant_name,
            crop_name,
            planting_date,
            harvest_date,
            days_to_harvest,
            parameter_mode,
            parameters_json,
            created_by_user_id,
            created_at,
            updated_at
        FROM cultivations
        ORDER BY row_key ASC, created_at DESC
        """
    ).fetchall()
    return rows


HARVEST_COLUMNS = (
    "id",
    "row_key",
    "crop_type",
    "custom_plant_name",
    "crop_name",
    "planting_date",
    "harvest_date",
    "days_to_harvest",
    "parameter_mode",
    "parameters_json",
    "harvested_at",
    "days_grown",
    "on_schedule",
    "outcome",
    "planted_by_user_id",
    "harvested_by_user_id",
    "created_at",
)


def record_cultivation_harvest(
    connection: sqlite3.Connection,
    cultivation: sqlite3.Row,
    *,
    harvested_by_user_id: object = None,
    harvested_at: str | None = None,
    outcome: str = "harvested",
) -> sqlite3.Row | None:
    """Copy a finished cultivation into the harvest history.

    Called just before the cultivation is deleted, so the row it is reading is
    about to stop existing. Everything the history needs is copied rather than
    referenced for exactly that reason.

    days_grown and on_schedule are worked out here, once, and stored. Deriving
    them on read would need "today", and a report re-run tomorrow would then
    answer differently about the same finished crop.

    INSERT OR IGNORE against the natural-key unique index: the same harvest can
    arrive twice when the HTTPS relay carries it and the ordinary sync later
    finds it, and neither transport has a durable ack. Returns None when the
    row was already present, which is a no-op rather than an error.
    """
    stamp = str(harvested_at or utc_now_iso()).strip()
    planting_date = str(cultivation["planting_date"]).strip()
    harvest_date = str(cultivation["harvest_date"]).strip()
    normalized_outcome = (
        "removed" if str(outcome or "").strip().lower() == "removed" else "harvested"
    )

    # Whole days between planting and the moment the grower said it was done.
    # Clamped at zero so a clock that briefly ran backwards cannot store a
    # negative growing season.
    try:
        grown = (parse_iso_datetime(stamp).date() - date.fromisoformat(planting_date)).days
    except (TypeError, ValueError):
        grown = 0
    days_grown = max(0, grown)

    # "On schedule" means it was not harvested after the planned date. A crop
    # taken early is still on schedule -- the grower judged it ready -- so this
    # is deliberately not an equality test.
    #
    # A removed crop was never harvested at all, so the question does not apply
    # to it. Storing False would read in the report as "finished late", which
    # is a different and wrong claim; the outcome column is what says it never
    # finished, and the schedule columns are left alone for the harvests where
    # they mean something.
    try:
        on_schedule = parse_iso_datetime(stamp).date() <= date.fromisoformat(harvest_date)
    except (TypeError, ValueError):
        on_schedule = True
    if normalized_outcome == "removed":
        on_schedule = True

    connection.execute(
        """
        INSERT OR IGNORE INTO cultivation_harvests (
            row_key, crop_type, custom_plant_name, crop_name,
            planting_date, harvest_date, days_to_harvest,
            parameter_mode, parameters_json,
            harvested_at, days_grown, on_schedule, outcome,
            planted_by_user_id, harvested_by_user_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(cultivation["row_key"]).strip(),
            str(cultivation["crop_type"]).strip(),
            str(cultivation["custom_plant_name"] or "").strip(),
            str(cultivation["crop_name"]).strip(),
            planting_date,
            harvest_date,
            int(cultivation["days_to_harvest"]),
            str(cultivation["parameter_mode"]).strip(),
            # Round-tripped through parse_json_object rather than copied raw:
            # the source column is jsonb on Postgres (a dict) and TEXT on
            # SQLite (a string), and this column has to end up as text either
            # way. Dumped with the same separators/sort_keys as the cultivation
            # insert so the two stores hold byte-identical JSON.
            json.dumps(
                parse_json_object(cultivation["parameters_json"]),
                separators=(",", ":"),
                sort_keys=True,
            ),
            stamp,
            days_grown,
            1 if on_schedule else 0,
            normalized_outcome,
            cultivation["created_by_user_id"],
            int(harvested_by_user_id) if str(harvested_by_user_id or "").isdigit() else None,
            str(cultivation["created_at"]).strip(),
        ),
    )
    return find_cultivation_harvest(
        connection,
        row_key=str(cultivation["row_key"]).strip(),
        planting_date=planting_date,
        harvested_at=stamp,
    )


def find_cultivation_harvest(
    connection: sqlite3.Connection,
    *,
    row_key: str,
    planting_date: str,
    harvested_at: str,
) -> sqlite3.Row | None:
    return connection.execute(
        f"""
        SELECT {', '.join(HARVEST_COLUMNS)}
        FROM cultivation_harvests
        WHERE row_key = ? AND planting_date = ? AND harvested_at = ?
        """,  # nosec B608 - HARVEST_COLUMNS is a module constant, values are bound
        (row_key, planting_date, harvested_at),
    ).fetchone()


def list_cultivation_harvests(
    connection: sqlite3.Connection,
    *,
    limit: int = 50,
) -> list[sqlite3.Row]:
    """The most recent completed crops, newest first."""
    return connection.execute(
        f"""
        SELECT {', '.join(HARVEST_COLUMNS)}
        FROM cultivation_harvests
        ORDER BY harvested_at DESC
        LIMIT ?
        """,  # nosec B608 - HARVEST_COLUMNS is a module constant, values are bound
        (int(limit),),
    ).fetchall()


# Notification queries are filtered by role scope so admins and users only see relevant events.
# Account bookkeeping -- an account added, an account removed. These are
# written for the audit trail and are not farm events: the bell and the
# Notification History page are where someone looks to find out what the
# greenhouse is doing, and "Chy was added successfully and can now log in."
# answers a question nobody asked there. They stay in the table, so the record
# survives and the report can still account for them, and they are filtered out
# of the one place they did not belong.
HIDDEN_NOTIFICATION_SOURCE_TYPES = ("user",)

# The most history one request will carry. This query had no bound at all, so
# the payload grew with the table for the life of the farm: this Pi holds 5,133
# notification rows, and every dashboard load and every notification refresh
# fetched all of them, on the kiosk and over the uplink alike.
#
# 500 is far past what the page draws -- it pages 50 at a time -- so the button
# and the scroll-to-load still reach the end of what a grower reads back,
# while the reply stays a fixed size. Nothing is destroyed: the rows remain in
# the table for the reports, which query it directly.
NOTIFICATION_HISTORY_LIMIT = 500


def list_notifications_for_user(connection: sqlite3.Connection, *, user_id: int, role: str) -> list[sqlite3.Row]:
    # Built from the constant rather than written out, so adding a source type
    # to hide needs no second edit here and the two cannot drift apart.
    hidden = ", ".join("?" for _ in HIDDEN_NOTIFICATION_SOURCE_TYPES)
    return connection.execute(
        f"""
        SELECT
            notifications.id,
            notifications.scope,
            notifications.type,
            notifications.message,
            notifications.source_type,
            notifications.source_id,
            notifications.created_at,
            CASE WHEN notification_reads.id IS NULL THEN 0 ELSE 1 END AS is_read
        FROM notifications
        LEFT JOIN notification_reads
            ON notification_reads.notification_id = notifications.id
           AND notification_reads.user_id = ?
        WHERE notifications.scope IN ('all', ?)
          AND notifications.deleted_at IS NULL
          AND notifications.source_type NOT IN ({hidden})
        ORDER BY notifications.created_at DESC, notifications.id DESC
        LIMIT ?
        """,  # nosec B608 - only '?' placeholders interpolated; values are bound parameters
        (
            int(user_id),
            normalize_role(role),
            *HIDDEN_NOTIFICATION_SOURCE_TYPES,
            NOTIFICATION_HISTORY_LIMIT,
        ),
    ).fetchall()


def database_integrity_error(error: BaseException) -> bool:
    """Whether this is a constraint violation from either supported driver.

    The two schemas are not identical: Supabase carries a UNIQUE across the six
    fields that identify a notification, and the SQLite file does not. So a
    duplicate raised only on the hosted site, and only as a driver-specific
    class the caller had no reason to expect.
    """
    if isinstance(error, sqlite3.IntegrityError):
        return True
    if not postgres_backend_enabled():
        return False
    try:
        import psycopg
    except ImportError:
        return False
    return isinstance(error, psycopg.errors.IntegrityError)


# Farm events: what the sensors read, what the fan, lamp, mister and valves
# did. The Raspberry Pi is the only host that holds the sensors and the relays,
# so it is the only one that records these; the website receives the Pi's own
# rows over the sync, created_at and all.
#
# The website used to record its own. Each Vercel instance judged the relayed
# readings with an empty memory of what it had already announced, so every
# cold start announced every out-of-range row again -- 18,605 rows online
# against the Pi's 1,372 in one day. After a Delete all the website's History
# refilled before the kiosk's, and because the two copies of one alert carried
# different created_at, a deletion on one side matched nothing on the other.
PI_WRITTEN_NOTIFICATION_SOURCES = frozenset({"reading", "greenhouse", "irrigation", "actuator"})


def notification_is_left_to_the_pi(source_type: object) -> bool:
    """True where this host must not record a farm event itself."""
    return (
        running_on_managed_host()
        and str(source_type or "").strip() in PI_WRITTEN_NOTIFICATION_SOURCES
    )


def create_notification_record(
    connection: sqlite3.Connection,
    *,
    scope: str,
    type: str,
    message: str,
    source_type: str = "",
    source_id: str = "",
) -> sqlite3.Row | None:
    if notification_is_left_to_the_pi(source_type):
        return None
    created_at = utc_now_iso()
    try:
        cursor = connection.execute(
            """
            INSERT INTO notifications (
                scope,
                type,
                message,
                source_type,
                source_id,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                normalize_notification_scope(scope),
                str(type or "success").strip() or "success",
                str(message or "").strip(),
                str(source_type or "").strip(),
                str(source_id or "").strip(),
                created_at,
            ),
        )
    except Exception as error:  # noqa: BLE001 - driver-specific integrity errors
        if not database_integrity_error(error):
            raise
        cursor = None
    # A row identical in all six key fields already exists when the same event
    # is recorded twice in the same microsecond, which the sync can do while a
    # press is in flight. Supabase enforces that as UNIQUE; SQLite here does
    # not, so the duplicate only ever failed on the hosted site. Fall back to
    # reading the existing row instead of letting the insert escape.
    row_id = cursor.lastrowid if cursor is not None else None
    if row_id:
        notification = connection.execute(
            """
            SELECT id, scope, type, message, source_type, source_id, created_at, 0 AS is_read
            FROM notifications
            WHERE id = ?
            """,
            (int(row_id),),
        ).fetchone()
    else:
        notification = connection.execute(
            """
            SELECT id, scope, type, message, source_type, source_id, created_at, 0 AS is_read
            FROM notifications
            WHERE scope = ? AND type = ? AND message = ?
              AND source_type = ? AND source_id = ? AND created_at = ?
            """,
            (
                normalize_notification_scope(scope),
                str(type or "success").strip() or "success",
                str(message or "").strip(),
                str(source_type or "").strip(),
                str(source_id or "").strip(),
                created_at,
            ),
        ).fetchone()
    # The Pi owns farm-control events locally and writes them to its own
    # database. tools/sync_sqlite_to_supabase.py carries them to the cloud on
    # a timer, keyed on (scope, type, message, created_at) so a notification
    # cleared in the dashboard is not resurrected from the Pi.
    return notification


def insert_synced_notification(connection: sqlite3.Connection, item: dict[str, object]) -> bool:
    """Store a History entry recorded on the other side, as it was recorded.

    True when a row was added. The created_at is the author's, never a new
    one: that is what makes the two copies the same row under the six-field
    natural key, so a deletion made on either side finds its twin on the other.
    A copy already held -- live or deleted -- is left alone, so a deleted
    entry is never brought back by a late upload. Raises ValueError for an
    entry that is not a complete key.
    """
    scope = str(item.get("scope") or "").strip()
    notification_type = str(item.get("type") or "").strip()
    message = str(item.get("message") or "").strip()
    source_type = str(item.get("sourceType") or "").strip()
    source_id = str(item.get("sourceId") or "").strip()
    created_at = str(item.get("createdAt") or "").strip()
    if scope not in VALID_NOTIFICATION_SCOPES or not notification_type or not message:
        raise ValueError("A complete notification history key is required.")
    try:
        parse_iso_datetime(created_at)
    except (TypeError, ValueError) as error:
        raise ValueError("A notification needs the time it was recorded.") from error

    key = (scope, notification_type, message, source_type, source_id, created_at)
    held = connection.execute(
        """
        SELECT 1 FROM notifications
        WHERE scope = ? AND type = ? AND message = ?
          AND source_type = ? AND source_id = ? AND created_at = ?
        """,
        key,
    ).fetchone()
    if held is not None:
        return False
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO notifications (scope, type, message, source_type, source_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        key,
    )
    return max(0, int(cursor.rowcount or 0)) > 0


def apply_remote_synced_notifications(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    """History recorded on the website, stored on the Pi. Device-token only."""
    items = payload.get("notifications")
    if not isinstance(items, list):
        return HTTPStatus.BAD_REQUEST, {"message": "A notifications list is required."}
    added = refused = 0
    with connect_database() as connection:
        for item in items[:500]:
            if not isinstance(item, dict):
                refused += 1
                continue
            try:
                added += int(insert_synced_notification(connection, item))
            except ValueError:
                refused += 1
        connection.commit()
    return HTTPStatus.OK, {
        "message": "Synced History entries stored.",
        "applied": added,
        "refused": refused,
    }


def mark_notifications_read(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    role: str,
    notification_ids: list[int] | None = None,
) -> None:
    # Read state is stored per-user so one person's bell state does not affect others.
    normalized_role = normalize_role(role)
    timestamp = utc_now_iso()

    if notification_ids:
        placeholders = ", ".join("?" for _ in notification_ids)
        connection.execute(
            f"""
            INSERT OR IGNORE INTO notification_reads (notification_id, user_id, read_at)
            SELECT notifications.id, ?, ?
            FROM notifications
            WHERE notifications.scope IN ('all', ?)
              AND notifications.deleted_at IS NULL
              AND notifications.id IN ({placeholders})
            """,  # nosec B608 - only '?' placeholders / module constants interpolated; values are bound parameters
            (int(user_id), timestamp, normalized_role, *(int(item) for item in notification_ids)),
        )
        return

    connection.execute(
        """
        INSERT OR IGNORE INTO notification_reads (notification_id, user_id, read_at)
        SELECT notifications.id, ?, ?
        FROM notifications
        WHERE notifications.scope IN ('all', ?)
          AND notifications.deleted_at IS NULL
        """,
        (int(user_id), timestamp, normalized_role),
    )


def delete_notification_record(connection: sqlite3.Connection, notification_id: int) -> sqlite3.Row | None:
    notification = connection.execute(
        """
        SELECT id, scope, type, message, source_type, source_id, created_at
        FROM notifications
        WHERE id = ? AND deleted_at IS NULL
        """,
        (int(notification_id),),
    ).fetchone()
    if not notification:
        return None

    # Marked, not removed: the mark is what the sync carries to the other
    # device. purge_deleted_notifications() removes the row for real once both
    # sides have had time to see it.
    connection.execute(
        "UPDATE notifications SET deleted_at = ? WHERE id = ?",
        (utc_now_iso(), int(notification_id)),
    )
    return notification


def delete_all_notification_records_for_role(
    connection: sqlite3.Connection, *, role: str, created_before: str = ""
) -> int:
    """Soft-delete every visible notification for a role.

    created_before bounds it to what existed when the person pressed Delete
    all. The press made on the website reaches the Pi seconds or hours later,
    and without the bound it also erased every alert the farm had recorded in
    the meantime -- history nobody had seen, let alone chosen to delete.
    """
    normalized_role = normalize_role(role)
    cutoff = str(created_before or "").strip()
    if cutoff:
        notifications = connection.execute(
            """
            SELECT id
            FROM notifications
            WHERE scope IN ('all', ?) AND deleted_at IS NULL AND created_at <= ?
            """,
            (normalized_role, cutoff),
        ).fetchall()
    else:
        notifications = connection.execute(
            """
            SELECT id
            FROM notifications
            WHERE scope IN ('all', ?) AND deleted_at IS NULL
            """,
            (normalized_role,),
        ).fetchall()
    notification_ids = [int(notification["id"]) for notification in notifications]
    if not notification_ids:
        return 0

    # The read receipts stay with the row. Both go for real in the purge, and
    # deleting them now would strip the evidence before the other device has
    # been told anything happened.
    placeholders = ", ".join("?" for _ in notification_ids)
    connection.execute(
        f"UPDATE notifications SET deleted_at = ? WHERE id IN ({placeholders})",  # nosec B608 - only '?' placeholders / module constants interpolated; values are bound parameters
        (utc_now_iso(), *notification_ids),
    )
    return len(notification_ids)


# The newest "Delete all" pressed at the kiosk, for the relay to carry up.
# Each side records its own History, so the website's copy of an alert has its
# own created_at and never matches the Pi's row for row: a press sent up as
# the rows it deleted removed nothing online. It goes up as the cutoff
# instead, exactly as a press on the website comes down. Not one of the
# system_state keys the edge sync carries, so it stays on this installation.
KIOSK_HISTORY_DELETE_ALL_STATE_KEY = "history.delete_all_up"


def remember_kiosk_history_delete_all(connection: sqlite3.Connection, *, role: str) -> None:
    """Record a kiosk Delete all press; only the newest cutoff matters."""
    set_system_state_value(
        connection,
        key=KIOSK_HISTORY_DELETE_ALL_STATE_KEY,
        value=json_dumps_compact({"role": normalize_role(role), "before": utc_now_iso()}),
    )


def find_cultivation_by_id(connection: sqlite3.Connection, cultivation_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            id,
            row_key,
            crop_type,
            custom_plant_name,
            crop_name,
            planting_date,
            harvest_date,
            days_to_harvest,
            parameter_mode,
            parameters_json,
            created_by_user_id,
            created_at,
            updated_at
        FROM cultivations
        WHERE id = ?
        """,
        (int(cultivation_id),),
    ).fetchone()


def find_cultivation_by_row_key(connection: sqlite3.Connection, row_key: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            id,
            row_key,
            crop_type,
            custom_plant_name,
            crop_name,
            planting_date,
            harvest_date,
            days_to_harvest,
            parameter_mode,
            parameters_json,
            created_by_user_id,
            created_at,
            updated_at
        FROM cultivations
        WHERE row_key = ?
        """,
        (str(row_key).strip().lower(),),
    ).fetchone()


def create_cultivation_record(
    connection: sqlite3.Connection,
    *,
    row_key: str,
    crop_type: str,
    custom_plant_name: str,
    crop_name: str,
    planting_date: str,
    harvest_date: str,
    days_to_harvest: int,
    parameter_mode: str,
    parameters: dict[str, dict[str, float]],
    created_by_user_id: int | None,
) -> sqlite3.Row:
    timestamp = utc_now_iso()
    cursor = connection.execute(
        """
        INSERT INTO cultivations (
            row_key,
            crop_type,
            custom_plant_name,
            crop_name,
            planting_date,
            harvest_date,
            days_to_harvest,
            parameter_mode,
            parameters_json,
            created_by_user_id,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row_key,
            crop_type,
            custom_plant_name,
            crop_name,
            planting_date,
            harvest_date,
            int(days_to_harvest),
            parameter_mode,
            json.dumps(parameters, separators=(",", ":"), sort_keys=True),
            created_by_user_id,
            timestamp,
            timestamp,
        ),
    )
    ensure_irrigation_row_schema(connection)
    return find_cultivation_by_id(connection, int(cursor.lastrowid))


def update_cultivation_record(
    connection: sqlite3.Connection,
    *,
    cultivation_id: int,
    planting_date: str,
    harvest_date: str,
    days_to_harvest: int,
    parameters: dict[str, dict[str, float]],
) -> sqlite3.Row | None:
    """Correct a growing row's dates and target range in place.

    Nothing that identifies the planting moves -- not the row, not the crop,
    not created_at. Only what the parameters dialog offers.

    updated_at is what carries the change off this machine: the Pi<->Supabase
    sync settles a row that exists on both sides by comparing it, and the
    realtime fingerprint every open browser polls is MAX(updated_at) over this
    table. An edit that left it alone would stay on the host it was made on.
    """
    connection.execute(
        """
        UPDATE cultivations
           SET planting_date = ?,
               harvest_date = ?,
               days_to_harvest = ?,
               parameters_json = ?,
               updated_at = ?
         WHERE id = ?
        """,
        (
            planting_date,
            harvest_date,
            int(days_to_harvest),
            json.dumps(parameters, separators=(",", ":"), sort_keys=True),
            utc_now_iso(),
            int(cultivation_id),
        ),
    )
    return find_cultivation_by_id(connection, int(cultivation_id))


def insert_user_account(
    connection: sqlite3.Connection,
    *,
    display_name: str,
    email: str,
    role: str,
    password_hash: str,
    password_salt: str,
    password_iterations: int,
) -> sqlite3.Row:
    timestamp = utc_now_iso()
    cursor = connection.execute(
        """
        INSERT INTO users (
            display_name,
            email,
            role,
            password_hash,
            password_salt,
            password_iterations,
            is_active,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, TRUE, ?, ?)
        """,
        (
            display_name.strip(),
            normalize_email(email),
            normalize_role(role),
            password_hash,
            password_salt,
            int(password_iterations),
            timestamp,
            timestamp,
        ),
    )
    return connection.execute(
        """
        SELECT id, display_name, email, role, password_hash, password_salt, password_iterations,
               is_active, profile_photo_path, profile_photo_version,
               length(profile_photo_data) AS profile_photo_bytes
        FROM users
        WHERE id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()


def update_user_profile(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    display_name: str,
    profile_photo_data: bytes | None = None,
    profile_photo_mime: str = "",
    profile_photo_version: str = "",
) -> sqlite3.Row | None:
    timestamp = utc_now_iso()
    if profile_photo_data is None:
        connection.execute(
            """
            UPDATE users
            SET display_name = ?, updated_at = ?
            WHERE id = ?
            """,
            (display_name.strip(), timestamp, int(user_id)),
        )
    else:
        connection.execute(
            """
            UPDATE users
            SET display_name = ?,
                profile_photo_path = '',
                profile_photo_mime = ?,
                profile_photo_data = ?,
                profile_photo_version = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                display_name.strip(),
                profile_photo_mime,
                sqlite3.Binary(profile_photo_data),
                profile_photo_version or timestamp,
                timestamp,
                int(user_id),
            ),
        )

    return find_user_by_id(connection, int(user_id))


def create_user_account(
    connection: sqlite3.Connection,
    *,
    display_name: str,
    email: str,
    role: str,
    password: str,
) -> sqlite3.Row:
    salt, digest = create_secret_hash(password, iterations=PASSWORD_ITERATIONS)
    return insert_user_account(
        connection,
        display_name=display_name,
        email=email,
        role=role,
        password_hash=digest,
        password_salt=salt,
        password_iterations=PASSWORD_ITERATIONS,
    )


def delete_user_account_record(
    connection: sqlite3.Connection,
    *,
    user_id: int | None = None,
    email: str | None = None,
) -> sqlite3.Row | None:
    if user_id is None and not str(email or "").strip():
        raise ValueError("Provide a user id or email address.")

    query = """
        SELECT id, display_name, email, role, is_active, profile_photo_path,
               profile_photo_version, created_at
        FROM users
        WHERE {condition}
    """
    params: tuple[object, ...]
    if user_id is not None:
        condition = "id = ?"
        params = (int(user_id),)
    else:
        condition = "email = ?"
        params = (normalize_email(email),)

    user = connection.execute(query.format(condition=condition), params).fetchone()
    if not user:
        return None

    profile_photo_path = optional_row_value(user, "profile_photo_path")
    record_sync_tombstone(
        connection,
        entity=USER_TOMBSTONE,
        natural_key=user_sync_key(user["email"], optional_row_value(user, "created_at")),
    )
    connection.execute("DELETE FROM users WHERE id = ?", (int(user["id"]),))
    invalidate_auth_session_user_cache(int(user["id"]))
    if profile_photo_path:
        delete_profile_photo_file(profile_photo_path)
    return user


def create_account_creation_challenge(
    connection: sqlite3.Connection,
    *,
    display_name: str,
    email: str,
    role: str,
    password: str,
) -> tuple[str, str, str]:
    challenge_id = secrets.token_urlsafe(24)
    otp_code = generate_otp_code()
    password_salt, password_digest = create_secret_hash(password, iterations=PASSWORD_ITERATIONS)
    otp_salt, otp_digest = create_secret_hash(otp_code, iterations=OTP_ITERATIONS)
    created_at = utc_now()
    expires_at = created_at + timedelta(minutes=OTP_EXPIRY_MINUTES)

    connection.execute(
        "DELETE FROM account_creation_challenges WHERE email = ?",
        (normalize_email(email),),
    )
    connection.execute(
        """
        INSERT INTO account_creation_challenges (
            id,
            display_name,
            email,
            role,
            password_hash,
            password_salt,
            password_iterations,
            otp_hash,
            otp_salt,
            otp_iterations,
            attempt_count,
            max_attempts,
            created_at,
            expires_at,
            consumed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, NULL)
        """,
        (
            challenge_id,
            display_name.strip(),
            normalize_email(email),
            normalize_role(role),
            password_digest,
            password_salt,
            PASSWORD_ITERATIONS,
            otp_digest,
            otp_salt,
            OTP_ITERATIONS,
            OTP_MAX_ATTEMPTS,
            created_at.isoformat(),
            expires_at.isoformat(),
        ),
    )
    return challenge_id, otp_code, expires_at.isoformat()


def create_login_challenge(connection: sqlite3.Connection, user: sqlite3.Row) -> tuple[str, str, str]:
    challenge_id = secrets.token_urlsafe(24)
    otp_code = generate_otp_code()
    salt, digest = create_secret_hash(otp_code, iterations=OTP_ITERATIONS)
    created_at = utc_now()
    expires_at = created_at + timedelta(minutes=OTP_EXPIRY_MINUTES)

    connection.execute(
        "DELETE FROM login_challenges WHERE user_id = ?",
        (user["id"],),
    )
    connection.execute(
        """
        INSERT INTO login_challenges (
            id,
            user_id,
            otp_hash,
            otp_salt,
            otp_iterations,
            attempt_count,
            max_attempts,
            created_at,
            expires_at,
            consumed_at
        ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, NULL)
        """,
        (
            challenge_id,
            user["id"],
            digest,
            salt,
            OTP_ITERATIONS,
            OTP_MAX_ATTEMPTS,
            created_at.isoformat(),
            expires_at.isoformat(),
        ),
    )
    return challenge_id, otp_code, expires_at.isoformat()


def get_login_challenge(connection: sqlite3.Connection, challenge_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            login_challenges.id AS challenge_id,
            login_challenges.user_id,
            login_challenges.otp_hash,
            login_challenges.otp_salt,
            login_challenges.otp_iterations,
            login_challenges.attempt_count,
            login_challenges.max_attempts,
            login_challenges.expires_at,
            login_challenges.consumed_at,
            users.id,
            users.display_name,
            users.email,
            users.role,
            users.is_active,
            users.profile_photo_path,
            users.profile_photo_version
        FROM login_challenges
        JOIN users ON users.id = login_challenges.user_id
        WHERE login_challenges.id = ?
        """,
        (challenge_id,),
    ).fetchone()


def get_account_creation_challenge(connection: sqlite3.Connection, challenge_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            id,
            display_name,
            email,
            role,
            password_hash,
            password_salt,
            password_iterations,
            otp_hash,
            otp_salt,
            otp_iterations,
            attempt_count,
            max_attempts,
            expires_at,
            consumed_at
        FROM account_creation_challenges
        WHERE id = ?
        """,
        (challenge_id,),
    ).fetchone()


def verify_login_challenge(
    connection: sqlite3.Connection,
    challenge_id: str,
    otp_code: str,
    *,
    consume: bool,
) -> tuple[bool, dict[str, str]]:
    # One wording for every "the code did not work" outcome. A decoy challenge
    # id handed out for an unregistered address lands here (no such challenge);
    # a real account with a wrong code lands below. Both must read the same, and
    # take the same time, or the difference enumerates accounts.
    generic_otp_failure = "The code is incorrect or has expired. Please request a new code."

    challenge = get_login_challenge(connection, challenge_id)
    if not challenge:
        burn_password_verification(iterations=OTP_ITERATIONS)
        return False, {"message": generic_otp_failure}

    if challenge["consumed_at"]:
        return False, {"message": "OTP session has already been used."}

    if int(challenge["is_active"]) != 1:
        return False, {"message": "This account is inactive."}

    if parse_iso_datetime(str(challenge["expires_at"])) <= utc_now():
        connection.execute("DELETE FROM login_challenges WHERE id = ?", (challenge_id,))
        return False, {"message": "OTP has already expired. Please request a new code."}

    attempts = int(challenge["attempt_count"])
    max_attempts = int(challenge["max_attempts"])
    if attempts >= max_attempts:
        connection.execute("DELETE FROM login_challenges WHERE id = ?", (challenge_id,))
        return False, {"message": "Too many OTP attempts. Please request a new code."}

    is_match = verify_secret(
        otp_code,
        salt=str(challenge["otp_salt"]),
        digest=str(challenge["otp_hash"]),
        iterations=int(challenge["otp_iterations"]),
    )
    if not is_match:
        connection.execute(
            "UPDATE login_challenges SET attempt_count = attempt_count + 1 WHERE id = ?",
            (challenge_id,),
        )
        remaining_attempts = max(0, max_attempts - (attempts + 1))
        if remaining_attempts == 0:
            connection.execute("DELETE FROM login_challenges WHERE id = ?", (challenge_id,))
        return False, {"message": generic_otp_failure}

    if consume:
        connection.execute(
            "UPDATE login_challenges SET consumed_at = ? WHERE id = ?",
            (utc_now_iso(), challenge_id),
        )
        connection.execute(
            "DELETE FROM login_challenges WHERE user_id = ? AND id <> ?",
            (challenge["user_id"], challenge_id),
        )
    return True, build_user_payload(challenge)


def verify_account_creation_challenge(
    connection: sqlite3.Connection,
    challenge_id: str,
    otp_code: str,
    *,
    consume: bool,
) -> tuple[bool, sqlite3.Row | dict[str, str]]:
    challenge = get_account_creation_challenge(connection, challenge_id)
    if not challenge:
        return False, {"message": "OTP session is invalid or already expired."}

    if challenge["consumed_at"]:
        return False, {"message": "OTP session has already been used."}

    if parse_iso_datetime(str(challenge["expires_at"])) <= utc_now():
        connection.execute("DELETE FROM account_creation_challenges WHERE id = ?", (challenge_id,))
        return False, {"message": "OTP has already expired. Please request a new code."}

    attempts = int(challenge["attempt_count"])
    max_attempts = int(challenge["max_attempts"])
    if attempts >= max_attempts:
        connection.execute("DELETE FROM account_creation_challenges WHERE id = ?", (challenge_id,))
        return False, {"message": "Too many OTP attempts. Please request a new code."}

    is_match = verify_secret(
        otp_code,
        salt=str(challenge["otp_salt"]),
        digest=str(challenge["otp_hash"]),
        iterations=int(challenge["otp_iterations"]),
    )
    if not is_match:
        connection.execute(
            "UPDATE account_creation_challenges SET attempt_count = attempt_count + 1 WHERE id = ?",
            (challenge_id,),
        )
        remaining_attempts = max(0, max_attempts - (attempts + 1))
        if remaining_attempts == 0:
            connection.execute("DELETE FROM account_creation_challenges WHERE id = ?", (challenge_id,))
            return False, {"message": "OTP does not match. Please request a new code."}
        return False, {
            "message": f"OTP does not match. {remaining_attempts} attempt(s) remaining.",
        }

    if consume:
        connection.execute(
            "UPDATE account_creation_challenges SET consumed_at = ? WHERE id = ?",
            (utc_now_iso(), challenge_id),
        )
        connection.execute(
            "DELETE FROM account_creation_challenges WHERE email = ? AND id <> ?",
            (normalize_email(challenge["email"]), challenge_id),
        )
    return True, challenge












def der_read_value(data: bytes, offset: int = 0) -> tuple[int, bytes, int]:
    if offset >= len(data):
        raise ValueError("Invalid DER value.")
    tag = data[offset]
    offset += 1
    if offset >= len(data):
        raise ValueError("Invalid DER length.")
    first_length = data[offset]
    offset += 1
    if first_length & 0x80:
        length_bytes = first_length & 0x7F
        if length_bytes < 1 or length_bytes > 4 or offset + length_bytes > len(data):
            raise ValueError("Invalid DER long length.")
        length = int.from_bytes(data[offset : offset + length_bytes], "big")
        offset += length_bytes
    else:
        length = first_length
    end = offset + length
    if end > len(data):
        raise ValueError("Truncated DER value.")
    return tag, data[offset:end], end












def json_safe_copy(value: object) -> object:
    """Return a JSON-safe copy so callers cannot mutate the shared cache."""
    return json.loads(json.dumps(value, separators=(",", ":"), ensure_ascii=True))


































































































































































def sensor_reading_is_demo(record: dict[str, object]) -> bool:
    source_type = str(record.get("source_type") or record.get("sourceType") or "").strip().lower()
    source_identifier = str(
        record.get("source_identifier") or record.get("sourceIdentifier") or ""
    ).strip().lower()
    return source_type in {"seed", "hybrid-sync-test"} or source_identifier in {
        "default-backfill",
        "seed-simulator",
    }
















































def sqlite_row_to_record(row: sqlite3.Row) -> dict[str, object]:
    return {key: row[key] for key in row.keys()}




def sqlite_snapshot_map(rows: list[sqlite3.Row], key_field: str) -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}
    for row in rows:
        record = sqlite_row_to_record(row)
        snapshot[str(record[key_field]).strip()] = record
    return snapshot


def sqlite_notification_reads_snapshot(connection: sqlite3.Connection) -> dict[str, dict[str, dict[str, object]]]:
    rows = connection.execute(
        """
        SELECT notification_id, user_id, read_at
        FROM notification_reads
        ORDER BY notification_id ASC, user_id ASC
        """
    ).fetchall()
    snapshot: dict[str, dict[str, dict[str, object]]] = {}
    for row in rows:
        user_id = str(int(row["user_id"]))
        notification_id = str(int(row["notification_id"]))
        snapshot.setdefault(user_id, {})[notification_id] = {
            "notification_id": int(row["notification_id"]),
            "user_id": int(row["user_id"]),
            "read_at": str(row["read_at"]).strip(),
        }
    return snapshot


def sqlite_system_state_snapshot(connection: sqlite3.Connection) -> dict[str, str]:
    rows = connection.execute(
        """
        SELECT state_key, state_value
        FROM system_state
        ORDER BY state_key ASC
        """
    ).fetchall()
    return {
        str(row["state_key"]).strip(): str(row["state_value"]).strip()
        for row in rows
    }




















PI_CULTIVATION_CACHE_MIGRATION_KEY = "migration.pi_local_cultivations_v1"








def irrigation_control_surface(payload: dict[str, object]) -> str:
    """The part of the irrigation payload a person changes.

    Deliberately not the whole payload: `rows` carries each row's live soil
    reading, which moves every few seconds on its own, so fingerprinting the
    payload itself would announce a control change on every sensor message.
    What is left is the mode, the running lines, and the durations -- values
    that only move when someone presses something, here or on the far side of
    the sync.
    """
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    return json_dumps_compact({
        "mode": payload.get("mode"),
        "autoEnabled": payload.get("autoEnabled"),
        "rowModes": payload.get("rowModes"),
        "targetRows": payload.get("targetRows"),
        "scheduleArmedRows": payload.get("scheduleArmedRows"),
        "activeManualRows": payload.get("activeManualRows"),
        "activeScheduleRows": payload.get("activeScheduleRows"),
        "activeAutomaticRows": payload.get("activeAutomaticRows"),
        "channels": payload.get("channels"),
        "rowChannels": {
            str(row.get("key") or ""): row.get("channels")
            for row in rows
            if isinstance(row, dict)
        },
    })


def remember_irrigation_control_surface(payload: dict[str, object]) -> bool:
    """Store this payload's control surface, reporting whether it moved.

    Both the worker and the Start/Stop endpoint record here, under the same
    lock that serializes their database access. The endpoint ignores the
    answer -- its own response already published the change -- but it must
    still record, or the worker would find the surface moved a second later
    and rebuild the irrigation page underneath the person who just pressed
    the toggle.
    """
    global LAST_IRRIGATION_CONTROL_SURFACE

    surface = irrigation_control_surface(payload)
    with CONTROL_SURFACE_LOCK:
        previous = LAST_IRRIGATION_CONTROL_SURFACE
        LAST_IRRIGATION_CONTROL_SURFACE = surface
    # The first call has nothing to compare against, and announcing a change
    # then would rebuild every open page on each backend restart.
    return previous is not None and previous != surface


def irrigation_control_worker() -> None:
    next_cycle_at = 0.0
    latest_irrigation: dict[str, object] | None = None
    while True:
        remaining = next_cycle_at - time.monotonic()
        if remaining > 0:
            # Sensor bursts set the trigger several times per second. Coalesce
            # them so automatic irrigation stays responsive without pinning a
            # Pi CPU core rebuilding the same state continuously.
            time.sleep(remaining)
        try:
            with IRRIGATION_STATE_TRANSITION_LOCK:
                with connect_database() as connection:
                    previous = build_irrigation_payload(connection)
                    updated = reconcile_irrigation_state(connection)
                # This is the parameter-derived final state. Wake MQTT again;
                # the earlier browser command may only have been able to clear
                # the old Manual state, not decide whether Automatic is needed.
                cache_and_trigger_relay_publish(updated)
                latest_irrigation = updated
                # Recorded unconditionally, and inside the lock so a Start
                # committing right now cannot land between the read and the
                # record: the surface has to keep moving with the state even
                # on cycles that publish for the other reason, or the next
                # cycle reports the same change all over again.
                arrived_externally = remember_irrigation_control_surface(updated)
            reconciled = json_dumps_compact(previous) != json_dumps_compact(updated)
            if reconciled or arrived_externally:
                publish_realtime_change(
                    {"irrigation", "notifications"},
                    source_path="irrigation-control-worker",
                )
        except Exception:
            # The next control cycle retries; API requests continue to report their own errors.
            pass
        next_cycle_at = time.monotonic() + IRRIGATION_CONTROL_MIN_CYCLE_SECONDS
        # A timed run ending before the next ordinary sweep decides when this
        # one happens, so the relay closes when it was told to rather than
        # whenever the sweep next comes round. Nothing running means nothing to
        # be early for, and the usual interval applies.
        timeout = IRRIGATION_CONTROL_INTERVAL_SECONDS
        try:
            with connect_database() as connection:
                deadline = seconds_until_next_irrigation_deadline(connection)
        except Exception:
            deadline = None
        if deadline is not None:
            timeout = min(timeout, max(IRRIGATION_CONTROL_MIN_CYCLE_SECONDS, deadline))
        # Likewise a schedule window about to open, so the line starts on the
        # minute it was set for rather than on whichever pass comes next.
        if latest_irrigation is not None:
            try:
                schedule_start = seconds_until_next_schedule_start(
                    [row for row in latest_irrigation.get("rows") or [] if isinstance(row, dict)],
                    normalize_irrigation_row_map(latest_irrigation.get("scheduleArmedRows")),
                )
            except Exception:
                schedule_start = None
            if schedule_start is not None:
                timeout = min(timeout, max(IRRIGATION_CONTROL_MIN_CYCLE_SECONDS, schedule_start))
        IRRIGATION_CONTROL_TRIGGER.wait(timeout=timeout)
        IRRIGATION_CONTROL_TRIGGER.clear()


def enforce_actuator_safety_cuts(safety: dict) -> list[str]:
    """Deliberately does nothing: a manual On is the operator's to make.

    This used to write the mode back to Automatic whenever a reading passed the
    crops' limit. Two things were wrong with that. The person who pressed On is
    the one who can see the greenhouse, and the reading that triggers the cut is
    a single shared DHT22 -- so one sensor reading slightly high took a relay
    away from the whole farm with no way to override it. The limit is still
    computed and still shown on the card before the press, which is where a
    warning belongs.

    Kept as a function, returning nothing, so the control cycle's call site and
    the notification path around it stay as they are.
    """
    return []

def refresh_environment_control_state() -> dict[str, object]:
    """Refresh fan, grow light, and sensor relay state outside irrigation control."""
    with connect_database() as connection:
        # Before the registry is read, so a run that has just ended is off in
        # the snapshot this cycle publishes rather than staying on for one
        # more pass.
        expire_due_misting_run(connection)
        cultivations = list_cultivations(connection)
        registry_rows = list_sensor_registry(connection)
        latest_readings = latest_sensor_readings_by_key(connection)

    sensor_registry = {
        str(row["sensor_key"]).strip(): row
        for row in registry_rows
    }
    # Everything below reads the greenhouse DHT22 through reading_metric_value,
    # so the fit has to be in force for all of it -- the safety check, the
    # automatic rules and the snapshot that goes out. Scoping it here rather
    # than at the fetch is deliberate: the readings are consumed well outside
    # the database block, and a fit that ended with the connection would leave
    # the rules running on raw values while the cards showed fitted ones.
    with bench_fit_scope(cultivations):
        return _environment_control_state(
            cultivations, registry_rows, latest_readings, sensor_registry
        )


def _environment_control_state(
    cultivations, registry_rows, latest_readings, sensor_registry
) -> dict[str, object]:
    # Only this cycle records the trend and moves the fan and lamp's modelled
    # effect on the air, from what the relays did since the last pass. First,
    # so the safety limits, the rules and the alerts below all read the house
    # as the cards show it.
    record_climate_sample(latest_readings)
    trend = climate_trend_per_minute()
    advance_greenhouse_response(cultivations, latest_readings, trend=trend)
    climate = greenhouse_climate_values(latest_readings, live=True)
    # The cards as the dashboards show them, eased here once for every screen.
    card_target = greenhouse_climate_values(
        latest_readings, bounds=greenhouse_climate_bounds(cultivations)
    )
    shown = greenhouse_display_step(
        card_target, fresh=irrigation_sensor_reading_is_fresh(latest_readings.get("dht22"))
    )
    write_greenhouse_response_snapshot(climate, shown=shown)
    card_readings = greenhouse_card_readings(latest_readings, climate)
    safety = actuator_safety_status(cultivations, card_readings)

    # An actuator held On past the limit its crops can take is stopped here,
    # every cycle, whoever switched it on and from whichever device. Doing it
    # at the point the relay state is decided is what makes the guarantee hold
    # while nobody is watching the screen: the browser may be closed, asleep,
    # or on the other side of a dead uplink, and the cut still happens.
    cut_actuators = enforce_actuator_safety_cuts(safety)

    cache_relay_actuator_modes(
        {
            key: actuator_control_state(sensor_registry, key)
            for key in RELAY_BACKED_ACTUATOR_KEYS
        }
    )
    cache_relay_sensor_power(hardware_sensor_power_states(sensor_registry))
    light_limit = advance_grow_light_limit(latest_readings)
    guidance = automatic_actuator_guidance(
        cultivations,
        latest_readings,
        running=dict(AUTOMATIC_ACTUATOR_RUNNING),
        climate=climate,
        light_limit=light_limit,
    )
    guidance["safety"] = safety
    # Only this cycle decides the relays, so only it records what they are
    # running for. The dashboards read it; they never write it.
    AUTOMATIC_ACTUATOR_RUNNING.update(
        {
            "fanHumidity": bool(guidance["fan"].get("tooHumid")),
            "fanHeat": bool(guidance["fan"].get("tooHot")),
            "lightCold": bool(guidance["light"].get("tooCold")),
        }
    )
    if cut_actuators:
        # The registry changed underneath the read above, so re-read what the
        # dashboards are about to be told rather than publishing the pre-cut
        # modes and correcting them a cycle later.
        with connect_database() as connection:
            registry_rows = list_sensor_registry(connection)
        sensor_registry = {
            str(row["sensor_key"]).strip(): row
            for row in registry_rows
        }
        cache_relay_actuator_modes(
            {
                key: actuator_control_state(sensor_registry, key)
                for key in RELAY_BACKED_ACTUATOR_KEYS
            }
        )
    announced = announce_greenhouse_venting(guidance)
    # Crop parameters are judged on the same cycle as the actuators, from the
    # same readings. Doing it here rather than at ingest means one evaluation
    # per cycle instead of one per sensor publish, and it keeps the alert
    # arriving on a farm whose boards have gone quiet mid-condition.
    announced_readings = announce_reading_alerts(
        evaluate_reading_alerts(cultivations, card_readings, sensor_registry)
    )
    if (
        remember_environment_control_surface(registry_rows)
        or announced
        or announced_readings
        or cut_actuators
    ):
        # Same reasoning as the irrigation worker: a fan, grow light, or sensor
        # power switch flipped on another device reaches this database through
        # the edge sync daemon, which is a separate process and cannot bump
        # this one's realtime version map.
        publish_realtime_change(
            {"sensors", "notifications"}
            if (announced or announced_readings or cut_actuators)
            else {"sensors"},
            source_path="environment-control-worker",
        )
    desired = cache_relay_automatic_states(
        {key: bool(guidance[key]["on"]) for key in AUTOMATIC_ACTUATOR_KEYS}
    )
    # Sensor and crop-parameter changes can alter fan/light automation without
    # any button press, so they need the same event-driven MQTT wake-up.
    trigger_local_relay_publish()
    return desired


def announce_greenhouse_venting(guidance: dict[str, dict[str, object]]) -> bool:
    """Log the alert once when the house needs opening, and once when it stops.

    Nothing in here can cool the greenhouse -- the fan moves humidity, the
    grow light only adds heat -- so above the crop's ceiling the remedy is a
    person. That
    makes this the one automatic condition that has to reach someone rather
    than a relay, which is why it is written to the notification history and
    not only drawn on a card someone may not be looking at.

    Edge-triggered on the reason, so a house that stays humid all afternoon is
    one entry. A changed reason (humidity, then heat as well) is a new one,
    because the advice on screen changed with it.
    """
    global LAST_GREENHOUSE_VENT_REASON

    greenhouse = guidance.get("greenhouse") or {}
    if not bool(greenhouse.get("readingFresh")):
        # A silent board is not evidence the house is fine, and not evidence it
        # is not. Hold the last state rather than announcing either way.
        return False

    reason = str(greenhouse.get("reason") or "")
    with CONTROL_SURFACE_LOCK:
        previous = LAST_GREENHOUSE_VENT_REASON
        LAST_GREENHOUSE_VENT_REASON = reason
    if previous is None or previous == reason:
        return False

    if reason:
        message = greenhouse_vent_message(greenhouse)
        # Critical, not warning. This now only fires once the house is past the
        # fan's own trigger by a further margin -- the fan has been running and
        # has not brought it back -- so it is the case where a person really
        # does have to go and open the greenhouse. It used to fire the moment
        # the fan started, which is why it read as a warning.
        notification_type = "critical"
    else:
        message = "Greenhouse conditions are back inside the crop range. It can be closed again."
        notification_type = "success"
    try:
        with connect_database() as connection:
            create_notification_record(
                connection,
                scope="all",
                type=notification_type,
                message=message,
                source_type="greenhouse",
                source_id="ventilation",
            )
    except Exception:
        # The card on screen is the primary signal; a failed history write must
        # not take the control worker down with it.
        return False
    return True


def greenhouse_vent_message(greenhouse: dict[str, object]) -> str:
    """One sentence naming what is out of range and by how much."""
    reason = str(greenhouse.get("reason") or "")
    humidity = greenhouse.get("humidity")
    temperature = greenhouse.get("temperature")
    humidity_ceiling = greenhouse.get("humidityCeiling")
    temperature_ceiling = greenhouse.get("temperatureCeiling")
    affected_rows = greenhouse.get("affectedRows")
    row_labels = [
        str(row.get("label") or "").strip()
        for row in affected_rows
        if isinstance(row, dict) and str(row.get("label") or "").strip()
    ] if isinstance(affected_rows, list) else []
    if bool(greenhouse.get("allRowsAffected")) or not row_labels:
        affected_label = "All Rows"
    elif len(row_labels) == 1:
        affected_label = row_labels[0]
    elif len(row_labels) == 2:
        affected_label = f"{row_labels[0]} and {row_labels[1]}"
    else:
        affected_label = f"{', '.join(row_labels[:-1])}, and {row_labels[-1]}"
    if reason == "both":
        return (
            f"Open the greenhouse for {affected_label}: humidity is {humidity}% against a {humidity_ceiling}% ceiling"
            f" and it is {temperature} C against {temperature_ceiling} C."
        )
    if reason == "temperature":
        return (
            f"Open the greenhouse for {affected_label}: it is {temperature} C, above the {temperature_ceiling} C"
            " ceiling set for the crop, and nothing here can cool it."
        )
    return (
        f"Open the greenhouse for {affected_label}: humidity is {humidity}%, above the"
        f" {humidity_ceiling}% ceiling. The shared exhaust fan is running for every affected row."
    )


# Every crop parameter an operator sets, and where its reading comes from.
#
# The notification history used to carry only actuator presses and the vent
# alert, so the one thing the bell never said was that a crop was actually out
# of range -- the numbers were on the dashboard, and only for whoever happened
# to be looking at it. These rules give each parameter the same standing as a
# button press: a named row, a named reading, and an entry in history that the
# period report picks up.
#
# "sensor" is the registry suffix under a row key ("row2-moisture"), except for
# the two greenhouse-wide readings, which have no row of their own and are read
# from the shared DHT22. "metric" is the key inside that sensor's stored
# payload; "parameter" is the key inside the crop's parameters_json.
READING_ALERT_RULES = (
    {
        "parameter": "moisture",
        "label": "soil moisture",
        "sensor": "moisture",
        "metric": "moisture",
        "unit": "%",
        "shared": False,
        "criticalMargin": 15.0,
        "low": "low",
        "high": "high",
    },
    {
        "parameter": "ec",
        # The operator's word for EC on this farm. "Soil EC" alone reads as an
        # instrument name; what it tells them is whether the row is fed.
        "label": "soil EC (nutrients)",
        "sensor": "rs485",
        "metric": "ec",
        "unit": "mS/cm",
        "shared": False,
        "criticalMargin": 0.6,
        "low": "low",
        "high": "high",
    },
    {
        "parameter": "ph",
        "label": "soil pH",
        "sensor": "rs485",
        "metric": "ph",
        "unit": "pH",
        "shared": False,
        "criticalMargin": 0.8,
        # pH is the one reading where neither direction is the normal one, so
        # it is named for what it is rather than for the number.
        "low": "too acidic",
        "high": "too alkaline",
    },
    {
        "parameter": "temp",
        "label": "temperature",
        "sensor": "dht22",
        "metric": "temp",
        "unit": "\u00b0C",
        "shared": True,
        "criticalMargin": 4.0,
        "low": "low",
        "high": "high",
    },
    {
        "parameter": "humidity",
        "label": "humidity",
        "sensor": "dht22",
        "metric": "humidity",
        "unit": "%",
        "shared": True,
        "criticalMargin": 15.0,
        "low": "low",
        "high": "high",
    },
)


def reading_alert_sensor_key(rule: dict[str, object], row_key: str) -> str:
    """Which registry row holds this rule's reading for this planting row."""
    return str(rule["sensor"]) if bool(rule["shared"]) else f"{row_key}-{rule['sensor']}"


def format_reading_alert_value(value: float, unit: str) -> str:
    """A reading with its unit, spaced the way the unit is normally written."""
    if unit == "pH":
        # "6.40 pH" rather than "pH 6.40": every other reading here is
        # number-then-unit, and mixing the two orders reads as a typo.
        return f"{value:.2f} pH"
    # Percent sits tight against the number; degrees and mS/cm do not.
    separator = "" if unit == "%" else " "
    return f"{value:.1f}{separator}{unit}"


def evaluate_reading_alerts(
    cultivations: list[sqlite3.Row] | list[dict[str, object]],
    latest_readings: dict[str, sqlite3.Row] | dict[str, dict[str, object]],
    sensor_registry: dict[str, sqlite3.Row] | dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    """Which crop parameters are outside the range their own row asks for.

    One entry per planted row and parameter, keyed "row2:moisture". Only rows
    with an active cultivation are judged: a parameter range belongs to a
    planting, and an empty row has none to be outside of.

    Fail-closed in the same direction as the rest of the system. A powered-off
    sensor, a reading older than the irrigation freshness window, or a crop
    with no range saved for this parameter all yield no entry rather than a
    guess -- a silent board is not evidence a row is dry, and announcing that
    it is would send someone out to a row that is fine.
    """
    cultivation_by_row = active_cultivation_row_map(cultivations)
    states: dict[str, dict[str, object]] = {}

    for row_key in VALID_CULTIVATION_ROWS:
        cultivation = cultivation_by_row.get(row_key)
        if cultivation is None:
            continue
        for rule in READING_ALERT_RULES:
            parameter = str(rule["parameter"])
            metric_range = irrigation_parameter_range(cultivation, parameter)
            if metric_range is None:
                continue
            sensor_key = reading_alert_sensor_key(rule, row_key)
            if sensor_control_state(sensor_registry, sensor_key) != "on":
                continue
            reading = latest_readings.get(sensor_key)
            if not irrigation_sensor_reading_is_fresh(reading):
                continue
            value = reading_metric_value(reading, str(rule["metric"]))
            if value is None:
                continue

            minimum = float(metric_range["min"])
            maximum = float(metric_range["max"])
            # Warning and critical are separate directions on purpose, not two
            # severities of one. The edge-trigger below compares directions, so
            # a row drifting from warning-low into critical-low is a change and
            # is announced -- which is the moment worth telling someone about.
            margin = float(rule.get("criticalMargin") or 0.0)
            if value < minimum - margin:
                direction, limit = "critical-low", minimum
            elif value > maximum + margin:
                direction, limit = "critical-high", maximum
            elif value < minimum:
                direction, limit = "low", minimum
            elif value > maximum:
                direction, limit = "high", maximum
            else:
                direction, limit = "", 0.0

            states[f"{row_key}:{parameter}"] = {
                "rowKey": row_key,
                "rowLabel": cultivation_row_label(row_key),
                "parameter": parameter,
                "label": str(rule["label"]),
                "unit": str(rule["unit"]),
                "direction": direction,
                "value": round(value, 2),
                "limit": round(limit, 2),
                "min": round(minimum, 2),
                "max": round(maximum, 2),
                # "low"/"high" for both severities: the rules name the side,
                # not how far out it is, and pH's words ("too acidic") read the
                # same either way. The severity is carried by the direction.
                "word": str(rule[direction.replace("critical-", "")]) if direction else "",
                "critical": direction.startswith("critical-"),
            }
    return states


def reading_alert_message(entry: dict[str, object]) -> str:
    """One sentence naming the row, the reading, and the limit it crossed."""
    unit = str(entry["unit"])
    reading = format_reading_alert_value(float(entry["value"]), unit)
    limit = format_reading_alert_value(float(entry["limit"]), unit)
    word = str(entry["word"])
    # Compares the side, not the whole direction: "critical-low" is still low,
    # and matching on "low" alone would have called every critical reading a
    # maximum, including the ones below the floor.
    direction = str(entry["direction"])
    boundary = "minimum" if direction.endswith("low") else "maximum"
    # Trailing, not leading: the rules' words are not all adjectives -- pH says
    # "too acidic", and "Critically too acidic" is not a sentence. "(critical)"
    # after the phrase reads correctly whatever the word is.
    severity = " (critical)" if direction.startswith("critical-") else ""
    return (
        f"{entry['rowLabel']} {entry['label']} is {word}{severity}: {reading}, "
        f"against the {limit} {boundary} set for this crop."
    )


def reading_alert_cleared_message(entry: dict[str, object]) -> str:
    """The matching all-clear, so history shows how long a row was out."""
    unit = str(entry["unit"])
    reading = format_reading_alert_value(float(entry["value"]), unit)
    low = format_reading_alert_value(float(entry["min"]), unit)
    high = format_reading_alert_value(float(entry["max"]), unit)
    return (
        f"{entry['rowLabel']} {entry['label']} is back in range: {reading}, "
        f"within the {low} to {high} set for this crop."
    )


def announce_reading_alerts(states: dict[str, dict[str, object]]) -> bool:
    """Log a crop parameter going out of range, and log it coming back.

    Edge-triggered on the direction, exactly as the vent alert is. What is
    compared is the direction rather than the value, so a row holding steady
    at 40% against a 50% minimum is one entry until it recovers, and a row that
    swings from below the minimum to above the maximum gets a second entry --
    the reading is out either way, but the remedy is the opposite one.

    A key that disappears from `states` -- the sensor was switched off, the
    reading went stale, the row was harvested -- is forgotten without an
    all-clear. Nothing here knows whether that row recovered or simply stopped
    reporting, and "back in range" is a claim this cannot make on no evidence.
    """
    pending: list[tuple[str, str, str]] = []

    with CONTROL_SURFACE_LOCK:
        for key, entry in states.items():
            direction = str(entry["direction"])
            previous = LAST_READING_ALERT_STATES.get(key)
            if previous == direction:
                continue
            LAST_READING_ALERT_STATES[key] = direction
            # First sighting of this row and parameter since the process
            # started. An out-of-range row is announced: a restart must not
            # swallow a condition nobody has been told about. An in-range
            # first sighting is not news, so it only seeds the state.
            if previous is None and not direction:
                continue
            if direction.startswith("critical-"):
                pending.append((key, "critical", reading_alert_message(entry)))
            elif direction:
                # A warning is drawn on the card and left there. Only a reading
                # far enough out to be critical is worth a notification: this
                # farm has five metrics across four rows on one screen, and a
                # message for every crossing of every bound is a list nobody
                # reads by the time one of them matters.
                continue
            elif previous and previous.startswith("critical-"):
                # Only clear what was announced. A warning that resolves was
                # never sent, so an all-clear for it would arrive out of
                # nowhere.
                pending.append((key, "success", reading_alert_cleared_message(entry)))
        # Keys that stopped reporting are dropped rather than held, so a sensor
        # that comes back out of range is announced again instead of being
        # matched against a state from before it went quiet.
        for key in [key for key in LAST_READING_ALERT_STATES if key not in states]:
            del LAST_READING_ALERT_STATES[key]

    if not pending:
        return False

    try:
        with connect_database() as connection:
            for key, notification_type, message in pending:
                create_notification_record(
                    connection,
                    scope="all",
                    type=notification_type,
                    message=message,
                    source_type="reading",
                    source_id=key,
                )
    except Exception:
        # Same trade as the vent alert: the dashboard card is the primary
        # signal, and a failed history write must not take the control worker
        # down with it. The state map already moved, so this condition is not
        # retried -- re-announcing on every cycle while the database is
        # unreachable would flood history the moment it came back.
        return False
    return True


def remember_environment_control_surface(registry_rows: list[sqlite3.Row]) -> bool:
    """Store the registry's switch positions, reporting whether they moved.

    Only the three columns a person can set. display_name, the hardware
    identifier and the metric lists also live on these rows and are rewritten
    as boards are discovered, which is not a control change and must not
    rebuild every open page.

    As with the irrigation surface, the control endpoint records here too even
    though it never reads the answer -- otherwise the next worker cycle would
    find the switch moved and re-render the sensors page a second time.
    """
    global LAST_ENVIRONMENT_CONTROL_SURFACE

    surface = json_dumps_compact({
        str(row["sensor_key"]).strip(): [
            str(row["power_state"] or ""),
            str(row["actuator_mode"] or ""),
            str(row["alert_mode"] or ""),
        ]
        for row in registry_rows
    })
    with CONTROL_SURFACE_LOCK:
        previous = LAST_ENVIRONMENT_CONTROL_SURFACE
        LAST_ENVIRONMENT_CONTROL_SURFACE = surface
    return previous is not None and previous != surface


def environment_control_worker() -> None:
    next_cycle_at = 0.0
    while True:
        remaining = next_cycle_at - time.monotonic()
        if remaining > 0:
            # Coalesce a burst from the four sensor nodes while keeping the
            # worst-case automatic response below one sensor publish interval.
            time.sleep(remaining)
        try:
            refresh_environment_control_state()
        except Exception:
            # Keep the last local relay snapshot and retry next cycle.
            pass
        next_cycle_at = time.monotonic() + ENVIRONMENT_CONTROL_MIN_CYCLE_SECONDS
        # A misting run ending before the next ordinary sweep decides when this
        # one happens. Without it a five second mist waits for the ten second
        # interval and runs for fifteen -- and a short mist is exactly the case
        # someone sets a duration for.
        timeout = ENVIRONMENT_CONTROL_INTERVAL_SECONDS
        try:
            with connect_database() as connection:
                deadline = seconds_until_misting_deadline(connection)
        except Exception:
            deadline = None
        if deadline is not None:
            timeout = min(timeout, max(0.0, deadline))
        ENVIRONMENT_CONTROL_TRIGGER.wait(timeout=timeout)
        ENVIRONMENT_CONTROL_TRIGGER.clear()


def start_environment_control_worker() -> None:
    global ENVIRONMENT_CONTROL_WORKER
    with ENVIRONMENT_CONTROL_WORKER_LOCK:
        if ENVIRONMENT_CONTROL_WORKER is not None and ENVIRONMENT_CONTROL_WORKER.is_alive():
            return
        ENVIRONMENT_CONTROL_WORKER = threading.Thread(
            target=environment_control_worker,
            name="fan-light-sensor-controller",
            daemon=True,
        )
        ENVIRONMENT_CONTROL_WORKER.start()


def start_irrigation_control_worker() -> None:
    global IRRIGATION_CONTROL_WORKER
    with IRRIGATION_CONTROL_WORKER_LOCK:
        if IRRIGATION_CONTROL_WORKER is not None and IRRIGATION_CONTROL_WORKER.is_alive():
            return
        IRRIGATION_CONTROL_WORKER = threading.Thread(
            target=irrigation_control_worker,
            name="irrigation-row-controller",
            daemon=True,
        )
        IRRIGATION_CONTROL_WORKER.start()








def smtp_settings() -> dict[str, object]:
    host = os.getenv("ICUCROPS_SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("ICUCROPS_SMTP_PORT", "587"))
    username = os.getenv("ICUCROPS_SMTP_USERNAME", "").strip()
    password = os.getenv("ICUCROPS_SMTP_PASSWORD", "").strip()
    sender = os.getenv("ICUCROPS_SMTP_FROM", username).strip()

    if not username or not password or not sender:
        raise MailConfigurationError(
            "Gmail SMTP is not configured. Set ICUCROPS_SMTP_USERNAME, "
            "ICUCROPS_SMTP_PASSWORD, and ICUCROPS_SMTP_FROM in your environment or .env file."
        )

    if (
        username.lower() in PLACEHOLDER_SMTP_VALUES
        or password in PLACEHOLDER_SMTP_VALUES
        or sender.lower() in PLACEHOLDER_SMTP_VALUES
    ):
        raise MailConfigurationError(
            "Gmail SMTP is still using placeholder values. Replace ICUCROPS_SMTP_USERNAME, "
            "ICUCROPS_SMTP_PASSWORD, and ICUCROPS_SMTP_FROM with a real sender Gmail account "
            "and a 16-character Google App Password."
        )

    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "sender": sender,
    }


def smtp_is_configured() -> bool:
    try:
        smtp_settings()
    except MailConfigurationError:
        return False
    return True


def brevo_settings() -> dict[str, str]:
    api_key = os.getenv("ICUCROPS_BREVO_API_KEY", "").strip()
    sender_value = os.getenv(
        "ICUCROPS_BREVO_FROM",
        os.getenv("ICUCROPS_SMTP_FROM", os.getenv("ICUCROPS_SMTP_USERNAME", "")),
    ).strip()
    sender_name = os.getenv("ICUCROPS_BREVO_FROM_NAME", "ICuCrops Security").strip() or "ICuCrops Security"
    _, sender_email = parseaddr(sender_value)
    sender_email = normalize_email(sender_email or sender_value)

    if not api_key or not sender_email:
        raise MailConfigurationError(
            "HTTPS email delivery is not configured. Set ICUCROPS_BREVO_API_KEY and "
            "ICUCROPS_BREVO_FROM in the host environment."
        )

    return {
        "api_key": api_key,
        "sender_email": sender_email,
        "sender_name": sender_name,
    }


def brevo_is_configured() -> bool:
    try:
        brevo_settings()
    except MailConfigurationError:
        return False
    return True


def email_delivery_provider() -> str:
    configured = os.getenv("ICUCROPS_EMAIL_PROVIDER", "auto").strip().lower() or "auto"
    if configured not in {"auto", "brevo", "smtp"}:
        raise MailConfigurationError(
            "ICUCROPS_EMAIL_PROVIDER must be auto, brevo, or smtp."
        )

    if configured == "brevo":
        brevo_settings()
        return "brevo"

    if configured == "smtp":
        smtp_settings()
        return "smtp"

    if brevo_is_configured():
        return "brevo"

    if running_on_managed_host():
        raise MailConfigurationError(
            "OTP email delivery on a managed host requires ICUCROPS_BREVO_API_KEY "
            "and ICUCROPS_BREVO_FROM. Managed hosts block Gmail SMTP ports."
        )

    smtp_settings()
    return "smtp"


def email_delivery_is_configured() -> bool:
    try:
        email_delivery_provider()
    except MailConfigurationError:
        return False
    return True


def verify_smtp_login() -> None:
    config = smtp_settings()
    context = ssl.create_default_context()
    host = str(config["host"])
    port = int(config["port"])
    username = str(config["username"])
    password = str(config["password"])

    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as client:
            client.login(username, password)
        return

    with smtplib.SMTP(host, port, timeout=20) as client:
        client.ehlo()
        client.starttls(context=context)
        client.ehlo()
        client.login(username, password)


def send_email_via_brevo(message: EmailMessage) -> None:
    config = brevo_settings()
    recipient_name, recipient_email = parseaddr(str(message.get("To") or ""))
    recipient_email = normalize_email(recipient_email)
    if not recipient_email:
        raise OSError("OTP email recipient is invalid.")

    # The OTP messages address the recipient by bare email, so `parseaddr` hands
    # back an empty name. Brevo rejects the whole send with
    # "name is missing in to" when the key is present but blank, so the key only
    # travels when there is a real name behind it.
    recipient_entry: dict[str, str] = {"email": recipient_email}
    if recipient_name.strip():
        recipient_entry["name"] = recipient_name.strip()

    plain_part = message.get_body(preferencelist=("plain",))
    text_content = plain_part.get_content() if plain_part is not None else message.get_content()
    payload = {
        "sender": {
            "email": config["sender_email"],
            "name": config["sender_name"],
        },
        "to": [recipient_entry],
        "subject": str(message.get("Subject") or "ICuCrops Security Code"),
        "textContent": str(text_content),
    }
    request = Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "api-key": config["api_key"],
        },
        method="POST",
    )

    # An OTP is useful only for a few minutes, so Brevo delivery stays
    # synchronous. Brief API throttling, a cold network path, or a provider 5xx
    # should not make account creation depend on the first packet succeeding,
    # though. Retrying the *same* OTP is safe even if the first response was
    # lost after acceptance: at worst the recipient sees the same code twice.
    # 402 is Brevo's "out of sending credits". It is not worth retrying inside
    # one request -- the credit does not come back in 1.5 seconds -- so it is
    # deliberately absent here and is reported to the operator instead.
    transient_statuses = {408, 425, 429, 500, 502, 503, 504}
    max_attempts = max(
        1,
        min(4, configured_int("ICUCROPS_BREVO_SEND_ATTEMPTS", 3)),
    )

    for attempt in range(max_attempts):
        try:
            with urlopen(request, timeout=12) as response:  # nosec B310 - URL is fixed/localhost/Brevo or operator config, never attacker-controlled
                status = int(getattr(response, "status", HTTPStatus.CREATED))
                response.read()
            if 200 <= status < 300:
                return
            if status not in transient_statuses or attempt + 1 >= max_attempts:
                raise OSError(f"HTTPS email provider returned HTTP {status}.")
        except HTTPError as error:
            # The provider explains permanent rejections in the response body.
            # Keep that reason in the host log while the browser receives only
            # the generic delivery error.
            try:
                reason = error.read().decode("utf-8", "replace").strip()
            except OSError:
                reason = ""
            if int(error.code) not in transient_statuses or attempt + 1 >= max_attempts:
                suffix = f": {reason[:300]}" if reason else ""
                raise OSError(
                    f"HTTPS email provider rejected the request (HTTP {error.code}){suffix}"
                ) from error
        except (URLError, TimeoutError, ConnectionError) as error:
            if attempt + 1 >= max_attempts:
                raise OSError("HTTPS email provider could not be reached after retrying.") from error

        # Short and bounded: three default attempts add at most 1.5 seconds of
        # backoff, comfortably inside the serverless and browser OTP budgets.
        time.sleep(0.5 * (2 ** attempt))


def send_email_message(message: EmailMessage) -> None:
    if email_delivery_provider() == "brevo":
        send_email_via_brevo(message)
        return

    config = smtp_settings()
    context = ssl.create_default_context()
    host = str(config["host"])
    port = int(config["port"])
    username = str(config["username"])
    password = str(config["password"])

    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as client:
            client.login(username, password)
            client.send_message(message)
        return

    with smtplib.SMTP(host, port, timeout=20) as client:
        client.ehlo()
        client.starttls(context=context)
        client.ehlo()
        client.login(username, password)
        client.send_message(message)


def smtp_auth_failure_payload(error: smtplib.SMTPAuthenticationError) -> dict[str, str]:
    return {
        "message": (
            "Gmail SMTP login failed. Use a real Gmail address for ICUCROPS_SMTP_USERNAME "
            "and a 16-character Google App Password for ICUCROPS_SMTP_PASSWORD."
        ),
        "detail": str(error),
    }


def insecure_otp_fallback_enabled() -> bool:
    # The fallback prints the one-time code straight into the HTTP response for
    # local testing. On a managed, internet-facing host that is an OTP hand-out
    # anyone can read off the wire, so it is refused there no matter how the
    # environment is set -- a misconfigured ICUCROPS_DEV_OTP_FALLBACK can never
    # turn the public site into an OTP oracle. It stays available on the Pi and
    # desktop, where the response is only ever seen locally.
    if running_on_managed_host():
        return False
    configured = os.getenv("ICUCROPS_DEV_OTP_FALLBACK", "").strip().lower()
    if configured in {"1", "true", "yes", "on"}:
        return True
    return False


def otp_delivery_payload(
    *,
    challenge_id: str,
    email: str,
    expires_at: str,
    otp_code: str,
    success_message: str,
    use_screen_fallback: bool = False,
    fallback_message: str = "",
    delivery_mode: str = "email",
) -> dict[str, object]:
    if use_screen_fallback:
        print(f"Local OTP fallback for {email}: {otp_code}", flush=True)
        return {
            "message": fallback_message or f"Email delivery is not available right now. For local testing, use this OTP: {otp_code}",
            "challengeId": challenge_id,
            "maskedEmail": mask_email(email),
            "expiresAt": expires_at,
            "deliveryMode": "screen",
            "devOtpCode": otp_code,
        }

    return {
        "message": success_message,
        "challengeId": challenge_id,
        "maskedEmail": mask_email(email),
        "expiresAt": expires_at,
        "deliveryMode": delivery_mode,
    }


def send_password_reset_otp_email(*, recipient: str, display_name: str, otp_code: str, expires_at: str) -> None:
    sender = (
        os.getenv("ICUCROPS_BREVO_FROM", "").strip()
        or os.getenv("ICUCROPS_SMTP_FROM", "").strip()
        or os.getenv("ICUCROPS_SMTP_USERNAME", "").strip()
    )
    expiry = parse_iso_datetime(expires_at).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    greeting_name = display_name.strip() or "Farmer"

    message = EmailMessage()
    message["Subject"] = "ICuCrops Password Reset OTP"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "\n".join(
            [
                f"Hello {greeting_name},",
                "",
                f"Your ICuCrops password reset OTP is: {otp_code}",
                f"This code expires on {expiry}.",
                "",
                "If you did not request a password reset, you can ignore this email.",
                "",
                "ICuCrops Security",
            ]
        )
    )

    send_email_message(message)


def send_account_creation_otp_email(*, recipient: str, display_name: str, otp_code: str, expires_at: str) -> None:
    sender = (
        os.getenv("ICUCROPS_BREVO_FROM", "").strip()
        or os.getenv("ICUCROPS_SMTP_FROM", "").strip()
        or os.getenv("ICUCROPS_SMTP_USERNAME", "").strip()
    )
    expiry = parse_iso_datetime(expires_at).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    greeting_name = display_name.strip() or "Farmer"

    message = EmailMessage()
    message["Subject"] = "ICuCrops Account Verification OTP"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "\n".join(
            [
                f"Hello {greeting_name},",
                "",
                f"Your ICuCrops account verification OTP is: {otp_code}",
                f"This code expires on {expiry}.",
                "",
                "Use this code to finish creating your ICuCrops account.",
                "",
                "ICuCrops Security",
            ]
        )
    )

    send_email_message(message)


def otp_email_relay_worker_enabled() -> bool:
    configured = os.getenv("ICUCROPS_OTP_RELAY_WORKER", "").strip().lower()
    if configured in {"1", "true", "yes", "on"}:
        return True
    if configured in {"0", "false", "no", "off"}:
        return False
    return server_is_raspberry_pi()




def otp_email_relay_is_online() -> bool:
    """Always False: the relay announced itself through Firebase.

    The Pi used to publish an SMTP heartbeat that a managed host read before
    handing it an OTP to send. With that channel gone the hosted deployment
    sends its own mail (Brevo), and the Pi sends its own over SMTP.
    """
    return False




def send_or_enqueue_otp_email(
    *,
    challenge_id: str,
    purpose: str,
    recipient: str,
    display_name: str,
    otp_code: str,
    expires_at: str,
) -> str:
    try:
        if purpose == "account-creation":
            send_account_creation_otp_email(
                recipient=recipient,
                display_name=display_name,
                otp_code=otp_code,
                expires_at=expires_at,
            )
        else:
            send_password_reset_otp_email(
                recipient=recipient,
                display_name=display_name,
                otp_code=otp_code,
                expires_at=expires_at,
            )
        return "email"
    except (MailConfigurationError, OSError, smtplib.SMTPException) as error:
        # The host log keeps the provider's full explanation.
        print(f"OTP email delivery failed for {purpose}: {error}", file=sys.stderr, flush=True)
        # "Try again shortly" is a dead end when trying again cannot help: an
        # exhausted sending quota or an unverified sender stays broken until an
        # operator acts, and the admin creating the account has no way to read
        # the host log. Name those two so the message says what to do, while
        # everything else stays generic and reveals no credential detail.
        raise MailConfigurationError(
            otp_delivery_failure_message(error)
        ) from error


def otp_delivery_failure_message(error: BaseException) -> str:
    """Turn a delivery failure into something the operator can act on."""
    detail = str(error)
    if "HTTP 402" in detail:
        return (
            "OTP email could not be sent: the email provider is out of sending "
            "credits. Top up the provider plan, then try again."
        )
    # Brevo reports an unverified or unauthorised sender as 401/403.
    if "HTTP 401" in detail or "HTTP 403" in detail:
        return (
            "OTP email could not be sent: the email provider rejected the "
            "sender account. Check the provider API key and verified sender."
        )
    return "OTP email service is temporarily unavailable. Please try again shortly."








def email_delivery_status_payload() -> dict[str, object]:
    try:
        provider = email_delivery_provider()
    except MailConfigurationError:
        return {
            "emailDeliveryConfigured": False,
            "emailDeliveryProvider": "unavailable",
            "otpRelayOnline": False,
            "otpDeliveryIndependentOfPi": False,
        }
    return {
        "emailDeliveryConfigured": True,
        "emailDeliveryProvider": provider,
        "otpRelayOnline": otp_email_relay_is_online(),
        "otpDeliveryIndependentOfPi": provider == "brevo",
    }


def parse_flask_json_body() -> dict[str, object]:
    try:
        payload = flask_request.get_json(silent=False)
    except BadRequest as error:
        raise ValueError("Request body must be valid JSON.") from error

    if payload is None:
        return {}

    if not isinstance(payload, dict):
        raise ValueError("JSON request body must be an object.")

    return payload


def flask_json_response(status: HTTPStatus, payload: dict[str, object]):
    response = jsonify(payload)
    response.status_code = int(status)
    return response




def login_user(payload: dict[str, object], *, client_address: str = "") -> tuple[HTTPStatus, dict[str, object]]:
    email = normalize_email(payload.get("email"))
    password = str(payload.get("password") or "")
    raw_requested_role = str(payload.get("role") or "").strip().lower()
    requested_role = raw_requested_role if raw_requested_role in {"admin", "user"} else ""



    return _login_user_via_sqlite(
        email=email,
        password=password,
        requested_role=requested_role,
        client_address=client_address,
    )


def local_login_credentials_match(email: str, password: str, requested_role: str = "") -> bool:
    if not email or not password or not is_valid_gmail_address(email):
        return False
    with connect_database() as connection:
        user = find_user_by_email(connection, email)
    if not user or int(user["is_active"] or 0) != 1:
        return False
    if requested_role and normalize_role(user["role"]) != requested_role:
        return False
    return verify_secret(
        password,
        salt=str(user["password_salt"]),
        digest=str(user["password_hash"]),
        iterations=int(user["password_iterations"]),
    )




def login_lock_payload_for_scope(scope_key: str) -> dict[str, object] | None:
    with connect_database() as connection:
        return get_admin_login_lock(connection, scope_key)


def register_login_failure_for_scope(scope_key: str, failure_message: str) -> dict[str, object]:
    with connect_database() as connection:
        return register_admin_login_failure(connection, scope_key, failure_message)


def clear_login_attempts_for_scope(scope_key: str) -> None:
    with connect_database() as connection:
        clear_admin_login_attempts(connection, scope_key)




def _login_user_via_sqlite(
    *,
    email: str,
    password: str,
    requested_role: str,
    client_address: str = "",
) -> tuple[HTTPStatus, dict[str, object]]:
    with connect_database() as connection:
        user = find_user_by_email(connection, email) if email and is_valid_gmail_address(email) else None
        # Every login attempt is rate-limited, not just administrator accounts —
        # a regular "user" account is otherwise open to unlimited password guessing.
        enforce_admin_lock = True
        scope_key = admin_login_scope_key(client_address) if enforce_admin_lock else ""
        account_scope_key = admin_login_account_scope_key(email) if enforce_admin_lock else ""
        if enforce_admin_lock:
            active_lock = get_admin_login_lock(connection, scope_key)
            if not active_lock and account_scope_key:
                active_lock = get_admin_login_lock(connection, account_scope_key)
            if active_lock:
                return HTTPStatus.TOO_MANY_REQUESTS, active_lock

        if not email or not password:
            if not enforce_admin_lock:
                return HTTPStatus.BAD_REQUEST, {"message": "Please enter your Gmail address and password."}
            failure_payload = register_login_failure_across_scopes(
                connection,
                scope_key,
                account_scope_key,
                "Please enter your Gmail address and password.",
            )
            status = HTTPStatus.TOO_MANY_REQUESTS if failure_payload["code"] == "ADMIN_LOGIN_LOCKED" else HTTPStatus.BAD_REQUEST
            return status, failure_payload

        if not is_valid_gmail_address(email):
            if not enforce_admin_lock:
                return HTTPStatus.BAD_REQUEST, {"message": "Use a valid Gmail address."}
            failure_payload = register_login_failure_across_scopes(
                connection,
                scope_key,
                account_scope_key,
                "Use a valid Gmail address.",
            )
            status = HTTPStatus.TOO_MANY_REQUESTS if failure_payload["code"] == "ADMIN_LOGIN_LOCKED" else HTTPStatus.BAD_REQUEST
            return status, failure_payload

        if not user or int(user["is_active"]) != 1:
            # Say which half is wrong: an unknown email is not a wrong password.
            # A deactivated account reads as unregistered too. The attempt
            # still counts toward the IP and account lockouts.
            missing_message = "This Gmail address is not registered."
            if not enforce_admin_lock:
                return HTTPStatus.UNAUTHORIZED, {"message": missing_message}
            failure_payload = register_login_failure_across_scopes(
                connection,
                scope_key,
                account_scope_key,
                missing_message,
                user_id=int(user["id"]) if user else None,
            )
            status = HTTPStatus.TOO_MANY_REQUESTS if failure_payload["code"] == "ADMIN_LOGIN_LOCKED" else HTTPStatus.UNAUTHORIZED
            return status, failure_payload
        if not verify_secret(
            password,
            salt=str(user["password_salt"]),
            digest=str(user["password_hash"]),
            iterations=int(user["password_iterations"]),
        ):
            if not enforce_admin_lock:
                return HTTPStatus.UNAUTHORIZED, {"message": "Incorrect password."}
            failure_payload = register_login_failure_across_scopes(
                connection,
                scope_key,
                account_scope_key,
                "Incorrect password.",
                user_id=int(user["id"]) if user else None,
            )
            status = HTTPStatus.TOO_MANY_REQUESTS if failure_payload["code"] == "ADMIN_LOGIN_LOCKED" else HTTPStatus.UNAUTHORIZED
            return status, failure_payload

        user_role = normalize_role(user["role"])
        if requested_role == "admin" and user_role != "admin":
            failure_payload = register_login_failure_across_scopes(
                connection,
                scope_key,
                account_scope_key,
                "This login form is for administrator accounts only.",
            )
            status = HTTPStatus.TOO_MANY_REQUESTS if failure_payload["code"] == "ADMIN_LOGIN_LOCKED" else HTTPStatus.FORBIDDEN
            return status, failure_payload

        if requested_role == "user" and user_role != "user":
            return HTTPStatus.FORBIDDEN, {"message": "This login form is for user accounts only."}

        if enforce_admin_lock:
            clear_admin_login_attempts(connection, scope_key)
            if account_scope_key:
                clear_admin_login_attempts(connection, account_scope_key)

    return HTTPStatus.OK, {
        "message": "Login successful.",
        "user": build_user_payload(user),
    }


def request_password_reset_otp(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    email = normalize_email(payload.get("email"))
    use_screen_fallback = False
    fallback_message = ""
    delivery_mode = "email"
    # The outer handlers below also catch failures raised *before* a challenge
    # exists -- opening the database is itself an OSError away from failing.
    # Without these, formatting the fallback message raised UnboundLocalError
    # and the caller got a bare HTTP 500 with no body instead of a reason.
    challenge_id = ""
    otp_code = ""
    expires_at = ""

    if not email:
        return HTTPStatus.BAD_REQUEST, {"message": "Please enter your Gmail address first."}

    if not is_valid_gmail_address(email):
        return HTTPStatus.BAD_REQUEST, {"message": "Use a valid Gmail address."}


    try:
        with connect_database() as connection:
            cleanup_stale_login_challenges(connection)
            throttle_payload = check_otp_request_throttle(connection, email, client_ip_address())
            if throttle_payload:
                return HTTPStatus.TOO_MANY_REQUESTS, throttle_payload
            user = find_user_by_email(connection, email)
            if not user or int(user["is_active"]) != 1:
                # Do not reveal whether the address is registered. Return the
                # same shape a real request produces -- a decoy challenge id
                # that can never verify -- and spend the same hashing work, so
                # neither the response nor its timing can enumerate accounts.
                burn_password_verification(iterations=OTP_ITERATIONS)
                return HTTPStatus.OK, otp_delivery_payload(
                    challenge_id=secrets.token_urlsafe(18),
                    email=email,
                    expires_at=(utc_now() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat(),
                    otp_code="",
                    success_message="OTP sent successfully.",
                    delivery_mode="email",
                )
            challenge_id, otp_code, expires_at = create_login_challenge(connection, user)
            try:
                delivery_mode = send_or_enqueue_otp_email(
                    challenge_id=challenge_id,
                    purpose="password-reset",
                    recipient=normalize_email(user["email"]),
                    display_name=str(user["display_name"]),
                    otp_code=otp_code,
                    expires_at=expires_at,
                )
            except smtplib.SMTPAuthenticationError as error:
                if not insecure_otp_fallback_enabled():
                    return HTTPStatus.BAD_GATEWAY, smtp_auth_failure_payload(error)
                use_screen_fallback = True
                fallback_message = f"Gmail SMTP login failed. For local testing, use this OTP: {otp_code}"
            except MailConfigurationError as error:
                if not insecure_otp_fallback_enabled():
                    return HTTPStatus.SERVICE_UNAVAILABLE, {"message": str(error)}
                use_screen_fallback = True
                fallback_message = f"Gmail SMTP is not configured yet. For local testing, use this OTP: {otp_code}"
            except (OSError, smtplib.SMTPException) as error:
                if not insecure_otp_fallback_enabled():
                    return HTTPStatus.BAD_GATEWAY, {
                        "message": "OTP email could not be sent right now. Please check the configured email delivery service.",
                        "detail": str(error),
                    }
                use_screen_fallback = True
                fallback_message = f"OTP email could not be sent right now. For local testing, use this OTP: {otp_code}"
    except MailConfigurationError as error:
        if not insecure_otp_fallback_enabled() or not otp_code:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"message": str(error)}
        use_screen_fallback = True
        fallback_message = f"Gmail SMTP is not configured yet. For local testing, use this OTP: {otp_code}"
    except smtplib.SMTPAuthenticationError as error:
        if not insecure_otp_fallback_enabled() or not otp_code:
            return HTTPStatus.BAD_GATEWAY, smtp_auth_failure_payload(error)
        use_screen_fallback = True
        fallback_message = f"Gmail SMTP login failed. For local testing, use this OTP: {otp_code}"
    except (OSError, smtplib.SMTPException) as error:
        if not insecure_otp_fallback_enabled() or not otp_code:
            return HTTPStatus.BAD_GATEWAY, {
                "message": "OTP email could not be sent right now. Please check the configured email delivery service.",
                "detail": str(error),
            }
        use_screen_fallback = True
        fallback_message = f"OTP email could not be sent right now. For local testing, use this OTP: {otp_code}"

    return HTTPStatus.OK, otp_delivery_payload(
        challenge_id=challenge_id,
        email=email,
        expires_at=expires_at,
        otp_code=otp_code,
        success_message="OTP sent successfully.",
        use_screen_fallback=use_screen_fallback,
        fallback_message=fallback_message,
        delivery_mode=delivery_mode,
    )


def verify_password_reset_otp(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    challenge_id = str(payload.get("challengeId") or "").strip()
    otp_code = "".join(character for character in str(payload.get("otp") or "") if character.isdigit())

    if not challenge_id:
        return HTTPStatus.BAD_REQUEST, {"message": "OTP session is missing."}

    if len(otp_code) != OTP_LENGTH:
        return HTTPStatus.BAD_REQUEST, {"message": "Enter the full 6-digit OTP first."}


    with connect_database() as connection:
        cleanup_stale_login_challenges(connection)
        success, result = verify_login_challenge(connection, challenge_id, otp_code, consume=False)

    if not success:
        return HTTPStatus.UNAUTHORIZED, result
    return HTTPStatus.OK, {
        "message": "OTP verified successfully.",
        "maskedEmail": mask_email(result["email"]),
    }


def reset_password(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    challenge_id = str(payload.get("challengeId") or "").strip()
    otp_code = "".join(character for character in str(payload.get("otp") or "") if character.isdigit())
    new_password = str(payload.get("newPassword") or "")
    confirm_password = str(payload.get("confirmPassword") or "")

    if not challenge_id:
        return HTTPStatus.BAD_REQUEST, {"message": "OTP session is missing."}

    if len(otp_code) != OTP_LENGTH:
        return HTTPStatus.BAD_REQUEST, {"message": "Enter the full 6-digit OTP first."}

    if not new_password or not confirm_password:
        return HTTPStatus.BAD_REQUEST, {"message": "Please enter and confirm your new password."}

    if new_password != confirm_password:
        return HTTPStatus.BAD_REQUEST, {"message": "Passwords do not match."}

    if not is_valid_password(new_password):
        return HTTPStatus.BAD_REQUEST, {"message": PASSWORD_POLICY_MESSAGE}


    with connect_database() as connection:
        cleanup_stale_login_challenges(connection)
        success, result = verify_login_challenge(connection, challenge_id, otp_code, consume=True)
        if not success:
            return HTTPStatus.UNAUTHORIZED, result
        timestamp = utc_now_iso()
        salt, digest = create_secret_hash(new_password, iterations=PASSWORD_ITERATIONS)
        connection.execute(
            """
            UPDATE users
            SET password_hash = ?, password_salt = ?, password_iterations = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                digest,
                salt,
                PASSWORD_ITERATIONS,
                timestamp,
                int(result["id"]),
            ),
        )

    return HTTPStatus.OK, {
        "message": "Password updated successfully. You can log in now.",
    }


def request_profile_password_change_otp(user_id: str, payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    current_password = str(payload.get("currentPassword") or "")
    new_password = str(payload.get("newPassword") or "")
    use_screen_fallback = False
    fallback_message = ""
    delivery_mode = "email"

    if not str(user_id).strip().isdigit():
        return HTTPStatus.BAD_REQUEST, {"message": "Logged-in account is missing."}

    if not current_password or not new_password:
        return HTTPStatus.BAD_REQUEST, {"message": "Please enter your current and new password."}

    if not is_valid_password(new_password):
        return HTTPStatus.BAD_REQUEST, {"message": PASSWORD_POLICY_MESSAGE}


    try:
        with connect_database() as connection:
            cleanup_stale_login_challenges(connection)
            user = find_user_by_id(connection, int(user_id))
            if not user or int(user["is_active"]) != 1:
                return HTTPStatus.NOT_FOUND, {"message": "Logged-in account was not found or is inactive."}

            # The current-password check is a password oracle sitting behind a
            # session. Without a limit a hijacked or left-open session could
            # brute-force the real password here -- burning a 310k-iteration
            # hash each try -- with none of the login lockout applying. Rate
            # limit it on its own scopes, mirroring the login flow.
            pw_ip_scope = f"pwchk-ip:{client_ip_address()}"
            pw_account_scope = f"pwchk-acct:{normalize_email(user['email'])}"
            active_lock = get_admin_login_lock(connection, pw_ip_scope) or get_admin_login_lock(
                connection, pw_account_scope
            )
            if active_lock:
                return HTTPStatus.TOO_MANY_REQUESTS, active_lock

            if not verify_secret(
                current_password,
                salt=str(user["password_salt"]),
                digest=str(user["password_hash"]),
                iterations=int(user["password_iterations"]),
            ):
                failure = register_login_failure_across_scopes(
                    connection,
                    pw_ip_scope,
                    pw_account_scope,
                    "Current password is incorrect.",
                    user_id=int(user["id"]),
                )
                status = (
                    HTTPStatus.TOO_MANY_REQUESTS
                    if failure.get("code") == "ADMIN_LOGIN_LOCKED"
                    else HTTPStatus.UNAUTHORIZED
                )
                return status, failure

            clear_admin_login_attempts(connection, pw_ip_scope)
            clear_admin_login_attempts(connection, pw_account_scope)

            challenge_id, otp_code, expires_at = create_login_challenge(connection, user)
            try:
                delivery_mode = send_or_enqueue_otp_email(
                    challenge_id=challenge_id,
                    purpose="password-reset",
                    recipient=normalize_email(user["email"]),
                    display_name=str(user["display_name"]),
                    otp_code=otp_code,
                    expires_at=expires_at,
                )
            except smtplib.SMTPAuthenticationError as error:
                if not insecure_otp_fallback_enabled():
                    return HTTPStatus.BAD_GATEWAY, smtp_auth_failure_payload(error)
                use_screen_fallback = True
                fallback_message = f"Gmail SMTP login failed. For local testing, use this OTP: {otp_code}"
            except MailConfigurationError as error:
                if not insecure_otp_fallback_enabled():
                    return HTTPStatus.SERVICE_UNAVAILABLE, {"message": str(error)}
                use_screen_fallback = True
                fallback_message = f"Gmail SMTP is not configured yet. For local testing, use this OTP: {otp_code}"
            except (OSError, smtplib.SMTPException) as error:
                if not insecure_otp_fallback_enabled():
                    return HTTPStatus.BAD_GATEWAY, {
                        "message": "OTP email could not be sent right now. Please check the configured email delivery service.",
                        "detail": str(error),
                    }
                use_screen_fallback = True
                fallback_message = f"OTP email could not be sent right now. For local testing, use this OTP: {otp_code}"
    except KeyError:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "Account password data is incomplete."}

    return HTTPStatus.OK, otp_delivery_payload(
        challenge_id=challenge_id,
        email=normalize_email(user["email"]),
        expires_at=expires_at,
        otp_code=otp_code,
        success_message=f"OTP sent to {mask_email(user['email'])}.",
        use_screen_fallback=use_screen_fallback,
        fallback_message=fallback_message,
        delivery_mode=delivery_mode,
    )


def confirm_profile_password_change(user_id: str, payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    challenge_id = str(payload.get("challengeId") or "").strip()
    otp_code = "".join(character for character in str(payload.get("otp") or "") if character.isdigit())
    new_password = str(payload.get("newPassword") or "")

    if not str(user_id).strip().isdigit():
        return HTTPStatus.BAD_REQUEST, {"message": "Logged-in account is missing."}

    if not challenge_id:
        return HTTPStatus.BAD_REQUEST, {"message": "OTP session is missing."}

    if len(otp_code) != OTP_LENGTH:
        return HTTPStatus.BAD_REQUEST, {"message": "Enter the full 6-digit OTP first."}

    if not is_valid_password(new_password):
        return HTTPStatus.BAD_REQUEST, {"message": PASSWORD_POLICY_MESSAGE}


    with connect_database() as connection:
        cleanup_stale_login_challenges(connection)
        success, result = verify_login_challenge(connection, challenge_id, otp_code, consume=True)
        if not success:
            return HTTPStatus.UNAUTHORIZED, result
        if str(result.get("id") or "").strip() != str(int(user_id)):
            return HTTPStatus.FORBIDDEN, {"message": "OTP does not belong to the logged-in account."}

        timestamp = utc_now_iso()
        salt, digest = create_secret_hash(new_password, iterations=PASSWORD_ITERATIONS)
        connection.execute(
            """
            UPDATE users
            SET password_hash = ?, password_salt = ?, password_iterations = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                digest,
                salt,
                PASSWORD_ITERATIONS,
                timestamp,
                int(user_id),
            ),
        )

    return HTTPStatus.OK, {"message": "Password changed successfully."}


def request_user_creation_otp(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    # Account creation is OTP-gated so invalid or duplicate users never reach the real users table.
    display_name = str(payload.get("displayName") or payload.get("name") or "").strip()
    email = normalize_email(payload.get("email"))
    role = normalize_role(payload.get("role"))
    password = str(payload.get("password") or "")
    confirm_password = str(payload.get("confirmPassword") or password)
    use_screen_fallback = False
    fallback_message = ""
    delivery_mode = "email"
    # See request_password_reset_otp: the outer handlers below can run before a
    # challenge has been created, so these must already exist.
    challenge_id = ""
    otp_code = ""
    expires_at = ""

    if not display_name:
        return HTTPStatus.BAD_REQUEST, {"message": "Please enter the user's name."}

    if not email:
        return HTTPStatus.BAD_REQUEST, {"message": "Please enter the user's Gmail address."}

    if not is_valid_gmail_address(email):
        return HTTPStatus.BAD_REQUEST, {"message": "Use a valid Gmail address."}

    if not password:
        return HTTPStatus.BAD_REQUEST, {"message": "Please enter the user's password."}

    if password != confirm_password:
        return HTTPStatus.BAD_REQUEST, {"message": "Passwords do not match."}

    if not is_valid_password(password):
        return HTTPStatus.BAD_REQUEST, {"message": PASSWORD_POLICY_MESSAGE}


    try:
        with connect_database() as connection:
            cleanup_stale_account_creation_challenges(connection)
            throttle_payload = check_otp_request_throttle(connection, email, client_ip_address())
            if throttle_payload:
                return HTTPStatus.TOO_MANY_REQUESTS, throttle_payload
            existing_user = find_user_by_email(connection, email)
            if existing_user:
                return HTTPStatus.CONFLICT, {"message": "That Gmail address is already registered."}

            challenge_id, otp_code, expires_at = create_account_creation_challenge(
                connection,
                display_name=display_name,
                email=email,
                role=role,
                password=password,
            )
            try:
                delivery_mode = send_or_enqueue_otp_email(
                    challenge_id=challenge_id,
                    purpose="account-creation",
                    recipient=email,
                    display_name=display_name,
                    otp_code=otp_code,
                    expires_at=expires_at,
                )
            except smtplib.SMTPAuthenticationError as error:
                if not insecure_otp_fallback_enabled():
                    return HTTPStatus.BAD_GATEWAY, smtp_auth_failure_payload(error)
                use_screen_fallback = True
                fallback_message = f"Gmail SMTP login failed. For local testing, use this OTP: {otp_code}"
            except MailConfigurationError as error:
                if not insecure_otp_fallback_enabled():
                    return HTTPStatus.SERVICE_UNAVAILABLE, {"message": str(error)}
                use_screen_fallback = True
                fallback_message = f"Gmail SMTP is not configured yet. For local testing, use this OTP: {otp_code}"
            except (OSError, smtplib.SMTPException) as error:
                if not insecure_otp_fallback_enabled():
                    return HTTPStatus.BAD_GATEWAY, {
                        "message": "OTP email could not be sent right now. Please check the configured email delivery service.",
                        "detail": str(error),
                    }
                use_screen_fallback = True
                fallback_message = f"OTP email could not be sent right now. For local testing, use this OTP: {otp_code}"
    except MailConfigurationError as error:
        if not insecure_otp_fallback_enabled() or not otp_code:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"message": str(error)}
        use_screen_fallback = True
        fallback_message = f"Gmail SMTP is not configured yet. For local testing, use this OTP: {otp_code}"
    except smtplib.SMTPAuthenticationError as error:
        if not insecure_otp_fallback_enabled() or not otp_code:
            return HTTPStatus.BAD_GATEWAY, smtp_auth_failure_payload(error)
        use_screen_fallback = True
        fallback_message = f"Gmail SMTP login failed. For local testing, use this OTP: {otp_code}"
    except (OSError, smtplib.SMTPException) as error:
        if not insecure_otp_fallback_enabled() or not otp_code:
            return HTTPStatus.BAD_GATEWAY, {
                    "message": "OTP email could not be sent right now. Please check the configured email delivery service.",
                "detail": str(error),
            }
        use_screen_fallback = True
        fallback_message = f"OTP email could not be sent right now. For local testing, use this OTP: {otp_code}"

    return HTTPStatus.OK, otp_delivery_payload(
        challenge_id=challenge_id,
        email=email,
        expires_at=expires_at,
        otp_code=otp_code,
        success_message="OTP sent successfully. Enter the 6-digit code to finish creating the account.",
        use_screen_fallback=use_screen_fallback,
        fallback_message=fallback_message,
        delivery_mode=delivery_mode,
    )


def create_user_with_otp(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    challenge_id = str(payload.get("challengeId") or "").strip()
    otp_code = "".join(character for character in str(payload.get("otp") or "") if character.isdigit())

    if not challenge_id:
        return HTTPStatus.BAD_REQUEST, {"message": "OTP session is missing."}

    if len(otp_code) != OTP_LENGTH:
        return HTTPStatus.BAD_REQUEST, {"message": "Enter the full 6-digit OTP first."}


    try:
        with connect_database() as connection:
            cleanup_stale_account_creation_challenges(connection)
            success, result = verify_account_creation_challenge(connection, challenge_id, otp_code, consume=True)
            if not success:
                return HTTPStatus.UNAUTHORIZED, result

            challenge = result
            existing_user = find_user_by_email(connection, str(challenge["email"]))
            if existing_user:
                connection.execute("DELETE FROM account_creation_challenges WHERE id = ?", (challenge_id,))
                return HTTPStatus.CONFLICT, {"message": "That Gmail address is already registered."}

            # After OTP validation, the pending challenge is promoted into a real login account.
            user = insert_user_account(
                connection,
                display_name=str(challenge["display_name"]),
                email=str(challenge["email"]),
                role=str(challenge["role"]),
                password_hash=str(challenge["password_hash"]),
                password_salt=str(challenge["password_salt"]),
                password_iterations=int(challenge["password_iterations"]),
            )
            connection.execute("DELETE FROM account_creation_challenges WHERE id = ?", (challenge_id,))
            success_message = f"{str(user['display_name']).strip()} was added successfully and can now log in."
            create_notification_record(
                connection,
                scope="admin",
                type="success",
                message=success_message,
                source_type="user",
                source_id=str(user["id"]),
            )
            users = [build_user_payload(item) for item in list_users(connection)]
    except sqlite3.IntegrityError:
        return HTTPStatus.CONFLICT, {"message": "That Gmail address is already registered."}


    return HTTPStatus.CREATED, {
        "message": success_message,
        "user": build_user_payload(user),
        "users": users,
    }


def api_list_users() -> tuple[HTTPStatus, dict[str, object]]:

    with connect_database() as connection:
        users = [build_user_payload(user) for user in list_users(connection)]
    return HTTPStatus.OK, {"users": users}


def api_create_user(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    try:
        display_name, email, role, password = validate_user_account_fields(
            display_name=payload.get("displayName") or payload.get("name"),
            email=payload.get("email"),
            role=payload.get("role"),
            password=payload.get("password"),
            confirm_password=payload.get("confirmPassword") or payload.get("password"),
        )
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}


    try:
        with connect_database() as connection:
            user = create_user_account(
                connection,
                display_name=display_name,
                email=email,
                role=role,
                password=password,
            )
            success_message = f"{display_name} was added successfully and can now log in."
            create_notification_record(
                connection,
                scope="admin",
                type="success",
                message=success_message,
                source_type="user",
                source_id=str(user["id"]),
            )
            users = [build_user_payload(item) for item in list_users(connection)]
    except sqlite3.IntegrityError:
        return HTTPStatus.CONFLICT, {"message": "That Gmail address is already registered."}


    return HTTPStatus.CREATED, {
        "message": success_message,
        "user": build_user_payload(user),
        "users": users,
    }


def verify_acting_admin_password(password: str) -> tuple[HTTPStatus, dict[str, object]] | None:
    """None when the signed-in administrator typed their own password.

    Deleting an account or a cultivation cannot be undone, and adding an
    account -- an administrator above all -- hands someone a way in, so the
    dialog asks for the password of whoever is signed in: an unattended
    session, on the kiosk above all, must not be enough. It is a password oracle behind a
    session, so it shares the Change Password lockout scopes: guesses here and
    there count together.

    Refusals are 403, never 401: the browser reads a 401 as an expired session
    and would sign the administrator out for a typo.
    """
    acting = authenticated_request_user() or {}
    acting_id = str(acting.get("id") or "").strip()
    if not password:
        return HTTPStatus.FORBIDDEN, {
            "code": "ADMIN_PASSWORD_REQUIRED",
            "message": "Enter your password to confirm.",
        }
    if not acting_id.isdigit():
        return HTTPStatus.FORBIDDEN, {"message": "Logged-in account could not be detected."}
    with connect_database() as connection:
        admin = find_user_by_id(connection, int(acting_id))
        if not admin or int(admin["is_active"]) != 1:
            return HTTPStatus.FORBIDDEN, {"message": "Logged-in account was not found or is inactive."}
        ip_scope = f"pwchk-ip:{client_ip_address()}"
        account_scope = f"pwchk-acct:{normalize_email(admin['email'])}"
        active_lock = get_admin_login_lock(connection, ip_scope) or get_admin_login_lock(
            connection, account_scope
        )
        if active_lock:
            return HTTPStatus.TOO_MANY_REQUESTS, active_lock
        if not verify_secret(
            password,
            salt=str(admin["password_salt"]),
            digest=str(admin["password_hash"]),
            iterations=int(admin["password_iterations"]),
        ):
            failure = register_login_failure_across_scopes(
                connection,
                ip_scope,
                account_scope,
                "Incorrect password.",
                user_id=int(admin["id"]),
            )
            if failure.get("code") == "ADMIN_LOGIN_LOCKED":
                return HTTPStatus.TOO_MANY_REQUESTS, failure
            return HTTPStatus.FORBIDDEN, {**failure, "code": "ADMIN_PASSWORD_INCORRECT"}
        clear_admin_login_attempts(connection, ip_scope)
        clear_admin_login_attempts(connection, account_scope)
    return None


def refuse_without_acting_admin_password(field: str = "password") -> tuple[HTTPStatus, dict[str, object]] | None:
    """The route-side door to verify_acting_admin_password: reads the JSON body.

    ``field`` names the body key holding it. Adding an account sends it as
    adminPassword, because "password" there is the new account's own.
    """
    try:
        body = flask_request.get_json(silent=True) or {}
    except Exception:  # noqa: BLE001 - an unreadable body is a missing password
        body = {}
    password = str(body.get(field) or "") if isinstance(body, dict) else ""
    return verify_acting_admin_password(password)


def api_delete_user(user_id: str) -> tuple[HTTPStatus, dict[str, object]]:
    if not str(user_id or "").isdigit():
        return HTTPStatus.BAD_REQUEST, {"message": "User id is invalid."}


    with connect_database() as connection:
        user = connection.execute(
            """
            SELECT id, display_name, role, email, created_at
            FROM users
            WHERE id = ?
            """,
            (int(user_id),),
        ).fetchone()
        if not user:
            return HTTPStatus.NOT_FOUND, {"message": "User account not found."}

        if normalize_role(user["role"]) == "admin":
            return HTTPStatus.FORBIDDEN, {"message": "Administrator accounts cannot be deleted here."}

        message = f"{str(user['display_name']).strip()} was removed from user accounts."
        record_sync_tombstone(
            connection,
            entity=USER_TOMBSTONE,
            natural_key=user_sync_key(user["email"], user["created_at"]),
        )
        connection.execute("DELETE FROM users WHERE id = ?", (int(user_id),))
        create_notification_record(
            connection,
            scope="admin",
            type="warning",
            message=message,
            source_type="user",
            source_id=str(user["id"]),
        )


    return HTTPStatus.OK, {
        "message": message,
    }


def api_get_profile(user_id: str) -> tuple[HTTPStatus, dict[str, object]]:
    if not str(user_id or "").isdigit():
        return HTTPStatus.BAD_REQUEST, {"message": "User id is invalid."}


    with connect_database() as connection:
        user = find_user_by_id(connection, int(user_id))
        if not user or int(user["is_active"]) != 1:
            return HTTPStatus.NOT_FOUND, {"message": "Profile not found."}

    # A picture set on another device reaches this one through the sync timer,
    # which copies the photo columns whichever way profile_photo_version says
    # is newer. This response hands the frontend the URL it will display, and
    # the version in that URL is what makes a changed photo a cache miss.
    # Fetching just the user record (not the photo bytes) keeps that check
    # cheap enough to run every time a profile loads, e.g. right after login.
    return HTTPStatus.OK, {"user": build_user_payload(user)}


def api_get_profile_photo(user_id: str, requested_version: str = "") -> tuple[HTTPStatus, bytes, str]:
    if not str(user_id or "").isdigit():
        return HTTPStatus.NOT_FOUND, b"", "application/octet-stream"


    def read_local_photo_row():
        with connect_database() as connection:
            return connection.execute(
                """
                SELECT profile_photo_path, profile_photo_mime, profile_photo_data, profile_photo_version
                FROM users
                WHERE id = ? AND is_active = TRUE
                """,
                (int(user_id),),
            ).fetchone()

    row = read_local_photo_row()
    if not row:
        return HTTPStatus.NOT_FOUND, b"", "application/octet-stream"

    # Adopt a picture uploaded from another device before giving up on this one.
    #
    # The version is the reliable signal that a photo exists.
    # profile_photo_record_url builds /profile-photo/<id>?v=<version>, so a
    # changed photo produces a different URL and defeats the browser cache.
    stored_version = str(row["profile_photo_version"] or "").strip()
    wanted_version = str(requested_version or "").strip()

    # This endpoint is reachable without a session so that plain <img> tags can
    # load a photo -- an image request cannot carry the bearer token. That means
    # the user id in the URL cannot be the only guard, or anyone could walk
    # /profile-photo/1,2,3.. and pull every member's photo while confirming
    # which ids exist. Require the current version token, which the backend only
    # ever hands to an authenticated client inside its user payload; a request
    # that cannot present it (id enumeration) gets the same 404 as a missing
    # photo. The URL builder always appends the live version, so ordinary
    # rendering is unaffected, and a stale token self-heals on the next refresh.
    if (
        not stored_version
        or not wanted_version
        or not hmac.compare_digest(wanted_version, stored_version)
    ):
        return HTTPStatus.NOT_FOUND, b"", "application/octet-stream"

    data = bytes(row["profile_photo_data"] or b"")
    content_type = str(row["profile_photo_mime"] or "").strip().lower()
    if data and len(data) <= MAX_PROFILE_PHOTO_BYTES and content_type in {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    }:
        return HTTPStatus.OK, data, content_type

    legacy_photo = local_profile_photo_record(row["profile_photo_path"])
    if legacy_photo:
        return HTTPStatus.OK, legacy_photo[0], legacy_photo[1]
    return HTTPStatus.NOT_FOUND, b"", "application/octet-stream"


def validate_profile_display_name(value: object) -> str:
    display_name = str(value or "").strip()
    if not display_name:
        raise ValueError("Name is required.")
    if len(display_name) < PROFILE_NAME_MIN_LENGTH:
        raise ValueError(f"Name must contain at least {PROFILE_NAME_MIN_LENGTH} characters.")
    if len(display_name) > PROFILE_NAME_MAX_LENGTH:
        raise ValueError(f"Name cannot exceed {PROFILE_NAME_MAX_LENGTH} characters.")
    if re.search(r"([^\W\d_])\1{3}", display_name, flags=re.IGNORECASE):
        raise ValueError("A letter cannot repeat more than 3 times in a row.")
    return display_name


def api_update_profile(user_id: str) -> tuple[HTTPStatus, dict[str, object]]:
    if not str(user_id or "").isdigit():
        return HTTPStatus.BAD_REQUEST, {"message": "User id is invalid."}

    try:
        display_name = validate_profile_display_name(flask_request.form.get("display_name"))
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}

    uploaded_file = flask_request.files.get("profile_photo")
    saved_photo_data: bytes | None = None
    saved_photo_mime = ""
    saved_photo_version = ""
    previous_photo_path = ""


    try:
        with connect_database() as connection:
            user = find_user_by_id(connection, int(user_id))
            if not user or int(user["is_active"]) != 1:
                return HTTPStatus.NOT_FOUND, {"message": "Profile not found."}

            previous_photo_path = optional_row_value(user, "profile_photo_path")

            if uploaded_file and uploaded_file.filename:
                saved_photo_data, saved_photo_mime = read_profile_photo_upload(uploaded_file)
                saved_photo_version = utc_now_iso()

            updated_user = update_user_profile(
                connection,
                user_id=int(user_id),
                display_name=display_name,
                profile_photo_data=saved_photo_data,
                profile_photo_mime=saved_photo_mime,
                profile_photo_version=saved_photo_version,
            )
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}

    if saved_photo_data is not None and previous_photo_path:
        delete_profile_photo_file(previous_photo_path)

    return HTTPStatus.OK, {
        "message": "Profile updated successfully.",
        "user": build_user_payload(updated_user),
    }


def api_list_cultivations() -> tuple[HTTPStatus, dict[str, object]]:
    # The Pi is the edge authority for the farm. Its browser reads active rows
    # from the local database, so they survive losing the network.

    with connect_database() as connection:
        cultivations = [build_cultivation_payload(item) for item in list_cultivations(connection)]
    return HTTPStatus.OK, {"cultivations": cultivations}


# ---------------------------------------------------------------------------
# Cultivation requests
# ---------------------------------------------------------------------------
#
# A grower cannot plant a row -- the cultivation endpoints are the
# administrator's -- but can ask for one. A request is an admin notification
# whose source_id carries the planting as compact JSON, and the answer is a
# second notification naming the request. Nothing is ever updated in place.
#
# Notifications on purpose, not a table of their own: they already travel both
# ways between the Pi and the website, over Postgres and over the HTTPS
# fallback, deletions included. A request made on either side reaches the
# administrator on the other, and an approval made on either side reaches the
# grower, with no new schema, migration or sync rule to get wrong. The planting
# itself still goes through api_create_cultivation, so an approved request is
# exactly what an administrator's own Start would have made.

CULTIVATION_REQUEST_SOURCE = "cultivation_request"
CULTIVATION_REQUEST_DECISION_SOURCE = "cultivation_request_decision"
# An unanswered request stops counting after this long; the row is freed.
CULTIVATION_REQUEST_EXPIRY_DAYS = 30


def _decode_request_source(raw: object) -> dict[str, object] | None:
    try:
        decoded = json.loads(str(raw or ""))
    except (TypeError, ValueError):
        return None
    if not isinstance(decoded, dict) or not str(decoded.get("id") or "").strip():
        return None
    return decoded


def list_pending_cultivation_requests(connection: sqlite3.Connection) -> list[dict[str, object]]:
    """Requests nobody has answered yet, oldest first.

    A request is answered once any decision names it -- a deleted decision
    included, so clearing History never reopens one. A deleted request is
    withdrawn. The newest request per row wins when two sides raced.
    """
    decided = {
        str(decoded.get("id"))
        for row in connection.execute(
            "SELECT source_id FROM notifications WHERE source_type = ?",
            (CULTIVATION_REQUEST_DECISION_SOURCE,),
        ).fetchall()
        if (decoded := _decode_request_source(row["source_id"])) is not None
    }
    cutoff = (utc_now() - timedelta(days=CULTIVATION_REQUEST_EXPIRY_DAYS)).isoformat()
    # Planted since the request was made -- by an administrator directly, or
    # on the other side. Kept visible so it can be rejected, but it cannot be
    # approved into an occupied row.
    planted_rows = {str(item["row_key"]) for item in list_cultivations(connection)}
    pending: list[dict[str, object]] = []
    for row in connection.execute(
        """
        SELECT source_id, created_at FROM notifications
        WHERE source_type = ? AND deleted_at IS NULL AND created_at >= ?
        ORDER BY created_at ASC
        """,
        (CULTIVATION_REQUEST_SOURCE, cutoff),
    ).fetchall():
        decoded = _decode_request_source(row["source_id"])
        if decoded is None or str(decoded["id"]) in decided:
            continue
        row_key = str(decoded.get("rowKey") or "")
        pending = [item for item in pending if item["rowKey"] != row_key]
        pending.append({
            "id": str(decoded["id"]),
            "rowKey": row_key,
            "rowLabel": cultivation_row_label(row_key),
            "cropType": str(decoded.get("cropType") or ""),
            "cropName": str(decoded.get("cropName") or ""),
            "plantingDate": str(decoded.get("plantingDate") or ""),
            "harvestDate": str(decoded.get("harvestDate") or ""),
            "daysToHarvest": int(decoded.get("daysToHarvest") or 0),
            "requestedByEmail": str(decoded.get("requestedByEmail") or ""),
            "requestedByName": str(decoded.get("requestedByName") or ""),
            "requestedAt": str(row["created_at"] or ""),
            "rowInUse": row_key in planted_rows,
        })
    return pending


def api_request_cultivation(
    payload: dict[str, object], requester: dict[str, object]
) -> tuple[HTTPStatus, dict[str, object]]:
    """A grower asks for a row to be planted. Any signed-in account may ask."""
    row_key = str(payload.get("rowKey") or "").strip().lower()
    crop_type = str(payload.get("cropType") or "").strip()
    crop_name = str(payload.get("cropName") or payload.get("crop") or "").strip()
    requester_email = normalize_email(requester.get("email"))
    requester_name = str(requester.get("displayName") or "").strip() or requester_email

    if not requester_email:
        return HTTPStatus.UNAUTHORIZED, {"message": "Please sign in again to send a request."}
    if row_key not in VALID_CULTIVATION_ROWS:
        return HTTPStatus.BAD_REQUEST, {"message": "Please choose a valid planting row."}
    # A request is always for the recommended setup: the administrator applies
    # the reference range for the crop, so a custom plant has nothing to apply.
    if not crop_type or crop_type == "custom":
        return HTTPStatus.BAD_REQUEST, {"message": "Please choose a crop type."}
    if not crop_name:
        return HTTPStatus.BAD_REQUEST, {"message": "Crop name is required."}
    try:
        # Not held to this year: planting is always today now, so a request
        # made late in the year may be harvested in the next one. The day it
        # is actually planted is the day it is approved (api_create_cultivation).
        planting_date = cultivation_date_value(payload.get("plantingDate"), label="Planting date").isoformat()
        harvest_date = cultivation_date_value(payload.get("harvestDate"), label="Harvest date").isoformat()
        days_to_harvest = int(payload.get("daysToHarvest") or 0)
    except (TypeError, ValueError) as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}
    if days_to_harvest <= 0:
        return HTTPStatus.BAD_REQUEST, {"message": "Days to harvest must be greater than zero."}
    if harvest_date < planting_date:
        return HTTPStatus.BAD_REQUEST, {"message": "Harvest date cannot be earlier than planting date."}

    row_label = cultivation_row_label(row_key)
    with connect_database() as connection:
        if find_cultivation_by_row_key(connection, row_key):
            return HTTPStatus.CONFLICT, {"message": f"{row_label} already has an active cultivation."}
        if any(item["rowKey"] == row_key for item in list_pending_cultivation_requests(connection)):
            return HTTPStatus.CONFLICT, {"message": f"{row_label} already has a request waiting for approval."}
        request_id = secrets.token_hex(8)
        source = json.dumps(
            {
                "id": request_id,
                "rowKey": row_key,
                "cropType": crop_type[:40],
                "cropName": crop_name[:60],
                "plantingDate": planting_date,
                "harvestDate": harvest_date,
                "daysToHarvest": days_to_harvest,
                "requestedByEmail": requester_email,
                "requestedByName": requester_name[:60],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        create_notification_record(
            connection,
            scope="admin",
            type="warning",
            message=(
                f"{requester_name[:60]} asked to plant {crop_name[:60]} in {row_label}"
                f" on {planting_date}. Approve or reject it on the Cultivation page."
            ),
            source_type=CULTIVATION_REQUEST_SOURCE,
            source_id=source,
        )
        connection.commit()
        requests = list_pending_cultivation_requests(connection)
    return HTTPStatus.CREATED, {
        "message": f"Request sent. {crop_name} in {row_label} will start once an administrator approves it.",
        "requests": requests,
    }


def _record_cultivation_request_decision(
    connection: sqlite3.Connection,
    request: dict[str, object],
    *,
    decision: str,
    decided_by: str,
) -> None:
    verb = "approved" if decision == "approved" else "rejected"
    create_notification_record(
        connection,
        scope="all",
        type="success" if decision == "approved" else "warning",
        message=(
            f"{decided_by} {verb} {request['requestedByName'] or request['requestedByEmail']}'s"
            f" request to plant {request['cropName']} in {request['rowLabel']}."
        ),
        source_type=CULTIVATION_REQUEST_DECISION_SOURCE,
        source_id=json.dumps({"id": request["id"], "decision": verb}, separators=(",", ":"), sort_keys=True),
    )


def api_decide_cultivation_request(
    request_id: str,
    decision: str,
    payload: dict[str, object],
    administrator: dict[str, object],
) -> tuple[HTTPStatus, dict[str, object]]:
    """Approve (plant it) or reject a pending request. Administrator only."""
    decided_by = str(administrator.get("displayName") or "").strip() or "An administrator"
    with connect_database() as connection:
        request = next(
            (item for item in list_pending_cultivation_requests(connection) if item["id"] == str(request_id)),
            None,
        )
        if request is None:
            return HTTPStatus.NOT_FOUND, {
                "message": "That request was already answered or withdrawn.",
                "requests": list_pending_cultivation_requests(connection),
            }
        if decision == "rejected":
            _record_cultivation_request_decision(connection, request, decision="rejected", decided_by=decided_by)
            connection.commit()
            return HTTPStatus.OK, {
                "message": f"Request for {request['cropName']} in {request['rowLabel']} rejected.",
                "requests": list_pending_cultivation_requests(connection),
            }
        requester = find_user_by_email(connection, str(request["requestedByEmail"]))
        existing = find_cultivation_by_row_key(connection, str(request["rowKey"]))

    # An approval whose planting is already in the row -- a retry after the
    # answer failed to save -- only needs the answer written.
    # By crop only: the planting takes the day of approval, not the day asked
    # for, so the two dates no longer match.
    already_planted = existing is not None and str(existing["crop_type"]) == request["cropType"]
    response: dict[str, object] = {}
    if not already_planted:
        status, response = api_create_cultivation({
            "rowKey": request["rowKey"],
            "cropType": request["cropType"],
            "customPlantName": "",
            "cropName": request["cropName"],
            "plantingDate": request["plantingDate"],
            "harvestDate": request["harvestDate"],
            "daysToHarvest": request["daysToHarvest"],
            "parameterMode": "recommended",
            "parameters": payload.get("parameters"),
            "createdByUserId": str(requester["id"]) if requester else "",
        })
        if status != HTTPStatus.CREATED:
            return status, response

    with connect_database() as connection:
        _record_cultivation_request_decision(connection, request, decision="approved", decided_by=decided_by)
        connection.commit()
        response["requests"] = list_pending_cultivation_requests(connection)
        if already_planted:
            response["cultivations"] = [build_cultivation_payload(item) for item in list_cultivations(connection)]
    response["message"] = f"Approved. {request['cropName']} was started in {request['rowLabel']}."
    return HTTPStatus.CREATED if not already_planted else HTTPStatus.OK, response


def api_list_cultivation_harvests() -> tuple[HTTPStatus, dict[str, object]]:
    """Completed crops, newest first. Read-only; harvests are never edited."""
    with connect_database() as connection:
        harvests = [build_harvest_payload(item) for item in list_cultivation_harvests(connection)]
    return HTTPStatus.OK, {"harvests": harvests}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

REPORT_SECTION_KEYS = (
    "sensors",
    "irrigation",
    "cultivations",
    "alerts",
    "health",
)
REPORT_MAX_RANGE_DAYS = 366
REPORT_TABLE_ROW_LIMIT = 400
# A PDF is a readable summary, not a database dump. Hundreds of irrigation
# rows produced a dozen pages and made a hosted export spend seconds laying out
# information nobody can scan. Keep the recent activity and state exactly how
# much earlier history was omitted.
REPORT_PDF_TABLE_ROW_LIMIT = 40
REPORT_TREND_POINTS = 24
# How many recent rows per sensor the preview averages. The preview only has to
# describe the window, not reproduce it, and this caps what a page open costs on
# a metered connection.
REPORT_PREVIEW_SAMPLE_LIMIT = 200
# The preview says how much a range covers, and nothing on the page needs that
# number to be exact once it is large. sensor_readings has no retention policy,
# so an exact COUNT(*) had to visit every row the farm has ever recorded in the
# window -- fine when the table was young, minutes of it later, which is why the
# tiles ended up loading forever. Counting a capped subquery stops at the cap
# instead, so the cost is bounded no matter how big the table gets, and the tile
# reads "10,000+" past it.
REPORT_PREVIEW_COUNT_CAP = 10000
# Bok choy and mustasa are grown here; a row without a cultivation still gets a
# card so the report shows the whole greenhouse rather than only the used half.
REPORT_ROW_KEYS = ("row1", "row2", "row3", "row4")


def normalize_report_sections(value: object) -> list[str]:
    """Keep only recognised section keys, in a fixed order.

    Order matters: the caller's checkbox order should not decide the order of
    the sheets in the workbook or the sections in the PDF.
    """
    if isinstance(value, str):
        requested = {part.strip() for part in value.split(",")}
    elif isinstance(value, (list, tuple, set)):
        requested = {str(part).strip() for part in value}
    else:
        requested = set()

    selected = [key for key in REPORT_SECTION_KEYS if key in requested]
    return selected or list(REPORT_SECTION_KEYS)


def normalize_report_date(value: object, fallback: datetime) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return fallback


def report_range_bounds(payload: dict[str, object]) -> tuple[datetime, datetime]:
    """Resolve the requested window, clamped to something a report can carry.

    An open-ended or reversed range is a bad request rather than an error worth
    refusing: the export still has to produce a document, so the range is
    repaired instead.
    """
    now = utc_now()
    default_start = now - timedelta(days=29)
    start = normalize_report_date(payload.get("startDate"), default_start)
    end = normalize_report_date(payload.get("endDate"), now)

    if end < start:
        start, end = end, start
    if (end - start).days > REPORT_MAX_RANGE_DAYS:
        start = end - timedelta(days=REPORT_MAX_RANGE_DAYS)

    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start, end


def report_row_filter(payload: dict[str, object]) -> list[str]:
    """Which rows the report covers. An unrecognised value means every row."""
    raw = str(payload.get("rowKey") or "").strip().lower()
    if raw in VALID_CULTIVATION_ROWS:
        return [raw]
    return list(REPORT_ROW_KEYS)


def clamp_report_offset(offset_minutes: object) -> int:
    try:
        shift = int(offset_minutes)
    except (TypeError, ValueError):
        return 0
    return max(-14 * 60, min(14 * 60, shift))


def report_parse_moment(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return parse_iso_datetime(raw)
    except ValueError:
        return None


def format_report_clock(value: object, offset_minutes: int = 0) -> str:
    """Render a stored UTC timestamp on the viewer's clock, as 06:00 AM."""
    moment = report_parse_moment(value)
    if not moment:
        return ""
    local = moment + timedelta(minutes=clamp_report_offset(offset_minutes))
    hour = local.hour % 12 or 12
    meridiem = "AM" if local.hour < 12 else "PM"
    return f"{hour:02d}:{local.strftime('%M')} {meridiem}"


def format_report_day(value: object, offset_minutes: int = 0) -> str:
    moment = report_parse_moment(value)
    if not moment:
        return ""
    local = moment + timedelta(minutes=clamp_report_offset(offset_minutes))
    return f"{local.strftime('%b')} {local.day}, {local.year}"


# The trend chart draws a fixed number of points and the workbook's readings
# sheet is capped, so the export never needs every row in the window. This farm
# holds over half a million readings in a month: fetching them all was ~65MB
# across a link that stalls, plus a JSON parse each, which is why the hosted
# download ran past the function's 60s limit and returned nothing. Bucketing in
# SQL and capping the transfer keeps the same shape at a fraction of the cost.
REPORT_READING_BUCKETS = 240


def collect_report_readings(
    connection: sqlite3.Connection,
    start: datetime,
    end: datetime,
    row_keys: list[str] | None = None,
) -> dict[str, list[dict[str, object]]]:
    """Readings for the charted sensors, thinned to what the report can show.

    Every sensor is sampled in one query. The bucketing runs inside each branch
    of a UNION so PostgreSQL can still use the sensor/time index, while the
    whole sample crosses the managed database link in a single round trip.
    Sending one otherwise-fast query per sensor made a hosted export spend most
    of its function lifetime waiting on network latency.

    The bucket key is built from the timestamp text rather than a date
    function. strftime('%s', ...) cannot be used here even though the Postgres
    shim rewrites it: psycopg parses %s as its own placeholder, so the literal
    inside the SQL made the driver see zero placeholders and reject the five
    real parameters. Both backends store captured_at as an ISO-8601 string, so
    slicing that string is exact, portable, and needs no % at all.
    """
    grouped: dict[str, list[dict[str, object]]] = {}
    if (end - start).total_seconds() <= 0:
        return grouped

    # How much of "2026-08-30T14:23:45..." identifies one bucket. A window of a
    # few days buckets by hour (13 chars); a longer one by day (10). Both give
    # the chart more points than it draws, and the caller thins further.
    span_days = max(1, (end - start).days + 1)
    key_length = 10 if span_days > 3 else 13
    window = (start.isoformat(), end.isoformat())

    sensor_keys = report_charted_sensor_keys(row_keys)

    if postgres_backend_enabled():
        # Keep every lookup index-shaped and send all of them in one statement.
        # A LATERAL join let PostgreSQL choose a repeated range-scan plan, while
        # GROUP BY scanned all 1.28M readings in the month. Explicit UNION
        # branches give the planner a constant sensor/window for every small
        # `(sensor_key, captured_at DESC)` seek, yet still cost only one network
        # round trip to Supabase. A normal month is 30 buckets x 15 sensors.
        bucket_size = timedelta(days=1) if span_days > 3 else timedelta(hours=1)
        bucket_limit = 72
        total_span = end - start + timedelta(microseconds=1)
        if total_span > bucket_size * bucket_limit:
            bucket_size = total_span / bucket_limit

        buckets: list[tuple[str, str]] = []
        bucket_start = start
        while bucket_start <= end and len(buckets) < bucket_limit:
            bucket_end = min(bucket_start + bucket_size, end + timedelta(microseconds=1))
            buckets.append((bucket_start.isoformat(), bucket_end.isoformat()))
            bucket_start = bucket_end

        branches: list[str] = []
        parameters: list[object] = []
        for sensor_key in sensor_keys:
            for lower, upper in buckets:
                branches.append(
                    """
                    SELECT sensor_key, reading_payload_json, captured_at FROM (
                        SELECT sensor_key, reading_payload_json, captured_at
                        FROM sensor_readings
                        WHERE sensor_key = ?
                          AND captured_at >= ? AND captured_at < ?
                        ORDER BY captured_at DESC
                        LIMIT 1
                    ) AS bucket_sample
                    """
                )
                parameters.extend((sensor_key, lower, upper))

        rows = connection.execute(
            "\nUNION ALL\n".join(branches)
            + "\nORDER BY sensor_key ASC, captured_at ASC",
            parameters,
        ).fetchall()

        grouped: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            sensor_key = str(row["sensor_key"])
            sensor_entries = grouped.setdefault(sensor_key, [])
            payload = parse_json_object(row["reading_payload_json"])
            if not isinstance(payload, dict):
                continue
            sensor_entries.append(
                {"payload": payload, "capturedAt": row["captured_at"]}
            )
        return grouped

    branches: list[str] = []
    parameters: list[object] = []
    for sensor_key in sensor_keys:
        branches.append(
            """
            SELECT sensor_key, reading_payload_json, captured_at FROM (
            SELECT sensor_key, reading_payload_json, captured_at FROM (
                SELECT
                    sensor_key,
                    reading_payload_json,
                    captured_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY SUBSTR(captured_at, 1, ?)
                        ORDER BY captured_at DESC
                    ) AS rank_in_bucket
                FROM sensor_readings
                WHERE sensor_key = ? AND captured_at >= ? AND captured_at <= ?
            ) AS bucketed
            WHERE rank_in_bucket = 1
            ORDER BY captured_at ASC
            LIMIT ?
            ) AS sensor_sample
            """
        )
        parameters.extend((key_length, sensor_key, *window, REPORT_READING_BUCKETS))

    rows = connection.execute(
        "\nUNION ALL\n".join(branches) + "\nORDER BY sensor_key ASC, captured_at ASC",
        parameters,
    ).fetchall()

    for row in rows:
        payload = parse_json_object(row["reading_payload_json"])
        if not isinstance(payload, dict):
            continue
        grouped.setdefault(str(row["sensor_key"]), []).append(
            {"payload": payload, "capturedAt": row["captured_at"]}
        )

    return grouped


def report_metric_values(
    readings: dict[str, list[dict[str, object]]], sensor_key: str, metric_key: str
) -> list[float]:
    values: list[float] = []
    for entry in readings.get(sensor_key, []):
        value = normalize_numeric_value(entry["payload"].get(metric_key))
        if value is not None:
            values.append(float(value))
    return values


def report_metric_points(
    readings: dict[str, list[dict[str, object]]], sensor_key: str, metric_key: str
) -> list[dict[str, object]]:
    """Actual recorded values with their capture times, oldest first."""
    points: list[dict[str, object]] = []
    for entry in readings.get(sensor_key, []):
        value = normalize_numeric_value(entry["payload"].get(metric_key))
        captured_at = str(entry.get("capturedAt") or "").strip()
        if value is None or not captured_at:
            continue
        points.append({"value": float(value), "capturedAt": captured_at})
    return points


def report_row_metric_values(
    readings: dict[str, list[dict[str, object]]],
    row_keys: list[str],
    suffix: str,
    metric_key: str,
) -> list[float]:
    """Fall back to the per-row sensors when the shared dashboard key is idle."""
    values: list[float] = []
    for row_key in row_keys:
        values.extend(report_metric_values(readings, f"{row_key}-{suffix}", metric_key))
    return values


def report_row_metric_points(
    readings: dict[str, list[dict[str, object]]],
    row_keys: list[str],
    suffix: str,
    metric_key: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, object]]:
    """Average simultaneous row readings without inventing chart positions.

    A report for all rows has several physical probes for one metric. Their
    recorded values are averaged per real day/hour bucket, and the latest
    capture time in that bucket remains the x coordinate. Nothing is padded or
    interpolated between missing buckets.
    """
    bucket_length = 10 if (end - start).days + 1 > 3 else 13
    buckets: dict[str, dict[str, object]] = {}
    for row_key in row_keys:
        for point in report_metric_points(readings, f"{row_key}-{suffix}", metric_key):
            captured_at = str(point["capturedAt"])
            bucket = buckets.setdefault(
                captured_at[:bucket_length], {"values": [], "capturedAt": captured_at}
            )
            values = bucket["values"]
            assert isinstance(values, list)
            values.append(float(point["value"]))
            if captured_at > str(bucket["capturedAt"]):
                bucket["capturedAt"] = captured_at

    return [
        {
            "value": round(sum(bucket["values"]) / len(bucket["values"]), 4),
            "capturedAt": bucket["capturedAt"],
        }
        for _, bucket in sorted(buckets.items())
        if bucket["values"]
    ]


def report_period_metric_statistics(
    connection: sqlite3.Connection,
    start: datetime,
    end: datetime,
    row_keys: list[str],
    sampled_readings: dict[str, list[dict[str, object]]] | None = None,
) -> dict[str, dict[str, float | int | None]]:
    """Exact period averages and sample counts from every numeric reading.

    The graph is intentionally thinned to one real point per visible bucket,
    but a tile labelled "Average" must include every reading in the requested
    window. JSON extraction differs between SQLite and PostgreSQL, so only the
    numeric expression varies; both backends execute one grouped query.
    """

    fields = ("value", "ph", "ec", "temp", "humidity")

    def numeric_expression(field: str) -> str:
        if postgres_backend_enabled():
            return (
                "CASE WHEN jsonb_typeof(reading_payload_json -> "
                f"'{field}') = 'number' THEN "
                f"CAST(reading_payload_json ->> '{field}' AS DOUBLE PRECISION) END"
            )
        return (
            "CASE WHEN json_type(reading_payload_json, "
            f"'$.{field}') IN ('integer', 'real') THEN "
            f"CAST(json_extract(reading_payload_json, '$.{field}') AS REAL) END"
        )

    def query_statistics(
        requests: dict[str, set[str]],
    ) -> dict[str, sqlite3.Row]:
        """Aggregate only fields that a sensor can actually provide.

        Separate UNION branches let the composite sensor/time index serve each
        sensor directly. More importantly, an all-row report does not scan the
        four high-volume RS485 streams when the shared pH and EC streams are
        available; fallback sensors are queried only when they are needed.
        """
        if not requests:
            return {}
        branches: list[str] = []
        parameters: list[object] = []
        for sensor_key, requested_fields in requests.items():
            columns = ["sensor_key"]
            for field in fields:
                if field in requested_fields:
                    expression = numeric_expression(field)
                    columns.extend(
                        (
                            f"AVG({expression}) AS average_{field}",
                            f"COUNT({expression}) AS count_{field}",
                        )
                    )
                else:
                    columns.extend(
                        (
                            f"CAST(NULL AS DOUBLE PRECISION) AS average_{field}",
                            f"0 AS count_{field}",
                        )
                    )
            branches.append(
                f"""
                SELECT {', '.join(columns)}
                FROM sensor_readings
                WHERE sensor_key = ? AND captured_at >= ? AND captured_at <= ?
                GROUP BY sensor_key
                """
            )
            parameters.extend((sensor_key, start.isoformat(), end.isoformat()))
        rows = connection.execute(
            "\nUNION ALL\n".join(branches) + "\nORDER BY sensor_key ASC",
            parameters,
        ).fetchall()
        return {str(row["sensor_key"]): row for row in rows}

    def add_request(requests: dict[str, set[str]], sensor_key: str, *requested: str) -> None:
        requests.setdefault(sensor_key, set()).update(requested)

    single_row = len(row_keys) == 1
    primary_requests: dict[str, set[str]] = {"dht22": {"temp", "humidity"}}
    if single_row:
        # Row probes store the reading under "moisture"; only the shared
        # dashboard sensor uses "value". Same reason as REPORT_AVERAGE_METRICS.
        add_request(primary_requests, f"{row_keys[0]}-moisture", "moisture")
        add_request(primary_requests, f"{row_keys[0]}-rs485", "ph", "ec")
    else:
        add_request(primary_requests, "moisture", "value")
        add_request(primary_requests, "ph", "value")
        add_request(primary_requests, "ec", "value")

    by_sensor = query_statistics(primary_requests)

    def has_samples(sensor_key: str, field: str) -> bool:
        row = by_sensor.get(sensor_key)
        return bool(row and int(row[f"count_{field}"] or 0))

    fallback_requests: dict[str, set[str]] = {}

    def sampled_has(sensor_key: str, field: str) -> bool:
        # A bounded graph sample is already available in both preview/export.
        # If it contains no numeric value for a fallback stream, avoid scanning
        # that entire high-volume stream only to rediscover that it is empty.
        return sampled_readings is None or bool(
            report_metric_values(sampled_readings, sensor_key, field)
        )

    if single_row:
        row_key = row_keys[0]
        if not has_samples(f"{row_key}-moisture", "moisture") and sampled_has(
            "moisture", "value"
        ):
            add_request(fallback_requests, "moisture", "value")
        if not has_samples(f"{row_key}-rs485", "ph") and sampled_has("ph", "value"):
            add_request(fallback_requests, "ph", "value")
        if not has_samples(f"{row_key}-rs485", "ec") and sampled_has("ec", "value"):
            add_request(fallback_requests, "ec", "value")
    else:
        if not has_samples("moisture", "value"):
            for row_key in row_keys:
                sensor_key = f"{row_key}-moisture"
                if sampled_has(sensor_key, "moisture"):
                    add_request(fallback_requests, sensor_key, "moisture")
        missing_ph = not has_samples("ph", "value")
        missing_ec = not has_samples("ec", "value")
        if missing_ph or missing_ec:
            for row_key in row_keys:
                sensor_key = f"{row_key}-rs485"
                add_request(
                    fallback_requests,
                    sensor_key,
                    *(["ph"] if missing_ph and sampled_has(sensor_key, "ph") else []),
                    *(["ec"] if missing_ec and sampled_has(sensor_key, "ec") else []),
                )
                if not fallback_requests.get(sensor_key):
                    fallback_requests.pop(sensor_key, None)
    by_sensor.update(query_statistics(fallback_requests))

    def combined(
        shared_sensor: str,
        shared_field: str,
        fallback_sensors: list[str],
        fallback_field: str,
    ) -> dict[str, float | int | None]:
        shared = by_sensor.get(shared_sensor)
        shared_count = int(shared[f"count_{shared_field}"] or 0) if shared else 0
        # A single-row report must use that row's sensors even when a shared
        # farm sensor also exists. Shared readings are preferred only for an
        # all-row report, matching what the report filter promises.
        use_shared = shared_count > 0 and (len(row_keys) > 1 or not fallback_sensors)
        sources = [(shared, shared_field)] if use_shared else [
            (by_sensor.get(sensor_key), fallback_field) for sensor_key in fallback_sensors
        ]
        total = 0
        weighted_sum = 0.0
        for row, field in sources:
            if not row:
                continue
            count = int(row[f"count_{field}"] or 0)
            average = normalize_numeric_value(row[f"average_{field}"])
            if not count or average is None:
                continue
            total += count
            weighted_sum += float(average) * count
        if not total and shared_count and not use_shared:
            shared_average = normalize_numeric_value(shared[f"average_{shared_field}"])
            if shared_average is not None:
                total = shared_count
                weighted_sum = float(shared_average) * shared_count
        return {
            "average": round(weighted_sum / total, 2) if total else None,
            "count": total,
        }

    return {
        "moisture": combined(
            "moisture", "value", [f"{key}-moisture" for key in row_keys], "moisture"
        ),
        "ph": combined("ph", "value", [f"{key}-rs485" for key in row_keys], "ph"),
        "ec": combined("ec", "value", [f"{key}-rs485" for key in row_keys], "ec"),
        "temp": combined("dht22", "temp", [], "temp"),
        "humidity": combined("dht22", "humidity", [], "humidity"),
    }


def downsample_series(values: list[float], buckets: int = REPORT_TREND_POINTS) -> list[float]:
    """Average the readings into a fixed number of points.

    A month of readings is far more points than a 500pt-wide chart can show, and
    drawing all of them turns the line into a solid band.
    """
    if not values:
        return []
    if len(values) <= buckets:
        return [round(value, 2) for value in values]

    size = len(values) / buckets
    points: list[float] = []
    for index in range(buckets):
        window = values[int(index * size):int((index + 1) * size)] or [values[-1]]
        points.append(round(sum(window) / len(window), 2))
    return points


def scale_for_chart(values: list[float], maximum: float) -> list[float]:
    """Map a series onto the shared 0-100 axis the PDF chart draws."""
    if not values or maximum <= 0:
        return []
    return [max(0.0, min(100.0, value / maximum * 100)) for value in values]


def report_average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def build_report_dataset(payload: dict[str, object]) -> dict[str, object]:
    """Assemble everything both documents need, from one pass over the data."""
    sections = normalize_report_sections(payload.get("sections"))
    start, end = report_range_bounds(payload)
    row_keys = report_row_filter(payload)
    try:
        offset_minutes = int(payload.get("timezoneOffsetMinutes") or 0)
    except (TypeError, ValueError):
        offset_minutes = 0

    with connect_database() as connection:
        readings = collect_report_readings(connection, start, end, row_keys)
        cultivations = [
            build_cultivation_payload(item) for item in list_cultivations(connection)
        ]
        registry_rows = list_sensor_registry(connection)
        # Everything that finished inside the period, however it finished.
        # Ordered oldest-first so the report reads as a sequence of events
        # rather than in reverse.
        finished_cultivations = connection.execute(
            f"""
            SELECT {', '.join(HARVEST_COLUMNS)}
            FROM cultivation_harvests
            WHERE harvested_at >= ? AND harvested_at <= ?
            ORDER BY harvested_at ASC
            LIMIT ?
            """,  # nosec B608 - HARVEST_COLUMNS is a module constant, values are bound
            (start.isoformat(), end.isoformat(), REPORT_TABLE_ROW_LIMIT),
        ).fetchall()
        irrigation_runs = connection.execute(
            """
            SELECT
                id, channel_key, mode, status, duration_seconds, started_at, ended_at, notes,
                COUNT(*) OVER() AS period_count,
                COALESCE(SUM(duration_seconds) OVER(), 0) AS period_duration_seconds
            FROM irrigation_runs
            WHERE started_at >= ? AND started_at <= ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (start.isoformat(), end.isoformat(), REPORT_PDF_TABLE_ROW_LIMIT),
        ).fetchall()
        notification_rows = connection.execute(
            """
            SELECT type, message, created_at
            FROM notifications
            WHERE created_at >= ? AND created_at <= ? AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (start.isoformat(), end.isoformat(), REPORT_TABLE_ROW_LIMIT),
        ).fetchall()

    def selected_metric_points(
        shared_key: str, row_suffix: str, field: str
    ) -> tuple[list[dict[str, object]], str]:
        shared_points = report_metric_points(readings, shared_key, "value")
        row_points = report_row_metric_points(
            readings, row_keys, row_suffix, field, start, end
        )
        if len(row_keys) > 1 and shared_points:
            return shared_points, "Shared farm sensor"
        if row_points:
            source = cultivation_row_label(row_keys[0]) if len(row_keys) == 1 else "Row average"
            return row_points, source
        return shared_points, "Shared farm sensor"

    # "moisture" as the row field, for the reason given on REPORT_AVERAGE_METRICS.
    moisture, moisture_source = selected_metric_points("moisture", "moisture", "moisture")
    ph_values, ph_source = selected_metric_points("ph", "rs485", "ph")
    ec_values, ec_source = selected_metric_points("ec", "rs485", "ec")
    temperature = report_metric_points(readings, "dht22", "temp")
    humidity = report_metric_points(readings, "dht22", "humidity")
    metric_statistics = report_sampled_metric_statistics(readings, row_keys)

    cultivation_by_row = {
        str(item.get("rowKey") or ""): item for item in cultivations
    }

    return {
        "sections": sections,
        "start": start,
        "end": end,
        "rowKeys": row_keys,
        "offsetMinutes": offset_minutes,
        "readings": readings,
        "cultivations": cultivations,
        "cultivationByRow": cultivation_by_row,
        "registryRows": registry_rows,
        "irrigationRuns": irrigation_runs,
        "finishedCultivations": finished_cultivations,
        "notifications": notification_rows,
        "series": {
            "moisture": moisture,
            "ph": ph_values,
            "ec": ec_values,
            "temp": temperature,
            "humidity": humidity,
        },
        "seriesSources": {
            "moisture": moisture_source,
            "ph": ph_source,
            "ec": ec_source,
            "temp": "Shared farm sensor",
        },
        "averages": {key: value["average"] for key, value in metric_statistics.items()},
        "sampleCounts": {key: value["count"] for key, value in metric_statistics.items()},
    }


def score_row_health(
    *,
    row_key: str,
    label: str,
    crop_name: str,
    cultivation: dict[str, object] | None,
    moisture: list[float],
    ph_values: list[float],
    ec_values: list[float],
) -> dict[str, object]:
    """Grade one row against its crop's target ranges.

    Shared by the preview and the exported document so a row can never be
    graded one way on screen and another way in the file. A row with no
    cultivation, no readings, or no target range says so rather than showing a
    number, because a fabricated score is worse than an honest blank.
    """
    sample_count = len(moisture) + len(ph_values) + len(ec_values)
    blank = {
        "rowKey": row_key,
        "label": label,
        "crop": crop_name,
        "gradeColor": icucrops_reports.INK_SOFT,
        "score": None,
        "samples": sample_count,
    }

    if not cultivation:
        return {**blank, "crop": "No cultivation", "grade": "Idle", "trend": "Not planted", "samples": sample_count}
    if not sample_count:
        return {**blank, "grade": "No data", "trend": "No readings"}

    parameters = cultivation.get("parameters")
    parameters = parameters if isinstance(parameters, dict) else {}
    inside = 0
    total = 0
    for metric_key, values in (("moisture", moisture), ("ph", ph_values), ("ec", ec_values)):
        bounds = parameters.get(metric_key)
        bounds = bounds if isinstance(bounds, dict) else {}
        minimum = normalize_numeric_value(bounds.get("min"))
        maximum = normalize_numeric_value(bounds.get("max"))
        if minimum is None or maximum is None or not values:
            continue
        for value in values:
            total += 1
            if float(minimum) <= value <= float(maximum):
                inside += 1

    if not total:
        return {**blank, "grade": "No target", "trend": f"{sample_count} readings"}

    score = int(round(inside / total * 100))
    if score >= 90:
        grade, color = "Excellent", icucrops_reports.GREEN_600
    elif score >= 75:
        grade, color = "Good", icucrops_reports.GREEN_600
    elif score >= 55:
        grade, color = "Fair", icucrops_reports.AMBER
    else:
        grade, color = "Needs care", icucrops_reports.RED

    # The trend compares the first and last thirds of the sample, so a row that
    # is recovering does not read the same as one that is slipping.
    trend = "Steady"
    if len(moisture) >= 6:
        third = max(1, len(moisture) // 3)
        early = sum(moisture[:third]) / third
        late = sum(moisture[-third:]) / third
        if late - early > 3:
            trend = "Improving"
        elif early - late > 3:
            trend = "Declining"

    return {
        "rowKey": row_key,
        "label": label,
        "crop": crop_name,
        "grade": grade,
        "gradeColor": color,
        "score": score,
        "trend": trend,
        "samples": sample_count,
    }


def report_row_health(dataset: dict[str, object]) -> list[dict[str, object]]:
    """A per-row health card for the exported document, over the whole window."""
    readings = dataset["readings"]
    cultivation_by_row = dataset["cultivationByRow"]
    cards: list[dict[str, object]] = []

    for row_key in dataset["rowKeys"]:
        cultivation = cultivation_by_row.get(row_key)
        crop_name = ""
        if cultivation:
            crop_name = str(
                cultivation.get("crop")
                or cultivation.get("customPlantName")
                or "Active cultivation"
            )

        cards.append(
            score_row_health(
                row_key=row_key,
                label=cultivation_row_label(row_key),
                crop_name=crop_name,
                cultivation=cultivation,
                # The row probes publish this as "moisture"; "value" belongs to
                # the shared dashboard sensor. Reading the wrong one graded
                # every row on pH and EC alone.
                moisture=report_metric_values(readings, f"{row_key}-moisture", "moisture"),
                ph_values=report_metric_values(readings, f"{row_key}-rs485", "ph"),
                ec_values=report_metric_values(readings, f"{row_key}-rs485", "ec"),
            )
        )

    return cards


def report_sensor_health(dataset: dict[str, object]) -> dict[str, object]:
    """Counts of registered sensors and how many are currently powered."""
    rows = [
        row
        for row in dataset["registryRows"]
        if str(row["category"] or "").strip() in {"dashboard", "row", "shared"}
    ]
    powered = [row for row in rows if str(row["power_state"] or "").strip().lower() == "on"]
    return {
        "total": len(rows),
        "online": len(powered),
        "offline": len(rows) - len(powered),
    }


def report_irrigation_rows(dataset: dict[str, object]) -> dict[str, object]:
    """The irrigation table, shared by both documents."""
    offset = dataset["offsetMinutes"]
    channel_labels = {
        str(channel["channel_key"]).strip(): str(channel["label"])
        for channel in DEFAULT_IRRIGATION_CHANNELS
    }

    rows: list[list[object]] = []
    shown_seconds = 0
    for run in dataset["irrigationRuns"]:
        duration = normalize_numeric_value(run["duration_seconds"]) or 0
        shown_seconds += int(duration)
        channel_key = str(run["channel_key"] or "")
        rows.append(
            [
                format_report_day(run["started_at"], offset),
                format_report_clock(run["started_at"], offset),
                format_report_clock(run["ended_at"], offset) or "Running",
                int(duration),
                channel_labels.get(channel_key) or irrigation_channel_label(channel_key),
                str(run["mode"] or "").title(),
                str(run["status"] or "").title(),
            ]
        )

    period_count = len(rows)
    total_seconds = shown_seconds
    if dataset["irrigationRuns"]:
        first = dataset["irrigationRuns"][0]
        try:
            period_count = max(period_count, int(first["period_count"] or 0))
            total_seconds = int(first["period_duration_seconds"] or shown_seconds)
        except (KeyError, TypeError, ValueError):
            # Hand-built report models and older local databases may not carry
            # the window totals; the visible rows remain a correct fallback.
            pass

    return {
        "headers": [
            "Date",
            "Start Time",
            "End Time",
            "Duration (s)",
            "Channel",
            "Mode",
            "Status",
        ],
        "pdfRows": rows,
        "omittedFromPdf": max(0, period_count - len(rows)),
        "widths": [1.15, 1.0, 1.0, 1.0, 1.1, 0.95, 1.0],
        "rows": rows,
        "total": (
            ["Total (Period)", "", "", total_seconds, "", "", f"{period_count} runs"]
            if rows
            else []
        ),
        "totalSeconds": total_seconds,
    }


def irrigation_channel_label(channel_key: str) -> str:
    labels = {
        "water": "Water",
        "fertilizer": "Fertilizer",
        "limeSolution": "Lime Solution",
    }
    return labels.get(str(channel_key or "").strip(), str(channel_key or "").title() or "Channel")


def report_alert_cards(dataset: dict[str, object]) -> dict[str, object]:
    """The alerts table, tallied by condition.

    This was four cards, which was the wrong shape twice over. A farm running
    for a week raises far more than four distinct alerts, and the other four
    were simply dropped -- the page said "Row 4 soil pH is too acidic" and
    said nothing at all about rows 1 and 2. And a card per alert cannot show a
    count next to a date next to a severity without becoming a paragraph.

    So it is a table now, the same one Irrigation Activity uses: every
    condition the period raised, one row each, with how many times it fired.
    It paginates the same way, so a long list runs onto the next page instead
    of being cut at four.

    Rows are still grouped by condition rather than listed raw. Twenty-two
    occurrences of one row's pH is one line that says 22, not twenty-two
    lines -- which is the tally the operator actually wants and what makes the
    table readable at a glance.
    """
    offset = dataset["offsetMinutes"]
    buckets: dict[str, dict[str, object]] = {}
    tones = {
        "warning": (icucrops_reports.AMBER, "Medium"),
        "danger": (icucrops_reports.RED, "High"),
        "critical": (icucrops_reports.RED, "High"),
        "alert": (icucrops_reports.AMBER, "Medium"),
        "info": (icucrops_reports.BLUE, "Low"),
        "success": (icucrops_reports.GREEN_600, "Low"),
    }

    for row in dataset["notifications"]:
        notification_type = str(row["type"] or "info").strip().lower()
        color, severity = tones.get(notification_type, (icucrops_reports.AMBER, "Medium"))
        message = str(row["message"] or "").strip()
        if not message:
            continue
        # Repeats of one alert differ only in their trailing numbers, so the
        # leading clause groups "Row 2 soil moisture is low" raised twelve
        # times into a single line.
        #
        # The colon is what separates the condition from its numbers, and it is
        # tried first. Splitting on the full stop alone cut crop-parameter
        # alerts at the decimal point instead -- "Row 1 soil moisture is low:
        # 42" and "... 41" are the same condition but grouped as two.
        title = (message.split(":", 1)[0] if ":" in message else message.split(".")[0]).strip()
        title = title or message
        entry = buckets.setdefault(
            title.lower(),
            {
                "title": title,
                "severity": severity,
                "color": color,
                "count": 0,
                "firstSeen": row["created_at"],
                "lastSeen": row["created_at"],
                "type": notification_type,
            },
        )
        entry["count"] = int(entry["count"]) + 1
        # The query orders newest first, so the row that created the bucket is
        # this condition's most recent occurrence and every row after it is
        # older. That makes lastSeen fixed at creation and firstSeen the one
        # that keeps moving back.
        entry["firstSeen"] = row["created_at"]

    # Severity first so a high alert is never pushed onto a later page by a
    # chattier informational one, then by how often it fired.
    severity_rank = {"High": 0, "Medium": 1, "Low": 2}
    ordered = sorted(
        buckets.values(),
        key=lambda item: (severity_rank.get(str(item["severity"]), 3), -int(item["count"])),
    )

    rows: list[list[object]] = []
    for entry in ordered:
        first = format_report_day(entry["firstSeen"], offset)
        last = format_report_day(entry["lastSeen"], offset)
        rows.append(
            [
                str(entry["title"]),
                str(entry["severity"]),
                int(entry["count"]),
                first or "-",
                last or "-",
            ]
        )

    total_occurrences = sum(int(entry["count"]) for entry in ordered)
    return {
        # "Times", not "Occurrences". The column counts how many times a
        # condition fired, and that is the word a grower reading the page
        # already uses for it -- "Occurrences" is the longer, more clinical
        # word for the same count, and being the longest header in the table
        # it also forced the column wider than the two-digit numbers under it.
        "headers": ["Alert", "Severity", "Times", "First Seen", "Last Seen"],
        # The condition needs the room; the four tallies beside it are short.
        # Times is the narrowest of them -- it holds a count, never more than
        # three digits, and the header no longer has to fit "Occurrences" --
        # so the room it gives up goes to the two date columns, which have to
        # hold "Sep 22, 2026" without truncating.
        "widths": [2.9, 0.95, 0.6, 1.25, 1.25],
        "rows": rows,
        "pdfRows": rows[:REPORT_PDF_TABLE_ROW_LIMIT],
        "omittedFromPdf": max(0, len(rows) - REPORT_PDF_TABLE_ROW_LIMIT),
        "total": (
            ["Total (Period)", "", total_occurrences, "", f"{len(rows)} alert(s)"]
            if rows
            else []
        ),
    }


def report_field(item: object, key: str, default: object = None) -> object:
    """One field of a report row, whether it is a sqlite3.Row or a dict.

    sqlite3.Row indexes like a mapping but has no .get, so the usual
    ``item.get(key)`` raises AttributeError on a database row and ``item[key]``
    raises IndexError on a row that predates a column. Both shapes reach the
    report builders -- the local query returns Row objects, the sync and the
    tests pass dicts -- so the access has to cope with either.
    """
    try:
        value = item[key]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def report_cultivation_history(dataset: dict[str, object]) -> dict[str, object]:
    """Every cultivation that finished in the period, and how it finished.

    The report could say what is growing now and nothing about what is over.
    A crop that reached harvest and one that was scrapped both simply vanished
    from the active list, so the page could not answer the two questions a
    grower actually asks of a season: how many made it, and which ones did
    not.

    One row per finished cultivation, with the outcome, how long it grew, and
    whether the parameters were the recommended ones or the farm's own --
    which is the column that makes a run of failures worth reading, because it
    says whether the custom ranges were involved.
    """
    offset = dataset["offsetMinutes"]
    rows: list[list[object]] = []
    harvested = removed = 0
    on_schedule = 0

    for item in dataset["finishedCultivations"]:
        outcome = str(item["outcome"] or "harvested").strip().lower()
        is_harvest = outcome != "removed"
        if is_harvest:
            harvested += 1
            if int(item["on_schedule"] or 0):
                on_schedule += 1
        else:
            removed += 1
        # "Custom" or "Recommended", capitalised for the column. The stored
        # value is lowercase and is what the cultivation form wrote.
        mode = str(item["parameter_mode"] or "").strip().lower()
        rows.append(
            [
                cultivation_row_label(str(item["row_key"] or "")),
                str(item["crop_name"] or "").strip(),
                "Harvested" if is_harvest else "Removed",
                # When it went in. Without it the table gave a finish date and a
                # day count, leaving the reader to subtract one from the other
                # to learn when a crop was planted.
                #
                # Read defensively, unlike the fields above: those come from
                # HARVEST_COLUMNS on every path, while a harvest row that
                # arrived over the sync, or one written before this column
                # existed, can be missing it. A report is worth printing with
                # one date unknown; it is not worth failing to render.
                format_report_day(report_field(item, "planting_date"), offset) or "-",
                format_report_day(item["harvested_at"], offset) or "-",
                int(item["days_grown"] or 0),
                # A removed crop was never judged against its harvest date, so
                # the schedule column is blank for it rather than claiming an
                # answer the outcome already contradicts.
                ("On schedule" if int(item["on_schedule"] or 0) else "Late") if is_harvest else "-",
                "Custom" if mode == "custom" else "Recommended",
            ]
        )

    total = len(rows)
    return {
        "headers": [
            "Row",
            "Crop",
            "Outcome",
            "Planted",
            "Finished",
            "Days Grown",
            "Schedule",
            "Parameters",
        ],
        # Eight columns across the same width, so the two date columns get
        # enough room for "Sep 22, 2026" without the crop name truncating.
        "widths": [0.7, 1.2, 0.9, 1.0, 1.0, 0.85, 0.85, 0.95],
        "rows": rows,
        "pdfRows": rows[:REPORT_PDF_TABLE_ROW_LIMIT],
        "omittedFromPdf": max(0, total - REPORT_PDF_TABLE_ROW_LIMIT),
        # One entry per header, so nothing lands under the wrong column now
        # that there are eight. Both figures cannot share the Outcome cell --
        # "1 harvested, 3 removed" is 83pt against a 50pt column and would
        # truncate -- so the removals sit in the next wide cell along.
        "total": (
            [
                "Total (Period)",
                "",
                f"{harvested} harvested",
                f"{removed} removed",
                "",
                "",
                "",
                "",
            ]
            if rows
            else []
        ),
        # The chart reads these, and so does the summary line above it.
        "harvested": harvested,
        "removed": removed,
        "onSchedule": on_schedule,
        "finished": total,
    }


def build_report_document_model(dataset: dict[str, object]) -> dict[str, object]:
    """Turn the dataset into the shape both writers consume."""
    sections = dataset["sections"]
    averages = dataset["averages"]
    sample_counts = dataset["sampleCounts"]
    series = dataset["series"]
    series_sources = dataset.get("seriesSources", {})
    offset = dataset["offsetMinutes"]

    def metric_tile(
        label: str, value: float | None, unit: str, suffix: str = "", sample_count: int = 0
    ) -> dict[str, object]:
        if value is None:
            return {"label": label, "value": "n/a", "unit": "No readings", "sampleCount": 0}
        return {
            "label": label,
            "value": f"{value:g}{suffix}",
            "unit": unit,
            "sampleCount": sample_count,
        }

    metrics = [
        metric_tile("Sampled Soil Moisture", averages["moisture"], "%", sample_count=int(sample_counts["moisture"])),
        metric_tile("Sampled pH", averages["ph"], "pH", sample_count=int(sample_counts["ph"])),
        metric_tile("Sampled EC", averages["ec"], "mS/cm", sample_count=int(sample_counts["ec"])),
        metric_tile("Sampled Temperature", averages["temp"], "C", sample_count=int(sample_counts["temp"])),
        metric_tile("Sampled Humidity", averages["humidity"], "%", sample_count=int(sample_counts["humidity"])),
    ]

    # Each chart carries raw values and capture times. The PDF renderer gives
    # every metric its own labelled axis; values are never converted to an
    # arbitrary percentage or evenly spaced when readings are missing.
    chart_series = [
        {
            "label": f"Soil Moisture - {series_sources.get('moisture', 'Recorded readings')}",
            "unit": "%",
            "color": icucrops_reports.GREEN_500,
            "points": series["moisture"],
        },
        {
            "label": f"pH - {series_sources.get('ph', 'Recorded readings')}",
            "unit": "pH",
            "color": icucrops_reports.BLUE,
            "points": series["ph"],
        },
        {
            "label": f"EC - {series_sources.get('ec', 'Recorded readings')}",
            "unit": "mS/cm",
            "color": icucrops_reports.AMBER,
            "points": series["ec"],
        },
        {
            "label": f"Temperature - {series_sources.get('temp', 'Recorded readings')}",
            "unit": "C",
            "color": (0.46, 0.40, 0.85),
            "points": series["temp"],
        },
    ]
    start = dataset["start"]
    end = dataset["end"]
    health = report_sensor_health(dataset)
    irrigation = report_irrigation_rows(dataset)

    return {
        "farmName": report_farm_name(),
        "period": icucrops_reports.format_report_period(
            start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        ),
        "generatedAt": icucrops_reports.local_timestamp_label(offset),
        "sections": sections,
        "metrics": metrics,
        "series": chart_series,
        "chartStart": start.isoformat(),
        "chartEnd": end.isoformat(),
        "rowHealth": report_row_health(dataset) if "cultivations" in sections else [],
        "cultivationHistory": (
            report_cultivation_history(dataset) if "cultivations" in sections else {}
        ),
        "irrigation": irrigation,
        "alerts": report_alert_cards(dataset) if "alerts" in sections else [],
        "sensorHealth": [
            {"label": "Total Sensors", "value": str(health["total"]), "color": icucrops_reports.GREEN_700},
            {"label": "Powered On", "value": str(health["online"]), "color": icucrops_reports.GREEN_600},
            {
                "label": "Powered Off",
                "value": str(health["offline"]),
                "color": icucrops_reports.AMBER if health["offline"] else icucrops_reports.GREEN_600,
            },
        ],
    }


def report_farm_name() -> str:
    return str(os.getenv("ICUCROPS_FARM_NAME", "").strip() or "Sarate Agriculture Farm")


def build_report_workbook_sheets(dataset: dict[str, object], model: dict[str, object]) -> list[dict[str, object]]:
    """One sheet per selected section, plus a summary that always leads.

    Values are written as numbers wherever they are numbers so the workbook can
    be sorted, filtered and summed after download.
    """
    sections = dataset["sections"]
    offset = dataset["offsetMinutes"]
    averages = dataset["averages"]
    sheets: list[dict[str, object]] = []

    summary_rows: list[list[object]] = []
    for label, key, unit in (
        ("Average Soil Moisture", "moisture", "%"),
        ("Average pH", "ph", ""),
        ("Average EC", "ec", "mS/cm"),
        ("Average Temperature", "temp", "C"),
        ("Average Humidity", "humidity", "%"),
    ):
        value = averages[key]
        summary_rows.append([label, value if value is not None else "No readings", unit])

    sheets.append(
        {
            "name": "Summary",
            "widths": [30, 16, 12],
            "blocks": [
                {
                    "kind": "title",
                    "text": "ICuCrops Farm Monitoring Report",
                    "lines": [
                        model["farmName"],
                        f"Reporting Period: {model['period']}",
                        f"Generated: {model['generatedAt']}",
                    ],
                },
                {
                    "kind": "table",
                    "title": "Period Averages",
                    "headers": ["Metric", "Value", "Unit"],
                    "rows": summary_rows,
                },
            ],
        }
    )

    if "sensors" in sections:
        readings = dataset["readings"]
        rows: list[list[object]] = []
        for sensor_key, entries in sorted(readings.items()):
            for entry in entries[-REPORT_TABLE_ROW_LIMIT:]:
                payload = entry["payload"]
                rows.append(
                    [
                        format_report_day(entry["capturedAt"], offset),
                        format_report_clock(entry["capturedAt"], offset),
                        sensor_key,
                        normalize_numeric_value(payload.get("value")),
                        normalize_numeric_value(payload.get("ph")),
                        normalize_numeric_value(payload.get("ec")),
                        normalize_numeric_value(payload.get("temp")),
                        normalize_numeric_value(payload.get("humidity")),
                    ]
                )
        rows = rows[:REPORT_TABLE_ROW_LIMIT]
        sheets.append(
            {
                "name": "Sensor Readings",
                "widths": [15, 12, 20, 12, 10, 10, 12, 12],
                "freezeRow": 1,
                "blocks": [
                    {
                        "kind": "table",
                        "headers": [
                            "Date",
                            "Time",
                            "Sensor",
                            "Value",
                            "pH",
                            "EC",
                            "Temp (C)",
                            "Humidity (%)",
                        ],
                        "rows": rows,
                    }
                ],
            }
        )

    if "irrigation" in sections:
        irrigation = model["irrigation"]
        sheets.append(
            {
                "name": "Irrigation History",
                "widths": [16, 13, 13, 14, 14, 12, 13],
                "freezeRow": 1,
                "blocks": [
                    {
                        "kind": "table",
                        "headers": irrigation["headers"],
                        "rows": irrigation["rows"],
                        "total": irrigation["total"],
                    }
                ],
            }
        )

    if "cultivations" in sections:
        cultivation_history = report_cultivation_history(dataset)
        cultivation_rows = [
            [
                cultivation_row_label(str(item.get("rowKey") or "")),
                str(item.get("crop") or item.get("customPlantName") or ""),
                str(item.get("plantingDate") or ""),
                str(item.get("harvestDate") or ""),
                normalize_numeric_value(item.get("daysToHarvest")),
            ]
            for item in dataset["cultivations"]
        ]
        health_rows = [
            [
                card["label"],
                card["crop"],
                card["grade"],
                card["score"] if card["score"] is not None else "",
                card["trend"],
                card["samples"],
            ]
            for card in (model["rowHealth"] or report_row_health(dataset))
        ]
        sheets.append(
            {
                "name": "Cultivation",
                "widths": [16, 20, 15, 15, 16, 12],
                "blocks": [
                    {
                        "kind": "table",
                        "title": "Active Cultivations",
                        "headers": ["Row", "Crop", "Planting Date", "Harvest Date", "Days to Harvest"],
                        "rows": cultivation_rows,
                    },
                    {
                        "kind": "table",
                        "title": "Row Health",
                        "headers": ["Row", "Crop", "Grade", "Score (%)", "Trend", "Readings"],
                        "rows": health_rows,
                    },
                    {
                        # What finished in the period and how, beside what is
                        # still growing. The workbook carries every row; the
                        # PDF prints the most recent slice of the same table.
                        "kind": "table",
                        "title": "Cultivation History",
                        "headers": list(cultivation_history["headers"]),
                        "rows": list(cultivation_history["rows"]),
                        "total": list(cultivation_history["total"]) or None,
                    },
                ],
            }
        )

    if "alerts" in sections:
        alert_rows = [
            [
                format_report_day(row["created_at"], offset),
                format_report_clock(row["created_at"], offset),
                str(row["type"] or "").title(),
                str(row["message"] or ""),
            ]
            for row in dataset["notifications"]
        ]
        # Two blocks, because they answer different questions. The tally is
        # what the PDF prints and what someone scanning for "which row keeps
        # going out" needs; the log below it is every entry with its own
        # timestamp, which is what someone reconstructing a particular
        # afternoon needs. The workbook has room for both, so neither has to
        # be thrown away for the other.
        alerts_table = report_alert_cards(dataset)
        sheets.append(
            {
                "name": "Alerts",
                "widths": [52, 12, 14, 15, 15],
                "freezeRow": 1,
                "blocks": [
                    {
                        "kind": "table",
                        "title": "Alert Summary",
                        "headers": list(alerts_table["headers"]),
                        "rows": list(alerts_table["rows"]),
                        "total": list(alerts_table["total"]) or None,
                    },
                    {
                        "kind": "table",
                        "title": "Full Alert Log",
                        "headers": ["Date", "Time", "Type", "Message"],
                        "rows": alert_rows,
                    },
                ],
            }
        )

    if "health" in sections:
        sheets.append(
            {
                "name": "Sensor Health",
                "widths": [24, 22, 14, 12, 14],
                "freezeRow": 1,
                "blocks": [
                    {
                        "kind": "table",
                        "headers": ["Sensor", "Device", "Row", "Category", "Power"],
                        "rows": [
                            [
                                str(row["display_name"] or row["sensor_key"]),
                                str(row["device_name"] or ""),
                                cultivation_row_label(str(row["row_key"] or "")) if row["row_key"] else "Shared",
                                str(row["category"] or "").title(),
                                str(row["power_state"] or "").title(),
                            ]
                            for row in dataset["registryRows"]
                        ],
                    }
                ],
            }
        )

    return sheets


def report_file_stem(dataset: dict[str, object]) -> str:
    start = dataset["start"].strftime("%Y%m%d")
    end = dataset["end"].strftime("%Y%m%d")
    return f"ICuCrops-Farm-Report-{start}-{end}"


def api_build_report(payload: dict[str, object], report_format: str) -> tuple[HTTPStatus, object]:
    """Produce the requested report document.

    Returns either an error payload or the finished bytes with the filename and
    content type the download needs.
    """
    normalized_format = str(report_format or "").strip().lower()
    if normalized_format != "pdf":
        return HTTPStatus.BAD_REQUEST, {"message": "Reports are available as PDF only."}

    report_started = time.perf_counter()
    try:
        dataset = build_report_dataset(payload)
        dataset_seconds = time.perf_counter() - report_started
        model = build_report_document_model(dataset)
    except Exception as error:
        if not report_database_error(error):
            raise
        print(f"ICuCrops: report query failed ({error})")
        return HTTPStatus.SERVICE_UNAVAILABLE, {
            "message": "The farm database is not reachable right now. Please try again."
        }

    pdf_started = time.perf_counter()
    content = icucrops_reports.build_report_pdf(model)
    print(
        "ICuCrops: report generated "
        f"(data={dataset_seconds:.2f}s, pdf={time.perf_counter() - pdf_started:.2f}s, "
        f"bytes={len(content)})"
    )
    return HTTPStatus.OK, {
        "content": content,
        "filename": f"{report_file_stem(dataset)}.pdf",
        "contentType": "application/pdf",
    }


def report_database_error(error: BaseException) -> bool:
    """Whether a report failure came from either supported database driver.

    Only faults that a retry could plausibly clear count here -- the connection
    dropped, the host is unreachable, the statement timed out. A schema fault is
    deliberately excluded: a missing column or table is a mismatch between this
    code and the database it was pointed at, and no amount of trying again will
    fix it. Reporting one as "the farm database is not reachable" is how an
    unapplied migration in supabase/migrations/ comes to look like a network
    outage -- it sends whoever is debugging to the uplink while the real cause
    sits in the schema. Those propagate instead, so the traceback names the
    column in the host's logs.
    """
    if isinstance(error, sqlite3.Error):
        return True
    if not postgres_backend_enabled():
        return False
    try:
        import psycopg
    except ImportError:
        return False
    # UndefinedColumn and UndefinedTable are ProgrammingError subclasses;
    # OperationalError -- the dropped connection, the unreachable host -- is
    # not, so a real outage still answers with the retry message.
    if isinstance(error, psycopg.ProgrammingError):
        return False
    return isinstance(error, psycopg.Error)


def report_charted_sensor_keys(row_keys: list[str] | None = None) -> list[str]:
    """The sensor keys any report reads, in one place for query and count."""
    selected_rows = [
        row_key for row_key in (row_keys or list(REPORT_ROW_KEYS)) if row_key in REPORT_ROW_KEYS
    ] or list(REPORT_ROW_KEYS)
    return list(
        dict.fromkeys(
            [str(metric["sensor_key"]).strip() for metric in DASHBOARD_SERIES_METRICS]
            + [f"{row_key}-moisture" for row_key in selected_rows]
            + [f"{row_key}-rs485" for row_key in selected_rows]
        )
    )


REPORT_AVERAGE_METRICS = (
    # (result key, sensor key, JSON field, row-sensor suffix, row field)
    # The row probes store this under "moisture", not "value": the firmware
    # publishes {"moisture": 57, "raw": 2100} and the shared dashboard sensor
    # is the only one that uses "value". Reading the row sensor with "value"
    # matched nothing, so a report for a farm whose moisture comes only from
    # the row probes -- which is every farm here -- showed no moisture at all
    # while the dashboard showed it fine. ph and ec were already correct.
    ("moisture", "moisture", "value", "moisture", "moisture"),
    ("ph", "ph", "value", "rs485", "ph"),
    ("ec", "ec", "value", "rs485", "ec"),
    ("temp", "dht22", "temp", "", ""),
    ("humidity", "dht22", "humidity", "", ""),
)


def report_preview_readings(
    connection: sqlite3.Connection,
    start: datetime,
    end: datetime,
    row_keys: list[str],
) -> dict[str, list[dict[str, object]]]:
    """Fetch the preview sample for every relevant sensor in one round trip.

    Each UNION branch retains its own ORDER BY/LIMIT, allowing both SQLite and
    PostgreSQL to seek through the sensor/time index instead of ranking the
    whole month. Combining the branches is important on the hosted backend:
    the database is across the network, so seventeen small queries were still
    slow enough together to exceed the page's deadline.
    """
    shared_keys = [str(item[1]) for item in REPORT_AVERAGE_METRICS]
    row_sensor_keys = [
        f"{row_key}-{suffix}"
        for row_key in row_keys
        for suffix in ("moisture", "rs485")
    ]
    sensor_keys = list(dict.fromkeys([*shared_keys, *row_sensor_keys]))
    window = (start.isoformat(), end.isoformat())
    branches: list[str] = []
    parameters: list[object] = []
    for sensor_key in sensor_keys:
        branches.append(
            """
            SELECT sensor_key, reading_payload_json, captured_at FROM (
                SELECT sensor_key, reading_payload_json, captured_at
                FROM sensor_readings
                WHERE sensor_key = ? AND captured_at >= ? AND captured_at <= ?
                ORDER BY captured_at DESC
                LIMIT ?
            ) AS sensor_sample
            """
        )
        parameters.extend((sensor_key, *window, REPORT_PREVIEW_SAMPLE_LIMIT))

    rows = connection.execute(
        "\nUNION ALL\n".join(branches) + "\nORDER BY sensor_key ASC, captured_at ASC",
        parameters,
    ).fetchall()
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        payload = parse_json_object(row["reading_payload_json"])
        if not isinstance(payload, dict):
            continue
        grouped.setdefault(str(row["sensor_key"]), []).append(
            {"payload": payload, "capturedAt": row["captured_at"]}
        )
    return grouped


def report_period_averages(
    readings: dict[str, list[dict[str, object]]], row_keys: list[str]
) -> dict[str, float | None]:
    """Compute preview averages from the shared bounded reading sample."""
    averages: dict[str, float | None] = {}
    for key, sensor_key, field, suffix, row_field in REPORT_AVERAGE_METRICS:
        values = report_metric_values(readings, sensor_key, field)
        if not values and suffix:
            values = report_row_metric_values(readings, row_keys, suffix, row_field)
        averages[key] = round(sum(values) / len(values), 2) if values else None
    return averages


def report_sampled_metric_statistics(
    readings: dict[str, list[dict[str, object]]], row_keys: list[str]
) -> dict[str, dict[str, float | int | None]]:
    """Fast, transparent averages from the real points shown by the report.

    A hosted month can contain hundreds of thousands of readings. Re-scanning
    every JSON payload solely for five header tiles added 4-17 seconds after
    the graph points were already available. These summaries average the same
    actual timestamped samples used by the report and expose their point count,
    so no interpolated or fabricated value is introduced.
    """

    def selected_values(
        shared_sensor: str,
        shared_field: str,
        row_suffix: str = "",
        row_field: str = "",
    ) -> list[float]:
        shared = report_metric_values(readings, shared_sensor, shared_field)
        if not row_suffix:
            return shared
        row_values = report_row_metric_values(readings, row_keys, row_suffix, row_field)
        if len(row_keys) > 1 and shared:
            return shared
        return row_values or shared

    selected = {
        "moisture": selected_values("moisture", "value", "moisture", "moisture"),
        "ph": selected_values("ph", "value", "rs485", "ph"),
        "ec": selected_values("ec", "value", "rs485", "ec"),
        "temp": selected_values("dht22", "temp"),
        "humidity": selected_values("dht22", "humidity"),
    }
    return {
        key: {
            "average": round(sum(values) / len(values), 2) if values else None,
            "count": len(values),
        }
        for key, values in selected.items()
    }


def report_row_health_summary(
    readings: dict[str, list[dict[str, object]]],
    row_keys: list[str],
    cultivations: list[dict[str, object]],
) -> list[dict[str, object]]:
    """The per-row cards the preview shows, from a sample rather than the window."""
    cultivation_by_row = {str(item.get("rowKey") or ""): item for item in cultivations}
    cards: list[dict[str, object]] = []

    for row_key in row_keys:
        cultivation = cultivation_by_row.get(row_key)
        label = cultivation_row_label(row_key)
        if not cultivation:
            cards.append({
                "rowKey": row_key, "label": label, "crop": "No cultivation",
                "grade": "Idle", "score": None, "trend": "Not planted",
            })
            continue

        crop_name = str(
            cultivation.get("crop") or cultivation.get("customPlantName") or "Active cultivation"
        )
        moisture = report_metric_values(readings, f"{row_key}-moisture", "moisture")
        ph_values = report_metric_values(readings, f"{row_key}-rs485", "ph")
        ec_values = report_metric_values(readings, f"{row_key}-rs485", "ec")

        card = score_row_health(
            row_key=row_key,
            label=label,
            crop_name=crop_name,
            cultivation=cultivation,
            moisture=moisture,
            ph_values=ph_values,
            ec_values=ec_values,
        )
        cards.append({
            "rowKey": card["rowKey"], "label": card["label"], "crop": card["crop"],
            "grade": card["grade"], "score": card["score"], "trend": card["trend"],
        })

    return cards


def report_preview_counts(
    connection: sqlite3.Connection, start: datetime, end: datetime
) -> dict[str, int]:
    """Row counts for the period, without transferring the rows.

    The preview only prints four numbers and a per-row grade. Building the full
    export dataset to get them pulled every reading in the window across the
    wire -- a month of readings for fifteen charted sensors, on every date
    change and every dataset toggle. That is what made the hosted page time out
    against its request deadline, and on Supabase it is metered egress for data
    that is immediately discarded.
    """
    sensor_keys = report_charted_sensor_keys()
    placeholders = ", ".join("?" for _ in sensor_keys)
    window = (start.isoformat(), end.isoformat())

    # Only the readings count is unbounded; the other two tables stay small
    # enough that an exact count costs nothing. Capping is applied by counting
    # rows from a LIMIT-ed subquery, which both SQLite and Postgres stop early.
    row = connection.execute(
        f"""
        SELECT
            (
                SELECT COUNT(*) FROM (
                    SELECT 1 FROM sensor_readings
                    WHERE sensor_key IN ({placeholders})
                      AND captured_at >= ? AND captured_at <= ?
                    LIMIT ?
                ) AS capped_readings
            ) AS readings,
            (
                SELECT COUNT(*) FROM irrigation_runs
                WHERE started_at >= ? AND started_at <= ?
            ) AS irrigation_runs,
            (
                SELECT COUNT(*) FROM notifications
                WHERE created_at >= ? AND created_at <= ? AND deleted_at IS NULL
            ) AS alerts
        """,  # nosec B608 - only '?' placeholders / module constants interpolated; values are bound parameters
        (*sensor_keys, *window, REPORT_PREVIEW_COUNT_CAP, *window, *window),
    ).fetchone()

    def count(name: str) -> int:
        try:
            return int(row[name])
        except (TypeError, ValueError, KeyError):
            return 0

    readings = count("readings")
    return {
        "readings": readings,
        # Tell the page the cap was reached so it can say "10,000+" rather than
        # presenting a capped number as though it were the true total.
        "readingsCapped": readings >= REPORT_PREVIEW_COUNT_CAP,
        "irrigationRuns": count("irrigation_runs"),
        "alerts": count("alerts"),
    }


def api_report_preview(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    """What the page shows before anything is downloaded.

    The Reports page needs to say how much data a range actually covers, so the
    farm is not left guessing whether an export will be empty. It answers from
    counts and the latest per-row readings, never from the whole window, so
    opening the page costs a fraction of an export.
    """
    sections = normalize_report_sections(payload.get("sections"))
    start, end = report_range_bounds(payload)
    row_keys = report_row_filter(payload)
    offset_minutes = clamp_report_offset(payload.get("timezoneOffsetMinutes"))

    try:
        with connect_database() as connection:
            counts = report_preview_counts(connection, start, end)
            cultivations = [
                build_cultivation_payload(item) for item in list_cultivations(connection)
            ]
            registry_rows = list_sensor_registry(connection)
            sampled_readings = report_preview_readings(connection, start, end, row_keys)
            metric_statistics = report_sampled_metric_statistics(sampled_readings, row_keys)
            averages = {key: value["average"] for key, value in metric_statistics.items()}
            row_health = report_row_health_summary(sampled_readings, row_keys, cultivations)
    except (sqlite3.Error, RuntimeError, OSError) as error:
        print(f"ICuCrops: report preview failed ({error})")
        return HTTPStatus.SERVICE_UNAVAILABLE, {
            "message": "The farm records could not be read right now. Please try again."
        }

    registry = {str(row["sensor_key"]).strip(): row for row in registry_rows}

    return HTTPStatus.OK, {
        "farmName": report_farm_name(),
        "period": icucrops_reports.format_report_period(
            start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        ),
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "sections": sections,
        "counts": {**counts, "cultivations": len(cultivations)},
        "averages": averages,
        "sampleCounts": {key: value["count"] for key, value in metric_statistics.items()},
        "rowHealth": row_health,
        "generatedAt": icucrops_reports.local_timestamp_label(offset_minutes),
    }


def api_list_notifications(user_id: str, role: str) -> tuple[HTTPStatus, dict[str, object]]:
    if not str(user_id or "").isdigit():
        return HTTPStatus.OK, {"notifications": []}


    with connect_database() as connection:
        user = find_user_by_id(connection, int(user_id))
        if not user or int(user["is_active"]) != 1:
            return HTTPStatus.OK, {"notifications": []}

        notifications = [
            build_notification_payload(item)
            for item in list_notifications_for_user(connection, user_id=int(user_id), role=role)
        ]

    return HTTPStatus.OK, {"notifications": notifications}


def api_mark_notifications_read(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    user_id = str(payload.get("userId") or "").strip()
    role = normalize_role(payload.get("role"))
    raw_ids = payload.get("notificationIds")
    notification_ids: list[int] | None = None

    if not user_id.isdigit():
        return HTTPStatus.OK, {"notifications": []}

    if isinstance(raw_ids, list):
        normalized_ids = [int(str(item).strip()) for item in raw_ids if str(item).strip().isdigit()]
        if normalized_ids:
            notification_ids = normalized_ids


    # The frontend sends explicit read sync requests so badge counts stay correct across sessions.
    with connect_database() as connection:
        user = find_user_by_id(connection, int(user_id))
        if not user or int(user["is_active"]) != 1:
            return HTTPStatus.OK, {"notifications": []}

        mark_notifications_read(
            connection,
            user_id=int(user_id),
            role=role,
            notification_ids=notification_ids,
        )
        notifications = [
            build_notification_payload(item)
            for item in list_notifications_for_user(connection, user_id=int(user_id), role=role)
        ]

    return HTTPStatus.OK, {"notifications": notifications}


def api_delete_notification(notification_id: str, payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    if not str(notification_id or "").isdigit():
        return HTTPStatus.BAD_REQUEST, {"message": "Notification id is invalid."}

    user_id = str(payload.get("userId") or "").strip()
    role = normalize_role(payload.get("role"))
    if role != "admin" or not user_id.isdigit():
        return HTTPStatus.FORBIDDEN, {"message": "Administrator access is required to delete notifications."}


    remote_command: dict[str, object] | None = None
    with connect_database() as connection:
        admin_user = find_user_by_id(connection, int(user_id))
        if not admin_user or int(admin_user["is_active"]) != 1 or normalize_role(admin_user["role"]) != "admin":
            return HTTPStatus.FORBIDDEN, {"message": "Administrator access is required to delete notifications."}

        deleted = delete_notification_record(connection, int(notification_id))
        if not deleted:
            return HTTPStatus.NOT_FOUND, {"message": "Notification not found."}

        remote_command = enqueue_remote_hardware_command(
            connection,
            command_type="notificationDelete",
            payload={
                "scope": str(deleted["scope"]),
                "type": str(deleted["type"]),
                "message": str(deleted["message"]),
                "sourceType": str(deleted["source_type"]),
                "sourceId": str(deleted["source_id"]),
                "createdAt": str(deleted["created_at"]),
            },
        )

        notifications = [
            build_notification_payload(item)
            for item in list_notifications_for_user(connection, user_id=int(user_id), role="admin")
        ]

    response: dict[str, object] = {
        "message": "Notification deleted.",
        "notifications": notifications,
    }
    if remote_command is not None:
        response["remoteCommand"] = remote_command
    return HTTPStatus.OK, response


def api_delete_all_notifications(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    user_id = str(payload.get("userId") or "").strip()
    role = normalize_role(payload.get("role"))
    if role != "admin" or not user_id.isdigit():
        return HTTPStatus.FORBIDDEN, {"message": "Administrator access is required to delete notifications."}


    remote_command: dict[str, object] | None = None
    with connect_database() as connection:
        admin_user = find_user_by_id(connection, int(user_id))
        if not admin_user or int(admin_user["is_active"]) != 1 or normalize_role(admin_user["role"]) != "admin":
            return HTTPStatus.FORBIDDEN, {"message": "Administrator access is required to delete notifications."}

        deleted_count = delete_all_notification_records_for_role(connection, role="admin")
        if deleted_count:
            remote_command = enqueue_remote_hardware_command(
                connection,
                command_type="notificationDeleteAll",
                payload={"role": "admin", "before": utc_now_iso()},
            )
        if not running_on_managed_host():
            remember_kiosk_history_delete_all(connection, role="admin")
        notifications = [
            build_notification_payload(item)
            for item in list_notifications_for_user(connection, user_id=int(user_id), role="admin")
        ]

    response: dict[str, object] = {
        "message": f"Deleted {deleted_count} notification{'s' if deleted_count != 1 else ''}.",
        "notifications": notifications,
    }
    if remote_command is not None:
        response["remoteCommand"] = remote_command
    return HTTPStatus.OK, response


def wake_farm_for_first_cultivation(connection: sqlite3.Connection) -> list[str]:
    """Hand a newly planted row a system that is actually switched on.

    Someone who has just filled in a crop's parameters expects the greenhouse
    to start looking after them. Finding every sensor powered down and both
    actuators forced Off -- which is exactly the state a farm is left in after
    a season ends -- means the parameters they entered do nothing at all, with
    no error anywhere to say why.

    So the first cultivation wakes what is asleep, and only what is asleep:

      * a sensor still powered on is left alone,
      * an actuator already on Automatic, or deliberately forced On, is left
        alone -- only an Off one moves to Automatic,
      * a row already set to Schedule or Manual keeps that mode.

    Nothing here is enforced afterwards. Every one of these can be switched
    straight back by hand, and this never runs again while a cultivation is
    already growing, so a deliberate Off stays off.
    """
    woken: list[str] = []
    timestamp = utc_now_iso()

    asleep_sensors = [
        str(row["sensor_key"]).strip()
        for row in connection.execute(
            "SELECT sensor_key, category, power_state FROM sensor_registry"
        ).fetchall()
        if str(row["category"] or "").strip().lower() != "actuator"
        and normalize_sensor_power_state(row["power_state"]) == "off"
    ]
    for sensor_key in asleep_sensors:
        connection.execute(
            "UPDATE sensor_registry SET power_state = 'on', updated_at = ? WHERE sensor_key = ?",
            (timestamp, sensor_key),
        )
    if asleep_sensors:
        woken.append(f"{len(asleep_sensors)} sensor(s) powered on")

    # Only the actuators a sensor rule decides. Misting is left where it is:
    # its Automatic means "mist with every water run", which is a choice for
    # whoever runs the farm and not something to switch on while waking the
    # rest. Off is its resting state.
    forced_off = [
        str(row["sensor_key"]).strip()
        for row in connection.execute(
            "SELECT sensor_key, actuator_mode FROM sensor_registry WHERE sensor_key IN ("
            + ", ".join("?" for _ in AUTOMATIC_ACTUATOR_KEYS)
            + ")",
            AUTOMATIC_ACTUATOR_KEYS,
        ).fetchall()
        if normalize_actuator_mode(row["actuator_mode"], str(row["sensor_key"])) == "off"
    ]
    for sensor_key in forced_off:
        connection.execute(
            "UPDATE sensor_registry SET actuator_mode = 'automatic', updated_at = ? WHERE sensor_key = ?",
            (timestamp, sensor_key),
        )
    if forced_off:
        woken.append(" and ".join(sorted(forced_off)) + " set to Automatic")

    # A row whose controller was disabled cannot irrigate at all, whatever its
    # mode says, so that is turned back on with it.
    disabled_rows = connection.execute(
        "UPDATE irrigation_row_controls SET is_enabled = TRUE, updated_at = ?"
        " WHERE is_enabled = FALSE",
        (timestamp,),
    ).rowcount
    if disabled_rows and disabled_rows > 0:
        woken.append(f"{disabled_rows} row controller(s) re-enabled")

    if not normalize_bool_flag(
        system_state_map(connection).get("irrigation.auto_enabled"), default=True
    ):
        set_system_state_value(connection, key="irrigation.auto_enabled", value="1")
        woken.append("automatic irrigation switched back on")

    return woken


def api_create_cultivation(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    row_key = str(payload.get("rowKey") or "").strip().lower()
    crop_type = str(payload.get("cropType") or "").strip()
    custom_plant_name = str(payload.get("customPlantName") or "").strip()
    crop_name = str(payload.get("cropName") or payload.get("crop") or "").strip()
    parameter_mode = str(payload.get("parameterMode") or "").strip().lower()
    created_by_user_id_raw = str(payload.get("createdByUserId") or "").strip()

    if row_key not in VALID_CULTIVATION_ROWS:
        return HTTPStatus.BAD_REQUEST, {"message": "Please choose a valid planting row."}

    if not crop_type:
        return HTTPStatus.BAD_REQUEST, {"message": "Crop type is required."}

    if not crop_name:
        return HTTPStatus.BAD_REQUEST, {"message": "Crop name is required."}

    if parameter_mode not in VALID_CULTIVATION_PARAMETER_MODES:
        return HTTPStatus.BAD_REQUEST, {"message": "Cultivation parameter mode is invalid."}

    try:
        requested_planting = cultivation_date_value(payload.get("plantingDate"), label="Planting date")
        requested_harvest = cultivation_date_value(payload.get("harvestDate"), label="Harvest date")
        days_to_harvest = int(payload.get("daysToHarvest") or 0)
        parameters = normalize_cultivation_parameters(payload.get("parameters"))
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}

    if days_to_harvest <= 0:
        return HTTPStatus.BAD_REQUEST, {"message": "Days to harvest must be greater than zero."}
    if requested_harvest < requested_planting:
        return HTTPStatus.BAD_REQUEST, {"message": "Harvest date cannot be earlier than planting date."}

    # A crop is planted this month, by this server's clock in the farm's time
    # zone. The farm asked for the month and year to be locked: a planting
    # entered in the wrong month or year threw off every countdown, harvest
    # check and schedule anchored on it. The day stays the one chosen while it
    # is in the current month; anything else -- a browser with a wrong clock,
    # or a grower's request approved in a later month -- is planted today. The
    # window the page worked out (planting to harvest) is kept either way.
    today = irrigation_local_now().date()
    in_this_month = (requested_planting.year, requested_planting.month) == (today.year, today.month)
    planting_day = requested_planting if in_this_month else today
    planting_date = planting_day.isoformat()
    harvest_date = (planting_day + (requested_harvest - requested_planting)).isoformat()

    created_by_user_id = int(created_by_user_id_raw) if created_by_user_id_raw.isdigit() else None


    try:
        with connect_database() as connection:
            if created_by_user_id is not None and not find_user_by_id(connection, created_by_user_id):
                created_by_user_id = None

            # Each hardware row can only hold one active cultivation at a time.
            existing = find_cultivation_by_row_key(connection, row_key)
            if existing:
                return HTTPStatus.CONFLICT, {
                    "message": f"{cultivation_row_label(row_key)} already has an active cultivation.",
                }

            cultivation = create_cultivation_record(
                connection,
                row_key=row_key,
                crop_type=crop_type,
                custom_plant_name=custom_plant_name,
                crop_name=crop_name,
                planting_date=planting_date,
                harvest_date=harvest_date,
                days_to_harvest=days_to_harvest,
                parameter_mode=parameter_mode,
                parameters=parameters,
                created_by_user_id=created_by_user_id,
            )
            success_message = f"{crop_name} was started in {cultivation_row_label(row_key)}."
            # Cultivation starts are real domain events, so they are persisted as notifications.
            create_notification_record(
                connection,
                scope="all",
                type="success",
                message=success_message,
                source_type="cultivation",
                source_id=str(cultivation["id"]),
            )
            # Only when this is the first row growing again. A farm already
            # running has deliberate settings, and nothing planted later should
            # reach in and undo them.
            if len(list_cultivations(connection)) == 1:
                woken = wake_farm_for_first_cultivation(connection)
                if woken:
                    create_notification_record(
                        connection,
                        scope="all",
                        type="success",
                        message=(
                            "Automatic control resumed for the new cultivation: "
                            + ", ".join(woken)
                            + ". Any of these can still be set to On or Off by hand."
                        ),
                        source_type="cultivation",
                        source_id=str(cultivation["id"]),
                    )
            cultivations = [build_cultivation_payload(item) for item in list_cultivations(connection)]
    except sqlite3.IntegrityError as error:
        details = str(error).lower()
        if "row_key" in details or "unique" in details:
            return HTTPStatus.CONFLICT, {"message": "That planting row already has an active cultivation."}
        return HTTPStatus.BAD_REQUEST, {"message": "Unable to save cultivation details."}

    # Recommended and custom ranges become control inputs as soon as the row is
    # saved. Reconcile synchronously so a local Pi never waits for either the
    # periodic controller fallback or the MQTT bridge's 0.5-second fallback.
    with IRRIGATION_STATE_TRANSITION_LOCK:
        with connect_database() as connection:
            irrigation = reconcile_irrigation_state(connection)
        cache_and_trigger_relay_publish(irrigation)
        remember_irrigation_control_surface(irrigation)
    refresh_environment_control_state()

    return HTTPStatus.CREATED, {
        "message": success_message,
        "cultivation": build_cultivation_payload(cultivation),
        "cultivations": cultivations,
        "irrigation": irrigation,
    }


def api_update_cultivation(
    cultivation_id: str, payload: dict[str, object]
) -> tuple[HTTPStatus, dict[str, object]]:
    """Edit a cultivation that is already in the ground.

    Only the three things the parameters dialog shows: when it was planted,
    when it is expected out, and -- for a row whose range was set by hand --
    the five numbers it is judged against. The row and the crop stay as they
    are, because changing either is a different planting and every reading
    already recorded belongs to this one.

    A recommended row is refused. Those five numbers are the Department of
    Agriculture reference for the crop, so an edited one is no longer the
    reference while both dashboards would still be calling it one.
    """
    if not str(cultivation_id or "").isdigit():
        return HTTPStatus.BAD_REQUEST, {"message": "Cultivation id is invalid."}

    with connect_database() as connection:
        cultivation = find_cultivation_by_id(connection, int(cultivation_id))
        if not cultivation:
            return HTTPStatus.NOT_FOUND, {"message": "Cultivation not found."}

        row_key = str(cultivation["row_key"]).strip()
        crop_name = str(cultivation["crop_name"]).strip()
        parameter_mode = str(cultivation["parameter_mode"]).strip().lower()
        current_planting_date = str(cultivation["planting_date"]).strip()
        current_harvest_date = str(cultivation["harvest_date"]).strip()
        current_parameters = parse_json_object(cultivation["parameters_json"])

        requested_parameters = payload.get("parameters")
        if requested_parameters is not None and parameter_mode != "custom":
            return HTTPStatus.BAD_REQUEST, {
                "message": (
                    "Recommended parameters follow the Department of Agriculture "
                    "reference and cannot be edited."
                ),
            }

        try:
            planting_date = normalize_cultivation_date(
                payload.get("plantingDate") or current_planting_date,
                label="Planting date",
            )
            harvest_date = normalize_cultivation_date(
                payload.get("harvestDate") or current_harvest_date,
                label="Harvest date",
            )
            parameters = (
                normalize_cultivation_parameters(requested_parameters)
                if requested_parameters is not None
                else current_parameters
            )
        except ValueError as error:
            return HTTPStatus.BAD_REQUEST, {"message": str(error)}

        # Recomputed here rather than trusted from the browser: the timeline and
        # the days-remaining badge are both drawn from it, and the two dates it
        # has to agree with are right there.
        days_to_harvest = (
            datetime.strptime(harvest_date, "%Y-%m-%d")
            - datetime.strptime(planting_date, "%Y-%m-%d")
        ).days
        if days_to_harvest <= 0:
            return HTTPStatus.BAD_REQUEST, {
                "message": "Harvest date must be later than the planting date.",
            }

        changes: list[str] = []
        if parameters != current_parameters:
            changes.append("target range")
        if planting_date != current_planting_date or harvest_date != current_harvest_date:
            changes.append("planting and harvest dates")

        # Saving a dialog nobody changed must not add a line to History, and
        # must not touch updated_at either -- that is the stamp the sync reads.
        if not changes and int(days_to_harvest) == int(cultivation["days_to_harvest"]):
            return HTTPStatus.OK, {
                "message": f"{crop_name} in {cultivation_row_label(row_key)} is already up to date.",
                "cultivation": build_cultivation_payload(cultivation),
                "cultivations": [
                    build_cultivation_payload(item) for item in list_cultivations(connection)
                ],
                "irrigation": build_irrigation_payload(connection),
            }

        updated = update_cultivation_record(
            connection,
            cultivation_id=int(cultivation_id),
            planting_date=planting_date,
            harvest_date=harvest_date,
            days_to_harvest=days_to_harvest,
            parameters=parameters,
        )
        message = (
            f"{crop_name} in {cultivation_row_label(row_key)} had its "
            f"{' and '.join(changes) or 'schedule'} updated."
        )
        create_notification_record(
            connection,
            scope="all",
            type="success",
            message=message,
            source_type="cultivation",
            source_id=str(cultivation["id"]),
        )
        cultivations = [build_cultivation_payload(item) for item in list_cultivations(connection)]

    # An edited range is an edited control input. Reconcile in the same request,
    # exactly as starting or removing a cultivation does, so a local Pi never
    # waits for the periodic controller pass to notice the new numbers.
    with IRRIGATION_STATE_TRANSITION_LOCK:
        with connect_database() as connection:
            irrigation = reconcile_irrigation_state(connection)
        cache_and_trigger_relay_publish(irrigation)
        remember_irrigation_control_surface(irrigation)
    refresh_environment_control_state()

    return HTTPStatus.OK, {
        "message": message,
        "cultivation": build_cultivation_payload(updated) if updated else None,
        "cultivations": cultivations,
        "irrigation": irrigation,
    }


def api_delete_cultivation(cultivation_id: str) -> tuple[HTTPStatus, dict[str, object]]:
    if not str(cultivation_id or "").isdigit():
        return HTTPStatus.BAD_REQUEST, {"message": "Cultivation id is invalid."}


    with connect_database() as connection:
        cultivation = find_cultivation_by_id(connection, int(cultivation_id))
        if not cultivation:
            return HTTPStatus.NOT_FOUND, {"message": "Cultivation not found."}

        message = f"{str(cultivation['crop_name']).strip()} was removed from {cultivation_row_label(str(cultivation['row_key']))}."
        update_irrigation_state(
            connection,
            irrigation_payload_without_row(
                build_irrigation_payload(connection),
                str(cultivation["row_key"]),
            ),
        )
        # Recorded before the delete, the same way a harvest is, and for the
        # same reason: the row is about to stop existing and everything the
        # history needs has to be copied out of it first. Without this a
        # scrapped crop left no trace at all, so a farm that pulled a failed
        # row was indistinguishable in the report from one that never planted
        # it -- and the crop's parameters, the ones that may be why it failed,
        # went with it.
        record_cultivation_harvest(
            connection,
            cultivation,
            harvested_by_user_id=None,
            outcome="removed",
        )
        record_sync_tombstone(
            connection,
            entity=CULTIVATION_TOMBSTONE,
            natural_key=cultivation_sync_key(cultivation["row_key"], cultivation["created_at"]),
        )
        connection.execute("DELETE FROM cultivations WHERE id = ?", (int(cultivation_id),))
        # Cultivation removals are also logged for the admin/user notification history pages.
        create_notification_record(
            connection,
            scope="all",
            type="warning",
            message=message,
            source_type="cultivation",
            source_id=str(cultivation["id"]),
        )
        cultivations = [build_cultivation_payload(item) for item in list_cultivations(connection)]

    # Removing a row must de-energize its parameter-driven outputs immediately
    # and recompute shared exhaust-fan/light rules from the remaining crops.
    with IRRIGATION_STATE_TRANSITION_LOCK:
        with connect_database() as connection:
            irrigation = reconcile_irrigation_state(connection)
        cache_and_trigger_relay_publish(irrigation)
        remember_irrigation_control_surface(irrigation)
    refresh_environment_control_state()

    return HTTPStatus.OK, {
        "message": message,
        "cultivations": cultivations,
        "irrigation": irrigation,
    }


def api_harvest_cultivation(
    cultivation_id: str,
    payload: dict[str, object] | None = None,
) -> tuple[HTTPStatus, dict[str, object]]:
    """Mark a crop harvested: file it in the history, then free the row.

    Deliberately api_delete_cultivation with one INSERT in front of the DELETE.
    The cultivation still has to leave the table -- row_key is UNIQUE, so the
    row cannot be replanted while it sits there -- and everything that made the
    delete path safe applies here unchanged, so the two follow the same order
    rather than growing separate ideas about irrigation and tombstones.

    The irrigation half is not incidental: without it a harvested row keeps
    watering an empty bed until the next periodic pass notices.
    """
    payload = payload if isinstance(payload, dict) else {}
    if not str(cultivation_id or "").isdigit():
        return HTTPStatus.BAD_REQUEST, {"message": "Cultivation id is invalid."}

    with connect_database() as connection:
        cultivation = find_cultivation_by_id(connection, int(cultivation_id))
        if not cultivation:
            return HTTPStatus.NOT_FOUND, {"message": "Cultivation not found."}

        # A crop is harvestable on its harvest date, not before. The button is
        # disabled until then, so reaching this is a replayed or hand-made
        # request; it is refused here because this is the only check both the
        # desktop and mobile clients pass through. A crop that is ready stays
        # ready -- there is no upper bound, an overdue crop must still be
        # closeable -- and an unreadable date is treated as ready so a bad
        # record can never strand a row as unharvestable.
        harvest_date = str(cultivation["harvest_date"]).strip()
        try:
            # Split on "T" first: the API stores YYYY-MM-DD, but older rows
            # carry a full timestamp, and on 3.10 date.fromisoformat rejects
            # one outright -- which would have read as "ready" and skipped the
            # check rather than applying it.
            not_ready = date.fromisoformat(harvest_date.split("T")[0]) > utc_now().date()
        except ValueError:
            not_ready = False
        if not_ready:
            return HTTPStatus.BAD_REQUEST, {
                "message": (
                    f"{str(cultivation['crop_name']).strip()} is not ready for harvest "
                    f"until {harvest_date}."
                )
            }

        row_label = cultivation_row_label(str(cultivation["row_key"]))
        message = f"{str(cultivation['crop_name']).strip()} on {row_label} was marked harvested."

        # Before the DELETE, because it reads the row that is about to go.
        harvest = record_cultivation_harvest(
            connection,
            cultivation,
            harvested_by_user_id=payload.get("harvestedByUserId"),
        )
        update_irrigation_state(
            connection,
            irrigation_payload_without_row(
                build_irrigation_payload(connection),
                str(cultivation["row_key"]),
            ),
        )
        # The same tombstone a removal records. The cultivation really is gone
        # from that table, and without the mark the next sync pass would read
        # its absence as "the other side is missing something" and put it back.
        record_sync_tombstone(
            connection,
            entity=CULTIVATION_TOMBSTONE,
            natural_key=cultivation_sync_key(cultivation["row_key"], cultivation["created_at"]),
        )
        connection.execute("DELETE FROM cultivations WHERE id = ?", (int(cultivation_id),))
        # "success", not the removal path's "warning": a finished crop is the
        # good outcome, and source_type distinguishes it from a scrapped one in
        # the notification history.
        create_notification_record(
            connection,
            scope="all",
            type="success",
            message=message,
            source_type="harvest",
            source_id=str(cultivation["id"]),
        )
        cultivations = [build_cultivation_payload(item) for item in list_cultivations(connection)]

    with IRRIGATION_STATE_TRANSITION_LOCK:
        with connect_database() as connection:
            irrigation = reconcile_irrigation_state(connection)
        cache_and_trigger_relay_publish(irrigation)
        remember_irrigation_control_surface(irrigation)
    refresh_environment_control_state()

    return HTTPStatus.OK, {
        "message": message,
        "harvest": build_harvest_payload(harvest) if harvest else None,
        "cultivations": cultivations,
        "irrigation": irrigation,
    }




























def api_list_sensors(
    *, live: bool = False, history_days: int | None = None
) -> tuple[HTTPStatus, dict[str, object]]:
    """The sensor overview, with the history and catalog only when asked for.

    `live` used to be honoured on the Pi alone: the hosted branch below ignored
    it and built the full payload every time. That is the request the hosted
    dashboards repeat every few seconds, and the history half of it is thirty
    days of readings for every charted sensor -- megabytes, rebuilt and shipped
    from Supabase on each one, for a caller that only wanted the latest value.

    There is nothing host-specific about the decision, so there is no longer a
    branch. A caller that omits `live` still gets everything, which is what the
    first load of a dashboard does.
    """
    with connect_database() as connection:
        return HTTPStatus.OK, build_sensor_overview_payload(
            connection,
            include_history=not live,
            include_catalog=not live,
            history_days=history_days,
        )


ACTUATOR_NOTIFICATION_LABELS = {
    "fan": "Exhaust fan",
    "light": "Grow light",
    "misting": "Misting",
}
ACTUATOR_MODE_LABELS = {
    "on": "turned ON",
    "off": "turned OFF",
    "automatic": "set to Automatic mode",
}


def record_actuator_mode_notification(
    connection: sqlite3.Connection,
    *,
    control_type: str,
    control_key: str,
    previous_mode: str,
    sensor: sqlite3.Row | None,
) -> sqlite3.Row | None:
    """Log a fan or light mode change, whichever host the button was pressed on.

    Both branches of api_update_sensor_control need this and only the Pi's had
    it, so switching the fan from the hosted or mobile dashboard changed the
    relay and left no trace in the bell or in History -- the same press on the
    kiosk logged normally, which made it look like the cloud had not done
    anything.

    Returns the row when one was written, so the caller can hand it back in the
    response and the dashboard can show it without waiting for a refresh.
    """
    if sensor is None or control_type != "actuatorMode":
        return None
    actuator_label = ACTUATOR_NOTIFICATION_LABELS.get(control_key)
    if actuator_label is None:
        return None
    next_mode = normalize_actuator_mode(sensor["actuator_mode"], control_key)
    if next_mode == previous_mode or next_mode not in ACTUATOR_MODE_LABELS:
        return None
    # The log entry is secondary to the relay. A press that moved the hardware
    # must not be reported as failed because its bell entry could not be
    # written, which is what turned a duplicate key into a 500 and reverted a
    # grow light the operator had already switched off.
    try:
        return create_notification_record(
            connection,
            scope="all",
            type="warning" if next_mode == "off" else "success",
            # No "from the dashboard": every host writes this now, so the phrase
            # was never true of all of them, and the message reads better without.
            message=f"{actuator_label} was {ACTUATOR_MODE_LABELS[next_mode]}.",
            source_type="actuator",
            source_id=control_key,
        )
    except Exception as error:  # noqa: BLE001 - driver-specific write failures
        if not database_integrity_error(error):
            raise
        print(f"ICuCrops: actuator notification skipped ({error})")
        return None


def api_update_sensor_control(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    # An On past the crops' limit is warned about on the card, not refused
    # here. The operator is the one standing in the greenhouse, and a press
    # that the server silently reverses is worse than one that is honoured with
    # the consequence spelled out beforehand.

    # Refused before anything is cached: an untimed mist would stay on.
    if misting_on_without_duration(payload):
        return HTTPStatus.BAD_REQUEST, {"message": MISTING_DURATION_REQUIRED_MESSAGE}

    # Hardware commands are local MQTT state. Update that snapshot before any
    # database write, so persistence can never delay a fan, light, or
    # sensor-power command on the Pi.
    pressed_at = utc_now()
    cached_relays = cache_relay_control_request(payload, pressed_at=pressed_at)
    if cached_relays is not None:
        trigger_local_relay_publish()
    if server_is_raspberry_pi():
        try:
            control_key = normalize_sensor_key(payload.get("key"))
            control_type = str(payload.get("controlType") or "").strip()
            notification: sqlite3.Row | None = None
            with connect_database() as connection:
                previous_sensor = find_sensor_registry_by_key(connection, control_key)
                previous_mode = (
                    normalize_actuator_mode(previous_sensor["actuator_mode"], control_key)
                    if previous_sensor is not None
                    else ""
                )
                update_sensor_control(connection, payload, pressed_at=pressed_at)
                sensor = find_sensor_registry_by_key(connection, control_key)
                notification = record_actuator_mode_notification(
                    connection,
                    control_type=control_type,
                    control_key=control_key,
                    previous_mode=previous_mode,
                    sensor=sensor,
                )
                remember_environment_control_surface(list_sensor_registry(connection))
            IRRIGATION_CONTROL_TRIGGER.set()
            ENVIRONMENT_CONTROL_TRIGGER.set()
        except ValueError as error:
            return HTTPStatus.BAD_REQUEST, {"message": str(error)}

        controls: dict[str, dict[str, str]] = {
            "sensorPower": {},
            "rowSensorPower": {},
            "actuatorMode": {},
        }
        if sensor is not None and control_type in {"sensorPower", "rowSensorPower"}:
            controls[control_type][control_key] = normalize_sensor_power_state(sensor["power_state"])
        elif sensor is not None and control_type == "actuatorMode":
            controls[control_type][control_key] = normalize_actuator_mode(sensor["actuator_mode"], control_key)

        response: dict[str, object] = {
            "message": "Sensor control updated locally.",
            "live": True,
            "controls": controls,
        }
        if notification is not None:
            response["notification"] = build_notification_payload(notification)
        return HTTPStatus.OK, response


    remote_command: dict[str, object] | None = None
    hosted_notification: sqlite3.Row | None = None
    hosted_sensor: sqlite3.Row | None = None
    try:
        with connect_database() as connection:
            hosted_control_key = normalize_sensor_key(payload.get("key"))
            hosted_control_type = str(payload.get("controlType") or "").strip()
            previous_sensor = find_sensor_registry_by_key(connection, hosted_control_key)
            previous_mode = (
                normalize_actuator_mode(previous_sensor["actuator_mode"], hosted_control_key)
                if previous_sensor is not None
                else ""
            )
            update_sensor_control(connection, payload)
            hosted_sensor = find_sensor_registry_by_key(connection, hosted_control_key)
            hosted_notification = record_actuator_mode_notification(
                connection,
                control_type=hosted_control_type,
                control_key=hosted_control_key,
                previous_mode=previous_mode,
                sensor=hosted_sensor,
            )
            # The command row is what actually reaches the farm, so it is the
            # last thing the press has to wait for. Everything after this point
            # is the dashboard catching up, not the relay moving.
            remote_command = enqueue_remote_hardware_command(
                connection,
                command_type="sensorControl",
                payload=payload,
            )
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}

    # Answer with the one control that was just written, the way the Pi branch
    # above already does.
    #
    # This used to rebuild the whole sensor overview first, and reconcile the
    # irrigation state before that. Measured, one press was 39 statements and
    # only 3 of them were the press: reconcile_irrigation_state() alone is 29.
    # On the Pi that is a local file and costs nothing worth naming. On the
    # managed host every statement is its own round trip to Supabase, so the
    # button was waiting on a full dashboard read -- and on the irrigation
    # controller -- before it could say yes. That is the lag.
    #
    # Nothing is lost by dropping them. The relay is driven by the command row,
    # not by the response; the irrigation controller reconciles on its own
    # cycle, which the trigger below wakes immediately; and the browser already
    # holds the pressed value optimistically and takes only `controls` from
    # this reply to confirm it. The overview it no longer sends is the same one
    # the next refresh brings in anyway.
    controls: dict[str, dict[str, str]] = {
        "sensorPower": {},
        "rowSensorPower": {},
        "actuatorMode": {},
    }
    if hosted_sensor is not None and hosted_control_type in {"sensorPower", "rowSensorPower"}:
        controls[hosted_control_type][hosted_control_key] = normalize_sensor_power_state(
            hosted_sensor["power_state"]
        )
    elif hosted_sensor is not None and hosted_control_type == "actuatorMode":
        controls[hosted_control_type][hosted_control_key] = normalize_actuator_mode(
            hosted_sensor["actuator_mode"], hosted_control_key
        )

    response: dict[str, object] = {
        "message": "Sensor control updated successfully.",
        "controls": controls,
    }
    if hosted_notification is not None:
        response["notification"] = build_notification_payload(hosted_notification)
    if remote_command is not None:
        response["message"] = "Control sent securely to the Raspberry Pi."
        response["remoteCommand"] = remote_command
    elif running_on_managed_host():
        # The row was written but nothing was queued, so the relay has nothing
        # to collect and the hardware will never move. That combination used to
        # answer 200 with "updated successfully", which is why a dead button
        # looked exactly like a working one: the card repainted, no error was
        # raised, and the farm simply did not respond. Say so instead.
        response["message"] = (
            "Saved, but the command could not be queued for the Raspberry Pi. "
            "The farm hardware has not been told about this change."
        )
        response["queued"] = False
    IRRIGATION_CONTROL_TRIGGER.set()
    ENVIRONMENT_CONTROL_TRIGGER.set()
    return HTTPStatus.OK, response


def api_list_sensor_registry() -> tuple[HTTPStatus, dict[str, object]]:

    with connect_database() as connection:
        registry = [build_sensor_registry_payload(item) for item in list_sensor_registry(connection)]
    return HTTPStatus.OK, {"registry": registry}


def api_list_sensor_definitions() -> tuple[HTTPStatus, dict[str, object]]:

    with connect_database() as connection:
        definitions = [build_sensor_definition_payload(item) for item in list_sensor_definitions(connection)]
    return HTTPStatus.OK, {"definitions": definitions}


def api_upsert_sensor_definition(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:

    try:
        with connect_database() as connection:
            definition = upsert_sensor_definition(connection, payload)
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}


    return HTTPStatus.OK, {
        "message": "Sensor definition updated successfully.",
        "definition": build_sensor_definition_payload(definition),
    }


def api_list_sensor_backends() -> tuple[HTTPStatus, dict[str, object]]:

    with connect_database() as connection:
        backends = [build_sensor_backend_payload(item) for item in list_sensor_backends(connection)]
    return HTTPStatus.OK, {"backends": backends}


def api_upsert_sensor_backend(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:

    try:
        with connect_database() as connection:
            backend = upsert_sensor_backend(connection, payload)
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}


    return HTTPStatus.OK, {
        "message": "Sensor backend updated successfully.",
        "backend": build_sensor_backend_payload(backend),
    }


def api_upsert_sensor_registry(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:

    try:
        with connect_database() as connection:
            sensor = update_sensor_registry_record(connection, payload)
            # No history here. These three hand the caller a fresh overview so
            # the dashboard can settle without waiting for a refresh, and the
            # only part of it that has to be current is the state just written.
            # Rebuilding the graph series as well meant a button press paid for
            # the thirty-day history query -- ten seconds against this farm's
            # readings -- before the response could be sent. The dashboard
            # extends its own curve from a live payload, so nothing is lost.
            overview = build_sensor_overview_payload(connection, include_history=False)
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}


    return HTTPStatus.OK, {
        "message": "Sensor registry updated successfully.",
        "sensor": build_sensor_registry_payload(sensor),
        **overview,
    }


def api_create_sensor_reading(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    if server_is_raspberry_pi():
        try:
            with connect_database() as connection:
                reading = record_sensor_reading(connection, payload)
                sensor = find_sensor_registry_by_key(
                    connection,
                    normalize_sensor_key(reading["sensor_key"]),
                )
            # Automatic irrigation still reacts immediately, but never holds
            # the MQTT ingest response open while a full reconcile runs.
            IRRIGATION_CONTROL_TRIGGER.set()
            ENVIRONMENT_CONTROL_TRIGGER.set()
        except ValueError as error:
            return HTTPStatus.BAD_REQUEST, {"message": str(error)}

        return HTTPStatus.CREATED, {
            "message": "Sensor reading recorded locally.",
            "reading": {
                "id": str(reading["id"]),
                "sensorKey": str(reading["sensor_key"]).strip(),
                "payload": parse_sensor_reading_payload(reading["reading_payload_json"]),
                "sourceType": str(reading["source_type"]).strip(),
                "sourceIdentifier": str(reading["source_identifier"]).strip(),
                "capturedAt": str(reading["captured_at"]).strip(),
            },
        }


    try:
        with connect_database() as connection:
            reading = record_sensor_reading(connection, payload)
            reconcile_irrigation_state(connection)
            # No history here. These three hand the caller a fresh overview so
            # the dashboard can settle without waiting for a refresh, and the
            # only part of it that has to be current is the state just written.
            # Rebuilding the graph series as well meant a button press paid for
            # the thirty-day history query -- ten seconds against this farm's
            # readings -- before the response could be sent. The dashboard
            # extends its own curve from a live payload, so nothing is lost.
            overview = build_sensor_overview_payload(connection, include_history=False)
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}

    return HTTPStatus.CREATED, {
        "message": "Sensor reading recorded successfully.",
        "reading": {
            "id": str(reading["id"]),
            "sensorKey": str(reading["sensor_key"]).strip(),
            "payload": parse_sensor_reading_payload(reading["reading_payload_json"]),
            "sourceType": str(reading["source_type"]).strip(),
            "sourceIdentifier": str(reading["source_identifier"]).strip(),
            "capturedAt": str(reading["captured_at"]).strip(),
        },
        **overview,
    }


def api_record_mqtt_node_status(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    node_id = str(payload.get("nodeId") or "").strip()
    state = str(payload.get("state") or "").strip().lower()
    if not node_id or state not in {"online", "offline", "restarting"}:
        return HTTPStatus.BAD_REQUEST, {"message": "nodeId and a valid state are required."}
    if node_id not in MQTT_NODE_SENSOR_KEYS:
        # Not an error: a board added to the fleet later, or a stray retained
        # message from a decommissioned one, should not fail the bridge's
        # request loop. It is simply not one this backend knows how to map to
        # a sensor key, so there is nothing further to record.
        return HTTPStatus.OK, {"message": "Unknown node id; ignored.", "recorded": False}
    with connect_database() as connection:
        previous = mqtt_node_status_map(connection).get(node_id) or {}
        changed = str(previous.get("state") or "") != state
        record_mqtt_node_status(connection, node_id, state)
    return HTTPStatus.OK, {
        "message": "Node status recorded.",
        "recorded": True,
        # The timestamp still moves -- the staleness window is measured from it
        # -- but a board repeating "online" every fifteen seconds is not a
        # change any browser needs to be told about.
        "changed": changed,
    }


def api_record_hardware_sync_batch(
    payload: dict[str, object],
) -> tuple[HTTPStatus, dict[str, object]]:
    """Record one Pi relay pass in one HTTPS request.

    The farm uplink can carry HTTPS but not the Supabase PostgreSQL ports. The
    original fallback posted every node and reading separately, making one
    twelve-sensor pass take 30-60 seconds on this link. Node heartbeats expire
    after 45 seconds, so a transport intended to keep the cards online was
    itself slower than the online window. One transaction and one response
    keeps the live heartbeat independent of request count and also leaves room
    for a small history slice.
    """
    raw_readings = payload.get("readings")
    raw_states = payload.get("nodeStates")
    readings = raw_readings if isinstance(raw_readings, list) else []
    states = raw_states if isinstance(raw_states, list) else []
    # The Pi's liveness stamp, in its own field because it is not a node state:
    # its value is a timestamp, and the hosted "is the farm's Pi alive" answer
    # reads this one row. It travels here because on a farm whose uplink blocks
    # the Postgres port this relay is the only thing that reaches the cloud at
    # all -- a heartbeat that only ever went by the blocked path would leave the
    # hosted badge reading Offline on a farm that is syncing perfectly.
    heartbeat = str(payload.get("piHeartbeat") or "").strip()[:64]
    # The Pi's fan-and-lamp effect, so the website shows the kiosk's numbers
    # (see relayed_greenhouse_response). Malformed is dropped, not rejected: it
    # is a display refinement and must never cost the readings their pass.
    greenhouse_response = normalize_relayed_greenhouse_response(payload.get("greenhouseResponse"))
    if not readings and not states and not heartbeat:
        return HTTPStatus.BAD_REQUEST, {
            "message": "At least one reading or node state is required."
        }
    # Unknown node ids are dropped further down rather than rejected, so this
    # bound exists only to cap the work one request can ask for. Sizing it
    # exactly to the fleet made it a tripwire instead: the Pi's own liveness
    # heartbeat shares the mqtt_node_status: prefix, the relay swept it up as a
    # fifth node, and a four-node farm posting five states had every pass
    # rejected -- which read on the website as a farm with no internet. The
    # relay no longer sends it, and this leaves room for one so that a single
    # unrecognised key degrades to being ignored, as it does everywhere else.
    if len(readings) > 256 or len(states) > len(MQTT_NODE_SENSOR_KEYS) + 4:
        return HTTPStatus.BAD_REQUEST, {"message": "Hardware sync batch is too large."}
    if any(not isinstance(item, dict) for item in readings + states):
        return HTTPStatus.BAD_REQUEST, {"message": "Hardware sync entries must be objects."}

    normalized_states: list[tuple[str, str]] = []
    for item in states:
        node_id = str(item.get("nodeId") or "").strip()
        state = str(item.get("state") or "").strip().lower()
        # A node this backend does not know is ignored rather than rejected --
        # the same tolerance the single-node endpoint applies. Checked before
        # the value is judged, because the bookkeeping keys that share the
        # mqtt_node_status: prefix (the Pi's own heartbeat, whose value is a
        # timestamp) are exactly the ones whose values are not node states. A
        # Pi still running the older relay must not have its entire pass
        # rejected over a row this backend was going to discard anyway.
        if node_id and node_id not in MQTT_NODE_SENSOR_KEYS:
            continue
        if not node_id or state not in {"online", "offline", "restarting"}:
            return HTTPStatus.BAD_REQUEST, {
                "message": "Every node state needs a known nodeId and valid state."
            }
        normalized_states.append((node_id, state))

    try:
        with connect_database() as connection:
            previous_states = mqtt_node_status_map(connection)
            changed_nodes = 0
            for node_id, state in normalized_states:
                if str((previous_states.get(node_id) or {}).get("state") or "") != state:
                    changed_nodes += 1
                # Repeated online heartbeats intentionally move updated_at;
                # that timestamp is what the hosted online window judges.
                record_mqtt_node_status(connection, node_id, state)

            # Stored under the key the hosted liveness check reads. Its value
            # is the Pi's own stamp and changes every time, which is what makes
            # its age trustworthy where an unchanging node state's is not.
            if heartbeat:
                set_system_state_value(
                    connection,
                    key=PI_HEARTBEAT_STATE_KEY,
                    value=heartbeat,
                )
            # Stamped with this server's time on arrival, so its age is judged
            # on one clock. Same statement-level trigger as the heartbeat in
            # the same transaction, so it adds no wake-up for the Pi's sync.
            if greenhouse_response:
                set_system_state_value(
                    connection,
                    key=GREENHOUSE_RESPONSE_RELAY_STATE_KEY,
                    value=json.dumps(greenhouse_response, separators=(",", ":")),
                )

            recorded_readings = 0
            for reading in readings:
                record_sensor_reading(connection, reading)
                recorded_readings += 1

            # The individual endpoint reconciles after every insert. A batch
            # needs the same final state, but only once after its newest and
            # backfill rows have landed.
            if recorded_readings:
                reconcile_irrigation_state(connection)
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}

    return HTTPStatus.CREATED, {
        "message": "Hardware sync batch recorded.",
        "readingsRecorded": recorded_readings,
        "nodeStatesRecorded": len(normalized_states),
        "nodeStatesChanged": changed_nodes,
    }


def api_get_irrigation() -> tuple[HTTPStatus, dict[str, object]]:

    with IRRIGATION_STATE_TRANSITION_LOCK:
        with connect_database() as connection:
            irrigation = reconcile_irrigation_state(connection)
        cache_relay_desired_state(irrigation)
    return HTTPStatus.OK, {"irrigation": irrigation}


# Last heartbeat write, so the 0.5 s poll below does not become a database
# write twice a second. Process-local and deliberately not persisted: a restart
# writing one extra heartbeat is free, and losing the throttle to a cold start
# is safer than carrying a stale one forward.
_PI_HEARTBEAT_LAST_WRITE_MONOTONIC: float | None = None


def stamp_pi_heartbeat_if_due() -> None:
    """Write the Pi's heartbeat, at most once per interval.

    Called from the relay desired-state endpoint because the MQTT bridge already
    polls it every 0.5 s from the Pi itself -- so the Pi proves it is alive by
    doing the thing it does anyway, and no new timer or service is needed. If
    the bridge stops, the farm really has lost its controller and the heartbeat
    should go stale.

    Pi only. Off the Pi this endpoint is not the farm, and a heartbeat written
    by the hosted app would claim a farm is up on the strength of a web request.
    """
    global _PI_HEARTBEAT_LAST_WRITE_MONOTONIC
    if not server_is_raspberry_pi():
        return
    now = time.monotonic()
    if (
        _PI_HEARTBEAT_LAST_WRITE_MONOTONIC is not None
        and now - _PI_HEARTBEAT_LAST_WRITE_MONOTONIC < PI_HEARTBEAT_INTERVAL_SECONDS
    ):
        return
    _PI_HEARTBEAT_LAST_WRITE_MONOTONIC = now
    try:
        with connect_database() as connection:
            record_pi_heartbeat(connection)
    except Exception:
        # A heartbeat is a status signal, not a control path. A locked or busy
        # database must not turn the relay poll -- which drives the pumps -- into
        # a failed request; the next pass will write it.
        _PI_HEARTBEAT_LAST_WRITE_MONOTONIC = None


def api_get_relay_desired_state() -> tuple[HTTPStatus, dict[str, object]]:
    stamp_pi_heartbeat_if_due()
    desired = cached_relay_desired_state()
    if desired is not None:
        return HTTPStatus.OK, {"relays": desired}

    status, response = api_get_irrigation()
    if status != HTTPStatus.OK:
        return status, {"message": "Unable to calculate the relay state."}
    desired = cached_relay_desired_state()
    if desired is None:
        return HTTPStatus.SERVICE_UNAVAILABLE, {"message": "Relay state is not ready yet."}
    return HTTPStatus.OK, {"relays": desired}


# Irrigation saves this process has already applied, by the id the page gives
# each one. The page's request helper retries a save that timed out -- on
# another API base, as a new request -- and the backend usually did finish the
# first one, just late. A Start retried that way ran the line a second time
# once the first run had ended.
RECENT_IRRIGATION_REQUEST_IDS: dict[str, float] = {}
RECENT_IRRIGATION_REQUEST_LOCK = threading.Lock()
IRRIGATION_REQUEST_ID_TTL_SECONDS = 600.0


def irrigation_request_already_applied(payload: dict[str, object]) -> bool:
    """True for a save whose id this process has seen; records a new one."""
    request_id = str(payload.get("requestId") or "").strip()[:80]
    if not request_id:
        return False
    now = time.monotonic()
    with RECENT_IRRIGATION_REQUEST_LOCK:
        for seen_id, seen_at in list(RECENT_IRRIGATION_REQUEST_IDS.items()):
            if now - seen_at > IRRIGATION_REQUEST_ID_TTL_SECONDS:
                RECENT_IRRIGATION_REQUEST_IDS.pop(seen_id, None)
        if request_id in RECENT_IRRIGATION_REQUEST_IDS:
            return True
        RECENT_IRRIGATION_REQUEST_IDS[request_id] = now
        return False


def current_irrigation_response() -> tuple[HTTPStatus, dict[str, object]]:
    with connect_database() as connection:
        irrigation = build_irrigation_payload(connection)
    return HTTPStatus.OK, {
        "message": "Irrigation request was already applied.",
        "irrigation": irrigation,
        "duplicate": True,
    }


def api_update_irrigation(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    # The MQTT bridge is woken by UDP and has a 0.5-second fallback poll. Apply
    # the per-row request first; the database write is durable storage and must
    # not sit in the physical pump command path.
    #
    # pressed_at ties the two together: the first publish already carries the
    # run's deadline (pressed_at + duration), and the run stored afterwards
    # starts at pressed_at, so both end at the same instant however long the
    # write takes.
    pressed_at = utc_now()
    if server_is_raspberry_pi():
        with IRRIGATION_STATE_TRANSITION_LOCK:
            # Checked inside the lock: a retry that arrives while the first
            # copy is still being applied waits here, then finds it recorded.
            if irrigation_request_already_applied(payload):
                return current_irrigation_response()
            cache_relay_irrigation_request(payload, pressed_at=pressed_at)
            trigger_local_relay_publish()
            try:
                with connect_database() as connection:
                    irrigation = update_irrigation_state(
                        connection, payload, pressed_at=pressed_at
                    )
            except ValueError as error:
                return HTTPStatus.BAD_REQUEST, {"message": str(error)}

            cache_and_trigger_relay_publish(irrigation)
            remember_irrigation_control_surface(irrigation)
        return HTTPStatus.OK, {
            "message": "Irrigation settings updated locally.",
            "irrigation": irrigation,
        }

    if irrigation_request_already_applied(payload):
        return current_irrigation_response()
    cache_relay_irrigation_request(payload, pressed_at=pressed_at)
    trigger_local_relay_publish()

    remote_command: dict[str, object] | None = None
    try:
        with connect_database() as connection:
            irrigation = update_irrigation_state(connection, payload, pressed_at=pressed_at)
            remote_command = enqueue_remote_hardware_command(
                connection,
                command_type="irrigation",
                payload=payload,
            )
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"message": str(error)}

    cache_and_trigger_relay_publish(irrigation)
    remember_irrigation_control_surface(irrigation)
    response: dict[str, object] = {
        "message": "Irrigation command sent securely to the Raspberry Pi.",
        "irrigation": irrigation,
    }
    if remote_command is not None:
        response["remoteCommand"] = remote_command
    return HTTPStatus.OK, response


def pending_hardware_command_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """The queued commands still waiting for the Pi, and nothing else.

    Every command row is kept after the Pi acknowledges it, and the Pi polls
    this queue every 1.5s. Reading all of them each time meant every press and
    every History deletion ever made online was carried back to the Pi's poll,
    forever. The status is filtered in the query so only live ones travel.
    """
    return connection.execute(
        "SELECT state_key, state_value FROM system_state WHERE state_key LIKE ? AND state_value LIKE ?",
        (f"{REMOTE_HARDWARE_COMMAND_PREFIX}%", '%"status":"pending"%'),
    ).fetchall()


# A queued command expires within a day (remote_hardware_command_expiry), so
# anything older than this is finished one way or another.
HOSTED_COMMAND_RETENTION_DAYS = 2
HOSTED_COMMAND_PRUNE_INTERVAL_SECONDS = 600.0
_LAST_HOSTED_COMMAND_PRUNE_MONOTONIC: float | None = None


def prune_finished_hardware_commands_if_due(connection: sqlite3.Connection) -> None:
    global _LAST_HOSTED_COMMAND_PRUNE_MONOTONIC
    now = time.monotonic()
    if (
        _LAST_HOSTED_COMMAND_PRUNE_MONOTONIC is not None
        and now - _LAST_HOSTED_COMMAND_PRUNE_MONOTONIC < HOSTED_COMMAND_PRUNE_INTERVAL_SECONDS
    ):
        return
    _LAST_HOSTED_COMMAND_PRUNE_MONOTONIC = now
    cutoff = (utc_now() - timedelta(days=HOSTED_COMMAND_RETENTION_DAYS)).isoformat()
    connection.execute(
        "DELETE FROM system_state WHERE state_key LIKE ? AND updated_at < ?",
        (f"{REMOTE_HARDWARE_COMMAND_PREFIX}%", cutoff),
    )


# How long a website press counts as still on its way to the Pi. Past this the
# press is either applied or stuck, and a stuck one must not hold the kiosk's
# own changes back from the website indefinitely.
HOSTED_PRESS_IN_FLIGHT_SECONDS = 120


def hosted_control_presses_in_flight(connection: sqlite3.Connection) -> bool:
    """True while a switch pressed on the website has not reached the Pi yet.

    The kiosk's controls upload carries the Pi's rows stamped with the Pi's own
    clock. Press Light On and then Automatic online, and the Pi applies the On
    first and uploads it with a stamp newer than the Automatic press -- so the
    website card jumped back to On until the second command landed, which on
    this link can be many seconds. That is the lag people saw after the kiosk
    presses started going up. While a press is in flight the upload waits.
    """
    cutoff = utc_now() - timedelta(seconds=HOSTED_PRESS_IN_FLIGHT_SECONDS)
    for row in pending_hardware_command_rows(connection):
        try:
            command = json.loads(row["state_value"] or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(command, dict) or command.get("status") != "pending":
            continue
        if command.get("type") not in {"sensorControl", "irrigation"}:
            continue
        try:
            requested_at = parse_iso_datetime(str(command.get("requestedAt") or ""))
        except (TypeError, ValueError):
            continue
        if requested_at >= cutoff:
            return True
    return False


def api_list_pending_hardware_commands() -> tuple[HTTPStatus, dict[str, object]]:
    """Pending cloud commands, for a Pi that cannot reach Postgres.

    The edge normally learns about a control press through Postgres LISTEN, and
    that is still the fast path. When the farm's link stops carrying the
    Postgres port - which it does, while continuing to carry 443 - nothing
    reaches the farm at all: readings can still be relayed up over HTTPS, but a
    switch pressed on the hosted dashboard has no way down, so the site reads
    live and controls nothing.

    This is the same queue the Postgres path drains, offered over the door that
    is still open. Device-token only, like the other hardware endpoints.
    """
    if not running_on_managed_host():
        return HTTPStatus.NOT_FOUND, {"message": "Command queue is unavailable."}

    now = utc_now()
    pending: list[dict[str, object]] = []
    with connect_database() as connection:
        rows = pending_hardware_command_rows(connection)
        prune_finished_hardware_commands_if_due(connection)

    for row in rows:
        try:
            command = json.loads(row["state_value"] or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(command, dict):
            continue
        if str(command.get("status") or "") != "pending":
            continue
        # Expired commands are deliberately not handed out: a switch pressed
        # long enough ago that it has lapsed should not fire when the link
        # comes back, which is exactly when a backlog would be delivered.
        try:
            expires_at = parse_iso_datetime(str(command.get("expiresAt") or ""))
        except (TypeError, ValueError):
            expires_at = None
        if expires_at is not None and expires_at <= now:
            continue
        pending.append({
            "id": str(command.get("id") or ""),
            "type": str(command.get("type") or ""),
            "payload": command.get("payload") if isinstance(command.get("payload"), dict) else {},
            "requestedAt": str(command.get("requestedAt") or ""),
            "expiresAt": str(command.get("expiresAt") or ""),
        })

    # Oldest first, so a burst of presses is applied in the order they were made.
    pending.sort(key=lambda item: str(item.get("requestedAt") or ""))
    return HTTPStatus.OK, {"commands": pending}


def api_list_sync_tombstones(
    *, after_deleted_at: str = "", limit: int = 200
) -> tuple[HTTPStatus, dict[str, object]]:
    """The deletion marks the Pi has not seen yet, over HTTPS.

    The ordinary edge sync exchanges these over Postgres. On a farm network that
    blocks the Postgres port that path never runs, so an account or cultivation
    removed on the hosted dashboard stayed live on the Pi indefinitely: the
    kiosk kept showing a user the cloud had already deleted, and the two sides
    read as out of sync because they were.

    Commands, readings and history deletions already had an HTTPS fallback.
    This is the same door for the one class of change that did not.
    """
    cursor = str(after_deleted_at or "").strip()
    try:
        capped = max(1, min(500, int(limit)))
    except (TypeError, ValueError):
        capped = 200

    try:
        with connect_database() as connection:
            if cursor:
                rows = connection.execute(
                    """
                    SELECT entity, natural_key, deleted_at FROM sync_tombstones
                    WHERE deleted_at > ?
                    ORDER BY deleted_at ASC
                    LIMIT ?
                    """,
                    (cursor, capped),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT entity, natural_key, deleted_at FROM sync_tombstones
                    ORDER BY deleted_at ASC
                    LIMIT ?
                    """,
                    (capped,),
                ).fetchall()
    except (sqlite3.Error, RuntimeError) as error:
        # A backend that has not created the table yet answers empty rather
        # than failing the Pi's whole poll.
        print(f"ICuCrops: tombstone listing unavailable ({error})")
        return HTTPStatus.OK, {"tombstones": [], "nextCursor": cursor}

    tombstones = [
        {
            "entity": str(row["entity"]),
            "naturalKey": str(row["natural_key"]),
            "deletedAt": str(row["deleted_at"] or ""),
        }
        for row in rows
    ]

    next_cursor = tombstones[-1]["deletedAt"] if tombstones else cursor
    return HTTPStatus.OK, {"tombstones": tombstones, "nextCursor": next_cursor}


def api_list_sync_accounts(
    *, after_updated_at: str = "", limit: int = 200
) -> tuple[HTTPStatus, dict[str, object]]:
    """The accounts the Pi has not seen yet, over HTTPS.

    Registration is meant to work while the Pi is off or offline: the hosted
    site has its own backend and its own Brevo mail path, so an admin can
    create an account from anywhere without the farm being up. What was
    missing was the way back. The edge sync carries users over Postgres, and
    this farm's network answers the TCP connect on 6543 but never replies to
    the Postgres handshake, so that path never completes. Deletions already had
    an HTTPS door (sync/tombstones); creations did not, so an account made
    while the Pi was down stayed invisible to the kiosk indefinitely.

    The password material is included because the Pi authenticates logins
    locally and offline; without it a synced account could not sign in at the
    kiosk, which is the whole point of creating it. The response is gated on
    the device token and only ever travels Pi-to-host over TLS. The stored
    values are PBKDF2 hash and salt, never a recoverable password.
    """
    cursor = str(after_updated_at or "").strip()
    try:
        capped = max(1, min(500, int(limit)))
    except (TypeError, ValueError):
        capped = 200

    # The cursor is an updated_at, and an account made or edited at the kiosk
    # carries the Pi's clock. That board has no battery-backed clock and has
    # booted a year ahead, so one such row could carry a stamp from the
    # future -- and a cursor moved onto it would skip every account created
    # here afterwards, forever: registered online, never at the kiosk. A
    # cursor from the future is therefore dropped (the full list is replayed
    # once, and a replay changes nothing), and it is never advanced past now.
    now = utc_now_iso()
    if cursor > now:
        cursor = ""

    columns = """
        id, display_name, email, role, password_hash, password_salt,
        password_iterations, is_active, created_at, updated_at,
        profile_photo_mime, profile_photo_version
    """
    try:
        with connect_database() as connection:
            if cursor:
                rows = connection.execute(
                    f"""
                    SELECT {columns} FROM users
                    WHERE updated_at > ?
                    ORDER BY updated_at ASC, id ASC
                    LIMIT ?
                    """,
                    (cursor, capped),
                ).fetchall()
            else:
                rows = connection.execute(
                    f"""
                    SELECT {columns} FROM users
                    ORDER BY updated_at ASC, id ASC
                    LIMIT ?
                    """,
                    (capped,),
                ).fetchall()
    except (sqlite3.Error, RuntimeError) as error:
        # Same rule as the tombstone listing: answer empty rather than failing
        # the Pi's whole poll.
        print(f"ICuCrops: account listing unavailable ({error})")
        return HTTPStatus.OK, {"accounts": [], "nextCursor": cursor}

    accounts = [
        {
            # The host's own id, needed only to build /profile-photo/<id>?v=...
            # The relay fetches the picture by that route, and without the id it
            # gave up on every photo without a word -- the name reached the kiosk
            # and the picture never did. The Pi still matches accounts by email.
            "id": int(row["id"]),
            "displayName": str(row["display_name"]),
            "email": normalize_email(row["email"]),
            "role": str(row["role"]),
            "passwordHash": str(row["password_hash"]),
            "passwordSalt": str(row["password_salt"]),
            "passwordIterations": int(row["password_iterations"]),
            "isActive": int(row["is_active"] or 0),
            "createdAt": str(row["created_at"] or ""),
            "updatedAt": str(row["updated_at"] or ""),
            # The photo travels as its version and mime only. The image itself
            # is fetched from /profile-photo/<id>?v=<version> and only when the
            # Pi finds the version newer than its own, so a listing that almost
            # always ends "already match" stays small -- the same reasoning
            # sync_profile_photos uses to keep the blob out of its comparison
            # query, where fetching it every pass cost 3.4 GB of egress a day.
            "profilePhotoVersion": str(row["profile_photo_version"] or ""),
            "profilePhotoMime": str(row["profile_photo_mime"] or ""),
        }
        for row in rows
    ]

    # A future-stamped row is still listed, every pass until its time comes,
    # but the cursor stays at the newest stamp that is not ahead of now.
    next_cursor = cursor
    for account in accounts:
        stamp = str(account["updatedAt"])
        if next_cursor < stamp <= now:
            next_cursor = stamp
    return HTTPStatus.OK, {"accounts": accounts, "nextCursor": next_cursor}


def apply_remote_profile_photo(
    connection: sqlite3.Connection, user_id: int, payload: dict[str, object]
) -> bool:
    """Bring a hosted profile photo down over HTTPS, newest version wins.

    Photos are otherwise carried only by sync_profile_photos(), which runs over
    Postgres. On this farm's network that port never completes its handshake,
    so a photo changed on the hosted dashboard reached the kiosk by no route at
    all -- the name arrived through this door and the picture silently did not,
    which reads as "the profile did not save".

    Only the version string travels in the listing. The image is fetched here,
    and only when the hosted version is newer than the stored one, so the usual
    pass -- where nothing changed -- costs nothing. profile_photo_version is an
    ISO-8601 stamp written at upload and compares correctly as text, the same
    rule the Postgres path uses, so the two cannot disagree about which edit
    happened second.
    """
    version = str(payload.get("profilePhotoVersion") or "").strip()
    if not version:
        return False

    row = connection.execute(
        "SELECT profile_photo_version FROM users WHERE id = ?", (int(user_id),)
    ).fetchone()
    if row is not None and str(row["profile_photo_version"] or "") >= version:
        return False

    encoded = str(payload.get("profilePhotoData") or "")
    if not encoded:
        # The relay fetches the image and puts it here; without it there is
        # nothing to write. Leaving the version unwritten is what makes the
        # next pass try again, so this must not be recorded as applied.
        return False
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return False
    if not data or len(data) > MAX_PROFILE_PHOTO_BYTES:
        return False
    mime = str(payload.get("profilePhotoMime") or "").strip() or "image/jpeg"
    connection.execute(
        """
        UPDATE users
        SET profile_photo_data = ?, profile_photo_mime = ?,
            profile_photo_version = ?, profile_photo_path = ''
        WHERE id = ?
        """,
        (sqlite3.Binary(data), mime, version, int(user_id)),
    )
    return True


def apply_remote_sync_account(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    """Apply one hosted account to the Pi, creating or updating it.

    This is the return leg of registering while the farm is down. The hosted
    site can create an account from anywhere (its own backend, its own Brevo
    mail path), but until now nothing brought it back to a Pi whose Postgres
    path is blocked, so the new user could not log in at the kiosk.

    Matching is on the email, which is the users table's UNIQUE column and the
    same natural key the Postgres sync uses, so an account that arrived by both
    routes converges instead of duplicating. Newest-wins on updated_at matches
    the rest of the sync's rules and makes a replayed pass a no-op.

    The password hash and salt travel with it because the kiosk authenticates
    locally and offline. A row that arrives without them would exist but never
    be able to sign in, which would look like the sync half-worked.
    """
    email = normalize_email(payload.get("email"))
    display_name = str(payload.get("displayName") or "").strip()
    role = normalize_role(payload.get("role"))
    password_hash = str(payload.get("passwordHash") or "").strip()
    password_salt = str(payload.get("passwordSalt") or "").strip()
    updated_at = str(payload.get("updatedAt") or "").strip() or utc_now_iso()
    created_at = str(payload.get("createdAt") or "").strip() or updated_at

    if not email or not is_valid_gmail_address(email):
        return HTTPStatus.BAD_REQUEST, {"message": "A valid Gmail address is required."}
    if not display_name:
        return HTTPStatus.BAD_REQUEST, {"message": "A display name is required."}
    if not password_hash or not password_salt:
        return HTTPStatus.BAD_REQUEST, {"message": "Password material is required."}

    try:
        iterations = int(payload.get("passwordIterations") or 0)
    except (TypeError, ValueError):
        iterations = 0
    if iterations <= 0:
        iterations = PASSWORD_ITERATIONS

    is_active = 0 if str(payload.get("isActive") or "1").strip() in {"0", "false", "False"} else 1

    with connect_database() as connection:
        # A deletion already applied here must not be undone by a listing that
        # still carries the row: the tombstone is the newer fact.
        tombstone = connection.execute(
            "SELECT 1 FROM sync_tombstones WHERE entity = ? AND natural_key = ?",
            (USER_TOMBSTONE, user_sync_key(email, created_at)),
        ).fetchone()
        if tombstone is not None:
            return HTTPStatus.OK, {"applied": False, "reason": "deleted"}

        # find_user_by_email is the login path's helper and does not select
        # updated_at; newest-wins needs it, so this reads the two columns it
        # actually uses rather than widening a query the whole app shares.
        existing = connection.execute(
            "SELECT id, updated_at FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing is not None:
            if str(existing["updated_at"] or "") >= updated_at:
                # The photo has its own version and is judged on it alone. An
                # account whose name already arrived -- by an earlier pass whose
                # photo fetch failed, or by the Postgres sync -- would otherwise
                # never get its picture, because its updated_at can no longer be
                # newer than itself.
                if apply_remote_profile_photo(connection, int(existing["id"]), payload):
                    invalidate_auth_session_user_cache(int(existing["id"]))
                    connection.commit()
                    return HTTPStatus.OK, {"applied": True, "created": False, "photo": True}
                return HTTPStatus.OK, {"applied": False, "reason": "not newer"}
            connection.execute(
                """
                UPDATE users
                SET display_name = ?, role = ?, password_hash = ?, password_salt = ?,
                    password_iterations = ?, is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    display_name, role, password_hash, password_salt,
                    iterations, is_active, updated_at, int(existing["id"]),
                ),
            )
            apply_remote_profile_photo(connection, int(existing["id"]), payload)
            invalidate_auth_session_user_cache(int(existing["id"]))
            connection.commit()
            return HTTPStatus.OK, {"applied": True, "created": False}

        connection.execute(
            """
            INSERT INTO users (
                display_name, email, role, password_hash, password_salt,
                password_iterations, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                display_name, email, role, password_hash, password_salt,
                iterations, is_active, created_at, updated_at,
            ),
        )
        # A new account can arrive with its picture already set -- one made
        # and given a photo while the other side was offline.
        created = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if created is not None:
            apply_remote_profile_photo(connection, int(created["id"]), payload)
        connection.commit()

    return HTTPStatus.OK, {"applied": True, "created": True}


def apply_remote_sync_tombstone(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    """Apply one hosted deletion mark to the Pi, and remove what it names.

    The mark is recorded first and in the same transaction as the delete it
    describes, so a crash between the two cannot leave the row deleted with
    nothing to stop the next sync restoring it.
    """
    entity = str(payload.get("entity") or "").strip()
    natural_key = str(payload.get("naturalKey") or "").strip()
    deleted_at = str(payload.get("deletedAt") or "").strip() or utc_now_iso()

    if entity not in {USER_TOMBSTONE, CULTIVATION_TOMBSTONE} or not natural_key.strip("|"):
        return HTTPStatus.BAD_REQUEST, {"message": "A known entity and natural key are required."}

    removed = 0
    with connect_database() as connection:
        record_sync_tombstone(connection, entity=entity, natural_key=natural_key)

        if entity == USER_TOMBSTONE:
            email, _, created_at = natural_key.partition("|")
            for row in connection.execute(
                "SELECT id, email, created_at, role FROM users"
            ).fetchall():
                if user_sync_key(row["email"], row["created_at"]) != natural_key:
                    continue
                # Administrator accounts are never deleted by the application
                # itself, so a mark naming one is recorded but not acted on
                # here either. That keeps the farm from being locked out of its
                # own kiosk by a mark that arrived over the network.
                if normalize_role(row["role"]) == "admin":
                    connection.commit()
                    return HTTPStatus.OK, {"applied": False, "reason": "administrator"}
                connection.execute("DELETE FROM users WHERE id = ?", (int(row["id"]),))
                invalidate_auth_session_user_cache(int(row["id"]))
                removed += 1
        else:
            for row in connection.execute(
                "SELECT id, row_key, created_at FROM cultivations"
            ).fetchall():
                if cultivation_sync_key(row["row_key"], row["created_at"]) != natural_key:
                    continue
                connection.execute("DELETE FROM cultivations WHERE id = ?", (int(row["id"]),))
                removed += 1

        connection.commit()

    return HTTPStatus.OK, {"applied": True, "removed": removed}


# Pi-to-host fields of a cultivation, the same set the Postgres sync compares.
SYNC_CULTIVATION_VALUE_COLUMNS = (
    "crop_type",
    "custom_plant_name",
    "crop_name",
    "planting_date",
    "harvest_date",
    "days_to_harvest",
    "parameter_mode",
    "parameters_json",
)


def _sync_cultivation_values(source: object) -> dict[str, object]:
    """One cultivation's synced values, reduced to what both stores compare equal on."""
    values: dict[str, object] = {}
    for column in SYNC_CULTIVATION_VALUE_COLUMNS:
        value = report_field(source, column, None)
        if column == "days_to_harvest":
            try:
                values[column] = int(value or 0)
            except (TypeError, ValueError):
                values[column] = 0
        elif column == "parameters_json":
            values[column] = json.dumps(parse_json_object(value), separators=(",", ":"), sort_keys=True)
        else:
            values[column] = "" if value is None else str(value)
    return values


def apply_remote_sync_cultivation(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    """Apply one Pi cultivation to the host, by the Postgres sync's rules.

    row_key is UNIQUE, so the row is the identity. A different planting in the
    same row is resolved by created_at -- replanting is the only way a second
    record exists, and the newer one is what is in the ground. The same
    planting is resolved by updated_at, the Pi winning a tie exactly as it does
    in sync_cultivations. A planting already deleted here is never restored.
    """
    row_key = str(payload.get("rowKey") or "").strip().lower()
    created_at = str(payload.get("createdAt") or "").strip()
    updated_at = str(payload.get("updatedAt") or "").strip() or created_at
    if row_key not in VALID_CULTIVATION_ROWS or not created_at:
        return HTTPStatus.BAD_REQUEST, {"message": "A known row and a created time are required."}

    incoming = _sync_cultivation_values({
        "crop_type": payload.get("cropType"),
        "custom_plant_name": payload.get("customPlantName"),
        "crop_name": payload.get("cropName"),
        "planting_date": payload.get("plantingDate"),
        "harvest_date": payload.get("harvestDate"),
        "days_to_harvest": payload.get("daysToHarvest"),
        "parameter_mode": payload.get("parameterMode"),
        "parameters_json": payload.get("parameters"),
    })
    if not incoming["crop_name"]:
        return HTTPStatus.BAD_REQUEST, {"message": "A crop name is required."}

    with connect_database() as connection:
        if connection.execute(
            "SELECT 1 FROM sync_tombstones WHERE entity = ? AND natural_key = ?",
            (CULTIVATION_TOMBSTONE, cultivation_sync_key(row_key, created_at)),
        ).fetchone() is not None:
            return HTTPStatus.OK, {"applied": False, "reason": "deleted"}

        owner_email = normalize_email(payload.get("createdByEmail"))
        owner = connection.execute(
            "SELECT id FROM users WHERE email = ?", (owner_email,)
        ).fetchone() if owner_email else None
        owner_id = int(owner["id"]) if owner is not None else None

        columns = ", ".join(SYNC_CULTIVATION_VALUE_COLUMNS)
        existing = connection.execute(
            f"SELECT id, created_at, updated_at, {columns} FROM cultivations WHERE row_key = ?",
            (row_key,),
        ).fetchone()
        if existing is None:
            placeholders = ", ".join(["?"] * len(SYNC_CULTIVATION_VALUE_COLUMNS))
            connection.execute(
                f"""
                INSERT INTO cultivations (row_key, created_at, updated_at, created_by_user_id, {columns})
                VALUES (?, ?, ?, ?, {placeholders})
                """,
                (row_key, created_at, updated_at, owner_id)
                + tuple(incoming[column] for column in SYNC_CULTIVATION_VALUE_COLUMNS),
            )
            seed_irrigation_rows_for_cultivations(connection)
            connection.commit()
            return HTTPStatus.OK, {"applied": True, "created": True}

        existing_created = str(existing["created_at"] or "")
        if existing_created != created_at:
            if created_at <= existing_created:
                return HTTPStatus.OK, {"applied": False, "reason": "older planting"}
        elif _sync_cultivation_values(existing) == incoming:
            return HTTPStatus.OK, {"applied": False, "reason": "unchanged"}
        elif updated_at < str(existing["updated_at"] or ""):
            return HTTPStatus.OK, {"applied": False, "reason": "not newer"}

        assignments = ", ".join(f"{column} = ?" for column in SYNC_CULTIVATION_VALUE_COLUMNS)
        connection.execute(
            f"""
            UPDATE cultivations
            SET {assignments}, created_by_user_id = ?, created_at = ?, updated_at = ?
            WHERE id = ?
            """,
            tuple(incoming[column] for column in SYNC_CULTIVATION_VALUE_COLUMNS)
            + (owner_id, created_at, updated_at, int(existing["id"])),
        )
        connection.commit()
    return HTTPStatus.OK, {"applied": True, "created": False}


def api_list_sync_cultivations(
    *, after_updated_at: str = "", limit: int = 200
) -> tuple[HTTPStatus, dict[str, object]]:
    """Cultivations started or edited on the host that the Pi has not seen, over HTTPS.

    The way down for plantings. Their deletions already travelled this way
    (sync/tombstones), so a crop removed on the website left the kiosk within
    seconds -- but a crop planted or edited there had only the Postgres sync,
    which this farm's network never lets finish, and never reached the kiosk.
    The Pi is the side that actually waters and ventilates, so a planting it
    does not know about is a row it does not look after.

    Same shape as the Pi's own upload, applied on the Pi by the same
    apply_remote_sync_cultivation, so both directions share one set of rules.
    """
    cursor = str(after_updated_at or "").strip()
    try:
        capped = max(1, min(500, int(limit)))
    except (TypeError, ValueError):
        capped = 200

    columns = """
        c.row_key, c.created_at, c.updated_at, u.email AS owner_email,
        c.crop_type, c.custom_plant_name, c.crop_name, c.planting_date,
        c.harvest_date, c.days_to_harvest, c.parameter_mode, c.parameters_json
    """
    try:
        with connect_database() as connection:
            if cursor:
                rows = connection.execute(
                    f"""
                    SELECT {columns}
                    FROM cultivations AS c
                    LEFT JOIN users AS u ON u.id = c.created_by_user_id
                    WHERE c.updated_at > ?
                    ORDER BY c.updated_at ASC, c.row_key ASC
                    LIMIT ?
                    """,  # nosec B608 - columns is a module constant
                    (cursor, capped),
                ).fetchall()
            else:
                rows = connection.execute(
                    f"""
                    SELECT {columns}
                    FROM cultivations AS c
                    LEFT JOIN users AS u ON u.id = c.created_by_user_id
                    ORDER BY c.updated_at ASC, c.row_key ASC
                    LIMIT ?
                    """,  # nosec B608 - columns is a module constant
                    (capped,),
                ).fetchall()
    except (sqlite3.Error, RuntimeError) as error:
        # Same rule as the account listing: answer empty rather than failing
        # the Pi's whole poll.
        print(f"ICuCrops: cultivation listing unavailable ({error})")
        return HTTPStatus.OK, {"cultivations": [], "nextCursor": cursor}

    cultivations = [
        {
            "rowKey": str(row["row_key"] or ""),
            "createdAt": str(row["created_at"] or ""),
            "updatedAt": str(row["updated_at"] or ""),
            "createdByEmail": normalize_email(row["owner_email"]),
            "cropType": row["crop_type"],
            "customPlantName": row["custom_plant_name"],
            "cropName": row["crop_name"],
            "plantingDate": row["planting_date"],
            "harvestDate": row["harvest_date"],
            "daysToHarvest": row["days_to_harvest"],
            "parameterMode": row["parameter_mode"],
            "parameters": row["parameters_json"],
        }
        for row in rows
    ]
    next_cursor = cultivations[-1]["updatedAt"] if cultivations else cursor
    return HTTPStatus.OK, {"cultivations": cultivations, "nextCursor": next_cursor}


# A planting that arrives later than this is not a fresh start. The farm may
# have been switched off by hand in the meantime, and waking it then would undo
# a deliberate choice made after the crop was planted.
SYNCED_CULTIVATION_WAKE_WINDOW_SECONDS = 10 * 60


def settle_farm_after_synced_cultivation(payload: dict[str, object], result: dict[str, object]) -> None:
    """On the Pi, do what a local start, edit or removal does after its write.

    A planting that arrived from the host was only a row in a table. Planted
    at the kiosk, the same crop also recomputes irrigation and the fan and
    light rules at once, and a first crop wakes a farm left asleep after the
    last season. The host did its own wake, but that changed the host's copy
    of the switches, not the relays in the greenhouse, so the Pi must do it.
    A removal that arrived the same way needs the reconcile just as much: it
    is what stops an emptied row being watered.
    """
    if result.get("created"):
        try:
            created_at = parse_iso_datetime(str(payload.get("createdAt") or ""))
            fresh = (utc_now() - created_at).total_seconds() <= SYNCED_CULTIVATION_WAKE_WINDOW_SECONDS
        except (TypeError, ValueError):
            fresh = False
        if fresh:
            with connect_database() as connection:
                if len(list_cultivations(connection)) == 1:
                    wake_farm_for_first_cultivation(connection)
                    connection.commit()

    with IRRIGATION_STATE_TRANSITION_LOCK:
        with connect_database() as connection:
            irrigation = reconcile_irrigation_state(connection)
        cache_and_trigger_relay_publish(irrigation)
        remember_irrigation_control_surface(irrigation)
    refresh_environment_control_state()


def apply_uploaded_notification_deletions(items: list[dict[str, object]]) -> tuple[int, int]:
    """History deleted at the kiosk, applied to the host. Returns (deleted, refused).

    Matched by the same six-field natural key the rest of the sync uses: ids
    are minted separately on each side and mean nothing across them. The Pi's
    own deleted_at is kept where it is a real stamp, so the host's deletion
    feed does not hand the same rows straight back to the Pi as new. A row
    already deleted here is left alone.
    """
    deleted = refused = 0
    with connect_database() as connection:
        for item in items:
            scope = str(item.get("scope") or "").strip()
            notification_type = str(item.get("type") or "").strip()
            message = str(item.get("message") or "")
            source_type = str(item.get("sourceType") or "").strip()
            source_id = str(item.get("sourceId") or "").strip()
            created_at = str(item.get("createdAt") or "").strip()
            if (
                scope not in VALID_NOTIFICATION_SCOPES
                or not notification_type
                or not message
                or not created_at
            ):
                refused += 1
                continue
            stamp = str(item.get("deletedAt") or "").strip()
            try:
                parse_iso_datetime(stamp)
            except (TypeError, ValueError):
                stamp = ""
            cursor = connection.execute(
                """
                UPDATE notifications
                SET deleted_at = ?
                WHERE scope = ? AND type = ? AND message = ?
                  AND source_type = ? AND source_id = ? AND created_at = ?
                  AND deleted_at IS NULL
                """,
                (
                    stamp or utc_now_iso(),
                    scope,
                    notification_type,
                    message,
                    source_type,
                    source_id,
                    created_at,
                ),
            )
            matched = max(0, int(cursor.rowcount or 0))
            if not matched:
                matched = delete_nearest_uploaded_notification(
                    connection,
                    key=(scope, notification_type, message, source_type, source_id),
                    created_at=created_at,
                    stamp=stamp or utc_now_iso(),
                )
            deleted += matched
        connection.commit()
    return deleted, refused


# How far apart the two sides' copies of one alert can be. Each side records
# its own History when it sees the reading, so the same alert carries a
# different created_at online -- measured on the farm at a median of ~20s.
UPLOADED_NOTIFICATION_MATCH_WINDOW_SECONDS = 120


def delete_nearest_uploaded_notification(
    connection: sqlite3.Connection,
    *,
    key: tuple[str, str, str, str, str],
    created_at: str,
    stamp: str,
) -> int:
    """Delete this side's copy of an alert deleted at the kiosk. Returns 0 or 1.

    The exact natural key never matches here (see the window above), so a
    single deletion made at the kiosk removed nothing online. The copy is the
    live entry with the same scope, type, message and source nearest in time.
    If an already deleted copy is at least as near, this deletion was applied
    before -- a resent page -- and nothing more is removed.
    """
    try:
        moment = parse_iso_datetime(created_at)
    except (TypeError, ValueError):
        return 0
    window = timedelta(seconds=UPLOADED_NOTIFICATION_MATCH_WINDOW_SECONDS + 1)
    candidates = connection.execute(
        """
        SELECT id, created_at, deleted_at
        FROM notifications
        WHERE scope = ? AND type = ? AND message = ?
          AND source_type = ? AND source_id = ?
          AND created_at >= ? AND created_at <= ?
        """,
        (*key, (moment - window).isoformat(), (moment + window).isoformat()),
    ).fetchall()

    nearest_live: tuple[float, int] | None = None
    nearest_deleted: float | None = None
    for candidate in candidates:
        try:
            distance = abs((parse_iso_datetime(str(candidate["created_at"])) - moment).total_seconds())
        except (TypeError, ValueError):
            continue
        if distance > UPLOADED_NOTIFICATION_MATCH_WINDOW_SECONDS:
            continue
        if candidate["deleted_at"] is None:
            if nearest_live is None or distance < nearest_live[0]:
                nearest_live = (distance, int(candidate["id"]))
        elif nearest_deleted is None or distance < nearest_deleted:
            nearest_deleted = distance
    if nearest_live is None or (nearest_deleted is not None and nearest_deleted <= nearest_live[0]):
        return 0
    cursor = connection.execute(
        "UPDATE notifications SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
        (stamp, nearest_live[1]),
    )
    return max(0, int(cursor.rowcount or 0))


# The switches and settings either dashboard can change: table -> (natural
# key, booleans, integers, texts, owned by a cultivation). The same tables as
# the edge sync's CONTROL_TABLES, with the duration columns by their real
# names. tools/hosted_command_relay.py reads the Pi's side from the same list.
UPLOADED_CONTROL_TABLES: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], bool]] = {
    "irrigation_settings": (
        ("channel_key",),
        ("automatic_enabled", "schedule_enabled"),
        ("automatic_duration_seconds", "manual_duration_seconds", "schedule_duration_seconds"),
        ("schedule_start_time", "schedule_frequency"),
        False,
    ),
    "irrigation_row_controls": (("row_key",), ("is_enabled",), (), ("mode",), True),
    "irrigation_row_settings": (
        ("row_key", "channel_key"),
        ("automatic_enabled", "schedule_enabled"),
        ("automatic_duration_seconds", "manual_duration_seconds", "schedule_duration_seconds"),
        ("schedule_start_time", "schedule_frequency"),
        True,
    ),
    "sensor_registry": (("sensor_key",), (), (), ("power_state", "actuator_mode", "alert_mode"), False),
}


def uploaded_state_key_allowed(key: str) -> bool:
    """The system_state keys a kiosk press writes that the website shows.

    The lime tank keys are left out: they name cultivations by id, and ids
    are minted separately on each side, so the Pi's would point at nothing
    here (or at the wrong planting).
    """
    if key == MISTING_DEADLINE_STATE_KEY:
        return True
    return key.startswith("irrigation.") and not key.startswith("irrigation.lime_tank_")


def _comparable_uploaded_control(value: object, kind: str) -> object:
    if kind == "boolean":
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes", "on"}
        return bool(value)
    if kind == "integer":
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
    return str(value if value is not None else "").strip()


def apply_uploaded_controls(controls: dict[str, object]) -> tuple[int, int]:
    """Kiosk switch presses and settings, applied to the host. Returns (applied, refused).

    A press on the website reaches the Pi as a command; a press at the kiosk
    had only the Postgres sync to carry it up, and this farm's network never
    lets that finish -- so a fan switched Off at the kiosk stayed Automatic on
    every other screen. The rules are the sync's own, so the two routes agree:
    a row is written only when its values differ and the Pi's edit is at least
    as new as this side's (the Pi holds the relays, so it wins a tie); a
    system_state key only when the Pi's is strictly newer. Rows this side
    does not have are never created. Written directly, never through the press
    endpoints, so nothing is queued back down to the Pi.
    """
    applied = refused = 0
    rows = controls.get("rows") if isinstance(controls.get("rows"), list) else []
    states = controls.get("state") if isinstance(controls.get("state"), list) else []
    with connect_database() as connection:
        for item in rows[:500]:
            if not isinstance(item, dict):
                refused += 1
                continue
            spec = UPLOADED_CONTROL_TABLES.get(str(item.get("table") or ""))
            key_values = item.get("key")
            values = item.get("values")
            stamp = str(item.get("updatedAt") or "").strip()
            if spec is None or not isinstance(key_values, dict) or not isinstance(values, dict):
                refused += 1
                continue
            keys, booleans, integers, texts, owned = spec
            key = tuple(str(key_values.get(column) or "").strip() for column in keys)
            try:
                parse_iso_datetime(stamp)
            except (TypeError, ValueError):
                refused += 1
                continue
            if any(not part for part in key):
                refused += 1
                continue
            kinds = {column: "boolean" for column in booleans}
            kinds.update({column: "integer" for column in integers})
            kinds.update({column: "text" for column in texts})
            if any(column not in values for column in kinds):
                refused += 1
                continue
            table = str(item["table"])
            live_only = " AND cultivation_id IN (SELECT id FROM cultivations)" if owned else ""
            where = " AND ".join(f"{column} = ?" for column in keys)
            current = connection.execute(
                f"SELECT {', '.join(kinds)}, updated_at FROM {table} WHERE {where}{live_only}",  # nosec B608 - table and columns come from UPLOADED_CONTROL_TABLES only
                key,
            ).fetchone()
            if current is None:
                continue
            incoming = {column: _comparable_uploaded_control(values[column], kinds[column]) for column in kinds}
            mine = {column: _comparable_uploaded_control(current[column], kinds[column]) for column in kinds}
            if incoming == mine or stamp < str(current["updated_at"] or ""):
                continue
            connection.execute(
                f"UPDATE {table} SET {', '.join(f'{column} = ?' for column in kinds)}, updated_at = ?"  # nosec B608 - as above
                f" WHERE {where}{live_only}",
                (*incoming.values(), stamp, *key),
            )
            applied += 1

        for item in states[:100]:
            if not isinstance(item, dict):
                refused += 1
                continue
            state_key = str(item.get("key") or "").strip()
            stamp = str(item.get("updatedAt") or "").strip()
            try:
                parse_iso_datetime(stamp)
            except (TypeError, ValueError):
                refused += 1
                continue
            if not uploaded_state_key_allowed(state_key) or not isinstance(item.get("value"), str):
                refused += 1
                continue
            value = str(item["value"])
            current = connection.execute(
                "SELECT state_value, updated_at FROM system_state WHERE state_key = ?",
                (state_key,),
            ).fetchone()
            if current is not None and (
                str(current["state_value"]) == value or stamp <= str(current["updated_at"] or "")
            ):
                continue
            connection.execute(
                """
                INSERT INTO system_state (state_key, state_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(state_key) DO UPDATE SET
                    state_value = excluded.state_value,
                    updated_at = excluded.updated_at
                """,
                (state_key, value, stamp),
            )
            applied += 1
        connection.commit()
    return applied, refused


def api_apply_sync_upload(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    """The Pi's own accounts, cultivations and deletions, carried up over HTTPS.

    Readings and node states already had an HTTPS door up, and commands,
    accounts and deletions had one down. Nothing made at the kiosk went up: the
    Postgres sync is its only carrier, and this farm's network never completes
    that handshake. So an account deleted at the kiosk stayed on the website, a
    replant there never appeared online, and the stale planting left online
    skewed everything judged against the crops -- the humidity fit among them,
    which is why the website showed a raw 96 %RH against the kiosk's fitted 79.

    Applied in dependency order -- deletions, then accounts, then cultivations,
    whose owner is looked up by email -- with the Postgres sync's own rules, so
    a record that arrives by both routes converges.
    """
    if not running_on_managed_host():
        return HTTPStatus.NOT_FOUND, {"message": "Upload is only accepted by the hosted backend."}

    def entries(key: str) -> list[dict[str, object]]:
        value = payload.get(key)
        return [item for item in value if isinstance(item, dict)][:200] if isinstance(value, list) else []

    # notificationDeletions is always present in the answer, even at zero. The
    # Pi reads the key as proof that this host understood the deletions it
    # sent: an older host would ignore them and still answer 200, and the Pi
    # would move its cursor past history that was never deleted here. The same
    # holds for notificationDeleteAll.
    applied = {
        "tombstones": 0,
        "accounts": 0,
        "cultivations": 0,
        "notificationDeletions": 0,
        "notificationDeleteAll": 0,
        "controls": 0,
        "notifications": 0,
    }
    rejected = 0
    controls_deferred = False

    for tombstone in entries("tombstones"):
        entity = str(tombstone.get("entity") or "").strip()
        natural_key = str(tombstone.get("naturalKey") or "").strip()
        # A mark already held is skipped rather than rewritten: recording it
        # again moves its deleted_at, and the Pi's down-feed pages by that
        # stamp, so every upload would hand the Pi its own marks back.
        with connect_database() as connection:
            known = connection.execute(
                "SELECT 1 FROM sync_tombstones WHERE entity = ? AND natural_key = ?",
                (entity, natural_key),
            ).fetchone()
        if known is not None:
            continue
        status, result = apply_remote_sync_tombstone(tombstone)
        if status != HTTPStatus.OK:
            rejected += 1
        elif result.get("applied"):
            applied["tombstones"] += 1

    for kind, apply in (
        ("accounts", apply_remote_sync_account),
        ("cultivations", apply_remote_sync_cultivation),
    ):
        for item in entries(kind):
            status, result = apply(item)
            if status != HTTPStatus.OK:
                rejected += 1
            elif result.get("applied"):
                applied[kind] += 1

    # History the Pi recorded, stored here as the same rows. Before the
    # deletions, so a batch that carries both finds what it deletes.
    notifications = entries("notifications")
    if notifications:
        with connect_database() as connection:
            for item in notifications:
                try:
                    applied["notifications"] += int(insert_synced_notification(connection, item))
                except ValueError:
                    rejected += 1
            connection.commit()

    # A Delete all pressed at the kiosk, as the cutoff it was pressed at. It
    # goes before the single rows, so none of those is matched against an
    # entry the cutoff was about to remove anyway.
    delete_all = payload.get("notificationDeleteAll")
    if isinstance(delete_all, dict):
        role = normalize_role(delete_all.get("role"))
        before = str(delete_all.get("before") or "").strip()
        try:
            parse_iso_datetime(before)
        except (TypeError, ValueError):
            before = ""
        if role != "admin" or not before:
            # Never an unbounded delete: without a cutoff this would also
            # erase everything recorded online after the press.
            rejected += 1
        else:
            with connect_database() as connection:
                applied["notificationDeleteAll"] += delete_all_notification_records_for_role(
                    connection, role=role, created_before=before
                )
                connection.commit()

    controls = payload.get("controls")
    if isinstance(controls, dict):
        with connect_database() as connection:
            controls_deferred = hosted_control_presses_in_flight(connection)
        if not controls_deferred:
            changed, refused = apply_uploaded_controls(controls)
            applied["controls"] += changed
            rejected += refused

    deletions = entries("notificationDeletions")
    if deletions:
        deleted, refused = apply_uploaded_notification_deletions(deletions)
        applied["notificationDeletions"] += deleted
        rejected += refused

    return HTTPStatus.OK, {
        "applied": applied,
        "rejected": rejected,
        "changed": any(applied.values()),
        # The Pi sends the same snapshot again next pass instead of
        # remembering it as delivered.
        "controlsDeferred": controls_deferred,
    }


# Harvest rows one exchange carries each way. A farm ends a few crops a month,
# so this is years of history; newest first, so a cap only ever drops the
# oldest rows, and those were carried long ago.
HARVEST_SYNC_MAX_ROWS = 200


def uploaded_harvest_values(item: dict[str, object]) -> tuple[object, ...]:
    """One harvest row from the Pi, checked and in HARVEST_SYNC_COLUMNS order.

    Raises ValueError for a row this store could not hold. The same checks the
    Supabase schema makes (row_key, outcome) are made here so a bad row is
    refused and counted rather than failing the whole batch on a constraint.
    """
    row_key = str(item.get("rowKey") or "").strip()
    if row_key not in {"row1", "row2", "row3", "row4"}:
        raise ValueError("unknown row")
    outcome = str(item.get("outcome") or "harvested").strip().lower()
    if outcome not in {"harvested", "removed"}:
        raise ValueError("unknown outcome")
    texts = {}
    for field in ("cropType", "cropName", "plantingDate", "harvestDate", "parameterMode", "harvestedAt", "createdAt"):
        value = str(item.get(field) or "").strip()
        if not value:
            raise ValueError(f"missing {field}")
        texts[field] = value
    parameters = item.get("parameters")
    if isinstance(parameters, str):
        parameters = parse_json_object(parameters)
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    try:
        days_to_harvest = int(item.get("daysToHarvest"))
        days_grown = max(0, int(item.get("daysGrown") or 0))
    except (TypeError, ValueError) as error:
        raise ValueError("days must be whole numbers") from error
    return (
        row_key,
        texts["cropType"],
        str(item.get("customPlantName") or "").strip(),
        texts["cropName"],
        texts["plantingDate"],
        texts["harvestDate"],
        days_to_harvest,
        texts["parameterMode"],
        json.dumps(parameters, separators=(",", ":"), sort_keys=True),
        texts["harvestedAt"],
        days_grown,
        1 if item.get("onSchedule", True) else 0,
        outcome,
        texts["createdAt"],
    )


HARVEST_SYNC_COLUMNS = (
    "row_key", "crop_type", "custom_plant_name", "crop_name",
    "planting_date", "harvest_date", "days_to_harvest",
    "parameter_mode", "parameters_json",
    "harvested_at", "days_grown", "on_schedule", "outcome", "created_at",
)


def api_exchange_sync_harvests(payload: dict[str, object]) -> tuple[HTTPStatus, dict[str, object]]:
    """Finished and removed crops, both ways, over HTTPS.

    Harvest history had only the Postgres sync, which this farm's network
    rarely lets finish -- measured 2026-09-25, three crops ended at the kiosk
    on Sept 23-24 were still missing from the website's reports. The Pi sends
    every row it holds; this stores the ones missing here and answers with the
    ones the Pi is missing, so one request converges both sides.

    Same identity and rules as sync_harvests in the Postgres sync: the natural
    key (row_key, planting_date, harvested_at), additive, no tombstones, and
    the per-store user ids left out. A row that arrives by both routes is an
    INSERT OR IGNORE no-op the second time.
    """
    if not running_on_managed_host():
        return HTTPStatus.NOT_FOUND, {"message": "Harvest sync is only accepted by the hosted backend."}

    value = payload.get("harvests")
    items = [item for item in value if isinstance(item, dict)][:HARVEST_SYNC_MAX_ROWS] if isinstance(value, list) else []

    applied = rejected = 0
    held_by_pi: set[tuple[str, str, str]] = set()
    placeholders = ", ".join(["?"] * len(HARVEST_SYNC_COLUMNS))
    with connect_database() as connection:
        for item in items:
            try:
                values = uploaded_harvest_values(item)
            except ValueError:
                rejected += 1
                continue
            key = (str(values[0]), str(values[4]), str(values[9]))
            held_by_pi.add(key)
            if find_cultivation_harvest(
                connection, row_key=key[0], planting_date=key[1], harvested_at=key[2]
            ) is not None:
                continue
            connection.execute(
                f"INSERT OR IGNORE INTO cultivation_harvests ({', '.join(HARVEST_SYNC_COLUMNS)})"
                f" VALUES ({placeholders})",  # nosec B608 - column names are a module constant
                values,
            )
            applied += 1
        if applied:
            connection.commit()
        rows = list_cultivation_harvests(connection, limit=HARVEST_SYNC_MAX_ROWS)

    missing_on_pi = []
    for row in rows:
        key = (str(row["row_key"]).strip(), str(row["planting_date"]).strip(), str(row["harvested_at"]).strip())
        if key in held_by_pi:
            continue
        missing_on_pi.append({
            "rowKey": key[0],
            "cropType": str(row["crop_type"]).strip(),
            "customPlantName": str(row["custom_plant_name"] or "").strip(),
            "cropName": str(row["crop_name"]).strip(),
            "plantingDate": key[1],
            "harvestDate": str(row["harvest_date"]).strip(),
            "daysToHarvest": int(row["days_to_harvest"]),
            "parameterMode": str(row["parameter_mode"]).strip(),
            "parameters": parse_json_object(row["parameters_json"]),
            "harvestedAt": key[2],
            "daysGrown": int(row["days_grown"] or 0),
            "onSchedule": bool(row["on_schedule"]),
            "outcome": str(row["outcome"] or "harvested").strip(),
            "createdAt": str(row["created_at"]).strip(),
        })

    return HTTPStatus.OK, {
        "applied": applied,
        "rejected": rejected,
        "changed": applied > 0,
        "harvests": missing_on_pi,
    }


def api_list_notification_deletions(
    *, after_deleted_at: str = "", after_id: int = 0, limit: int = 50
) -> tuple[HTTPStatus, dict[str, object]]:
    """Paged deletion marks missed while the full Postgres sync was blocked.

    New hosted deletions also enqueue an immediate edge command. This feed is
    the backstop for marks created before that command existed, or while a
    queue acknowledgement was interrupted. The cursor is (deleted_at, id), not
    id alone: deleting an old notification later gives it a new timestamp but
    of course does not change its original id.
    """
    if not running_on_managed_host():
        return HTTPStatus.NOT_FOUND, {"message": "Deletion feed is unavailable."}

    normalized_after = str(after_deleted_at or "").strip()
    try:
        normalized_id = max(0, int(after_id or 0))
    except (TypeError, ValueError):
        normalized_id = 0
    page_size = max(1, min(int(limit or 50), 100))

    with connect_database() as connection:
        if normalized_after:
            rows = connection.execute(
                f"""
                SELECT id, scope, type, message, source_type, source_id,
                       created_at, deleted_at
                FROM notifications
                WHERE deleted_at IS NOT NULL
                  AND (deleted_at > ? OR (deleted_at = ? AND id > ?))
                ORDER BY deleted_at ASC, id ASC
                LIMIT {page_size + 1}
                """,  # nosec B608 - page_size is clamped to an integer above
                (normalized_after, normalized_after, normalized_id),
            ).fetchall()
        else:
            rows = connection.execute(
                f"""
                SELECT id, scope, type, message, source_type, source_id,
                       created_at, deleted_at
                FROM notifications
                WHERE deleted_at IS NOT NULL
                ORDER BY deleted_at ASC, id ASC
                LIMIT {page_size + 1}
                """  # nosec B608 - page_size is clamped to an integer above
            ).fetchall()

    has_more = len(rows) > page_size
    rows = rows[:page_size]
    deletions = [
        {
            "scope": str(row["scope"]),
            "type": str(row["type"]),
            "message": str(row["message"]),
            "sourceType": str(row["source_type"]),
            "sourceId": str(row["source_id"]),
            "createdAt": str(row["created_at"]),
            "deletedAt": str(row["deleted_at"]),
        }
        for row in rows
    ]
    next_cursor: dict[str, object] | None = None
    if rows:
        next_cursor = {
            "deletedAt": str(rows[-1]["deleted_at"]),
            "id": int(rows[-1]["id"]),
        }
    return HTTPStatus.OK, {
        "deletions": deletions,
        "nextCursor": next_cursor,
        "hasMore": has_more,
    }


def api_acknowledge_hardware_command(
    payload: dict[str, object],
) -> tuple[HTTPStatus, dict[str, object]]:
    """Mark a command applied, from a Pi that took it over HTTPS.

    Without this the command stays pending and would be handed out again on the
    next poll, so the fan would keep being told to switch on for as long as the
    row lived.
    """
    if not running_on_managed_host():
        return HTTPStatus.NOT_FOUND, {"message": "Command queue is unavailable."}

    command_id = str(payload.get("commandId") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", command_id):
        return HTTPStatus.BAD_REQUEST, {"message": "A valid commandId is required."}

    status_value = str(payload.get("status") or "applied").strip().lower()
    if status_value not in {"applied", "failed"}:
        return HTTPStatus.BAD_REQUEST, {"message": "Status must be applied or failed."}

    with connect_database() as connection:
        key = f"{REMOTE_HARDWARE_COMMAND_PREFIX}{command_id}"
        row = connection.execute(
            "SELECT state_value FROM system_state WHERE state_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return HTTPStatus.NOT_FOUND, {"message": "Unknown command."}
        try:
            command = json.loads(row["state_value"] or "{}")
        except (TypeError, ValueError):
            command = {}
        if not isinstance(command, dict):
            command = {}
        command["status"] = status_value
        command["statusUpdatedAt"] = utc_now_iso()
        set_system_state_value(connection, key=key, value=json_dumps_compact(command))

    return HTTPStatus.OK, {"commandId": command_id, "status": status_value}


# A row older than this has certainly committed, so the cursor may pass it.
# Postgres hands out ids at insert, not at commit, and a younger id can become
# visible before an older one.
SYNC_NOTIFICATION_SETTLE_SECONDS = 300


def api_list_sync_notifications(
    *, after_id: str = "", limit: object = 200
) -> tuple[HTTPStatus, dict[str, object]]:
    """History recorded on the website that the Pi has not stored yet.

    Farm events are left out: the Pi records those itself and every one of
    them here is the Pi's own row, uploaded. What is left is what happened on
    the website -- an account, a planting, a harvest made there. Without a
    cursor the answer is only where to start, so the Pi does not pull the
    website's whole past on its first pass.
    """
    if not running_on_managed_host():
        return HTTPStatus.NOT_FOUND, {"message": "History feed is unavailable."}
    try:
        capped = max(1, min(500, int(limit)))
    except (TypeError, ValueError):
        capped = 200
    farm_sources = sorted(PI_WRITTEN_NOTIFICATION_SOURCES)
    placeholders = ", ".join("?" for _ in farm_sources)

    with connect_database() as connection:
        raw_cursor = str(after_id or "").strip()
        if not raw_cursor:
            newest = connection.execute("SELECT MAX(id) AS newest FROM notifications").fetchone()
            return HTTPStatus.OK, {
                "notifications": [],
                "nextCursor": int((newest["newest"] if newest is not None else 0) or 0),
            }
        try:
            cursor = max(0, int(raw_cursor))
        except ValueError:
            return HTTPStatus.BAD_REQUEST, {"message": "afterId must be a number."}
        rows = connection.execute(
            f"""
            SELECT id, scope, type, message, source_type, source_id, created_at
            FROM notifications
            WHERE id > ? AND deleted_at IS NULL AND source_type NOT IN ({placeholders})
            ORDER BY id ASC
            LIMIT ?
            """,  # nosec B608 - only '?' placeholders are interpolated
            (cursor, *farm_sources, capped),
        ).fetchall()
        if rows:
            next_cursor = int(rows[-1]["id"])
        else:
            # Nothing for the Pi, but the farm rows after the cursor would be
            # scanned again on every poll. Move past the settled ones.
            settled = connection.execute(
                "SELECT MAX(id) AS newest FROM notifications WHERE id > ? AND created_at < ?",
                (
                    cursor,
                    (utc_now() - timedelta(seconds=SYNC_NOTIFICATION_SETTLE_SECONDS)).isoformat(),
                ),
            ).fetchone()
            next_cursor = max(cursor, int((settled["newest"] if settled is not None else 0) or 0))

    return HTTPStatus.OK, {
        "notifications": [
            {
                "scope": str(row["scope"] or ""),
                "type": str(row["type"] or ""),
                "message": str(row["message"] or ""),
                "sourceType": str(row["source_type"] or ""),
                "sourceId": str(row["source_id"] or ""),
                "createdAt": str(row["created_at"] or ""),
            }
            for row in rows
        ],
        "nextCursor": next_cursor,
    }


def apply_remote_notification_deletion(
    payload: dict[str, object], *, delete_all: bool = False
) -> tuple[HTTPStatus, dict[str, object]]:
    """Apply a hosted History deletion to the Pi without a user session.

    The command carrying this payload was created by an authenticated admin
    and is delivered through the device-token queue. IDs cannot be used here:
    SQLite and Postgres mint them independently, so a single row is matched by
    the same six-field natural key used by the ordinary full sync.
    """
    with connect_database() as connection:
        if delete_all:
            role = normalize_role(payload.get("role"))
            if role != "admin":
                return HTTPStatus.BAD_REQUEST, {"message": "A valid history role is required."}
            before = str(payload.get("before") or "").strip()
            try:
                parse_iso_datetime(before)
            except (TypeError, ValueError):
                # A command queued before the bound existed carries none, and
                # deletes everything, exactly as it did when it was made.
                before = ""
            deleted = delete_all_notification_records_for_role(
                connection, role=role, created_before=before
            )
        else:
            scope = str(payload.get("scope") or "").strip()
            notification_type = str(payload.get("type") or "").strip()
            message = str(payload.get("message") or "")
            source_type = str(payload.get("sourceType") or "").strip()
            source_id = str(payload.get("sourceId") or "").strip()
            created_at = str(payload.get("createdAt") or "").strip()
            if (
                scope not in VALID_NOTIFICATION_SCOPES
                or not notification_type
                or not message
                or not created_at
            ):
                return HTTPStatus.BAD_REQUEST, {
                    "message": "A complete notification history key is required."
                }
            cursor = connection.execute(
                """
                UPDATE notifications
                SET deleted_at = COALESCE(deleted_at, ?)
                WHERE scope = ? AND type = ? AND message = ?
                  AND source_type = ? AND source_id = ? AND created_at = ?
                """,
                (
                    utc_now_iso(),
                    scope,
                    notification_type,
                    message,
                    source_type,
                    source_id,
                    created_at,
                ),
            )
            deleted = max(0, int(cursor.rowcount or 0))

    return HTTPStatus.OK, {
        "message": "Notification history deletion applied on the Raspberry Pi.",
        "deleted": deleted,
    }


def api_apply_remote_hardware_command(
    payload: dict[str, object],
) -> tuple[HTTPStatus, dict[str, object]]:
    """Apply one cloud command on the Pi, exactly once.

    This endpoint is device-token-only and the route additionally refuses to
    run anywhere except the Raspberry Pi.  The local applied marker makes a
    replay harmless if the Pi applied the command but lost internet before it
    could acknowledge Supabase.
    """
    if not server_is_raspberry_pi():
        return HTTPStatus.NOT_FOUND, {"message": "Edge command endpoint is unavailable."}

    command_id = str(payload.get("commandId") or "").strip()
    command_type = str(payload.get("type") or "").strip()
    command_payload = payload.get("payload")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", command_id):
        return HTTPStatus.BAD_REQUEST, {"message": "A valid commandId is required."}
    if command_type not in REMOTE_HARDWARE_COMMAND_TYPES:
        return HTTPStatus.BAD_REQUEST, {"message": "Unsupported hardware command type."}
    if not isinstance(command_payload, dict):
        return HTTPStatus.BAD_REQUEST, {"message": "A command payload object is required."}

    marker_key = f"{REMOTE_HARDWARE_COMMAND_APPLIED_PREFIX}{command_id}"
    with connect_database() as connection:
        marker = connection.execute(
            "SELECT state_value FROM system_state WHERE state_key = ?", (marker_key,)
        ).fetchone()
    if marker is not None:
        return HTTPStatus.OK, {
            "message": "Remote hardware command was already applied.",
            "commandId": command_id,
            "status": "applied",
            "duplicate": True,
        }

    if command_type == "irrigation":
        status, result = api_update_irrigation(command_payload)
    elif command_type == "sensorControl":
        status, result = api_update_sensor_control(command_payload)
    elif command_type == "notificationDelete":
        status, result = apply_remote_notification_deletion(command_payload)
    elif command_type == "syncTombstone":
        status, result = apply_remote_sync_tombstone(command_payload)
    elif command_type == "syncAccount":
        status, result = apply_remote_sync_account(command_payload)
    elif command_type == "syncCultivation":
        status, result = apply_remote_sync_cultivation(command_payload)
    elif command_type == "syncNotifications":
        status, result = apply_remote_synced_notifications(command_payload)
    else:
        status, result = apply_remote_notification_deletion(command_payload, delete_all=True)
    if status not in {HTTPStatus.OK, HTTPStatus.CREATED}:
        return status, result

    changed_a_planting = (
        command_type == "syncCultivation" and bool(result.get("applied"))
    ) or (
        command_type == "syncTombstone"
        and str(command_payload.get("entity") or "") == CULTIVATION_TOMBSTONE
        and int(result.get("removed") or 0) > 0
    )
    if changed_a_planting:
        try:
            settle_farm_after_synced_cultivation(command_payload, result)
        except Exception as error:  # noqa: BLE001 - the periodic pass reconciles too
            # The row itself is written and must be marked applied, or the
            # next poll would apply it again. The periodic controller pass
            # still reconciles; this only makes it immediate.
            print(f"ICuCrops: reconcile after a synced planting failed ({error})")

    applied_at = utc_now_iso()
    if command_id.startswith(UNMARKED_REMOTE_COMMAND_PREFIXES):
        return HTTPStatus.OK, {
            "message": "Remote hardware command applied on the Raspberry Pi.",
            "commandId": command_id,
            "status": "applied",
            "appliedAt": applied_at,
        }
    with connect_database() as connection:
        set_system_state_value(
            connection,
            key=marker_key,
            value=json_dumps_compact(
                {"id": command_id, "type": command_type, "appliedAt": applied_at}
            ),
        )
        prune_applied_command_markers_if_due(connection)
    return HTTPStatus.OK, {
        "message": "Remote hardware command applied on the Raspberry Pi.",
        "commandId": command_id,
        "status": "applied",
        "appliedAt": applied_at,
    }


def api_get_remote_hardware_command_status(
    command_id: str,
) -> tuple[HTTPStatus, dict[str, object]]:
    with connect_database() as connection:
        command = remote_hardware_command_record(connection, command_id)
    if command is None:
        return HTTPStatus.NOT_FOUND, {"message": "Remote command was not found."}

    request_user = authenticated_request_user() or {}
    requested_by = str(command.get("requestedByUserId") or "")
    if not request_user_is_admin() and not hmac.compare_digest(
        requested_by, str(request_user.get("id") or "")
    ):
        return HTTPStatus.FORBIDDEN, {"message": "You cannot view this command."}

    return HTTPStatus.OK, {
        "remoteCommand": {
            key: command.get(key)
            for key in (
                "id",
                "type",
                "status",
                "requestedAt",
                "expiresAt",
                "statusUpdatedAt",
                "appliedAt",
                "error",
            )
            if key in command
        }
    }


# How stale the sync daemon's state file may be before it is disregarded.
# The daemon rewrites it every 5s, so anything older than this means the daemon
# is not running rather than that the cloud is down -- a difference the badge
# must not confuse, because a stopped daemon is a local fault, not an outage.
SYNC_STATE_MAX_AGE_SECONDS = 60.0


def cloud_reachability_payload() -> dict[str, object]:
    """Whether the cloud is actually reachable, as reported by the sync daemon.

    This exists because "degraded" cannot answer it on the Pi. Degraded means
    the database is unreachable, and the Pi's database is the local SQLite
    file -- always reachable, internet or not. So health answered ok:true
    through every outage and the website's Online/Offline badge never moved.

    The sync daemon is the process that genuinely knows, because it is the one
    talking to Supabase; it publishes its verdict to a small file and this
    reads it. Returns an empty dict when there is nothing trustworthy to say --
    no file, unreadable, or too old to believe -- and the badge then falls back
    to the database signal exactly as it did before, rather than claiming an
    outage on the strength of a missing file.
    """
    try:
        raw = (DATA_DIR / "sync-state.json").read_text(encoding="utf-8")
        state = json.loads(raw)
        if not isinstance(state, dict):
            return {}
        updated_at = float(state.get("updatedAt") or 0.0)
        if time.time() - updated_at > SYNC_STATE_MAX_AGE_SECONDS:
            return {}
        return {"cloudOnline": bool(state.get("online"))}
    except (OSError, ValueError, TypeError):
        return {}


# The key the Pi's sync daemon stamps to say it is alive. Must match
# PI_HEARTBEAT_KEY in tools/sync_daemon.py.
PI_HEARTBEAT_STATE_KEY = "mqtt_node_status:pi-host"
# How long the hosted site waits before calling the Pi down.
#
# 60 s, down from 420. The old figure allowed three missed beats at the daemon's
# old 120 s cadence; at 15 s it allows four, so a slow pass or one that fell
# back to the HTTPS relay still cannot flip a healthy farm to "Pi offline".
#
# Seven minutes was the other half of why a working farm read offline on a
# phone: even once the Pi was back and beating, the badge could keep the old
# verdict for most of that window. The pair now answers within about a minute
# either way -- coming up or going down.
PI_HEARTBEAT_MAX_AGE_SECONDS = 60


def pi_heartbeat_is_fresh(connection: sqlite3.Connection) -> bool | None:
    """Is the Pi still stamping its liveness row? None when it never has.

    The same row pi_liveness_payload() reports to the health endpoint, read here
    so the sensor cards can use it too. It is the only signal in the system that
    says "the farm controller is up" rather than inferring it from a sensor:
    readings arrive only when a board has something to send, and ESP32 node
    status reaches Supabase only when its VALUE changes -- which is how an
    "offline" written once ends up sitting there while live readings arrive
    beside it.

    None means no heartbeat has ever been written: a farm on an older Pi build,
    or a fresh database. Saying nothing lets the caller fall back rather than
    accusing a working farm of being down.

    Takes an open connection because the payload builder already has one; this
    is read once per payload, not once per card.
    """
    try:
        row = connection.execute(
            "SELECT state_value FROM system_state WHERE state_key = ?",
            (PI_HEARTBEAT_STATE_KEY,),
        ).fetchone()
    except Exception:  # noqa: BLE001 - a status signal must not break the page
        return None
    if row is None:
        return None
    raw = str(row["state_value"] or "").strip()
    if not raw:
        return None
    try:
        beat = parse_iso_datetime(raw)
    except (TypeError, ValueError):
        return None
    # A heartbeat from the future is a clock disagreement, not a dead farm. The
    # Pi has no RTC and has booted with a wrong clock before, so a small
    # negative age reads as alive rather than as a fault.
    age = (utc_now() - beat).total_seconds()
    return -PI_HEARTBEAT_MAX_AGE_SECONDS <= age <= PI_HEARTBEAT_MAX_AGE_SECONDS


def pi_liveness_payload() -> dict[str, object]:
    """Whether the greenhouse Pi is still reporting in, for the hosted site.

    This answers a question the hosted dashboard could not previously ask. It
    reads Supabase, and a Pi that has stopped leaves the last rows it ever
    pushed sitting there: the farm looks quiet rather than absent, and there is
    no way from a phone to tell "nothing is happening" from "the Pi is dead".

    The heartbeat's value is a timestamp, so it changes on every write. That
    matters because the edge sync pushes system_state rows only when the value
    changes -- an unchanged one is skipped, which is why node status can sit
    hours stale in Supabase and why its age cannot be trusted. This row's age
    can be, because every refresh is a change.

    Only meaningful off the Pi. On the Pi itself the answer is trivially yes --
    the request was served by it -- so this reports nothing there and the badge
    keeps using the sync signal, which is the useful one on that host.
    """
    if server_is_raspberry_pi():
        return {}
    try:
        with connect_database() as connection:
            row = connection.execute(
                "SELECT state_value, updated_at FROM system_state WHERE state_key = ?",
                (PI_HEARTBEAT_STATE_KEY,),
            ).fetchone()
    except Exception:  # noqa: BLE001 - health must answer even if this cannot
        return {}
    if not row:
        # No heartbeat ever recorded: a farm running an older Pi build, not a
        # dead one. Saying nothing lets the badge fall back rather than
        # accusing a working Pi of being down.
        return {}
    # The Pi's own stamp, not the row's updated_at. They used to be the same
    # thing, because the row only ever changed when a fresh heartbeat arrived.
    # They are not the same now: the HTTPS relay carries the heartbeat in its
    # own field and this backend writes the row on every pass, so updated_at
    # tracks when the *cloud* last wrote and stays seconds old even after the
    # farm has gone dark -- which pinned the hosted badge to Online through a
    # power cut. state_value is what the Pi itself wrote when it was last
    # alive, so it is the only value whose age means what the badge claims.
    #
    # Falls back to updated_at when the value is not a timestamp, which is what
    # a Pi on an older build still sends.
    try:
        stamp = parse_iso_datetime(str(row["state_value"] or ""))
    except (TypeError, ValueError):
        try:
            stamp = parse_iso_datetime(str(row["updated_at"] or ""))
        except (TypeError, ValueError):
            return {}
    age = (utc_now() - stamp).total_seconds()
    return {
        "piOnline": age <= PI_HEARTBEAT_MAX_AGE_SECONDS,
        "piLastSeenSeconds": int(max(age, 0)),
    }


def api_health() -> tuple[HTTPStatus, dict[str, object]]:
    email_status = email_delivery_status_payload()


    def degraded_health() -> tuple[HTTPStatus, dict[str, object]]:
        # Keep the health endpoint responsive while the database is temporarily
        # unreachable. Render can keep the process alive, and its next health
        # request retries initialization instead of turning a brief outage into
        # a failed deployment. The Windows/Pi launchers poll this endpoint to
        # decide whether the backend came up, so it must answer 200 with an
        # offline report rather than raising a 500 -- otherwise an offline boot
        # looks identical to a backend that failed to start.
        with connect_database() as connection:
            user_count = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
            cultivation_count = int(connection.execute("SELECT COUNT(*) FROM cultivations").fetchone()[0])
            definition_count = int(connection.execute("SELECT COUNT(*) FROM sensor_definitions").fetchone()[0])
            backend_count = int(connection.execute("SELECT COUNT(*) FROM sensor_backends").fetchone()[0])
        return HTTPStatus.OK, {
            "ok": False,
            "degraded": True,
            "database": supabase_display_target() if postgres_backend_enabled() else str(DATABASE_PATH),
            "databaseBackend": DATABASE_BACKEND,
            "seededUsers": user_count,
            "activeCultivations": cultivation_count,
            "sensorDefinitions": definition_count,
            "sensorBackends": backend_count,
            "smtpConfigured": smtp_is_configured(),
            **email_status,
            "defaultApiPort": DEFAULT_API_FALLBACK_PORT,
        }

    try:
        ensure_database()
    except (RuntimeError, OSError):
        # OSError covers the socket and TLS timeouts a blocked or slow database
        # connection raises. Health is the one endpoint that must answer even then: turning
        # an unreachable database into a 500 hides the very state it reports.
        return degraded_health()


    with connect_database() as connection:
        user_count = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        cultivation_count = int(connection.execute("SELECT COUNT(*) FROM cultivations").fetchone()[0])
        definition_count = int(connection.execute("SELECT COUNT(*) FROM sensor_definitions").fetchone()[0])
        backend_count = int(connection.execute("SELECT COUNT(*) FROM sensor_backends").fetchone()[0])
    payload = {
        "ok": True,
        # Name the store the counts above actually came from. Reporting the
        # SQLite path while serving Supabase rows made health output lie.
        "database": supabase_display_target() if postgres_backend_enabled() else str(DATABASE_PATH),
        "databaseBackend": "postgres" if postgres_backend_enabled() else "sqlite",
        "seededUsers": user_count,
        "activeCultivations": cultivation_count,
        "sensorDefinitions": definition_count,
        "sensorBackends": backend_count,
        "smtpConfigured": smtp_is_configured(),
        **email_status,
        "defaultApiPort": DEFAULT_API_FALLBACK_PORT,
        **cloud_reachability_payload(),
        **pi_liveness_payload(),
    }
    return HTTPStatus.OK, payload


def server_is_raspberry_pi() -> bool:
    env_override = os.getenv("ICUCROPS_PI_MODE", "").strip().lower()
    if env_override in {"1", "true", "yes", "on"}:
        return True
    if env_override in {"0", "false", "no", "off"}:
        return False

    system_text = " ".join(
        part
        for part in (
            platform.system(),
            platform.machine(),
            platform.platform(),
        )
        if part
    ).lower()
    if "raspberry" in system_text or "raspbian" in system_text:
        return True

    for model_path in (
        Path("/proc/device-tree/model"),
        Path("/proc/device-tree/compatible"),
        Path("/sys/firmware/devicetree/base/model"),
        Path("/sys/firmware/devicetree/base/compatible"),
    ):
        try:
            model = model_path.read_text(encoding="utf-8", errors="ignore").replace("\x00", "").lower()
        except OSError:
            continue
        if "raspberry pi" in model or "raspberrypi" in model:
            return True

    try:
        cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        cpuinfo = ""

    return "raspberry pi" in cpuinfo or "raspberrypi" in cpuinfo


def raspberry_pi_wifi_connected() -> bool:
    """Return whether a Pi currently has an associated wireless link."""
    if not server_is_raspberry_pi():
        return True

    network_root = Path(os.getenv("ICUCROPS_NETWORK_CLASS_PATH", "/sys/class/net"))
    try:
        interfaces = list(network_root.iterdir())
    except OSError:
        return False

    for interface in interfaces:
        if not (interface / "wireless").exists():
            continue
        try:
            carrier_path = interface / "carrier"
            if carrier_path.exists():
                if carrier_path.read_text(encoding="utf-8").strip() == "1":
                    return True
                continue
            operstate = (interface / "operstate").read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue
        if operstate in {"up", "dormant"}:
            return True
    return False




def normalized_ip_address(value: object) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    text = str(value or "").strip().strip("[]")
    if not text:
        return None

    # IPv6 link-local addresses can include an interface scope such as "%eth0".
    text = text.split("%", 1)[0]
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None

    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def request_is_from_server_device() -> bool:
    # Reverse proxies connect to Flask through loopback, but their forwarded
    # client can be remote. Do not classify those browsers as the Pi's own
    # kiosk or remote desktop/mobile clients will inherit Pi mode.
    forwarded_for = str(flask_request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        forwarded_address = normalized_ip_address(forwarded_for.split(",", 1)[0])
        if forwarded_address is not None and not forwarded_address.is_loopback:
            return False

    remote_address = normalized_ip_address(flask_request.remote_addr)
    if remote_address is None:
        return False
    if remote_address.is_loopback:
        return True

    local_addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    request_hostname = str(flask_request.host or "").strip()
    if request_hostname.startswith("["):
        request_hostname = request_hostname[1:].split("]", 1)[0]
    elif request_hostname.count(":") == 1:
        request_hostname = request_hostname.rsplit(":", 1)[0]

    request_host_address = normalized_ip_address(request_hostname)
    if request_host_address is not None:
        local_addresses.add(request_host_address)

    hostnames = {
        platform.node().strip(),
        socket.gethostname().strip(),
        socket.getfqdn().strip(),
    }
    if request_hostname and request_host_address is None:
        normalized_request_hostname = request_hostname.rstrip(".").lower()
        if any(
            normalized_request_hostname == hostname.rstrip(".").lower()
            or normalized_request_hostname == f"{hostname.rstrip('.').lower()}.local"
            for hostname in hostnames
            if hostname
        ):
            hostnames.add(request_hostname)

    for hostname in hostnames:
        if not hostname:
            continue
        try:
            address_info = socket.getaddrinfo(hostname, None)
        except OSError:
            continue
        for entry in address_info:
            address = normalized_ip_address(entry[4][0])
            if address is not None:
                local_addresses.add(address)

    return remote_address in local_addresses


# The Raspberry Pi kiosk must never open Chromium's native file dialog: that
# dialog browses the whole filesystem -- root, /media and every home folder
# included -- from a panel anyone walking past can touch. The picker reads one
# directory and nothing else: no recursion, no symlinks out of it, and only the
# extensions the profile-photo upload already accepts, so anything listed here
# is also uploadable.
KIOSK_PHOTO_LIBRARY_LIMIT = 60
KIOSK_PHOTO_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def kiosk_photo_library_dir() -> Path:
    configured = os.getenv("ICUCROPS_KIOSK_PHOTO_DIR", "").strip()
    base = Path(configured).expanduser() if configured else Path.home() / "Pictures"
    try:
        return base.resolve()
    except OSError:
        return base


def kiosk_photo_library_entries() -> list[dict[str, object]]:
    base = kiosk_photo_library_dir()
    if not base.is_dir():
        return []

    try:
        children = list(base.iterdir())
    except OSError:
        return []

    entries: list[dict[str, object]] = []
    for child in children:
        if child.name.startswith(".") or child.is_symlink():
            continue
        if child.suffix.lower() not in ALLOWED_PROFILE_PHOTO_EXTENSIONS:
            continue
        if not child.is_file():
            continue
        try:
            stat_result = child.stat()
        except OSError:
            continue
        entries.append(
            {
                "name": child.name,
                "bytes": int(stat_result.st_size),
                "modified": int(stat_result.st_mtime),
                "tooLarge": stat_result.st_size > MAX_PROFILE_PHOTO_BYTES,
            }
        )

    entries.sort(key=lambda entry: (-int(entry["modified"]), str(entry["name"]).lower()))
    return entries[:KIOSK_PHOTO_LIBRARY_LIMIT]


def kiosk_photo_library_file(name: str) -> tuple[Path, str] | None:
    cleaned = str(name or "").strip()
    if not cleaned or cleaned.startswith(".") or cleaned in {".", ".."}:
        return None
    if "/" in cleaned or "\\" in cleaned or "\x00" in cleaned:
        return None

    base = kiosk_photo_library_dir()
    if not base.is_dir():
        return None

    candidate = base / cleaned
    if candidate.is_symlink() or not candidate.is_file():
        return None

    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    # A resolved parent that is no longer the library means the name escaped it.
    if resolved.parent != base:
        return None

    content_type = KIOSK_PHOTO_CONTENT_TYPES.get(resolved.suffix.lower())
    if not content_type:
        return None

    return resolved, content_type


def runtime_platform_payload() -> dict[str, object]:
    return {
        "isRaspberryPi": server_is_raspberry_pi(),
        "isLocalClient": request_is_from_server_device(),
        "system": platform.system().lower(),
        "machine": platform.machine().lower(),
    }


def normalized_request_origin() -> str:
    origin = str(flask_request.headers.get("Origin") or "").strip().rstrip("/")
    return origin if origin and origin != "null" else ""


def effective_request_origin() -> str:
    forwarded_proto = str(flask_request.headers.get("X-Forwarded-Proto") or "").split(",", 1)[0].strip()
    scheme = forwarded_proto if forwarded_proto in {"http", "https"} else flask_request.scheme
    return f"{scheme}://{flask_request.host}".rstrip("/")


def cors_origin_is_allowed(origin: str) -> bool:
    normalized = str(origin or "").strip().rstrip("/")
    if not normalized:
        return True
    if normalized == effective_request_origin():
        return True
    if normalized in ALLOWED_CORS_ORIGINS:
        return True

    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError:
        return False
    if parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        return False
    if parsed.scheme == "https":
        return port in {None, 443}
    return parsed.scheme == "http" and port in {80, 8080}


def api_path_is_public(path: str) -> bool:
    return path in {
        "/api/health",
        "/api/release",
        "/api/auth/login",
        "/api/auth/forgot-password/request-otp",
        "/api/auth/forgot-password/verify-otp",
        "/api/auth/forgot-password/reset",
    }


def api_request_requires_admin(path: str, method: str) -> bool:
    if path.startswith("/api/users/"):
        return not path.startswith("/api/users/profile")
    if path == "/api/users":
        return method != "GET"
    if (
        path in {
            "/api/sensors/registry",
            "/api/sensors/definitions",
            "/api/sensors/backends",
        }
        and method != "GET"
    ):
        return True
    if path.startswith("/api/notifications") and method == "DELETE":
        return True
    # Planning the season is the administrator's job: the grower's page shows
    # the active crops and their parameters and offers no way to change them.
    # Only the buttons were missing, though -- the endpoints took any signed-in
    # session, so a user could plant, edit, scrap or harvest a row by calling
    # them directly. Harvesting is the one that cannot be undone: it copies the
    # crop into the history and deletes it, freeing the row for a replant.
    # GET stays open, because reading the crops is what that page does.
    # Asking for a planting is open too: it plants nothing, and only an
    # administrator's approval turns it into a cultivation.
    if path == "/api/cultivations/requests" and method == "POST":
        return False
    if path.startswith("/api/cultivations") and method != "GET":
        return True
    # Reports are a backup of the farm's own record, and a grower is as
    # entitled to a copy as the administrator: both shells carry the page. It
    # stays behind authentication -- api_path_is_public does not list it -- and
    # it remains read-only, so widening it grants a download, never a write.
    return False


def create_app() -> Flask:
    # Flask serves the API and static dashboard files from the same local backend process.
    app = Flask(__name__, static_folder=None)
    app.config.setdefault("AUTH_SESSION_REQUIRE_ACTIVE_USER", True)
    # Reject an oversized body before it is buffered into memory.
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BODY_BYTES

    # main() prepares the database before serving, but a managed host imports
    # this factory directly and never runs main(). Without the schema the first
    # request that touches SQLite fails with "no such table: users", which the
    # browser only ever sees as a bare 500. Only the local schema is prepared
    # here; nothing else in start-up waits on the network.
    try:
        ensure_local_database_schema()
    except (RuntimeError, OSError, sqlite3.Error) as error:
        print(f"ICuCrops: database bootstrap deferred ({error})")

    @app.after_request
    def apply_default_headers(response):
        path = flask_request.path
        if path.startswith("/api/") or path.endswith((".html", "/")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        else:
            response.headers.setdefault("Cache-Control", "public, max-age=300")

        origin = normalized_request_origin()
        if path.startswith("/api/") and origin and cors_origin_is_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, X-ICUCROPS-Device-Token"
            )
            response.headers["Access-Control-Max-Age"] = "600"
            # The dashboard reads the server's clock off Date to age readings
            # correctly on a browser whose own clock is wrong; cross-origin,
            # the header is hidden unless it is exposed.
            exposed = str(response.headers.get("Access-Control-Expose-Headers") or "").strip()
            if "date" not in exposed.lower():
                response.headers["Access-Control-Expose-Headers"] = (
                    f"{exposed}, Date" if exposed else "Date"
                )

        forwarded_proto = str(flask_request.headers.get("X-Forwarded-Proto") or "").split(",", 1)[0].strip()
        request_is_https = flask_request.is_secure or forwarded_proto == "https"

        content_security_policy = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self'"
        )
        # Over TLS, tell the browser to auto-upgrade any stray http subresource
        # rather than send it in the clear. It is left off for plain-http local
        # development, where there is no TLS listener to upgrade to.
        if request_is_https:
            content_security_policy += "; upgrade-insecure-requests"
        response.headers["Content-Security-Policy"] = content_security_policy
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        if request_is_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        if (
            flask_request.path.startswith("/api/")
            and flask_request.path != "/api/realtime/versions"
            and flask_request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and response.status_code < 400
            and not getattr(g, "suppress_realtime_publish", False)
        ):
            try:
                publish_realtime_change(
                    realtime_scopes_for_api_mutation(flask_request.path),
                    source_path=flask_request.path,
                )
            except RuntimeError as error:
                app.logger.warning("Realtime change publication failed: %s", error)

        return response

    @app.before_request
    def protect_api_routes():
        path = flask_request.path
        if not path.startswith("/api/"):
            forwarded_proto = (
                str(flask_request.headers.get("X-Forwarded-Proto") or "")
                .split(",", 1)[0]
                .strip()
            )
            if (
                flask_request.method in {"GET", "HEAD"}
                and flask_request.scheme == "http"
                and forwarded_proto != "https"
                and request_is_from_server_device()
                and local_https_is_ready()
            ):
                query = flask_request.query_string.decode("utf-8", errors="ignore")
                suffix = f"?{query}" if query else ""
                return redirect(f"https://localhost{path}{suffix}", code=308)
            return None

        origin = normalized_request_origin()
        if origin and not cors_origin_is_allowed(origin):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "This website origin is not allowed to use the ICuCrops API."},
            )

        if flask_request.method == "OPTIONS" and flask_request.path.startswith("/api/"):
            return ("", int(HTTPStatus.NO_CONTENT))

        if api_path_is_public(path):
            return None

        if path in {
            "/api/sensors/readings",
            "/api/hardware/relays/desired",
            "/api/hardware/node-status",
            "/api/hardware/sync",
            "/api/hardware/commands/apply",
            "/api/hardware/commands/pending",
            "/api/hardware/commands/ack",
            "/api/hardware/notifications/deletions",
            "/api/hardware/sync/tombstones",
            "/api/hardware/sync/accounts",
            "/api/hardware/sync/cultivations",
            "/api/hardware/sync/notifications",
            "/api/hardware/sync/upload",
            "/api/hardware/sync/harvests",
        } and request_has_valid_device_token():
            g.authenticated_device = True
            return None

        session_user = verify_auth_session(request_bearer_token())
        if not session_user:
            return flask_json_response(
                HTTPStatus.UNAUTHORIZED,
                {
                    "code": "AUTH_SESSION_REQUIRED",
                    "message": "Your session has expired. Please sign in again.",
                },
            )

        user = session_user
        if app.config.get("AUTH_SESSION_REQUIRE_ACTIVE_USER", True):
            user = active_user_for_auth_session(session_user)
            revoke_reason = str(getattr(g, "auth_session_revoke_reason", "revoked") or "revoked")
            if not user:
                if revoke_reason == "backend-unavailable":
                    # Not an authentication failure: the records could not be
                    # read. A 401 here would make the browser discard a session
                    # that is still perfectly valid, so this must not be one.
                    return flask_json_response(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        {
                            "code": "AUTH_BACKEND_UNAVAILABLE",
                            "message": "The farm records could not be reached right now. Your session is still active -- please try again.",
                        },
                    )
                if revoke_reason == "superseded":
                    # Name the device that took over, so the person signed out
                    # can tell a colleague on the kiosk from someone unexpected.
                    taken_by = auth_session_device(str(session_user.get("id") or ""))
                    superseded_payload: dict[str, object] = {
                        "code": "AUTH_SESSION_SUPERSEDED",
                        "message": (
                            f"This account was opened on another device ({taken_by['label']}). "
                            "Only one device can be signed in at a time."
                            if taken_by
                            else "This account was used to sign in on another device. Only one device can be signed in at a time."
                        ),
                    }
                    if taken_by:
                        superseded_payload["device"] = taken_by
                    return flask_json_response(HTTPStatus.UNAUTHORIZED, superseded_payload)
                return flask_json_response(
                    HTTPStatus.UNAUTHORIZED,
                    {
                        "code": "AUTH_SESSION_REVOKED",
                        "message": "This account no longer has an active session. Please log in again.",
                    },
                )

        g.authenticated_user = user
        if api_request_requires_admin(path, flask_request.method) and not request_user_is_admin():
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "Administrator permission is required for this action."},
            )
        return None

    @app.errorhandler(404)
    def handle_not_found(error):
        if flask_request.path.startswith("/api/"):
            return flask_json_response(HTTPStatus.NOT_FOUND, {"message": "API endpoint not found."})
        return error

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        if flask_request.path.startswith("/api/"):
            return flask_json_response(HTTPStatus.METHOD_NOT_ALLOWED, {"message": "API endpoint not found."})
        return error

    # What an unauthenticated caller may see. Everything else in the health
    # payload describes the deployment rather than its liveness.
    #
    # This endpoint has to stay public: the Pi launcher, the kiosk's onboarding
    # server and the uplink watchdog all poll it to decide whether the backend
    # came up, and none of them hold a session. But it was answering with the
    # full report, so anyone could read the exact Supabase host
    # (aws-0-...pooler.supabase.com:6543 -- confirmed reachable from any
    # network), how many accounts exist, and which mail provider is in use.
    # That is a free target list for a credential attack, handed out over
    # HTTPS to people who never logged in.
    #
    # The pollers only look at the status code and, in the kiosk's case, at
    # "ok"/"degraded" -- see check_backend_health() in the onboarding server
    # and server_is_ready() in the Pi launcher. So the public shape keeps those
    # and drops the rest.
    PUBLIC_HEALTH_FIELDS = frozenset({"ok", "degraded", "cloudOnline", "piOnline"})

    @app.get("/api/health")
    def api_health_route():
        status, payload = api_health()
        # Verified here rather than read from g: the guard returns early for
        # public paths, so g.authenticated_user is never populated for this
        # route, even when an admin is signed in. Without this the full report
        # would be unreachable for everyone rather than merely private.
        if not verify_auth_session(request_bearer_token()):
            payload = {
                key: value
                for key, value in payload.items()
                if key in PUBLIC_HEALTH_FIELDS
            }
        return flask_json_response(status, payload)

    @app.get("/api/release")
    def api_release_route():
        return flask_json_response(
            HTTPStatus.OK,
            {
                "ok": True,
                # Read HEAD for every lightweight probe so frontend-only Git
                # updates can be reported without restarting the healthy API.
                "release": detect_application_release_id(),
            },
        )

    @app.get("/api/realtime/versions")
    def api_realtime_versions_route():
        return flask_json_response(
            HTTPStatus.OK,
            {
                "ok": True,
                "versions": read_realtime_versions(),
            },
        )

    @app.get("/api/kiosk/photos")
    def api_kiosk_photos_route():
        # Off the Pi the picker is never shown, so the endpoint does not exist
        # there either -- the managed cloud host has no business listing a disk.
        if not server_is_raspberry_pi():
            return flask_json_response(
                HTTPStatus.NOT_FOUND,
                {"message": "API endpoint not found."},
            )

        library = kiosk_photo_library_dir()
        return flask_json_response(
            HTTPStatus.OK,
            {
                "ok": True,
                "folder": library.name or str(library),
                "available": library.is_dir(),
                "photos": kiosk_photo_library_entries(),
            },
        )

    @app.get("/api/kiosk/photos/<name>")
    def api_kiosk_photo_file_route(name: str):
        if not server_is_raspberry_pi():
            return Response(status=int(HTTPStatus.NOT_FOUND))

        target = kiosk_photo_library_file(name)
        if target is None:
            return Response(status=int(HTTPStatus.NOT_FOUND))

        photo_path, content_type = target
        try:
            photo_data = photo_path.read_bytes()
        except OSError:
            return Response(status=int(HTTPStatus.NOT_FOUND))

        if len(photo_data) > MAX_PROFILE_PHOTO_BYTES:
            return Response(status=int(HTTPStatus.REQUEST_ENTITY_TOO_LARGE))

        response = Response(photo_data, status=int(HTTPStatus.OK), mimetype=content_type)
        response.headers["Content-Length"] = str(len(photo_data))
        return response

    @app.get("/profile-photo/<user_id>")
    def profile_photo_route(user_id: str):
        status, photo_data, content_type = api_get_profile_photo(
            user_id,
            str(flask_request.args.get("v") or ""),
        )
        if status != HTTPStatus.OK:
            return Response(status=int(status))
        response = Response(photo_data, status=int(status), mimetype=content_type)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        response.headers["Content-Length"] = str(len(photo_data))
        return response

    @app.route("/api/users", methods=["GET", "POST"])
    def api_users_route():
        if flask_request.method == "GET":
            if not request_user_is_admin():
                request_user = authenticated_request_user() or {}
                status, profile_payload = api_get_profile(str(request_user.get("id") or ""))
                if status != HTTPStatus.OK:
                    return flask_json_response(status, profile_payload)
                return flask_json_response(
                    HTTPStatus.OK,
                    {"users": [profile_payload["user"]]},
                )
            status, payload = api_list_users()
            return flask_json_response(status, payload)

        refused = refuse_without_acting_admin_password("adminPassword")
        if refused:
            return flask_json_response(*refused)
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = api_create_user(payload)
        return flask_json_response(status, response)

    @app.post("/api/users/confirm-admin-password")
    def api_users_confirm_admin_password_route():
        # Add User opens on the password card: the form only follows a password
        # this accepts. It changes nothing -- request-otp and POST /api/users
        # still check the password themselves -- and it counts against the same
        # lockout as every other guess.
        refused = refuse_without_acting_admin_password()
        if refused:
            return flask_json_response(*refused)
        return flask_json_response(HTTPStatus.OK, {"confirmed": True})

    @app.post("/api/users/request-otp")
    def api_users_request_otp_route():
        # The door to adding an account: verify-otp creates it only from a
        # challenge issued here, so the password is asked for once, up front.
        refused = refuse_without_acting_admin_password("adminPassword")
        if refused:
            return flask_json_response(*refused)
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = request_user_creation_otp(payload)
        return flask_json_response(status, response)

    @app.post("/api/users/verify-otp")
    def api_users_verify_otp_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = create_user_with_otp(payload)
        return flask_json_response(status, response)

    @app.delete("/api/users/<user_id>")
    def api_delete_user_route(user_id: str):
        refused = refuse_without_acting_admin_password()
        if refused:
            return flask_json_response(*refused)
        status, payload = api_delete_user(user_id)
        return flask_json_response(status, payload)

    @app.route("/api/profile/<user_id>", methods=["GET", "POST"])
    def api_profile_route(user_id: str):
        if not request_user_can_access(user_id):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "You can only access your own profile."},
            )
        if flask_request.method == "GET":
            status, payload = api_get_profile(user_id)
            return flask_json_response(status, payload)

        status, payload = api_update_profile(user_id)
        return flask_json_response(status, payload)

    @app.post("/api/profile/<user_id>/password/request-otp")
    def api_profile_password_request_otp_route(user_id: str):
        if not request_user_can_access(user_id):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "You can only change your own password."},
            )
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = request_profile_password_change_otp(user_id, payload)
        return flask_json_response(status, response)

    @app.post("/api/profile/<user_id>/password/confirm")
    def api_profile_password_confirm_route(user_id: str):
        if not request_user_can_access(user_id):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "You can only change your own password."},
            )
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = confirm_profile_password_change(user_id, payload)
        return flask_json_response(status, response)

    @app.route("/api/cultivations", methods=["GET", "POST"])
    def api_cultivations_route():
        if flask_request.method == "GET":
            status, payload = api_list_cultivations()
            # Both shells read the waiting requests with the crops, so the live
            # refresh that already polls this page carries them too.
            with connect_database() as connection:
                payload["requests"] = list_pending_cultivation_requests(connection)
            return flask_json_response(status, payload)

        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        request_user = authenticated_request_user() or {}
        payload["createdByUserId"] = str(request_user.get("id") or "")
        status, response = api_create_cultivation(payload)
        return flask_json_response(status, response)

    @app.patch("/api/cultivations/<cultivation_id>")
    def api_update_cultivation_route(cultivation_id: str):
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = api_update_cultivation(cultivation_id, payload)
        return flask_json_response(status, response)

    @app.delete("/api/cultivations/<cultivation_id>")
    def api_delete_cultivation_route(cultivation_id: str):
        refused = refuse_without_acting_admin_password()
        if refused:
            return flask_json_response(*refused)
        status, payload = api_delete_cultivation(cultivation_id)
        return flask_json_response(status, payload)

    # Under /api/cultivations on purpose: the prefix already invalidates the
    # cultivations/irrigation/sensors/notifications sync scopes, which is
    # exactly the set a harvest touches.
    @app.post("/api/cultivations/<cultivation_id>/harvest")
    def api_harvest_cultivation_route(cultivation_id: str):
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        request_user = authenticated_request_user() or {}
        payload["harvestedByUserId"] = str(request_user.get("id") or "")
        status, response = api_harvest_cultivation(cultivation_id, payload)
        return flask_json_response(status, response)

    @app.post("/api/cultivations/requests")
    def api_cultivation_requests_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})
        status, response = api_request_cultivation(payload, authenticated_request_user() or {})
        return flask_json_response(status, response)

    @app.post("/api/cultivations/requests/<request_id>/<decision>")
    def api_cultivation_request_decision_route(request_id: str, decision: str):
        verdicts = {"approve": "approved", "reject": "rejected"}
        if decision not in verdicts:
            return flask_json_response(HTTPStatus.NOT_FOUND, {"message": "API endpoint not found."})
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})
        status, response = api_decide_cultivation_request(
            request_id, verdicts[decision], payload, authenticated_request_user() or {}
        )
        return flask_json_response(status, response)

    @app.get("/api/cultivations/harvests")
    def api_cultivation_harvests_route():
        status, payload = api_list_cultivation_harvests()
        return flask_json_response(status, payload)

    @app.get("/api/sensors")
    def api_sensors_route():
        live = str(flask_request.args.get("live") or "").strip().lower() in {
            "1", "true", "yes", "on",
        }
        # How far back the caller intends to plot. Absent or unreadable means the
        # full retention window, which is what every caller before this got.
        try:
            history_days = int(str(flask_request.args.get("days") or "").strip())
        except ValueError:
            history_days = None
        status, payload = api_list_sensors(live=live, history_days=history_days)
        return flask_json_response(status, payload)

    @app.post("/api/sensors/control")
    def api_sensor_control_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = api_update_sensor_control(payload)
        return flask_json_response(status, response)

    @app.route("/api/sensors/registry", methods=["GET", "POST"])
    def api_sensor_registry_route():
        if flask_request.method == "GET":
            status, payload = api_list_sensor_registry()
            return flask_json_response(status, payload)

        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = api_upsert_sensor_registry(payload)
        return flask_json_response(status, response)

    @app.route("/api/sensors/definitions", methods=["GET", "POST"])
    def api_sensor_definitions_route():
        if flask_request.method == "GET":
            status, payload = api_list_sensor_definitions()
            return flask_json_response(status, payload)

        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = api_upsert_sensor_definition(payload)
        return flask_json_response(status, response)

    @app.route("/api/sensors/backends", methods=["GET", "POST"])
    def api_sensor_backends_route():
        if flask_request.method == "GET":
            status, payload = api_list_sensor_backends()
            return flask_json_response(status, payload)

        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = api_upsert_sensor_backend(payload)
        return flask_json_response(status, response)

    @app.post("/api/sensors/readings")
    def api_sensor_readings_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = api_create_sensor_reading(payload)
        return flask_json_response(status, response)

    @app.route("/api/irrigation", methods=["GET", "POST"])
    def api_irrigation_route():
        if flask_request.method == "GET":
            status, payload = api_get_irrigation()
            return flask_json_response(status, payload)

        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = api_update_irrigation(payload)
        return flask_json_response(status, response)

    @app.get("/api/hardware/relays/desired")
    def api_hardware_relay_desired_state_route():
        status, payload = api_get_relay_desired_state()
        return flask_json_response(status, payload)

    @app.get("/api/hardware/commands/pending")
    def api_hardware_commands_pending_route():
        if not getattr(g, "authenticated_device", False):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "A valid Raspberry Pi device token is required."},
            )
        status, payload = api_list_pending_hardware_commands()
        return flask_json_response(status, payload)

    @app.get("/api/hardware/notifications/deletions")
    def api_hardware_notification_deletions_route():
        if not getattr(g, "authenticated_device", False):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "A valid Raspberry Pi device token is required."},
            )
        status, payload = api_list_notification_deletions(
            after_deleted_at=str(flask_request.args.get("after") or ""),
            after_id=str(flask_request.args.get("afterId") or "0"),
        )
        return flask_json_response(status, payload)

    @app.get("/api/hardware/sync/tombstones")
    def api_hardware_sync_tombstones_route():
        if not getattr(g, "authenticated_device", False):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "A valid Raspberry Pi device token is required."},
            )
        status, payload = api_list_sync_tombstones(
            after_deleted_at=str(flask_request.args.get("after") or ""),
            limit=str(flask_request.args.get("limit") or "200"),
        )
        return flask_json_response(status, payload)

    @app.get("/api/hardware/sync/accounts")
    def api_hardware_sync_accounts_route():
        if not getattr(g, "authenticated_device", False):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "A valid Raspberry Pi device token is required."},
            )
        status, payload = api_list_sync_accounts(
            after_updated_at=str(flask_request.args.get("after") or ""),
            limit=str(flask_request.args.get("limit") or "200"),
        )
        return flask_json_response(status, payload)

    @app.get("/api/hardware/sync/cultivations")
    def api_hardware_sync_cultivations_route():
        if not getattr(g, "authenticated_device", False):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "A valid Raspberry Pi device token is required."},
            )
        status, payload = api_list_sync_cultivations(
            after_updated_at=str(flask_request.args.get("after") or ""),
            limit=str(flask_request.args.get("limit") or "200"),
        )
        return flask_json_response(status, payload)

    @app.get("/api/hardware/sync/notifications")
    def api_hardware_sync_notifications_route():
        if not getattr(g, "authenticated_device", False):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "A valid Raspberry Pi device token is required."},
            )
        status, payload = api_list_sync_notifications(
            after_id=str(flask_request.args.get("afterId") or ""),
            limit=str(flask_request.args.get("limit") or "200"),
        )
        return flask_json_response(status, payload)

    @app.post("/api/hardware/sync/upload")
    def api_hardware_sync_upload_route():
        if not getattr(g, "authenticated_device", False):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "A valid Raspberry Pi device token is required."},
            )
        try:
            body = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})
        status, response = api_apply_sync_upload(body)
        if not response.get("changed"):
            g.suppress_realtime_publish = True
        return flask_json_response(status, response)

    @app.post("/api/hardware/sync/harvests")
    def api_hardware_sync_harvests_route():
        if not getattr(g, "authenticated_device", False):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "A valid Raspberry Pi device token is required."},
            )
        try:
            body = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})
        status, response = api_exchange_sync_harvests(body)
        # Polled every minute; only a pass that stored something is news.
        if not response.get("changed"):
            g.suppress_realtime_publish = True
        return flask_json_response(status, response)

    @app.post("/api/hardware/commands/ack")
    def api_hardware_commands_ack_route():
        if not getattr(g, "authenticated_device", False):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "A valid Raspberry Pi device token is required."},
            )
        try:
            body = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})
        status, payload = api_acknowledge_hardware_command(body)
        return flask_json_response(status, payload)

    @app.post("/api/hardware/commands/apply")
    def api_hardware_command_apply_route():
        if not getattr(g, "authenticated_device", False):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "A valid Raspberry Pi device token is required."},
            )
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})
        status, response = api_apply_remote_hardware_command(payload)
        return flask_json_response(status, response)

    @app.get("/api/hardware/commands/<command_id>")
    def api_hardware_command_status_route(command_id: str):
        status, payload = api_get_remote_hardware_command_status(command_id)
        return flask_json_response(status, payload)

    @app.post("/api/hardware/node-status")
    def api_hardware_node_status_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = api_record_mqtt_node_status(payload)
        if not response.get("changed"):
            g.suppress_realtime_publish = True
        return flask_json_response(status, response)

    @app.post("/api/hardware/sync")
    def api_hardware_sync_route():
        if not getattr(g, "authenticated_device", False):
            return flask_json_response(
                HTTPStatus.FORBIDDEN,
                {"message": "A valid Raspberry Pi device token is required."},
            )
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})
        status, response = api_record_hardware_sync_batch(payload)
        if not response.get("nodeStatesChanged") and not response.get("readingsRecorded"):
            g.suppress_realtime_publish = True
        return flask_json_response(status, response)

    @app.post("/api/reports/preview")
    def api_reports_preview_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = api_report_preview(payload)
        return flask_json_response(status, response)

    @app.post("/api/reports/export")
    def api_reports_export_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        report_format = str(payload.get("format") or "").strip().lower()
        status, response = api_build_report(payload, report_format)
        if status != HTTPStatus.OK or not isinstance(response, dict) or "content" not in response:
            message = response.get("message") if isinstance(response, dict) else ""
            return flask_json_response(status, {"message": message or "Report export failed."})

        # The browser reads the filename from this header, so it has to survive
        # a proxy that only forwards what it is told to expose.
        download = Response(response["content"], mimetype=response["contentType"])
        download.headers["Content-Disposition"] = (
            f'attachment; filename="{response["filename"]}"'
        )
        download.headers["Content-Length"] = str(len(response["content"]))
        download.headers["Cache-Control"] = "no-store"
        download.headers["X-ICuCrops-Filename"] = response["filename"]
        download.headers["Access-Control-Expose-Headers"] = (
            "Content-Disposition, X-ICuCrops-Filename"
        )
        return download

    @app.get("/api/notifications")
    def api_notifications_route():
        request_user = authenticated_request_user() or {}
        status, payload = api_list_notifications(
            str(request_user.get("id") or ""),
            str(request_user.get("role") or ""),
        )
        return flask_json_response(status, payload)

    @app.delete("/api/notifications")
    def api_notifications_delete_all_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        request_user = authenticated_request_user() or {}
        payload["userId"] = str(request_user.get("id") or "")
        payload["role"] = str(request_user.get("role") or "")
        status, response = api_delete_all_notifications(payload)
        return flask_json_response(status, response)

    @app.post("/api/notifications/mark-read")
    def api_notifications_mark_read_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        request_user = authenticated_request_user() or {}
        payload["userId"] = str(request_user.get("id") or "")
        payload["role"] = str(request_user.get("role") or "")
        status, response = api_mark_notifications_read(payload)
        return flask_json_response(status, response)

    @app.delete("/api/notifications/<notification_id>")
    def api_notifications_delete_route(notification_id: str):
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        request_user = authenticated_request_user() or {}
        payload["userId"] = str(request_user.get("id") or "")
        payload["role"] = str(request_user.get("role") or "")
        status, response = api_delete_notification(notification_id, payload)
        return flask_json_response(status, response)

    @app.post("/api/auth/login")
    def api_login_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = login_user(payload, client_address=client_ip_address())
        if status == HTTPStatus.OK and isinstance(response.get("user"), dict):
            auth_client_id = normalize_auth_client_id(payload.get("clientId"))
            session = issue_auth_session(response["user"], client_id=auth_client_id)
            session_jti = str(session.pop("jti", "") or "")
            response["session"] = session
            user_id = str(response["user"].get("id") or "").strip()
            # Claim this as the account's live session. The jti and user id were
            # already being computed here and then dropped on the floor, which
            # is why single-session enforcement never actually engaged.
            # The farm kiosk is a shared terminal: signing in there must not
            # sign the same account out of a phone, so it never claims the
            # account's one live session. See request_is_farm_kiosk.
            if not request_is_farm_kiosk():
                claim_active_auth_session(user_id, session_jti, auth_client_id)
                remember_auth_session_device(
                    user_id,
                    describe_login_device(
                        str(flask_request.headers.get("User-Agent") or ""),
                        hints=payload.get("device"),
                    ),
                )
        return flask_json_response(status, response)

    @app.get("/api/auth/session")
    def api_auth_session_route():
        user = authenticated_request_user() or {}
        return flask_json_response(
            HTTPStatus.OK,
            {
                "ok": True,
                "user": user,
            },
        )

    @app.post("/api/auth/forgot-password/request-otp")
    def api_forgot_password_request_otp_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = request_password_reset_otp(payload)
        return flask_json_response(status, response)

    @app.post("/api/auth/forgot-password/verify-otp")
    def api_forgot_password_verify_otp_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = verify_password_reset_otp(payload)
        return flask_json_response(status, response)

    @app.post("/api/auth/forgot-password/reset")
    def api_forgot_password_reset_route():
        try:
            payload = parse_flask_json_body()
        except ValueError as error:
            return flask_json_response(HTTPStatus.BAD_REQUEST, {"message": str(error)})

        status, response = reset_password(payload)
        return flask_json_response(status, response)

    @app.get("/raspberry_pi/pi-runtime.js")
    def serve_pi_runtime():
        runtime_file = WORKSPACE_DIR / "raspberry_pi" / "pi-runtime.js"
        try:
            runtime_source = runtime_file.read_text(encoding="utf-8")
        except OSError:
            return ("Not Found", int(HTTPStatus.NOT_FOUND))

        bootstrap = (
            "window.ICuCropsServerPlatform = "
            f"{json.dumps(runtime_platform_payload(), separators=(',', ':'))};\n"
        )
        return Response(bootstrap + runtime_source, mimetype="application/javascript")

    @app.get("/")
    def serve_root():
        return send_from_directory(WORKSPACE_DIR, "index.html")

    @app.get("/<path:relative_path>")
    def serve_workspace_file(relative_path: str):
        target = (WORKSPACE_DIR / relative_path).resolve()
        workspace_root = WORKSPACE_DIR.resolve()

        try:
            relative_target = target.relative_to(workspace_root)
        except ValueError:
            return ("Not Found", int(HTTPStatus.NOT_FOUND))

        # The workspace root is the repository itself -- it holds .env, the
        # SQLite database, service-account files, and the source. This route
        # exists only to hand out the front-end's own assets, so it is a strict
        # allowlist: no dot-file or dot-directory (.env, .git, .icucrops-data)
        # is ever reachable, and only known web asset types are served. Without
        # this an unauthenticated GET /.env or /crops_db.sqlite would return the
        # file verbatim.
        if any(part.startswith(".") for part in relative_target.parts):
            return ("Not Found", int(HTTPStatus.NOT_FOUND))

        if target.is_dir():
            index_file = target / "index.html"
            if index_file.exists():
                relative_index = index_file.relative_to(workspace_root).as_posix()
                return send_from_directory(WORKSPACE_DIR, relative_index)
            return ("Not Found", int(HTTPStatus.NOT_FOUND))

        if not target.exists() or not target.is_file():
            return ("Not Found", int(HTTPStatus.NOT_FOUND))

        if target.suffix.lower() not in SERVABLE_STATIC_SUFFIXES:
            return ("Not Found", int(HTTPStatus.NOT_FOUND))

        return send_from_directory(WORKSPACE_DIR, relative_path)

    return app


def parse_args() -> argparse.Namespace:
    # Small CLI surface for local setup, diagnostics, and direct account maintenance.
    parser = argparse.ArgumentParser(description="Run the ICuCrops static and auth API server.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind the local server to.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind the local server to.")
    parser.add_argument(
        "--check-smtp",
        action="store_true",
        help="Validate Gmail SMTP credentials and exit.",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize the SQLite database and exit.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "list-users",
        help="List user accounts stored in the SQLite database and exit.",
    )

    add_user_parser = subparsers.add_parser(
        "add-user",
        help="Add a user account directly to the SQLite database and exit.",
    )
    add_user_parser.add_argument("--name", required=True, help="Display name for the new account.")
    add_user_parser.add_argument("--email", required=True, help="Gmail address for the new account.")
    add_user_parser.add_argument(
        "--role",
        default="user",
        choices=("admin", "user"),
        help="Role to assign to the new account.",
    )
    add_user_parser.add_argument("--password", required=True, help="Password for the new account.")

    delete_user_parser = subparsers.add_parser(
        "delete-user",
        help="Delete a user account directly from the SQLite database and exit.",
    )
    delete_user_target = delete_user_parser.add_mutually_exclusive_group(required=True)
    delete_user_target.add_argument("--id", type=int, help="Database id of the account to delete.")
    delete_user_target.add_argument("--email", help="Email address of the account to delete.")

    print_user_sql_parser = subparsers.add_parser(
        "print-user-sql",
        help="Print a ready-to-run SQL INSERT statement for a new user account and exit.",
    )
    print_user_sql_parser.add_argument("--name", required=True, help="Display name for the new account.")
    print_user_sql_parser.add_argument("--email", required=True, help="Gmail address for the new account.")
    print_user_sql_parser.add_argument(
        "--role",
        default="user",
        choices=("admin", "user"),
        help="Role to assign to the new account.",
    )
    print_user_sql_parser.add_argument("--password", required=True, help="Password for the new account.")
    return parser.parse_args()


def sql_text_literal(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def build_manual_user_insert_sql(*, display_name: str, email: str, role: str, password: str) -> str:
    password_salt, password_hash = create_secret_hash(password, iterations=PASSWORD_ITERATIONS)
    timestamp = utc_now_iso()
    values = {
        "display_name": sql_text_literal(display_name),
        "email": sql_text_literal(email),
        "role": sql_text_literal(role),
        "password_hash": sql_text_literal(password_hash),
        "password_salt": sql_text_literal(password_salt),
        "created_at": sql_text_literal(timestamp),
        "updated_at": sql_text_literal(timestamp),
        "profile_photo_path": sql_text_literal(""),
    }
    return (
        "INSERT INTO users (\n"
        "    display_name,\n"
        "    email,\n"
        "    role,\n"
        "    password_hash,\n"
        "    password_salt,\n"
        "    password_iterations,\n"
        "    is_active,\n"
        "    created_at,\n"
        "    updated_at,\n"
        "    profile_photo_path\n"
        ") VALUES (\n"
        f"    {values['display_name']},\n"
        f"    {values['email']},\n"
        f"    {values['role']},\n"
        f"    {values['password_hash']},\n"
        f"    {values['password_salt']},\n"
        f"    {PASSWORD_ITERATIONS},\n"
        "    1,\n"
        f"    {values['created_at']},\n"
        f"    {values['updated_at']},\n"
        f"    {values['profile_photo_path']}\n"
        ");"
    )


def run_list_users_command() -> None:
    with connect_database() as connection:
        users = list_users(connection)

    if not users:
        print("No users found.", flush=True)
        return

    print("id\trole\tactive\temail\tdisplay_name", flush=True)
    for user in users:
        print(
            f"{int(user['id'])}\t{normalize_role(user['role'])}\t{int(user['is_active'])}\t{str(user['email']).strip()}\t{str(user['display_name']).strip()}",
            flush=True,
        )


def run_add_user_command(args: argparse.Namespace) -> None:
    try:
        display_name, email, role, password = validate_user_account_fields(
            display_name=args.name,
            email=args.email,
            role=args.role,
            password=args.password,
        )
    except ValueError as error:
        print(str(error), flush=True)
        raise SystemExit(1)

    try:
        with connect_database() as connection:
            user = create_user_account(
                connection,
                display_name=display_name,
                email=email,
                role=role,
                password=password,
            )
    except sqlite3.IntegrityError:
        print("That Gmail address is already registered.", flush=True)
        raise SystemExit(1)

    print(
        f"Added user #{int(user['id'])}: {str(user['display_name']).strip()} <{str(user['email']).strip()}> ({normalize_role(user['role'])})",
        flush=True,
    )


def run_delete_user_command(args: argparse.Namespace) -> None:
    with connect_database() as connection:
        user = delete_user_account_record(
            connection,
            user_id=args.id,
            email=args.email,
        )

    if not user:
        identifier = f"id {args.id}" if args.id is not None else f"email {normalize_email(args.email)}"
        print(f"No user found for {identifier}.", flush=True)
        raise SystemExit(1)

    print(
        f"Deleted user #{int(user['id'])}: {str(user['display_name']).strip()} <{str(user['email']).strip()}> ({normalize_role(user['role'])})",
        flush=True,
    )


def run_print_user_sql_command(args: argparse.Namespace) -> None:
    try:
        display_name, email, role, password = validate_user_account_fields(
            display_name=args.name,
            email=args.email,
            role=args.role,
            password=args.password,
        )
    except ValueError as error:
        print(str(error), flush=True)
        raise SystemExit(1)

    print(
        build_manual_user_insert_sql(
            display_name=display_name,
            email=email,
            role=role,
            password=password,
        ),
        flush=True,
    )


def main() -> None:
    # Entry point supports both one-off maintenance commands and the long-running Flask server.
    args = parse_args()
    ensure_database()
    auth_session_secret()
    device_api_token()

    if args.command == "list-users":
        run_list_users_command()
        return

    if args.command == "add-user":
        run_add_user_command(args)
        return

    if args.command == "delete-user":
        run_delete_user_command(args)
        return

    if args.command == "print-user-sql":
        run_print_user_sql_command(args)
        return

    if args.check_smtp:
        try:
            verify_smtp_login()
        except MailConfigurationError as error:
            print(str(error), flush=True)
            raise SystemExit(1)
        except smtplib.SMTPAuthenticationError as error:
            print(smtp_auth_failure_payload(error)["message"], flush=True)
            print(str(error), flush=True)
            raise SystemExit(1)
        except (OSError, smtplib.SMTPException) as error:
            print("SMTP connection failed.", flush=True)
            print(str(error), flush=True)
            raise SystemExit(1)

        print("Gmail SMTP login succeeded.", flush=True)
        return

    if args.init_db:
        print(f"SQLite database initialized at {DATABASE_PATH}", flush=True)
        if not smtp_is_configured():
            print(
                "Gmail SMTP is not configured yet. Set ICUCROPS_SMTP_* in your environment or .env before testing OTP delivery.",
                flush=True,
            )
        return

    base_url = f"http://{args.host}:{args.port}/"
    app = create_app()

    # Keep the legacy marker because VS Code's serverReadyAction uses it to
    # detect readiness, while the browser itself opens the trusted HTTPS URL.
    print(f"ICuCrops Flask server running at {base_url}", flush=True)
    print("Login UI: https://localhost/auth/index.html#/", flush=True)
    print(f"Private backend: {base_url}", flush=True)
    print(f"API health: {base_url}api/health", flush=True)
    if not smtp_is_configured():
        print(
            "Warning: Gmail SMTP is not configured. OTP emails will fail until ICUCROPS_SMTP_* is set in your environment or .env.",
            flush=True,
        )
    print("Press Ctrl+C to stop the server.", flush=True)

    try:
        # Call Werkzeug directly instead of Flask.app.run(). Flask deliberately
        # returns without starting a server when FLASK_RUN_FROM_CLI is truthy.
        # A stale value in a Pi service environment therefore looks like a
        # successful process exit and sends systemd into an endless restart
        # loop. run_simple() always binds here and blocks for the service.
        run_simple(
            hostname=args.host,
            port=args.port,
            application=app,
            use_debugger=False,
            use_reloader=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        print("\nStopping ICuCrops local server...", flush=True)


if __name__ == "__main__":
    main()
