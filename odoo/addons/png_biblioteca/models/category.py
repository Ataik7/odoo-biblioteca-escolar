
from odoo import models, fields, api
from odoo.exceptions import ValidationError # type: ignore
from ..helpers.category_helper import CategoryHelper

class Category(models.Model):
    """
    Modelo Category
    Representa una categoría dentro de la biblioteca.
    Permite agrupar libros por tipo o temática.
    """

    # Nombre técnico
    _name = 'png_biblioteca.category'

    # Descripción
    _description = 'Categoría de Biblioteca'

    # Ordenar categorías por nombre
    _order = 'name'

    # =========================
    # Campos básicos
    # =========================

    # Nombre de la categoría
    name = fields.Char(string="Nombre de la Categoría", required=True, index=True,
                       help="Nombre de la categoría a la que pertenece el libro.", translate=True)

    color = fields.Integer(string='Color', default=0, help="Color para el widget de tags")

    # =========================
    # Relaciones Many2many
    # =========================

    # Una categoría puede tener muchos libros (Many2many)
    book_ids = fields.Many2many(
        'png_biblioteca.book',
        'book_category_rel',
        'category_id',
        'book_id',
        string='Libros',
        help="Libros clasificados en esta categoría"
    )

    # =========================
    # Campos computados
    # =========================

    # Cantidad de libros en esta categoría
    books_count = fields.Integer(
        string='Cantidad de Libros',
        compute='_compute_books_count',
        store=True
    )

    # =========================
    # Métodos computados
    # =========================

    @api.depends('book_ids')
    def _compute_books_count(self):
        """
        Calcula la cantidad total de libros asociados a esta categoría.
        """

        for category in self:
            category.books_count = len(category.book_ids)

    # =========================
    # Validaciones Python
    # =========================

    @api.constrains('name')
    def _check_name(self):
        """
        Valida que el nombre de la categoría sea único y cumpla con requisitos mínimos.

        Raises:
            ValidationError: Si el nombre tiene menos de 3 caracteres o ya existe otra categoría con el mismo nombre.
        """

        for category in self:
            if not category.name or len(category.name.strip()) < 3:
                raise ValidationError("El nombre de la categoría debe tener al menos 3 caracteres.")

            # Buscamos si existe otra categoría con el mismo nombre (insensible a mayúsculas)
            domain = [
                ('name', '=ilike', category.name),
                ('id', '!=', category.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(f"Ya existe una categoría con el nombre '{category.name}'.")

    # =========================
    # Acciones de usuario
    # =========================

    def action_view_books(self):
        """
        Botón: Genera la acción para visualizar los libros filtrados por esta categoría.

        Returns:
            dict: Una acción de ventana de Odoo para mostrar libros.
        """

        self.ensure_one()
        return CategoryHelper.get_book_action(self)