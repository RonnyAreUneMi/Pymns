# articulos/urls.py

from django.urls import path
from . import views

app_name = 'articulos'

urlpatterns = [
        # ==================== GESTIÓN DE CAMPOS ====================
    path('proyecto/<int:proyecto_id>/campos/', 
         views.gestionar_campos, 
         name='gestionar_campos'),
    
    path('campo/<int:campo_id>/eliminar/', 
         views.eliminar_campo, 
         name='eliminar_campo'),
    
    # ==================== ASIGNACIÓN DE TAREAS ====================
    path('proyecto/<int:proyecto_id>/asignar-tareas/', 
         views.asignar_tareas, 
         name='asignar_tareas'),
    
    path('proyecto/<int:proyecto_id>/usuario/<int:usuario_id>/articulos/', 
         views.cargar_articulos_usuario, 
         name='cargar_articulos_usuario'),
    
    path('proyecto/<int:proyecto_id>/asignar-campos/', 
         views.asignar_campos_articulos, 
         name='asignar_campos_articulos'),
    
    # ==================== PLANTILLAS ====================
    path('proyecto/<int:proyecto_id>/plantillas/', 
         views.gestionar_plantillas, 
         name='gestionar_plantillas'),
    
    path('plantilla/<int:plantilla_id>/eliminar/', 
         views.eliminar_plantilla, 
         name='eliminar_plantilla'),
    
    path('proyecto/<int:proyecto_id>/plantilla/aplicar-masiva/', 
         views.aplicar_plantilla_masiva, 
         name='aplicar_plantilla_masiva'),

    
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