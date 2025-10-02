# Roles de Usuario

## Invitados
- Pueden buscar proyectos.  
- En base a un proyecto pueden solicitar unirse como **colaboradores**.  
- También pueden ingresar directamente como colaboradores si reciben un link de invitación.  
- Si no quieren ser colaboradores, pueden solicitar ser **investigadores**.  

---

## Investigadores
- Acceden al menú **Proyectos**.  
- Pueden crear proyectos o ver sus proyectos en **Mis proyectos**.  
- En cada proyecto pueden subir archivos `.bib`.  
- Tienen un menú para cambiar roles de usuarios dentro del proyecto:  
  - **Supervisor**: revisa el trabajo de los colaboradores y aprueba o rechaza.  
  - **Colaborador**: tiene acceso a un proyecto, puede subir archivos `.bib` y trabajar en artículos.  
- En base a los archivos `.bib` se genera un menú de **Artículos (Kanban)** con estados:  
  - No iniciados  
  - En progreso  
  - En revisión / testing  
  - Aprobados / finalizados  
- El menú de revisión solo lo ven **supervisores** y **administradores**.  
- Todos los roles tienen un **área de trabajo** donde se abre el artículo para editar y añadir detalles.  

### Restricciones
- El **colaborador** solo ve artículos derivados de sus archivos `.bib`.  
- El **supervisor**, **administrador** y **dueño del proyecto** pueden ver todos los artículos y archivos.  
- El **dueño del proyecto** ve en **Mis proyectos**:  
  - Título del proyecto  
  - Categoría  
  - Artículos en proceso  
  - Artículos finalizados  

---

## Administrador
- Es administrador a nivel de toda la aplicación.  
- Puede ver un **dashboard** con estadísticas de usuarios.  
- Dentro de un proyecto que no sea suyo no tiene control, debe enviar solicitud para ser colaborador.  
- Tiene las mismas funciones que un **investigador**, pero además:  
  - Puede crear proyectos propios.  
  - Tiene un menú de **Seguridad** para cambiar roles globales (invitado ↔ investigador).  
