from datetime import timedelta
from odoo import api, fields, models  # type: ignore
from odoo.exceptions import UserError, ValidationError  # type: ignore


class LoanRequest(models.Model):
    """
    Solicitud de préstamo hecha por un usuario desde la app.

    El bibliotecario la aprueba (se crea el préstamo) o la rechaza.
    El usuario puede cancelarla mientras esté pendiente.
    """

    # Nombre técnico
    _name = 'png_biblioteca.loan.request'

    # Descripción
    _description = 'Solicitud de Préstamo'

    # Herencia para habilitar Chatter y actividades
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Más recientes primero
    _order = 'request_date desc, id desc'

    # Para el título
    _rec_name = 'book_id'

    # Días de préstamo cuando se aprueba una solicitud
    LOAN_DAYS = 14

    # =========================
    # Campos
    # =========================

    # Usuario de la biblioteca que pide el libro
    user_id = fields.Many2one('png_biblioteca.user', string='Usuario', required=True,
                              ondelete='cascade', index=True, tracking=True)

    # Libro solicitado
    book_id = fields.Many2one('png_biblioteca.book', string='Libro', required=True,
                              ondelete='cascade', index=True, tracking=True)

    # Momento en el que se hizo la solicitud
    request_date = fields.Datetime(string='Fecha de Solicitud', required=True, readonly=True,
                                   default=fields.Datetime.now)

    # Estado de la solicitud
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', required=True, default='pending', index=True, tracking=True)

    # Explicación para el usuario si se rechaza
    rejection_reason = fields.Text(string='Motivo del Rechazo', tracking=True)

    # Préstamo creado al aprobar la solicitud
    loan_id = fields.Many2one('png_biblioteca.loan', string='Préstamo', readonly=True, ondelete='set null')

    # =========================
    # Validaciones
    # =========================

    @api.constrains('book_id')
    def _check_book_available(self):
        """
        Solo se pueden pedir libros que estén disponibles.

        Raises:
            ValidationError: Si el libro está prestado.
        """

        for request in self:
            if request.state == 'pending' and request.book_id.state != 'available':
                raise ValidationError(f"El libro '{request.book_id.name}' no está disponible en este momento.")

    @api.constrains('user_id', 'book_id', 'state')
    def _check_duplicate_pending(self):
        """
        Un usuario no puede tener dos solicitudes pendientes del mismo libro.

        Raises:
            ValidationError: Si ya existe otra solicitud pendiente igual.
        """

        for request in self.filtered(lambda r: r.state == 'pending'):
            duplicate = self.search_count([
                ('id', '!=', request.id),
                ('user_id', '=', request.user_id.id),
                ('book_id', '=', request.book_id.id),
                ('state', '=', 'pending'),
            ])
            if duplicate:
                raise ValidationError(f"Ya hay una solicitud pendiente de '{request.book_id.name}' para este usuario.")

    # =========================
    # Acciones
    # =========================

    def _check_pending(self, action):
        """
        Comprueba que todas las solicitudes estén pendientes antes de cambiarlas.

        Raises:
            UserError: Si alguna no está pendiente.
        """

        if self.filtered(lambda r: r.state != 'pending'):
            raise UserError(f"Solo se pueden {action} solicitudes pendientes.")

    def action_approve(self):
        """
        Botón: aprueba la solicitud y crea el préstamo.

        Las demás solicitudes pendientes del mismo libro se rechazan automáticamente,
        porque el libro deja de estar disponible.
        """

        self._check_pending('aprobar')
        for request in self:
            loan = self.env['png_biblioteca.loan'].create({
                'user_id': request.user_id.id,
                'book_id': request.book_id.id,
                'return_date': fields.Date.today() + timedelta(days=self.LOAN_DAYS),
            })
            request.write({'state': 'approved', 'loan_id': loan.id})

            others = self.search([
                ('id', '!=', request.id),
                ('book_id', '=', request.book_id.id),
                ('state', '=', 'pending'),
            ])
            others.write({
                'state': 'rejected',
                'rejection_reason': 'El libro se ha prestado a otro usuario.',
            })
        return True

    def action_reject(self):
        """
        Botón: rechaza la solicitud. El motivo se escribe antes en el formulario.
        """

        self._check_pending('rechazar')
        self.write({'state': 'rejected'})
        return True

    def action_cancel(self):
        """
        Botón: cancela la solicitud (la usa el propio usuario desde la app).
        """

        self._check_pending('cancelar')
        self.write({'state': 'cancelled'})
        return True