FROM odoo:17.0

USER root

# 1. Copiamos el requirements.txt e instalamos las librerías
COPY ./requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

# 2. Copiamos tu nuevo entrypoint personalizado
COPY ./entrypoint.sh /usr/bin/my_entrypoint.sh
RUN chmod +x /usr/bin/my_entrypoint.sh

# 3. Solucionamos el problema de permisos de una vez por todas
RUN mkdir -p /var/lib/odoo/sessions && chown -R odoo:odoo /var/lib/odoo

USER odoo

# 4. Establecemos el nuevo entrypoint
ENTRYPOINT ["/usr/bin/my_entrypoint.sh"]
CMD ["odoo"]