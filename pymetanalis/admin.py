from django.contrib import admin
from .models import Proyecto, UsuarioProyecto, EstadisticaProyecto

admin.site.register(Proyecto)
admin.site.register(UsuarioProyecto)
admin.site.register(EstadisticaProyecto)