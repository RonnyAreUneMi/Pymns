from django.urls import path
from . import views

app_name = 'articulos'

urlpatterns = [
    path('<int:proyecto_id>/', views.ver_articulos, name='ver_articulos'),
    path('<int:proyecto_id>/agregar/', views.agregar_articulo, name='agregar_articulo'),
    path('descargar/<int:articulo_id>/', views.descargar_articulo, name='descargar_articulo'),
    path('eliminar/<int:articulo_id>/', views.eliminar_articulo, name='eliminar_articulo'),
    path('descargar-archivo/<str:archivo_nombre>/', views.descargar_archivo_bib, name='descargar_archivo_bib'),
]