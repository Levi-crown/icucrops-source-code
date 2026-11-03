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

ICuCrops was made for Sarate Agriculture Farm in San Pablo, Laguna. The farm grows
pechay, bok choy, mustasa and green ice lettuce in soil beds, and it used to water them
on a fixed schedule, twice a day, whether the soil needed it or not.

ICuCrops puts sensors in every cultivation row and in the greenhouse air. It reads soil
moisture, soil pH, EC, temperature, humidity and light, and checks each reading against
the range of the crop planted in that row. From there it:

- waters a row when the soil gets too dry, and stops once the row has enough water
- runs the exhaust fan when the air gets too humid
- turns on the grow light when it gets dark or too cold
- alerts the farm staff when pH, EC, temperature, humidity or light goes out of range
- counts the days from planting so the staff know when a crop is due for harvest

Administrators and users follow all of this on a web dashboard, where they can also
control the equipment by hand and download reports.

This repository has the website (frontend) and the Flask server (backend) only. The
sensor firmware is not included.

> [!IMPORTANT]
> **There is no sensitive information in this repository.** No API keys, no passwords,
> no `.env` files, no Supabase connection strings and no database files. The server reads
> its keys from the computer it runs on, so none of them are written in the code.

---

## <img src="assets/icons/database.svg" width="26" height="26" align="absmiddle" alt=""> Database

<table>
  <tr>
    <td width="50%" align="center" valign="top">
      <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/supabase/supabase-original.svg" width="80" alt="Supabase logo">
      <h3>Supabase</h3>
      <p><b>Online database (PostgreSQL)</b></p>
      <p>Stores the accounts, sensor readings, cultivations, equipment controls, alerts
      and history, so the website can be opened outside the farm.</p>
    </td>
    <td width="50%" align="center" valign="top">
      <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/sqlite/sqlite-original.svg" width="80" alt="SQLite logo">
      <h3>SQLite</h3>
      <p><b>Offline database at the farm</b></p>
      <p>Keeps monitoring and watering running when the internet is down. The two
      databases sync again once the connection is back.</p>
    </td>
  </tr>
</table>

---

## <img src="assets/icons/code.svg" width="26" height="26" align="absmiddle" alt=""> Languages used

<p align="center">
  <img src="https://skillicons.dev/icons?i=py,js,html,css,postgres,sqlite,supabase,flask&theme=dark" alt="Python, JavaScript, HTML, CSS, SQL, SQLite, Supabase, Flask">
</p>

| Language | Used for |
| --- | --- |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/python/python-original.svg" width="20"> **Python** | The Flask server, the watering and climate rules, database code and reports |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/javascript/javascript-original.svg" width="20"> **JavaScript** | The dashboard, live graphs and equipment controls |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/html5/html5-original.svg" width="20"> **HTML5** | The administrator, user, sign-in and mobile pages |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/css3/css3-original.svg" width="20"> **CSS3** | Layout, colors, dark mode and the touchscreen panel |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/postgresql/postgresql-original.svg" width="20"> **SQL** | The Supabase tables and the SQLite queries |

---

## <img src="assets/icons/gauge.svg" width="26" height="26" align="absmiddle" alt=""> What ICuCrops monitors

| | Reading | Sensor | What ICuCrops does with it |
| :---: | --- | --- | --- |
| <img src="assets/icons/tile-drop.svg" width="36" height="36" alt=""> | **Soil moisture** | Capacitive probes, averaged per row | Waters the row when it is too dry |
| <img src="assets/icons/tile-flask.svg" width="36" height="36" alt=""> | **Soil pH** | RS485 soil sensor | Alerts the staff when the pH is outside the crop's range |
| <img src="assets/icons/tile-lightning.svg" width="36" height="36" alt=""> | **EC** (electrical conductivity) | RS485 soil sensor | Alerts the staff when the soil is too salty or low on nutrients |
| <img src="assets/icons/tile-thermometer-simple.svg" width="36" height="36" alt=""> | **Temperature** | DHT22 | Turns on the grow light when it is too cold, alerts when it is too hot |
| <img src="assets/icons/tile-drop-half-bottom.svg" width="36" height="36" alt=""> | **Humidity** | DHT22 | Runs the exhaust fan when the air is too humid |
| <img src="assets/icons/tile-sun.svg" width="36" height="36" alt=""> | **Light** | HW-072 light sensor | Turns on the grow light when it is dark |

## <img src="assets/icons/sliders-horizontal.svg" width="26" height="26" align="absmiddle" alt=""> What ICuCrops controls

| | Equipment | How it runs |
| :---: | --- | --- |
| <img src="assets/icons/tile-shower.svg" width="36" height="36" alt=""> | **Water valve** (one per row) | Automatic, Manual or Scheduled. Stops when the soil has enough water. |
| <img src="assets/icons/tile-cloud-fog.svg" width="36" height="36" alt=""> | **Misting** | Turned on from the dashboard, or set to run with the irrigation |
| <img src="assets/icons/tile-fan.svg" width="36" height="36" alt=""> | **Exhaust fan** | Runs when the humidity goes above the crop's limit |
| <img src="assets/icons/tile-lightbulb.svg" width="36" height="36" alt=""> | **Grow light** | Runs when it is dark (up to 4 hours at a time) or when the air is too cold |
| <img src="assets/icons/tile-test-tube.svg" width="36" height="36" alt=""> | **Lime solution** | Applied by the staff after ICuCrops flags a low soil pH |

---

## <img src="assets/icons/squares-four.svg" width="26" height="26" align="absmiddle" alt=""> Features

<table>
  <tr>
    <td width="50%" valign="top">

<img src="assets/icons/tile-drop.svg" width="44" height="44" alt="">

### Irrigation
- Each row is watered on its own
- Automatic, Manual and Scheduled modes
- Moisture limits keep a row from being under- or over-watered

    </td>
    <td width="50%" valign="top">

<img src="assets/icons/tile-thermometer-simple.svg" width="44" height="44" alt="">

### Greenhouse climate
- Exhaust fan for high humidity
- Grow light for dark or cold hours
- Misting for dry air

    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">

<img src="assets/icons/tile-chart-line-up.svg" width="44" height="44" alt="">

### Readings and reports
- Live readings and graphs for each row
- History of readings and farm events
- Reports in Excel and PDF
- Alerts when a reading is out of range

    </td>
    <td width="50%" valign="top">

<img src="assets/icons/tile-plant.svg" width="44" height="44" alt="">

### Cultivation
- Pick a crop and a row to start a cultivation
- Set ranges for pechay, bok choy, mustasa and green ice lettuce
- Expected harvest date counted from the planting date
- Users request a cultivation and an administrator approves it

    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">

<img src="assets/icons/tile-shield-check.svg" width="44" height="44" alt="">

### Accounts
- Administrator and User accounts
- Password reset with a code sent by email
- One active sign-in per account

    </td>
    <td width="50%" valign="top">

<img src="assets/icons/tile-devices.svg" width="44" height="44" alt="">

### Where to use it
- On a computer or a phone
- On the touchscreen panel at the farm, even without internet
- Light and dark mode

    </td>
  </tr>
</table>

---

## <img src="assets/icons/flow-arrow.svg" width="26" height="26" align="absmiddle" alt=""> How it works

<p align="center">
  <img src="assets/icucrops-how-it-works.svg" alt="How ICuCrops works, from the sensors in the field to the people who use the website" width="100%">
</p>

1. **Field.** Each of the 4 rows has 3 soil-moisture probes and an RS485 sensor for pH and EC.
   A DHT22 and an HW-072 light sensor read the greenhouse air.
2. **Edge.** Four ESP32 boards, one per row, read the soil sensors and switch the relays for the
   water valves, lime and fertilizer lines, exhaust fans, grow light and misting line. A fifth
   ESP32 reads the air and light sensors.
3. **Local server.** The ESP32 boards send their readings to the Raspberry Pi 4 over MQTT.
   The Flask server checks them against the crop planted in each row, decides what to turn on
   or off, saves everything in SQLite and shows it on the kiosk.
4. **Cloud.** When the internet is on, the Pi syncs with Supabase. Vercel serves the website
   for people outside the farm, and an email service sends the sign-in and reset codes.
5. **People.** Administrators and users open ICuCrops on a phone, a computer or the kiosk.
   At the farm it keeps working even when the internet is down.

---

## <img src="assets/icons/stack.svg" width="26" height="26" align="absmiddle" alt=""> Tech stack

| Part | Built with |
| --- | --- |
| **Database** | Supabase (PostgreSQL) online, SQLite offline |
| **Backend** | Python 3.11+, Flask, psycopg, Pillow |
| **Frontend** | HTML5, CSS3 and plain JavaScript, no framework |
| **Reports** | Excel (.xlsx) and PDF files made by the server itself |

---

## <img src="assets/icons/folder-open.svg" width="26" height="26" align="absmiddle" alt=""> Project structure

```text
icucrops-source-code/
├── administrator/        # Administrator pages: dashboard, irrigation, cultivation,
│                         # sensors, history, accounts, settings
├── user/                 # User pages: the same, without account management
├── auth/                 # Sign-in and password-reset pages
├── mobile_web/           # Phone layouts for both
├── assets/               # Shared styles, scripts, icons, logos and photos
├── supabase/
│   └── migrations/       # Supabase table definitions
├── main.py               # Flask server: pages, API routes, watering and climate rules
├── icucrops_pg.py        # Supabase (PostgreSQL) database code
├── icucrops_reports.py   # Excel and PDF reports
└── requirements.txt      # Python packages
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
