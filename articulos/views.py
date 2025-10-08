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

from .models import Articulo, ArchivoSubida, HistorialArticulo
from pymetanalis.models import Proyecto, UsuarioProyecto
from .utils import ExtractorTexto


@login_required
def ver_articulos(request, proyecto_id):
    """Vista para que administradores e investigadores vean los artículos de un proyecto."""
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)

    # Verificar rol del usuario
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()

    # Obtener artículos del proyecto
    articulos = Articulo.objects.filter(proyecto=proyecto).order_by('-fecha_carga')

    context = {
        'proyecto': proyecto,
        'articulos': articulos
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
        return redirect('core:home')
    
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
        return redirect('core:home')
    
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar acceso
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permiso para acceder a este proyecto.')
        return redirect('core:home')
    
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
        return redirect('core:home')
    
    articulo = get_object_or_404(Articulo, id=articulo_id)
    proyecto_id = articulo.proyecto.id

    # Verificar que el usuario tiene acceso al proyecto
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=articulo.proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permiso para eliminar este artículo.')
        return redirect('core:home')

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
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # Verificar que el usuario tiene acceso al proyecto
    usuario_proyecto = UsuarioProyecto.objects.filter(
        usuario=request.user,
        proyecto=proyecto
    ).first()
    
    if not usuario_proyecto:
        messages.error(request, 'No tienes permiso para agregar artículos a este proyecto.')
        return redirect('core:home')
    
    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        
        if archivo:
            # ========== PROCESAMIENTO DE ARCHIVO CON EXTRACCIÓN ==========
            try:
                # Validar tipo de archivo
                ext = os.path.splitext(archivo.name)[1].lower()
                if ext not in ['.pdf', '.doc', '.docx', '.txt']:
                    messages.error(request, 'Formato de archivo no válido. Solo se permiten PDF, DOC, DOCX o TXT.')
                    return redirect('articulos:agregar_articulo', proyecto_id=proyecto.id)
                
                # Validar tamaño (10MB máximo)
                if archivo.size > 10 * 1024 * 1024:
                    messages.error(request, 'El archivo es demasiado grande. Tamaño máximo: 10MB.')
                    return redirect('articulos:agregar_articulo', proyecto_id=proyecto.id)
                
                # Guardar archivo
                archivo_subida = ArchivoSubida.objects.create(
                    proyecto=proyecto,
                    usuario=request.user,
                    nombre_archivo=archivo.name,
                    ruta_archivo=archivo
                )
                
                try:
                    # Extraer metadata del archivo
                    metadata, texto_completo = ExtractorTexto.procesar_archivo(
                        archivo_subida.ruta_archivo,
                        archivo.name
                    )
                    
                    # Generar bibtex_key único
                    bibtex_key = ExtractorTexto.generar_bibtex_key(
                        metadata['autores'],
                        metadata['anio']
                    )
                    
                    # Asegurar que sea único
                    contador = 1
                    bibtex_key_original = bibtex_key
                    while Articulo.objects.filter(bibtex_key=bibtex_key).exists():
                        bibtex_key = f"{bibtex_key_original}_{contador}"
                        contador += 1
                    
                    # Generar BibTeX
                    bibtex_original = ExtractorTexto.generar_bibtex(metadata, bibtex_key)
                    
                    # Preparar metadata_completos
                    metadata_completos = {
                        'autores': metadata['autores'],
                        'abstract': metadata['abstract'],
                        'anio_publicacion': metadata['anio'],
                        'palabras_clave': metadata['palabras_clave'].split(',') if metadata['palabras_clave'] else [],
                        'archivo_origen': archivo.name,
                        'texto_completo': texto_completo[:5000],  # Guardar primeros 5000 caracteres
                        'extraido_automaticamente': True
                    }
                    
                    if metadata.get('journal'):
                        metadata_completos['journal'] = metadata['journal']
                    if metadata.get('url'):
                        metadata_completos['url'] = metadata['url']
                    
                    # Crear artículo
                    articulo = Articulo.objects.create(
                        proyecto=proyecto,
                        usuario_carga=request.user,
                        bibtex_key=bibtex_key,
                        titulo=metadata['titulo'],
                        doi=metadata.get('doi'),
                        bibtex_original=bibtex_original,
                        metadata_completos=metadata_completos,
                        estado='PENDIENTE'
                    )
                    
                    # Registrar en historial
                    HistorialArticulo.objects.create(
                        articulo=articulo,
                        usuario=request.user,
                        tipo_cambio='CREACION',
                        valor_nuevo=f'Artículo creado desde archivo: {archivo.name}'
                    )
                    
                    archivo_subida.articulos_procesados = 1
                    archivo_subida.save()
                    
                    messages.success(request, f'Artículo "{articulo.titulo}" agregado correctamente desde el archivo.')
                    return redirect('articulos:ver_articulos', proyecto_id=proyecto.id)
                    
                except Exception as e:
                    # Si hay error en la extracción, guardar el error
                    archivo_subida.errores_procesamiento = {
                        'error': str(e),
                        'timestamp': timezone.now().isoformat()
                    }
                    archivo_subida.save()
                    messages.error(request, f'Error al extraer datos del archivo: {str(e)}')
                    return redirect('articulos:agregar_articulo', proyecto_id=proyecto.id)
                
            except Exception as e:
                messages.error(request, f'Error al procesar el archivo: {str(e)}')
                return redirect('articulos:agregar_articulo', proyecto_id=proyecto.id)
        
        else:
            # ========== PROCESAMIENTO DE FORMULARIO MANUAL ==========
            try:
                # Obtener datos del formulario
                titulo = request.POST.get('titulo', '').strip()
                autores = request.POST.get('autores', '').strip()
                abstract = request.POST.get('abstract', '').strip()
                doi = request.POST.get('doi', '').strip()
                anio = request.POST.get('anio')
                journal = request.POST.get('journal', '').strip()
                volumen = request.POST.get('volumen', '').strip()
                paginas = request.POST.get('paginas', '').strip()
                editorial = request.POST.get('editorial', '').strip()
                palabras_clave = request.POST.get('palabras_clave', '').strip()
                url = request.POST.get('url', '').strip()
                
                # Validaciones
                if not titulo:
                    messages.error(request, 'El título es obligatorio.')
                    return redirect('articulos:agregar_articulo', proyecto_id=proyecto.id)
                
                if not autores:
                    messages.error(request, 'Los autores son obligatorios.')
                    return redirect('articulos:agregar_articulo', proyecto_id=proyecto.id)
                
                if not abstract or len(abstract) < 50:
                    messages.error(request, 'El abstract es obligatorio y debe tener al menos 50 caracteres.')
                    return redirect('articulos:agregar_articulo', proyecto_id=proyecto.id)
                
                if not anio:
                    messages.error(request, 'El año de publicación es obligatorio.')
                    return redirect('articulos:agregar_articulo', proyecto_id=proyecto.id)
                
                try:
                    anio = int(anio)
                    if anio < 1900 or anio > 2100:
                        raise ValueError()
                except (ValueError, TypeError):
                    messages.error(request, 'El año debe ser un número válido entre 1900 y 2100.')
                    return redirect('articulos:agregar_articulo', proyecto_id=proyecto.id)
                
                if not palabras_clave:
                    messages.error(request, 'Las palabras clave son obligatorias.')
                    return redirect('articulos:agregar_articulo', proyecto_id=proyecto.id)
                
                # Generar bibtex_key único
                primer_autor = autores.split(';')[0].split(',')[0].strip().lower().replace(' ', '')
                bibtex_key = f"{primer_autor}{anio}"
                
                # Asegurar que sea único
                contador = 1
                bibtex_key_original = bibtex_key
                while Articulo.objects.filter(bibtex_key=bibtex_key).exists():
                    bibtex_key = f"{bibtex_key_original}_{contador}"
                    contador += 1
                
                # Generar BibTeX
                bibtex_original = f"""@article{{{bibtex_key},
  author = {{{autores}}},
  title = {{{titulo}}},
  year = {{{anio}}},"""
                
                if journal:
                    bibtex_original += f"\n  journal = {{{journal}}},"
                if volumen:
                    bibtex_original += f"\n  volume = {{{volumen}}},"
                if paginas:
                    bibtex_original += f"\n  pages = {{{paginas}}},"
                if doi:
                    bibtex_original += f"\n  doi = {{{doi}}},"
                if editorial:
                    bibtex_original += f"\n  publisher = {{{editorial}}},"
                if url:
                    bibtex_original += f"\n  url = {{{url}}},"
                
                bibtex_original += "\n}"
                
                # Crear metadata_completos
                metadata_completos = {
                    'autores': autores,
                    'abstract': abstract,
                    'anio_publicacion': anio,
                    'palabras_clave': [kw.strip() for kw in palabras_clave.split(',')],
                    'entrada_manual': True
                }
                
                if journal:
                    metadata_completos['journal'] = journal
                if volumen:
                    metadata_completos['volumen'] = volumen
                if paginas:
                    metadata_completos['paginas'] = paginas
                if editorial:
                    metadata_completos['editorial'] = editorial
                if url:
                    metadata_completos['url'] = url
                
                # Crear el artículo
                articulo = Articulo.objects.create(
                    proyecto=proyecto,
                    usuario_carga=request.user,
                    bibtex_key=bibtex_key,
                    titulo=titulo,
                    doi=doi if doi else None,
                    bibtex_original=bibtex_original,
                    metadata_completos=metadata_completos,
                    estado='PENDIENTE'
                )
                
                # Registrar en historial
                HistorialArticulo.objects.create(
                    articulo=articulo,
                    usuario=request.user,
                    tipo_cambio='CREACION',
                    valor_nuevo=f'Artículo creado manualmente: {titulo}'
                )
                
                messages.success(request, f'Artículo "{articulo.titulo}" agregado correctamente.')
                return redirect('articulos:ver_articulos', proyecto_id=proyecto.id)
                
            except Exception as e:
                messages.error(request, f'Error al guardar el artículo: {str(e)}')
                return redirect('articulos:agregar_articulo', proyecto_id=proyecto.id)
    
    # GET request - mostrar formulario
    context = {
        'proyecto': proyecto
    }
    
    return render(request, 'indv_articulo.html', context)