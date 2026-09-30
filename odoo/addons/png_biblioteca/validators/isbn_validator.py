import re

class ISBNValidator:
    """
    Utilidad para la normalización y validación algorítmica de ISBNs.

    Implementa los estándares internacionales para ISBN-10 e ISBN-13, incluyendo la limpieza de caracteres no deseados, validación mediante expresiones regulares y el cálculo del dígito de control (Check Digit).
    """

    # ISBN-10: 9 dígitos seguidos de un dígito o 'X'
    ISBN_10_REGEX = re.compile(r'^[\d]{9}[\dXx]$')

    # ISBN-13: Prefijo 978 o 979 seguido de 10 dígitos
    ISBN_13_REGEX = re.compile(r'^97[89][\d]{10}$')

    @classmethod
    def clean(cls, isbn):
        """
        Limpia un ISBN eliminando guiones y espacios.

        Elimina guiones, espacios y cualquier carácter que no sea un número o la letra 'X'. Convierte el resultado a mayúsculas.

        Args:
            isbn (str): ISBN a limpiar.

        Returns:
            str: ISBN limpio.
        """

        if not isbn:
            return ''

        # Eliminamos cualquier carácter que no sea dígito o la letra X
        isbn_upper = str(isbn).upper()
        return re.sub(r'[^0-9X]', '', isbn_upper)

    @classmethod
    def is_valid_isbn10(cls, isbn):
        """
        Valida si es un ISBN-10 válido.

        Verifica primero el formato por regex y luego calcula la suma ponderada de los dígitos para validar el dígito de control.

        Args:
            isbn (str): ISBN de 10 caracteres a validar.

        Returns:
            bool: True si es válido.
        """

        isbn_clean = cls.clean(isbn)
        if not cls.ISBN_10_REGEX.match(isbn_clean):
            return False

        # Cálculo del dígito de control (Suma ponderada)
        total = 0
        for i in range(9):
            total += int(isbn_clean[i]) * (10 - i)

        last_char = isbn_clean[9]
        total += (10 if last_char == 'X' else int(last_char))

        return total % 11 == 0

    @classmethod
    def is_valid_isbn13(cls, isbn):
        """
        Valida si es un ISBN-13 válido.
        Verifica el formato y aplica la suma ponderada.

        Args:
            isbn (str): ISBN a validar.

        Returns:
            bool: True si es válido.
        """

        isbn_clean = cls.clean(isbn)
        if not cls.ISBN_13_REGEX.match(isbn_clean):
            return False

        # Cálculo del dígito de control
        total = 0
        for i in range(13):
            factor = 3 if i % 2 else 1
            total += (10 if isbn_clean[i] == 'X' else int(isbn_clean[i])) * factor

        return total % 10 == 0

    @classmethod
    def is_valid(cls, isbn):
        """
        Valida si es un ISBN válido (10 o 13).

        Args:
            isbn (str): ISBN a validar.

        Returns:
            bool: True si es válido.
        """

        return cls.is_valid_isbn10(isbn) or cls.is_valid_isbn13(isbn)

    @classmethod
    def format_isbn(cls, isbn):
        """
        Formatea un ISBN con guiones según estándar.

        Args:
            isbn (str): ISBN a formatear.

        Returns:
            str: ISBN con guiones según su tipo o cadena original si es inválida.
        """

        isbn_clean = cls.clean(isbn)

        if not cls.is_valid(isbn_clean):
            return isbn

        if len(isbn_clean) == 13:
            return f"{isbn_clean[:3]}-{isbn_clean[3]}-{isbn_clean[4:7]}-{isbn_clean[7:12]}-{isbn_clean[12]}"
        else:
            return f"{isbn_clean[0]}-{isbn_clean[1:4]}-{isbn_clean[4:9]}-{isbn_clean[9]}"

    @classmethod
    def get_isbn_type(cls, isbn):
        """
        Determina el tipo de ISBN.

        Args:
            isbn (str): ISBN a analizar.

        Returns:
            str: 'ISBN-10', 'ISBN-13', o 'Invalid'.
        """

        isbn_clean = cls.clean(isbn)
        if cls.is_valid_isbn13(isbn_clean): return 'ISBN-13'
        if cls.is_valid_isbn10(isbn_clean): return 'ISBN-10'
        return 'Invalid'
