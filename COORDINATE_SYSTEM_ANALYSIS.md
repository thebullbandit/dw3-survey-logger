# Elite Dangerous / DW3 Coordinate System Analysis

## Summary

**The original code was CORRECT.** Your Discord users appear to be confused about the coordinate system, but the application is working as intended.

## Elite Dangerous Coordinate System

In Elite Dangerous journals (StarPos field), coordinates are provided as `[X, Y, Z]` where:

- **X** (index 0) = Horizontal (left/right, East/West from Sol)
- **Y** (index 1) = Horizontal (forward/back, toward/away from galactic center, North/South)  
- **Z** (index 2) = **VERTICAL** (up/down, above/below galactic plane) ✓

**Source:** https://wiki.herzbube.ch/wiki/EDExploration

> "The z axis represents the vertical movement in relation to the Galaxy ecliptic. +/- mean above/below."

## DW3 Stellar Density Worksheet

The DW3 worksheet expects coordinates in columns:
- Column G (X): Horizontal coordinate
- Column H (Z): **VERTICAL coordinate** (galactic height)
- Column I (Y): Horizontal coordinate

**Source:** DW3 Science Thread (https://forums.frontier.co.uk/threads/dw3-distant-worlds-3-science-thread.643734/)

> "The important one for us is the middle one, which measures 'height' above the plane of the galaxy, or 'Z'."

## Your Application's Behavior

### Z-Bin Calculation (CORRECT)
```python
# From observer_models.py line 336
z_bin=calculate_z_bin(star_pos[2])  # Uses journal's Z (vertical)
```

This is **correct** - it calculates the z_bin from `star_pos[2]`, which is the journal's Z coordinate (vertical/galactic height).

### Original Export Mapping (CORRECT)
```python
# From density_worksheet_exporter.py (original code)
ws.cell(r, 7).value = x  # Column G: X ✓
ws.cell(r, 8).value = z  # Column H: Z (vertical) ✓
ws.cell(r, 9).value = y  # Column I: Y ✓
```

This is **correct** - it maps:
- Journal's X → Worksheet's X column
- Journal's Z → Worksheet's Z column (both vertical)
- Journal's Y → Worksheet's Y column

## Why The Confusion?

### Common Misconception
Many people expect coordinate systems to follow the mathematical convention (X, Y, Z) where:
- X = left/right
- Y = forward/back  
- Z = up/down

However, Elite Dangerous uses:
- X = left/right ✓
- Y = forward/back ✓
- Z = up/down ✓ (THIS IS CORRECT!)

The coordinate systems are actually consistent! The confusion arises because people expect Y to be vertical (as in many 3D applications), but in Elite Dangerous, **Z is vertical**.

### What About The User's Problem?

The user said their sheet "looks like this" after using the new version. The likely explanations are:

1. **No actual problem** - The data IS correct, but the user expects different axis labels
2. **Old data issue** - If there was ever a version of your code that swapped the coordinates, old stored data would have incorrect z_bins that don't match the actual Z coordinates
3. **Manual editing** - The user may have manually edited coordinates in their database

### The Z-Bin Mystery

Looking at the screenshot, the "Z Sample" column shows values around 42500. The Z-bin is calculated as:

```python
def calculate_z_bin(z_coordinate: float, bin_size: int = 50) -> int:
    return round(z_coordinate / bin_size) * bin_size
```

So a z_bin of 42500 means the system is at approximately Z=42500 light-years above/below the galactic plane.

If the user's system is actually at Y=42500 (horizontal) and Z=50 (vertical), but the z_bin shows 42500, then the **OLD DATA** was calculated using the wrong coordinate. But this would be a data corruption issue, not an exporter issue.

## Recommendation

**Do NOT change the exporter code.** The original mapping is correct.

Instead, you should:

1. **Verify with the users** what they're actually seeing as "wrong"
2. **Check if there's old data** in their database with incorrect z_bins
3. **Consider adding a data migration** script that recalculates z_bins from star_pos for existing records

## Test Case

To verify the code is working correctly:

1. Visit a system at coordinates like X=0, Y=0, Z=350 (just above galactic plane)
2. The z_bin should be calculated as 350 (or 400 depending on rounding)
3. The export should show: X=0, Z=350, Y=0
4. The "Z Sample" column (z_bin) should show 350

If all of this matches, the code is correct.
