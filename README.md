<p align="center">
  <img src="assets/icucrops-sensors-hero.svg" alt="ICuCrops: An IoT Web-Based System for Crops Cultivation and Monitoring for Sarate Agriculture Farm in San Pablo, Laguna" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Supabase">
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-145F3E?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="JavaScript">
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white" alt="HTML5">
  <img src="https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white" alt="CSS3">
  <img src="https://img.shields.io/badge/SQL-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="SQL">
  <img src="https://img.shields.io/badge/No%20secrets-included-0E3D2B?style=for-the-badge&logo=letsencrypt&logoColor=white" alt="No secrets included">
</p>

---

## <img src="assets/icons/leaf.svg" width="26" height="26" align="absmiddle" alt=""> About

ICuCrops is an IoT web-based system for crops cultivation and monitoring, built for
Sarate Agriculture Farm in San Pablo, Laguna. Sensors in the soil and in
the air report their readings to a Flask backend, which stores them, decides when to
irrigate, run the fan or switch on the grow light, and serves a web dashboard where
people see every row at a glance and control the equipment by hand when they need to.

**Supabase (PostgreSQL)** is the cloud database. It holds the accounts, sensor
readings, cultivations, irrigation controls, notifications and history, so the dashboard
works from anywhere, and a local SQLite copy keeps the greenhouse running when the
internet drops.

> This repository contains the basic **frontend** and **backend** source code only.
> The sensor firmware and hardware-communication code are not included.

> [!IMPORTANT]
> **No sensitive information is included in this repository.**
> There are **no API keys**, no `.env` files, no passwords, no Supabase connection
> strings, no tokens and no database files here. Every secret is read from the
> environment of the machine that runs ICuCrops and is never written into the code.

---

## <img src="assets/icons/database.svg" width="26" height="26" align="absmiddle" alt=""> Database

<table>
  <tr>
    <td width="50%" align="center" valign="top">
      <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/supabase/supabase-original.svg" width="80" alt="Supabase logo">
      <h3>Supabase</h3>
      <p><b>Cloud database (PostgreSQL)</b></p>
      <p>The main online store for accounts, sensor readings, cultivations, irrigation
      controls, notifications and history. The website reads and writes here, so the
      farm can be followed from anywhere.</p>
    </td>
    <td width="50%" align="center" valign="top">
      <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/sqlite/sqlite-original.svg" width="80" alt="SQLite logo">
      <h3>SQLite</h3>
      <p><b>Local database (offline copy)</b></p>
      <p>Runs beside the greenhouse so sensors, automation and the kiosk keep working
      when the internet is down. It syncs with Supabase once the connection is back.</p>
    </td>
  </tr>
</table>

---

## <img src="assets/icons/code.svg" width="26" height="26" align="absmiddle" alt=""> Languages used

<p align="center">
  <img src="https://skillicons.dev/icons?i=py,js,html,css,postgres,sqlite,supabase,flask&theme=dark" alt="Python, JavaScript, HTML, CSS, SQL, SQLite, Supabase, Flask">
</p>

| Language | Where it is used |
| --- | --- |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/python/python-original.svg" width="20"> **Python** | Backend: Flask server, automation rules, database layer, reports |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/javascript/javascript-original.svg" width="20"> **JavaScript** | Frontend logic: dashboard, live graphs, controls, real-time sync |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/html5/html5-original.svg" width="20"> **HTML5** | Every page of the Administrator, User, sign-in and mobile portals |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/css3/css3-original.svg" width="20"> **CSS3** | Styling, emerald theme, dark mode, mobile and kiosk layouts |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/postgresql/postgresql-original.svg" width="20"> **SQL** | Supabase (PostgreSQL) schema migrations and SQLite queries |

---

## <img src="assets/icons/gauge.svg" width="26" height="26" align="absmiddle" alt=""> What ICuCrops monitors

| | Reading | Sensor | What it is used for |
| :---: | --- | --- | --- |
| <img src="assets/icons/tile-drop.svg" width="36" height="36" alt=""> | **Soil Moisture** | Capacitive soil-moisture probes (per row) | Decides when each row needs water |
| <img src="assets/icons/tile-flask.svg" width="36" height="36" alt=""> | **Soil pH** | RS485 soil sensor | Shows soil acidity; tells when lime solution is needed |
| <img src="assets/icons/tile-lightning.svg" width="36" height="36" alt=""> | **EC (Electrical Conductivity)** | RS485 soil sensor | Shows the nutrient / salt level of the soil |
| <img src="assets/icons/tile-thermometer-simple.svg" width="36" height="36" alt=""> | **Temperature** | DHT22 | Greenhouse air temperature; drives the fan and grow light |
| <img src="assets/icons/tile-drop-half-bottom.svg" width="36" height="36" alt=""> | **Humidity** | DHT22 | Greenhouse air humidity; turns the fan on when it is too humid |
| <img src="assets/icons/tile-sun.svg" width="36" height="36" alt=""> | **Light** | HW-072 light sensor | Detects dark or bright; runs the grow light in the dark |

## <img src="assets/icons/sliders-horizontal.svg" width="26" height="26" align="absmiddle" alt=""> What ICuCrops controls

| | Equipment | How it runs |
| :---: | --- | --- |
| <img src="assets/icons/tile-shower.svg" width="36" height="36" alt=""> | **Irrigation pump** | Automatic, Manual or Scheduled, per row, with moisture safety limits |
| <img src="assets/icons/tile-cloud-fog.svg" width="36" height="36" alt=""> | **Misting** | Follows the irrigation, or on a timer |
| <img src="assets/icons/tile-fan.svg" width="36" height="36" alt=""> | **Fan** | Turns on when the humidity is high |
| <img src="assets/icons/tile-lightbulb.svg" width="36" height="36" alt=""> | **Grow light** | Turns on in the dark, with a daily limit |
| <img src="assets/icons/tile-test-tube.svg" width="36" height="36" alt=""> | **Lime solution** | Applied when the soil pH is too low |

---

## <img src="assets/icons/squares-four.svg" width="26" height="26" align="absmiddle" alt=""> Features

<table>
  <tr>
    <td width="50%" valign="top">

<img src="assets/icons/tile-drop.svg" width="44" height="44" alt="">

### Smart irrigation
- Live soil-moisture reading for every row
- **Automatic**, **Manual** and **Scheduled** watering modes
- Safety bands that stop watering at the right moisture level
- Misting that follows the irrigation

    </td>
    <td width="50%" valign="top">

<img src="assets/icons/tile-thermometer-simple.svg" width="44" height="44" alt="">

### Greenhouse climate
- Temperature and humidity (DHT22) and light sensing
- Fan runs on high humidity
- Grow light runs in the dark, with a daily limit
- Lime solution control for soil pH

    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">

<img src="assets/icons/tile-chart-line-up.svg" width="44" height="44" alt="">

### Monitoring & reports
- Real-time dashboard and live graphs
- Per-sensor detail pages and history log
- Downloadable reports as **Excel (.xlsx)** and **PDF**
- Alerts and notifications

    </td>
    <td width="50%" valign="top">

<img src="assets/icons/tile-plant.svg" width="44" height="44" alt="">

### Cultivation tracking
- Plant and track crops per row
- Growth parameters and harvest records
- Cultivation requests from growers, approved by admins
- Harvest outcome tracking

    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">

<img src="assets/icons/tile-shield-check.svg" width="44" height="44" alt="">

### Accounts & security
- Separate **Administrator** and **User** portals
- Email OTP password reset
- Single-session sign-in per account
- Profile management with photos

    </td>
    <td width="50%" valign="top">

<img src="assets/icons/tile-devices.svg" width="44" height="44" alt="">

### Works everywhere
- Desktop web dashboard
- Mobile-friendly pages
- Touch kiosk mode for the greenhouse panel
- Light and dark appearance

    </td>
  </tr>
</table>

---

## <img src="assets/icons/flow-arrow.svg" width="26" height="26" align="absmiddle" alt=""> How it works

```mermaid
flowchart LR
    A["Greenhouse sensors<br/>moisture, pH, EC, DHT22, light"] --> B["Flask backend<br/>main.py"]
    B -- relays --> C["Pump, misting, fan,<br/>grow light, lime"]
    B <--> D[("Supabase<br/>PostgreSQL")]
    B <--> E[("Local SQLite<br/>offline copy")]
    B --> F["Web dashboard<br/>Administrator, User, Mobile"]
```

---

## <img src="assets/icons/stack.svg" width="26" height="26" align="absmiddle" alt=""> Tech stack

| Layer | Technology |
| --- | --- |
| **Database** | **Supabase** (PostgreSQL) in the cloud + **SQLite** locally for offline use |
| **Backend** | Python 3.11+, Flask, psycopg, Pillow |
| **Languages** | Python, JavaScript, HTML5, CSS3, SQL |
| **Frontend** | HTML5, CSS3, vanilla JavaScript, no framework |
| **Reports** | Built-in Excel (.xlsx) and PDF writers |

---

## <img src="assets/icons/folder-open.svg" width="26" height="26" align="absmiddle" alt=""> Project structure

```text
icucrops-source-code/
├── administrator/        # Administrator portal: dashboard, irrigation, cultivation,
│                         # sensors, history, user management, settings
├── user/                 # Grower portal: the same pages without admin tools
├── auth/                 # Sign-in and password-reset pages
├── mobile_web/           # Mobile layouts for both portals
├── assets/               # Shared styles, scripts, icons, logos and images
├── supabase/
│   └── migrations/       # Supabase PostgreSQL schema
├── main.py               # Flask backend: pages, REST endpoints, automation rules
├── icucrops_pg.py        # Supabase / PostgreSQL data layer
├── icucrops_reports.py   # Excel and PDF report builder
└── requirements.txt      # Python dependencies
```

---

## <img src="assets/icons/users-three.svg" width="26" height="26" align="absmiddle" alt=""> Team

<p align="center">
  <img src="assets/ChrisPic.png" width="90" alt="Team member">
  <img src="assets/EronPic.png" width="90" alt="Team member">
  <img src="assets/jhonelPic.png" width="90" alt="Team member">
  <img src="assets/sheilaPic.png" width="90" alt="Team member">
</p>

<p align="center">
  <img src="assets/icucrops-logo-transparent.png" width="120" alt="ICuCrops logo">
  <br>
  <sub>ICuCrops: An IoT Web-Based System for Crops Cultivation and Monitoring for Sarate Agriculture Farm in San Pablo, Laguna</sub>
</p>
