from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from pymetanalis.models import Proyecto

# ==================== MODELO PRINCIPAL: ARTÍCULO ====================

class Articulo(models.Model):
    """Modelo principal de artículos con sistema de estados mejorado"""
    
    # Estados según el flujo de trabajo
    ESTADO_CHOICES = [
        ('EN_ESPERA', 'En Espera'),           # 0 - Subido pero sin tareas asignadas
        ('PENDIENTE', 'Pendiente'),           # 1 - Tarea asignada, puede empezar
        ('EN_PROCESO', 'En Proceso'),         # 2 - Colaborador trabajando
        ('EN_REVISION', 'En Revisión'),       # 3 - Enviado a supervisor
        ('APROBADO', 'Aprobado'),             # 4 - Finalizado y aceptado
    ]
    
    # Relaciones base
    proyecto = models.ForeignKey(
        Proyecto, 
        on_delete=models.CASCADE, 
        related_name='articulos'
    )
    usuario_carga = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='articulos_subidos',
        help_text='Usuario que subió el artículo'
    )
    usuario_asignado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articulos_asignados',
        help_text='Colaborador asignado para trabajar en este artículo'
    )
    
    # Datos bibliográficos
    bibtex_key = models.CharField(max_length=200, unique=True)
    titulo = models.CharField(max_length=500)
    doi = models.CharField(max_length=200, null=True, blank=True)
    bibtex_original = models.TextField()
    metadata_completos = models.JSONField(null=True, blank=True)
    archivo_bib = models.CharField(
        max_length=255, 
        null=True, 
        blank=True, 
        help_text="Nombre del archivo .bib de origen"
    )
    
    # Control de estado
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='EN_ESPERA'
    )
    
    # Control de duplicados
    articulo_original = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicados'
    )
    
    # Fechas de control
    fecha_carga = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_asignacion = models.DateTimeField(
        null=True, 
        blank=True,
        help_text='Cuándo se asignaron tareas (paso a PENDIENTE)'
    )
    fecha_inicio_trabajo = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Cuándo el colaborador empezó a trabajar (EN_PROCESO)'
    )
    fecha_envio_revision = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Cuándo se envió a revisión'
    )
    fecha_aprobacion = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Cuándo fue aprobado'
    )

    class Meta:
        verbose_name = 'Artículo'
        verbose_name_plural = 'Artículos'
        ordering = ['-fecha_carga']
        indexes = [
            models.Index(fields=['proyecto', 'estado']),
            models.Index(fields=['usuario_asignado', 'estado']),
            models.Index(fields=['fecha_actualizacion']),
            models.Index(fields=['bibtex_key']),
        ]

    def __str__(self):
        return f"{self.titulo[:50]}... ({self.get_estado_display()})"
    
    def cambiar_estado(self, nuevo_estado, usuario=None):
        """Método centralizado para cambio de estados con validaciones"""
        estado_anterior = self.estado
        self.estado = nuevo_estado
        
        # Registrar fechas según el estado
        if nuevo_estado == 'PENDIENTE' and not self.fecha_asignacion:
            self.fecha_asignacion = timezone.now()
        elif nuevo_estado == 'EN_PROCESO' and not self.fecha_inicio_trabajo:
            self.fecha_inicio_trabajo = timezone.now()
        elif nuevo_estado == 'EN_REVISION':
            self.fecha_envio_revision = timezone.now()
        elif nuevo_estado == 'APROBADO':
            self.fecha_aprobacion = timezone.now()
        
        self.save()
        
        # Registrar en historial
        if usuario:
            HistorialArticulo.objects.create(
                articulo=self,
                usuario=usuario,
                tipo_cambio='CAMBIO_ESTADO',
                campo_modificado='estado',
                valor_anterior=estado_anterior,
                valor_nuevo=nuevo_estado
            )
        
        return True
    
    def porcentaje_completado(self):
        """Calcula el % de campos completados vs asignados"""
        campos_asignados = self.campos_asignados.all()
        if not campos_asignados.exists():
            return 0
        
        total = campos_asignados.count()
        completados = campos_asignados.filter(completado=True).count()
        
        return round((completados / total) * 100, 2) if total > 0 else 0
    
    def porcentaje_aprobado(self):
        """Calcula el % de campos aprobados vs completados"""
        campos_completados = self.campos_asignados.filter(completado=True)
        if not campos_completados.exists():
            return 0
        
        total = campos_completados.count()
        aprobados = campos_completados.filter(aprobado=True).count()
        
        return round((aprobados / total) * 100, 2) if total > 0 else 0
    
    def puede_aprobar_articulo(self):
        """Verifica si todos los campos completados están aprobados"""
        campos_completados = self.campos_asignados.filter(completado=True)
        if not campos_completados.exists():
            return False
        
        return not campos_completados.filter(aprobado=False).exists()


# ==================== CATÁLOGO DE CAMPOS PARA METAANÁLISIS ====================

class CampoMetanalisis(models.Model):
    """Catálogo de campos/variables que se pueden buscar en artículos"""
    
    CATEGORIA_CHOICES = [
        ('IDENTIFICACION', 'Identificación del Estudio'),
        ('METODOLOGIA', 'Metodología'),
        ('MUESTRA', 'Muestra y Participantes'),
        ('RESULTADOS', 'Resultados Estadísticos'),
        ('EFECTOS', 'Tamaños de Efecto'),
        ('CALIDAD', 'Calidad del Estudio'),
        ('OTROS', 'Otros'),
    ]
    
    TIPO_DATO_CHOICES = [
        ('TEXTO', 'Texto'),
        ('NUMERO', 'Número'),
        ('FECHA', 'Fecha'),
        ('BOOLEANO', 'Sí/No'),
        ('OPCIONES', 'Opciones múltiples'),
    ]
    
    nombre = models.CharField(
        max_length=200,
        unique=True,
        help_text='Nombre del campo (ej: "Tamaño de muestra")'
    )
    codigo = models.CharField(
        max_length=50,
        unique=True,
        help_text='Código corto para base de datos (ej: "sample_size")'
    )
    categoria = models.CharField(
        max_length=30,
        choices=CATEGORIA_CHOICES,
        default='OTROS'
    )
    tipo_dato = models.CharField(
        max_length=20,
        choices=TIPO_DATO_CHOICES,
        default='TEXTO'
    )
    descripcion = models.TextField(
        blank=True,
        help_text='Descripción detallada de qué buscar'
    )
    opciones_validas = models.JSONField(
        null=True,
        blank=True,
        help_text='Si tipo_dato=OPCIONES, lista de opciones válidas'
    )
    
    # Control
    es_predefinido = models.BooleanField(
        default=False,
        help_text='Campo del sistema (no se puede eliminar)'
    )
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='campos_personalizados',
        help_text='Si es NULL, es global. Si tiene proyecto, es personalizado.'
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campos_creados'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Campo de Metaanálisis'
        verbose_name_plural = 'Campos de Metaanálisis'
        ordering = ['categoria', 'nombre']
        indexes = [
            models.Index(fields=['categoria', 'activo']),
            models.Index(fields=['proyecto']),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.get_categoria_display()})"


# ==================== ASIGNACIÓN DE CAMPOS A ARTÍCULOS ====================

class AsignacionCampo(models.Model):
    """Relación entre artículo, colaborador y campo a buscar"""
    
    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.CASCADE,
        related_name='campos_asignados'
    )
    campo = models.ForeignKey(
        CampoMetanalisis,
        on_delete=models.PROTECT,
        related_name='asignaciones'
    )
    
    # Valor encontrado (consistente con las vistas)
    valor = models.TextField(
        blank=True,
        null=True,
        help_text='Valor encontrado por el colaborador'
    )
    completado = models.BooleanField(
        default=False,
        help_text='Si el colaborador ya llenó este campo'
    )
    
    # Control de trabajo
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_completado = models.DateTimeField(null=True, blank=True)
    asignado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='campos_que_asigno'
    )
    
    # 🆕 Aprobación granular por campo
    aprobado = models.BooleanField(
        default=False,
        help_text='Si este campo específico fue aprobado por un supervisor'
    )
    aprobado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campos_aprobados',
        help_text='Supervisor que aprobó este campo específico'
    )
    fecha_aprobacion_campo = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Cuándo fue aprobado este campo'
    )
    
    # Notas internas
    notas = models.TextField(
        blank=True,
        help_text='Notas del colaborador sobre este campo específico'
    )

    class Meta:
        unique_together = ('articulo', 'campo')
        verbose_name = 'Asignación de Campo'
        verbose_name_plural = 'Asignaciones de Campos'
        ordering = ['campo__categoria', 'campo__nombre']
        indexes = [
            models.Index(fields=['articulo', 'completado']),
        ]

    def __str__(self):
        return f"{self.articulo.titulo[:30]}... - {self.campo.nombre}"
    
    def marcar_completado(self, valor, usuario=None):
        """Marca el campo como completado y guarda el valor"""
        self.valor = valor
        self.completado = bool(valor)  # Solo completado si tiene valor
        self.fecha_completado = timezone.now() if valor else None
        self.save()
        
        # Registrar en historial
        if usuario:
            HistorialArticulo.objects.create(
                articulo=self.articulo,
                usuario=usuario,
                tipo_cambio='EDICION_METADATA',
                campo_modificado=self.campo.codigo,
                valor_nuevo=valor
            )
    
    def aprobar_campo(self, supervisor):
        """Aprueba este campo específico (aprobación granular)"""
        self.aprobado = True
        self.aprobado_por = supervisor
        self.fecha_aprobacion_campo = timezone.now()
        self.save()
        
        # Registrar en historial
        HistorialArticulo.objects.create(
            articulo=self.articulo,
            usuario=supervisor,
            tipo_cambio='APROBACION',
            campo_modificado=self.campo.codigo,
            valor_nuevo=f'Campo "{self.campo.nombre}" aprobado individualmente'
        )
    
    def desaprobar_campo(self, supervisor, razon=None):
        """Quita la aprobación de un campo (para correcciones)"""
        self.aprobado = False
        self.aprobado_por = None
        self.fecha_aprobacion_campo = None
        self.save()
        
        # Registrar en historial
        HistorialArticulo.objects.create(
            articulo=self.articulo,
            usuario=supervisor,
            tipo_cambio='SOLICITUD_CORRECCION',
            campo_modificado=self.campo.codigo,
            valor_nuevo=f'Aprobación retirada' + (f': {razon}' if razon else '')
        )


# ==================== PLANTILLAS DE ASIGNACIÓN ====================

class PlantillaBusqueda(models.Model):
    """Plantillas predefinidas de conjuntos de campos para reutilizar"""
    
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name='plantillas_busqueda'
    )
    campos = models.ManyToManyField(
        CampoMetanalisis,
        related_name='plantillas'
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    es_predeterminada = models.BooleanField(
        default=False,
        help_text='Se aplica automáticamente a nuevos artículos'
    )

    class Meta:
        verbose_name = 'Plantilla de Búsqueda'
        verbose_name_plural = 'Plantillas de Búsqueda'
        ordering = ['-es_predeterminada', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.campos.count()} campos)"
    
    def aplicar_a_articulo(self, articulo, asignado_por):
        """Aplica todos los campos de la plantilla a un artículo"""
        campos_creados = []
        for campo in self.campos.all():
            asignacion, created = AsignacionCampo.objects.get_or_create(
                articulo=articulo,
                campo=campo,
                defaults={'asignado_por': asignado_por}
            )
            if created:
                campos_creados.append(asignacion)
        
        return campos_creados


# ==================== COMENTARIOS DE REVISIÓN ====================

class ComentarioRevision(models.Model):
    """Comentarios de supervisores durante el proceso de revisión"""
    
    TIPO_ACCION_CHOICES = [
        ('APROBADO', 'Aprobado'),
        ('CORRECCION', 'Corrección Solicitada'),
    ]
    
    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.CASCADE,
        related_name='comentarios_revision'
    )
    supervisor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comentarios_dados',
        help_text='Supervisor que hizo el comentario'
    )
    colaborador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comentarios_recibidos',
        help_text='Colaborador que recibe el comentario'
    )
    comentario = models.TextField()
    tipo_accion = models.CharField(
        max_length=20,
        choices=TIPO_ACCION_CHOICES
    )
    fecha_comentario = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(
        default=False,
        help_text='Si el colaborador ya vio el comentario'
    )

    class Meta:
        ordering = ['-fecha_comentario']
        verbose_name = 'Comentario de Revisión'
        verbose_name_plural = 'Comentarios de Revisión'
        indexes = [
            models.Index(fields=['articulo', '-fecha_comentario']),
            models.Index(fields=['colaborador', 'leido']),
        ]

    def __str__(self):
        return f"{self.supervisor.username} -> {self.colaborador.username}: {self.tipo_accion}"


# ==================== ARCHIVOS SUBIDOS ====================

class ArchivoSubida(models.Model):
    """Archivos .bib subidos al proyecto"""
    
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name='archivos_subidos'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='archivos_subidos'
    )
    nombre_archivo = models.CharField(max_length=255)
    ruta_archivo = models.FileField(upload_to='uploads/articulos/')
    articulos_procesados = models.IntegerField(default=0)
    errores_procesamiento = models.JSONField(null=True, blank=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Archivo Subido'
        verbose_name_plural = 'Archivos Subidos'
        ordering = ['-fecha_subida']
        indexes = [
            models.Index(fields=['proyecto', '-fecha_subida']),
        ]

    def __str__(self):
        return f"{self.nombre_archivo} ({self.proyecto.nombre})"


# ==================== HISTORIAL DE ARTÍCULOS ====================

class HistorialArticulo(models.Model):
    """Historial completo de cambios en artículos"""
    
    TIPO_CAMBIO_CHOICES = [
        ('CREACION', 'Creación'),
        ('EDICION_METADATA', 'Edición de Metadata'),
        ('CAMBIO_ESTADO', 'Cambio de Estado'),
        ('ASIGNACION', 'Asignación de Tarea'),
        ('MODIFICACION', 'Modificación'),
        ('DESCARGA', 'Descarga'),
        ('ELIMINACION', 'Eliminación'),
        ('ENVIO_REVISION', 'Envío a Revisión'),
        ('APROBACION', 'Aprobación'),
        ('SOLICITUD_CORRECCION', 'Corrección Solicitada'),
    ]
    
    articulo = models.ForeignKey(
        Articulo, 
        on_delete=models.CASCADE, 
        related_name='historial'
    )
    usuario = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='historial_articulos'
    )
    tipo_cambio = models.CharField(
        max_length=30,
        choices=TIPO_CAMBIO_CHOICES
    )
    campo_modificado = models.CharField(max_length=100, null=True, blank=True)
    valor_anterior = models.TextField(null=True, blank=True)
    valor_nuevo = models.TextField(null=True, blank=True)
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Historial de Artículo'
        verbose_name_plural = 'Historial de Artículos'
        ordering = ['-fecha_cambio']
        indexes = [
            models.Index(fields=['articulo', '-fecha_cambio']),
            models.Index(fields=['tipo_cambio']),
            models.Index(fields=['usuario', '-fecha_cambio']),
        ]

    def __str__(self):
        fecha_str = self.fecha_cambio.strftime('%d/%m/%Y %H:%M')
        usuario_str = self.usuario.get_full_name() or self.usuario.username if self.usuario else 'Sistema'
        return f"{self.get_tipo_cambio_display()} - {self.articulo.titulo[:30]}... - {usuario_str} - {fecha_str}"