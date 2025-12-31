# MAQM GPS Course & DOP Fix

## Issues Identified

### 1. Course Field Always Empty ❌
**Why**: GPS course (heading/direction of travel) is **only valid when moving**.

When GPS is stationary or moving very slowly (<1 knot), the course field in RMC messages is empty because:
- GPS calculates direction from consecutive position changes
- At low speeds, position noise makes direction meaningless
- This is normal GPS behavior, not a bug

**Real data from your GPS**:
```
RMC: status=A, speed=0.568kn, course=   (empty)
RMC: status=A, speed=0.760kn, course=   (empty)
```

**Decision**: ✅ **REMOVED** course field - not useful for stationary monitoring

---

### 2. Missing VDOP and PDOP ❌
**Why**: Code only captured HDOP from GGA messages, but VDOP and PDOP are in GSA messages.

**Real data from your GPS**:
```
GSA: PDOP=12.15, HDOP=4.78, VDOP=11.17
     ^^^^^ Position DOP (3D accuracy)
           ^^^^^ Horizontal DOP (2D accuracy)
                 ^^^^^ Vertical DOP (altitude accuracy)
```

**Decision**: ✅ **ADDED** PDOP and VDOP from GSA message parsing

---

## Changes Made

### 1. Removed Course Field
**Locations**: Lines 59, 114, 250, 285, 383

**Removed from**:
- `last_position` dictionary
- RMC message parsing
- CSV headers
- Data collection
- Status display

**Why**: Not applicable for stationary monitoring. If you mount this on a vehicle in the future, we can add it back.

---

### 2. Added PDOP and VDOP
**Locations**: Lines 60, 127-134, 252, 289-291, 384-386, 403

**Added GSA message parsing** [MAQM_main.py:127-134](MAQM_main.py#L127-L134):
```python
elif msg.msgID == "GSA":
    # GSA: DOP and active satellites - contains PDOP, HDOP, VDOP
    if hasattr(msg, 'PDOP') and msg.PDOP:
        self.last_position.update({
            "pdop": float(msg.PDOP) if msg.PDOP else None,
            "hdop": float(msg.HDOP) if msg.HDOP else None,
            "vdop": float(msg.VDOP) if msg.VDOP else None
        })
```

---

## New CSV Format

### GPS Columns (Updated):
```
timestamp,
gnss_lat, gnss_lon, gnss_alt, gnss_speed,
gnss_fix_status, gnss_quality, gnss_num_sv,
gnss_pdop, gnss_hdop, gnss_vdop,    <-- NEW!
...
```

### Removed:
- ❌ `gnss_course` (not useful when stationary)

### Added:
- ✅ `gnss_pdop` - Position DOP (3D accuracy)
- ✅ `gnss_vdop` - Vertical DOP (altitude accuracy)
- ✅ (gnss_hdop was already present)

---

## Console Output

### Before:
```
GPS:A 40.831°,-73.135° 0.5kn 45° SV:5 HDOP:2.7 | ...
                            ^^^ always empty
                                      ^^^^ only HDOP
```

### After:
```
GPS:A 40.831°,-73.135° 0.5kn SV:5 P/H/V:12.1/4.8/11.2 | ...
                                        ^^^^^^^^^^^^^^
                                        PDOP/HDOP/VDOP
```

Much more informative for GPS quality assessment!

---

## Understanding DOP Values

### What is DOP?
**DOP** = Dilution of Precision - measures satellite geometry quality.

- **Lower is better** (1-2 = excellent, >20 = poor)
- Affected by satellite positions in sky
- Better satellite spread = better DOP

### The Three DOPs:

1. **PDOP** (Position DOP) - **3D accuracy**
   - Combines horizontal and vertical error
   - Overall GPS quality indicator
   - **Good**: <6, **Fair**: 6-10, **Poor**: >10

2. **HDOP** (Horizontal DOP) - **2D accuracy** (lat/lon)
   - Most important for navigation
   - **Good**: <2, **Fair**: 2-5, **Poor**: >5

3. **VDOP** (Vertical DOP) - **Altitude accuracy**
   - Usually worse than HDOP
   - GPS altitude is less accurate than lat/lon
   - **Good**: <3, **Fair**: 3-10, **Poor**: >10

### Your Current GPS:
```
PDOP: 12.15  (Poor - satellites low on horizon)
HDOP: 4.78   (Fair - acceptable for stationary)
VDOP: 11.17  (Poor - altitude error high)
```

**Why Poor?**: Likely indoor/window placement. For better DOP:
- Move antenna outdoors
- Clear view of entire sky hemisphere
- Avoid urban canyons / tall buildings

---

## Example Data Interpretation

### Good GPS Fix:
```csv
2025-12-04T12:30:00,40.831350,-73.135522,84.2,0.5,A,1,8,3.2,1.8,2.7
                                            ^   ^ ^  ^^^  ^^^  ^^^
                                            fix Q SV PDOP HDOP VDOP
                                            A   1 8  good good good
```

### Poor GPS Fix:
```csv
2025-12-04T12:31:00,40.831355,-73.135520,95.8,0.4,A,1,4,18.5,6.2,17.3
                                            ^   ^ ^  ^^^^  ^^^  ^^^^
                                            fix Q SV PDOP HDOP VDOP
                                            A   1 4  poor fair poor
```

In post-processing, you can filter out data points with PDOP>10 or HDOP>5.

---

## When Would Course Be Useful?

Course/heading would be valuable if you:
1. **Mount MAQM on a vehicle** - track pollution along routes
2. **Walk transects** - survey air quality in neighborhoods
3. **Analyze plume dispersion** - correlate direction with concentration

For **stationary monitoring**, course is meaningless, so we removed it.

---

## Technical Details

### Message Types Used:

1. **RMC** (Recommended Minimum Navigation Information)
   - Fix status (A/V)
   - Position (lat/lon)
   - Speed
   - ~~Course~~ (removed - not useful when stationary)

2. **GGA** (Global Positioning System Fix Data)
   - Position (lat/lon/alt)
   - Fix quality
   - Number of satellites
   - HDOP only (not PDOP or VDOP)

3. **GSA** (DOP and Active Satellites) ← **NEW!**
   - PDOP (3D accuracy)
   - HDOP (2D accuracy)
   - VDOP (altitude accuracy)
   - Satellite IDs in use

---

## Testing

### Syntax Check:
```bash
python3 -m py_compile MAQM_main.py
```
✅ **PASSED**

### Expected Console Output:
```
[12:30:45] GPS:A 40.831350°,-73.135522° 0.5kn SV:5 P/H/V:5.5/2.8/4.7 | T:22.3°C RH:45.2% PM2.5:12.1 ...
```

### CSV Output:
All three DOP values should now be populated (not empty).

---

## Summary

### ✅ What Changed:
1. **Removed** `gnss_course` - not applicable for stationary use
2. **Added** `gnss_pdop` - 3D position accuracy
3. **Added** `gnss_vdop` - vertical accuracy
4. **Added** GSA message parsing
5. **Updated** console display to show P/H/V DOP values

### ✅ Why It Matters:
- **Better GPS quality assessment** - can now evaluate 3D accuracy
- **Post-processing filtering** - remove low-quality data points
- **Altitude accuracy** - understand vertical uncertainty
- **More complete metadata** - all relevant GPS metrics captured

### ✅ Files Updated:
- [MAQM_main.py](MAQM_main.py) - All GPS changes applied
- [MAQM_DOP_FIX.md](MAQM_DOP_FIX.md) - This documentation

---

**Your MAQM logger now captures complete GPS accuracy metrics!**
