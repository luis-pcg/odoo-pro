# i18n generator — el `.po` lo escribe Odoo

Los archivos de traducción de nuestros módulos **no se escriben a mano**. Este
script crea una base, instala el módulo, activa el idioma y corre
`odoo i18n export`: los `msgid`, el orden de las entradas, las referencias `#:`
y los comentarios `#. odoo-python` los pone Odoo. Lo único nuestro son los
`msgstr`.

## Requisitos

- **Docker Desktop** corriendo, con el contenedor `${ODOO_DEVELOPER}_v19` arriba
  (`docker-compose up -d`).
- Credenciales y puertos se leen de `../../.env`.

## Uso

```bash
cd tools/i18n-generator
./generate-po.sh --module=l10n_do_hr_holidays
```

Ciclo de trabajo:

1. `./generate-po.sh --module=X` — escribe `X/i18n/es_DO.po` con lo que exportó
   Odoo y lista los términos sin traducir.
2. Rellenar esos `msgstr` en el archivo.
3. `./generate-po.sh --module=X` otra vez — reimporta lo traducido, reexporta y
   deja el archivo con el formato exacto de Odoo. Es idempotente: correrlo dos
   veces no cambia nada.

| Opción | Qué hace |
|--------|----------|
| `--module=<nombre>` | Módulo a exportar (obligatorio). Se busca en `odoo-pro/` y en `odoo-pro/store-addons/` |
| `--lang=<código>` | Idioma; por defecto `es_DO` |
| `--pot` | Exporta la plantilla `X/i18n/X.pot` en vez del `.po` |
| `--db=<nombre>` | Base a usar; por defecto `i18n_v19_<módulo>` |
| `--extra-modules=a,b` | Módulos extra a instalar (contexto que el módulo no depende) |
| `--fresh` | Borra y recrea la base |
| `--no-install` | Exige que la base exista; no instala nada |
| `--out=<ruta>` | Escribe el `.po` en otra ruta |
| `--check` | No toca el repo: exporta a un temporal y sólo reporta |
| `--strict` | Sale con código 1 si queda algún `msgstr` vacío (para CI) |

La base se conserva entre corridas, así que la segunda vez sólo hace `-u` del
módulo y tarda segundos.

## Qué resuelve

- `odoo i18n export` **no acepta** `--db_host/--db_user/--db_password`, sólo
  `-c`. El `/etc/odoo/odoo.conf` del contenedor no trae `db_host`, así que el
  script arma un conf temporal con las credenciales.
- Exportar un idioma que no está activo devuelve **todos los `msgstr` vacíos**:
  antes hay que `odoo i18n loadlang`.
- Una base vieja guarda traducciones viejas y el export las escribiría de vuelta
  encima de lo editado en el repo. Por eso, antes de exportar, el script hace
  `odoo i18n import -w` del `.po` que está en el repo: **lo editado manda**.
- Las traducciones de código Python salen con su comentario `#. odoo-python`,
  que es lo que hace que Odoo 16+ las cargue. Escritas a mano se olvidan y el
  término sale en inglés en producción.

## Un vacío que nunca se llena

Si el `msgstr` es idéntico al `msgid` (`"ID"` → `"ID"`), Odoo no guarda esa
traducción y el export la devuelve vacía en cada corrida. Sale en el reporte
para siempre y no es un error: por eso el script sólo falla con `--strict`.

## Archivos

| Archivo | Rol |
|---------|-----|
| `generate-po.sh` | Orquestador (base → instalar → idioma → import → export → reporte) |
| `report_untranslated.py` | Lista los `msgstr` vacíos del `.po`; código 1 si falta alguno |
