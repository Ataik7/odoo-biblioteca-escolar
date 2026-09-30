from odoo.exceptions import ValidationError  # type: ignore
import re

class UserValidator:
    """
    Validador de reglas de negocio para usuarios.

    Centraliza la validación de credenciales de identidad y contacto para garantizar la integridad de la base de datos de socios de la biblioteca.
    """

    # Regex para validación de formato de correo electrónico
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    @staticmethod
    def validate_email(email):
        """
        Valida el formato del email.

        Args:
            email (str): Email a validar.

        Raises:
            ValidationError: Si el formato es inválido.
        """

        if not email:
            return  # Email es opcional

        if not UserValidator.EMAIL_REGEX.match(email):
            raise ValidationError(
                f"El email '{email}' no tiene un formato válido.\n"
                f"Ejemplo: usuario@ejemplo.com"
            )

    @staticmethod
    def validate_library_card(library_card):
        """
        Valida el formato del carnet de biblioteca.

        Args:
            library_card (str): Número de carnet.

        Raises:
            ValidationError: Si el formato es inválido.
        """

        if not library_card:
            raise ValidationError("El número de carnet es obligatorio.")

        # Debe tener al menos 4 caracteres
        if len(library_card.strip()) < 4:
            raise ValidationError(
                "El número de carnet debe tener al menos 4 caracteres."
            )

    @staticmethod
    def validate_library_card_uniqueness(env, library_card, user_id=None):
        """
        Valida que el carnet sea único.

        Args:
            env: Entorno de Odoo.
            library_card (str): Número de carnet.
            user_id (int): ID del usuario actual (para excluirlo en edición).

        Raises:
            ValidationError: Si el carnet ya existe.
        """

        User = env['png_biblioteca.user']

        domain = [('library_card', '=', library_card)]

        if user_id:
            domain.append(('id', '!=', user_id))

        existing_user = User.search(domain, limit=1)

        if existing_user:
            raise ValidationError(
                f"El número de carnet '{library_card}' ya está asignado a '{existing_user.name}'."
            )