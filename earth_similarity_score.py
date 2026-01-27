"""
Earth Similarity Score Calculator
==================================

Based on Cmdr Coddiwompler's scoring system for Observatory Core.
Measures how similar an Earth-like World is to actual Earth (or Mars).

Lower scores = more similar to Earth
Score of 0 = exact match to Earth

Original: https://github.com/fredjk-gh/ObservatoryExtras
Forum: https://forums.frontier.co.uk/threads/how-close-to-earth-is-your-elw-a-scoring-method.354719/

Ported to Python for DW3 Earth2 Logger
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   earth_similarity_score.py
#
# Connected modules (direct imports):
#   (none)
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only (no logic changes).
# ============================================================================

import math
from typing import Dict, Any, Optional, Tuple


class ReferenceBody:
    """Reference body for similarity comparison"""
    
    def __init__(self, name: str):
        self.name = name
        self.gravity_g = 0.0
        self.temp_k = 0.0
        self.pressure_atm = 0.0
        self.atmo_nitrogen_pct = 0.0
        self.atmo_oxygen_pct = 0.0
        self.atmo_argon_pct = 0.0
        self.atmo_water_pct = 0.0
        self.orbital_period_days = 0.0
        self.rotational_period_days = 0.0
        self.axial_tilt_degrees = 0.0
        self.eccentricity = 0.0
        self.tidal_lock = False
        self.star_count = 1
        self.moon_count = 1


# Earth reference values (from Elite Dangerous in-game Earth)
EARTH = ReferenceBody("Earth")
EARTH.gravity_g = 9.797759 / 9.81  # Convert to G
EARTH.temp_k = 288.0
EARTH.pressure_atm = 101231.656250 / 101325.0  # Convert to atmospheres
EARTH.atmo_nitrogen_pct = 77.886406
EARTH.atmo_oxygen_pct = 20.892998
EARTH.atmo_argon_pct = 0.931637
EARTH.atmo_water_pct = 0.0
EARTH.orbital_period_days = 31558150.649071 / 86400.0  # Convert to days
EARTH.rotational_period_days = 86164.106590 / 86400.0  # Convert to days
EARTH.axial_tilt_degrees = math.degrees(0.401426)
EARTH.eccentricity = 0.016700
EARTH.tidal_lock = False
EARTH.star_count = 1
EARTH.moon_count = 1


# Mars reference values (from Elite Dangerous in-game Mars)
MARS = ReferenceBody("Mars")
MARS.gravity_g = 3.697488 / 9.81  # Convert to G
MARS.temp_k = 260.811890
MARS.pressure_atm = 233391.062500 / 101325.0  # Convert to atmospheres
MARS.atmo_nitrogen_pct = 91.169930
MARS.atmo_oxygen_pct = 8.682851
MARS.atmo_argon_pct = 0.0
MARS.atmo_water_pct = 0.095125
MARS.orbital_period_days = 59354294.538498 / 86400.0  # Convert to days
MARS.rotational_period_days = 88642.690263 / 86400.0  # Convert to days
MARS.axial_tilt_degrees = math.degrees(0.439648)
MARS.eccentricity = 0.093400
MARS.tidal_lock = False
MARS.star_count = 1
MARS.moon_count = 0


# ============================================================================
# FUNCTIONS
# ============================================================================

def weighted_score(
    target_val: float,
    reference_val: float,
    pos_weight: float,
    neg_weight: float
) -> float:
    """
    Calculate weighted score for a parameter
    
    Args:
        target_val: Value from scanned body
        reference_val: Value from reference body (Earth/Mars)
        pos_weight: Weight when target > reference
        neg_weight: Weight when target < reference
        
    Returns:
        Weighted difference score
    """
    if reference_val == 0:
        return 0
    
    factor = (target_val - reference_val) / reference_val
    
    if factor >= 0:
        return factor * pos_weight
    else:
        return abs(factor) * neg_weight


def compute_similarity_score(
    scan_data: Dict[str, Any],
    reference: ReferenceBody = EARTH,
    star_count: int = 1
) -> float:
    """
    Compute similarity score comparing a scanned ELW to a reference body
    
    Lower score = more similar
    Score of 0 = exact match
    
    Args:
        scan_data: Scan data dictionary from journal
        reference: Reference body to compare against (default: Earth)
        star_count: Number of stars in the system
        
    Returns:
        Similarity score (0 = exact match, higher = more different)
        Returns -1 if not an ELW
    """
    # Only works for Earth-like worlds
    if scan_data.get("planet_class") != "Earthlike body":
        return -1.0
    
    score = 0.0
    
    # Gravity (very important for habitability)
    gravity_g = scan_data.get("surface_gravity_g", 0)
    score += weighted_score(gravity_g, reference.gravity_g, 25, 20)
    
    # Surface temperature (important for liquid water)
    temp_k = scan_data.get("surface_temp_k", 0)
    score += weighted_score(temp_k, reference.temp_k, 2, 1)
    
    # Surface pressure (important for atmosphere retention)
    pressure_atm = scan_data.get("surface_pressure_atm", 0)
    score += weighted_score(pressure_atm, reference.pressure_atm, 1, 2)
    
    # Orbital eccentricity (affects temperature variation)
    eccentricity = scan_data.get("orbital_eccentricity", 0)
    score += weighted_score(eccentricity, reference.eccentricity, 20, 0)
    
    # Tidal lock (very important - tidally locked = no day/night cycle)
    tidal_lock = scan_data.get("tidal_lock") == "Yes"
    tidal_val = 2 if tidal_lock else 1
    ref_tidal_val = 2 if reference.tidal_lock else 1
    score += weighted_score(tidal_val, ref_tidal_val, 5, 1)
    
    # Atmosphere composition (if available)
    # This would require parsing AtmosphereComposition from journal
    # For now, we'll skip this part as it's not in our current data structure
    
    # Orbital period (year length)
    orbital_period_days = abs(scan_data.get("orbital_period_days", 0))
    score += weighted_score(orbital_period_days, reference.orbital_period_days, 1, 1)
    
    # Rotational period (day length - very important for habitability)
    rotational_period_days = abs(scan_data.get("rotation_period_days", 0))
    score += weighted_score(rotational_period_days, reference.rotational_period_days, 10, 15)
    
    # Axial tilt (affects seasons)
    axial_tilt_deg = abs(scan_data.get("axial_tilt_deg", 0))
    score += weighted_score(axial_tilt_deg, reference.axial_tilt_degrees, 1, 1)
    
    # Star count (single star systems are more stable)
    score += weighted_score(star_count, reference.star_count, 5, 0)
    
    return score


def score_to_category(score: float) -> str:
    """
    Convert similarity score to category
    
    Args:
        score: Similarity score (lower = better)
        
    Returns:
        Category: Descriptive rating based on Earth similarity
    """
    if score < 0:
        return "Unknown"
    elif score <= 25:
        return "Earth Twin"
    elif score <= 50:
        return "Excellent"
    elif score <= 100:
        return "Very Good"
    elif score <= 150:
        return "Good"
    elif score <= 250:
        return "Fair"
    elif score <= 400:
        return "Marginal"
    else:
        return "Poor"


def get_metric_comparison(value: float, target: float, tolerance: float = 0.10) -> str:
    """
    Get visual indicator for how close a metric is to target
    
    Args:
        value: Actual value
        target: Target (Earth) value
        tolerance: Acceptable deviation (default 10%)
        
    Returns:
        Visual indicator: ✓ (good), ~ (acceptable), ✗ (poor)
    """
    if target == 0:
        return "—"
    
    diff = abs(value - target) / target
    
    if diff <= tolerance:
        return "✓"
    elif diff <= tolerance * 3:
        return "~"
    else:
        return "✗"


def get_similarity_breakdown(scan_data: Dict[str, Any], reference: ReferenceBody = EARTH) -> Dict[str, Any]:
    """
    Get detailed breakdown of similarity metrics
    
    Args:
        scan_data: Scan data dictionary
        reference: Reference body (default: Earth)
        
    Returns:
        Dictionary with detailed breakdown for each metric
    """
    if scan_data.get("planet_class") != "Earthlike body":
        return {}
    
    breakdown = {}
    
    # Gravity
    gravity_g = scan_data.get("surface_gravity_g", 0)
    breakdown["gravity"] = {
        "value": gravity_g,
        "target": reference.gravity_g,
        "unit": "G",
        "indicator": get_metric_comparison(gravity_g, reference.gravity_g, 0.15),
        "score": weighted_score(gravity_g, reference.gravity_g, 25, 20)
    }
    
    # Temperature
    temp_k = scan_data.get("surface_temp_k", 0)
    breakdown["temperature"] = {
        "value": temp_k,
        "target": reference.temp_k,
        "unit": "K",
        "indicator": get_metric_comparison(temp_k, reference.temp_k, 0.10),
        "score": weighted_score(temp_k, reference.temp_k, 2, 1)
    }
    
    # Pressure
    pressure_atm = scan_data.get("surface_pressure_atm", 0)
    breakdown["pressure"] = {
        "value": pressure_atm,
        "target": reference.pressure_atm,
        "unit": "atm",
        "indicator": get_metric_comparison(pressure_atm, reference.pressure_atm, 0.20),
        "score": weighted_score(pressure_atm, reference.pressure_atm, 1, 2)
    }
    
    # Rotation period (day length)
    rotation_days = abs(scan_data.get("rotation_period_days", 0))
    breakdown["rotation"] = {
        "value": rotation_days * 24,  # Convert to hours
        "target": reference.rotational_period_days * 24,  # Earth's day
        "unit": "hours",
        "indicator": get_metric_comparison(rotation_days, reference.rotational_period_days, 0.25),
        "score": weighted_score(rotation_days, reference.rotational_period_days, 10, 15)
    }
    
    # Orbital period (year length)
    orbital_days = abs(scan_data.get("orbital_period_days", 0))
    breakdown["orbital"] = {
        "value": orbital_days,
        "target": reference.orbital_period_days,
        "unit": "days",
        "indicator": get_metric_comparison(orbital_days, reference.orbital_period_days, 0.20),
        "score": weighted_score(orbital_days, reference.orbital_period_days, 1, 1)
    }
    
    # Tidal lock
    tidal_lock = scan_data.get("tidal_lock") == "Yes"
    breakdown["tidal_lock"] = {
        "value": tidal_lock,
        "target": reference.tidal_lock,
        "locked": tidal_lock,
        "indicator": "✓" if tidal_lock == reference.tidal_lock else "✗"
    }
    
    # Axial tilt
    axial_tilt = abs(scan_data.get("axial_tilt_deg", 0))
    breakdown["axial_tilt"] = {
        "value": axial_tilt,
        "target": reference.axial_tilt_degrees,
        "unit": "°",
        "indicator": get_metric_comparison(axial_tilt, reference.axial_tilt_degrees, 0.30),
        "score": weighted_score(axial_tilt, reference.axial_tilt_degrees, 1, 1)
    }
    
    return breakdown


# ============================================================================
# GOLDILOCKS ZONE HABITABILITY SCORING
# ============================================================================

def get_temperature_points(temp_k: float) -> int:
    """
    Get Goldilocks points for temperature (0-4)
    
    Perfect habitable zone for liquid water and comfortable conditions
    """
    if 280 <= temp_k <= 295:
        return 4  # Perfect - Earth range
    elif 270 <= temp_k < 280 or 295 < temp_k <= 310:
        return 3  # Good
    elif 250 <= temp_k < 270 or 310 < temp_k <= 330:
        return 2  # Acceptable
    elif 230 <= temp_k < 250 or 330 < temp_k <= 350:
        return 1  # Marginal
    else:
        return 0  # Poor


def get_gravity_points(gravity_g: float) -> int:
    """
    Get Goldilocks points for gravity (0-4)
    
    Important for human habitability and atmospheric retention
    """
    if 0.90 <= gravity_g <= 1.10:
        return 4  # Perfect - near Earth
    elif 0.70 <= gravity_g < 0.90 or 1.10 < gravity_g <= 1.30:
        return 3  # Good
    elif 0.50 <= gravity_g < 0.70 or 1.30 < gravity_g <= 1.50:
        return 2  # Acceptable
    elif 0.30 <= gravity_g < 0.50 or 1.50 < gravity_g <= 2.00:
        return 1  # Marginal
    else:
        return 0  # Poor


def get_pressure_points(pressure_atm: float) -> int:
    """
    Get Goldilocks points for atmospheric pressure (0-4)
    
    Critical for breathability and liquid water
    """
    if 0.80 <= pressure_atm <= 1.20:
        return 4  # Perfect - breathable
    elif 0.60 <= pressure_atm < 0.80 or 1.20 < pressure_atm <= 1.50:
        return 3  # Good
    elif 0.40 <= pressure_atm < 0.60 or 1.50 < pressure_atm <= 2.00:
        return 2  # Acceptable
    elif 0.20 <= pressure_atm < 0.40 or 2.00 < pressure_atm <= 3.00:
        return 1  # Marginal
    else:
        return 0  # Poor


def get_day_length_points(rotation_period_days: float, tidal_locked: bool) -> int:
    """
    Get Goldilocks points for day length (0-4)
    
    Important for temperature regulation and habitability
    """
    if tidal_locked:
        return 0  # Tidally locked = permanent day/night sides (Poor)
    
    # Convert to hours
    day_hours = abs(rotation_period_days) * 24
    
    if 18 <= day_hours <= 30:
        return 4  # Perfect - similar to Earth's 24h
    elif 12 <= day_hours < 18 or 30 < day_hours <= 48:
        return 3  # Good
    elif 6 <= day_hours < 12 or 48 < day_hours <= 96:
        return 2  # Acceptable
    elif 1 <= day_hours < 6 or 96 < day_hours <= 240:
        return 1  # Marginal
    else:
        return 0  # Poor - too fast or too slow


def calculate_goldilocks_score(scan_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate Goldilocks Zone habitability score (0-16 points)
    
    Measures habitability based on 4 key factors:
    - Temperature (water/comfort)
    - Gravity (human tolerance/atmosphere retention)
    - Pressure (breathability)
    - Day length (temperature regulation)
    
    Args:
        scan_data: Scan data dictionary
        
    Returns:
        Dictionary with Goldilocks scoring breakdown
    """
    if scan_data.get("planet_class") != "Earthlike body":
        return {
            "total": -1,
            "max": 16,
            "category": "N/A",
            "breakdown": {}
        }
    
    # Get values
    temp_k = scan_data.get("surface_temp_k", 0)
    gravity_g = scan_data.get("surface_gravity_g", 0)
    pressure_atm = scan_data.get("surface_pressure_atm", 0)
    rotation_days = scan_data.get("rotation_period_days", 0)
    tidal_locked = scan_data.get("tidal_lock") == "Yes"
    
    # Calculate points for each factor
    temp_points = get_temperature_points(temp_k)
    grav_points = get_gravity_points(gravity_g)
    pressure_points = get_pressure_points(pressure_atm)
    day_points = get_day_length_points(rotation_days, tidal_locked)
    
    total = temp_points + grav_points + pressure_points + day_points
    
    # Determine category
    if total == 16:
        category = "Perfect Goldilocks"
    elif total >= 14:
        category = "Excellent Habitat"
    elif total >= 12:
        category = "Very Good Habitat"
    elif total >= 10:
        category = "Good Habitat"
    elif total >= 7:
        category = "Acceptable Habitat"
    elif total >= 4:
        category = "Marginal Habitat"
    else:
        category = "Poor Habitat"
    
    # Build breakdown
    breakdown = {
        "temperature": {
            "points": temp_points,
            "max": 4,
            "value": temp_k,
            "unit": "K",
            "stars": "⭐" * temp_points
        },
        "gravity": {
            "points": grav_points,
            "max": 4,
            "value": gravity_g,
            "unit": "G",
            "stars": "⭐" * grav_points
        },
        "pressure": {
            "points": pressure_points,
            "max": 4,
            "value": pressure_atm,
            "unit": "atm",
            "stars": "⭐" * pressure_points
        },
        "day_length": {
            "points": day_points,
            "max": 4,
            "value": abs(rotation_days) * 24,  # in hours
            "unit": "hours",
            "locked": tidal_locked,
            "stars": "⭐" * day_points
        }
    }
    
    return {
        "total": total,
        "max": 16,
        "category": category,
        "stars": "⭐" * min(total // 3, 5),  # 0-5 stars for display
        "breakdown": breakdown
    }


def get_similarity_breakdown(scan_data: Dict[str, Any], reference: ReferenceBody = EARTH) -> Dict[str, Any]:
    """
    Get detailed breakdown of similarity metrics
    
    Args:
        scan_data: Scan data dictionary
        reference: Reference body (default: Earth)
        
    Returns:
        Dictionary with detailed breakdown for each metric
    """
    if scan_data.get("planet_class") != "Earthlike body":
        return {}
    
    breakdown = {}
    
    # Gravity
    gravity_g = scan_data.get("surface_gravity_g", 0)
    breakdown["gravity"] = {
        "value": gravity_g,
        "target": reference.gravity_g,
        "unit": "G",
        "indicator": get_metric_comparison(gravity_g, reference.gravity_g, 0.15),
        "score": weighted_score(gravity_g, reference.gravity_g, 25, 20)
    }
    
    # Temperature
    temp_k = scan_data.get("surface_temp_k", 0)
    breakdown["temperature"] = {
        "value": temp_k,
        "target": reference.temp_k,
        "unit": "K",
        "indicator": get_metric_comparison(temp_k, reference.temp_k, 0.10),
        "score": weighted_score(temp_k, reference.temp_k, 2, 1)
    }
    
    # Pressure
    pressure_atm = scan_data.get("surface_pressure_atm", 0)
    breakdown["pressure"] = {
        "value": pressure_atm,
        "target": reference.pressure_atm,
        "unit": "atm",
        "indicator": get_metric_comparison(pressure_atm, reference.pressure_atm, 0.20),
        "score": weighted_score(pressure_atm, reference.pressure_atm, 1, 2)
    }
    
    # Rotation period (day length)
    rotation_days = abs(scan_data.get("rotation_period_days", 0))
    breakdown["rotation"] = {
        "value": rotation_days * 24,  # Convert to hours
        "target": reference.rotational_period_days * 24,  # Earth's day
        "unit": "hours",
        "indicator": get_metric_comparison(rotation_days, reference.rotational_period_days, 0.25),
        "score": weighted_score(rotation_days, reference.rotational_period_days, 10, 15)
    }
    
    # Orbital period (year length)
    orbital_days = abs(scan_data.get("orbital_period_days", 0))
    breakdown["orbital"] = {
        "value": orbital_days,
        "target": reference.orbital_period_days,
        "unit": "days",
        "indicator": get_metric_comparison(orbital_days, reference.orbital_period_days, 0.20),
        "score": weighted_score(orbital_days, reference.orbital_period_days, 1, 1)
    }
    
    # Tidal lock
    tidal_lock = scan_data.get("tidal_lock") == "Yes"
    breakdown["tidal_lock"] = {
        "value": tidal_lock,
        "target": reference.tidal_lock,
        "locked": tidal_lock,
        "indicator": "✓" if tidal_lock == reference.tidal_lock else "✗"
    }
    
    # Axial tilt
    axial_tilt = abs(scan_data.get("axial_tilt_deg", 0))
    breakdown["axial_tilt"] = {
        "value": axial_tilt,
        "target": reference.axial_tilt_degrees,
        "unit": "°",
        "indicator": get_metric_comparison(axial_tilt, reference.axial_tilt_degrees, 0.30),
        "score": weighted_score(axial_tilt, reference.axial_tilt_degrees, 1, 1)
    }
    
    return breakdown


def get_similarity_description(score: float) -> str:
    """
    Get human-readable description of similarity score
    
    Args:
        score: Similarity score
        
    Returns:
        Description string
    """
    if score < 0:
        return "Not an Earth-like World"
    elif score == 0:
        return "Exact Earth twin!"
    elif score <= 10:
        return "Extremely similar to Earth"
    elif score <= 25:
        return "Very similar to Earth"
    elif score <= 50:
        return "Quite similar to Earth"
    elif score <= 100:
        return "Moderately similar to Earth"
    elif score <= 150:
        return "Somewhat Earth-like"
    elif score <= 250:
        return "Slightly Earth-like"
    else:
# ============================================================================
# ENTRYPOINT
# ============================================================================

        return "Different from Earth"


# Example usage
if __name__ == "__main__":
    # Example scan data (in our format)
    example_scan = {
        "planet_class": "Earthlike body",
        "surface_gravity_g": 1.0,
        "surface_temp_k": 290.0,
        "surface_pressure_atm": 1.0,
        "orbital_eccentricity": 0.02,
        "tidal_lock": "No",
        "orbital_period_days": 365.25,
        "rotation_period_days": 1.0,
        "axial_tilt_deg": 23.5
    }
    
    score = compute_similarity_score(example_scan, EARTH, star_count=1)
    rating = score_to_rating(score)
    description = get_similarity_description(score)
    
    print(f"Earth Similarity Score: {score:.2f}")
    print(f"Rating: {rating}")
    print(f"Description: {description}")
