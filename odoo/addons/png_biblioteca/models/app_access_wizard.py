from markupsafe import Markup  # type: ignore
from odoo import fields, models  # type: ignore
from odoo.exceptions import UserError  # type: ignore


class AppAccessWizard(models.TransientModel):
    """
    Asistente para dar acceso a la app a un usuario de la biblioteca.

    Crea (o reactiva) un usuario de Odoo del grupo Portal con el login y la
    contraseña indicados, y lo enlaza con el usuario de la biblioteca.
    """

    # Nombre técnico
    _name = 'png_biblioteca.app.access.wizard'

    # Descripción
    _description = 'Dar Acceso a la App'

    # Longitud mínima de la contraseña
    MIN_PASSWORD = 8

    # Usuario de la biblioteca al que se da acceso
    library_user_id = fields.Many2one('png_biblioteca.user', string='Usuario de Biblioteca',
                                      required=True, readonly=True)

    # Login con el que entrará en la app (por defecto, su email)
    login = fields.Char(string='Usuario de la App', required=True)

    # Contraseña inicial
    password = fields.Char(string='Contraseña', required=True)

    def action_confirm(self):
        """
        Botón: crea o reactiva el usuario de acceso y lo enlaza.

        Raises:
            UserError: Si la contraseña es corta o el login ya es de un usuario interno.
        """

        self.ensure_one()
        if len(self.password) < self.MIN_PASSWORD:
            raise UserError(f"La contraseña debe tener al menos {self.MIN_PASSWORD} caracteres.")

        Users = self.env['res.users'].sudo().with_context(active_test=False, no_reset_password=True)
        library_user = self.library_user_id
        login = self.login.strip().lower()

        # Reutilizamos el usuario de acceso que ya tuviera, o uno con ese login
        user = library_user.res_user_id.sudo() or Users.search([('login', '=', login)], limit=1)
        if user and not user.share:
            raise UserError(f"El login '{login}' ya pertenece a un usuario interno de Odoo.")

        if user:
            user.write({'login': login, 'password': self.password, 'active': True})
        else:
            user = Users.create({
                'name': library_user.name,
                'login': login,
                'email': library_user.email,
                'password': self.password,
                'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
            })

        library_user.res_user_id = user
        library_user.message_post(
            body=Markup("📱 <strong>Acceso a la app concedido</strong> (usuario: {})").format(login),
            message_type='notification',
        )
        return {'type': 'ir.actions.act_window_close'}