from django.db import models
from django.contrib.auth.models import User
from pymetanalis.models import Proyecto

class Articulo(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='articulos')
    usuario_carga = models.ForeignKey(User, on_delete=models.PROTECT, related_name='articulos_subidos')
    bibtex_key = models.CharField(max_length=200, unique=True)
    titulo = models.CharField(max_length=500)
    doi = models.CharField(max_length=200, null=True, blank=True)
    bibtex_original = models.TextField()
    metadata_completos = models.JSONField(null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=[
            ('PENDIENTE', 'Pendiente'),
            ('EN_REVISION', 'En Revisión'),
            ('APROBADO', 'Aprobado'),
            ('RECHAZADO', 'Rechazado')
        ],
        default='PENDIENTE'
    )
    articulo_original = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicados'
    )
    fecha_carga = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo


class ArchivoSubida(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='archivos_subidos')
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='archivos_subidos')
    nombre_archivo = models.CharField(max_length=255)
    ruta_archivo = models.FileField(upload_to='uploads/articulos/')
    articulos_procesados = models.IntegerField(default=0)
    errores_procesamiento = models.JSONField(null=True, blank=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre_archivo} ({self.proyecto.nombre})"


class HistorialArticulo(models.Model):
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name='historial')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    tipo_cambio = models.CharField(
        max_length=30,
        choices=[
            ('CREACION', 'Creación'),
            ('EDICION_METADATA', 'Edición de Metadata'),
            ('CAMBIO_ESTADO', 'Cambio de Estado')
        ]
    )
    campo_modificado = models.CharField(max_length=100, null=True, blank=True)
    valor_anterior = models.TextField(null=True, blank=True)
    valor_nuevo = models.TextField(null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo_cambio} - {self.articulo.titulo}"