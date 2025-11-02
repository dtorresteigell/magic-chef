# app/utils/geo.py
from flask import request, current_app
import requests
import pycountry


def iso_to_country_name(iso_code):
    """
    Convert ISO 3166-1 alpha-2 code to full country name.
    Returns the code itself if not found.
    """
    if not iso_code:
        return "Unknown"
    try:
        country = pycountry.countries.get(alpha_2=iso_code.upper())
        return country.name if country else iso_code
    except Exception:
        return iso_code


def get_user_country(default_loc="Germany", default_lat=49.5):
    """
    Roughly detect the user's country based on their IP address.
    Falls back to default if detection fails.
    """
    try:
        # Get IP
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip is None:
            return default

        # Use free geolocation API (ipinfo.io)
        response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=2)
        if response.status_code == 200:
            data = response.json()
            city = data.get("city", None)
            country = data.get("country", None)
            lat_str, _ = data.get("loc", ",").split(",")
            latitude = float(lat_str) if lat_str else None

            if country is not None:
                if city is not None:
                    location = f"{city} ({iso_to_country_name(country)})"
                else:
                    location = iso_to_country_name(country)

            return location, latitude
    except Exception:
        pass

    return default_loc, default_lat


def get_season_tag_from_latitude(latitude):
    """
    Determine the current season based on latitude.
    Northern Hemisphere: Spring (Mar-May), Summer (Jun-Aug), Autumn (Sep-Nov), Winter (Dec-Feb)
    Southern Hemisphere: Opposite seasons.
    """
    from datetime import datetime, date

    current_date = datetime.now().date()
    current_year = current_date.year

    spring_start = date(current_year, 3, 20)
    summer_start = date(current_year, 6, 21)
    autumn_start = date(current_year, 9, 22)
    winter_start = date(current_year, 12, 21)

    if latitude >= 0:
        # Northern Hemisphere
        if spring_start <= current_date < summer_start:
            return "spring"
        elif summer_start <= current_date < autumn_start:
            return "summer"
        elif autumn_start <= current_date < winter_start:
            return "autumn"
        else:
            return "winter"
    else:
        # Southern Hemisphere
        if spring_start <= current_date < summer_start:
            return "autumn"
        elif summer_start <= current_date < autumn_start:
            return "winter"
        elif autumn_start <= current_date < winter_start:
            return "spring"
        else:
            return "summer"
