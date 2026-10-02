{
    "name": "Biblioteca Escolar",
    "summary": "Gestión de libros, usuarios, préstamos y categorías, con conexión a API externa.",
    "version": "17.0.1.4.0",
    "author": "Ataik7",
    "license": "LGPL-3",
    "category": "Education",
    "depends": ["base", "web", "mail"],

    "data": [
        # Seguridad
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "security/portal_rules.xml",

        # Menús
        "views/menus.xml",

        # Informes
        "reports/loan_report.xml",

        # Vistas
        "views/book_views.xml",
        "views/user_views.xml",
        "views/loan_views.xml",
        "views/category_views.xml",
        "views/wizard_views.xml",
        "views/loan_job_views.xml",

        # Datos
        "data/categories.xml",
        "data/cron.xml",
    ],

    "demo": [
        "demo/demo.xml",
    ],

    "assets": {
        "web.assets_backend": [
            "png_biblioteca/static/src/css/styles.css",
        ],
    },

    "external_dependencies": {
        "python": ["requests"],
    },

    "application": True,
}
