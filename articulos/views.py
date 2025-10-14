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
    CampoMetanalisis, AsignacionCampo, PlantillaBusqueda, ComentarioRevision
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
def obtener_campos_asignados(request, proyecto_id):
    """AJAX: Obtiene los campos ya asignados a los artículos seleccionados"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        articulos_ids = data.get('articulos_ids', [])
        
        if not articulos_ids:
            return JsonResponse({'campos_asignados': []})
        
        # Obtener todos los campos asignados a estos artículos
        campos_asignados = AsignacionCampo.objects.filter(
            articulo_id__in=articulos_ids
        ).values('campo_id').annotate(
            cantidad=Count('id')
        ).order_by('-cantidad')
        
        # Obtener información completa de los campos
        campos_ids = [c['campo_id'] for c in campos_asignados]
        campos = CampoMetanalisis.objects.filter(id__in=campos_ids)
        
        campos_data = []
        for campo in campos:
            cantidad = next((c['cantidad'] for c in campos_asignados if c['campo_id'] == campo.id), 0)
            campos_data.append({
                'id': campo.id,
                'nombre': campo.nombre,
                'categoria': campo.get_categoria_display(),
                'cantidad_articulos': cantidad,
                'total_articulos': len(articulos_ids)
            })
        
        return JsonResponse({'campos_asignados': campos_data})
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Error al procesar datos'}, status=400)
    except Exception as e:
        print(f"❌ Error en obtener_campos_asignados: {str(e)}")
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
@login_required
def detalle_plantilla(request, plantilla_id):
    """Devuelve los detalles de una plantilla en formato JSON"""
    
    plantilla = get_object_or_404(PlantillaBusqueda, id=plantilla_id)
    
    # Verificar que el usuario tiene acceso al proyecto
    if not UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=plantilla.proyecto
    ).exists():
        return JsonResponse({
            'success': False,
            'error': 'No tienes acceso a esta plantilla'
        }, status=403)
    
    # Preparar datos de los campos agrupados por categoría
    campos_data = []
    for campo in plantilla.campos.all().order_by('categoria', 'nombre'):
        campos_data.append({
            'id': campo.id,
            'nombre': campo.nombre,
            'descripcion': campo.descripcion or '',
            'categoria': campo.get_categoria_display(),
            'tipo_dato': campo.get_tipo_dato_display(),
            'es_personalizado': campo.proyecto is not None
        })
    
    plantilla_data = {
        'id': plantilla.id,
        'nombre': plantilla.nombre,
        'descripcion': plantilla.descripcion or '',
        'es_predeterminada': plantilla.es_predeterminada,
        'creado_por': plantilla.creado_por.get_full_name() or plantilla.creado_por.username,
        'fecha_creacion': plantilla.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'total_campos': plantilla.campos.count(),
        'campos': campos_data
    }
    
    return JsonResponse({
        'success': True,
        'plantilla': plantilla_data
    })

# ==================== WORKSPACE Y SISTEMA DE REVISIÓN ====================

@login_required
def workspace_articulo(request, articulo_id):
    """
    Workspace principal para trabajar en un artículo.
    Roles:
    - COLABORADOR: Solo sus artículos asignados, envía a revisión
    - SUPERVISOR/DUEÑO: Todos los artículos, puede aprobar directamente
    """
    articulo = get_object_or_404(Articulo, id=articulo_id)
    proyecto = articulo.proyecto
    
    # Verificar acceso al proyecto
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes acceso a este proyecto.')
        return redirect('mis_proyectos')
    
    # Control de acceso por rol
    es_supervisor_o_dueno = usuario_proyecto.rol_proyecto in ['SUPERVISOR', 'DUEÑO']
    
    # COLABORADOR: Solo puede ver artículos que le pertenecen
    if usuario_proyecto.rol_proyecto == 'COLABORADOR':
        if articulo.usuario_asignado != request.user and articulo.usuario_carga != request.user:
            messages.error(request, 'No tienes permiso para acceder a este artículo.')
            return redirect('articulos:ver_articulos', proyecto_id=proyecto.id)
    
    # Verificar estado del artículo
    if articulo.estado == 'EN_ESPERA':
        messages.warning(request, 'Este artículo aún no tiene tareas asignadas.')
        return redirect('articulos:ver_articulos', proyecto_id=proyecto.id)
    
    # Obtener campos asignados con prefetch
    campos_asignados = AsignacionCampo.objects.filter(
        articulo=articulo
    ).select_related('campo', 'asignado_por').order_by('campo__categoria', 'campo__nombre')
    
    # Obtener historial de cambios
    historial = HistorialArticulo.objects.filter(
        articulo=articulo
    ).select_related('usuario').order_by('-fecha_cambio')[:20]
    
    # Obtener comentarios de revisión
    comentarios = ComentarioRevision.objects.filter(
        articulo=articulo
    ).select_related('supervisor', 'colaborador').order_by('-fecha_comentario')
    
    # Calcular progreso
    total_campos = campos_asignados.count()
    campos_completados = campos_asignados.filter(completado=True).count()
    campos_aprobados = campos_asignados.filter(aprobado=True).count()
    progreso_porcentaje = (campos_completados / total_campos * 100) if total_campos > 0 else 0
    progreso_aprobacion = (campos_aprobados / campos_completados * 100) if campos_completados > 0 else 0
    
    context = {
        'articulo': articulo,
        'proyecto': proyecto,
        'usuario_proyecto': usuario_proyecto,
        'es_supervisor_o_dueno': es_supervisor_o_dueno,
        'campos_asignados': campos_asignados,
        'historial': historial,
        'comentarios': comentarios,
        'total_campos': total_campos,
        'campos_completados': campos_completados,
        'campos_aprobados': campos_aprobados,
        'progreso_porcentaje': round(progreso_porcentaje, 1),
        'progreso_aprobacion': round(progreso_aprobacion, 1),
        'puede_editar': articulo.estado not in ['APROBADO'],
        'puede_aprobar': es_supervisor_o_dueno,
        'puede_enviar_revision': articulo.estado in ['PENDIENTE', 'EN_PROCESO'],
    }
    
    return render(request, 'workspace.html', context)


# ==================== GUARDAR CAMPO (AJAX) ====================

@login_required
def guardar_campo_workspace(request, articulo_id):
    """
    Guarda el valor de un campo específico del artículo.
    Cambia automáticamente el estado a EN_PROCESO si estaba PENDIENTE.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    articulo = get_object_or_404(Articulo, id=articulo_id)
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=articulo.proyecto
    ).first()
    
    if not usuario_proyecto:
        return JsonResponse({'success': False, 'error': 'No tienes acceso'}, status=403)
    
    # Verificar que puede editar
    if articulo.estado == 'APROBADO':
        return JsonResponse({'success': False, 'error': 'Este artículo ya fue aprobado'}, status=400)
    
    try:
        data = json.loads(request.body)
        campo_id = data.get('campo_id')
        valor = data.get('valor', '').strip()
        
        # Obtener asignación
        asignacion = get_object_or_404(
            AsignacionCampo,
            articulo=articulo,
            campo_id=campo_id
        )
        
        # 🆕 Verificar si el campo está aprobado
        if asignacion.aprobado:
            return JsonResponse({
                'success': False,
                'error': 'Este campo ya fue aprobado y no puede ser modificado'
            }, status=400)
        
        # Usar el método del modelo para guardar
        asignacion.marcar_completado(valor, usuario=request.user)
        
        # Cambiar estado a EN_PROCESO si estaba PENDIENTE
        if articulo.estado == 'PENDIENTE' and valor:
            articulo.cambiar_estado('EN_PROCESO', usuario=request.user)
            estado_cambiado = True
        else:
            estado_cambiado = False
        
        # Calcular nuevo progreso
        total_campos = articulo.campos_asignados.count()
        campos_completados = articulo.campos_asignados.filter(completado=True).count()
        progreso = (campos_completados / total_campos * 100) if total_campos > 0 else 0
        
        return JsonResponse({
            'success': True,
            'mensaje': 'Campo guardado exitosamente',
            'estado_cambiado': estado_cambiado,
            'nuevo_estado': articulo.get_estado_display(),
            'campos_completados': campos_completados,
            'total_campos': total_campos,
            'progreso_porcentaje': round(progreso, 1)
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Datos inválidos'}, status=400)
    except Exception as e:
        print(f"❌ Error en guardar_campo_workspace: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== APROBACIÓN DE CAMPOS INDIVIDUALES ====================

@login_required
def aprobar_campo_individual(request, asignacion_id):
    """
    Aprueba un campo individual dentro del workspace
    Solo SUPERVISORES y DUEÑOS
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    asignacion = get_object_or_404(AsignacionCampo, id=asignacion_id)
    articulo = asignacion.articulo
    proyecto = articulo.proyecto
    
    # Verificar rol
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        rol_proyecto__in=['SUPERVISOR', 'DUEÑO']
    ).first()
    
    if not usuario_proyecto:
        return JsonResponse({'success': False, 'error': 'No tienes permisos'}, status=403)
    
    # Validar que el campo esté completado
    if not asignacion.completado or not asignacion.valor:
        return JsonResponse({
            'success': False,
            'error': 'Solo puedes aprobar campos que hayan sido completados'
        }, status=400)
    
    try:
        # Aprobar el campo
        asignacion.aprobar_campo(supervisor=request.user)
        
        # Calcular progreso de aprobación
        total_completados = articulo.campos_asignados.filter(completado=True).count()
        total_aprobados = articulo.campos_asignados.filter(aprobado=True).count()
        progreso_aprobacion = round((total_aprobados / total_completados * 100), 1) if total_completados > 0 else 0
        
        # Si todos los campos completados están aprobados, cambiar estado del artículo
        if articulo.puede_aprobar_articulo() and articulo.estado == 'EN_REVISION':
            articulo.cambiar_estado('APROBADO', usuario=request.user)
            articulo_aprobado_completo = True
            
            # 🔔 Notificar al colaborador
            colaborador = articulo.usuario_asignado or articulo.usuario_carga
            if colaborador and colaborador.id != request.user.id:
                crear_notificacion_articulos(
                    usuario=colaborador,
                    tipo='tarea_aprobada',
                    titulo=f'✅ Artículo completamente aprobado - {proyecto.nombre}',
                    mensaje=f'Todos los campos del artículo "{articulo.titulo[:50]}..." han sido aprobados. ¡Excelente trabajo!',
                    url=reverse('articulos:workspace_articulo', args=[articulo.id]),
                    proyecto=proyecto
                )
        else:
            articulo_aprobado_completo = False
        
        return JsonResponse({
            'success': True,
            'mensaje': f'Campo "{asignacion.campo.nombre}" aprobado',
            'campo_aprobado': True,
            'progreso_aprobacion': progreso_aprobacion,
            'total_aprobados': total_aprobados,
            'total_completados': total_completados,
            'articulo_aprobado_completo': articulo_aprobado_completo,
            'nuevo_estado_articulo': articulo.get_estado_display() if articulo_aprobado_completo else None
        })
    
    except Exception as e:
        print(f"❌ Error en aprobar_campo_individual: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def solicitar_correccion_campo(request, asignacion_id):
    """
    Solicita corrección en un campo específico
    Quita la aprobación si ya estaba aprobado
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    asignacion = get_object_or_404(AsignacionCampo, id=asignacion_id)
    articulo = asignacion.articulo
    proyecto = articulo.proyecto
    
    # Verificar rol
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        rol_proyecto__in=['SUPERVISOR', 'DUEÑO']
    ).first()
    
    if not usuario_proyecto:
        return JsonResponse({'success': False, 'error': 'No tienes permisos'}, status=403)
    
    try:
        data = json.loads(request.body)
        comentario = data.get('comentario', '').strip()
        
        if not comentario:
            return JsonResponse({
                'success': False,
                'error': 'Debes proporcionar un comentario'
            }, status=400)
        
        # Quitar aprobación si tenía
        if asignacion.aprobado:
            asignacion.desaprobar_campo(supervisor=request.user, razon=comentario)
        
        # Guardar comentario en el campo de notas
        nota_anterior = asignacion.notas or ""
        nueva_nota = f"[{timezone.now().strftime('%d/%m/%Y %H:%M')}] {request.user.get_full_name() or request.user.username}: {comentario}"
        asignacion.notas = f"{nota_anterior}\n{nueva_nota}" if nota_anterior else nueva_nota
        asignacion.save()
        
        # Crear comentario de revisión general
        colaborador = articulo.usuario_asignado or articulo.usuario_carga
        ComentarioRevision.objects.create(
            articulo=articulo,
            supervisor=request.user,
            colaborador=colaborador,
            comentario=f'Campo "{asignacion.campo.nombre}": {comentario}',
            tipo_accion='CORRECCION'
        )
        
        # Si el artículo estaba APROBADO, volver a EN_REVISION
        if articulo.estado == 'APROBADO':
            articulo.cambiar_estado('EN_REVISION', usuario=request.user)
        
        # 🔔 Notificar al colaborador
        if colaborador and colaborador.id != request.user.id:
            crear_notificacion_articulos(
                usuario=colaborador,
                tipo='tarea_correccion',
                titulo=f'🔄 Corrección solicitada en campo - {proyecto.nombre}',
                mensaje=f'Corrección en "{asignacion.campo.nombre}" del artículo "{articulo.titulo[:50]}...": {comentario[:100]}',
                url=reverse('articulos:workspace_articulo', args=[articulo.id]),
                proyecto=proyecto
            )
        
        return JsonResponse({
            'success': True,
            'mensaje': 'Corrección solicitada exitosamente',
            'campo_desaprobado': True,
            'comentario_agregado': nueva_nota
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Datos inválidos'}, status=400)
    except Exception as e:
        print(f"❌ Error en solicitar_correccion_campo: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== ENVIAR A REVISIÓN ====================

@login_required
def enviar_a_revision(request, articulo_id):
    """
    Envía un artículo a revisión (COLABORADOR)
    Notifica a SUPERVISORES y DUEÑO
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    articulo = get_object_or_404(Articulo, id=articulo_id)
    proyecto = articulo.proyecto
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        return JsonResponse({'success': False, 'error': 'No tienes acceso'}, status=403)
    
    # Validar que puede enviar a revisión
    if articulo.estado not in ['PENDIENTE', 'EN_PROCESO']:
        return JsonResponse({
            'success': False,
            'error': f'No puedes enviar a revisión un artículo en estado {articulo.get_estado_display()}'
        }, status=400)
    
    try:
        # Cambiar estado
        articulo.cambiar_estado('EN_REVISION', usuario=request.user)
        
        # Registrar en historial
        HistorialArticulo.objects.create(
            articulo=articulo,
            usuario=request.user,
            tipo_cambio='ENVIO_REVISION',
            valor_nuevo='Enviado a revisión'
        )
        
        # 🔔 NOTIFICAR A SUPERVISORES Y DUEÑO
        revisores = UsuarioProyecto.objects.filter(
            proyecto=proyecto,
            rol_proyecto__in=['SUPERVISOR', 'DUEÑO']
        ).exclude(usuario=request.user)
        
        usuarios_notificados = 0
        for revisor in revisores:
            crear_notificacion_articulos(
                usuario=revisor.usuario,
                tipo='tarea_revision',
                titulo=f'📝 Artículo enviado a revisión - {proyecto.nombre}',
                mensaje=f'{request.user.get_full_name() or request.user.username} ha enviado el artículo "{articulo.titulo[:50]}..." para tu revisión.',
                url=reverse('articulos:workspace_articulo', args=[articulo.id]),
                proyecto=proyecto
            )
            usuarios_notificados += 1
        
        return JsonResponse({
            'success': True,
            'mensaje': 'Artículo enviado a revisión exitosamente',
            'usuarios_notificados': usuarios_notificados,
            'nuevo_estado': articulo.get_estado_display()
        })
    
    except Exception as e:
        print(f"❌ Error en enviar_a_revision: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def enviar_masivo_revision(request, proyecto_id):
    """
    Permite a un COLABORADOR enviar múltiples artículos a revisión
    de forma masiva usando checkboxes
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        return JsonResponse({'success': False, 'error': 'No tienes acceso'}, status=403)
    
    try:
        data = json.loads(request.body)
        articulos_ids = data.get('articulos_ids', [])
        
        if not articulos_ids:
            return JsonResponse({
                'success': False,
                'error': 'Debes seleccionar al menos un artículo'
            })
        
        # Filtrar artículos que puede enviar
        articulos = Articulo.objects.filter(
            id__in=articulos_ids,
            proyecto=proyecto,
            estado__in=['PENDIENTE', 'EN_PROCESO']
        )
        
        # Si es COLABORADOR, solo sus artículos
        if usuario_proyecto.rol_proyecto == 'COLABORADOR':
            articulos = articulos.filter(
                Q(usuario_asignado=request.user) | Q(usuario_carga=request.user)
            )
        
        articulos_enviados = 0
        
        for articulo in articulos:
            # Cambiar estado
            articulo.cambiar_estado('EN_REVISION', usuario=request.user)
            
            # Registrar en historial
            HistorialArticulo.objects.create(
                articulo=articulo,
                usuario=request.user,
                tipo_cambio='ENVIO_REVISION',
                valor_nuevo='Enviado a revisión masivamente'
            )
            
            articulos_enviados += 1
        
        # 🔔 NOTIFICAR A SUPERVISORES (una sola notificación agrupada)
        if articulos_enviados > 0:
            revisores = UsuarioProyecto.objects.filter(
                proyecto=proyecto,
                rol_proyecto__in=['SUPERVISOR', 'DUEÑO']
            ).exclude(usuario=request.user)
            
            for revisor in revisores:
                if articulos_enviados == 1:
                    mensaje = f'{request.user.get_full_name() or request.user.username} ha enviado 1 artículo para tu revisión.'
                    titulo = f'📝 Artículo enviado a revisión - {proyecto.nombre}'
                else:
                    mensaje = f'{request.user.get_full_name() or request.user.username} ha enviado {articulos_enviados} artículos para tu revisión.'
                    titulo = f'📝 {articulos_enviados} artículos enviados a revisión - {proyecto.nombre}'
                
                crear_notificacion_articulos(
                    usuario=revisor.usuario,
                    tipo='tarea_revision',
                    titulo=titulo,
                    mensaje=mensaje,
                    url=reverse('articulos:bandeja_revision', args=[proyecto.id]),
                    proyecto=proyecto
                )
        
        return JsonResponse({
            'success': True,
            'mensaje': f'Se enviaron {articulos_enviados} artículo(s) a revisión exitosamente',
            'articulos_enviados': articulos_enviados
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Datos inválidos'}, status=400)
    except Exception as e:
        print(f"❌ Error en enviar_masivo_revision: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== APROBAR ARTÍCULO ====================

@login_required
def aprobar_articulo(request, articulo_id):
    """
    Aprueba un artículo completo (SUPERVISOR/DUEÑO)
    🆕 Aprueba automáticamente todos los campos completados
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    articulo = get_object_or_404(Articulo, id=articulo_id)
    proyecto = articulo.proyecto
    
    # Verificar rol de supervisor/dueño
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        rol_proyecto__in=['SUPERVISOR', 'DUEÑO']
    ).first()
    
    if not usuario_proyecto:
        return JsonResponse({
            'success': False,
            'error': 'Solo Supervisores y Dueños pueden aprobar artículos'
        }, status=403)
    
    try:
        data = json.loads(request.body)
        comentario_texto = data.get('comentario', '').strip()
        
        # Cambiar estado a APROBADO
        articulo.cambiar_estado('APROBADO', usuario=request.user)
        
        # 🆕 Aprobar todos los campos completados automáticamente
        campos_aprobados = 0
        for asignacion in articulo.campos_asignados.filter(completado=True, aprobado=False):
            asignacion.aprobar_campo(supervisor=request.user)
            campos_aprobados += 1
        
        # Registrar en historial
        mensaje_historial = f'Aprobado por {request.user.get_full_name() or request.user.username}'
        if campos_aprobados > 0:
            mensaje_historial += f' ({campos_aprobados} campos aprobados automáticamente)'
        
        HistorialArticulo.objects.create(
            articulo=articulo,
            usuario=request.user,
            tipo_cambio='APROBACION',
            valor_nuevo=mensaje_historial
        )
        
        # Si hay comentario, guardarlo
        if comentario_texto:
            ComentarioRevision.objects.create(
                articulo=articulo,
                supervisor=request.user,
                colaborador=articulo.usuario_asignado or articulo.usuario_carga,
                comentario=comentario_texto,
                tipo_accion='APROBADO'
            )
        
        # 🔔 NOTIFICAR AL COLABORADOR (si no es quien aprobó)
        usuario_responsable = articulo.usuario_asignado or articulo.usuario_carga
        if usuario_responsable and usuario_responsable.id != request.user.id:
            mensaje_notif = f'¡Felicidades! Tu artículo "{articulo.titulo[:50]}..." ha sido aprobado por {request.user.get_full_name() or request.user.username}.'
            if comentario_texto:
                mensaje_notif += f' Comentario: "{comentario_texto[:100]}"'
            
            crear_notificacion_articulos(
                usuario=usuario_responsable,
                tipo='tarea_aprobada',
                titulo=f'✅ Artículo aprobado - {proyecto.nombre}',
                mensaje=mensaje_notif,
                url=reverse('articulos:workspace_articulo', args=[articulo.id]),
                proyecto=proyecto
            )
        
        return JsonResponse({
            'success': True,
            'mensaje': 'Artículo aprobado exitosamente',
            'campos_aprobados': campos_aprobados,
            'redirect_url': reverse('articulos:bandeja_revision', args=[proyecto.id])
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Datos inválidos'}, status=400)
    except Exception as e:
        print(f"❌ Error en aprobar_articulo: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== SOLICITAR CORRECCIÓN ====================

@login_required
def solicitar_correccion(request, articulo_id):
    """
    Devuelve un artículo al colaborador con comentarios de corrección
    El artículo pasa de EN_REVISION a PENDIENTE
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    articulo = get_object_or_404(Articulo, id=articulo_id)
    proyecto = articulo.proyecto
    
    # Verificar rol
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        rol_proyecto__in=['SUPERVISOR', 'DUEÑO']
    ).first()
    
    if not usuario_proyecto:
        return JsonResponse({'success': False, 'error': 'No tienes permisos'}, status=403)
    
    # Validar estado
    if articulo.estado != 'EN_REVISION':
        return JsonResponse({
            'success': False,
            'error': 'Solo puedes solicitar corrección a artículos en revisión'
        }, status=400)
    
    try:
        data = json.loads(request.body)
        comentario_texto = data.get('comentario', '').strip()
        
        if not comentario_texto:
            return JsonResponse({
                'success': False,
                'error': 'Debes proporcionar un comentario de retroalimentación'
            }, status=400)
        
        # Cambiar estado a PENDIENTE (mantiene los cambios guardados)
        articulo.cambiar_estado('PENDIENTE', usuario=request.user)
        
        # Registrar en historial
        HistorialArticulo.objects.create(
            articulo=articulo,
            usuario=request.user,
            tipo_cambio='SOLICITUD_CORRECCION',
            valor_nuevo=f'Requiere corrección: {comentario_texto[:100]}'
        )
        
        # Guardar comentario
        colaborador = articulo.usuario_asignado or articulo.usuario_carga
        ComentarioRevision.objects.create(
            articulo=articulo,
            supervisor=request.user,
            colaborador=colaborador,
            comentario=comentario_texto,
            tipo_accion='CORRECCION'
        )
        
        # 🔔 NOTIFICAR AL COLABORADOR
        if colaborador:
            crear_notificacion_articulos(
                usuario=colaborador,
                tipo='tarea_correccion',
                titulo=f'🔄 Corrección solicitada - {proyecto.nombre}',
                mensaje=f'{request.user.get_full_name() or request.user.username} solicita correcciones en tu artículo "{articulo.titulo[:50]}...". Comentario: "{comentario_texto[:100]}"',
                url=reverse('articulos:workspace_articulo', args=[articulo.id]),
                proyecto=proyecto
            )
        
        return JsonResponse({
            'success': True,
            'mensaje': 'Corrección solicitada exitosamente',
            'redirect_url': reverse('articulos:bandeja_revision', args=[proyecto.id])
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Datos inválidos'}, status=400)
    except Exception as e:
        print(f"❌ Error en solicitar_correccion: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== BANDEJA DE REVISIÓN ====================

@login_required
def bandeja_revision(request, proyecto_id):
    """
    Vista de SUPERVISORES/DUEÑOS para revisar artículos
    Muestra todos los artículos EN_REVISION y permite filtrar
    """
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar rol
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        rol_proyecto__in=['SUPERVISOR', 'DUEÑO']
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes acceso a la bandeja de revisión.')
        return redirect('articulos:ver_articulos', proyecto_id=proyecto_id)
    
    # Filtros
    estado_filtro = request.GET.get('estado', 'EN_REVISION')
    usuario_filtro = request.GET.get('usuario', '')
    
    # Base query
    articulos = Articulo.objects.filter(proyecto=proyecto)
    
    # Aplicar filtros
    if estado_filtro:
        articulos = articulos.filter(estado=estado_filtro)
    
    if usuario_filtro:
        articulos = articulos.filter(
            Q(usuario_asignado_id=usuario_filtro) | Q(usuario_carga_id=usuario_filtro)
        )
    
    # Prefetch relacionados
    articulos = articulos.select_related(
        'usuario_carga', 'usuario_asignado'
    ).prefetch_related(
        'campos_asignados__campo'
    ).order_by('-fecha_actualizacion')
    
    # Calcular estadísticas
    total_en_revision = Articulo.objects.filter(
        proyecto=proyecto,
        estado='EN_REVISION'
    ).count()
    
    total_en_proceso = Articulo.objects.filter(
        proyecto=proyecto,
        estado='EN_PROCESO'
    ).count()
    
    total_aprobados = Articulo.objects.filter(
        proyecto=proyecto,
        estado='APROBADO'
    ).count()
    
    # Obtener colaboradores del proyecto
    colaboradores = UsuarioProyecto.objects.filter(
        proyecto=proyecto
    ).select_related('usuario').order_by('usuario__first_name')
    
    context = {
        'proyecto': proyecto,
        'articulos': articulos,
        'usuario_proyecto': usuario_proyecto,
        'estado_filtro': estado_filtro,
        'usuario_filtro': usuario_filtro,
        'total_en_revision': total_en_revision,
        'total_en_proceso': total_en_proceso,
        'total_aprobados': total_aprobados,
        'colaboradores': colaboradores,
    }
    
    return render(request, 'bandeja_revision.html', context)


# ==================== ASIGNAR CAMPOS A ARTÍCULOS ====================

@login_required
def asignar_campos_articulos(request, proyecto_id):
    """
    🎯 FUNCIÓN UNIFICADA: Asigna o desasigna campos a artículos
    
    Soporta DOS modos de operación:
    1. AJAX (JSON) - Para interfaces modernas con JavaScript
    2. FORMULARIO (POST) - Para formularios HTML tradicionales
    
    Características:
    - ✅ Protege campos ya aprobados
    - ✅ Soporta plantillas predefinidas
    - ✅ Reactiva artículos APROBADOS cuando se asignan nuevos campos
    - ✅ Sistema de notificaciones integrado
    - ✅ Registro en historial
    """
    
    if request.method != 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
        messages.error(request, 'Método no permitido')
        return redirect('articulos:ver_articulos', proyecto_id=proyecto_id)
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto,
        rol_proyecto='DUEÑO'
    ).first()
    
    if not usuario_proyecto:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'No tienes permisos'}, status=403)
        messages.error(request, 'No tienes acceso a este proyecto.')
        return redirect('mis_proyectos')
    
    # 🔍 DETECTAR TIPO DE REQUEST
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    content_type = request.headers.get('Content-Type', '')
    es_json = 'application/json' in content_type
    
    try:
        # ==================== EXTRAER DATOS SEGÚN EL TIPO ====================
        if is_ajax or es_json:
            # 📡 MODO AJAX (JSON)
            try:
                data = json.loads(request.body)
                articulos_ids = data.get('articulos_ids', [])
                campos_ids = data.get('campos_ids', [])
                usar_plantilla = data.get('usar_plantilla', False)
                plantilla_id = data.get('plantilla_id')
                accion = data.get('accion', 'asignar')
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Error al procesar datos JSON'}, status=400)
        else:
            # 📝 MODO FORMULARIO (POST tradicional)
            articulos_ids = request.POST.getlist('articulos')
            campos_ids = request.POST.getlist('campos')
            usar_plantilla = False
            plantilla_id = None
            accion = request.POST.get('accion', 'asignar')
        
        # ==================== VALIDACIONES ====================
        if not articulos_ids:
            error_msg = 'Debes seleccionar al menos un artículo'
            if is_ajax or es_json:
                return JsonResponse({'success': False, 'error': error_msg})
            messages.warning(request, error_msg)
            return redirect('articulos:ver_articulos', proyecto_id=proyecto_id)
        
        # ==================== OBTENER CAMPOS ====================
        if usar_plantilla and plantilla_id:
            # Usar plantilla
            plantilla = get_object_or_404(PlantillaBusqueda, id=plantilla_id, proyecto=proyecto)
            campos = plantilla.campos.all()
            nombre_campos = f'plantilla "{plantilla.nombre}"'
        else:
            # Usar campos seleccionados
            if not campos_ids and accion == 'asignar':
                error_msg = 'Debes seleccionar al menos un campo'
                if is_ajax or es_json:
                    return JsonResponse({'success': False, 'error': error_msg})
                messages.warning(request, error_msg)
                return redirect('articulos:ver_articulos', proyecto_id=proyecto_id)
            
            campos = CampoMetanalisis.objects.filter(id__in=campos_ids, activo=True) if accion == 'asignar' else []
            nombre_campos = f"{len(campos)} campo(s)"
        
        # ==================== PROCESAR ARTÍCULOS ====================
        asignaciones_creadas = 0
        asignaciones_eliminadas = 0
        campos_protegidos = 0
        articulos_actualizados = []
        articulos_reactivados = []
        usuarios_articulos = {}
        
        for articulo_id in articulos_ids:
            articulo = get_object_or_404(Articulo, id=articulo_id, proyecto=proyecto)
            
            if accion == 'desasignar':
                # ==================== DESASIGNAR CAMPOS ====================
                # Solo eliminar campos NO aprobados
                asignaciones_a_eliminar = AsignacionCampo.objects.filter(
                    articulo=articulo,
                    aprobado=False
                )
                
                if campos:
                    # Si hay campos específicos, filtrar por ellos
                    asignaciones_a_eliminar = asignaciones_a_eliminar.filter(campo__in=campos)
                
                # Contar campos aprobados protegidos
                campos_aprobados_count = AsignacionCampo.objects.filter(
                    articulo=articulo,
                    aprobado=True
                ).count()
                
                if campos_aprobados_count > 0:
                    campos_protegidos += campos_aprobados_count
                
                count_eliminados = asignaciones_a_eliminar.count()
                asignaciones_a_eliminar.delete()
                asignaciones_eliminadas += count_eliminados
                
                # Si no quedan campos, volver a EN_ESPERA
                if not articulo.campos_asignados.exists():
                    articulo.cambiar_estado('EN_ESPERA', usuario=request.user)
                    articulos_actualizados.append(articulo.titulo[:30])
                
                # Registrar en historial
                if count_eliminados > 0:
                    mensaje_historial = f'{count_eliminados} campo(s) desasignado(s)'
                    if campos_aprobados_count > 0:
                        mensaje_historial += f' ({campos_aprobados_count} protegido(s))'
                    
                    HistorialArticulo.objects.create(
                        articulo=articulo,
                        usuario=request.user,
                        tipo_cambio='DESASIGNACION_CAMPOS',
                        valor_nuevo=mensaje_historial
                    )
                    
            else:
                # ==================== ASIGNAR CAMPOS ====================
                campos_nuevos = 0
                campos_protegidos_articulo = 0
                
                for campo in campos:
                    # Verificar si ya existe
                    asignacion_existente = AsignacionCampo.objects.filter(
                        articulo=articulo,
                        campo=campo
                    ).first()
                    
                    if asignacion_existente:
                        if asignacion_existente.aprobado:
                            # ⚠️ Campo aprobado, no tocar
                            campos_protegidos += 1
                            campos_protegidos_articulo += 1
                            continue
                        else:
                            # Ya existe pero no está aprobado
                            continue
                    
                    # Crear nueva asignación
                    AsignacionCampo.objects.create(
                        articulo=articulo,
                        campo=campo,
                        asignado_por=request.user
                    )
                    asignaciones_creadas += 1
                    campos_nuevos += 1
                
                # 🔄 CAMBIO DE ESTADO
                if campos_nuevos > 0:
                    # Caso 1: EN_ESPERA → PENDIENTE
                    if articulo.estado == 'EN_ESPERA':
                        articulo.cambiar_estado('PENDIENTE', usuario=request.user)
                        articulos_actualizados.append(articulo.titulo[:30])
                    
                    # Caso 2: APROBADO → PENDIENTE (REACTIVACIÓN)
                    elif articulo.estado == 'APROBADO':
                        articulo.cambiar_estado('PENDIENTE', usuario=request.user)
                        articulos_reactivados.append(articulo.titulo[:30])
                        
                        HistorialArticulo.objects.create(
                            articulo=articulo,
                            usuario=request.user,
                            tipo_cambio='ASIGNACION',
                            valor_nuevo=f'Artículo reactivado: {campos_nuevos} campos nuevos después de aprobación'
                        )
                        
                        # 🔔 NOTIFICACIÓN ESPECIAL para reactivación
                        usuario_responsable = articulo.usuario_asignado or articulo.usuario_carga
                        if usuario_responsable and usuario_responsable.id != request.user.id:
                            crear_notificacion_articulos(
                                usuario=usuario_responsable,
                                tipo='tarea_asignada',
                                titulo=f'🔄 Artículo reactivado - {proyecto.nombre}',
                                mensaje=f'El artículo "{articulo.titulo[:50]}..." que habías completado tiene {campos_nuevos} nuevos campos asignados.',
                                url=reverse('articulos:workspace_articulo', args=[articulo.id]),
                                proyecto=proyecto
                            )
                    
                    # Registrar en historial (solo cambios normales)
                    elif articulo.estado not in ['APROBADO']:
                        mensaje_historial = f'{campos_nuevos} campo(s) asignado(s)'
                        if campos_protegidos_articulo > 0:
                            mensaje_historial += f' ({campos_protegidos_articulo} protegido(s))'
                        
                        HistorialArticulo.objects.create(
                            articulo=articulo,
                            usuario=request.user,
                            tipo_cambio='ASIGNACION_CAMPOS',
                            valor_nuevo=mensaje_historial
                        )
                
                # 🔑 Preparar notificaciones (solo asignaciones normales)
                if campos_nuevos > 0 and articulo.estado not in ['APROBADO']:
                    usuario_responsable = articulo.usuario_asignado or articulo.usuario_carga
                    
                    if usuario_responsable and usuario_responsable.id != request.user.id:
                        if usuario_responsable.id not in usuarios_articulos:
                            usuarios_articulos[usuario_responsable.id] = {
                                'usuario': usuario_responsable,
                                'cantidad': 0,
                                'articulos_titulos': []
                            }
                        usuarios_articulos[usuario_responsable.id]['cantidad'] += 1
                        usuarios_articulos[usuario_responsable.id]['articulos_titulos'].append(articulo.titulo[:50])
        
        # 🔔 ENVIAR NOTIFICACIONES (solo asignaciones normales)
        usuarios_notificados = 0
        if accion == 'asignar' and asignaciones_creadas > 0:
            for user_id, info in usuarios_articulos.items():
                usuario = info['usuario']
                cantidad = info['cantidad']
                
                if cantidad == 1:
                    mensaje = f'{request.user.get_full_name() or request.user.username} te ha asignado nuevas tareas en 1 artículo.'
                    titulo = f'📋 Nueva tarea asignada - {proyecto.nombre}'
                else:
                    mensaje = f'{request.user.get_full_name() or request.user.username} te ha asignado nuevas tareas en {cantidad} artículos.'
                    titulo = f'📋 {cantidad} nuevas tareas asignadas - {proyecto.nombre}'
                
                crear_notificacion_articulos(
                    usuario=usuario,
                    tipo='tarea_asignada',
                    titulo=titulo,
                    mensaje=mensaje,
                    url=reverse('articulos:ver_articulos', args=[proyecto.id]),
                    proyecto=proyecto
                )
                usuarios_notificados += 1
        
        # ==================== CONSTRUIR RESPUESTA ====================
        if accion == 'desasignar':
            mensaje_respuesta = f'Se desasignaron {asignaciones_eliminadas} campo(s) de {len(articulos_ids)} artículo(s).'
            if campos_protegidos > 0:
                mensaje_respuesta += f' {campos_protegidos} campo(s) aprobado(s) fueron protegido(s).'
            if articulos_actualizados:
                mensaje_respuesta += f' {len(articulos_actualizados)} artículo(s) volvieron a EN ESPERA.'
        else:
            mensaje_respuesta = f'Se asignaron {asignaciones_creadas} campo(s) a {len(articulos_ids)} artículo(s).'
            if campos_protegidos > 0:
                mensaje_respuesta += f' {campos_protegidos} campo(s) ya estaban aprobado(s).'
            if articulos_actualizados:
                mensaje_respuesta += f' {len(articulos_actualizados)} artículo(s) pasaron a PENDIENTE.'
            if articulos_reactivados:
                mensaje_respuesta += f' 🔄 {len(articulos_reactivados)} artículo(s) aprobados fueron reactivados.'
            if usuarios_notificados > 0:
                mensaje_respuesta += f' Se notificó a {usuarios_notificados} usuario(s).'
        
        print(f"📊 Resumen: Acción={accion} | Asignadas={asignaciones_creadas} | Eliminadas={asignaciones_eliminadas} | Reactivados={len(articulos_reactivados)} | Protegidos={campos_protegidos}")
        
        # ==================== DEVOLVER RESPUESTA SEGÚN TIPO ====================
        if is_ajax or es_json:
            # 📡 RESPUESTA AJAX (JSON)
            return JsonResponse({
                'success': True,
                'mensaje': mensaje_respuesta,
                'accion': accion,
                'asignaciones_creadas': asignaciones_creadas,
                'asignaciones_eliminadas': asignaciones_eliminadas,
                'campos_protegidos': campos_protegidos,
                'articulos_actualizados': len(articulos_actualizados),
                'articulos_reactivados': len(articulos_reactivados),
                'usuarios_notificados': usuarios_notificados
            })
        else:
            # 📝 RESPUESTA FORMULARIO (Redirect con mensaje)
            if accion == 'asignar':
                if asignaciones_creadas > 0:
                    messages.success(request, f'✅ {mensaje_respuesta}')
                elif campos_protegidos > 0:
                    messages.warning(request, f'⚠️ {mensaje_respuesta}')
                else:
                    messages.info(request, 'ℹ️ No se realizaron cambios. Los campos ya estaban asignados.')
            else:
                if asignaciones_eliminadas > 0:
                    messages.success(request, f'✅ {mensaje_respuesta}')
                elif campos_protegidos > 0:
                    messages.warning(request, f'⚠️ {mensaje_respuesta}')
                else:
                    messages.info(request, 'ℹ️ No había campos para eliminar.')
            
            return redirect('articulos:ver_articulos', proyecto_id=proyecto_id)
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error en asignar_campos_articulos: {str(e)}")
        print(error_trace)
        
        if is_ajax or es_json:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        else:
            messages.error(request, f'Error al procesar la asignación: {str(e)}')
            return redirect('articulos:ver_articulos', proyecto_id=proyecto_id)

@login_required
def estadisticas_articulo(request, articulo_id):
    """
    Vista AJAX que retorna estadísticas actualizadas del artículo
    Útil para actualizaciones en tiempo real sin recargar página
    """
    articulo = get_object_or_404(Articulo, id=articulo_id)
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=articulo.proyecto
    ).first()
    
    if not usuario_proyecto:
        return JsonResponse({'success': False, 'error': 'No tienes acceso'}, status=403)
    
    # Calcular estadísticas
    total_campos = articulo.campos_asignados.count()
    campos_completados = articulo.campos_asignados.filter(completado=True).count()
    campos_aprobados = articulo.campos_asignados.filter(aprobado=True).count()
    campos_pendientes = total_campos - campos_completados
    
    progreso_completado = (campos_completados / total_campos * 100) if total_campos > 0 else 0
    progreso_aprobado = (campos_aprobados / campos_completados * 100) if campos_completados > 0 else 0
    
    return JsonResponse({
        'success': True,
        'estado': articulo.estado,
        'estado_display': articulo.get_estado_display(),
        'total_campos': total_campos,
        'campos_completados': campos_completados,
        'campos_aprobados': campos_aprobados,
        'campos_pendientes': campos_pendientes,
        'progreso_completado': round(progreso_completado, 1),
        'progreso_aprobado': round(progreso_aprobado, 1),
        'puede_aprobar_completo': articulo.puede_aprobar_articulo(),
        'fecha_actualizacion': articulo.fecha_actualizacion.strftime('%d/%m/%Y %H:%M')
    })