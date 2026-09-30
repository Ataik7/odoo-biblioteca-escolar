from odoo import models, fields


class LoanJob(models.Model):
    """
    Historial de ejecuciones de las tareas programadas (CRON) de préstamos.
    Cada ejecución de un cron deja un registro con su resultado.
    """

    # Nombre técnico
    _name = 'png_biblioteca.loan.job'

    # Descripción
    _description = 'Historial de Tareas Programadas'

    # Más recientes primero
    _order = 'execution_date desc'

    # Nombre del cron ejecutado
    name = fields.Char(string="Tarea", required=True, readonly=True)

    # Momento de la ejecución
    execution_date = fields.Datetime(string="Fecha de Ejecución", default=fields.Datetime.now,
                                     required=True, readonly=True)

    # Resultado de la ejecución
    state = fields.Selection([
        ('done', 'Completado'),
        ('failed', 'Fallido'),
    ], string="Estado", required=True, readonly=True)

    # Número de préstamos afectados
    records_count = fields.Integer(string="Registros Procesados", readonly=True)

    # Resumen o error
    result_message = fields.Text(string="Mensaje de Resultado", readonly=True)
    error_message = fields.Text(string="Mensaje de Error", readonly=True)
