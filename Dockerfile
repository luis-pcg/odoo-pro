# Odoo has not branched 20.0: the development series lives on `master`, and
# Odoo publishes no Docker image for it. ghcr.io/indexa-git/odoo:master fills
# that gap — same recipe as the official odoo:<series> images, built from the
# master nightly .deb, published from odoo-pro/docker/odoo-master.
#
# So this file stays the same shape as dev_env_odoo_pro-19's: a base image plus
# the Indexa layers. Swap the tag for odoo:20.0 once Odoo ships one.
#
#   docker compose pull   # take a newer master build
FROM ghcr.io/indexa-git/odoo:master

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
