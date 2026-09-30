import logging

_logger = logging.getLogger(__name__)

class CategoryHelper:
    """
    Helper para acciones y transformaciones de categorías.
    """

    @staticmethod
    def get_book_action(category):
        """
        Genera acción para ver libros de la categoría.

        Args:
            category: Registro de categoría.

        Returns:
            dict: Acción de ventana de Odoo.
        """

        _logger.info(f"📂 Abriendo libros de categoría: '{category.name}' (ID: {category.id})")

        return {
            'type': 'ir.actions.act_window',
            'name': f'Libros de {category.name}',
            'res_model': 'png_biblioteca.book',
            'view_mode': 'tree,form,kanban',
            'domain': [('category_ids', 'in', category.id)],
            'context': {'default_category_ids': [category.id]},
            'target': 'current',
        }