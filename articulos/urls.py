from django.urls import path
from . import views

app_name = 'articulos'

urlpatterns = [
    path('subir/<int:proyecto_id>/', views.subir_archivo, name='subir_archivo'),
    path('visualizar/<int:archivo_id>/', views.visualizar_articulos, name='visualizar_articulos'),
]