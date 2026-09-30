from odoo import fields
from datetime import timedelta
from ..validators.loan_validator import LoanValidator
from odoo.exceptions import ValidationError, UserError # type: ignore
from markupsafe import Markup  # type: ignore
from odoo.tools import format_date # type: ignore
import logging

_logger = logging.getLogger(__name__)

class LoanHelper:
    """Helper para cálculos y acciones de préstamos

    Proporciona métodos estáticos para facilitar operaciones comunes con préstamos,
    centralizando la lógica de estados, cálculos de fechas y mensajería en el chatter.
    """

    # =========================
    # Cálculos de estado y fechas
    # =========================

    @staticmethod
    def calculate_state(return_date, actual_return_date):
        """
        Determina el estado lógico de un préstamo basándose en sus fechas.

        Args:
            return_date (date): Fecha límite de devolución.
            actual_return_date (date|None): Fecha real de devolución.

        Returns:
            str: Estado del préstamo ('returned', 'late_returned', 'overdue', 'ongoing')
        """

        if actual_return_date:
            # Comparación de fechas para determinar si hubo retraso en la entrega
            if return_date and actual_return_date > return_date:
                return 'late_returned' # Entregado fuera de plazo
            return 'returned'          # Entregado a tiempo

        if not return_date:
            _logger.warning("Préstamo sin fecha de devolución, marcando como 'ongoing'")
            return 'ongoing'

        # Si no hay fecha de devolución real, comparamos con el día de hoy
        today = fields.Date.today()
        return 'overdue' if return_date < today else 'ongoing'

    @staticmethod
    def get_overdue_days(return_date):
        """
        Calcula los días de retraso del préstamo.

        Args:
            return_date (date): Fecha límite de devolución.

        Returns:
            int: Número de días de retraso (0 si no hay retraso).
        """

        if not return_date:
            return 0

        today = fields.Date.today()
        if return_date < today:
            # La diferencia de objetos date retorna un timedelta
            days = (today - return_date).days
            _logger.debug(f"Préstamo vencido hace {days} días")
            return days

        return 0

    @staticmethod
    def is_due_soon(return_date, days_threshold=3):
        """
        Determina si el préstamo vencerá pronto.

        Args:
            return_date (date): Fecha límite de devolución.
            days_threshold (int): Umbral de días para considerar "pronto". Default: 3.

        Returns:
            bool: True si vence dentro del umbral de días.
        """

        if not return_date:
            return False

        today = fields.Date.today()
        # Si ya venció o vence hoy, no se considera "vencimiento próximo"
        if return_date <= today:
            return False

        days_remaining = (return_date - today).days
        is_soon = days_remaining <= days_threshold

        if is_soon:
            _logger.debug(f"Préstamo vence pronto: {days_remaining} días restantes")

        return is_soon

    @staticmethod
    def get_days_remaining(return_date):
        """
        Calcula la diferencia de días entre hoy y la fecha de devolución.

        Args:
            return_date (date): Fecha límite de devolución.

        Returns:
            int: Días restantes (negativo si ya venció, 0 si no hay fecha).
        """

        if not return_date:
            return 0

        return (return_date - fields.Date.today()).days

    # =========================
    # Mensajes de Chatter
    # =========================

    @staticmethod
    def post_creation_message(loan):
        """
        Publica mensaje al crear préstamo.

        Args:
            loan (recordset): Registro del préstamo creado.
        """

        try:
            # format_date adapta la fecha al idioma del usuario de Odoo
            date_f = format_date(loan.env, loan.return_date)

            body = Markup("""
                <p>📚 <strong>Préstamo creado</strong></p>
                <ul>
                    <li><strong>Libro:</strong> {}</li>
                    <li><strong>Usuario:</strong> {}</li>
                    <li><strong>Fecha de devolución:</strong> {}</li>
                </ul>
            """).format(loan.book_id.name, loan.user_id.name, date_f)

            loan.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            _logger.info(f"✅ Préstamo creado: '{loan.book_id.name}'")

        except Exception as e:
            _logger.warning(f"No se pudo publicar mensaje de creación: {str(e)}")

    @staticmethod
    def post_return_message(loans):
        """
        Publica mensaje al devolver libro.

        Args:
            loans (recordset): Recordset de préstamos devueltos.
        """

        for loan in loans:
            loan.ensure_one() # Garantiza un registro único por iteración
            try:
                state = LoanHelper.calculate_state(loan.return_date, loan.actual_return_date)

                if state == 'late_returned':
                    delay = (loan.actual_return_date - loan.return_date).days
                    status_msg = f"⚠️ Devuelto Tarde ({delay} días de retraso)"
                else:
                    status_msg = "✅ Devuelto a Tiempo"

                date_f = format_date(loan.env, loan.actual_return_date)

                body = Markup("""
                    <strong>{}</strong>
                    <ul>
                        <li><strong>Libro:</strong> {}</li>
                        <li><strong>Usuario:</strong> {}</li>
                        <li><strong>Fecha:</strong> {}</li>
                    </ul>
                """).format(status_msg, loan.book_id.name, loan.user_id.name, date_f)

                loan.message_post(
                    body=body,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
            except Exception as e:
                _logger.warning(f"No se pudo publicar mensaje de devolución: {str(e)}")

    @staticmethod
    def post_extension_message(loans):
        """
        Publica mensaje al extender préstamo.

        Args:
            loans (recordset): Recordset de préstamos extendidos.
        """

        for loan in loans:
            loan.ensure_one()
            try:
                date_f = format_date(loan.env, loan.return_date) if loan.return_date else "N/A"

                body = Markup("""
                    <p>📅 <strong>Préstamo extendido</strong></p>
                    <ul>
                        <li><strong>Libro:</strong> {}</li>
                        <li><strong>Usuario:</strong> {}</li>
                        <li><strong>Nueva fecha de devolución:</strong> {}</li>
                    </ul>
                """).format(loan.book_id.name, loan.user_id.name, date_f)

                loan.message_post(
                    body=body,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
            except Exception as e:
                _logger.warning(f"❌ Error al publicar extensión: {str(e)}")

    # =========================
    # Acciones de usuario
    # =========================

    @staticmethod
    def handle_return_action(loan):
        """
        Procesa la devolución y refresca la pestaña automáticamente.
        La notificación visual queda registrada en el Chatter.

        Args:
            loan (png_biblioteca.loan): Registro a devolver.

        Returns:
            dict: Acción de notificación (warning o success).
        """

        if loan.state in ['returned', 'late_returned']:
            fecha_dev = format_date(loan.env, loan.actual_return_date)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '⚠️ Ya devuelto',
                    'message': f"Este libro ya fue recibido el {fecha_dev}.",
                    'type': 'warning',
                }
            }

        # Escribir la fecha dispara los computes de estado
        loan.write({'actual_return_date': fields.Date.today()})
        _logger.info("Libro devuelto: %s por %s", loan.book_id.name, loan.user_id.name)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @staticmethod
    def handle_extend_action(loan, days=7):
        """
        Maneja la acción de extender préstamo y refresca la pestaña.

        Args:
            loan (recordset): Préstamo a extender.
            days (int): Días a sumar al plazo actual.

        Returns:
            dict: Notificación de éxito o error para el usuario.
        """

        if days <= 0:
            raise ValidationError("El número de días debe ser positivo.")

        # Si la fecha es nula
        if not loan.return_date:
            raise UserError("No se puede extender un préstamo que no tiene fecha de devolución inicial.")

        if loan.state != 'ongoing':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '⚠️ No se puede extender',
                    'message': 'Solo se pueden extender préstamos en curso.',
                    'type': 'warning',
                }
            }

        new_return_date = loan.return_date + timedelta(days=days)

        # Si supera el máximo lanza ValidationError y Odoo muestra el diálogo de error
        LoanValidator.validate_loan_extension(loan.loan_date, new_return_date, max_extension_days=30)
        loan.write({'return_date': new_return_date})

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


