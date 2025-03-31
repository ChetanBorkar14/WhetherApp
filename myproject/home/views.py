import json
import requests
import requests_cache
from retry_requests import retry
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from opencage.geocoder import OpenCageGeocode
from django.shortcuts import render
from django.conf import settings
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Setup caching & retry mechanism
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)

# Initialize OpenCage geocoder
geocoder = OpenCageGeocode("afe20602d803452f95ca6e41f153ffbe")

def home(request):
    return render(request, "home.html")

@csrf_exempt
def get_weather(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)
    
    try:
        # Parse request data
        try:
            data = json.loads(request.body.decode('utf-8'))
            city = data.get('city', '').strip()
            if not city:
                return JsonResponse({"error": "City name is required"}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        
        # Get coordinates (cached or fresh)
        cache_key = f"geocode_{city.lower()}"
        cached_coords = cache.get(cache_key)
        
        if cached_coords:
            latitude, longitude = cached_coords
            logger.info(f"Using cached coordinates for {city}")
        else:
            try:
                results = geocoder.geocode(city)
                if not results:
                    return JsonResponse({"error": "Could not find location"}, status=404)
                
                latitude = results[0]['geometry']['lat']
                longitude = results[0]['geometry']['lng']
                cache.set(cache_key, (latitude, longitude), 60*60*24*7)  # Cache for 1 week
                logger.info(f"Geocoded new coordinates for {city}")
            except Exception as e:
                logger.error(f"Geocoding failed for {city}: {str(e)}")
                return JsonResponse({"error": "Location service unavailable"}, status=503)

        # Prepare default response
        response_data = {
            'weather': {
                'city': city,
                'temperature': None,
                'precipitation': None,
                'wind_speed': None
            },
            'uv_index': None,
            'aqi': None
        }

        # Fetch weather data
        weather_data = fetch_weather_data(latitude, longitude)
        if weather_data:
            response_data['weather'].update(weather_data.get('current', {}))
            response_data['uv_index'] = weather_data.get('uv_index')

        # Fetch AQI data
        aqi_data = fetch_aqi_data(latitude, longitude)
        if aqi_data:
            response_data['aqi'] = aqi_data

        # Determine response status
        if weather_data and aqi_data:
            return JsonResponse(response_data)
        elif weather_data or aqi_data:
            return JsonResponse(response_data, status=206)  # Partial content
        else:
            return JsonResponse({"error": "Weather services unavailable"}, status=503)

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)

def fetch_weather_data(latitude, longitude):
    """Fetch weather data from Open-Meteo API"""
    try:
        weather_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ["temperature_2m", "precipitation", "wind_speed_10m"],
            "daily": ["uv_index_clear_sky_max"],
            "timezone": "auto"
        }
        
        response = retry_session.get(weather_url, params=params)
        if response.status_code != 200:
            return None
            
        data = response.json()
        
        result = {
            'current': {
                'temperature': data.get('current', {}).get('temperature_2m'),
                'precipitation': data.get('current', {}).get('precipitation'),
                'wind_speed': data.get('current', {}).get('wind_speed_10m')
            },
            'uv_index': None
        }
        
        # Extract UV index if available
        daily = data.get('daily', {})
        if daily and daily.get('uv_index_clear_sky_max'):
            result['uv_index'] = daily['uv_index_clear_sky_max'][0]
            
        return result
        
    except Exception as e:
        logger.error(f"Weather API error: {str(e)}")
        return None

def fetch_aqi_data(latitude, longitude):
    """Fetch air quality data from Open-Meteo API"""
    try:
        aqi_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ["european_aqi"],
            "timezone": "auto"
        }

        response = retry_session.get(aqi_url, params=params)
        if response.status_code != 200:
            return None
            
        data = response.json()
        return data.get('current', {}).get('european_aqi')
        
    except Exception as e:
        logger.error(f"AQI API error: {str(e)}")
        return None