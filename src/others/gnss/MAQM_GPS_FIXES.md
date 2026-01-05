# MAQM_main.py GPS Improvements

## Changes Made

### 1. Added GPS Fix Status Tracking
**Location**: [MAQM_main.py:60](MAQM_main.py#L60)

Added `"fix_status"` field to track whether GPS has an active fix.
- `"A"` = Active (valid GPS fix)
- `"V"` = Void (no fix, waiting for satellites)
- `None` = No data received yet

**Before:**
```python
self.last_position = {"lat": None, "lon": None, "alt": None,
                     "speed": None, "course": None, "quality": None,
                     "num_sv": None, "hdop": None}
```

**After:**
```python
self.last_position = {"lat": None, "lon": None, "alt": None,
                     "speed": None, "course": None, "quality": None,
                     "num_sv": None, "hdop": None, "fix_status": None}
```

---

### 2. Improved RMC Message Processing
**Location**: [MAQM_main.py:106-115](MAQM_main.py#L106-L115)

Now processes RMC messages even without valid fix to track GPS status.

**Before:**
```python
if msg.msgID == "RMC" and msg.status == "A":
    self.last_position.update({
        "lat": msg.lat,
        "lon": msg.lon,
        "speed": float(msg.spd) if msg.spd else None,
        "course": float(msg.cog) if msg.cog else None
    })
```

**After:**
```python
if msg.msgID == "RMC":
    # Always update fix status, update position only if valid
    self.last_position["fix_status"] = msg.status
    if msg.status == "A":  # A = Active (valid fix), V = Void (no fix)
        self.last_position.update({
            "lat": msg.lat,
            "lon": msg.lon,
            "speed": float(msg.spd) if msg.spd else None,
            "course": float(msg.cog) if msg.cog else None
        })
```

**Benefits:**
- Can now detect when GPS loses fix (shows "V" instead of "A")
- Helpful for debugging GPS antenna issues
- Shows GPS is communicating even without position fix

---

### 3. Added GPS Course to CSV
**Location**: [MAQM_main.py:241-242](MAQM_main.py#L241-L242)

Added missing `gnss_course` and `gnss_fix_status` fields to CSV output.

**Before:**
```python
"gnss_lat", "gnss_lon", "gnss_alt", "gnss_speed",
"gnss_quality", "gnss_num_sv", "gnss_hdop",
```

**After:**
```python
"gnss_lat", "gnss_lon", "gnss_alt", "gnss_speed", "gnss_course",
"gnss_fix_status", "gnss_quality", "gnss_num_sv", "gnss_hdop",
```

**Benefits:**
- **Course** (heading): Important for mobile air quality monitoring to know direction of travel
- **Fix status**: Can identify data points with invalid GPS in post-processing

---

### 4. Updated Data Collection
**Location**: [MAQM_main.py:271-281](MAQM_main.py#L271-L281)

Added course and fix_status to data collection.

```python
row.update({
    "gnss_lat": gnss_data["lat"],
    "gnss_lon": gnss_data["lon"],
    "gnss_alt": gnss_data["alt"],
    "gnss_speed": gnss_data["speed"],
    "gnss_course": gnss_data["course"],           # NEW
    "gnss_fix_status": gnss_data["fix_status"],   # NEW
    "gnss_quality": gnss_data["quality"],
    "gnss_num_sv": gnss_data["num_sv"],
    "gnss_hdop": gnss_data["hdop"]
})
```

---

### 5. Enhanced Status Display
**Location**: [MAQM_main.py:369-394](MAQM_main.py#L369-L394)

Added GPS fix status and course to console output.

**Before:**
```
GPS: 40.831350°,-73.135522° 0.5kn SV:5 HDOP:2.7 | ...
```

**After:**
```
GPS:A 40.831350°,-73.135522° 0.5kn 45° SV:5 HDOP:2.7 | ...
    ^ fix status           ^ speed ^ course
```

**Benefits:**
- Instant visual feedback on GPS fix status (A or V)
- Shows direction of travel
- Easier to debug GPS issues during field deployment

---

## CSV Output Format

### New CSV columns (in order):
```
timestamp,
gnss_lat, gnss_lon, gnss_alt, gnss_speed, gnss_course,
gnss_fix_status, gnss_quality, gnss_num_sv, gnss_hdop,
pm1p0, pm2p5, pm4p0, pm10p0,
sen66_humidity, sen66_temperature, voc_index, nox_index, co2,
spec_co_sensor_sn, spec_co_ppb, spec_co_ppm, spec_co_temperature_c, spec_co_humidity_pct, spec_co_adc_g, spec_co_adc_t, spec_co_adc_h,
spec_no2_sensor_sn, spec_no2_ppb, spec_no2_ppm, spec_no2_temperature_c, spec_no2_humidity_pct, spec_no2_adc_g, spec_no2_adc_t, spec_no2_adc_h,
spec_o3_sensor_sn, spec_o3_ppb, spec_o3_ppm, spec_o3_temperature_c, spec_o3_humidity_pct, spec_o3_adc_g, spec_o3_adc_t, spec_o3_adc_h
```

---

## Example Console Output

```
[04:25:30] GPS:A 40.831350°,-73.135522° 0.5kn 45° SV:5 HDOP:2.7 | T:22.3°C RH:45.2% PM2.5:12.1 CO2:450 VOC:120 NOx:1 | CO:0.123 NO2:0.045 O3:0.032ppm | Buf:30
[04:25:31] GPS:A 40.831355°,-73.135520° 0.6kn 47° SV:6 HDOP:2.5 | T:22.3°C RH:45.2% PM2.5:12.2 CO2:451 VOC:121 NOx:1 | CO:0.124 NO2:0.045 O3:0.033ppm | Buf:31
[04:25:32] GPS:V 40.831355°,-73.135520° 0.6kn 47° SV:3 HDOP:9.9 | T:22.3°C RH:45.3% PM2.5:12.0 CO2:450 VOC:120 NOx:1 | CO:0.123 NO2:0.044 O3:0.032ppm | Buf:32
            ^ Lost GPS fix (V = Void)                    ^ Fewer satellites, high HDOP
```

---

## Why These Changes Matter

### For Mobile Air Quality Monitoring:

1. **Course/Heading** enables:
   - Wind direction analysis relative to travel direction
   - Plume tracking and source identification
   - Route reconstruction and visualization

2. **Fix Status** enables:
   - Data quality control (filter out invalid GPS points)
   - Identification of GPS-challenged areas (urban canyons, tunnels)
   - Debugging antenna or receiver issues

3. **Better Status Visibility**:
   - Real-time monitoring of GPS health during field campaigns
   - Early detection of GPS antenna disconnection
   - Verification that active antenna power is working

---

## Testing the Changes

### Quick Test (dry-run without sensors):
```bash
# This will fail at sensor initialization, but you can verify GPS code compiles
python3 -m py_compile MAQM_main.py
echo $?  # Should be 0 (success)
```

### Full Test (with all sensors connected):
```bash
python3 MAQM_main.py
```

Expected output should now show:
- `GPS:A` when GPS has valid fix
- `GPS:V` when GPS is searching for fix
- Course in degrees (0-360)
- Fix status in CSV file

---

## Compatibility

- ✅ **Backward compatible** with existing MAQM hardware
- ✅ **No changes needed** to sensor wiring or I2C configuration
- ✅ **No new dependencies** - uses existing pynmeagps library
- ⚠️ **CSV format changed** - new columns added (won't match old CSV files)

---

## Related GPS Configuration

If GPS is not getting a fix, ensure active antenna power is enabled:
```bash
python3 ublox_enable_lna_power.py
```

This only needs to be run once - the configuration is saved to GPS non-volatile memory.

---

## Summary

✅ **Added GPS fix status tracking** - know when GPS has/loses fix
✅ **Added GPS course/heading** - important for mobile monitoring
✅ **Improved console output** - better real-time visibility
✅ **Enhanced CSV logging** - more complete GPS metadata
✅ **Syntax verified** - code compiles without errors

The MAQM system is now better equipped for mobile air quality monitoring campaigns!
