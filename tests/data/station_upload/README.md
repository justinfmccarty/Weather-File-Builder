# Station-upload fixtures

Built from one private 1-minute weather logger in Zurich (47.41 N, 8.51 E,
about 530 m; export `weather_data.csv`, Oct 2024 to Jan 2026, 80.8 MB) with
`scripts/prepare_station_upload_fixtures.py`. The raw export is not in the
repository.

| File | What it is | Expected result |
|---|---|---|
| `station_upload_reject.parquet` | The logger's own values for 10–16 Feb 2025, 16–22 Jun 2025 and 8–12 Jan 2026: 1-minute rows, the original timestamps, contract column names, nothing else fixed | Rejected: unknown column, 1-minute spacing, out-of-range values, clock |
| `station_upload_pass.parquet` | Calendar year 2025 (UTC), hourly, prepared as described below | Passes; builds a full (not partial) 2025 AMY |
| `station_upload_fill_log.csv` | Every (hour, variable) taken from MeteoSwiss Zurich/Affoltern | — |

## What was wrong with the export

1. **Clock.** Timestamps carry `+00` but are Swiss wall-clock time. The
   irradiance peak jumps about +60 min on 30 Mar 2025 and about −90 min on
   26 Oct 2025, when daylight saving starts and ends. The first weeks
   (9–26 Oct 2024) do not jump on 27 Oct 2024 and look like UTC+1 without
   daylight saving. They are outside 2025 and not used.
2. **Outages.** 44 outages longer than 6 h (1,336 h in total). Many run from
   about 23:00 to 07:00–08:00 night after night (for example 25–29 Nov 2024),
   which suggests the logger loses power overnight. The longest are
   25 Dec 2024 – 6 Jan 2025 (282 h) and 15–21 Oct 2025 (150 h). In 2025 every
   month has an outage longer than 6 h, so without filling no AMY month can be
   built.
3. **Units.** `pressure` is in hPa. `rainfall` is not mm per minute: read
   that way, 2025 would total about 36,900 mm. Read as a rate in mm/h logged
   every minute, it gives about 615 mm.
4. **Junk.** 180 values such as 7.7e31 °C, 2.1e11 m/s and rainfall of 7.9e34.
   179 of them fall in 7–13 Jan 2026, when a sensor was failing. There is
   also one −40.00 °C fault value.
5. **Wind direction.** 26,272 values between 360° and 400° (the vane wrapping
   past north) and 161 above 720°, up to 18,049° (junk).
6. **Irradiance sensor.** It reads 25–60 % of Affoltern's global irradiance
   (May–Jul about 28 %), close to zero at the low December sun, and peaks
   5–38 min after solar noon even with the clock fixed. That points to a
   shaded or tilted sensor. The validator accepts it with warnings, but the
   direct/diffuse split and sky cover derived from it are not trustworthy.
   **Do not use this AMY as a reference file**: it is a test fixture.

## What was done to make `station_upload_pass.parquet`

1. Dropped the `+00` suffix and read the timestamps as Europe/Zurich wall
   clock, then converted to UTC. The 120 minutes of the repeated hour when
   daylight saving ends cannot be told apart and were dropped.
2. Renamed the columns to the contract names:
   `temperature→temp_C`, `relative_humidity→rh_pct`, `pressure→pressure_Pa`,
   `irradiation→ghi_Wm2`, `average_wind_speed→wind_speed_ms`,
   `wind_direction→wind_dir_deg`. Dropped `max_wind_speed` and `wind_gust`,
   which are not in the contract, and `rainfall`, whose unit is uncertain.
3. Pressure ×100 (hPa to Pa).
4. Wind directions in (360°, 720°] reduced by 360°.
5. Set to missing: the −40.00 °C fault value and anything outside these
   ranges: temperature −35 to 45 °C, RH 0–105 %, pressure 850–1050 hPa,
   irradiance 0–1500 W/m², wind 0–60 m/s, direction 0–360°.
6. 1 minute → hourly, period ending (minutes :01–:00 make the hour ending
   at :00): means, and a speed-weighted vector mean for direction. An hour
   needs at least 30 one-minute readings.
7. Gaps longer than 6 h (958 h of each variable, 11 % of the year) filled
   from **MeteoSwiss Zürich/Affoltern (REH)**, 2.1 km away at 444 m,
   10-minute data aggregated the same way. Monthly corrections were fitted on
   the 8,953 hours both have:

   | Variable | Correction | Bias before → after | RMSE before → after |
   |---|---|---|---|
   | temperature | + 0.1 to 1.2 K by month (the logger is warmer) | −0.66 → 0.00 K | 1.99 → 1.84 K |
   | RH | −5.1 to +2.7 % by month | +1.1 → 0.0 % | 8.7 → 8.2 % |
   | pressure | −8.6 to −9.0 hPa (height) | — | 8.8 → 0.6 hPa |
   | irradiance | ratio by month and hour of day (0.25–0.63 monthly) | +81 → +4 W/m² | 168 → 62 W/m² |
   | wind speed | ratio 0.92–1.16 by month | −0.08 → 0.00 m/s | 0.94 → 0.98 m/s |
   | direction | none | 16° mean difference | — |

   The errors are in-sample. Filled hours are listed in
   `station_upload_fill_log.csv`.
8. The remaining 81 h of short gaps (≤ 6 h) were left for the builder to
   interpolate. Values rounded to 2 decimals; `timestamp` written as a UTC
   timestamp type.

What the validator then says: the file passes. It warns about clock offsets
of +20 to +38 min (Jun–Aug, Dec), low irradiance in May–Jul, and too few
typical-year candidates. The 2025 AMY builds with one edge hour (00:00–01:00
on 1 January local time) taken from the adjacent day.

Data: contains data from MeteoSwiss (Federal Office of Meteorology and
Climatology), open government data, Zürich/Affoltern 10-minute values.
