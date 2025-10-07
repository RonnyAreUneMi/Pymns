from django.urls import path
from . import views

app_name = 'articulos'

urlpatterns = [
    path('<int:proyecto_id>/', views.ver_articulos, name='ver_articulos'),
    path('<int:proyecto_id>/agregar/', views.agregar_articulo, name='agregar_articulo'),
]