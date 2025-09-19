from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from .forms import CustomUserCreationForm, CustomLoginForm
from .models import Profile, Role
from django.contrib.auth.models import User
import json
from django.db import transaction

def home_view(request):
    context = {}
    
    # Si el usuario está autenticado y es administrador, agregar estadísticas
    if (request.user.is_authenticated and 
        hasattr(request.user, 'profile') and 
        request.user.profile.role and 
        request.user.profile.role.name == 'administrador'):
        
        # Obtener estadísticas reales
        context['total_usuarios'] = User.objects.count()
        context['total_roles'] = Role.objects.count()
        
        # Aquí puedes agregar más estadísticas cuando tengas los modelos correspondientes
        # context['total_articulos'] = Article.objects.count()
        # context['total_analisis'] = Analysis.objects.count()
        # context['revisiones_pendientes'] = Review.objects.filter(status='pending').count()
        
        # Por ahora, usar valores por defecto para las estadísticas que no existen aún
        context.update({
            'total_articulos': 89,
            'total_analisis': 34,
            'revisiones_pendientes': 12,
        })
    
    return render(request, 'home.html', context)

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()  # Esto dispara el signal y crea el perfil automáticamente
            
            messages.success(request, 'Cuenta creada exitosamente. Ahora puedes iniciar sesión.')
            return redirect('login')
        else:
            # Agregar mensajes de error
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')  # Viene como 'username' del form
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'¡Bienvenido {user.get_full_name()}!')
                return redirect('home')
            else:
                messages.error(request, 'Credenciales incorrectas.')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = CustomLoginForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, 'Has cerrado sesión correctamente.')
    return redirect('home')

@login_required 
def usuarios_list_view(request):
    # Verificar que el usuario sea administrador
    if not (hasattr(request.user, 'profile') and 
            request.user.profile.role and 
            request.user.profile.role.name == 'administrador'):
        messages.error(request, 'No tienes permisos para acceder a esta sección.')
        return redirect('home')
    
    # Parámetros de búsqueda y filtros
    search_query = request.GET.get('search', '').strip()
    role_filter = request.GET.get('role', '').strip()
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 10))
    
    # Query base optimizada con select_related y prefetch_related
    usuarios_query = User.objects.select_related('profile', 'profile__role').all()
    
    # Aplicar filtros de búsqueda si existe término de búsqueda
    if search_query:
        # Buscar por nombre, apellido, username, email
        usuarios_query = usuarios_query.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(profile__first_name__icontains=search_query) |
            Q(profile__last_name__icontains=search_query)
        ).distinct()
    
    # Aplicar filtro por rol si se especifica
    if role_filter:
        if role_filter.lower() == 'sin-rol':
            # Filtrar usuarios sin rol
            usuarios_query = usuarios_query.filter(
                Q(profile__role__isnull=True) |
                Q(profile__isnull=True)
            )
        else:
            # Filtrar por rol específico
            try:
                role_obj = Role.objects.get(name__iexact=role_filter)
                usuarios_query = usuarios_query.filter(profile__role=role_obj)
            except Role.DoesNotExist:
                # Si el rol no existe, devolver queryset vacío
                usuarios_query = usuarios_query.none()
    
    # Ordenar por fecha de registro (más recientes primero)
    usuarios_query = usuarios_query.order_by('-date_joined')
    
    # Obtener el conteo total antes de la paginación
    total_usuarios = usuarios_query.count()
    
    # Paginación
    paginator = Paginator(usuarios_query, per_page)
    
    try:
        usuarios_page = paginator.get_page(page)
    except (PageNotAnInteger, EmptyPage):
        usuarios_page = paginator.get_page(1)
    
    # Obtener roles para el selector
    roles = Role.objects.all().order_by('name')
    
    # Contexto para el template
    context = {
        'usuarios': usuarios_page,
        'roles': roles,
        'title': 'Gestión de Usuarios',
        'search_query': search_query,
        'role_filter': role_filter,
        'total_usuarios': User.objects.count(),  # Total real de usuarios en el sistema
        'filtered_count': total_usuarios,  # Cantidad después de filtros
        'per_page': per_page,
        'paginator': paginator,
    }
    
    # Si es una petición AJAX (para búsqueda en tiempo real)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'html': render(request, 'usuarios_list_partial.html', context).content.decode('utf-8'),
            'total_count': context['total_usuarios'],
            'filtered_count': total_usuarios,
            'shown_count': len(usuarios_page),
            'has_next': usuarios_page.has_next(),
            'has_previous': usuarios_page.has_previous(),
            'current_page': usuarios_page.number,
            'total_pages': paginator.num_pages,
        })
    
    return render(request, 'usuarios_list.html', context)

@login_required
@require_http_methods(["POST"])
@csrf_protect
def delete_user_view(request, user_id):
    # Verificar permisos de administrador
    if not (hasattr(request.user, 'profile') and 
            request.user.profile.role and 
            request.user.profile.role.name == 'administrador'):
        return JsonResponse({
            'success': False, 
            'error': 'No tienes permisos para realizar esta acción.'
        }, status=403)
    
    try:
        with transaction.atomic():
            user_to_delete = get_object_or_404(User, id=user_id)
            
            # Validaciones de seguridad
            if user_to_delete == request.user:
                return JsonResponse({
                    'success': False, 
                    'error': 'No puedes eliminarte a ti mismo.'
                }, status=400)
            
            # Verificar si es el único administrador
            admin_role = Role.objects.filter(name='administrador').first()
            if (admin_role and hasattr(user_to_delete, 'profile') and user_to_delete.profile.role == admin_role):
                admin_count = User.objects.filter(
                    profile__role=admin_role
                ).exclude(id=user_id).count()
                
                if admin_count == 0:
                    return JsonResponse({
                        'success': False,
                        'error': 'No puedes eliminar el último administrador del sistema.'
                    }, status=400)
            
            user_name = user_to_delete.get_full_name() or user_to_delete.username
            user_to_delete.delete()
            
            return JsonResponse({
                'success': True, 
                'message': f'Usuario {user_name} eliminado correctamente.'
            })
            
    except User.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': 'Usuario no encontrado.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Error interno del servidor: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_protect
def change_user_role_view(request, user_id):
    # Verificar permisos de administrador
    if not (hasattr(request.user, 'profile') and 
            request.user.profile.role and 
            request.user.profile.role.name == 'administrador'):
        return JsonResponse({
            'success': False, 
            'error': 'No tienes permisos para realizar esta acción.'
        }, status=403)
    
    try:
        with transaction.atomic():
            # Parsear datos JSON
            try:
                data = json.loads(request.body)
                new_role_id = data.get('role_id')
            except json.JSONDecodeError:
                return JsonResponse({
                    'success': False, 
                    'error': 'Datos inválidos.'
                }, status=400)
            
            if not new_role_id:
                return JsonResponse({
                    'success': False, 
                    'error': 'Rol no especificado.'
                }, status=400)
            
            # Obtener objetos
            user_to_change = get_object_or_404(User, id=user_id)
            new_role = get_object_or_404(Role, id=new_role_id)
            
            # Validaciones de seguridad
            admin_role = Role.objects.filter(name='administrador').first()
            
            # No permitir que se quite a sí mismo el rol de administrador
            if (user_to_change == request.user and 
                hasattr(request.user, 'profile') and
                request.user.profile.role == admin_role and 
                new_role != admin_role):
                return JsonResponse({
                    'success': False, 
                    'error': 'No puedes quitarte el rol de administrador a ti mismo.'
                }, status=400)
            
            # Verificar que no sea el último administrador
            if (hasattr(user_to_change, 'profile') and 
                user_to_change.profile.role == admin_role and 
                new_role != admin_role):
                admin_count = User.objects.filter(profile__role=admin_role).count()
                if admin_count <= 1:
                    return JsonResponse({
                        'success': False,
                        'error': 'No puedes quitar el rol de administrador al último administrador del sistema.'
                    }, status=400)
            
            # Actualizar el rol
            if hasattr(user_to_change, 'profile'):
                old_role = user_to_change.profile.role
                user_to_change.profile.role = new_role
                user_to_change.profile.save()
            else:
                # Crear perfil si no existe (caso edge)
                Profile.objects.create(user=user_to_change, role=new_role)
                old_role = None
            
            user_name = user_to_change.get_full_name() or user_to_change.username
            
            return JsonResponse({
                'success': True,
                'message': f'Rol de {user_name} actualizado de {old_role.name if old_role else "sin rol"} a {new_role.name}.',
                'user_id': user_id,
                'new_role': {
                    'id': new_role.id,
                    'name': new_role.name
                }
            })
            
    except User.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': 'Usuario no encontrado.'
        }, status=404)
    except Role.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': 'Rol no encontrado.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Error interno del servidor: {str(e)}'
        }, status=500)

@login_required
def search_users_ajax(request):
    """Vista AJAX optimizada para búsqueda de usuarios en tiempo real"""
    if not (hasattr(request.user, 'profile') and 
            request.user.profile.role and 
            request.user.profile.role.name == 'administrador'):
        return JsonResponse({
            'success': False, 
            'error': 'No tienes permisos.'
        }, status=403)
    
    search_query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 10))
    
    # Query optimizada
    usuarios_query = User.objects.select_related('profile', 'profile__role')
    
    # Aplicar filtros de búsqueda
    if search_query:
        usuarios_query = usuarios_query.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(profile__first_name__icontains=search_query) |
            Q(profile__last_name__icontains=search_query)
        ).distinct()
    
    # Aplicar filtro por rol
    if role_filter:
        if role_filter.lower() == 'sin-rol':
            usuarios_query = usuarios_query.filter(
                Q(profile__role__isnull=True) |
                Q(profile__isnull=True)
            )
        else:
            try:
                role_obj = Role.objects.get(name__iexact=role_filter)
                usuarios_query = usuarios_query.filter(profile__role=role_obj)
            except Role.DoesNotExist:
                usuarios_query = usuarios_query.none()
    
    usuarios_query = usuarios_query.order_by('-date_joined')
    
    # Paginación
    paginator = Paginator(usuarios_query, per_page)
    usuarios_page = paginator.get_page(page)
    
    # Preparar datos para JSON
    usuarios_data = []
    for usuario in usuarios_page:
        usuarios_data.append({
            'id': usuario.id,
            'username': usuario.username,
            'email': usuario.email,
            'first_name': usuario.first_name,
            'last_name': usuario.last_name,
            'full_name': usuario.get_full_name(),
            'date_joined': usuario.date_joined.strftime('%d/%m/%Y'),
            'role': {
                'id': usuario.profile.role.id if usuario.profile.role else None,
                'name': usuario.profile.role.name if usuario.profile.role else 'Sin rol',
            } if hasattr(usuario, 'profile') else None,
            'is_current_user': usuario == request.user,
        })
    
    return JsonResponse({
        'success': True,
        'users': usuarios_data,
        'pagination': {
            'current_page': usuarios_page.number,
            'total_pages': paginator.num_pages,
            'has_next': usuarios_page.has_next(),
            'has_previous': usuarios_page.has_previous(),
            'total_count': paginator.count,
            'start_index': usuarios_page.start_index(),
            'end_index': usuarios_page.end_index(),
        }
    })

@login_required 
def seguridad_accesos_view(request):
    # Verificar que el usuario sea administrador
    if not (hasattr(request.user, 'profile') and 
            request.user.profile.role and 
            request.user.profile.role.name == 'administrador'):
        messages.error(request, 'No tienes permisos para acceder a esta sección.')
        return redirect('home')
    
    context = {
        'title': 'Seguridad y Accesos',
        'message': 'Esta sección estará disponible próximamente.'
    }
    
    return render(request, 'usuarios/seguridad_accesos.html', context)