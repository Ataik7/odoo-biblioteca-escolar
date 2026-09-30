from odoo.exceptions import AccessError  # type: ignore
from odoo.tests.common import new_test_user  # type: ignore
from odoo.tools import mute_logger  # type: ignore
from .common import BibliotecaCase


class TestSecurity(BibliotecaCase):
    """
    Tests de permisos: qué puede hacer cada grupo de la biblioteca.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reader = new_test_user(
            cls.env, login='lector_test', context={'no_reset_password': True},
            groups='base.group_user,png_biblioteca.group_biblioteca_user')
        cls.librarian = new_test_user(
            cls.env, login='bibliotecario_test', context={'no_reset_password': True},
            groups='base.group_user,png_biblioteca.group_biblioteca_librarian')
        cls.manager = new_test_user(
            cls.env, login='admin_biblioteca_test', context={'no_reset_password': True},
            groups='base.group_user,png_biblioteca.group_biblioteca_manager')
        cls.nobody = new_test_user(
            cls.env, login='sin_grupo_test', context={'no_reset_password': True},
            groups='base.group_user')

    def test_01_reader_can_only_read(self):
        """
        Un 'Usuario de Biblioteca' puede consultar pero no crear ni modificar préstamos.
        """

        loan = self._create_loan(self.book, self.student)
        Loan = self.Loan.with_user(self.reader)

        self.assertIn(loan, Loan.search([]))
        with self.assertRaises(AccessError):
            Loan.create({
                'book_id': self.book2.id,
                'user_id': self.student.id,
                'return_date': self.today,
            })
        with self.assertRaises(AccessError):
            loan.with_user(self.reader).write({'return_date': self.today})

    def test_02_librarian_can_manage_loans(self):
        """
        Un bibliotecario puede crear y devolver préstamos, pero no borrarlos.
        """

        loan = self.Loan.with_user(self.librarian).create({
            'book_id': self.book.id,
            'user_id': self.student.id,
            'return_date': self.today,
        })
        loan.action_return_book()
        self.assertEqual(loan.state, 'returned')

        with self.assertRaises(AccessError):
            loan.unlink()

    def test_03_manager_can_delete(self):
        """
        El administrador de biblioteca puede borrar préstamos.
        """

        loan = self._create_loan(self.book, self.student)
        loan.with_user(self.manager).unlink()
        self.assertFalse(loan.exists())

    def test_04_no_group_no_access(self):
        """
        Un usuario interno sin grupo de biblioteca no puede ver los préstamos.
        """

        with self.assertRaises(AccessError):
            self.Loan.with_user(self.nobody).search([])

    def test_05_buttons_hidden_for_reader(self):
        """
        Los botones 'Marcar como Devuelto' y 'Extender' solo los ven los bibliotecarios.
        """

        arch_reader = self.Loan.with_user(self.reader).get_views([(False, 'form')])['views']['form']['arch']
        arch_librarian = self.Loan.with_user(self.librarian).get_views([(False, 'form')])['views']['form']['arch']

        self.assertNotIn('action_return_book', arch_reader)
        self.assertNotIn('action_extend_loan', arch_reader)
        self.assertIn('action_return_book', arch_librarian)
        self.assertIn('action_extend_loan', arch_librarian)

    def test_06_task_history_permissions(self):
        """
        El historial de tareas: el lector no lo ve, el bibliotecario solo lo lee.
        """

        Job = self.env['png_biblioteca.loan.job']
        with self.assertRaises(AccessError):
            Job.with_user(self.reader).search([])

        Job.with_user(self.librarian).search([])
        with self.assertRaises(AccessError):
            Job.with_user(self.librarian).create({'name': 'Manual', 'state': 'done'})

    @mute_logger('odoo.addons.base.models.ir_model')
    def test_07_menu_visibility(self):
        """
        Solo los usuarios con algún grupo de biblioteca ven la aplicación.
        """

        root = self.env.ref('png_biblioteca.menu_biblioteca_root')
        history = self.env.ref('png_biblioteca.menu_loan_job')
        Menu = self.env['ir.ui.menu']

        reader_menus = Menu.with_user(self.reader)._visible_menu_ids()
        self.assertIn(root.id, reader_menus)
        self.assertNotIn(history.id, reader_menus)
        self.assertNotIn(root.id, Menu.with_user(self.nobody)._visible_menu_ids())
        self.assertIn(history.id, Menu.with_user(self.manager)._visible_menu_ids())