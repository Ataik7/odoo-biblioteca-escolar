from datetime import timedelta
from unittest.mock import patch
from odoo.tools import mute_logger  # type: ignore
from .common import BibliotecaCase


class TestCron(BibliotecaCase):
    """
    Tests de las tareas programadas y de su historial.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cron = cls.env['png_biblioteca.loan.cron']
        cls.Job = cls.env['png_biblioteca.loan.job']

    def _last_job(self):
        """
        Devuelve el último registro del historial de tareas.
        """

        return self.Job.search([], order='id desc', limit=1)

    def _move_return_date(self, loan, days):
        """
        Simula el paso del tiempo: cambia la fecha de devolución directamente en
        la base de datos, sin recalcular los campos (como pasaría al cambiar el día).
        """

        loan.flush_recordset()
        self.env.cr.execute(
            "UPDATE png_biblioteca_loan SET loan_date = %s, return_date = %s WHERE id = %s",
            (self.today - timedelta(days=20), self.today + timedelta(days=days), loan.id),
        )
        self.env.invalidate_all()

    def test_01_update_overdue_loans(self):
        """
        El cron marca como vencidos los préstamos cuya fecha ya pasó
        y avisa en el chatter el primer día de retraso.
        """

        loan = self._create_loan(self.book, self.student, days=5)
        self._move_return_date(loan, -1)
        self.assertEqual(loan.state, 'ongoing')

        self.Cron.update_overdue_loans()
        self.env.invalidate_all()

        self.assertEqual(loan.state, 'overdue')
        self.assertEqual(loan.overdue_days, 1)
        self.assertIn('Préstamo vencido', ' '.join(loan.message_ids.mapped('body')))

        job = self._last_job()
        self.assertEqual(job.state, 'done')
        self.assertIn('recalculados', job.result_message)

    def test_02_send_due_soon_reminders(self):
        """
        El cron envía recordatorio a los préstamos que vencen en los próximos 3 días.
        """

        loan = self._create_loan(self.book, self.student, days=2)
        self.Cron.send_due_soon_reminders()

        self.assertIn('Recordatorio de devolución', ' '.join(loan.message_ids.mapped('body')))
        job = self._last_job()
        self.assertEqual(job.state, 'done')
        self.assertGreaterEqual(job.records_count, 1)

    def test_03_failed_task_is_logged(self):
        """
        Si una tarea falla, queda registrada como fallida con el error.
        """

        with patch.object(type(self.Cron), '_update_overdue_loans', side_effect=ValueError('fallo simulado')), \
                mute_logger('odoo.addons.png_biblioteca.jobs.loan_job'):
            self.Cron.update_overdue_loans()

        job = self._last_job()
        self.assertEqual(job.state, 'failed')
        self.assertIn('fallo simulado', job.error_message)