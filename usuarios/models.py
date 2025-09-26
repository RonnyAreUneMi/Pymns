from django.db import models
from django.contrib.auth.models import User, Permission
from django.db.models.signals import post_save
from django.dispatch import receiver

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    
    def __str__(self):
        return self.name

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Si no se proporcionan nombres en el perfil, usar los del User
        if not self.first_name and self.user.first_name:
            self.first_name = self.user.first_name.upper()
        elif self.first_name:
            self.first_name = self.first_name.upper()
            
        if not self.last_name and self.user.last_name:
            self.last_name = self.user.last_name.upper()
        elif self.last_name:
            self.last_name = self.last_name.upper()
            
        super().save(*args, **kwargs)
        
        # Sincronizar con el modelo User si es necesario
        if self.first_name and self.user.first_name != self.first_name.title():
            self.user.first_name = self.first_name.title()
            self.user.save()
        if self.last_name and self.user.last_name != self.last_name.title():
            self.user.last_name = self.last_name.title()
            self.user.save()
    
    def get_full_name(self):
        # Priorizar nombres del Profile, luego del User
        first = self.first_name or self.user.first_name
        last = self.last_name or self.user.last_name
        return f"{first} {last}".strip()
    
    def __str__(self):
        return self.get_full_name() or self.user.username

# Signal para crear automáticamente el perfil cuando se crea un usuario
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Solo crear si no existe ya
        if not hasattr(instance, 'profile'):
            try:
                invitado_role = Role.objects.get(name='invitado')
            except Role.DoesNotExist:
                invitado_role = Role.objects.create(name='invitado')
            
            Profile.objects.create(
                user=instance, 
                role=invitado_role,
                first_name=instance.first_name,
                last_name=instance.last_name
            )

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Actualizar el perfil si existe
    if hasattr(instance, 'profile'):
        # Sincronizar nombres si han cambiado en User
        if instance.profile.first_name.title() != instance.first_name:
            instance.profile.first_name = instance.first_name.upper()
            instance.profile.save()
        if instance.profile.last_name.title() != instance.last_name:
            instance.profile.last_name = instance.last_name.upper()
            instance.profile.save()

# Agregar estos modelos a tu archivo models.py existente

class Category(models.Model):
    """Modelo para categorías de proyectos"""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#22c55e', help_text='Color en formato hexadecimal')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    activa = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Project(models.Model):
    """Modelo para proyectos"""
    
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('completado', 'Completado'),
        ('pausado', 'Pausado'),
        ('cancelado', 'Cancelado'),
    ]
    
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    categoria = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo')
    
    # Fechas
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    
    # Información adicional
    tecnologias = models.TextField(blank=True, help_text='Tecnologías separadas por comas')
    url_publica = models.URLField(blank=True, help_text='URL pública del proyecto')
    url_repositorio = models.URLField(blank=True, help_text='URL del repositorio de código')
    
    # Control de visibilidad
    is_public = models.BooleanField(default=False, help_text='¿El proyecto es visible públicamente?')
    is_featured = models.BooleanField(default=False, help_text='¿Es un proyecto destacado?')
    
    # Relaciones
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proyectos_creados')
    colaboradores = models.ManyToManyField(User, blank=True, related_name='proyectos_colaborando')
    
    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['estado', 'is_public']),
            models.Index(fields=['fecha_creacion']),
            models.Index(fields=['categoria']),
        ]
    
    def __str__(self):
        return self.nombre
    
    def get_tecnologias_list(self):
        """Retorna las tecnologías como una lista"""
        if self.tecnologias:
            return [tech.strip() for tech in self.tecnologias.split(',') if tech.strip()]
        return []
    
    def get_colaboradores_names(self):
        """Retorna los nombres de los colaboradores"""
        return [colab.get_full_name() or colab.username for colab in self.colaboradores.all()]
    