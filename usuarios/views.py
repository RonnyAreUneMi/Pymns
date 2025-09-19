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
def seguridad_accesos_view(request):
    # Verificar que el usuario sea administrador
    if not (hasattr(request.user, 'profile') and request.user.profile.role and request.user.profile.role.name == 'administrador'):
        messages.error(request, 'No tienes permisos para acceder a esta sección.')
        return redirect('home')
    
    context = {
        'title': 'Seguridad y Accesos',
        'message': 'Esta sección estará disponible próximamente.'
    }
    
    return render(request, 'usuarios/seguridad_accesos.html', context)