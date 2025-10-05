# pymetanalis/urls.py (archivo principal del proyecto)

from django.contrib import admin
from django.urls import path, include
from pymetanalis import views  # Importar las views de pymetanalis

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),  # URLs del core, incluyendo el home
    path('usuarios/', include('usuarios.urls')),  # URLs de usuarios con prefijo
    path('security/', include('security.urls')),  # Faltaba la coma aquí
    
    # URLs de proyectos (directamente en el proyecto principal)
    path('proyectos/crear/', views.crear_proyecto, name='crear_proyecto'),
    path('proyectos/mis-proyectos/', views.mis_proyectos, name='mis_proyectos'),
    path('proyectos/buscar/', views.buscar_proyectos, name='buscar_proyectos'),
    path('proyectos/<int:proyecto_id>/', views.detalle_proyecto, name='detalle_proyecto'),
    path('proyectos/<int:proyecto_id>/editar/', views.editar_proyecto, name='editar_proyecto'),
]