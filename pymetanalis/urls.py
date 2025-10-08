# pymetanalis/urls.py

from django.contrib import admin
from django.urls import path, include
from pymetanalis import views
from django.conf import settings
from django.conf.urls.static import static  # ← Agregar esta línea

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('usuarios/', include('usuarios.urls')),
    path('security/', include('security.urls')),
    path('articulos/', include('articulos.urls')),
    
    path('proyectos/crear/', views.crear_proyecto, name='crear_proyecto'),
    path('proyectos/mis-proyectos/', views.mis_proyectos, name='mis_proyectos'),
    path('proyectos/buscar/', views.buscar_proyectos, name='buscar_proyectos'),
    path('proyectos/<int:proyecto_id>/', views.detalle_proyecto, name='detalle_proyecto'),
    path('proyectos/<int:proyecto_id>/editar/', views.editar_proyecto, name='editar_proyecto'),
]

# Agregar esto al final (fuera de urlpatterns)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)