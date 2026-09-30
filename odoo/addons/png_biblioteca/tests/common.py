from datetime import timedelta
from odoo import fields  # type: ignore
from odoo.tests.common import TransactionCase  # type: ignore


class BibliotecaCase(TransactionCase):
    """
    Base común de los tests de la biblioteca.

    Crea usuarios y libros de prueba una sola vez por clase
    y ofrece un atajo para crear préstamos.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.today()

        cls.Book = cls.env['png_biblioteca.book']
        cls.Loan = cls.env['png_biblioteca.loan']
        cls.User = cls.env['png_biblioteca.user']

        # Usuarios de la biblioteca
        cls.student = cls.User.create({
            'name': 'Alumno Test',
            'user_type': 'student',
            'library_card': 'TST-001',
            'email': 'alumno.test@test.com',
        })
        cls.teacher = cls.User.create({
            'name': 'Profesor Test',
            'user_type': 'teacher',
            'library_card': 'TST-002',
            'email': 'profesor.test@test.com',
        })

        # Libros
        cls.book = cls.Book.create({'name': 'Libro de Prueba', 'isbn': '9780000000002'})
        cls.book2 = cls.Book.create({'name': 'Segundo Libro de Prueba'})

    @classmethod
    def _create_loan(cls, book, user, days=7, loan_days_ago=0):
        """
        Crea un préstamo.

        Args:
            book (recordset): Libro a prestar.
            user (recordset): Usuario de la biblioteca.
            days (int): Días desde hoy hasta la fecha de devolución (negativo = ya pasada).
            loan_days_ago (int): Hace cuántos días se hizo el préstamo.

        Returns:
            recordset: El préstamo creado.
        """

        return cls.Loan.create({
            'book_id': book.id,
            'user_id': user.id,
            'loan_date': cls.today - timedelta(days=loan_days_ago),
            'return_date': cls.today + timedelta(days=days),
        })