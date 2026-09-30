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