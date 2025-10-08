# pymetanalis/urls.py (archivo principal del proyecto)
from django.contrib import admin
from django.urls import path, include
from pymetanalis import views  # Importar las views de pymetanalis

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),  # URLs del core, incluyendo el home
    path('usuarios/', include('usuarios.urls')),  # URLs de usuarios con prefijo
    path('security/', include('security.urls')),  # Faltaba la coma aquí
    path('articulos/', include('articulos.urls')), 
    
    # URLs de proyectos
    path('proyectos/crear/', views.crear_proyecto, name='crear_proyecto'),
    path('proyectos/mis-proyectos/', views.mis_proyectos, name='mis_proyectos'),
    path('proyectos/buscar/', views.buscar_proyectos, name='buscar_proyectos'),
    path('proyectos/<int:proyecto_id>/', views.detalle_proyecto, name='detalle_proyecto'),
    path('proyectos/<int:proyecto_id>/editar/', views.editar_proyecto, name='editar_proyecto'),
    
    # ==================== URLs DE SOLICITUDES Y MIEMBROS (FALTAN ESTAS) ====================
    path('proyectos/<int:proyecto_id>/solicitar-unirse/', views.solicitar_unirse_proyecto, name='solicitar_unirse_proyecto'),
    path('solicitudes/<int:solicitud_id>/gestionar/', views.gestionar_solicitud, name='gestionar_solicitud'),
    path('proyectos/<int:proyecto_id>/invitar/', views.invitar_usuario, name='invitar_usuario'),
    
    # ==================== URLs DE NOTIFICACIONES ====================
    path('notificaciones/obtener/', views.obtener_notificaciones, name='obtener_notificaciones'),
    path('notificaciones/contar/', views.contar_notificaciones, name='contar_notificaciones'),
    path('notificaciones/marcar-leida/<int:notificacion_id>/', views.marcar_notificacion_leida, name='marcar_notificacion_leida'),
    path('notificaciones/marcar-todas-leidas/', views.marcar_todas_notificaciones_leidas, name='marcar_todas_notificaciones_leidas'),
    path('proyectos/<int:proyecto_id>/miembro/<int:usuario_id>/cambiar-rol/', views.cambiar_rol_miembro, name='cambiar_rol_miembro'),
    path('proyectos/<int:proyecto_id>/miembro/<int:usuario_id>/eliminar/', views.eliminar_miembro, name='eliminar_miembro'),
    path('proyectos/<int:proyecto_id>/abandonar/', views.abandonar_proyecto, name='abandonar_proyecto'),

]
