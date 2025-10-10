from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.http import HttpResponse, FileResponse
import os
import json
import io

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

from .models import Articulo, ArchivoSubida, HistorialArticulo
from pymetanalis.models import Proyecto, UsuarioProyecto
from .utils import ExtractorTexto


@login_required
def seleccionar_proyecto_articulos(request):
    """Vista para seleccionar un proyecto antes de gestionar artículos"""
    
    # Obtener proyectos donde el usuario participa
    usuario_proyectos = UsuarioProyecto.objects.filter(
        usuario=request.user
    ).select_related('proyecto').order_by('-fecha_incorporacion')
    
    # Si no tiene proyectos, redirigir a buscar proyectos
    if not usuario_proyectos.exists():
        messages.info(
            request, 
            'No tienes proyectos asignados. Busca proyectos para unirte o crea uno nuevo.'
        )
        return redirect('buscar_proyectos')
    
    # Filtros (igual que mis_proyectos)
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
        
        # Contar artículos del proyecto
        total_articulos = Articulo.objects.filter(proyecto=proyecto).count()
        
        proyectos_data.append({
            'proyecto': proyecto,
            'rol': usuario_proyecto.rol_proyecto if usuario_proyecto else None,
            'puede_invitar': usuario_proyecto.puede_invitar if usuario_proyecto else False,
            'total_articulos': total_articulos,
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
        'es_seleccion_articulos': True,
    }
    
    return render(request, 'seleccionar_proyecto.html', context)


@login_required
def ver_articulos(request, proyecto_id):
    """Vista para que administradores e investigadores vean los artículos de un proyecto."""
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    except (Proyecto.DoesNotExist, ValueError):
        messages.error(request, 'Proyecto no encontrado.')
        return redirect('articulos:seleccionar_proyecto')

    # Verificar rol del usuario
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes acceso a este proyecto.')
        return redirect('articulos:seleccionar_proyecto')
    
    # ✅ GUARDAR PROYECTO ACTUAL EN SESIÓN
    request.session['proyecto_actual_id'] = proyecto.id
    request.session.modified = True

    # Limpiar COMPLETAMENTE la sesión de archivos subidos
    if 'archivos_sesion' in request.session:
        try:
            del request.session['archivos_sesion']
        except KeyError:
            pass

    # Obtener artículos del proyecto
    articulos = Articulo.objects.filter(proyecto=proyecto).order_by('-fecha_carga')

    context = {
        'proyecto': proyecto,
        'articulos': articulos,
        'usuario_proyecto': usuario_proyecto,
    }

    return render(request, 'ver_articulos.html', context)


@login_required
def descargar_articulo(request, articulo_id):
    """Vista para descargar el BibTeX de un artículo individual."""
    articulo = get_object_or_404(Articulo, id=articulo_id)
    
    # Verificar que el usuario tiene acceso al proyecto
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=articulo.proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permiso para acceder a este artículo.')
        return redirect('articulos:seleccionar_proyecto')
    
    # Crear el contenido BibTeX
    bibtex_content = articulo.bibtex_original
    
    # Crear respuesta HTTP con el archivo
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
        return redirect('articulos:seleccionar_proyecto')
    
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    except (Proyecto.DoesNotExist, ValueError):
        messages.error(request, 'Proyecto no encontrado.')
        return redirect('articulos:seleccionar_proyecto')
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permiso para acceder a este proyecto.')
        return redirect('articulos:seleccionar_proyecto')
    
    # Obtener todos los artículos del archivo
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


@login_required
def eliminar_articulo(request, articulo_id):
    """Vista para eliminar un artículo."""
    if request.method != 'POST':
        messages.error(request, 'Método no permitido.')
        return redirect('articulos:seleccionar_proyecto')
    
    articulo = get_object_or_404(Articulo, id=articulo_id)
    proyecto_id = articulo.proyecto.id

    # Verificar que el usuario tiene acceso al proyecto
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=articulo.proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permiso para eliminar este artículo.')
        return redirect('articulos:seleccionar_proyecto')

    # Guardar información antes de eliminar
    titulo_articulo = articulo.titulo
    bibtex_key = articulo.bibtex_key

    # Registrar en historial antes de eliminar
    HistorialArticulo.objects.create(
        articulo=articulo,
        usuario=request.user,
        tipo_cambio='ELIMINACION',
        valor_anterior=titulo_articulo,
        valor_nuevo=f'Artículo eliminado por {request.user.get_full_name() or request.user.username}'
    )

    # Eliminar el artículo
    articulo.delete()

    messages.success(request, f'Artículo "{titulo_articulo}" eliminado correctamente.')
    return redirect('articulos:ver_articulos', proyecto_id=proyecto_id)


@login_required
def agregar_articulo(request, proyecto_id):
    """Vista para agregar un nuevo artículo al proyecto."""
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    except (Proyecto.DoesNotExist, ValueError):
        messages.error(request, 'Proyecto no encontrado.')
        return redirect('articulos:seleccionar_proyecto')
    
    # Verificar que el usuario tiene acceso al proyecto
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permiso para agregar artículos a este proyecto.')
        return redirect('articulos:seleccionar_proyecto')
    
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        if titulo:
            Articulo.objects.create(
                proyecto=proyecto,
                usuario_carga=request.user,
                titulo=titulo,
                bibtex_key=f"{titulo[:20]}_{timezone.now().timestamp()}",
                bibtex_original="@article{...}",
                archivo_bib=None  # 🔹 CAMBIO: Artículos manuales no tienen archivo origen
            )
            messages.success(request, 'Artículo agregado correctamente.')
            return redirect('articulos:ver_articulos', proyecto_id=proyecto.id)
    
    return render(request, 'indv_articulo.html', {'proyecto': proyecto})


@login_required
def subir_archivo(request, proyecto_id):
    try:
        proyecto = Proyecto.objects.get(id=proyecto_id)
    except (Proyecto.DoesNotExist, ValueError):
        messages.error(request, "El proyecto no existe.")
        return redirect('articulos:seleccionar_proyecto')
    
    # Verificar acceso del usuario
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes acceso a este proyecto.')
        return redirect('articulos:seleccionar_proyecto')
    
    # ✅ GUARDAR PROYECTO ACTUAL EN SESIÓN
    request.session['proyecto_actual_id'] = proyecto.id
    
    # Inicializar lista de archivos de la sesión si no existe o está vacía
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
            # Guardar archivo primero
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
                # Configurar parser con opciones robustas
                parser = BibTexParser(common_strings=True)
                parser.ignore_nonstandard_types = False
                parser.homogenize_fields = True
                
                # Leer el archivo - Django FileField requiere modo binario y decodificar manualmente
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
                
                # Parsear el contenido
                bib_database = bibtexparser.loads(contenido, parser=parser)
                
                print(f"📊 DEBUG: Entradas encontradas en el archivo: {len(bib_database.entries)}")
                
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
                        
                        # Verificar si ya existe (para evitar duplicados)
                        if Articulo.objects.filter(
                            bibtex_key=bibtex_key,
                            proyecto=proyecto
                        ).exists():
                            errores.append({
                                'entry': bibtex_key,
                                'error': 'Ya existe un artículo con esta clave en este proyecto'
                            })
                            continue
                        
                        # Crear un string del bibtex original
                        entry_type = entry.get('ENTRYTYPE', 'article').upper()
                        bibtex_str = f"@{entry_type}{{{bibtex_key},\n"
                        
                        for key, value in entry.items():
                            if key not in ['ENTRYTYPE', 'ID']:
                                # Limpiar el valor de caracteres problemáticos
                                value_clean = str(value).strip()
                                bibtex_str += f"  {key} = {{{value_clean}}},\n"
                        bibtex_str += "}"
                        
                        # Extraer título limpio
                        titulo = entry.get('title', 'Sin título')
                        if isinstance(titulo, str):
                            titulo = titulo.strip()
                        
                        # 🔹 CAMBIO IMPORTANTE: Asignar archivo_bib con el nombre del archivo
                        articulo = Articulo(
                            proyecto=proyecto,
                            usuario_carga=request.user,
                            bibtex_key=bibtex_key,
                            titulo=titulo[:500],  # Limitar a 500 caracteres
                            doi=entry.get('doi', None),
                            bibtex_original=bibtex_str,
                            metadata_completos=entry,
                            archivo_bib=archivo.name  # 🔹 Aquí está el cambio clave
                        )
                        articulo.save()
                        cantidad_articulos_procesados += 1
                        print(f"✅ Artículo guardado: {bibtex_key}")
                        
                    except Exception as e:
                        error_msg = str(e)
                        errores.append({
                            'entry': entry.get('ID', 'desconocido'),
                            'error': error_msg
                        })
                        print(f"❌ ERROR en entrada {entry.get('ID', 'desconocido')}: {error_msg}")
                        
            except Exception as e:
                error_msg = str(e)
                errores.append({'error': f'Error al procesar archivo: {error_msg}'})
                print(f"❌ ERROR GENERAL: {error_msg}")

            # Guardar cantidad de artículos procesados y errores
            nuevo_archivo.articulos_procesados = cantidad_articulos_procesados
            if errores:
                nuevo_archivo.errores_procesamiento = errores
            nuevo_archivo.save()
            
            # Agregar el archivo a la lista de la sesión
            archivos_sesion = request.session.get('archivos_sesion', [])
            archivos_sesion.append(nuevo_archivo.id)
            request.session['archivos_sesion'] = archivos_sesion
            request.session.modified = True
            
            # Mostrar mensaje según el resultado
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

    # Obtener solo los archivos de la sesión actual
    archivos_ids = request.session.get('archivos_sesion', [])
    archivos = ArchivoSubida.objects.filter(id__in=archivos_ids).order_by('-fecha_subida')
    
    return render(request, 'subir.html', {
        'proyecto_id': proyecto_id,
        'proyecto': proyecto,
        'archivos': archivos
    })


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
        return redirect('articulos:seleccionar_proyecto')
    
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