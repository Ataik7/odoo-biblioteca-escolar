from odoo import models, fields, api
from ..helpers.loan_helper import LoanHelper
from markupsafe import Markup  # type: ignore
import logging

_logger = logging.getLogger(__name__)


class LoanCron(models.AbstractModel):
    """
    Tareas programadas (CRON) relacionadas con préstamos.

    Centraliza la lógica de los procesos automáticos de la biblioteca,
    como la actualización de estados de mora y el envío de recordatorios preventivos.
    Cada ejecución queda registrada en el historial (png_biblioteca.loan.job).
    """

    # Nombre técnico
    _name = 'png_biblioteca.loan.cron'

    # Descripción
    _description = 'CRON Jobs de Préstamos'

    # =========================
    # Registro en el historial
    # =========================

    def _run_and_log(self, name, func):
        """
        Ejecuta una tarea del cron y guarda el resultado en el historial.
        Si falla, deshace sus cambios y registra el error sin detener el cron.

        Args:
            name (str): Nombre de la tarea para el historial.
            func (callable): Función que devuelve (registros_procesados, mensaje).
        """

        Job = self.env['png_biblioteca.loan.job']
        try:
            # El savepoint permite deshacer solo esta tarea si falla
            with self.env.cr.savepoint():
                count, message = func()
            Job.create({
                'name': name,
                'state': 'done',
                'records_count': count,
                'result_message': message,
            })
        except Exception as e:
            _logger.exception("CRON [%s] ha fallado", name)
            Job.create({
                'name': name,
                'state': 'failed',
                'error_message': str(e),
            })
        return True

    # =========================
    # Métodos llamados por el cron
    # =========================

    @api.model
    def update_overdue_loans(self):
        """CRON JOB: Actualiza estados de préstamos (con registro en el historial)."""
        return self._run_and_log("Actualizar préstamos vencidos", self._update_overdue_loans)

    @api.model
    def send_due_soon_reminders(self):
        """CRON JOB: Envía recordatorios (con registro en el historial)."""
        return self._run_and_log("Enviar recordatorios de devolución", self._send_due_soon_reminders)

    # =========================
    # Lógica de cada tarea
    # =========================

    def _update_overdue_loans(self):
        """
        Recalcula los campos que dependen de la fecha actual
        (estado, días de retraso, días restantes) y notifica los nuevos vencidos.

        Returns:
            tuple: (préstamos procesados, mensaje resumen)
        """

        Loan = self.env['png_biblioteca.loan']
        loans = Loan.search([('actual_return_date', '=', False)])

        # Forzamos el recálculo de los campos almacenados que dependen de "hoy"
        for fname in ('state', 'overdue_days', 'days_remaining'):
            self.env.add_to_compute(Loan._fields[fname], loans)
        loans.flush_recordset()

        # Solo avisamos el primer día de retraso para no repetir el mensaje cada día
        newly_overdue = loans.filtered(lambda l: l.state == 'overdue' and l.overdue_days == 1)

        for loan in newly_overdue:
            loan.message_post(
                body=Markup(
                    "⚠️ <strong>Préstamo vencido</strong><br/>"
                    "📖 <b>Libro:</b> {}<br/>"
                    "👤 <b>Usuario:</b> {}<br/>"
                    "📅 <b>Fecha límite:</b> {}"
                ).format(loan.book_id.name, loan.user_id.name, loan.return_date),
                subject="ALERTA: Préstamo Vencido",
                message_type='notification',
            )

        message = f"{len(loans)} préstamos recalculados, {len(newly_overdue)} nuevos vencidos."
        _logger.info("CRON [update_overdue_loans]: %s", message)
        return len(loans), message

    def _send_due_soon_reminders(self):
        """
        Envía recordatorios de préstamos que vencen en los próximos 3 días.

        Returns:
            tuple: (recordatorios enviados, mensaje resumen)
        """

        ongoing_loans = self.env['png_biblioteca.loan'].search([
            ('state', '=', 'ongoing'),
            ('actual_return_date', '=', False),
        ])

        # El helper decide cuáles están dentro del umbral
        due_soon_loans = ongoing_loans.filtered(
            lambda l: LoanHelper.is_due_soon(l.return_date, days_threshold=3)
        )

        for loan in due_soon_loans:
            loan.message_post(
                body=Markup(
                    "📅 <strong>Recordatorio de devolución</strong><br/>"
                    "Libro: '{}'<br/>"
                    "Quedan <b>{}</b> días para la entrega."
                ).format(loan.book_id.name, LoanHelper.get_days_remaining(loan.return_date)),
                subject="Recordatorio: Próximo Vencimiento",
                message_type='notification',
            )

        message = f"{len(due_soon_loans)} recordatorios enviados."
        _logger.info("CRON [send_due_soon_reminders]: %s", message)
        return len(due_soon_loans), message