from unittest.mock import patch
from odoo.exceptions import UserError  # type: ignore
from odoo.addons.png_biblioteca.services.api_service import BookAPIService  # type: ignore
from .common import BibliotecaCase

# Resultados falsos de Open Library: los tests no dependen de internet
FAKE_RESULTS = [
    {
        'title': 'Libro que ya tenemos',
        'author': 'Autor Uno',
        'isbn': '9780000000002',
        'year': 2010,
        'cover_id': '',
        'suggested_category': 'Ficción',
    },
    {
        'title': 'Libro con ISBN erróneo',
        'author': 'Autor Dos',
        'isbn': '9780000000027',
        'year': 2009,
        'cover_id': '',
        'suggested_category': None,
    },
    {
        'title': 'Libro nuevo',
        'author': 'Autor Tres',
        'isbn': '9780000000040',
        'year': 2010,
        'cover_id': '123',
        'suggested_category': 'Ficción',
    },
]


class TestSearch(BibliotecaCase):
    """
    Tests del asistente de búsqueda de libros (con la API simulada).
    """

    def _search(self, **vals):
        """
        Crea el asistente, lanza la búsqueda y lo devuelve.
        """

        wizard = self.env['png_biblioteca.book.search.wizard'].create(
            dict({'search_type': 'title', 'search_title': 'Prueba'}, **vals))
        wizard.action_search()
        return wizard

    @patch.object(BookAPIService, 'search_by_title', return_value=FAKE_RESULTS)
    def test_01_results_created(self, mock_search):
        """
        La búsqueda crea un resultado por libro y usa el idioma elegido.
        """

        wizard = self._search()
        self.assertEqual(len(wizard.result_ids), 3)
        self.assertEqual(wizard.state, 'results')
        mock_search.assert_called_with('Prueba', limit=10, language='spa')

    @patch.object(BookAPIService, 'search_by_title', return_value=FAKE_RESULTS)
    def test_02_any_language(self, mock_search):
        """
        Con el idioma 'Todos' no se filtra por idioma.
        """

        self._search(search_language='any')
        mock_search.assert_called_with('Prueba', limit=10, language=False)

    @patch.object(BookAPIService, 'search_by_title', return_value=FAKE_RESULTS)
    def test_03_existing_and_invalid_isbn(self, mock_search):
        """
        Se detectan los libros que ya están en la biblioteca y los ISBN no válidos.
        """

        existing, invalid, new = self._search().result_ids.sorted('id')

        self.assertEqual(existing.existing_book_id, self.book)
        self.assertTrue(existing.isbn_valid)

        self.assertFalse(invalid.isbn_valid)
        self.assertFalse(invalid.existing_book_id)

        self.assertTrue(new.isbn_valid)
        self.assertFalse(new.existing_book_id)

    @patch.object(BookAPIService, 'search_by_title', return_value=FAKE_RESULTS)
    def test_04_import_without_invalid_isbn(self, mock_search):
        """
        Un resultado con ISBN no válido se importa sin ISBN.
        """

        invalid = self._search().result_ids.sorted('id')[1]
        action = invalid.action_import()

        book = self.Book.browse(action['res_id'])
        self.assertEqual(book.name, 'Libro con ISBN erróneo')
        self.assertFalse(book.isbn)

    @patch.object(BookAPIService, 'download_cover', return_value=None)
    @patch.object(BookAPIService, 'get_google_data', return_value={})
    @patch.object(BookAPIService, 'get_book_by_isbn', return_value={
        'publisher': 'Salamandra', 'pages': 253, 'description': 'Sinopsis de prueba',
    })
    @patch.object(BookAPIService, 'search_by_title', return_value=FAKE_RESULTS)
    def test_05_import_new_book(self, mock_search, mock_isbn, mock_google, mock_cover):
        """
        Importar un resultado crea el libro, y en la siguiente búsqueda aparece como 'Ya en biblioteca'.
        """

        new = self._search().result_ids.sorted('id')[2]
        action = new.action_import()

        book = self.Book.browse(action['res_id'])
        self.assertEqual(book.isbn, '9780000000040')
        self.assertEqual(book.pages, 253)
        self.assertEqual(book.publisher, 'Salamandra')
        self.assertIn('Ficción', book.category_ids.mapped('name'))

        again = self._search().result_ids.sorted('id')[2]
        self.assertEqual(again.existing_book_id, book)

    @patch.object(BookAPIService, 'search_by_title', return_value=[])
    def test_06_no_results(self, mock_search):
        """
        Si la búsqueda no encuentra nada, se avisa al usuario.
        """

        with self.assertRaises(UserError):
            self._search()

    def test_07_search_invalid_isbn(self):
        """
        Buscar por un ISBN no válido da error sin llegar a consultar la API.
        """

        with self.assertRaises(UserError):
            self._search(search_type='isbn', search_isbn='1234567890123')