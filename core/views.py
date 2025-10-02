from django.shortcuts import render
from django.contrib.auth.models import User
from usuarios.models import Role

def home_view(request):
    context = {
        'total_usuarios': 0,
        'total_roles': 0,
        'total_articulos': 0,
        'total_analisis': 0,
        'revisiones_pendientes': 0,
    }
    
    # Si el usuario está autenticado
    if request.user.is_authenticated:
        # Verificar si es superusuario o administrador
        is_admin = request.user.is_superuser
        
        if hasattr(request.user, 'profile') and request.user.profile.role:
            is_admin = is_admin or request.user.profile.role.name == 'administrador'
        
        # Si es administrador, agregar estadísticas
        if is_admin:
            context['total_usuarios'] = User.objects.count()
            context['total_roles'] = Role.objects.count()
            
            # Aquí puedes agregar más estadísticas cuando tengas los modelos
            # context['total_articulos'] = Article.objects.count()
            # context['total_analisis'] = Analysis.objects.count()
            # context['revisiones_pendientes'] = Review.objects.filter(status='pending').count()
            
            # Por ahora, usar valores de ejemplo
            context['total_articulos'] = 89
            context['total_analisis'] = 34
            context['revisiones_pendientes'] = 12
    
    return render(request, 'home.html', context)