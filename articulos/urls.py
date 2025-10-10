# articulos/urls.py

from django.urls import path
from . import views

app_name = 'articulos'

urlpatterns = [
    # ✅ NUEVA: Ruta principal para seleccionar proyecto
    path('', views.seleccionar_proyecto_articulos, name='seleccionar_proyecto'),
    
    # Rutas específicas de proyecto
    path('<int:proyecto_id>/', views.ver_articulos, name='ver_articulos'),
    path('<int:proyecto_id>/agregar/', views.agregar_articulo, name='agregar_articulo'),
    path('<int:proyecto_id>/subir/', views.subir_archivo, name='subir_archivo'),
    
    # Rutas de descarga y eliminación
    path('descargar/<int:articulo_id>/', views.descargar_articulo, name='descargar_articulo'),
    path('eliminar/<int:articulo_id>/', views.eliminar_articulo, name='eliminar_articulo'),
    path('descargar-archivo/<str:archivo_nombre>/', views.descargar_archivo_bib, name='descargar_archivo_bib'),
    
    # Visualización
    path('visualizar/<int:archivo_id>/', views.visualizar_articulos, name='visualizar_articulos'),
]