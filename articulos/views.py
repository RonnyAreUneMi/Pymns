import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ArchivoSubida, Articulo
from pymetanalis.models import Proyecto

def subir_archivo(request, proyecto_id):
    try:
        proyecto = Proyecto.objects.get(id=proyecto_id)
    except Proyecto.DoesNotExist:
        messages.error(request, "El proyecto no existe.")
        return redirect('core:home')
    
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
                        
                        # Guardar cada artículo en el modelo Articulo
                        articulo = Articulo(
                            proyecto=proyecto,
                            usuario_carga=request.user,
                            bibtex_key=bibtex_key,
                            titulo=titulo[:500],  # Limitar a 500 caracteres
                            doi=entry.get('doi', None),
                            bibtex_original=bibtex_str,
                            metadata_completos=entry
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

    # Obtener archivos del proyecto
    archivos = ArchivoSubida.objects.filter(proyecto_id=proyecto_id).order_by('-fecha_subida')
    
    return render(request, 'subir.html', {
        'proyecto_id': proyecto_id,
        'proyecto': proyecto,
        'archivos': archivos
    })


def visualizar_articulos(request, archivo_id):
    """Vista para mostrar todos los artículos de un archivo .bib subido"""
    archivo = get_object_or_404(ArchivoSubida, id=archivo_id)
    
    # Obtener todos los artículos asociados a este archivo específico
    articulos = Articulo.objects.filter(
        proyecto=archivo.proyecto,
        usuario_carga=archivo.usuario,
        fecha_carga__gte=archivo.fecha_subida
    ).order_by('-fecha_carga')
    
    return render(request, 'visualizar_articulos.html', {
        'archivo': archivo,
        'articulos': articulos,
        'proyecto': archivo.proyecto
    })