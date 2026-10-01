import hashlib
import secrets
from datetime import timedelta
from odoo import api, fields, models  # type: ignore


class ApiToken(models.Model):
    """
    Tokens de acceso a la API REST de la biblioteca (app móvil).

    Solo se guarda el hash SHA-256 del token: aunque alguien lea la base de datos,
    no puede usar los tokens para entrar en la API.
    """

    # Nombre técnico
    _name = 'png_biblioteca.api.token'

    # Descripción
    _description = 'Token de API de la Biblioteca'

    # Más recientes primero
    _order = 'create_date desc'

    # Días que dura un token antes de tener que volver a hacer login
    TOKEN_DAYS = 30

    # =========================
    # Campos
    # =========================

    # Usuario de Odoo (portal) dueño del token
    user_id = fields.Many2one('res.users', string='Usuario', required=True, ondelete='cascade', index=True)

    # Hash del token (el token en claro nunca se guarda)
    token_hash = fields.Char(string='Hash del Token', required=True, index=True, copy=False)

    # Fecha a partir de la cual el token deja de valer
    expiration = fields.Datetime(string='Caduca', required=True)

    _sql_constraints = [
        ('token_hash_unique', 'unique(token_hash)', 'El token ya existe.'),
    ]

    # =========================
    # Métodos
    # =========================

    @api.model
    def _hash(self, token):
        """
        Calcula el hash SHA-256 de un token.
        """

        return hashlib.sha256(token.encode()).hexdigest()

    @api.model
    def _generate(self, user):
        """
        Crea un token nuevo para el usuario.

        Args:
            user (recordset): Usuario de Odoo (res.users).

        Returns:
            tuple: (token en claro, fecha de caducidad). El token solo se puede ver ahora.
        """

        token = secrets.token_urlsafe(32)
        record = self.sudo().create({
            'user_id': user.id,
            'token_hash': self._hash(token),
            'expiration': fields.Datetime.now() + timedelta(days=self.TOKEN_DAYS),
        })
        return token, record.expiration

    @api.model
    def _find_user(self, token):
        """
        Devuelve el usuario dueño de un token válido (no caducado y con el usuario activo).

        Args:
            token (str): Token en claro recibido en la cabecera Authorization.

        Returns:
            recordset: Usuario de Odoo, o un recordset vacío si el token no vale.
        """

        Users = self.env['res.users']
        if not token:
            return Users

        record = self.sudo().search([
            ('token_hash', '=', self._hash(token)),
            ('expiration', '>', fields.Datetime.now()),
        ], limit=1)
        return record.user_id if record.user_id.active else Users

    @api.model
    def _revoke(self, token):
        """
        Anula un token (logout).
        """

        self.sudo().search([('token_hash', '=', self._hash(token))]).unlink()

    @api.autovacuum
    def _gc_expired_tokens(self):
        """
        Borra los tokens caducados. Odoo lo ejecuta automáticamente una vez al día.
        """

        self.sudo().search([('expiration', '<=', fields.Datetime.now())]).unlink()