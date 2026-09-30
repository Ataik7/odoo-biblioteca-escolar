# Biblioteca Escolar para Odoo 17

Módulo de Odoo 17 (`png_biblioteca`) para gestionar una biblioteca escolar: libros, usuarios, préstamos y categorías. Los libros se pueden importar automáticamente desde Open Library y Google Books. El repositorio incluye un entorno Docker para arrancarlo todo con un comando.

## Funcionalidades

### Libros
- Catálogo con portada, autor, editorial, páginas, sinopsis y categorías de colores.
- Validación de ISBN-10 e ISBN-13 (dígito de control) y detección de duplicados aunque el ISBN se escriba con guiones.
- El estado del libro (*Disponible* o *Prestado*) se actualiza solo.
- Botón *Actualizar datos ISBN* para completar la ficha con datos de internet.

### Búsqueda e importación
- Asistente para buscar en Open Library por título, autor o ISBN.
- Filtro por idioma (español, inglés, catalán, francés o todos) que devuelve la edición en ese idioma.
- El asistente completa las páginas y la sinopsis con Google Books y con los datos de la obra en Open Library.
- En los resultados se marcan los libros que ya están en la biblioteca y los que tienen un ISBN no válido.
- Al importar, el libro recibe su categoría automáticamente y se descarga la portada.

### Préstamos
- Estados: *En curso*, *Vencido*, *Devuelto* y *Entregado tarde*.
- Cada usuario puede tener como máximo 3 préstamos activos, y cada préstamo dura como máximo 30 días.
- Botones para devolver el libro y para extender el préstamo 7 días.
- Ticket de préstamo en PDF.
- Historial de cambios y mensajes automáticos en el chatter.
- Vistas kanban, lista, gráfico y tabla dinámica.

### Tareas programadas
- Cada día se actualizan los préstamos vencidos y se avisa el primer día de retraso.
- Recordatorio de los préstamos que vencen en los próximos 3 días.
- Historial de tareas con el resultado de cada ejecución.

### Seguridad
| Grupo | Permisos |
|---|---|
| Usuario de Biblioteca | Consulta libros, usuarios y préstamos |
| Bibliotecario | Crea y gestiona préstamos, libros y usuarios |
| Administrador de Biblioteca | Todo, incluido borrar y ver el historial de tareas |

## Requisitos
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Opcional: una clave gratuita de la Google Books API (ver más abajo)

## Instalación

1. Clona el repositorio:
   ```bash
   git clone https://github.com/Ataik7/odoo-biblioteca-escolar.git
   cd odoo-biblioteca-escolar
   ```
2. Crea tu archivo de configuración a partir de la plantilla:
   ```bash
   cp odoo/config/odoo.conf.template odoo/config/odoo.conf
   ```
3. Arranca los contenedores (la primera vez tarda unos minutos porque se construye la imagen de Odoo):
   ```bash
   docker compose up -d
   ```
4. Abre http://localhost:8069 y crea una base de datos. La *Master Password* por defecto es `admin`, y si quieres datos de ejemplo, marca *Demo Data*. Después instala la aplicación **Biblioteca Escolar** desde *Aplicaciones*.

| Servicio | URL |
|---|---|
| Odoo | http://localhost:8069 |
| pgAdmin | http://localhost:8081 |

Para entrar en pgAdmin, usa el usuario `admin@admin.com` y la contraseña `Passw0rd`. La contraseña de la base de datos es `odoo`. La primera vez que arrancas los contenedores, pgAdmin tarda unos segundos en estar disponible.

## Clave de Google Books (opcional)
El módulo funciona sin clave, pero entonces Google suele responder "cuota agotada" y las fichas pueden quedarse sin páginas o sin sinopsis en español.

1. Entra en https://console.cloud.google.com/ y crea un proyecto.
2. En *APIs y servicios → Biblioteca*, habilita **Books API**.
3. En *Credenciales → Crear credenciales → Clave de API*, crea la clave y restríngela a Books API.
4. Añádela en `odoo/config/odoo.conf` y reinicia Odoo (`docker restart odoo1`):
   ```ini
   google_books_api_key = TU_CLAVE
   ```

`odoo.conf` está en el `.gitignore`, así que tu clave no se sube al repositorio.

## Tests
El módulo tiene 46 tests que cubren libros, préstamos, usuarios, permisos, tareas programadas y búsqueda. No necesitan conexión a internet porque las llamadas a la API están simuladas.

```bash
docker exec odoo1 odoo -d NOMBRE_BD --db_host=db --db_user=odoo --db_password=odoo -u png_biblioteca --test-enable --test-tags /png_biblioteca --stop-after-init --no-http
```

## Estructura del módulo
```
odoo/addons/png_biblioteca/
├── models/       # Libro, préstamo, usuario, categoría, asistente de búsqueda, historial
├── helpers/      # Lógica de negocio (préstamos, libros, usuarios, categorías)
├── validators/   # Validaciones (ISBN, libros, préstamos, usuarios)
├── services/     # Conexión con Open Library y Google Books
├── jobs/         # Tareas programadas (cron)
├── views/        # Vistas, menús y asistente
├── reports/      # Ticket de préstamo en PDF
├── security/     # Grupos y permisos
├── data/         # Categorías y tareas programadas
├── demo/         # Datos de ejemplo
└── tests/        # Tests automáticos
```

## Tecnologías
Odoo 17 · Python 3 · PostgreSQL 15 · pgAdmin 4 · Docker Compose · Open Library API · Google Books API

## Créditos y licencia
- El módulo `png_biblioteca` se distribuye con licencia LGPL-3.
- El entorno Docker y `set_permissions.sh` se basan en el trabajo de [javnitram](https://github.com/javnitram), con licencia GPL-3 (ver `LICENSE`).