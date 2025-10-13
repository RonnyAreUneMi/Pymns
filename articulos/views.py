# ARTICULOS VIEWS CON SISTEMA DE NOTIFICACIONES INTEGRADO
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Prefetch
from django.contrib.auth.models import User
from django.urls import reverse
import bibtexparser
from bibtexparser.bparser import BibTexParser
import json

from .models import (
    Articulo, ArchivoSubida, HistorialArticulo,
    CampoMetanalisis, AsignacionCampo, PlantillaBusqueda
)
from pymetanalis.models import Proyecto, UsuarioProyecto, Notificacion


# ==================== FUNCIÓN HELPER PARA NOTIFICACIONES ====================

def crear_notificacion_articulos(usuario, tipo, titulo, mensaje, url=None, proyecto=None):
    """Helper para crear notificaciones relacionadas con artículos"""
    try:
        Notificacion.objects.create(
            usuario=usuario,
            tipo=tipo,
            titulo=titulo,
            mensaje=mensaje,
            url=url,
            proyecto=proyecto
        )
    except Exception as e:
        print(f"Error creando notificación: {e}")


# ==================== VISUALIZACIÓN DE ARTÍCULOS ====================

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q
from pymetanalis.models import Proyecto, UsuarioProyecto
from .models import Articulo

@login_required
def ver_articulos(request, proyecto_id):
    """Vista para ver los artículos de un proyecto."""
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    except (Proyecto.DoesNotExist, ValueError):
        messages.error(request, 'Proyecto no encontrado.')
        return redirect('mis_proyectos')

    # Verificar rol del usuario
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes acceso a este proyecto.')
        return redirect('mis_proyectos')
    
    # Guardar proyecto actual en sesión
    request.session['proyecto_actual_id'] = proyecto.id
    request.session.modified = True

    # Limpiar sesión de archivos subidos
    if 'archivos_sesion' in request.session:
        try:
            del request.session['archivos_sesion']
        except KeyError:
            pass

    # Obtener todos los artículos del proyecto
    articulos = Articulo.objects.filter(proyecto=proyecto).order_by('-fecha_carga')
    
    # Separar artículos con y sin archivo BIB
    articulos_con_bib = articulos.filter(archivo_bib__isnull=False).exclude(archivo_bib='')
    articulos_sin_bib = articulos.filter(Q(archivo_bib__isnull=True) | Q(archivo_bib=''))
    
    # Calcular estadísticas por estado
    total_articulos = articulos.count()
    articulos_en_espera = articulos.filter(estado='EN_ESPERA').count()
    articulos_pendientes = articulos.filter(estado='PENDIENTE').count()
    articulos_en_proceso = articulos.filter(estado='EN_PROCESO').count()
    articulos_en_revision = articulos.filter(estado='EN_REVISION').count()
    articulos_aprobados = articulos.filter(estado='APROBADO').count()

    context = {
        'proyecto': proyecto,
        'articulos': articulos,  # Todos los artículos para el regroup
        'articulos_con_bib': articulos_con_bib,
        'articulos_sin_bib': articulos_sin_bib,
        'usuario_proyecto': usuario_proyecto,
        # Estadísticas
        'total_articulos': total_articulos,
        'articulos_en_espera': articulos_en_espera,
        'articulos_pendientes': articulos_pendientes,
        'articulos_en_proceso': articulos_en_proceso,
        'articulos_en_revision': articulos_en_revision,
        'articulos_aprobados': articulos_aprobados,
    }

    return render(request, 'ver_articulos.html', context)

@login_required
def visualizar_articulos(request, archivo_id):
    """Vista para mostrar todos los artículos de un archivo .bib subido"""
    archivo = get_object_or_404(ArchivoSubida, id=archivo_id)
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=archivo.proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes acceso a este proyecto.')
        return redirect('mis_proyectos')
    
    # Obtener todos los artículos asociados a este archivo específico
    articulos = Articulo.objects.filter(
        proyecto=archivo.proyecto,
        archivo_bib=archivo.nombre_archivo
    ).order_by('-fecha_carga')
    
    return render(request, 'visualizar_articulos.html', {
        'archivo': archivo,
        'articulos': articulos,
        'proyecto': archivo.proyecto
    })


# ==================== DESCARGAS ====================

@login_required
def descargar_articulo(request, articulo_id):
    """Vista para descargar el BibTeX de un artículo individual."""
    articulo = get_object_or_404(Articulo, id=articulo_id)
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=articulo.proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permiso para acceder a este artículo.')
        return redirect('mis_proyectos')
    
    # Crear contenido BibTeX
    bibtex_content = articulo.bibtex_original
    
    # Crear respuesta HTTP
    response = HttpResponse(bibtex_content, content_type='application/x-bibtex')
    nombre_archivo = f"{articulo.bibtex_key}.bib"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    
    # Registrar descarga en historial
    HistorialArticulo.objects.create(
        articulo=articulo,
        usuario=request.user,
        tipo_cambio='DESCARGA',
        valor_nuevo=f'Archivo BibTeX descargado'
    )
    
    return response


@login_required
def descargar_archivo_bib(request, archivo_nombre):
    """Vista para descargar un archivo .bib completo con todos sus artículos."""
    proyecto_id = request.GET.get('proyecto_id')
    
    if not proyecto_id:
        messages.error(request, 'Proyecto no especificado.')
        return redirect('mis_proyectos')
    
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    except (Proyecto.DoesNotExist, ValueError):
        messages.error(request, 'Proyecto no encontrado.')
        return redirect('mis_proyectos')
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permiso para acceder a este proyecto.')
        return redirect('mis_proyectos')
    
    # Obtener artículos del archivo
    articulos = Articulo.objects.filter(
        proyecto=proyecto,
        archivo_bib=archivo_nombre
    ).order_by('bibtex_key')
    
    if not articulos.exists():
        messages.error(request, 'No se encontraron artículos para este archivo.')
        return redirect('articulos:ver_articulos', proyecto_id=proyecto.id)
    
    # Generar contenido BibTeX completo
    bibtex_content = ""
    for articulo in articulos:
        bibtex_content += articulo.bibtex_original + "\n\n"
    
    # Crear respuesta HTTP
    response = HttpResponse(bibtex_content, content_type='application/x-bibtex')
    response['Content-Disposition'] = f'attachment; filename="{archivo_nombre}"'
    
    return response


# ==================== GESTIÓN DE ARTÍCULOS ====================

@login_required
def agregar_articulo(request, proyecto_id):
    """Vista para agregar un nuevo artículo al proyecto."""
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    except (Proyecto.DoesNotExist, ValueError):
        messages.error(request, 'Proyecto no encontrado.')
        return redirect('mis_proyectos')
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permiso para agregar artículos a este proyecto.')
        return redirect('mis_proyectos')
    
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        if titulo:
            articulo = Articulo.objects.create(
                proyecto=proyecto,
                usuario_carga=request.user,
                titulo=titulo,
                bibtex_key=f"{titulo[:20]}_{timezone.now().timestamp()}",
                bibtex_original="@article{...}",
                archivo_bib=None
            )
            
            # 🔔 NOTIFICAR AL DUEÑO (si no es él quien lo agregó)
            try:
                dueno = UsuarioProyecto.objects.get(
                    proyecto=proyecto,
                    rol_proyecto='DUEÑO'
                ).usuario
                
                if dueno != request.user:
                    crear_notificacion_articulos(
                        usuario=dueno,
                        tipo='general',
                        titulo=f'Nuevo artículo agregado - {proyecto.nombre}',
                        mensaje=f'{request.user.get_full_name() or request.user.username} agregó el artículo "{titulo[:50]}" al proyecto.',
                        url=reverse('articulos:ver_articulos', args=[proyecto.id]),
                        proyecto=proyecto
                    )
            except UsuarioProyecto.DoesNotExist:
                pass
            
            messages.success(request, 'Artículo agregado correctamente.')
            return redirect('articulos:ver_articulos', proyecto_id=proyecto.id)
    
    return render(request, 'indv_articulo.html', {'proyecto': proyecto})


@login_required
def eliminar_articulo(request, articulo_id):
    """Vista para eliminar un artículo."""
    if request.method != 'POST':
        messages.error(request, 'Método no permitido.')
        return redirect('mis_proyectos')
    
    articulo = get_object_or_404(Articulo, id=articulo_id)
    proyecto_id = articulo.proyecto.id
    proyecto = articulo.proyecto

    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permiso para eliminar este artículo.')
        return redirect('mis_proyectos')

    # Guardar información antes de eliminar
    titulo_articulo = articulo.titulo
    bibtex_key = articulo.bibtex_key
    usuario_asignado = articulo.usuario_asignado

    # Registrar en historial antes de eliminar
    HistorialArticulo.objects.create(
        articulo=articulo,
        usuario=request.user,
        tipo_cambio='ELIMINACION',
        valor_anterior=titulo_articulo,
        valor_nuevo=f'Artículo eliminado por {request.user.get_full_name() or request.user.username}'
    )

    # 🔔 NOTIFICAR al usuario asignado (si existe y no es quien elimina)
    if usuario_asignado and usuario_asignado != request.user:
        crear_notificacion_articulos(
            usuario=usuario_asignado,
            tipo='general',
            titulo=f'Artículo eliminado - {proyecto.nombre}',
            mensaje=f'El artículo "{titulo_articulo[:50]}" que tenías asignado fue eliminado del proyecto.',
            url=reverse('articulos:ver_articulos', args=[proyecto_id]),
            proyecto=proyecto
        )

    # Eliminar el artículo
    articulo.delete()

    messages.success(request, f'Artículo "{titulo_articulo}" eliminado correctamente.')
    return redirect('articulos:ver_articulos', proyecto_id=proyecto_id)


# ==================== SUBIR ARCHIVOS .BIB ====================

@login_required
def subir_archivo(request, proyecto_id):
    try:
        proyecto = Proyecto.objects.get(id=proyecto_id)
    except (Proyecto.DoesNotExist, ValueError):
        messages.error(request, "El proyecto no existe.")
        return redirect('mis_proyectos')
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes acceso a este proyecto.')
        return redirect('mis_proyectos')
    
    # Guardar proyecto actual en sesión
    request.session['proyecto_actual_id'] = proyecto.id
    
    # Inicializar lista de archivos de la sesión
    if 'archivos_sesion' not in request.session or request.session['archivos_sesion'] is None:
        request.session['archivos_sesion'] = []
        request.session.modified = True
    
    if request.method == 'POST':
        archivo = request.FILES.get('archivo')

        if not archivo:
            messages.error(request, "Debes seleccionar un archivo .bib")
        elif not archivo.name.endswith('.bib'):
            messages.error(request, "Solo se permiten archivos con extensión .bib")
        else:
            # Guardar archivo
            nuevo_archivo = ArchivoSubida(
                proyecto=proyecto,
                usuario=request.user,
                nombre_archivo=archivo.name,
                ruta_archivo=archivo
            )
            nuevo_archivo.save()

            cantidad_articulos_procesados = 0
            errores = []

            try:
                # Configurar parser
                parser = BibTexParser(common_strings=True)
                parser.ignore_nonstandard_types = False
                parser.homogenize_fields = True
                
                # Leer archivo con múltiples encodings
                contenido = None
                for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                    try:
                        nuevo_archivo.ruta_archivo.open('rb')
                        contenido_bytes = nuevo_archivo.ruta_archivo.read()
                        nuevo_archivo.ruta_archivo.close()
                        contenido = contenido_bytes.decode(encoding)
                        break
                    except (UnicodeDecodeError, AttributeError):
                        continue
                
                if not contenido:
                    raise Exception("No se pudo leer el archivo con ningún encoding soportado")
                
                # Parsear contenido
                bib_database = bibtexparser.loads(contenido, parser=parser)
                
                if not bib_database.entries:
                    errores.append({'error': 'No se encontraron entradas válidas en el archivo .bib'})
                
                for entry in bib_database.entries:
                    try:
                        bibtex_key = entry.get('ID', '')
                        
                        if not bibtex_key:
                            errores.append({
                                'entry': 'Sin ID',
                                'error': 'La entrada no tiene un ID válido'
                            })
                            continue
                        
                        # Verificar duplicados
                        if Articulo.objects.filter(
                            bibtex_key=bibtex_key,
                            proyecto=proyecto
                        ).exists():
                            errores.append({
                                'entry': bibtex_key,
                                'error': 'Ya existe un artículo con esta clave en este proyecto'
                            })
                            continue
                        
                        # Crear string BibTeX
                        entry_type = entry.get('ENTRYTYPE', 'article').upper()
                        bibtex_str = f"@{entry_type}{{{bibtex_key},\n"
                        
                        for key, value in entry.items():
                            if key not in ['ENTRYTYPE', 'ID']:
                                value_clean = str(value).strip()
                                bibtex_str += f"  {key} = {{{value_clean}}},\n"
                        bibtex_str += "}"
                        
                        # Extraer título
                        titulo = entry.get('title', 'Sin título')
                        if isinstance(titulo, str):
                            titulo = titulo.strip()
                        
                        # Crear artículo
                        articulo = Articulo(
                            proyecto=proyecto,
                            usuario_carga=request.user,
                            bibtex_key=bibtex_key,
                            titulo=titulo[:500],
                            doi=entry.get('doi', None),
                            bibtex_original=bibtex_str,
                            metadata_completos=entry,
                            archivo_bib=archivo.name
                        )
                        articulo.save()
                        cantidad_articulos_procesados += 1
                        
                    except Exception as e:
                        error_msg = str(e)
                        errores.append({
                            'entry': entry.get('ID', 'desconocido'),
                            'error': error_msg
                        })
                        
            except Exception as e:
                error_msg = str(e)
                errores.append({'error': f'Error al procesar archivo: {error_msg}'})

            # Guardar resultados
            nuevo_archivo.articulos_procesados = cantidad_articulos_procesados
            if errores:
                nuevo_archivo.errores_procesamiento = errores
            nuevo_archivo.save()
            
            # Agregar a sesión
            archivos_sesion = request.session.get('archivos_sesion', [])
            archivos_sesion.append(nuevo_archivo.id)
            request.session['archivos_sesion'] = archivos_sesion
            request.session.modified = True
            
            # 🔔 NOTIFICAR AL DUEÑO sobre la carga del archivo
            if cantidad_articulos_procesados > 0:
                try:
                    dueno = UsuarioProyecto.objects.get(
                        proyecto=proyecto,
                        rol_proyecto='DUEÑO'
                    ).usuario
                    
                    if dueno != request.user:
                        crear_notificacion_articulos(
                            usuario=dueno,
                            tipo='general',
                            titulo=f'Archivo .bib subido - {proyecto.nombre}',
                            mensaje=f'{request.user.get_full_name() or request.user.username} subió el archivo "{archivo.name}" con {cantidad_articulos_procesados} artículos al proyecto.',
                            url=reverse('articulos:ver_articulos', args=[proyecto.id]),
                            proyecto=proyecto
                        )
                except UsuarioProyecto.DoesNotExist:
                    pass
            
            # Mensajes al usuario
            if cantidad_articulos_procesados > 0:
                messages.success(
                    request, 
                    f"Archivo '{archivo.name}' subido correctamente ✅. Artículos procesados: {cantidad_articulos_procesados}"
                )
            else:
                messages.warning(
                    request,
                    f"Archivo subido pero no se procesaron artículos. Revisa el formato del archivo."
                )
            
            if errores:
                messages.warning(request, f"Se encontraron {len(errores)} errores durante el procesamiento.")
            
            return redirect('articulos:subir_archivo', proyecto_id=proyecto_id)

    # GET: Mostrar formulario
    archivos_ids = request.session.get('archivos_sesion', [])
    archivos = ArchivoSubida.objects.filter(id__in=archivos_ids).order_by('-fecha_subida')
    
    return render(request, 'subir.html', {
        'proyecto_id': proyecto_id,
        'proyecto': proyecto,
        'archivos': archivos
    })


# ==================== GESTIÓN DE CAMPOS DE METAANÁLISIS ====================

@login_required
def gestionar_campos(request, proyecto_id):
    """Vista para que el Dueño gestione los campos de búsqueda disponibles"""
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar que es Dueño
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        rol_proyecto='DUEÑO'
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'Solo el Dueño del proyecto puede gestionar campos.')
        return redirect('detalle_proyecto', proyecto_id=proyecto_id)
    
    # Obtener campos
    campos_globales = CampoMetanalisis.objects.filter(
        proyecto__isnull=True,
        activo=True
    ).order_by('categoria', 'nombre')
    
    campos_personalizados = CampoMetanalisis.objects.filter(
        proyecto=proyecto,
        activo=True
    ).order_by('categoria', 'nombre')
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        codigo = request.POST.get('codigo')
        categoria = request.POST.get('categoria')
        tipo_dato = request.POST.get('tipo_dato')
        descripcion = request.POST.get('descripcion', '')
        opciones = request.POST.get('opciones_validas', '')
        
        # Validar código único
        if CampoMetanalisis.objects.filter(codigo=codigo).exists():
            messages.error(request, f'Ya existe un campo con el código "{codigo}".')
        else:
            # Procesar opciones
            opciones_json = None
            if tipo_dato == 'OPCIONES' and opciones:
                opciones_json = [opt.strip() for opt in opciones.split(',')]
            
            campo = CampoMetanalisis.objects.create(
                nombre=nombre,
                codigo=codigo,
                categoria=categoria,
                tipo_dato=tipo_dato,
                descripcion=descripcion,
                opciones_validas=opciones_json,
                proyecto=proyecto,
                creado_por=request.user,
                es_predefinido=False
            )
            
            # 🔔 NOTIFICAR A SUPERVISORES sobre el nuevo campo
            supervisores = UsuarioProyecto.objects.filter(
                proyecto=proyecto,
                rol_proyecto='SUPERVISOR'
            ).exclude(usuario=request.user)
            
            for sup in supervisores:
                crear_notificacion_articulos(
                    usuario=sup.usuario,
                    tipo='general',
                    titulo=f'Nuevo campo creado - {proyecto.nombre}',
                    mensaje=f'Se creó el campo "{nombre}" ({categoria}) en el proyecto.',
                    url=reverse('articulos:gestionar_campos', args=[proyecto.id]),
                    proyecto=proyecto
                )
            
            messages.success(request, f'Campo "{nombre}" creado exitosamente.')
            return redirect('articulos:gestionar_campos', proyecto_id=proyecto_id)
    
    context = {
        'proyecto': proyecto,
        'campos_globales': campos_globales,
        'campos_personalizados': campos_personalizados,
        'categorias': CampoMetanalisis.CATEGORIA_CHOICES,
        'tipos_dato': CampoMetanalisis.TIPO_DATO_CHOICES,
    }
    
    return render(request, 'gestionar_campos.html', context)


@login_required
def eliminar_campo(request, campo_id):
    """Elimina un campo personalizado (solo si no está en uso)"""
    
    campo = get_object_or_404(CampoMetanalisis, id=campo_id)
    proyecto_id = campo.proyecto.id if campo.proyecto else None
    
    if campo.es_predefinido:
        messages.error(request, 'No se pueden eliminar campos predefinidos del sistema.')
    elif campo.asignaciones.exists():
        messages.error(request, 'No se puede eliminar este campo porque ya está asignado a artículos.')
    else:
        nombre = campo.nombre
        campo.delete()
        messages.success(request, f'Campo "{nombre}" eliminado exitosamente.')
    
    if proyecto_id:
        return redirect('articulos:gestionar_campos', proyecto_id=proyecto_id)
    return redirect('articulos:ver_articulos')


# ==================== ASIGNAR TAREAS ====================

@login_required
def asignar_tareas(request, proyecto_id):
    """Vista principal para asignar tareas (campos de búsqueda) a colaboradores"""
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar que es Dueño
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        rol_proyecto='DUEÑO'
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'Solo el Dueño puede asignar tareas.')
        return redirect('detalle_proyecto', proyecto_id=proyecto_id)
    
    # Obtener colaboradores
    colaboradores = UsuarioProyecto.objects.filter(
        proyecto=proyecto
    ).select_related('usuario').order_by('usuario__username')
    
    # Obtener campos disponibles
    campos_disponibles = CampoMetanalisis.objects.filter(
        Q(proyecto__isnull=True) | Q(proyecto=proyecto),
        activo=True
    ).order_by('categoria', 'nombre')
    
    # Obtener plantillas
    plantillas = PlantillaBusqueda.objects.filter(
        proyecto=proyecto
    ).prefetch_related('campos')
    
    context = {
        'proyecto': proyecto,
        'colaboradores': colaboradores,
        'campos_disponibles': campos_disponibles,
        'plantillas': plantillas,
    }
    
    return render(request, 'asignar_tareas.html', context)


@login_required
def cargar_articulos_usuario(request, proyecto_id, usuario_id):
    """AJAX: Carga los artículos de un usuario específico del proyecto"""
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    usuario = get_object_or_404(User, id=usuario_id)
    
    # Obtener artículos del usuario
    articulos = Articulo.objects.filter(
        Q(proyecto=proyecto),
        Q(usuario_asignado=usuario) | Q(usuario_carga=usuario),
        estado__in=['EN_ESPERA', 'PENDIENTE']
    ).prefetch_related(
        Prefetch(
            'campos_asignados',
            queryset=AsignacionCampo.objects.select_related('campo')
        )
    ).order_by('-fecha_carga')
    
    articulos_data = []
    for art in articulos:
        campos_asignados = [
            {
                'id': ca.campo.id,
                'nombre': ca.campo.nombre,
                'completado': ca.completado
            }
            for ca in art.campos_asignados.all()
        ]
        
        articulos_data.append({
            'id': art.id,
            'titulo': art.titulo,
            'estado': art.estado,
            'estado_display': art.get_estado_display(),
            'fecha_carga': art.fecha_carga.strftime('%d/%m/%Y'),
            'campos_asignados': campos_asignados,
            'tiene_campos': len(campos_asignados) > 0
        })
    
    return JsonResponse({'articulos': articulos_data})


@login_required
def asignar_campos_articulos(request, proyecto_id):
    """Asigna campos de búsqueda a artículos específicos"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar rol
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        rol_proyecto='DUEÑO'
    ).first()
    
    if not usuario_proyecto:
        return JsonResponse({'success': False, 'error': 'No tienes permisos'}, status=403)
    
    try:
        data = json.loads(request.body)
        articulos_ids = data.get('articulos_ids', [])
        campos_ids = data.get('campos_ids', [])
        usar_plantilla = data.get('usar_plantilla', False)
        plantilla_id = data.get('plantilla_id')
        
        if not articulos_ids:
            return JsonResponse({'success': False, 'error': 'Debes seleccionar al menos un artículo'})
        
        # Si usa plantilla
        if usar_plantilla and plantilla_id:
            plantilla = get_object_or_404(PlantillaBusqueda, id=plantilla_id, proyecto=proyecto)
            campos = plantilla.campos.all()
            nombre_campos = f'plantilla "{plantilla.nombre}"'
        else:
            if not campos_ids:
                return JsonResponse({'success': False, 'error': 'Debes seleccionar al menos un campo'})
            campos = CampoMetanalisis.objects.filter(id__in=campos_ids, activo=True)
            nombre_campos = f"{len(campos)} campo(s)"
        
        # Asignar campos
        asignaciones_creadas = 0
        articulos_actualizados = []
        
        # Diccionario para agrupar artículos por usuario responsable
        usuarios_articulos = {}
        
        for articulo_id in articulos_ids:
            articulo = get_object_or_404(Articulo, id=articulo_id, proyecto=proyecto)
            
            # Asignar cada campo
            for campo in campos:
                asignacion, created = AsignacionCampo.objects.get_or_create(
                    articulo=articulo,
                    campo=campo,
                    defaults={'asignado_por': request.user}
                )
                if created:
                    asignaciones_creadas += 1
            
            # Cambiar estado si está EN_ESPERA
            if articulo.estado == 'EN_ESPERA':
                articulo.cambiar_estado('PENDIENTE', usuario=request.user)
                articulos_actualizados.append(articulo.titulo[:30])
            
            # 🔑 Determinar usuario responsable
            # Prioridad: usuario_asignado > usuario_carga
            usuario_responsable = articulo.usuario_asignado if articulo.usuario_asignado else articulo.usuario_carga
            
            if usuario_responsable and usuario_responsable.id != request.user.id:
                if usuario_responsable.id not in usuarios_articulos:
                    usuarios_articulos[usuario_responsable.id] = {
                        'usuario': usuario_responsable,
                        'cantidad': 0,
                        'articulos_titulos': []
                    }
                usuarios_articulos[usuario_responsable.id]['cantidad'] += 1
                usuarios_articulos[usuario_responsable.id]['articulos_titulos'].append(articulo.titulo[:50])
        
        # 🔔 NOTIFICAR a cada usuario responsable
        usuarios_notificados = 0
        for user_id, info in usuarios_articulos.items():
            usuario = info['usuario']
            cantidad = info['cantidad']
            
            # Construir mensaje personalizado
            if cantidad == 1:
                mensaje = (
                    f'{request.user.get_full_name() or request.user.username} te ha asignado '
                    f'nuevas tareas en 1 artículo del proyecto "{proyecto.nombre}". '
                    f'Haz clic para revisar tus tareas pendientes.'
                )
                titulo = f'📋 Nueva tarea asignada - {proyecto.nombre}'
            else:
                mensaje = (
                    f'{request.user.get_full_name() or request.user.username} te ha asignado '
                    f'nuevas tareas en {cantidad} artículos del proyecto "{proyecto.nombre}". '
                    f'Haz clic para revisar tus tareas pendientes.'
                )
                titulo = f'📋 {cantidad} nuevas tareas asignadas - {proyecto.nombre}'
            
            # Crear notificación
            crear_notificacion_articulos(
                usuario=usuario,
                tipo='tarea_asignada',  # ⭐ Tipo específico
                titulo=titulo,
                mensaje=mensaje,
                url=reverse('articulos:ver_articulos', args=[proyecto.id]),
                proyecto=proyecto
            )
            usuarios_notificados += 1
            
            print(f"✅ Notificación enviada a {usuario.username}: {cantidad} artículo(s)")
        
        # Construir mensaje de respuesta
        mensaje_respuesta = f'Se asignaron {asignaciones_creadas} campos a {len(articulos_ids)} artículo(s).'
        if articulos_actualizados:
            mensaje_respuesta += f' {len(articulos_actualizados)} artículo(s) pasaron a estado PENDIENTE.'
        if usuarios_notificados > 0:
            mensaje_respuesta += f' Se notificó a {usuarios_notificados} usuario(s).'
        
        print(f"📊 Resumen: {asignaciones_creadas} asignaciones | {usuarios_notificados} usuarios notificados")
        
        return JsonResponse({
            'success': True,
            'mensaje': mensaje_respuesta,
            'asignaciones_creadas': asignaciones_creadas,
            'articulos_actualizados': len(articulos_actualizados),
            'usuarios_notificados': usuarios_notificados
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Error al procesar datos'}, status=400)
    except Exception as e:
        import traceback
        print(f"❌ Error en asignar_campos_articulos: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
# ==================== PLANTILLAS DE BÚSQUEDA ====================

@login_required
def gestionar_plantillas(request, proyecto_id):
    """Gestión de plantillas de búsqueda"""
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar rol
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        rol_proyecto__in=['DUEÑO', 'SUPERVISOR']
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permisos para gestionar plantillas.')
        return redirect('detalle_proyecto', proyecto_id=proyecto_id)
    
    plantillas = PlantillaBusqueda.objects.filter(
        proyecto=proyecto
    ).prefetch_related('campos').annotate(
        num_campos=Count('campos')
    ).order_by('-es_predeterminada', '-fecha_creacion')
    
    campos_disponibles = CampoMetanalisis.objects.filter(
        Q(proyecto__isnull=True) | Q(proyecto=proyecto),
        activo=True
    ).order_by('categoria', 'nombre')
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion', '')
        campos_ids = request.POST.getlist('campos')
        es_predeterminada = request.POST.get('es_predeterminada') == 'on'
        
        if not nombre or not campos_ids:
            messages.error(request, 'Debes proporcionar un nombre y seleccionar al menos un campo.')
        else:
            # Si marca como predeterminada, desmarcar las demás
            if es_predeterminada:
                PlantillaBusqueda.objects.filter(
                    proyecto=proyecto,
                    es_predeterminada=True
                ).update(es_predeterminada=False)
            
            plantilla = PlantillaBusqueda.objects.create(
                nombre=nombre,
                descripcion=descripcion,
                proyecto=proyecto,
                creado_por=request.user,
                es_predeterminada=es_predeterminada
            )
            
            campos = CampoMetanalisis.objects.filter(id__in=campos_ids)
            plantilla.campos.set(campos)
            
            # 🔔 NOTIFICAR A SUPERVISORES Y COLABORADORES sobre nueva plantilla
            usuarios_a_notificar = UsuarioProyecto.objects.filter(
                proyecto=proyecto,
                rol_proyecto__in=['SUPERVISOR', 'COLABORADOR']
            ).exclude(usuario=request.user)
            
            for up in usuarios_a_notificar:
                crear_notificacion_articulos(
                    usuario=up.usuario,
                    tipo='general',
                    titulo=f'Nueva plantilla creada - {proyecto.nombre}',
                    mensaje=f'Se creó la plantilla "{nombre}" con {len(campos_ids)} campos para el proyecto.',
                    url=reverse('articulos:gestionar_plantillas', args=[proyecto.id]),
                    proyecto=proyecto
                )
            
            messages.success(request, f'Plantilla "{nombre}" creada con {len(campos_ids)} campos.')
            return redirect('articulos:gestionar_plantillas', proyecto_id=proyecto_id)
    
    context = {
        'proyecto': proyecto,
        'plantillas': plantillas,
        'campos_disponibles': campos_disponibles,
    }
    
    return render(request, 'gestionar_plantillas.html', context)


@login_required
def eliminar_plantilla(request, plantilla_id):
    """Elimina una plantilla"""
    
    plantilla = get_object_or_404(PlantillaBusqueda, id=plantilla_id)
    proyecto_id = plantilla.proyecto.id
    proyecto = plantilla.proyecto
    nombre = plantilla.nombre
    
    # 🔔 NOTIFICAR A SUPERVISORES sobre eliminación de plantilla
    supervisores = UsuarioProyecto.objects.filter(
        proyecto=proyecto,
        rol_proyecto='SUPERVISOR'
    ).exclude(usuario=request.user)
    
    for sup in supervisores:
        crear_notificacion_articulos(
            usuario=sup.usuario,
            tipo='general',
            titulo=f'Plantilla eliminada - {proyecto.nombre}',
            mensaje=f'La plantilla "{nombre}" fue eliminada del proyecto.',
            url=reverse('articulos:gestionar_plantillas', args=[proyecto_id]),
            proyecto=proyecto
        )
    
    plantilla.delete()
    messages.success(request, f'Plantilla "{nombre}" eliminada.')
    
    return redirect('articulos:gestionar_plantillas', proyecto_id=proyecto_id)


@login_required
def aplicar_plantilla_masiva(request, proyecto_id):
    """Aplica una plantilla a múltiples artículos de forma masiva"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    try:
        data = json.loads(request.body)
        plantilla_id = data.get('plantilla_id')
        filtro_estado = data.get('filtro_estado', 'EN_ESPERA')
        filtro_usuario = data.get('filtro_usuario')
        
        plantilla = get_object_or_404(PlantillaBusqueda, id=plantilla_id, proyecto=proyecto)
        
        # Construir query
        query = Q(proyecto=proyecto, estado=filtro_estado)
        if filtro_usuario:
            query &= Q(usuario_asignado_id=filtro_usuario)
        
        articulos = Articulo.objects.filter(query)
        
        total_asignaciones = 0
        usuarios_notificados = set()
        
        for articulo in articulos:
            campos_creados = plantilla.aplicar_a_articulo(articulo, request.user)
            total_asignaciones += len(campos_creados)
            
            # Cambiar a PENDIENTE
            if articulo.estado == 'EN_ESPERA':
                articulo.cambiar_estado('PENDIENTE', usuario=request.user)
            
            # 🔔 NOTIFICAR al usuario asignado
            if articulo.usuario_asignado and articulo.usuario_asignado.id not in usuarios_notificados:
                crear_notificacion_articulos(
                    usuario=articulo.usuario_asignado,
                    tipo='general',
                    titulo=f'Plantilla aplicada a tus artículos - {proyecto.nombre}',
                    mensaje=f'Se aplicó la plantilla "{plantilla.nombre}" a tus artículos asignados. Revisa las nuevas tareas.',
                    url=reverse('articulos:ver_articulos', args=[proyecto.id]),
                    proyecto=proyecto
                )
                usuarios_notificados.add(articulo.usuario_asignado.id)
        
        return JsonResponse({
            'success': True,
            'mensaje': f'Plantilla aplicada a {articulos.count()} artículos con {total_asignaciones} asignaciones.',
            'articulos_procesados': articulos.count(),
            'asignaciones_creadas': total_asignaciones
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)