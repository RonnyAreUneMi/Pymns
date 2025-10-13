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
    
    path('plantilla/<int:plantilla_id>/detalle/', 
         views.detalle_plantilla, 
         name='detalle_plantilla'),
    
    path('plantilla/<int:plantilla_id>/eliminar/', 
         views.eliminar_plantilla, 
         name='eliminar_plantilla'),
    
    path('proyecto/<int:proyecto_id>/aplicar-plantilla-masiva/', 
         views.aplicar_plantilla_masiva, 
         name='aplicar_plantilla_masiva'),
    
    # ==================== WORKSPACE Y TRABAJO EN ARTÍCULOS ====================
    path('workspace/<int:articulo_id>/', 
         views.workspace_articulo, 
         name='workspace_articulo'),
    
    path('workspace/<int:articulo_id>/guardar-campo/', 
         views.guardar_campo_workspace, 
         name='guardar_campo_workspace'),
    
    path('workspace/<int:articulo_id>/estadisticas/', 
         views.estadisticas_articulo, 
         name='estadisticas_articulo'),
    
    # ==================== REVISIÓN Y APROBACIÓN ====================
    path('proyecto/<int:proyecto_id>/bandeja-revision/', 
         views.bandeja_revision, 
         name='bandeja_revision'),
    
    path('articulo/<int:articulo_id>/enviar-revision/', 
         views.enviar_a_revision, 
         name='enviar_a_revision'),
    
    path('proyecto/<int:proyecto_id>/enviar-masivo-revision/', 
         views.enviar_masivo_revision, 
         name='enviar_masivo_revision'),
    
    path('articulo/<int:articulo_id>/aprobar/', 
         views.aprobar_articulo, 
         name='aprobar_articulo'),
    
    path('articulo/<int:articulo_id>/solicitar-correccion/', 
         views.solicitar_correccion, 
         name='solicitar_correccion'),
    
    # ==================== APROBACIÓN DE CAMPOS INDIVIDUALES ====================
    path('campo/<int:asignacion_id>/aprobar/', 
         views.aprobar_campo_individual, 
         name='aprobar_campo_individual'),
    
    path('campo/<int:asignacion_id>/solicitar-correccion/', 
         views.solicitar_correccion_campo, 
         name='solicitar_correccion_campo'),
    
    # ==================== GESTIÓN DE ARTÍCULOS ====================
    path('<int:proyecto_id>/', 
         views.ver_articulos, 
         name='ver_articulos'),
    
    path('<int:proyecto_id>/agregar/', 
         views.agregar_articulo, 
         name='agregar_articulo'),
    
    path('<int:proyecto_id>/subir/', 
         views.subir_archivo, 
         name='subir_archivo'),
    
    # ==================== DESCARGA Y ELIMINACIÓN ====================
    path('descargar/<int:articulo_id>/', 
         views.descargar_articulo, 
         name='descargar_articulo'),
    
    path('eliminar/<int:articulo_id>/', 
         views.eliminar_articulo, 
         name='eliminar_articulo'),
    
    path('descargar-archivo/<str:archivo_nombre>/', 
         views.descargar_archivo_bib, 
         name='descargar_archivo_bib'),
    
    # ==================== VISUALIZACIÓN ====================
    path('visualizar/<int:archivo_id>/', 
         views.visualizar_articulos, 
         name='visualizar_articulos'),
]