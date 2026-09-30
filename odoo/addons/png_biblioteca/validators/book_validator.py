from odoo.exceptions import ValidationError # type: ignore
from .isbn_validator import ISBNValidator

class BookValidator:
    """
    Validador de reglas de negocio para libros.

    Proporciona métodos estáticos para centralizar la validación de datos
    antes de persistirlos en la base de datos de Odoo
    """

    @staticmethod
    def validate_isbn_format(isbn):
        """
        Valida el formato del ISBN y el dígito de control del ISBN son correctos.

        Args:
            isbn (str): Cadena de texto que contiene el ISBN (10 o 13 dígitos).

        Raises:
            ValidationError: Si el formato es inválido.
        """

        if not isbn or not str(isbn).strip():
            return

        if not ISBNValidator.is_valid(isbn):
            isbn_type = ISBNValidator.get_isbn_type(isbn)
            raise ValidationError(
                f"El ISBN '{isbn}' no tiene un formato válido.\n"
                f"Tipo detectado: {isbn_type}\n\n"
                f"Formatos válidos:\n"
                f"- ISBN-10: 10 dígitos (ej: 054792822X)\n"
                f"- ISBN-13: 13 dígitos con prefijo 978 o 979 (ej: 9780547928227)"
            )

    @staticmethod
    def validate_isbn_uniqueness(env, isbn, book_id=None):
        """
        Garantiza que no existan dos libros con el mismo ISBN en la base de datos.

        Args:
            env: Entorno de Odoo.
            isbn (str): ISBN a validar.
            book_id (int): ID del libro actual (para excluirlo en edición).

        Raises:
            ValidationError: Si ya existe otro registro con el mismo ISBN.
        """

        if not isbn or not str(isbn).strip():
            return

        isbn_clean = ISBNValidator.clean(isbn)

        Book = env['png_biblioteca.book']

        # Buscamos por el ISBN limpio
        domain = [('isbn', '=', isbn_clean)]

        if book_id:
            domain.append(('id', '!=', book_id))

        existing_book = Book.search(domain, limit=1)

        if existing_book:
            raise ValidationError(
                f"Ya existe el libro '{existing_book.name}' con el ISBN '{isbn}'."
            )

    @staticmethod
    def validate_title(title):
        """
        Valida que el título no esté vacío.

        Args:
            title (str): Título del libro.

        Raises:
            ValidationError: Si el título es inválido.
        """

        if not title or not title.strip():
            raise ValidationError("El título del libro no puede estar vacío.")