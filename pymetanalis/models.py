from django.db import models
from django.contrib.auth.models import User
from usuarios.models import Role  # Asumiendo que Role está en usuarios app; ajusta si es necesario

class Proyecto(models.Model):
    ESTADO_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('PAUSADO', 'Pausado'),
        ('FINALIZADO', 'Finalizado'),
    ]

    nombre = models.CharField(max_length=255)
    usuario_creador = models.ForeignKey(User, on_delete=models.PROTECT, related_name='proyectos_creados')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='ACTIVO')
    configuracion = models.JSONField(null=True, blank=True)
    total_articulos = models.IntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Proyecto'
        verbose_name_plural = 'Proyectos'

    def __str__(self):
        return self.nombre

class UsuarioProyecto(models.Model):
    ROL_PROYECTO_CHOICES = [
        ('DUEÑO', 'Dueño'),
        ('SUPERVISOR', 'Supervisor'),
        ('COLABORADOR', 'Colaborador'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='usuario_proyectos')
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='usuario_proyectos')
    rol_proyecto = models.CharField(max_length=20, choices=ROL_PROYECTO_CHOICES)
    fecha_incorporacion = models.DateTimeField(auto_now_add=True)
    puede_invitar = models.BooleanField(default=False)

    class Meta:
        unique_together = ('usuario', 'proyecto')
        verbose_name = 'Usuario Proyecto'
        verbose_name_plural = 'Usuarios Proyectos'

    def __str__(self):
        return f"{self.usuario.username} - {self.proyecto.nombre} ({self.rol_proyecto})"

class EstadisticaProyecto(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='estadisticas')
    fecha = models.DateField()
    total_articulos = models.IntegerField(default=0)
    articulos_aprobados = models.IntegerField(default=0)
    promedio_calidad = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ('proyecto', 'fecha')
        verbose_name = 'Estadística Proyecto'
        verbose_name_plural = 'Estadísticas Proyectos'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.proyecto.nombre} - {self.fecha}"