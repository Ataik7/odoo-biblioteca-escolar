from odoo import models, fields, api
from odoo.exceptions import UserError  # type: ignore
from ..validators.loan_validator import LoanValidator
from ..helpers.loan_helper import LoanHelper

class Loan(models.Model):
    """
    Modelo Loan (Préstamo)
    Gestiona los préstamos de libros con validaciones automáticas.
    Incluye Chatter para seguimiento de cambios y actividades.
    """

    # Nombre técnico
    _name = 'png_biblioteca.loan'

    # Descripción
    _description = 'Préstamo'

    # Herencia para habilitar Chatter y actividades
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Ordenar préstamos por fecha más reciente
    _order = 'loan_date desc'

    # Para el título
    _rec_name = 'book_id'

    # =========================
    # Campos básicos
    # =========================

    # Fecha en la que se realiza el préstamo
    loan_date = fields.Date(string='Fecha de Préstamo', required=True, default=fields.Date.today, tracking=True, index=True,
                            help="Fecha en la que se presta el libro al usuario.")

    # Fecha límite para devolver el libro
    return_date = fields.Date(string='Fecha de Devolución', required=True, tracking=True, index=True,
                              help="Fecha límite en la que el alumno debe devolver el libro.")

    # Fecha real en la que el libro fue devuelto
    actual_return_date = fields.Date(string='Fecha Real de Devolución', tracking=False)

    # =========================
    # Relaciones
    # =========================

    # Usuario que realiza el préstamo
    user_id = fields.Many2one('png_biblioteca.user', string='Usuario', required=True, tracking=True, ondelete='restrict', index=True)

    # Libro que se presta
    book_id = fields.Many2one('png_biblioteca.book', string='Libro', required=True, tracking=True, ondelete='restrict', index=True)

    # =========================
    # Campos computados
    # =========================

    # Estado del préstamo (en curso, devuelto, vencido y entregado tarde)
    state = fields.Selection([
        ('ongoing', 'En Curso'),
        ('returned', 'Devuelto'),
        ('overdue', 'Vencido'),
        ('late_returned', 'Entregado Tarde'),
    ], string='Estado', compute='_compute_state', store=True, tracking=False, default='ongoing')

    # Días de retraso si el préstamo está vencido
    overdue_days = fields.Integer(string='Días de Retraso', compute='_compute_overdue_days', store=True, help="Número de días de retraso en la devolución")

    # Indica si el préstamo vencerá pronto (próximos 3 días)
    is_due_soon = fields.Boolean(string='Próximo a Vencer', compute='_compute_is_due_soon', help="True si el préstamo vence en los próximos 3 días")

    # Días restantes hasta la fecha de devolución
    days_remaining = fields.Integer(string='Días Restantes', compute='_compute_days_remaining',store=True, help="Días restantes para la devolución (negativo si está vencido)")

    # =========================
    # Métodos computados
    # =========================

    @api.depends('return_date', 'actual_return_date')
    def _compute_state(self):
        """
        Calcula el estado del préstamo:
        - 'Devuelto' si existe fecha real de devolución
        - 'Vencido' si la fecha de devolución ya pasó
        - 'En Curso' en cualquier otro caso
        """
        for loan in self:
            loan.state = LoanHelper.calculate_state(loan.return_date, loan.actual_return_date)

    @api.depends('return_date', 'actual_return_date', 'state')
    def _compute_overdue_days(self):
        """
        Calcula los días de retraso si el préstamo está vencido.
        Retorna 0 si no está vencido.
        """

        for loan in self:
            # Inicializamos el valor por defecto
            delay = 0

            # Validamos fecha y estados de retraso
            if loan.return_date and loan.state in ['overdue', 'late_returned']:
                compare_date = loan.actual_return_date or fields.Date.today()
                if compare_date > loan.return_date:
                    delay = (compare_date - loan.return_date).days

            loan.overdue_days = delay

    @api.depends('return_date', 'state')
    def _compute_is_due_soon(self):
        """
        Determina si el préstamo vencerá en los próximos 3 días.
        Solo aplica para préstamos en curso.
        """

        for loan in self:
            loan.is_due_soon = loan.state == 'ongoing' and LoanHelper.is_due_soon(loan.return_date)

    @api.depends('return_date', 'state')
    def _compute_days_remaining(self):
        """
        Calcula los días restantes para la devolución.
        Retorna valor negativo si está vencido.
        """

        for loan in self:
            # 1. Asignación por defecto al inicio
            delay = 0
            # 2. Solo calculamos si hay fecha y no se ha devuelto
            if loan.return_date and loan.state not in ['returned', 'late_returned']:
                delay = LoanHelper.get_days_remaining(loan.return_date)

            loan.days_remaining = delay

    # =========================
    # Validaciones Python
    # =========================

    @api.constrains('loan_date', 'return_date')
    def _check_dates(self):
        """
        Valida que la fecha de devolución sea posterior a la de préstamo.

        Raises:
            ValidationError: Si la fecha de retorno es anterior a la fecha de préstamo.
        """

        for loan in self:
            LoanValidator.validate_dates(loan.loan_date, loan.return_date)

    @api.constrains('book_id', 'state')
    def _check_book_availability(self):
        """
        Valida que el libro no esté prestado a otro usuario.
        No permite préstamos duplicados del mismo libro.

        Raises:
            ValidationError: Si el libro ya tiene un préstamo activo por otro registro.
        """

        for loan in self:
            LoanValidator.validate_book_availability(self.env, loan.book_id.id, loan.id, loan.state)

    @api.constrains('user_id', 'state')
    def _check_user_loan_limit(self):
        """
        Valida que el usuario no exceda el límite de préstamos activos.
        Límite máximo: 3 préstamos simultáneos.

        Raises:
            ValidationError: Si el usuario supera el máximo de préstamos permitidos.
        """

        for loan in self:
            if loan.state in ['ongoing', 'overdue']:
                LoanValidator.validate_user_loan_limit(self.env, loan.user_id.id, loan.id, max_loans=3)

    @api.constrains('loan_date', 'return_date')
    def _check_loan_duration(self):
        """
        Valida que el préstamo no exceda la duración máxima permitida (30 días).

        Raises:
            ValidationError: Si la duración calculada excede el máximo permitido.
        """

        for loan in self:
            LoanValidator.validate_loan_extension(loan.loan_date, loan.return_date, max_extension_days=30)

    # =========================
    # Lógica en eventos
    # =========================

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrescribe la creación de préstamos para personalizar el chatter.

        Args:
            vals_list (list[dict]): Lista de diccionarios con los datos para los nuevos registros.

        Returns:
            recordset: El registro de préstamo creado.
        """

        loans = super(Loan, self.with_context(tracking_disable=True)).create(vals_list)

        for loan in loans:
            LoanHelper.post_creation_message(loan)

        return loans

    def write(self, vals):
        """
        Sobrescribe la actualización para gestionar notificaciones personalizadas.

        Args:
            vals (dict): Diccionario con los campos a actualizar.

        Returns:
            bool: Resultado de la operación.
        """

        result = super().write(vals)

        for record in self:

            # Registro de devolución física
            if vals.get('actual_return_date'):
                LoanHelper.post_return_message(record)

            # Extensión del plazo
            elif vals.get('return_date') and not record.actual_return_date:
                LoanHelper.post_extension_message(record)

        return result

    # =========================
    # Acciones de usuario
    # =========================

    def action_return_book(self):
        """
        Botón: Marca el libro como devuelto.
        Establece la fecha actual como fecha real de devolución.

        Returns:
            dict/bool: Acción o resultado del Helper.

        Raises:
            UserError: Si el préstamo ya estaba marcado como devuelto.
        """

        self.ensure_one()
        if self.actual_return_date:
            raise UserError("El libro ya ha sido devuelto anteriormente.")

        return LoanHelper.handle_return_action(self)

    def action_extend_loan(self):
        """
        Botón: Extiende el préstamo 7 días más.
        Solo disponible para préstamos en curso.

        Returns:
            dict/bool: Acción o resultado del Helper.

        Raises:
            UserError: Si el préstamo no está en curso o ya fue devuelto.
        """

        self.ensure_one()
        if self.state != 'ongoing':
            raise UserError("Solo se pueden extender préstamos que estén en curso.")

        return LoanHelper.handle_extend_action(self, days=7)