# Imagen base de Odoo versión 17.0
FROM odoo:17.0

# Cambiar al usuario root para realizar configuraciones administrativas
USER root

# Limpieza e instalación de dependencias
RUN apt-get clean && apt-get update --fix-missing \
    && apt-get install -y python3-pip --no-install-recommends \
    && pip3 install --no-cache-dir requests \
    && rm -rf /var/lib/apt/lists/*

# Copiar los addons locales al path de Odoo
COPY ./odoo/addons /mnt/extra-addons

# Cambiar de nuevo al usuario `odoo`
USER odoo

CMD ["odoo"]