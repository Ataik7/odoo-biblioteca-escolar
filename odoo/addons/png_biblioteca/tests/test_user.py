from odoo.exceptions import ValidationError  # type: ignore
from odoo.tools import mute_logger  # type: ignore
from psycopg2 import IntegrityError  # type: ignore
from .common import BibliotecaCase


class TestUser(BibliotecaCase):
    """
    Tests del modelo Usuario de biblioteca: validaciones y estadísticas.
    """

    def _user_vals(self, **extra):
        """
        Valores mínimos válidos para crear un usuario.
        """

        vals = {
            'name': 'Pepe',
            'email': 'pepe@example.com',
            'user_type': 'student',
            'library_card': 'STU001',
        }
        vals.update(extra)
        return vals

    def test_01_user_fields(self):
        """
        Validar creación de usuario con campos obligatorios.
        """

        user = self.User.create(self._user_vals())
        self.assertEqual(user.name, 'Pepe')

    def test_02_duplicate_email(self):
        """
        Verificar que el email es único (restricción SQL).
        """

        self.User.create(self._user_vals(email='test@test.com', library_card='TEA001'))

        # Capturamos IntegrityError porque es una restricción SQL (_sql_constraints)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.User.create(self._user_vals(email='test@test.com', library_card='STU002'))

    def test_03_duplicate_library_card(self):
        """
        Verificar que el número de carnet es único (restricción SQL).
        """

        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.User.create(self._user_vals(library_card='TST-001'))

    def test_04_invalid_email(self):
        """
        Un email sin formato válido se rechaza.
        """

        with self.assertRaises(ValidationError):
            self.User.create(self._user_vals(email='correo-sin-arroba'))

    def test_05_short_library_card(self):
        """
        El número de carnet debe tener al menos 4 caracteres.
        """

        with self.assertRaises(ValidationError):
            self.User.create(self._user_vals(library_card='AB'))

    def test_06_loan_statistics(self):
        """
        Los contadores de préstamos activos, vencidos y totales son correctos.
        """

        self._create_loan(self.book, self.student)
        self._create_loan(self.book2, self.student, days=-2, loan_days_ago=10)

        self.assertEqual(self.student.active_loans_count, 1)
        self.assertEqual(self.student.overdue_loans_count, 1)
        self.assertEqual(self.student.total_loans_count, 2)

    def test_07_full_info(self):
        """
        La información completa incluye nombre y carnet.
        """

        self.assertIn('Alumno Test', self.student.full_info)
        self.assertIn('TST-001', self.student.full_info)