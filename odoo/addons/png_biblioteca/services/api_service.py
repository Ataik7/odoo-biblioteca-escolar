import requests  # type: ignore
import logging
from ..validators.isbn_validator import ISBNValidator
from odoo.tools import config  # type: ignore

_logger = logging.getLogger(__name__)

class BookAPIService:
    """
    Servicio híbrido para interactuar con las APIs de Open Library y Google Books.
    Centraliza la obtención de metadatos externos para el catálogo.
    """

    # =========================
    # Configuración y atributos
    # =========================

    OL_BASE_URL = "https://openlibrary.org"
    GOOGLE_BASE_URL = "https://www.googleapis.com/books/v1"

    TIMEOUT = 10
    EDITION_TIMEOUT = 5

    # Campos que pedimos a la búsqueda, incluida la edición que coincide con el idioma
    SEARCH_FIELDS = (
        "key,title,author_name,first_publish_year,cover_i,isbn,subject,cover_edition_key,"
        "editions,editions.title,editions.isbn,editions.cover_i,editions.publish_year"
    )

    # Sesión persistente para optimizar rendimiento
    _session = requests.Session()

    # Para identificarnos para evitar baneos de IPs
    _session.headers.update({
        'User-Agent': 'Odoo-Library-Module/1.0 (Biblioteca Escolar)',
        'Accept': 'application/json',
    })

    # =========================
    # Métodos de Google Books
    # =========================

    @classmethod
    def get_google_data(cls, isbn):
        """
        Obtiene metadata de Google Books API.
        Incluye la URL de la portada si está disponible.
        """

        if not isbn:
            return {}

        isbn_clean = ISBNValidator.clean(isbn)
        params = {'q': f"isbn:{isbn_clean}"}

        # Clave propia de Google Books (odoo.conf). Sin ella se comparte un cupo anónimo que suele estar agotado
        api_key = config.get('google_books_api_key')
        if api_key:
            params['key'] = api_key

        try:
            response = cls._session.get(f"{cls.GOOGLE_BASE_URL}/volumes", params=params, timeout=cls.TIMEOUT)
            if response.status_code == 429:
                _logger.warning("⚠️ Google Books: cuota agotada. Añade 'google_books_api_key' en odoo.conf")
                return {}
            response.raise_for_status()
            data = response.json()
            items = data.get('items', [])
            if items:
                volume_info = items[0].get('volumeInfo', {})

                # Portadas
                image_links = volume_info.get('imageLinks', {})
                cover_url = image_links.get('thumbnail') or image_links.get('smallThumbnail')
                if cover_url:
                    cover_url = cover_url.replace('http://', 'https://')

                # Formateo de fecha a año
                raw_date = volume_info.get('publishedDate', '')
                clean_year = raw_date.split('-')[0] if raw_date else False

                return {
                    'title': volume_info.get('title'),
                    'author': ", ".join(volume_info.get('authors', [])),
                    'description': volume_info.get('description', ''),
                    'pages': volume_info.get('pageCount', 0),
                    'publisher': volume_info.get('publisher', ''),
                    'year': clean_year if clean_year else None,
                    'categories': volume_info.get('categories', []),
                    'cover_url': cover_url,
                }

        except Exception as e:
            _logger.warning(f"⚠️ Error con Google Books: {str(e)}")

        return {}

    # =========================
    # Acciones de usuario
    # =========================

    @classmethod
    def search_by_title(cls, title, limit=10, language=None):
        """
        Busca libros por título en Open Library.

        Args:
            title (str): El título o parte del título a buscar.
            limit (int): Número máximo de resultados a retornar. Default 10.
            language (str): Código de idioma para filtrar los resultados (spa, eng...).

        Returns:
            list[dict]: Lista de libros procesados con formato estandarizado.
        """

        _logger.info("🔍 Buscando en Open Library por título: %s (idioma: %s)", title, language or 'todos')
        return cls._search(title, limit, language)

    @classmethod
    def search_by_author(cls, author, limit=10, language=None):
        """
        Busca libros por autor en Open Library.

        Args:
            author (str): Nombre del autor.
            limit (int): Número máximo de resultados.
            language (str): Código de idioma para filtrar los resultados (spa, eng...).

        Returns:
            list[dict]: Resultados estandarizados.
        """

        _logger.info("🔍 Buscando en Open Library por autor: %s (idioma: %s)", author, language or 'todos')
        return cls._search(f'author:"{author}"', limit, language)

    @classmethod
    def _search(cls, query, limit, language=None):
        """
        Lanza una búsqueda general en Open Library.

        Usa el parámetro 'q', que busca también en los títulos de todas las ediciones
        (no solo en el título original de la obra). Si se indica idioma, se añade
        'language:xxx' a la consulta y Open Library devuelve la edición en ese idioma.

        Args:
            query (str): Texto de búsqueda (o 'author:"..."').
            limit (int): Número máximo de resultados.
            language (str): Código de idioma de 3 letras o None para todos.

        Returns:
            list[dict]: Resultados estandarizados.
        """

        if language:
            query = f"{query} language:{language}"

        params = {'q': query, 'limit': limit, 'fields': cls.SEARCH_FIELDS}

        try:
            response = cls._session.get(f"{cls.OL_BASE_URL}/search.json", params=params, timeout=cls.TIMEOUT)
            response.raise_for_status()
            return cls._process_search_results(response.json().get('docs', []), limit)
        except Exception as e:
            _logger.error(f"❌ Error en la búsqueda '{query}': {str(e)}")
            return []

    @classmethod
    def get_book_by_isbn(cls, isbn):
        """
        Obtiene información completa de un libro por ISBN intentando
        múltiples endpoints de la API en orden de exhaustividad.

        Args:
            isbn (str): ISBN-10 o ISBN-13.

        Returns:
            dict|None: Datos del libro normalizados o None si no se encuentra.
        """

        isbn_clean = ISBNValidator.clean(isbn)

        # Si un endpoint falla o no tiene datos, se intenta con el siguiente para maximizar la tasa de éxito.
        for method in [cls._try_books_api, cls._try_isbn_api, cls._try_search_api]:
            book_data = method(isbn_clean)
            if book_data:
                # Completamos autor, páginas y sinopsis si la edición no los trae
                missing_author = book_data.get('author') in (None, '', 'Autor desconocido')
                if missing_author or not book_data.get('pages') or not book_data.get('description'):
                    extra = cls.get_work_data(isbn_clean)
                    if missing_author and extra.get('author'):
                        book_data['author'] = extra['author']
                    for key in ('pages', 'description'):
                        if not book_data.get(key) and extra.get(key):
                            book_data[key] = extra[key]
                return book_data

        _logger.warning(f"⚠️ No se encontró información para ISBN: {isbn}")
        return None

    @classmethod
    def get_work_data(cls, isbn_clean):
        """
        Obtiene datos que no suelen venir en la edición: autor, páginas y sinopsis.

        - Autor y sinopsis: de la obra (común a todas sus ediciones).
        - Páginas: de la edición; si no las tiene, de otra edición de la misma obra
          en el mismo idioma (valor aproximado).

        Args:
            isbn_clean (str): ISBN normalizado.

        Returns:
            dict: Puede contener 'author', 'pages' y/o 'description'.
        """

        result = {}
        try:
            response = cls._session.get(f"{cls.OL_BASE_URL}/isbn/{isbn_clean}.json", timeout=cls.TIMEOUT)
            if not response.ok:
                return result
            edition = response.json()

            if edition.get('number_of_pages'):
                result['pages'] = edition['number_of_pages']

            works = edition.get('works') or []
            if not works:
                return result
            work_key = works[0]['key']

            work_resp = cls._session.get(f"{cls.OL_BASE_URL}{work_key}.json", timeout=cls.TIMEOUT)
            if work_resp.ok:
                work = work_resp.json()

                # La descripción puede venir como texto o como {'value': '...'}
                desc = work.get('description')
                if isinstance(desc, dict):
                    desc = desc.get('value')
                if desc:
                    result['description'] = desc

                # Autor: la obra solo trae la clave (/authors/OL...A), hay que pedir el nombre
                authors = work.get('authors') or []
                if authors and authors[0].get('author', {}).get('key'):
                    author_resp = cls._session.get(
                        f"{cls.OL_BASE_URL}{authors[0]['author']['key']}.json", timeout=cls.EDITION_TIMEOUT)
                    if author_resp.ok and author_resp.json().get('name'):
                        result['author'] = author_resp.json()['name']

            # Páginas aproximadas: otra edición de la misma obra en el mismo idioma
            if not result.get('pages'):
                languages = {l.get('key') for l in edition.get('languages', [])}
                eds_resp = cls._session.get(f"{cls.OL_BASE_URL}{work_key}/editions.json",
                                            params={'limit': 100}, timeout=cls.TIMEOUT)
                if eds_resp.ok:
                    for ed in eds_resp.json().get('entries', []):
                        ed_languages = {l.get('key') for l in ed.get('languages', [])}
                        if ed.get('number_of_pages') and (not languages or languages & ed_languages):
                            result['pages'] = ed['number_of_pages']
                            break

        except (requests.RequestException, ValueError) as e:
            _logger.warning(f"⚠️ No se pudieron obtener datos de la obra para {isbn_clean}: {e}")
        return result

    @classmethod
    def download_cover(cls, cover_url_or_id):
        """
        Descarga los bytes de una imagen de portada.

        Args:
            cover_url_or_id (str): URL completa de la imagen o el ID numérico.

        Returns:
            bytes|None: El contenido binario de la imagen o None si falla.
        """

        if not cover_url_or_id:
            return None

        url = cover_url_or_id
        # Si el parámetro es un ID numérico (ej: "12345"), construye la URL Large (L)
        if isinstance(cover_url_or_id, str) and not cover_url_or_id.startswith('http'):
            url = f"https://covers.openlibrary.org/b/id/{cover_url_or_id}-L.jpg"

        try:
            response = cls._session.get(url, timeout=cls.TIMEOUT)
            response.raise_for_status()
            return response.content
        except Exception as e:
            _logger.warning(f"⚠️ No se pudo descargar portada de {url}: {str(e)}")
            return None

    # =========================
    # Procesamiento de datos
    # =========================

    @classmethod
    def _process_search_results(cls, docs, limit):
        """Transforma los documentos raw de la API en diccionarios estructurados.

        Si la API devuelve la edición concreta (por ejemplo, la edición en español),
        se usan su título, ISBN, portada y año en lugar de los de la obra original.

        Args:
            docs (list): Lista de diccionarios (documentos) devueltos por search.json.
            limit (int): Número máximo de resultados a procesar y devolver.

        Returns:
            list: Lista de diccionarios normalizados con el formato requerido por el Wizard de búsqueda.
        """

        results = []
        for book in docs[:limit]:
            # Edición que coincide con la búsqueda (puede no venir)
            editions = book.get('editions', {}).get('docs', [])
            edition = editions[0] if editions else {}

            # ISBN: primero el de la edición, luego el de la obra
            isbn_list = edition.get('isbn') or book.get('isbn', [])
            isbn = isbn_list[0] if isbn_list else ''

            # A veces, el ISBN no viene en el primer nivel
            # Intentamos recuperarlo de la edición específica si existe
            if not isbn and book.get('cover_edition_key'):
                isbn = cls.get_isbn_from_edition(book.get('cover_edition_key'))

            # Año: el de la edición si existe (puede venir como lista)
            year = edition.get('publish_year') or book.get('first_publish_year', 0)
            if isinstance(year, list):
                year = year[0] if year else 0

            cover_id = edition.get('cover_i') or book.get('cover_i', '')

            results.append({
                'title': edition.get('title') or book.get('title', 'Sin título'),
                'author': ', '.join(book.get('author_name', ['Autor desconocido'])),
                'isbn': ISBNValidator.clean(isbn) if isbn else '',
                'year': year or 0,
                'cover_id': str(cover_id) if cover_id else '',
                'suggested_category': cls.guess_category(book.get('subject', [])),
            })
        return results

    # =========================
    # Endpoints
    # =========================

    @classmethod
    def _try_books_api(cls, isbn_clean):
        """
        Consulta el endpoint 'data' de la API para obtener información enriquecida.

        Devuelve datos estructurados y completos de autores, categorías y portadas.

        Args:
            isbn_clean (str): ISBN normalizado (solo dígitos).

        Returns:
            dict|None: Datos normalizados del libro o None si no hubo respuesta.
        """

        url = f"{cls.OL_BASE_URL}/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=data"

        try:
            response = cls._session.get(url, timeout=cls.TIMEOUT)
            data = response.json().get(f"ISBN:{isbn_clean}")
            if data:
                return cls._normalize_books_api_response(data)
        except (requests.RequestException, ValueError) as e:
            _logger.debug("Open Library api/books falló para %s: %s", isbn_clean, e)
        return None

    @classmethod
    def _try_isbn_api(cls, isbn_clean):
        """
        Consulta el endpoint directo por JSON mediante la ruta de ISBN.

        Se utiliza como alternativa para recuperar metadatos técnicos o descripciones que no están presentes en otros endpoints.

        Args:
            isbn_clean (str): ISBN normalizado (solo dígitos).

        Returns:
            dict|None: Datos normalizados o None si la petición falla.
        """

        url = f"{cls.OL_BASE_URL}/isbn/{isbn_clean}.json"

        try:
            response = cls._session.get(url, timeout=cls.TIMEOUT)
            if response.ok:
                return cls._normalize_isbn_api_response(response.json())
        except (requests.RequestException, ValueError) as e:
            _logger.debug("Open Library /isbn falló para %s: %s", isbn_clean, e)
        return None

    @classmethod
    def _try_search_api(cls, isbn_clean):
        """
        Realiza una búsqueda general filtrando específicamente por el campo ISBN.

        Actúa como último recurso de la cadena de búsqueda para ediciones con poca documentación en los endpoints principales.

        Args:
            isbn_clean (str): ISBN normalizado (solo dígitos).

        Returns:
            dict|None: Primer resultado de búsqueda normalizado o None.
        """

        url = f"{cls.OL_BASE_URL}/search.json?isbn={isbn_clean}"

        try:
            response = cls._session.get(url, timeout=cls.TIMEOUT)
            docs = response.json().get('docs', [])
            if docs:
                return cls._normalize_search_api_response(docs[0])
        except (requests.RequestException, ValueError) as e:
            _logger.debug("Open Library search.json falló para %s: %s", isbn_clean, e)
        return None

    # =========================
    # Normalizadores de datos
    # =========================

    @classmethod
    def _normalize_books_api_response(cls, data):
        """
        Normaliza la respuesta del endpoint 'jscmd=data'.
        Extrae información detallada de autores, portadas de alta resolución y temas para la categorización automática.

        Args:
            data (dict): JSON crudo retornado por el endpoint /api/books.

        Returns:
            dict: Diccionario con llaves estándar para el Wizard y el Modelo Book.
        """

        cover_dict = data.get('cover', {})
        return {
            'title': data.get('title', 'Sin título'),
            'author': (data.get('authors') or [{}])[0].get('name', 'Autor desconocido'),
            'publish_date': data.get('publish_date'),
            'cover_url': cover_dict.get('large') or cover_dict.get('medium'),
            'publisher': data.get('publishers', [{}])[0].get('name', '') if data.get('publishers') else '',
            'pages': data.get('number_of_pages', 0),
            'description': str(data.get('notes', '')),
            'suggested_category': cls.guess_category([s.get('name', s) if isinstance(s, dict) else s for s in data.get('subjects', [])]),
        }

    @classmethod
    def _normalize_isbn_api_response(cls, data):
        """
        Normaliza la respuesta técnica del endpoint directo por ISBN.
        Maneja específicamente las descripciones complejas (objetos o strings) y reconstruye la URL de la portada mediante el ID de la edición.

        Args:
            data (dict): JSON crudo retornado por el endpoint /isbn/{isbn}.json.

        Returns:
            dict: Datos normalizados incluyendo limpieza de descripción.
        """

        cover_id = data.get('covers', [None])[0]
        # Procesa descripciones que pueden venir como string o como diccionario {'value': '...'}
        desc_raw = data.get('description', '')
        description = desc_raw.get('value', '') if isinstance(desc_raw, dict) else str(desc_raw)

        return {
            'title': data.get('title', 'Sin título'),
            'author': 'Autor desconocido',
            'publish_date': data.get('publish_date'),
            'cover_url': f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None,
            'publisher': data.get('publishers', [''])[0] if data.get('publishers') else '',
            'pages': data.get('number_of_pages', 0),
            'description': description,
            'suggested_category': cls.guess_category(data.get('subjects', [])),
        }

    @classmethod
    def _normalize_search_api_response(cls, doc):
        """
        Normaliza el primer documento encontrado por el motor de búsqueda general.
        Útil para capturar metadatos básicos de ediciones que no responden en los endpoints estructurados.

        Args:
            doc (dict): Primer elemento de la lista 'docs' del search.json.

        Returns:
            dict: Estructura básica de libro con autor concatenado.
        """

        cover_id = doc.get('cover_i')
        return {
            'title': doc.get('title', 'Sin título'),
            'author': ', '.join(doc.get('author_name', ['Autor desconocido'])),
            'publish_date': str(doc.get('first_publish_year', '')),
            'cover_url': f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None,
            'publisher': doc.get('publisher', [''])[0] if doc.get('publisher') else '',
            'pages': 0,
            'description': '',
            'suggested_category': cls.guess_category(doc.get('subject', [])),
        }

    # =========================
    # Herramientas de apoyo
    # =========================

    @classmethod
    def get_isbn_from_edition(cls, edition_key):
        """
        Recupera el identificador ISBN consultando una edición específica.

        Se utiliza cuando la búsqueda principal devuelve llaves de edición (Work/Edition) en lugar de metadatos directos.
        Prioriza el estándar ISBN-13 sobre el ISBN-10.

        Args:
            edition_key (str): Identificador único de edición (ej. 'OL12345M').

        Returns:
            str: ISBN encontrado o un string vacío si la consulta falla.
        """

        try:
            url = f"{cls.OL_BASE_URL}/books/{edition_key}.json"
            response = cls._session.get(url, timeout=cls.EDITION_TIMEOUT)
            if response.ok:
                data = response.json()
                # Prioriza ISBN-13 sobre ISBN-10
                isbns = data.get('isbn_13') or data.get('isbn_10') or ['']
                return isbns[0]
        except (requests.RequestException, ValueError) as e:
            _logger.debug("No se pudo obtener el ISBN de la edición %s: %s", edition_key, e)
        return ''

    @classmethod
    def guess_category(cls, subjects):
        """
        Clasifica el libro en categorías internas basadas en etiquetas de la API.

        Args:
            subjects (list): Lista de temas devueltos por la API.

        Returns:
            str|None: Nombre de la categoría mapeada o None.
        """

        if not subjects: return None

        # Analizamos solo los primeros 5 temas
        subjects_lower = [str(s).lower() for s in subjects[:5]]

        category_map = {
            'Ficción': ['fiction', 'novel', 'fantasy', 'ficción', 'novela', 'literature', 'drama'],
            'Ciencia': ['science', 'biology', 'physics', 'chemistry', 'mathematics', 'nature'],
            'Historia': ['history', 'historical', 'biography', 'historia', 'politics'],
            'Tecnología': ['technology', 'computer', 'programming', 'software', 'engineering'],
            'Infantil': ['children', 'kids', 'juvenile', 'infantil', 'youth'],
        }

        for category, keywords in category_map.items():
            if any(any(k in s for k in keywords) for s in subjects_lower):
                return category

        return None

