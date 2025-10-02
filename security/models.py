# security/models.py

import uuid
from django.db import models
from django.contrib.auth.models import User
from pymetanalis.models import Proyecto  # Importa Proyecto desde pymetanalisis

class Invitacion(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('ACEPTADA', 'Aceptada'),
        ('EXPIRADA', 'Expirada'),
    ]

    ROL_ASIGNADO_CHOICES = [
        ('SUPERVISOR', 'Supervisor'),
        ('COLABORADOR', 'Colaborador'),
    ]

    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='invitaciones')
    usuario_invitador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invitaciones_enviadas')
    email_invitado = models.EmailField(max_length=254)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    rol_asignado = models.CharField(max_length=20, choices=ROL_ASIGNADO_CHOICES)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    fecha_expiracion = models.DateTimeField()

    class Meta:
        verbose_name = 'Invitación'
        verbose_name_plural = 'Invitaciones'

    def __str__(self):
        return f"Invitación a {self.email_invitado} para {self.proyecto.nombre}"