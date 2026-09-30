from datetime import timedelta
from odoo.exceptions import UserError, ValidationError  # type: ignore
from .common import BibliotecaCase


class TestLoan(BibliotecaCase):
    """
    Tests del modelo Préstamo: estados, fechas, límites, extensiones y devoluciones.
    """

    # =========================
    # Estados y campos calculados
    # =========================

    def test_01_loan_ongoing(self):
        """
        Un préstamo nuevo está en curso y calcula los días restantes.
        """

        loan = self._create_loan(self.book, self.student, days=7)
        self.assertEqual(loan.state, 'ongoing')
        self.assertEqual(loan.days_remaining, 7)
        self.assertEqual(loan.overdue_days, 0)
        self.assertFalse(loan.is_due_soon)

    def test_02_due_soon(self):
        """
        Un préstamo que vence en 3 días o menos se marca como próximo a vencer.
        """

        loan = self._create_loan(self.book, self.student, days=2)
        self.assertTrue(loan.is_due_soon)

    def test_03_overdue(self):
        """
        Un préstamo con la fecha de devolución pasada está vencido.
        """

        loan = self._create_loan(self.book, self.student, days=-3, loan_days_ago=10)
        self.assertEqual(loan.state, 'overdue')
        self.assertEqual(loan.overdue_days, 3)
        self.assertEqual(loan.days_remaining, -3)

    # =========================
    # Validaciones
    # =========================

    def test_04_book_already_borrowed(self):
        """
        No se puede prestar un libro que ya está prestado.
        """

        self._create_loan(self.book, self.student)
        with self.assertRaises(ValidationError):
            self._create_loan(self.book, self.teacher)

    def test_05_user_loan_limit(self):
        """
        Un usuario no puede tener más de 3 préstamos activos.
        """

        books = self.Book.create([{'name': 'Libro límite %s' % i} for i in range(4)])
        for book in books[:3]:
            self._create_loan(book, self.student)

        with self.assertRaises(ValidationError):
            self._create_loan(books[3], self.student)
        self.assertEqual(self.student.active_loans_count, 3)

    def test_06_return_date_before_loan_date(self):
        """
        La fecha de devolución no puede ser anterior a la del préstamo.
        """

        with self.assertRaises(ValidationError):
            self._create_loan(self.book, self.student, days=-1)

    def test_07_max_duration(self):
        """
        Un préstamo no puede durar más de 30 días.
        """

        with self.assertRaises(ValidationError):
            self._create_loan(self.book, self.student, days=31)

    # =========================
    # Extender préstamo
    # =========================

    def test_08_extend(self):
        """
        Extender suma 7 días a la fecha de devolución.
        """

        loan = self._create_loan(self.book, self.student, days=10)
        loan.action_extend_loan()
        self.assertEqual(loan.return_date, self.today + timedelta(days=17))

    def test_09_extend_over_limit(self):
        """
        No se puede extender más allá de 30 días y la fecha no cambia.
        """

        loan = self._create_loan(self.book, self.student, days=20)
        loan.action_extend_loan()
        self.assertEqual(loan.return_date, self.today + timedelta(days=27))

        with self.assertRaises(ValidationError):
            loan.action_extend_loan()
        self.assertEqual(loan.return_date, self.today + timedelta(days=27))

    def test_10_extend_not_ongoing(self):
        """
        Solo se pueden extender préstamos en curso.
        """

        loan = self._create_loan(self.book, self.student, days=-2, loan_days_ago=10)
        with self.assertRaises(UserError):
            loan.action_extend_loan()

    # =========================
    # Devolver libro
    # =========================

    def test_11_return_on_time(self):
        """
        Devolver a tiempo deja el préstamo como devuelto y el libro disponible.
        """

        loan = self._create_loan(self.book, self.student)
        loan.action_return_book()

        self.assertEqual(loan.state, 'returned')
        self.assertEqual(loan.actual_return_date, self.today)
        self.assertEqual(loan.days_remaining, 0)
        self.assertEqual(self.book.state, 'available')

    def test_12_return_late(self):
        """
        Devolver después de la fecha límite deja el préstamo como entregado tarde.
        """

        loan = self._create_loan(self.book, self.student, days=-2, loan_days_ago=10)
        loan.action_return_book()

        self.assertEqual(loan.state, 'late_returned')
        self.assertEqual(loan.overdue_days, 2)

    def test_13_return_twice(self):
        """
        No se puede devolver dos veces el mismo préstamo.
        """

        loan = self._create_loan(self.book, self.student)
        loan.action_return_book()
        with self.assertRaises(UserError):
            loan.action_return_book()

    def test_14_chatter_messages(self):
        """
        Se publican mensajes en el chatter al crear, extender y devolver.
        """

        loan = self._create_loan(self.book, self.student, days=10)
        loan.action_extend_loan()
        loan.action_return_book()

        bodies = ' '.join(loan.message_ids.mapped('body'))
        self.assertIn('Préstamo creado', bodies)
        self.assertIn('Préstamo extendido', bodies)
        self.assertIn('Devuelto a Tiempo', bodies)

    def test_15_chatter_escapes_html(self):
        """
        Los nombres con HTML se muestran escapados en el chatter (protección XSS).
        """

        book = self.Book.create({'name': '<b>XSS</b>'})
        loan = self._create_loan(book, self.student)

        body = loan.message_ids.filtered(lambda m: 'Préstamo creado' in m.body)[:1].body
        self.assertIn('&lt;b&gt;XSS&lt;/b&gt;', body)
        self.assertNotIn('<b>XSS</b>', body)