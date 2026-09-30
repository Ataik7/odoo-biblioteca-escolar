from odoo.exceptions import ValidationError # type: ignore

class LoanValidator:
    """
    Validador de reglas de negocio para préstamos.

    Asegura que no existan errores de registro donde la fecha de devolución sea anterior al inicio del préstamo.
    """

    @staticmethod
    def validate_dates(loan_date, return_date):
        """
        Valida que la fecha de devolución sea posterior a la de préstamo.

        Args:
            loan_date (date): Fecha de préstamo.
            return_date (date): Fecha de devolución.

        Raises:
            ValidationError: Si las fechas son inválidas.
        """

        if not loan_date or not return_date:
            raise ValidationError("Las fechas de préstamo y devolución son obligatorias.")

        if return_date < loan_date:
            raise ValidationError(
                f"La fecha de devolución ({return_date}) no puede ser anterior "
                f"a la fecha de préstamo ({loan_date})."
            )

    @staticmethod
    def validate_book_availability(env, book_id, loan_id, state):
        """
        Valida que un libro no tenga préstamos activos duplicados.

        Args:
            env: Entorno de Odoo.
            book_id (int): ID del libro.
            loan_id (int): ID del préstamo actual (para excluirlo).
            state (str): Estado del préstamo.

        Raises:
            ValidationError: Si el libro ya está prestado.
        """

        if state not in ['ongoing', 'overdue']:
            return  # No validar si está devuelto

        Loan = env['png_biblioteca.loan']

        # Buscar otros préstamos activos del mismo libro
        other_loans = Loan.search([
            ('book_id', '=', book_id),
            ('state', 'in', ['ongoing', 'overdue']),
            ('id', '!=', loan_id)
        ], limit=1)

        if other_loans:
            Book = env['png_biblioteca.book']
            book = Book.browse(book_id)

            raise ValidationError(
                f"El libro '{book.name}' ya está prestado.\n"
                f"Préstamo activo: {other_loans[0].user_id.name} "
                f"(debe devolverse el {other_loans[0].return_date})"
            )

    @staticmethod
    def validate_user_loan_limit(env, user_id, current_loan_id=None, max_loans=3):
        """
        Valida que un usuario no exceda el límite de préstamos activos.

        Args:
            env: Entorno de Odoo.
            user_id (int): ID del usuario.
            current_loan_id (int): ID del préstamo actual (para excluirlo en edición).
            max_loans (int): Número máximo de préstamos permitidos.

        Raises:
            ValidationError: Si excede el límite.
        """

        Loan = env['png_biblioteca.loan']

        # Construir dominio de búsqueda
        domain = [
            ('user_id', '=', user_id),
            ('state', 'in', ['ongoing', 'overdue'])
        ]

        # Excluir el préstamo actual si se está editando
        if current_loan_id:
            domain.append(('id', '!=', current_loan_id))

        active_loans_count = Loan.search_count(domain)

        if active_loans_count >= max_loans:
            User = env['png_biblioteca.user']
            user = User.browse(user_id)

            raise ValidationError(
                f"El usuario '{user.name}' ya tiene {active_loans_count} préstamos activos.\n"
                f"Límite máximo permitido: {max_loans}.\n"
                f"Debe devolver un libro antes de solicitar otro."
            )

    @staticmethod
    def validate_loan_extension(loan_date, return_date, max_extension_days=30):
        """
        Valida que un préstamo no se extienda más allá del límite permitido.

        Args:
            loan_date (date): Fecha de préstamo.
            return_date (date): Nueva fecha de devolución.
            max_extension_days (int): Días máximos de préstamo.

        Raises:
            ValidationError: Si excede el límite.
        """

        if not loan_date or not return_date:
            return

        delta = return_date - loan_date

        if delta.days > max_extension_days:
            raise ValidationError(
                f"El período de préstamo no puede exceder {max_extension_days} días.\n"
                f"Período solicitado: {delta.days} días."
            )
