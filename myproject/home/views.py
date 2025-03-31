import json
import requests
import requests_cache
from retry_requests import retry
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from opencage.geocoder import OpenCageGeocode

# Setup caching & retry mechanism
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)

# Initialize OpenCage geocoder with your API key
geocoder = OpenCageGeocode("afe20602d803452f95ca6e41f153ffbe")

@csrf_exempt  # Disable CSRF for Postman testing
def get_weather(request):
    if request.method == 'POST':
        try:
            # Decode JSON safely
            try:
                data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON format"}, status=400)

            city = data.get('city')
            if not city:
                return JsonResponse({"error": "City is required"}, status=400)
            
            # Check if geocoding result is in cache
            cache_key = f"geocode_{city}"
            cached_coords = cache.get(cache_key)
            
            if cached_coords:
                latitude, longitude = cached_coords
            else:
                # Get Latitude & Longitude using OpenCage geocoder
                try:
                    results = geocoder.geocode(city)
                    
                    if results and len(results):
                        latitude = results[0]['geometry']['lat']
                        longitude = results[0]['geometry']['lng']
                        
                        # Cache the coordinates for future use (1 week)
                        cache.set(cache_key, (latitude, longitude), 60*60*24*7)
                    else:
                        return JsonResponse({"error": "Could not geocode city"}, status=400)
                    
                except Exception as e:
                    return JsonResponse({"error": f"Geocoding error: {str(e)}"}, status=503)
            
            # Initialize response data
            response_data = {
                'weather': {
                    'city': city,
                    'temperature': "N/A",
                    'precipitation': "N/A",
                    'wind_speed': "N/A"
                },
                'uv_index': "N/A",
                'aqi': "N/A"
            }

            # Fetch weather data
            weather_success = False
            try:
                weather_url = "https://api.open-meteo.com/v1/forecast"
                weather_params = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": ["temperature_2m", "precipitation", "wind_speed_10m"],
                    "hourly": ["temperature_2m"],
                    "daily": ["uv_index_clear_sky_max"],
                    "timezone": "auto"
                }
                
                weather_response = retry_session.get(weather_url, params=weather_params)

                if weather_response.status_code == 200:
                    weather_data_json = weather_response.json()
                    
                    # Extract current weather data safely
                    current = weather_data_json.get("current", {})
                    response_data['weather'] = {
                        'city': city,
                        'temperature': current.get("temperature_2m", "N/A"),
                        'precipitation': current.get("precipitation", "N/A"),
                        'wind_speed': current.get("wind_speed_10m", "N/A")
                    }

                    # Extract UV index safely
                    daily = weather_data_json.get("daily", {})
                    if daily and "uv_index_clear_sky_max" in daily and daily["uv_index_clear_sky_max"]:
                        response_data['uv_index'] = daily["uv_index_clear_sky_max"][0]
                    
                    weather_success = True
            except Exception as e:
                print(f"Weather API error: {str(e)}")

            # Fetch AQI data
            aqi_success = False
            try:
                aqi_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
                aqi_params = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": ["european_aqi"],
                    "timezone": "auto"
                }

                aqi_response = retry_session.get(aqi_url, params=aqi_params)

                if aqi_response.status_code == 200:
                    aqi_data = aqi_response.json()
                    if "current" in aqi_data and "european_aqi" in aqi_data["current"]:
                        response_data['aqi'] = aqi_data["current"]["european_aqi"]
                    aqi_success = True
            except Exception as e:
                print(f"AQI API error: {str(e)}")

            # Return what we have, with appropriate status code
            if weather_success and aqi_success:
                return JsonResponse(response_data)
            elif weather_success or aqi_success:
                # Some data was retrieved successfully
                return JsonResponse(response_data, status=206)  # Partial Content
            else:
                return JsonResponse({"error": "Failed to retrieve any weather data"}, status=503)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)