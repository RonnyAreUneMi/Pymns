from django.db import models
from django.contrib.auth.models import User, Permission

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    permissions = models.ManyToManyField(Permission, blank=True)

    def __str__(self):
        return self.name

# Modelo de perfil que se conecta al usuario
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)

    def save(self, *args, **kwargs):
        # Convertir nombre y apellido a mayúsculas
        self.first_name = self.first_name.upper()
        self.last_name = self.last_name.upper()
        super().save(*args, **kwargs)

    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip()

    def __str__(self):
        return self.get_full_name()