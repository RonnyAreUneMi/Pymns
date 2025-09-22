from django.shortcuts import render
from django.contrib.auth.models import User
from usuarios.models import Role

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