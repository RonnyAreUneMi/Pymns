from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from .models import Proyecto, UsuarioProyecto, SolicitudProyecto,Notificacion
import json


# ==================== GESTIÓN DE PROYECTOS ====================

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
# ==================== SOLICITUDES Y MIEMBROS ====================

@login_required
@require_POST
def solicitar_unirse_proyecto(request, proyecto_id):
    """Vista para que un usuario solicite unirse a un proyecto"""
    
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id, estado='ACTIVO')
        
        # Verificar que el usuario no sea ya miembro
        ya_miembro = UsuarioProyecto.objects.filter(
            usuario=request.user,
            proyecto=proyecto
        ).exists()
        
        if ya_miembro:
            return JsonResponse({
                'success': False,
                'message': 'Ya eres miembro de este proyecto.'
            }, status=400)
        
        # Verificar si ya tiene una solicitud pendiente
        solicitud_existente = SolicitudProyecto.objects.filter(
            usuario=request.user,
            proyecto=proyecto,
            estado='PENDIENTE'
        ).exists()
        
        if solicitud_existente:
            return JsonResponse({
                'success': False,
                'message': 'Ya tienes una solicitud pendiente para este proyecto.'
            }, status=400)
        
        # Obtener el mensaje del request
        data = json.loads(request.body)
        mensaje = data.get('mensaje', '').strip()
        
        # Crear la solicitud
        with transaction.atomic():
            solicitud = SolicitudProyecto.objects.create(
                usuario=request.user,
                proyecto=proyecto,
                tipo_solicitud='UNIRSE',  # ← AGREGUÉ ESTO (faltaba en tu código)
                mensaje=mensaje,
                estado='PENDIENTE'
            )
            
            # 🔔 CREAR NOTIFICACIÓN IN-APP PARA EL DUEÑO
            try:
                dueno = UsuarioProyecto.objects.get(
                    proyecto=proyecto,
                    rol_proyecto='DUEÑO'
                ).usuario
                
                # Crear la notificación
                Notificacion.objects.create(
                    usuario=dueno,
                    tipo='nueva_solicitud',
                    titulo=f'Nueva solicitud para {proyecto.nombre}',
                    mensaje=f'{request.user.get_full_name() or request.user.username} ha solicitado unirse a tu proyecto.',
                    url=reverse('detalle_proyecto', args=[proyecto.id]),
                    proyecto=proyecto,
                    solicitud=solicitud
                )
                
                # Enviar email (tu código existente)
                if dueno.email:
                    asunto = f'Nueva solicitud para "{proyecto.nombre}"'
                    mensaje_email = f"""Hola {dueno.get_full_name() or dueno.username},

{request.user.get_full_name() or request.user.username} ha solicitado unirse a tu proyecto "{proyecto.nombre}".

{f'Mensaje: "{mensaje}"' if mensaje else 'No incluyó un mensaje.'}

Puedes revisar y gestionar esta solicitud en:
{request.build_absolute_uri(reverse('detalle_proyecto', args=[proyecto.id]))}

Saludos,
Equipo de Metaanálisis
"""
                    
                    send_mail(
                        asunto,
                        mensaje_email,
                        settings.DEFAULT_FROM_EMAIL,
                        [dueno.email],
                        fail_silently=True,
                    )
            except UsuarioProyecto.DoesNotExist:
                pass
            except Exception as e:
                # Si falla la notificación, continuar de todos modos
                print(f"Error creando notificación: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Solicitud enviada exitosamente. El administrador del proyecto revisará tu solicitud.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al enviar la solicitud: {str(e)}'
        }, status=500)

@login_required
@require_POST
def gestionar_solicitud(request, solicitud_id):
    """Vista para aceptar o rechazar solicitudes"""
    
    try:
        solicitud = get_object_or_404(SolicitudProyecto, id=solicitud_id, estado='PENDIENTE')
        
        # Verificar permisos (debe ser dueño o supervisor)
        usuario_proyecto = UsuarioProyecto.objects.filter(
            usuario=request.user,
            proyecto=solicitud.proyecto,
            rol_proyecto__in=['DUEÑO', 'SUPERVISOR']
        ).first()
        
        if not usuario_proyecto and not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'message': 'No tienes permisos para gestionar solicitudes.'
            }, status=403)
        
        data = json.loads(request.body)
        accion = data.get('accion')  # 'aceptar' o 'rechazar'
        
        if accion not in ['aceptar', 'rechazar']:
            return JsonResponse({
                'success': False,
                'message': 'Acción no válida.'
            }, status=400)
        
        with transaction.atomic():
            if accion == 'aceptar':
                # Verificar nuevamente que no sea miembro (por si acaso)
                if UsuarioProyecto.objects.filter(
                    usuario=solicitud.usuario,
                    proyecto=solicitud.proyecto
                ).exists():
                    return JsonResponse({
                        'success': False,
                        'message': 'El usuario ya es miembro del proyecto.'
                    }, status=400)
                
                # Crear el usuario en el proyecto
                UsuarioProyecto.objects.create(
                    usuario=solicitud.usuario,
                    proyecto=solicitud.proyecto,
                    rol_proyecto='COLABORADOR',
                    puede_invitar=False
                )
                
                solicitud.estado = 'APROBADA'
                solicitud.respondido_por = request.user
                from django.utils import timezone
                solicitud.fecha_respuesta = timezone.now()
                solicitud.save()
                
                mensaje_respuesta = f'{solicitud.usuario.get_full_name() or solicitud.usuario.username} ha sido agregado al proyecto.'
                
                # CREAR NOTIFICACIÓN IN-APP
                crear_notificacion(
                    usuario=solicitud.usuario,
                    tipo='solicitud_aceptada',
                    titulo=f'¡Solicitud aceptada! - {solicitud.proyecto.nombre}',
                    mensaje=f'Tu solicitud para unirte al proyecto "{solicitud.proyecto.nombre}" ha sido aceptada.',
                    url=reverse('detalle_proyecto', args=[solicitud.proyecto.id]),
                    proyecto=solicitud.proyecto,
                    solicitud=solicitud
                )
                
                # Enviar email
                if solicitud.usuario.email:
                    try:
                        send_mail(
                            f'¡Solicitud aceptada! - {solicitud.proyecto.nombre}',
                            f"""Hola {solicitud.usuario.get_full_name() or solicitud.usuario.username},

¡Buenas noticias! Tu solicitud para unirte al proyecto "{solicitud.proyecto.nombre}" ha sido aceptada.

Ya puedes acceder al proyecto y comenzar a colaborar:
{request.build_absolute_uri(reverse('detalle_proyecto', args=[solicitud.proyecto.id]))}

Saludos,
Equipo de Metaanálisis
""",
                            settings.DEFAULT_FROM_EMAIL,
                            [solicitud.usuario.email],
                            fail_silently=True,
                        )
                    except Exception as e:
                        print(f"Error enviando email: {e}")
                
            else:  # rechazar
                solicitud.estado = 'RECHAZADA'
                solicitud.respondido_por = request.user
                from django.utils import timezone
                solicitud.fecha_respuesta = timezone.now()
                solicitud.save()
                
                mensaje_respuesta = 'Solicitud rechazada.'
                
                # CREAR NOTIFICACIÓN IN-APP
                crear_notificacion(
                    usuario=solicitud.usuario,
                    tipo='solicitud_rechazada',
                    titulo=f'Solicitud rechazada - {solicitud.proyecto.nombre}',
                    mensaje=f'Tu solicitud para unirte al proyecto "{solicitud.proyecto.nombre}" no ha sido aceptada en este momento.',
                    url=reverse('buscar_proyectos'),
                    proyecto=solicitud.proyecto,
                    solicitud=solicitud
                )
                
                # Enviar email
                if solicitud.usuario.email:
                    try:
                        send_mail(
                            f'Actualización de solicitud - {solicitud.proyecto.nombre}',
                            f"""Hola {solicitud.usuario.get_full_name() or solicitud.usuario.username},

Tu solicitud para unirte al proyecto "{solicitud.proyecto.nombre}" no ha sido aceptada en este momento.

Puedes buscar otros proyectos que puedan interesarte en la plataforma.

Saludos,
Equipo de Metaanálisis
""",
                            settings.DEFAULT_FROM_EMAIL,
                            [solicitud.usuario.email],
                            fail_silently=True,
                        )
                    except Exception as e:
                        print(f"Error enviando email: {e}")
        
        return JsonResponse({
            'success': True,
            'message': mensaje_respuesta
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al gestionar la solicitud: {str(e)}'
        }, status=500)

@login_required
def invitar_usuario(request, proyecto_id):
    """Vista para invitar usuarios al proyecto"""
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar permisos
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        puede_invitar=True
    ).first()
    
    es_admin = request.user.is_superuser or (
        hasattr(request.user, 'profile') and 
        request.user.profile.role and 
        request.user.profile.role.name == 'administrador'
    )
    
    if not usuario_proyecto and not es_admin:
        messages.error(request, 'No tienes permisos para invitar usuarios a este proyecto.')
        return redirect('detalle_proyecto', proyecto_id=proyecto_id)
    
    if request.method == 'POST':
        metodo = request.POST.get('metodo')  # 'email' o 'usuario'
        
        if metodo == 'usuario':
            # Invitar por nombre de usuario
            username = request.POST.get('username', '').strip()
            
            if not username:
                messages.error(request, 'Debes proporcionar un nombre de usuario.')
                return render(request, 'invitar_usuario.html', {'proyecto': proyecto})
            
            try:
                usuario_invitado = User.objects.get(username=username)
                
                # Verificar que no sea ya miembro
                if UsuarioProyecto.objects.filter(usuario=usuario_invitado, proyecto=proyecto).exists():
                    messages.error(request, 'Este usuario ya es miembro del proyecto.')
                else:
                    with transaction.atomic():
                        UsuarioProyecto.objects.create(
                            usuario=usuario_invitado,
                            proyecto=proyecto,
                            rol_proyecto='COLABORADOR',
                            puede_invitar=False
                        )
                        
                        messages.success(request, f'{usuario_invitado.get_full_name() or usuario_invitado.username} ha sido agregado al proyecto.')
                        
                        # 🔔 CREAR NOTIFICACIÓN IN-APP
                        crear_notificacion(
                            usuario=usuario_invitado,
                            tipo='invitacion_proyecto',
                            titulo=f'Invitación a proyecto: {proyecto.nombre}',
                            mensaje=f'{request.user.get_full_name() or request.user.username} te ha invitado a colaborar en el proyecto "{proyecto.nombre}".',
                            url=reverse('detalle_proyecto', args=[proyecto.id]),
                            proyecto=proyecto
                        )
                        
                        # Enviar email
                        if usuario_invitado.email:
                            try:
                                send_mail(
                                    f'Invitación a proyecto: {proyecto.nombre}',
                                    f"""Hola {usuario_invitado.get_full_name() or usuario_invitado.username},

Has sido invitado a colaborar en el proyecto "{proyecto.nombre}" por {request.user.get_full_name() or request.user.username}.

Accede al proyecto aquí:
{request.build_absolute_uri(reverse('detalle_proyecto', args=[proyecto.id]))}

Saludos,
Equipo de Metaanálisis
""",
                                    settings.DEFAULT_FROM_EMAIL,
                                    [usuario_invitado.email],
                                    fail_silently=True,
                                )
                            except Exception as e:
                                print(f"Error enviando email: {e}")
                    
                    return redirect('detalle_proyecto', proyecto_id=proyecto_id)
                    
            except User.DoesNotExist:
                messages.error(request, 'Usuario no encontrado.')
        
        elif metodo == 'email':
            # Invitar por email
            email = request.POST.get('email', '').strip()
            
            if not email:
                messages.error(request, 'Debes proporcionar un correo electrónico.')
                return render(request, 'invitar_usuario.html', {'proyecto': proyecto})
            
            try:
                # Buscar si el usuario existe
                try:
                    usuario_existente = User.objects.get(email=email)
                    
                    if UsuarioProyecto.objects.filter(usuario=usuario_existente, proyecto=proyecto).exists():
                        messages.error(request, 'Este usuario ya es miembro del proyecto.')
                    else:
                        with transaction.atomic():
                            # Agregar al proyecto
                            UsuarioProyecto.objects.create(
                                usuario=usuario_existente,
                                proyecto=proyecto,
                                rol_proyecto='COLABORADOR',
                                puede_invitar=False
                            )
                            
                            # 🔔 CREAR NOTIFICACIÓN IN-APP
                            crear_notificacion(
                                usuario=usuario_existente,
                                tipo='invitacion_proyecto',
                                titulo=f'Invitación a proyecto: {proyecto.nombre}',
                                mensaje=f'{request.user.get_full_name() or request.user.username} te ha invitado a colaborar en el proyecto "{proyecto.nombre}".',
                                url=reverse('detalle_proyecto', args=[proyecto.id]),
                                proyecto=proyecto
                            )
                            
                            # Enviar email
                            send_mail(
                                f'Invitación a proyecto: {proyecto.nombre}',
                                f"""Hola {usuario_existente.get_full_name() or usuario_existente.username},

Has sido invitado a colaborar en el proyecto "{proyecto.nombre}" por {request.user.get_full_name() or request.user.username}.

Accede al proyecto aquí:
{request.build_absolute_uri(reverse('detalle_proyecto', args=[proyecto.id]))}

Saludos,
Equipo de Metaanálisis
""",
                                settings.DEFAULT_FROM_EMAIL,
                                [email],
                                fail_silently=False,
                            )
                            
                            messages.success(request, f'Usuario agregado al proyecto y notificado.')
                
                except User.DoesNotExist:
                    # Usuario no existe, enviar invitación para registrarse
                    send_mail(
                        f'Invitación a proyecto: {proyecto.nombre}',
                        f"""Hola,

{request.user.get_full_name() or request.user.username} te ha invitado a colaborar en el proyecto "{proyecto.nombre}" en nuestra plataforma de metaanálisis.

Para unirte, primero necesitas crear una cuenta:
{request.build_absolute_uri(reverse('register'))}

Después de registrarte, busca el proyecto "{proyecto.nombre}" en la plataforma para unirte.

Saludos,
Equipo de Metaanálisis
""",
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=False,
                    )
                    
                    messages.success(request, 'Invitación enviada por correo electrónico. El usuario deberá registrarse primero.')
                
                return redirect('detalle_proyecto', proyecto_id=proyecto_id)
            
            except Exception as e:
                messages.error(request, f'Error al enviar la invitación: {str(e)}')
        
        else:
            messages.error(request, 'Método de invitación no válido.')
    
    # GET: Mostrar formulario
    return render(request, 'invitar_usuario.html', {
        'proyecto': proyecto
    })



# ==================== SISTEMA DE NOTIFICACIONES ====================

@login_required
def obtener_notificaciones(request):
    """Vista para obtener las notificaciones del usuario (AJAX)"""
    
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Petición no válida'}, status=400)
    
    try:
        # Obtener las últimas 10 notificaciones
        notificaciones = Notificacion.objects.filter(
            usuario=request.user
        ).select_related('proyecto', 'solicitud')[:10]
        
        from django.utils.timesince import timesince
        
        notificaciones_data = []
        for notif in notificaciones:
            notificaciones_data.append({
                'id': notif.id,
                'tipo': notif.tipo,
                'titulo': notif.titulo,
                'mensaje': notif.mensaje,
                'leida': notif.leida,
                'url': notif.url or '#',
                'tiempo_relativo': f'hace {timesince(notif.fecha_creacion)}',
                'fecha_creacion': notif.fecha_creacion.isoformat(),
            })
        
        # Contar no leídas
        no_leidas = Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'notificaciones': notificaciones_data,
            'no_leidas': no_leidas
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def contar_notificaciones(request):
    """Vista para contar notificaciones no leídas (AJAX - polling)"""
    
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Petición no válida'}, status=400)
    
    try:
        no_leidas = Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'no_leidas': no_leidas
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def marcar_notificacion_leida(request, notificacion_id):
    """Vista para marcar una notificación como leída (AJAX)"""
    
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Petición no válida'}, status=400)
    
    try:
        notificacion = get_object_or_404(
            Notificacion,
            id=notificacion_id,
            usuario=request.user
        )
        
        notificacion.marcar_como_leida()
        
        return JsonResponse({
            'success': True,
            'message': 'Notificación marcada como leída',
            'url': notificacion.url
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def marcar_todas_notificaciones_leidas(request):
    """Vista para marcar todas las notificaciones como leídas (AJAX)"""
    
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Petición no válida'}, status=400)
    
    try:
        from django.utils import timezone
        
        actualizadas = Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        ).update(
            leida=True,
            fecha_lectura=timezone.now()
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{actualizadas} notificaciones marcadas como leídas'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== FUNCIÓN HELPER ====================

def crear_notificacion(usuario, tipo, titulo, mensaje, url=None, proyecto=None, solicitud=None):
    """
    Función helper para crear notificaciones fácilmente desde cualquier vista
    
    Parámetros:
        usuario: Usuario que recibirá la notificación
        tipo: Tipo de notificación (debe coincidir con TIPO_CHOICES)
        titulo: Título de la notificación
        mensaje: Mensaje descriptivo
        url: URL opcional para redirección
        proyecto: Proyecto relacionado (opcional)
        solicitud: Solicitud relacionada (opcional)
    """
    try:
        Notificacion.objects.create(
            usuario=usuario,
            tipo=tipo,
            titulo=titulo,
            mensaje=mensaje,
            url=url,
            proyecto=proyecto,
            solicitud=solicitud
        )
    except Exception as e:
        # Log del error pero no fallar la operación principal
        print(f"Error creando notificación: {e}")
    
@login_required
@require_POST
def cambiar_rol_miembro(request, proyecto_id, usuario_id):
    """Vista para cambiar el rol de un miembro del proyecto"""
    
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Petición no válida'}, status=400)
    
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
        
        # Verificar permisos (solo dueño puede cambiar roles)
        usuario_proyecto_gestor = UsuarioProyecto.objects.filter(
            usuario=request.user,
            proyecto=proyecto,
            rol_proyecto='DUEÑO'
        ).first()
        
        if not usuario_proyecto_gestor and not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'message': 'No tienes permisos para cambiar roles.'
            }, status=403)
        
        # Obtener el miembro a modificar
        miembro = get_object_or_404(
            UsuarioProyecto,
            proyecto=proyecto,
            usuario_id=usuario_id
        )
        
        # No permitir cambiar el rol del dueño
        if miembro.rol_proyecto == 'DUEÑO':
            return JsonResponse({
                'success': False,
                'message': 'No se puede cambiar el rol del dueño del proyecto.'
            }, status=400)
        
        # Obtener el nuevo rol
        data = json.loads(request.body)
        nuevo_rol = data.get('rol')
        
        if nuevo_rol not in ['SUPERVISOR', 'COLABORADOR']:
            return JsonResponse({
                'success': False,
                'message': 'Rol no válido.'
            }, status=400)
        
        # Actualizar el rol
        rol_anterior = miembro.get_rol_proyecto_display()
        miembro.rol_proyecto = nuevo_rol
        miembro.puede_invitar = (nuevo_rol in ['SUPERVISOR'])
        miembro.save()
        
        # Crear notificación
        crear_notificacion(
            usuario=miembro.usuario,
            tipo='cambio_rol',
            titulo=f'Cambio de rol - {proyecto.nombre}',
            mensaje=f'Tu rol en el proyecto "{proyecto.nombre}" ha cambiado de {rol_anterior} a {miembro.get_rol_proyecto_display()}.',
            url=reverse('detalle_proyecto', args=[proyecto.id]),
            proyecto=proyecto
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Rol cambiado a {miembro.get_rol_proyecto_display()}',
            'nuevo_rol': miembro.get_rol_proyecto_display(),
            'puede_invitar': miembro.puede_invitar
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al cambiar el rol: {str(e)}'
        }, status=500)


@login_required
@require_POST
def eliminar_miembro(request, proyecto_id, usuario_id):
    """Vista para eliminar un miembro del proyecto"""
    
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Petición no válida'}, status=400)
    
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
        
        # Verificar permisos (dueño o supervisor pueden eliminar)
        usuario_proyecto_gestor = UsuarioProyecto.objects.filter(
            usuario=request.user,
            proyecto=proyecto,
            rol_proyecto__in=['DUEÑO', 'SUPERVISOR']
        ).first()
        
        if not usuario_proyecto_gestor and not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'message': 'No tienes permisos para eliminar miembros.'
            }, status=403)
        
        # Obtener el miembro a eliminar
        miembro = get_object_or_404(
            UsuarioProyecto,
            proyecto=proyecto,
            usuario_id=usuario_id
        )
        
        # No permitir eliminar al dueño
        if miembro.rol_proyecto == 'DUEÑO':
            return JsonResponse({
                'success': False,
                'message': 'No se puede eliminar al dueño del proyecto.'
            }, status=400)
        
        # No permitirse eliminar a sí mismo
        if miembro.usuario == request.user:
            return JsonResponse({
                'success': False,
                'message': 'No puedes eliminarte a ti mismo. Usa la opción "Abandonar proyecto".'
            }, status=400)
        
        # Guardar datos antes de eliminar
        nombre_usuario = miembro.usuario.get_full_name() or miembro.usuario.username
        usuario_eliminado = miembro.usuario
        
        # Eliminar el miembro
        miembro.delete()
        
        # Crear notificación
        crear_notificacion(
            usuario=usuario_eliminado,
            tipo='general',
            titulo=f'Removido del proyecto - {proyecto.nombre}',
            mensaje=f'Has sido removido del proyecto "{proyecto.nombre}".',
            url=reverse('buscar_proyectos'),
            proyecto=None
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{nombre_usuario} ha sido eliminado del proyecto.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al eliminar el miembro: {str(e)}'
        }, status=500)
@login_required
@require_POST
def abandonar_proyecto(request, proyecto_id):
    """Vista para que un usuario abandone voluntariamente un proyecto"""
    
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Petición no válida'}, status=400)
    
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
        
        # Obtener la membresía del usuario
        miembro = UsuarioProyecto.objects.filter(
            usuario=request.user,
            proyecto=proyecto
        ).first()
        
        if not miembro:
            return JsonResponse({
                'success': False,
                'message': 'No eres miembro de este proyecto.'
            }, status=400)
        
        # El dueño no puede abandonar su propio proyecto
        if miembro.rol_proyecto == 'DUEÑO':
            return JsonResponse({
                'success': False,
                'message': 'No puedes abandonar un proyecto del que eres dueño. Debes transferir la propiedad primero o eliminar el proyecto.'
            }, status=400)
        
        # Guardar datos antes de eliminar
        nombre_proyecto = proyecto.nombre
        nombre_usuario = request.user.get_full_name() or request.user.username
        
        with transaction.atomic():
            # Eliminar la membresía
            miembro.delete()
            
            # Notificar al dueño del proyecto (IN-APP)
            try:
                dueno = UsuarioProyecto.objects.get(
                    proyecto=proyecto,
                    rol_proyecto='DUEÑO'
                ).usuario
                
                # Crear notificación in-app
                crear_notificacion(
                    usuario=dueno,
                    tipo='general',
                    titulo=f'Miembro abandonó proyecto - {nombre_proyecto}',
                    mensaje=f'{nombre_usuario} ha abandonado el proyecto "{nombre_proyecto}".',
                    url=reverse('detalle_proyecto', args=[proyecto.id]),
                    proyecto=proyecto
                )
                
                # Enviar email al dueño
                if dueno.email:
                    try:
                        send_mail(
                            f'Miembro abandonó proyecto - {nombre_proyecto}',
                            f"""Hola {dueno.get_full_name() or dueno.username},

Te informamos que {nombre_usuario} ha abandonado el proyecto "{nombre_proyecto}".

Puedes revisar el estado del proyecto aquí:
{request.build_absolute_uri(reverse('detalle_proyecto', args=[proyecto.id]))}

Saludos,
Equipo de Metaanálisis
""",
                            settings.DEFAULT_FROM_EMAIL,
                            [dueno.email],
                            fail_silently=True,
                        )
                    except Exception as e:
                        print(f"Error enviando email: {e}")
                        
            except UsuarioProyecto.DoesNotExist:
                pass
        
        return JsonResponse({
            'success': True,
            'message': f'Has abandonado el proyecto "{nombre_proyecto}".',
            'redirect': reverse('mis_proyectos')
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al abandonar el proyecto: {str(e)}'
        }, status=500)