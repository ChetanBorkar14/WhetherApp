import requests
from django.shortcuts import render

def home(request):
    weather_data = None
    error_message = None
    
    if request.method == 'POST':
        city = request.POST.get('city')
        if city:
            api_key = 'ec969c49b05f3542ea34e4df8bb3126b'  # 🔥 Add your API key here
            url = f'https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric'
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                weather_data = {
                    'city': city,
                    'temperature': data['main']['temp'],
                    'description': data['weather'][0]['description'],
                    'icon': data['weather'][0]['icon']
                }
            else:
                error_message = 'City not found!'
    
    context = {'weather_data': weather_data, 'error_message': error_message}
    return render(request, 'home.html', context)
