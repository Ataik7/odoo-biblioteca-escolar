from odoo import models, fields, api
from odoo.exceptions import ValidationError # type: ignore
from ..validators.user_validator import UserValidator
from ..helpers.user_helper import UserHelper


class User(models.Model):
    """
    Modelo User (Usuario de Biblioteca)
    Gestiona los usuarios que pueden realizar préstamos.
    Incluye Chatter para seguimiento de cambios y actividades.
    """

    # Nombre técnico
    _name = 'png_biblioteca.user'

    # Descripción
    _description = 'Usuario de Biblioteca'

    # Herencia para habilitar Chatter y actividades
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Ordenar usuarios por nombre
    _order = 'name'

    # =========================
    # Campos básicos
    # =========================

    # Nombre del usuario
    name = fields.Char(string='Nombre', required=True, tracking=True, index=True,
                        help="Nombre completo del usuario registrado en la biblioteca.")

    # Tipo de usuario dentro de la biblioteca
    user_type = fields.Selection([
        ('student', 'Estudiante'),
        ('teacher', 'Profesor'),
    ], string='Tipo de Usuario', required=True, tracking=True,
    help="Indica si el usuario es estudiante o profesor dentro del sistema de biblioteca.")

    # Número de carnet de biblioteca
    library_card = fields.Char(string='Número de Carnet', required=True, tracking=True, index=True,
                               help="Número de identificación del usuario asignado por la biblioteca.")

    # Correo electrónico del usuario
    email = fields.Char(string='Email', required=True, tracking=True,
                        help="Dirección de correo electrónico del usuario para notificaciones y comunicaciones.")

    # =========================
    # Imágenes
    # =========================

    # Foto del usuario
    image = fields.Image(string='Foto de Usuario', max_width=1024, max_height=1024)

    # Versiones reducidas para Kanban y Listas
    image_128 = fields.Image(string='Imagen 128', related='image', max_width=128, max_height=128, store=True)

    # =========================
    # Relaciones
    # =========================

    # Un usuario puede tener varios préstamos
    loan_ids = fields.One2many('png_biblioteca.loan', 'user_id', string='Préstamos')

    # Solicitudes de préstamo hechas desde la app
    request_ids = fields.One2many('png_biblioteca.loan.request', 'user_id', string='Solicitudes')

    # Usuario de Odoo (grupo Portal) con el que entra en la app
    res_user_id = fields.Many2one('res.users', string='Usuario de la App', readonly=True,
                                  copy=False, ondelete='set null', index=True)

    # Indica si ahora mismo puede entrar en la app
    app_access = fields.Boolean(string='Acceso a la App', compute='_compute_app_access')

    # =========================
    # Campos computados
    # =========================

    # Número de préstamos activos actualmente
    active_loans_count = fields.Integer(string='Préstamos Activos', compute='_compute_loan_statistics')

    # Número de préstamos vencidos
    overdue_loans_count = fields.Integer(string='Préstamos Vencidos', compute='_compute_loan_statistics')

    # Total de préstamos históricos
    total_loans_count = fields.Integer(string='Total de Préstamos', compute='_compute_loan_statistics')

    # Información completa del usuario (nombre - carnet - tipo)
    full_info = fields.Char(string='Información Completa', compute='_compute_full_info', inverse='_inverse_full_info', store=True, help="Nombre - Carnet (Tipo)")

    # =========================
    # SQL Constraint - Email y Carnet
    # =========================

    # Evita duplicados
    _sql_constraints = [
        ('email_unique', 'unique(email)', 'El correo electrónico ya está registrado en otro usuario.'),
        ('library_card_unique', 'unique(library_card)', 'El número de carnet ya está asignado a otro usuario.'),
        ('res_user_id_unique', 'unique(res_user_id)', 'El usuario de la app ya está asignado a otro usuario de biblioteca.'),
    ]

    # =========================
    # Métodos computados
    # =========================

    @api.depends('loan_ids', 'loan_ids.state')
    def _compute_loan_statistics(self):
        """
        Calcula estadísticas de préstamos del usuario a través del Helper.
        """

        for user in self:
            stats = UserHelper.get_user_statistics(user.loan_ids)
            user.active_loans_count = stats['active_loans']
            user.overdue_loans_count = stats['overdue_loans']
            user.total_loans_count = stats['total_loans']

    @api.depends('name', 'library_card', 'user_type')
    def _compute_full_info(self):
        """
        Genera una cadena con la información completa del usuario.
        Formato: Nombre - Número de Carnet (Tipo de Usuario)
        """

        for user in self:
        # Llamamos al Helper enviando los 4 argumentos que espera
            user.full_info = UserHelper.format_full_info(
                user.name,
                user.library_card,
                user.user_type,
                user.email
            )

    @api.depends('res_user_id', 'res_user_id.active')
    def _compute_app_access(self):
        """
        Tiene acceso a la app si tiene un usuario de acceso y está activo.
        """

        for user in self:
            user.app_access = bool(user.res_user_id.sudo().active)

    def _inverse_full_info(self):
        """
        Permite editar el campo 'full_info' y extraer el nombre.
        """

        for user in self:
            if user.full_info:
                user.name = UserHelper.parse_full_info(user.full_info)

    # =========================
    # Validaciones Python
    # =========================

    @api.constrains('email')
    def _check_email(self):
        """
        Valida que el email tenga un formato válido mediante el validador.

        Raises:
            ValidationError: Si el email no cumple con la expresión regular.
        """
        for user in self:
            if user.email:
                UserValidator.validate_email(user.email)

    @api.constrains('library_card')
    def _check_library_card(self):
        """
        Valida que el carnet tenga longitud mínima.

        Raises:
            ValidationError: Si el carnet ya existe o es demasiado corto.
        """

        for user in self:
            if user.library_card:
                UserValidator.validate_library_card(user.library_card)

    # =========================
    # Lógica en eventos
    # =========================

    @api.model_create_multi
    def create(self, vals_list):
        """
        Crea usuarios y notifica en el Chatter.

        Args:
            vals_list (list): Lista de diccionarios con valores de creación.

        Returns:
            recordset: Los registros de usuario creados.
        """

        # Para que no genere la notificación automática de creación
        users = super(User, self.with_context(tracking_disable=True)).create(vals_list)

        for user in users:
            UserHelper.post_creation_message(user)
        return users

    # =========================
    # Acciones de usuario
    # =========================

    def action_view_loans(self):
        """
        Botón: Genera la acción para visualizar los préstamos de este usuario.

        Returns:
            dict: Definición de la acción ir.actions.act_window.
        """

        self.ensure_one()
        return UserHelper.get_loans_action(self)

    def action_open_app_access_wizard(self):
        """
        Botón: Abre el asistente para dar acceso a la app (o cambiar la contraseña).

        Returns:
            dict: Acción que abre el asistente en una ventana emergente.
        """

        self.ensure_one()
        return {
            'name': 'Acceso a la App',
            'type': 'ir.actions.act_window',
            'res_model': 'png_biblioteca.app.access.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_library_user_id': self.id,
                'default_login': self.res_user_id.sudo().login or self.email,
            },
        }

    def action_revoke_app_access(self):
        """
        Botón: Quita el acceso a la app.

        Archiva el usuario de acceso y borra sus tokens, así que la app deja de funcionar
        al momento. Se puede volver a dar acceso con el mismo usuario.
        """

        for user in self.filtered('res_user_id'):
            access_user = user.res_user_id.sudo()
            self.env['png_biblioteca.api.token'].sudo().search([('user_id', '=', access_user.id)]).unlink()
            access_user.active = False
            user.message_post(body="📱 Acceso a la app retirado.", message_type='notification')
        return True
