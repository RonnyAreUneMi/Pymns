from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import Proyecto, UsuarioProyecto, SolicitudProyecto
from django.db.models import Q, Count
from datetime import datetime


@login_required
def crear_proyecto(request):
    """Vista para crear un nuevo proyecto"""
    
    # Verificar que el usuario puede crear proyectos
    puede_crear = False
    if request.user.is_superuser:
        puede_crear = True
    elif hasattr(request.user, 'profile') and request.user.profile.role:
        puede_crear = request.user.profile.role.name in ['administrador', 'investigador']
    
    if not puede_crear:
        messages.error(request, 'No tienes permisos para crear proyectos. Solicita el rol de Investigador.')
        return redirect('core:home')
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        categoria = request.POST.get('categoria', 'SALUD')
        descripcion = request.POST.get('descripcion', '').strip()
        configuracion_json = {}
        
        # Validaciones
        if not nombre:
            messages.error(request, 'El nombre del proyecto es obligatorio.')
            return render(request, 'crear_proyectos.html', {
                'categorias': Proyecto.CATEGORIA_CHOICES
            })
        
        if len(nombre) > 255:
            messages.error(request, 'El nombre del proyecto es demasiado largo (máximo 255 caracteres).')
            return render(request, 'crear_proyectos.html', {
                'categorias': Proyecto.CATEGORIA_CHOICES
            })
        
        # Agregar descripción a la configuración JSON
        if descripcion:
            configuracion_json['descripcion'] = descripcion
        
        try:
            with transaction.atomic():
                # Crear el proyecto
                proyecto = Proyecto.objects.create(
                    nombre=nombre,
                    categoria=categoria,
                    usuario_creador=request.user,
                    estado='ACTIVO',
                    configuracion=configuracion_json
                )
                
                # Asignar automáticamente al creador como DUEÑO
                UsuarioProyecto.objects.create(
                    usuario=request.user,
                    proyecto=proyecto,
                    rol_proyecto='DUEÑO',
                    puede_invitar=True
                )
                
                messages.success(request, f'¡Proyecto "{proyecto.nombre}" creado exitosamente!')
                return redirect('detalle_proyecto', proyecto_id=proyecto.id)
                
        except Exception as e:
            messages.error(request, f'Error al crear el proyecto: {str(e)}')
    
    return render(request, 'crear_proyectos.html', {
        'categorias': Proyecto.CATEGORIA_CHOICES
    })


@login_required
def mis_proyectos(request):
    """Vista para listar los proyectos del usuario"""
    
    # Obtener proyectos donde el usuario participa
    usuario_proyectos = UsuarioProyecto.objects.filter(
        usuario=request.user
    ).select_related('proyecto').order_by('-fecha_incorporacion')
    
    # Filtros
    filtro_rol = request.GET.get('rol', '')
    filtro_estado = request.GET.get('estado', '')
    filtro_categoria = request.GET.get('categoria', '')
    busqueda = request.GET.get('q', '')
    
    if filtro_rol:
        usuario_proyectos = usuario_proyectos.filter(rol_proyecto=filtro_rol)
    
    proyectos_ids = usuario_proyectos.values_list('proyecto_id', flat=True)
    proyectos = Proyecto.objects.filter(id__in=proyectos_ids)
    
    if filtro_estado:
        proyectos = proyectos.filter(estado=filtro_estado)
    
    if filtro_categoria:
        proyectos = proyectos.filter(categoria=filtro_categoria)
    
    if busqueda:
        proyectos = proyectos.filter(
            Q(nombre__icontains=busqueda) |
            Q(usuario_creador__username__icontains=busqueda) |
            Q(usuario_creador__first_name__icontains=busqueda) |
            Q(usuario_creador__last_name__icontains=busqueda)
        )
    
    # Agregar información del rol del usuario en cada proyecto
    proyectos_data = []
    for proyecto in proyectos:
        usuario_proyecto = usuario_proyectos.filter(proyecto=proyecto).first()
        proyectos_data.append({
            'proyecto': proyecto,
            'rol': usuario_proyecto.rol_proyecto if usuario_proyecto else None,
            'puede_invitar': usuario_proyecto.puede_invitar if usuario_proyecto else False,
            'progreso': (proyecto.articulos_trabajados / proyecto.total_articulos * 100) 
                        if proyecto.total_articulos > 0 else 0
        })
    
    # Paginación
    paginator = Paginator(proyectos_data, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'filtro_rol': filtro_rol,
        'filtro_estado': filtro_estado,
        'filtro_categoria': filtro_categoria,
        'busqueda': busqueda,
        'roles': UsuarioProyecto.ROL_PROYECTO_CHOICES,
        'estados': Proyecto.ESTADO_CHOICES,
        'categorias': Proyecto.CATEGORIA_CHOICES,
    }
    
    return render(request, 'mis_proyectos.html', context)


@login_required
def detalle_proyecto(request, proyecto_id):
    """Vista para ver los detalles de un proyecto"""
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar que el usuario tiene acceso al proyecto
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    es_admin = request.user.is_superuser or (
        hasattr(request.user, 'profile') and 
        request.user.profile.role and 
        request.user.profile.role.name == 'administrador'
    )
    
    if not usuario_proyecto and not es_admin:
        messages.error(request, 'No tienes acceso a este proyecto.')
        return redirect('mis_proyectos')
    
    # Obtener miembros del proyecto
    miembros = UsuarioProyecto.objects.filter(
        proyecto=proyecto
    ).select_related('usuario', 'usuario__profile').order_by('-fecha_incorporacion')
    
    # Calcular progreso
    progreso = 0
    if proyecto.total_articulos > 0:
        progreso = round((proyecto.articulos_trabajados / proyecto.total_articulos) * 100, 1)
    
    # Obtener solicitudes pendientes si es dueño o supervisor
    solicitudes_pendientes = None
    if usuario_proyecto and usuario_proyecto.rol_proyecto in ['DUEÑO', 'SUPERVISOR']:
        solicitudes_pendientes = SolicitudProyecto.objects.filter(
            proyecto=proyecto,
            estado='PENDIENTE'
        ).select_related('usuario').order_by('-fecha_solicitud')
    
    context = {
        'proyecto': proyecto,
        'usuario_proyecto': usuario_proyecto,
        'miembros': miembros,
        'progreso': progreso,
        'solicitudes_pendientes': solicitudes_pendientes,
        'es_dueno': usuario_proyecto and usuario_proyecto.rol_proyecto == 'DUEÑO',
        'es_supervisor': usuario_proyecto and usuario_proyecto.rol_proyecto == 'SUPERVISOR',
        'puede_gestionar': (usuario_proyecto and usuario_proyecto.rol_proyecto in ['DUEÑO', 'SUPERVISOR']) or es_admin,
    }
    
    return render(request, 'detalle_proyecto.html', context)


@login_required
def buscar_proyectos(request):
    """Vista para buscar proyectos públicos"""
    
    busqueda = request.GET.get('q', '')
    categoria = request.GET.get('categoria', '')
    
    # Obtener todos los proyectos activos
    proyectos = Proyecto.objects.filter(estado='ACTIVO').select_related('usuario_creador')
    
    if busqueda:
        proyectos = proyectos.filter(
            Q(nombre__icontains=busqueda) |
            Q(usuario_creador__username__icontains=busqueda) |
            Q(usuario_creador__first_name__icontains=busqueda)
        )
    
    if categoria:
        proyectos = proyectos.filter(categoria=categoria)
    
    # Anotar con el número de miembros
    proyectos = proyectos.annotate(num_miembros=Count('usuario_proyectos'))
    
    # Marcar proyectos donde el usuario ya participa
    mis_proyectos_ids = UsuarioProyecto.objects.filter(
        usuario=request.user
    ).values_list('proyecto_id', flat=True)
    
    proyectos_data = []
    for proyecto in proyectos:
        proyectos_data.append({
            'proyecto': proyecto,
            'ya_participo': proyecto.id in mis_proyectos_ids,
            'num_miembros': proyecto.num_miembros,
        })
    
    # Paginación
    paginator = Paginator(proyectos_data, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'busqueda': busqueda,
        'categoria_filtro': categoria,
        'categorias': Proyecto.CATEGORIA_CHOICES,
    }
    
    return render(request, 'buscar_proyectos.html', context)


@login_required
def editar_proyecto(request, proyecto_id):
    """Vista para editar un proyecto (solo dueños)"""
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar permisos
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        rol_proyecto='DUEÑO'
    ).first()
    
    if not usuario_proyecto and not request.user.is_superuser:
        messages.error(request, 'No tienes permisos para editar este proyecto.')
        return redirect('detalle_proyecto', proyecto_id=proyecto_id)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        categoria = request.POST.get('categoria')
        estado = request.POST.get('estado')
        descripcion = request.POST.get('descripcion', '').strip()
        
        if not nombre:
            messages.error(request, 'El nombre del proyecto es obligatorio.')
        else:
            proyecto.nombre = nombre
            proyecto.categoria = categoria
            proyecto.estado = estado
            
            # Actualizar configuración
            if not proyecto.configuracion:
                proyecto.configuracion = {}
            proyecto.configuracion['descripcion'] = descripcion
            
            proyecto.save()
            messages.success(request, 'Proyecto actualizado exitosamente.')
            return redirect('detalle_proyecto', proyecto_id=proyecto_id)
    
    return render(request, 'editar_proyecto.html', {
        'proyecto': proyecto,
        'categorias': Proyecto.CATEGORIA_CHOICES,
        'estados': Proyecto.ESTADO_CHOICES,
    })
