
from django.contrib import admin
from django.urls import include, path
from ladder import views 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ladder/', include('ladder.urls')),
    path('', views.ladder, name='home'),
]
