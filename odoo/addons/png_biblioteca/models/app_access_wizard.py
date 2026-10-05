import secrets
import string
from markupsafe import Markup  # type: ignore
from odoo import fields, models  # type: ignore
from odoo.exceptions import UserError  # type: ignore


class AppAccessWizard(models.TransientModel):
    """
    Asistente para dar acceso a la app a un usuario de la biblioteca.

    Crea (o reactiva) un usuario de Odoo del grupo Portal y lo enlaza con el
    usuario de la biblioteca. Si no se escribe contraseña:
    - si ya tuvo acceso antes, se reactiva con su contraseña de siempre;
    - si es la primera vez, se genera una aleatoria y se muestra una sola vez.
    """

    # Nombre técnico
    _name = 'png_biblioteca.app.access.wizard'

    # Descripción
    _description = 'Dar Acceso a la App'

    # Longitud mínima de la contraseña
    MIN_PASSWORD = 8

    # Longitud de las contraseñas generadas
    GENERATED_LENGTH = 10

    # Usuario de la biblioteca al que se da acceso
    library_user_id = fields.Many2one('png_biblioteca.user', string='Usuario de Biblioteca',
                                      required=True, readonly=True)

    # Login con el que entrará en la app (por defecto, su email)
    login = fields.Char(string='Usuario de la App', required=True)

    # Contraseña (opcional: ver la descripción de la clase)
    password = fields.Char(string='Contraseña')

    def _generate_password(self):
        """
        Genera una contraseña aleatoria segura, sin caracteres que se confundan (0/O, 1/l/I).
        """

        alphabet = ''.join(c for c in string.ascii_letters + string.digits if c not in '0O1lI')
        return ''.join(secrets.choice(alphabet) for _ in range(self.GENERATED_LENGTH))

    def action_confirm(self):
        """
        Botón: crea, reactiva o cambia la contraseña del usuario de acceso.

        Raises:
            UserError: Si la contraseña es corta, falta al cambiarla
                o el login ya es de un usuario interno.
        """

        self.ensure_one()
        password = self.password
        if password and len(password) < self.MIN_PASSWORD:
            raise UserError(f"La contraseña debe tener al menos {self.MIN_PASSWORD} caracteres.")

        Users = self.env['res.users'].sudo().with_context(active_test=False, no_reset_password=True)
        library_user = self.library_user_id
        login = self.login.strip().lower()
        had_access = library_user.app_access

        if had_access and not password:
            raise UserError("Escribe la nueva contraseña.")

        # Reutilizamos el usuario de acceso que ya tuviera, o uno con ese login
        user = library_user.res_user_id.sudo() or Users.search([('login', '=', login)], limit=1)
        if user and not user.share:
            raise UserError(f"El login '{login}' ya pertenece a un usuario interno de Odoo.")

        generated = False
        if user:
            vals = {'login': login, 'active': True}
            if password:
                vals['password'] = password
            user.write(vals)
        else:
            if not password:
                password = self._generate_password()
                generated = True
            user = Users.create({
                'name': library_user.name,
                'login': login,
                'email': library_user.email,
                'password': password,
                'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
            })

        library_user.res_user_id = user

        # Toda contraseña puesta por el bibliotecario (escrita o generada) es temporal
        if password:
            library_user.app_password_temporary = True

        # Mensaje en el chatter (nunca con la contraseña)
        if had_access:
            body = Markup("🔑 <strong>Contraseña de la app cambiada</strong> (usuario: {})").format(login)
        elif self.password or generated:
            body = Markup("📱 <strong>Acceso a la app concedido</strong> (usuario: {})").format(login)
        else:
            body = Markup("📱 <strong>Acceso a la app reactivado</strong> con la contraseña anterior (usuario: {})").format(login)
        library_user.message_post(body=body, message_type='notification')

        # Si se ha generado la contraseña, se muestra una sola vez al bibliotecario
        if generated:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Acceso a la app concedido',
                    'message': f"Usuario: {login} · Contraseña temporal: {password}",
                    'type': 'success',
                    'sticky': True,
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }
        return {'type': 'ir.actions.act_window_close'}
