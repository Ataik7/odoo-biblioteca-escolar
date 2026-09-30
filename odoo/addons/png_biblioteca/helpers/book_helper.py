import base64
import random
from datetime import date
from odoo.exceptions import UserError, ValidationError # type: ignore
from ..validators.isbn_validator import ISBNValidator
from ..services.api_service import BookAPIService
from markupsafe import Markup # type: ignore
import logging

_logger = logging.getLogger(__name__)


class BookHelper:
    """
    Helper para la gestión, transformación y enriquecimiento de datos de libros.

    Esta clase centraliza la lógica de negocio para interactuar con APIs externas
    (Google Books y Open Library), normalizar metadatos y gestionar la persistencia en Odoo.
    """

    # =========================
    # Transformaciones de datos
    # =========================

    @staticmethod
    def parse_publish_date(publish_date_str):
        """
        Limpia y convierte una cadena de texto en un objeto de fecha válido.

        Args:
            publish_date_str (str): Cadena que contiene el año o fecha (ej: "2025", "Oct 2024").

        Returns:
            date: Objeto date de Python (1 de enero del año detectado) o None si falla.
        """

        if not publish_date_str:
            return None

        try:
            year_str = ''.join(filter(str.isdigit, str(publish_date_str)))
            if len(year_str) >= 4:
                year = int(year_str[: 4])

                # Validación de rango para evitar años erróneos en la base de datos externa
                if 1000 <= year <= date.today().year + 1:
                    return date(year, 1, 1)
                _logger.warning(f"Año fuera de rango válido: {year}")
        except (ValueError, TypeError) as e:
            _logger.warning(f"No se pudo parsear la fecha: '{publish_date_str}' - {str(e)}")
        return None

    @staticmethod
    def get_cover_url(cover_id, size='L'):
        """
        Construye la URL oficial de descarga de portadas de Open Library.

        Args:
            cover_id (str): Identificador numérico de la portada en Open Library.
            size (str): Tamaño deseado ('S', 'M', 'L'). Por defecto 'L'.

        Returns:
            str: URL completa de la imagen.
        """

        if not cover_id:
            return None

        valid_sizes = ['S', 'M', 'L']
        size = size.upper()
        if size not in valid_sizes:
            raise ValidationError(f"Tamaño de portada inválido: '{size}'. Tamaños válidos: {', '.join(valid_sizes)}")

        return f"https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"

    @staticmethod
    def format_author_list(author_list):
        """
        Normaliza la representación de autores a una cadena de texto única.

        Args:
            author_list (list|str): Lista de nombres o string único.

        Returns:
            str: Nombres concatenados por comas o 'Autor desconocido'.
        """

        if not author_list:
            return 'Autor desconocido'
        if isinstance(author_list, list):
            return ', '.join(author_list)
        return str(author_list)

    @staticmethod
    def transform_api_book_data(api_data, isbn=None):
        """
        Motor de datos de entrada que combina datos de Open Library y Google Books.

        Prioriza los datos de Google Books para campos como descripción y páginas, ya que suelen ser más precisos y extensos.

        Args:
            api_data (dict): Diccionario base con datos (título, autor, etc.).
            isbn (str, optional): ISBN para realizar la búsqueda en Google Books.

        Returns:
            dict: Diccionario normalizado con las claves listas para Odoo.
        """

        if not isinstance(api_data, dict):
            raise ValidationError("api_data debe ser un diccionario")

        _logger.info("📦 Datos de entrada para transformar (ISBN %s): %s", isbn, api_data)

        # Mapeo de campos base
        transformed = {
            'name': api_data.get('title') or api_data.get('name'),
            'author': BookHelper.format_author_list(api_data.get('author')),
            'publisher': api_data.get('publisher', ''),
            'pages': api_data.get('pages', 0),
            'description': api_data.get('description') or "Sin descripción disponible.",
            'suggested_category': api_data.get('suggested_category')
        }

        # Procesamiento de la fecha de publicación
        raw_date = api_data.get('publish_date') or api_data.get('year')
        if raw_date:
            transformed['publication_date'] = BookHelper.parse_publish_date(str(raw_date))

        # Enriquecimiento secundario con Google Books
        if isbn:
            _logger.info("🔍 Enriqueciendo con Google Books para ISBN: %s", isbn)

            google_data = BookAPIService.get_google_data(isbn)

            _logger.info("📚 Datos de Google Books recibidos: %s", google_data)

            if google_data:
                _logger.info("✅ Enriqueciendo datos con Google Books")

                if google_data.get('categories'):
                    transformed['suggested_category'] = google_data['categories'][0]

                if google_data.get('description'):
                    transformed['description'] = google_data['description']

                # Google suele tener las páginas exactas de la edición: tienen prioridad
                if google_data.get('pages'):
                    transformed['pages'] = google_data['pages']

                # Si Open Library no conocía el autor, usamos el de Google
                if transformed.get('author') == 'Autor desconocido' and google_data.get('author'):
                    transformed['author'] = google_data['author']

                # Corrección de fechas genéricas
                google_year = google_data.get('year')
                current_date = transformed.get('publication_date')
                if google_year and (not current_date or current_date.year == 1970):
                    transformed['publication_date'] = BookHelper.parse_publish_date(str(google_year))
            else:
                _logger.warning("⚠️ Google Books no devolvió datos para ISBN: %s", isbn)

        _logger.info("📦 Datos finales transformados: %s", transformed)
        return transformed

    @staticmethod
    def count_active_loans(loan_ids):
        """
        Cuenta los préstamos que se consideran 'activos' (en curso o atrasados).

        Args:
            loan_ids (recordset): Conjunto de registros de préstamos de Odoo.

        Returns:
            int: Número de préstamos activos.
        """

        if not loan_ids:
            return 0

        # Filtramos por estados que impiden que el libro esté físicamente en la biblioteca
        return len(loan_ids.filtered(lambda l: l.state in ['ongoing', 'overdue']))

    @staticmethod
    def get_or_create_category(env, suggested_category):
        """
        Obtiene o crea una categoría aplicando un mapeo de traducción Inglés-Español.

        Args:
            env (odoo.api.Environment): Entorno de Odoo.
            suggested_category (str): Categoría sugerida por la API.

        Returns:
            int|bool: ID del registro o False si hay error.
        """

        if not suggested_category or not isinstance(suggested_category, str):
            return False

        # Diccionario de traducción
        mapping = {
            'Juvenile Nonfiction': 'Juvenil - No Ficción',
            'Juvenile Fiction': 'Infantil y Juvenil',
            'Fiction': 'Ficción',
            'Science Fiction': 'Ciencia Ficción',
            'History': 'Historia',
            'Computers': 'Tecnología e Informática',
            'Cooking': 'Cocina',
            'Religion': 'Religión',
            'Art': 'Arte'
        }

        final_name = mapping.get(suggested_category, suggested_category)

        Category = env['png_biblioteca.category']
        category = Category.search([('name', '=', final_name)], limit=1)

        if category:
            return category.id

        try:
            # Color aleatorio (1-11) para que la etiqueta se vea en el kanban
            category = Category.create({'name': final_name, 'color': random.randint(1, 11)})
            _logger.info(f"🆕 Nueva categoría creada: {final_name}")
            return category.id
        except Exception as e:
            _logger.warning(f"⚠️ Error al crear categoría '{final_name}': {str(e)}")
            return False

    @staticmethod
    def _download_and_set_cover(book, cover_url, openlibrary_service):
        """
        Descarga la imagen de portada y la guarda en el campo binario de Odoo.

        Args:
            book (recordset): El registro del libro.
            cover_url (str): URL de la imagen.
            openlibrary_service: Servicio de comunicación con la API.
        """

        try:
            if not cover_url:
                return

            # Corrige URLs con la extensión mal escrita (.jppg)
            clean_url = cover_url.replace('.jppg', '.jpg')

            cover_data = openlibrary_service.download_cover(clean_url)
            if cover_data:
                # Odoo requiere Base64 para campos de imagen
                book.image = base64.b64encode(cover_data)
                _logger.info("🖼️ Portada descargada")
        except Exception as e:
            _logger.warning(f"⚠️ No se pudo descargar portada desde {cover_url}: {str(e)}")

    # =========================
    # Acciones desde API
    # =========================

    @staticmethod
    def fetch_from_isbn(book, openlibrary_service):
        """
        Actualiza un libro existente en la base de datos usando metadatos de APIs externas.

        Valida el ISBN, consulta Open Library y enriquece los datos con Google Books
        antes de realizar la escritura en el registro.

        Args:
            book (recordset): Registro del libro (`png_biblioteca.book`) a actualizar.
            openlibrary_service (OpenLibraryService): Instancia del servicio de API.

        Returns:
            dict: Acción de Odoo para mostrar una notificación de éxito en la interfaz.

        Raises:
            ValidationError: Si el registro del libro no es válido.
            UserError: Si el ISBN falta, es inválido o no se encuentran datos.
        """

        if not book:
            raise ValidationError("Se requiere un registro de libro válido")

        # Validación previa a la llamada de API para ahorrar recursos de red
        if not book.isbn:
            raise UserError("❌ Debe ingresar un ISBN primero.")
        if not ISBNValidator.is_valid(book.isbn):
            raise UserError(f"❌ ISBN inválido: '{book.isbn}'")

        book_data = openlibrary_service.get_book_by_isbn(book.isbn)
        if not book_data:
            raise UserError(f"❌ No se encontró información para el ISBN: {book.isbn}")

        _logger.info("📦 Datos base recibidos de Open Library: %s", book_data)

        # Transformación
        transformed = BookHelper.transform_api_book_data(book_data, isbn=book.isbn)

        # Extraemos la categoría sugerida para procesarla por separado
        suggested = transformed.pop('suggested_category', None)

        _logger.info("🏷️ Categoría identificada: %s", suggested)

        # No sobrescribimos datos que ya tiene el libro con valores vacíos o desconocidos
        placeholders = ('Autor desconocido', 'Sin descripción disponible.', 'Sin título')
        transformed = {k: v for k, v in transformed.items() if v and v not in placeholders}

        # Actualizamos campos básicos
        book.write(transformed)

        if not book.category_ids and suggested:
            _logger.info("🚀 Buscando o creando categoría: '%s'", suggested)
            cat_id = BookHelper.get_or_create_category(book.env, suggested)
            if cat_id:
                book.category_ids = [(4, cat_id)]  # (4, id) = añadir relación
                _logger.info("✅ Categoría asignada (ID: %s)", cat_id)
            else:
                _logger.warning("❌ No se pudo asignar categoría '%s'", suggested)

        # Procesamiento de imagen de portada
        if book_data.get('cover_url'):
            _logger.info("🖼️ Descargando portada desde: %s", book_data['cover_url'])
            BookHelper._download_and_set_cover(book, book_data['cover_url'], openlibrary_service)

        # Notificación en el chatter del libro
        book.message_post(body=Markup("<strong>📚 Libro actualizado desde API (ISBN: {})</strong>").format(book.isbn))

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @staticmethod
    def create_from_isbn(env, isbn, category_id, openlibrary_service):
        """
        Crea un libro automáticamente desde un ISBN.

        Args:
            env (api.Environment): Entorno de Odoo para acceder a los modelos.
            isbn (str): Identificador ISBN-10 o ISBN-13.
            category_id (int): ID de categoría preseleccionada (opcional).
            openlibrary_service (OpenLibraryService): Instancia del servicio de API.

        Returns:
            recordset: El registro del libro recién creado.

        Raises:
            UserError: Si el libro ya existe o el ISBN no arroja resultados.
        """

        isbn = ISBNValidator.clean(isbn)

        Book = env['png_biblioteca.book']

        # Verificación de duplicados antes de procesar
        if Book.search([('isbn', '=', isbn)], limit=1):
            raise UserError(f"❌ El libro con ISBN {isbn} ya existe.")

        if not ISBNValidator.is_valid(isbn):
            raise UserError(f"❌ El ISBN '{isbn}' no es válido.")

        book_data = openlibrary_service.get_book_by_isbn(isbn)
        if not book_data:
            raise UserError(f"❌ No se encontró información para el ISBN: {isbn}")

        transformed = BookHelper.transform_api_book_data(book_data, isbn=isbn)

        # Prioridad de categoría: 1. Wizard / 2. API
        final_category_id = category_id
        suggested = transformed.pop('suggested_category', None)

        if not final_category_id and suggested:
            final_category_id = BookHelper.get_or_create_category(env, suggested)
            _logger.info("📂 Categoría asignada: %s (ID: %s)", suggested, final_category_id)

        # Construcción del diccionario de valores para creación
        book_vals = {
            'name': transformed.get('name'),
            'author': transformed.get('author'),
            'isbn': isbn,
            'publication_date': transformed.get('publication_date'),
            'publisher': transformed.get('publisher'),
            'pages': transformed.get('pages'),
            'description': transformed.get('description'),
            'category_ids': [(6, 0, [final_category_id])] if final_category_id else [],
        }

        _logger.info("📦 Valores finales para crear libro: %s", book_vals)

        # Uso de with_context para evitar disparar procesos pesados o bucles de tracking en la creación inicial
        book = Book.with_context(from_api=True, tracking_disable=True).create(book_vals)

        if book_data.get('cover_url'):
            BookHelper._download_and_set_cover(book, book_data['cover_url'], openlibrary_service)

        book.message_post(body=Markup("<strong>📚 Libro creado automáticamente</strong>"))

        _logger.info("✅ Libro creado exitosamente: '%s' (ID: %s)", book.name, book.id)
        return book

    @staticmethod
    def create_from_search_result(env, vals, openlibrary_service):
        """Crea un libro desde resultado de búsqueda del wizard

        Args:
            env (api.Environment): Entorno de Odoo.
            vals (dict): Valores provenientes del wizard de búsqueda.
            openlibrary_service (OpenLibraryService): Instancia del servicio de API.

        Returns:
            recordset: El registro del libro creado.
        """

        Book = env['png_biblioteca.book']

        # Normalización del campo ISBN
        isbn = vals.get('isbn') or vals.get('isbn_13') or vals.get('isbn_10')

        isbn = ISBNValidator.clean(isbn) if isbn else isbn

        if isbn and Book.search([('isbn', '=', isbn)], limit=1):
            raise UserError(f"❌ El libro con ISBN {isbn} ya existe.")

        vals['isbn'] = isbn

        # Si hay ISBN, intentamos completar datos
        if isbn:
            _logger.info("📖 Intentando enriquecer con Open Library para ISBN: %s", isbn)
            try:
                ol_data = openlibrary_service.get_book_by_isbn(isbn)
                if ol_data:
                    _logger.info("✅ Datos obtenidos de Open Library")
                    vals.update({
                        'publisher': ol_data.get('publisher', vals.get('publisher', '')),
                        'pages': ol_data.get('pages', vals.get('pages', 0)),
                        'description': ol_data.get('description', vals.get('description', '')),
                        'publish_date': ol_data.get('publish_date', vals.get('year')),
                        'suggested_category': ol_data.get('suggested_category', vals.get('suggested_category')),
                    })
            except Exception as e:
                _logger.warning(f"⚠️ No se pudo enriquecer con Open Library: {str(e)}")

        transformed = BookHelper.transform_api_book_data(vals, isbn=isbn)

        final_category_id = vals.get('category_id')
        suggested = transformed.pop('suggested_category', None)

        if not final_category_id and suggested:
            final_category_id = BookHelper.get_or_create_category(env, suggested)
            _logger.info("📂 Categoría asignada: %s (ID: %s)", suggested, final_category_id)

        # Construcción del diccionario de valores
        book_vals = {
            'name': transformed.get('name') or vals.get('title'),
            'author': transformed.get('author'),
            'isbn': isbn,
            'publisher': transformed.get('publisher'),
            'pages': transformed.get('pages'),
            'description': transformed.get('description'),
            'category_ids': [(6, 0, [final_category_id])] if final_category_id else [],
            'publication_date': transformed.get('publication_date'),
        }

        _logger.info("📦 Valores finales para crear libro: %s", book_vals)

        # Creación del registro
        book = Book.with_context(from_api=True, tracking_disable=True).create(book_vals)

        # Resolución de URL de portada
        cover_url = vals.get('cover_url') or (
            BookHelper.get_cover_url(vals.get('cover_id'))
            if vals.get('cover_id')
            else None
        )
        if cover_url:
            BookHelper._download_and_set_cover(book, cover_url, openlibrary_service)

        book.message_post(body=Markup("<strong>📚 Libro importado</strong>"))

        _logger.info("✅ Libro creado exitosamente: '%s' (ID: %s)", book.name, book.id)
        return book

    # =========================
    # Acciones de usuario
    # =========================

    @staticmethod
    def get_loans_action(book):
        """
        Genera acción para ver préstamos del libro.

        Args:
            book (recordset): Libro del cual se quieren ver los préstamos.

        Returns:
            dict: Diccionario de acción `ir.actions.act_window` con dominio aplicado.
        """

        if not book or not book.exists():
            raise ValidationError("Libro no válido.")

        return {
            'type': 'ir.actions.act_window',
            'name': f'Préstamos: {book.name}',
            'res_model': 'png_biblioteca.loan',
            'view_mode': 'tree,form',
            'domain': [('book_id', '=', book.id)],
            'context': {'default_book_id': book.id},
        }