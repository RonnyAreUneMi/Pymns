from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q
from usuarios.models import Role

# Importar modelos de proyectos si existen en tu app
# Ajusta el import según el nombre de tu app de proyectos
try:
    from pymetanalis.models import Proyecto, UsuarioProyecto, SolicitudProyecto
    PROYECTOS_APP_INSTALLED = True
except ImportError:
    PROYECTOS_APP_INSTALLED = False


def home_view(request):
    """Vista principal del dashboard con datos según el rol del usuario"""
    
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
        
        # ==================== DASHBOARD PARA ADMINISTRADOR ====================
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
        
        # ==================== DASHBOARD PARA INVESTIGADOR ====================
        elif hasattr(request.user, 'profile') and request.user.profile.role and \
             request.user.profile.role.name == 'investigador' and PROYECTOS_APP_INSTALLED:
            
            # Obtener proyectos del usuario
            usuario_proyectos = UsuarioProyecto.objects.filter(
                usuario=request.user
            ).select_related('proyecto')
            
            # ===== ESTADÍSTICAS GENERALES =====
            total_proyectos = usuario_proyectos.count()
            proyectos_dueno = usuario_proyectos.filter(rol_proyecto='DUEÑO').count()
            proyectos_colaborador = usuario_proyectos.filter(
                rol_proyecto__in=['COLABORADOR', 'SUPERVISOR']
            ).count()
            
            # Solicitudes pendientes en proyectos donde es dueño o supervisor
            proyectos_gestion = usuario_proyectos.filter(
                rol_proyecto__in=['DUEÑO', 'SUPERVISOR']
            ).values_list('proyecto_id', flat=True)
            
            solicitudes_pendientes = SolicitudProyecto.objects.filter(
                proyecto_id__in=proyectos_gestion,
                estado='PENDIENTE'
            ).count()
            
            # ===== PROYECTOS RECIENTES (últimos 5) =====
            proyectos_recientes_data = []
            for up in usuario_proyectos.order_by('-fecha_incorporacion')[:5]:
                proyecto = up.proyecto
                progreso = 0
                if proyecto.total_articulos > 0:
                    progreso = round((proyecto.articulos_trabajados / proyecto.total_articulos) * 100, 1)
                
                proyectos_recientes_data.append({
                    'proyecto': proyecto,
                    'rol': up.get_rol_proyecto_display(),
                    'progreso': progreso
                })
            
            # ===== PROYECTOS POR CATEGORÍA =====
            proyectos_ids = usuario_proyectos.values_list('proyecto_id', flat=True)
            proyectos_por_cat = Proyecto.objects.filter(
                id__in=proyectos_ids
            ).values('categoria').annotate(total=Count('id')).order_by('-total')
            
            # Colores para categorías
            colores_categoria = {
                'SALUD': '#10b981',          # green
                'TECNOLOGIA': '#3b82f6',     # blue
                'EDUCACION': '#f59e0b',      # amber
                'PSICOLOGIA': '#8b5cf6',     # violet
                'ECONOMIA': '#ef4444',       # red
                'CIENCIAS_SOCIALES': '#ec4899', # pink
                'INGENIERIA': '#6366f1',     # indigo
                'OTRO': '#6b7280'            # gray
            }
            
            proyectos_por_categoria = []
            total_proyectos_activos = sum([p['total'] for p in proyectos_por_cat])
            
            for cat in proyectos_por_cat:
                categoria_display = dict(Proyecto.CATEGORIA_CHOICES).get(cat['categoria'], cat['categoria'])
                porcentaje = (cat['total'] / total_proyectos_activos * 100) if total_proyectos_activos > 0 else 0
                
                proyectos_por_categoria.append({
                    'nombre': categoria_display,
                    'total': cat['total'],
                    'porcentaje': round(porcentaje, 1),
                    'color': colores_categoria.get(cat['categoria'], '#6b7280')
                })
            
            # ===== PROYECTOS POR ESTADO =====
            proyectos_por_est = Proyecto.objects.filter(
                id__in=proyectos_ids
            ).values('estado').annotate(total=Count('id')).order_by('-total')
            
            colores_estado = {
                'ACTIVO': '#10b981',      # green
                'PAUSADO': '#f59e0b',     # amber
                'FINALIZADO': '#6b7280',  # gray
                'ARCHIVADO': '#ef4444'    # red
            }
            
            proyectos_por_estado = []
            for est in proyectos_por_est:
                estado_display = dict(Proyecto.ESTADO_CHOICES).get(est['estado'], est['estado'])
                porcentaje = (est['total'] / total_proyectos_activos * 100) if total_proyectos_activos > 0 else 0
                
                proyectos_por_estado.append({
                    'nombre': estado_display,
                    'total': est['total'],
                    'porcentaje': round(porcentaje, 1),
                    'color': colores_estado.get(est['estado'], '#6b7280')
                })
            
            # Agregar todo al contexto
            context.update({
                'total_proyectos': total_proyectos,
                'proyectos_dueno': proyectos_dueno,
                'proyectos_colaborador': proyectos_colaborador,
                'solicitudes_pendientes': solicitudes_pendientes,
                'proyectos_recientes': proyectos_recientes_data,
                'proyectos_por_categoria': proyectos_por_categoria,
                'proyectos_por_estado': proyectos_por_estado,
            })
    
    return render(request, 'home.html', context)