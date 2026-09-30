from odoo.exceptions import ValidationError # type: ignore
from markupsafe import Markup # type: ignore
import logging

_logger = logging.getLogger(__name__)

class UserHelper:
    """Helper para cálculos y acciones de usuarios

    Proporciona métodos estáticos para gestionar estadísticas de préstamos, formateo de información de socios y generación de acciones de interfaz.
    """

    # =========================
    # Cálculos de préstamos
    # =========================

    @staticmethod
    def count_active_loans(loan_ids):
        """Cuenta los préstamos activos (en curso) de un usuario.

        Args:
            loan_ids (recordset): Recordset de modelos 'png_biblioteca.loan'

        Returns:
            int: Cantidad de préstamos en estado 'ongoing'.
        """

        if not loan_ids:
            return 0
        # filtered() es más eficiente en recordsets pequeños que un bucle manual
        return len(loan_ids.filtered(lambda l: l.state == 'ongoing'))

    @staticmethod
    def count_overdue_loans(loan_ids):
        """Cuenta los préstamos vencidos de un usuario

        Args:
            loan_ids (recordset): Recordset de modelos 'png_biblioteca.loan'

        Returns:
            int: Cantidad de préstamos en estado 'overdue'.
        """

        if not loan_ids:
            return 0
        return len(loan_ids.filtered(lambda l: l.state == 'overdue'))

    @staticmethod
    def count_total_loans(loan_ids):
        """Cuenta el total de préstamos históricos de un usuario

        Args:
            loan_ids (recordset): Recordset de modelos 'png_biblioteca.loan'

        Returns:
            int: Total de registros en el recordset

        """
        return len(loan_ids) if loan_ids else 0

    # =========================
    # Información de user
    # =========================

    @staticmethod
    def format_full_info(name, library_card, user_type, email):
        """
        Genera una cadena con la información resumida del usuario.
        Formato: Nombre - Carnet (Tipo de Usuario) Correo.

        Args:
            name (str): Nombre del usuario.
            library_card (str): Número de carnet de biblioteca.
            user_type (str): Tipo de usuario (técnico).
            email (str): Correo electrónico.

        Returns:
            str: Cadena formateada para campos de búsqueda o etiquetas.
        """

        nombre = name or "Sin nombre"
        carnet = library_card or "S/N"
        tipo = user_type or "Sin tipo"
        correo = email or ""

        return f"{nombre} - {carnet} ({tipo}) {correo}"

    @staticmethod
    def parse_full_info(full_info):
        """
        Extrae el nombre desde el campo 'full_info'.

        Args:
            full_info (str): Cadena con formato "Nombre - Carnet (Tipo)".

        Returns:
            str: Nombre extraído o cadena vacía si el formato es inválido.
        """

        if not full_info:
            return ''

        try:
            # Separamos por el delimitador definido en el formato
            parts = full_info.split(' - ')
            return parts[0].strip() if len(parts) >= 1 else ''
        except Exception as e:
                _logger.warning(f"Error al parsear full_info: {str(e)}")
                return ''

    @staticmethod
    def get_user_statistics(loan_ids):
        """
        Calcula estadísticas recorriendo el recordset.

        Args:
            loan_ids (recordset): Recordset de préstamos del usuario.

        Returns:
            dict: Diccionario con contadores: total, active, overdue, returned.
        """

        stats = {
            'total_loans': len(loan_ids) if loan_ids else 0,
            'active_loans': 0,
            'overdue_loans': 0,
            'returned_loans': 0
        }

        if not loan_ids:
            return stats

        # Iteración única para optimizar rendimiento
        for loan in loan_ids:
            if loan.state == 'ongoing':
                stats['active_loans'] += 1
            elif loan.state == 'overdue':
                stats['overdue_loans'] += 1
            elif loan.state == 'returned':
                stats['returned_loans'] += 1

        return stats

    # =========================
    # Mensajes de Chatter
    # =========================

    @staticmethod
    def post_creation_message(user):
        """
        Publica un mensaje en el Chatter al crear un usuario.

        Args:
            user (recordset): Registro del usuario recién creado.
        """

        try:
            label = dict(user._fields['user_type'].selection).get(user.user_type, 'No definido')

            body_html = Markup("""
                <p>👤 <strong>Usuario registrado</strong></p>
                <ul>
                    <li><b>Nombre:</b> {}</li>
                    <li><b>Carnet:</b> {}</li>
                    <li><b>Tipo:</b> {}</li>
                    <li><b>Email:</b> {}</li>
                </ul>
            """).format(user.name, user.library_card, label, user.email)

            user.message_post(
                body=body_html,
                message_type='notification'
            )
        except Exception as e:
            _logger.error(f"Error al publicar mensaje de creación: {str(e)}")

    # =========================
    # Acciones de usuario
    # =========================

    @staticmethod
    def get_loans_action(user):
        """
        Genera acción de ventana para ver los préstamos de un usuario.

        Args:
            user (recordset): Registro del usuario (socio).

        Returns:
            dict: Diccionario de acción ir.actions.act_window.
        """

        return {
            'type': 'ir.actions.act_window',
            'name': f'Préstamos de {user.name}',
            'res_model': 'png_biblioteca.loan',
            'view_mode': 'tree,kanban,form',
            'domain': [('user_id', '=', user.id)], # Filtro dinámico
            'context': {
                'default_user_id': user.id,        # Pre-asigna el usuario en nuevos registros
                'search_default_user_id': user.id  # Activa el filtro en la barra de búsqueda
            },
            'target': 'current',
        }