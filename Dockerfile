# Odoo 20.0 development image — tracks the `master` branch.
#
# Odoo has not branched 20.0: the development series lives on `master`, and so
# does every submodule of this environment (odoo, enterprise, odoo-pro and
# odoo-pro/store-addons). There is no `odoo:20.0` image on Docker Hub, so this
# file reproduces the official odoo/docker 19.0 recipe (ubuntu:noble +
# wkhtmltopdf + postgresql-client + rtlcss) and installs the `master` nightly
# .deb instead of a released one.
#
# The .deb filename is NOT hardcoded: it is resolved from the `Packages` index
# of http://nightly.odoo.com/master/nightly/deb/ at build time, together with
# its sha1. That keeps the image on whatever master currently is without
# pinning a version string that goes stale the moment master renames itself
# from 19.5a1 to 20.0a1.
#
# Docker caches that layer, so a plain rebuild keeps the .deb it already has.
# To move the core forward:
#   docker compose build --no-cache-filter odoo   # take master's latest
# To pin an exact nightly instead (both args required):
#   docker compose build \
#     --build-arg ODOO_DEB=odoo_19.5a1.20260901_all.deb \
#     --build-arg ODOO_SHA=56598126bcde55865369743dad3190ac03665289
#
# Once Odoo publishes a real odoo:20.0 image, replace this whole file with
# `FROM odoo:20.0` plus the Indexa layers at the bottom, matching
# dev_env_odoo_pro-19.

FROM ubuntu:noble
LABEL maintainer="Odoo S.A. <info@odoo.com>"

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

# Generate locale C.UTF-8 for postgres and general locale data
ENV LANG=en_US.UTF-8

# Retrieve the target architecture to install the correct wkhtmltopdf package
ARG TARGETARCH

# Install some deps, lessc and less-plugin-clean-css, and wkhtmltopdf
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        dirmngr \
        fonts-noto-cjk \
        gnupg \
        libssl-dev \
        node-less \
        python3-magic \
        python3-num2words \
        python3-odf \
        python3-pdfminer \
        python3-pip \
        python3-phonenumbers \
        python3-pyldap \
        python3-qrcode \
        python3-renderpm \
        python3-setuptools \
        python3-slugify \
        python3-vobject \
        python3-watchdog \
        python3-xlrd \
        python3-xlwt \
        xz-utils && \
    if [ -z "${TARGETARCH}" ]; then \
        TARGETARCH="$(dpkg --print-architecture)"; \
    fi; \
    WKHTMLTOPDF_ARCH=${TARGETARCH} && \
    case ${TARGETARCH} in \
    "amd64") WKHTMLTOPDF_ARCH=amd64 && WKHTMLTOPDF_SHA=967390a759707337b46d1c02452e2bb6b2dc6d59  ;; \
    "arm64")  WKHTMLTOPDF_SHA=90f6e69896d51ef77339d3f3a20f8582bdf496cc  ;; \
    "ppc64le" | "ppc64el") WKHTMLTOPDF_ARCH=ppc64el && WKHTMLTOPDF_SHA=5312d7d34a25b321282929df82e3574319aed25c  ;; \
    esac \
    && curl -o wkhtmltox.deb -sSL https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.jammy_${WKHTMLTOPDF_ARCH}.deb \
    && echo ${WKHTMLTOPDF_SHA} wkhtmltox.deb | sha1sum -c - \
    && apt-get install -y --no-install-recommends ./wkhtmltox.deb \
    && rm -rf /var/lib/apt/lists/* wkhtmltox.deb

# install latest postgresql-client
RUN echo 'deb http://apt.postgresql.org/pub/repos/apt/ noble-pgdg main' > /etc/apt/sources.list.d/pgdg.list \
    && GNUPGHOME="$(mktemp -d)" \
    && export GNUPGHOME \
    && repokey='B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8' \
    && gpg --batch --keyserver keyserver.ubuntu.com --recv-keys "${repokey}" \
    && gpg --batch --armor --export "${repokey}" > /etc/apt/trusted.gpg.d/pgdg.gpg.asc \
    && gpgconf --kill all \
    && rm -rf "$GNUPGHOME" \
    && apt-get update  \
    && apt-get install --no-install-recommends -y postgresql-client \
    && rm -f /etc/apt/sources.list.d/pgdg.list \
    && rm -rf /var/lib/apt/lists/*

# Install rtlcss
RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm \
    && npm install -g rtlcss \
    && apt-get purge --autoremove -y npm \
    && rm -rf /var/lib/apt/lists/*

# Install Odoo from the master nightly build (master == the future 20.0)
ENV ODOO_VERSION=master
# Leave both empty to resolve master's current nightly; set both to pin one.
ARG ODOO_DEB=
ARG ODOO_SHA=
RUN base="http://nightly.odoo.com/${ODOO_VERSION}/nightly/deb" \
    && deb="${ODOO_DEB}" && sha="${ODOO_SHA}" \
    && if [ -z "${deb}" ]; then \
        packages="$(curl -sSL "${base}/Packages")" \
        && deb="$(printf '%s' "${packages}" | awk '/^Filename:/ {print $2}' | sed 's|^\./||' | tail -n1)" \
        && sha="$(printf '%s' "${packages}" | awk '/^SHA1:/ {print $2}' | tail -n1)" \
        && echo "resolved master nightly: ${deb} (sha1 ${sha})"; \
    fi \
    && [ -n "${deb}" ] && [ -n "${sha}" ] \
    && curl -o odoo.deb -sSL "${base}/${deb}" \
    && echo "${sha} odoo.deb" | sha1sum -c - \
    && apt-get update \
    && apt-get -y install --no-install-recommends ./odoo.deb \
    && rm -rf /var/lib/apt/lists/* odoo.deb

# Mount points for the filestore and for user addons
RUN mkdir -p /mnt/extra-addons && chown -R odoo /mnt/extra-addons
VOLUME ["/var/lib/odoo", "/mnt/extra-addons"]

EXPOSE 8069 8071 8072

# conf/ is bind-mounted over /etc/odoo by docker-compose
ENV ODOO_RC=/etc/odoo/odoo.conf

COPY ./wait-for-psql.py /usr/local/bin/wait-for-psql.py
RUN chmod +x /usr/local/bin/wait-for-psql.py

# ─── Indexa layers (mirrors dev_env_odoo_pro-19) ──────────────────────────────

USER root

# 1. Instalamos dependencias Python
COPY ./requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt --break-system-packages --ignore-installed

# pyazul se instala desde el source local para que pip genere metadata
COPY ./pyazul /tmp/pyazul
RUN pip3 install /tmp/pyazul --break-system-packages --ignore-installed

# 2. Copiamos nuestro entrypoint personalizado (arranca odoo bajo debugpy)
COPY ./entrypoint.sh /usr/bin/my_entrypoint.sh
RUN chmod +x /usr/bin/my_entrypoint.sh

# 3. Permisos del data_dir
RUN mkdir -p /var/lib/odoo/sessions && chown -R odoo:odoo /var/lib/odoo

USER odoo

# 4. Establecemos el nuevo entrypoint
ENTRYPOINT ["/usr/bin/my_entrypoint.sh"]
CMD ["odoo"]
