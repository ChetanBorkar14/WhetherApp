from django.urls import path
from .views import home, get_weather  # Make sure both are imported

urlpatterns = [
    path('', home, name='home'),          # Serves home.html
    path('weather/', get_weather),        # API endpoint (NO trailing slash in pattern)
    # or alternatively:
    path('api/weather/', get_weather),    # More explicit API path
]