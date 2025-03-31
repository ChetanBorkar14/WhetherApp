from django.contrib import admin
from django.urls import path, include  # Add include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('home.urls')),  # Routes root URL to your app
]