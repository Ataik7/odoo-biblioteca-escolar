from odoo import models, fields, api
from odoo.exceptions import UserError # type: ignore
from ..services.api_service import BookAPIService


class BookSearchWizard(models.TransientModel):
    """
    Wizard para buscar libros en Open Library API.
    Permite buscar por título, autor o ISBN.
    """

    _name = 'png_biblioteca.book.search.wizard'
    _description = 'Asistente de Búsqueda de Libros'

    # Tipo de búsqueda
    search_type = fields.Selection([
        ('title', 'Por Título'),
        ('author', 'Por Autor'),
        ('isbn', 'Por ISBN'),
    ], string='Tipo de Búsqueda', required=True, default='title')

    # Campos de búsqueda
    search_title = fields.Char(string='Título')
    search_author = fields.Char(string='Autor')
    search_isbn = fields.Char(string='ISBN')

    # Idioma de los resultados (código de Open Library)
    search_language = fields.Selection([
        ('spa', 'Español'),
        ('eng', 'Inglés'),
        ('cat', 'Catalán'),
        ('fre', 'Francés'),
        ('any', 'Todos'),
    ], string='Idioma', default='spa', required=True)

    # Categoría opcional
    category_id = fields.Many2one('png_biblioteca.category', string='Categoría')

    # Resultados
    result_ids = fields.One2many(
        'png_biblioteca.book.search.result',
        'wizard_id',
        string='Resultados'
    )

    # Estado
    state = fields.Selection([
        ('search', 'Búsqueda'),
        ('results', 'Resultados'),
    ], default='search')

    @api.onchange('search_type')
    def _onchange_search_type(self):
        """Limpiar campos al cambiar tipo de búsqueda."""
        self.search_title = self.search_author = self.search_isbn = False

    def action_search(self):
        """Buscar libros y mostrar resultados."""

        self.ensure_one()

        language = False if self.search_language == 'any' else self.search_language

        Book = self.env['png_biblioteca.book']

        # Limpiar resultados anteriores
        self.result_ids.unlink()
        results = []

        # Buscar según tipo
        if self.search_type == 'title':
            if not self.search_title:
                raise UserError("Debe ingresar un título para buscar.")
            results = BookAPIService.search_by_title(self.search_title, limit=10, language=language)

        elif self.search_type == 'author':
            if not self.search_author:
                raise UserError("Debe ingresar un autor para buscar.")
            results = BookAPIService.search_by_author(self.search_author, limit=10, language=language)

        elif self.search_type == 'isbn':
            if not self.search_isbn:
                raise UserError("Debe ingresar un ISBN para buscar.")

            try:
                book = Book.create_from_isbn(
                    self.search_isbn,
                    self.category_id.id if self.category_id else False
                )

                return {
                    'name': 'Libro Importado',
                    'type': 'ir.actions.act_window',
                    'res_model': 'png_biblioteca.book',
                    'res_id': book.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            except Exception as e:
                raise UserError(f"Error al importar libro por ISBN: {str(e)}")

        if not results:
            raise UserError("No se encontraron resultados para tu búsqueda.")

        # Crear registros de resultados
        result_model = self.env['png_biblioteca.book.search.result']
        for res in results:
            result_model.create({
                'wizard_id': self.id,
                'title': res.get('title', 'Sin título'),
                'author': res.get('author', 'Autor desconocido'),
                'isbn': res.get('isbn', ''),
                'year': res.get('year', 0),
                'cover_id': res.get('cover_id', ''),
                'cover_url': res.get('cover_url', ''),
                'suggested_category': res.get('suggested_category'),
            })

        self.state = 'results'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back(self):
        """Volver a la búsqueda."""
        self.state = 'search'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }