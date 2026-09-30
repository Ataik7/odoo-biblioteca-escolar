from odoo import models, fields, api
from odoo.exceptions import UserError # type: ignore
from ..validators.isbn_validator import ISBNValidator


class BookSearchResult(models.TransientModel):
    """
    Resultado individual de búsqueda de libro.
    """

    _name = 'png_biblioteca.book.search.result'
    _description = 'Resultado de Búsqueda de Libro'

    # Relación con wizard
    wizard_id = fields.Many2one(
        'png_biblioteca.book.search.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    # Datos del libro
    title = fields.Char(string='Título', required=True)
    author = fields.Char(string='Autor')
    isbn = fields.Char(string='ISBN')
    year = fields.Integer(string='Año')

    # Portadas
    cover_id = fields.Char(string='ID de Portada (Open Library)')
    cover_url = fields.Char(string='URL de Portada')

    # Categoría
    suggested_category = fields.Char(string='Categoría Sugerida')

    # Libro de la biblioteca con el mismo ISBN (si ya se importó)
    existing_book_id = fields.Many2one(
        'png_biblioteca.book',
        string='Libro existente',
        compute='_compute_existing_book',
    )

    # Open Library a veces tiene ISBN con el dígito de control mal
    isbn_valid = fields.Boolean(string='ISBN válido', compute='_compute_isbn_valid')

    @api.depends('isbn')
    def _compute_isbn_valid(self):
        """
        Indica si el ISBN recibido de la API supera la validación del dígito de control.
        """

        for result in self:
            result.isbn_valid = bool(result.isbn) and ISBNValidator.is_valid(result.isbn)

    @api.depends('isbn', 'isbn_valid')
    def _compute_existing_book(self):
        """
        Busca si ya existe en la biblioteca un libro con el mismo ISBN.
        """

        Book = self.env['png_biblioteca.book']
        for result in self:
            result.existing_book_id = Book.search([('isbn', '=', result.isbn)], limit=1) if result.isbn_valid else False

    def action_open_existing(self):
        """
        Botón: Abre la ficha del libro que ya está en la biblioteca.
        """

        self.ensure_one()
        return {
            'name': 'Libro en biblioteca',
            'type': 'ir.actions.act_window',
            'res_model': 'png_biblioteca.book',
            'res_id': self.existing_book_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_import(self):
        """Importar este libro a la biblioteca."""
        self.ensure_one()
        Book = self.env['png_biblioteca.book']

        try:
            category_id = self.wizard_id.category_id.id if self.wizard_id.category_id else False

            if not category_id and self.suggested_category:
                category = self.env['png_biblioteca.category'].search([
                    ('name', '=', self.suggested_category)
                ], limit=1)

                if category:
                    category_id = category.id

            book = Book.create_from_search_result({
                'title': self.title,
                'author': self.author,
                'year': self.year,
                'cover_id': self.cover_id,
                'cover_url': self.cover_url,
                # Si el ISBN de la API no es válido, se importa sin él
                'isbn': self.isbn if self.isbn_valid else False,
                'category_id': category_id
            })

            return {
                'name': 'Libro Importado',
                'type': 'ir.actions.act_window',
                'res_model': 'png_biblioteca.book',
                'res_id': book.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except Exception as e:
            raise UserError(f"Error al importar libro: {str(e)}")