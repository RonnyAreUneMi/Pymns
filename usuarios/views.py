from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from .forms import CustomUserCreationForm, CustomLoginForm
from .models import Profile, Role
from django.contrib.auth.models import User

def home_view(request):
    return render(request, 'home.html')

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Crear un perfil para el usuario recién registrado
            invitado_role = Role.objects.get(name='invitado')
            Profile.objects.create(user=user, role=invitado_role)
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')
    else:
        form = CustomLoginForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def usuarios_list_view(request):
    # Verificar que el usuario sea administrador - versión mejorada
    try:
        # Verificar si tiene perfil
        if not hasattr(request.user, 'profile'):
            messages.error(request, 'Tu cuenta no tiene un perfil asignado. Contacta al administrador.')
            return redirect('home')
        
        # Verificar si tiene rol
        if not request.user.profile.role:
            messages.error(request, 'Tu cuenta no tiene un rol asignado. Contacta al administrador.')
            return redirect('home')
            
        # Verificar si es administrador
        if request.user.profile.role.name != 'administrador':
            messages.error(request, f'Tu rol actual es "{request.user.profile.role.name}". Solo los administradores pueden acceder a esta sección.')
            return redirect('home')
            
    except Exception as e:
        messages.error(request, f'Error al verificar permisos: {str(e)}')
        return redirect('home')
    
    # Obtener parámetro de búsqueda
    search_query = request.GET.get('search', '')
    
    # Filtrar usuarios
    usuarios = User.objects.select_related('profile', 'profile__role').all()
    
    if search_query:
        usuarios = usuarios.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(username__icontains=search_query)
        )
    
    # Ordenar por fecha de registro (más recientes primero)
    usuarios = usuarios.order_by('-date_joined')
    
    context = {
        'usuarios': usuarios,
        'search_query': search_query,
        'total_usuarios': User.objects.count(),
        'usuarios_activos': User.objects.filter(is_active=True).count(),
    }
    
    return render(request, 'usuarios_list.html', context)

@login_required
def delete_user_view(request, user_id):
    # Verificar que el usuario sea administrador
    if not (hasattr(request.user, 'profile') and request.user.profile.role.name == 'administrador'):
        return JsonResponse({'success': False, 'message': 'No tienes permisos para esta acción.'})
    
    if request.method == 'POST':
        try:
            usuario = get_object_or_404(User, id=user_id)
            
            # No permitir que el admin se elimine a sí mismo
            if usuario == request.user:
                return JsonResponse({'success': False, 'message': 'No puedes eliminar tu propia cuenta.'})
            
            nombre_usuario = usuario.get_full_name() or usuario.username
            usuario.delete()
            
            return JsonResponse({
                'success': True, 
                'message': f'Usuario "{nombre_usuario}" eliminado correctamente.'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': 'Error al eliminar el usuario.'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido.'})

@login_required 
def debug_user_view(request):
    """Vista temporal para debug - ELIMINAR EN PRODUCCIÓN"""
    info = {
        'username': request.user.username,
        'is_superuser': request.user.is_superuser,
        'has_profile': hasattr(request.user, 'profile'),
    }
    
    if hasattr(request.user, 'profile'):
        info['profile_role'] = request.user.profile.role.name if request.user.profile.role else None
    
    # Si es superuser y no tiene perfil, créalo
    if request.user.is_superuser and not hasattr(request.user, 'profile'):
        admin_role, _ = Role.objects.get_or_create(name='administrador')
        Profile.objects.create(user=request.user, role=admin_role)
        info['profile_created'] = True
        info['new_role'] = admin_role.name
    
    return JsonResponse(info)

@login_required 
def seguridad_accesos_view(request):
    # Verificar que el usuario sea administrador
    if not (hasattr(request.user, 'profile') and request.user.profile.role.name == 'administrador'):
        messages.error(request, 'No tienes permisos para acceder a esta sección.')
        return redirect('home')
    
    # TODO: Implementar lógica de seguridad y accesos
    context = {
        'title': 'Seguridad y Accesos',
        'message': 'Esta sección estará disponible próximamente.'
    }
    
    return render(request, 'usuarios/seguridad_accesos.html', context)