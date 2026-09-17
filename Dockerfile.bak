FROM odoo:19.0

USER root

# 1. Instalamos dependencias Python
COPY ./requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt --break-system-packages --ignore-installed

# pyazul se instala desde el source local para que pip genere metadata
COPY ./pyazul /tmp/pyazul
RUN pip3 install /tmp/pyazul --break-system-packages --ignore-installed

# 2. Copiamos tu nuevo entrypoint personalizado
COPY ./entrypoint.sh /usr/bin/my_entrypoint.sh
RUN chmod +x /usr/bin/my_entrypoint.sh

# 3. Solucionamos el problema de permisos de una vez por todas
RUN mkdir -p /var/lib/odoo/sessions && chown -R odoo:odoo /var/lib/odoo

USER odoo

# 4. Establecemos el nuevo entrypoint
ENTRYPOINT ["/usr/bin/my_entrypoint.sh"]
CMD ["odoo"]
