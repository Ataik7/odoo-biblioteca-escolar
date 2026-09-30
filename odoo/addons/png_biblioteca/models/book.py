from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError # type: ignore
from markupsafe import Markup # type: ignore
from ..services.api_service import BookAPIService
from ..validators.isbn_validator import ISBNValidator
from ..validators.book_validator import BookValidator
from ..helpers.book_helper import BookHelper

class Book(models.Model):
    """
    Modelo Book
    Gestión de libros de la biblioteca con integración a Open Library API.
    Incluye Chatter para seguimiento de cambios y actividades.
    """

    # Nombre técnico
    _name = 'png_biblioteca.book'

    # Descripción
    _description = 'Libro'

    # Herencia para habilitar Chatter y actividades
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Ordenar libros por nombre
    _order = 'name'

    # =========================
    # Campos básicos
    # =========================

    # Título del libro
    name = fields.Char(string='Título', required=True, tracking=True, index=True)

    # Autor del libro
    author = fields.Char(string='Autor', tracking=True, index=True)

    # ISBN del libro (puede ser ISBN-10 o ISBN-13)
    isbn = fields.Char(string='ISBN', tracking=True, index=True, help="Código ISBN-10 o ISBN-13 del libro")

    # Fecha de publicación del libro
    publication_date = fields.Date(string='Fecha de Publicación', tracking=True)

    # Nombre de la editorial del libro
    publisher = fields.Char(string='Editorial', tracking=True)

    # Número total de páginas del libro
    pages = fields.Integer(string='Páginas', tracking=True)

    # Descripción del libro
    description = fields.Text(string='Descripción')

    # =========================
    # Imágenes
    # =========================

    # Imagen principal de la portada del libro
    image = fields.Image(string='Portada', max_width=1024, max_height=1024)

    # Versión reducida (128x128)
    image_128 = fields.Image(string='Imagen del libro', related='image', max_width=128, max_height=128, store=True)

    # =========================
    # Relaciones
    # =========================

    # Un libro puede pertenecer a múltiples categorías (Many2many)
    category_ids = fields.Many2many(
        'png_biblioteca.category',
        'book_category_rel',
        'book_id',
        'category_id',
        string='Categorías',
        tracking=True,
        help="Un libro puede clasificarse en múltiples categorías"
    )

    # Un libro puede tener múltiples préstamos
    loan_ids = fields.One2many('png_biblioteca.loan', 'book_id', string='Préstamos')

    # =========================
    # Campos computados
    # =========================

    # Estado del libro (disponible o prestado)
    state = fields.Selection([
        ('available', 'Disponible'),
        ('borrowed', 'Prestado'),
    ], string='Estado', compute='_compute_state', store=True, tracking=True)

    # Total de préstamos que ha tenido el libro
    total_loans_count = fields.Integer(string='Total de Préstamos', compute='_compute_loan_statistics')

    # Número de préstamos activos actualmente
    active_loans_count = fields.Integer(string='Préstamos Activos', compute='_compute_loan_statistics')

    # ISBN formateado con guiones según estándar
    isbn_formatted = fields.Char(string='ISBN Formateado', compute='_compute_isbn_formatted', help="ISBN con guiones según estándar")

    # =========================
    # Métodos computados
    # =========================

    @api.depends('loan_ids', 'loan_ids.state')
    def _compute_state(self):
        """
        Calcula el estado del libro basándose en préstamos activos.

        Estado 'borrowed' si el Helper detecta préstamos en curso o vencidos,
        de lo contrario 'available'.
        """

        for book in self:
            book.state = 'borrowed' if BookHelper.count_active_loans(book.loan_ids) > 0 else 'available'

    @api.depends('loan_ids', 'loan_ids.state')
    def _compute_loan_statistics(self):
        """
        Calcula estadísticas de préstamos del libro.
        """

        for book in self:
            book.total_loans_count = len(book.loan_ids)
            book.active_loans_count = BookHelper.count_active_loans(book.loan_ids)

    @api.depends('isbn')
    def _compute_isbn_formatted(self):
        """
        Formatea el ISBN con guiones según estándar.
        """

        for book in self:
            book.isbn_formatted = ISBNValidator.format_isbn(book.isbn) if book.isbn else ''

    # =========================
    # Validaciones Python
    # =========================

    @api.constrains('isbn')
    def _check_isbn_format(self):
        """
        Valida que el ISBN tenga un formato válido internacional.

        Raises:
            ValidationError: Si el ISBN no cumple con el algoritmo de control.
        """

        for book in self:
            if book.isbn:
                # Validar Formato Algorítmico
                BookValidator.validate_isbn_format(book.isbn)
                # Validar Unicidad en Base de Datos (evitar duplicados)
                BookValidator.validate_isbn_uniqueness(self.env, book.isbn, book.id)

    @api.constrains('name')
    def _check_title(self):
        """
        Valida que el título sea coherente y no esté vacío.

        Raises:
            ValidationError: Si el nombre contiene caracteres prohibidos o está vacío.
        """

        for book in self:
            BookValidator.validate_title(book.name)

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrescribe create para normalizar el ISBN y detectar creación manual vs API.
        """

        for vals in vals_list:
            if vals.get('isbn'):
                vals['isbn'] = ISBNValidator.clean(vals['isbn'])

        books = super(Book, self.with_context(tracking_disable=True)).create(vals_list)

        for book in books:
            if not self.env.context.get('from_api'):
                book.message_post(
                    body=Markup("📚 <strong>Libro creado manualmente</strong>"),
                    message_type='notification',
                )
        return books

    def write(self, vals):
        """
        Normaliza el ISBN antes de guardar.
        """

        if vals.get('isbn'):
            vals['isbn'] = ISBNValidator.clean(vals['isbn'])
        return super().write(vals)

    # =========================
    # Integración con API
    # =========================

    def action_fetch_from_isbn(self):
        """
        Botón: Obtiene datos del libro desde Open Library usando el ISBN.

        Returns:
            dict: Acción de notificación para el cliente.

        Raises:
            UserError: Si el campo ISBN está vacío antes de la consulta.
        """

        self.ensure_one()
        if not self.isbn:
            raise UserError("❌ Por favor, introduzca un ISBN antes de consultar a la API.")

        # Pasamos el servicio como dependencia para facilitar tests
        return BookHelper.fetch_from_isbn(self, BookAPIService)

    @api.model
    def search_books_by_title(self, title, limit=10):
        """
        Busca libros en Open Library por título.

        Args:
            title (str): Título a buscar.
            limit (int): Límite de resultados.

        Returns:
            list: Lista de diccionarios con resultados de la API.
        """

        if not title:
            return []
        return BookAPIService.search_by_title(title, limit)

    @api.model
    def search_books_by_author(self, author, limit=10):
        """
        Busca libros en Open Library por autor.

        Args:
            author (str): Nombre del autor.
            limit (int): Límite de resultados.

        Returns:
            list: Lista de diccionarios con resultados de la API.
        """

        if not author:
            return []
        return BookAPIService.search_by_author(author, limit)

    @api.model
    def create_from_isbn(self, isbn, category_id=False):
        """
        Crea un libro automáticamente desde un ISBN.

        Args:
            isbn (str): ISBN del libro.
            category_id (int/bool): ID de la categoría opcional.

        Returns:
            recordset: El registro del libro creado.

        Raises:
            ValidationError: Si no se proporciona un ISBN.
        """

        if not isbn:
            raise ValidationError("El parámetro ISBN es obligatorio.")
        return BookHelper.create_from_isbn(self.env, isbn, category_id, BookAPIService)

    @api.model
    def create_from_search_result(self, vals):
        """
        Crea un libro desde resultado de búsqueda del wizard.
        Delega la lógica al helper para mantener separación de responsabilidades.

        Args:
            vals (dict): Datos del wizard (title, author, isbn, etc.)

        Returns:
            recordset: Libro creado
        """

        return BookHelper.create_from_search_result(self.env, vals, BookAPIService)

    # =========================
    # Acciones de usuario
    # =========================

    def action_view_loans(self):
        """
        Botón: Muestra todos los préstamos del libro.

        Returns:
            dict: Acción ir.actions.act_window para mostrar los préstamos.
        """

        self.ensure_one()
        return BookHelper.get_loans_action(self)


    def action_view_active_loans(self):
        """
        Botón: Muestra solo los préstamos activos del libro.
        """

        self.ensure_one()
        action = BookHelper.get_loans_action(self)
        action['domain'] = [('book_id', '=', self.id), ('state', 'in', ['ongoing', 'overdue'])]
        return action