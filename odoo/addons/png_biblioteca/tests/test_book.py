from odoo.exceptions import ValidationError  # type: ignore
from .common import BibliotecaCase


class TestBook(BibliotecaCase):
    """
    Tests del modelo Libro: validaciones de ISBN y título, y estado del libro.
    """

    def test_01_create_valid_book(self):
        """
        Prueba la creación básica de un libro.
        """

        book = self.Book.create({'name': 'Odoo Development', 'isbn': '9780000000033'})
        self.assertEqual(book.name, 'Odoo Development')
        self.assertEqual(book.state, 'available')

    def test_02_invalid_isbn_format(self):
        """
        Un ISBN con el dígito de control incorrecto se rechaza.
        """

        with self.assertRaises(ValidationError):
            self.Book.create({'name': 'Error Book', 'isbn': '123'})

    def test_03_isbn_saved_without_hyphens(self):
        """
        El ISBN se guarda sin guiones ni espacios, al crear y al modificar.
        """

        book = self.Book.create({'name': 'Con guiones', 'isbn': '978-0-00-000001-9'})
        self.assertEqual(book.isbn, '9780000000019')

        book.write({'isbn': '978 0 00 000002 6'})
        self.assertEqual(book.isbn, '9780000000026')

    def test_04_duplicate_isbn_other_format(self):
        """
        No se puede repetir un ISBN aunque se escriba con otro formato.
        """

        with self.assertRaises(ValidationError):
            self.Book.create({'name': 'Duplicado', 'isbn': '978-0-00-000000-2'})

    def test_05_isbn_formatted(self):
        """
        El campo calculado muestra el ISBN con guiones.
        """

        self.assertEqual(self.book.isbn_formatted, '978-0-000-00000-2')

    def test_06_empty_title(self):
        """
        Un título formado solo por espacios no es válido.
        """

        with self.assertRaises(ValidationError):
            self.Book.create({'name': '   '})

    def test_07_state_follows_loans(self):
        """
        El libro pasa a 'Prestado' con un préstamo activo y vuelve a 'Disponible' al devolverlo.
        """

        loan = self._create_loan(self.book, self.student)
        self.assertEqual(self.book.state, 'borrowed')
        self.assertEqual(self.book.active_loans_count, 1)

        loan.action_return_book()
        self.assertEqual(self.book.state, 'available')
        self.assertEqual(self.book.active_loans_count, 0)
        self.assertEqual(self.book.total_loans_count, 1)