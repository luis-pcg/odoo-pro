# Manual Generator — Odoo Pro v19

Genera manuales de usuario (capturas + `README.md` + `manual.html` + `manual.pdf`)
para cualquier módulo de Odoo Pro v19, de forma reproducible. Crea una base limpia `test_v19_<módulo>`,
instala el módulo, opcionalmente siembra datos de ejemplo, navega la interfaz
con Playwright (Chrome del sistema) y arma el manual en
`docs/manuals/<módulo>/`.

## Requisitos

- **Docker Desktop** corriendo y el contenedor de Odoo arriba:
  ```bash
  docker-compose up -d        # contenedor ${ODOO_DEVELOPER}_v19
  ```
- **Node.js** (incluye `npm`). Playwright usa el **Google Chrome del sistema**
  (canal `chrome`), no descarga Chromium.
- Las credenciales/puertos se leen de `../../.env` (`ODOO_DEVELOPER`, `ODOO_PORT`,
  `DB_*`).

La primera ejecución instala `playwright` en `node_modules/` automáticamente
(con `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`).

## Uso

```bash
cd tools/manual-generator
./generate-manual.sh --module=report_zpl_direct_print
./generate-manual.sh --module=report_zpl_direct_print --keep-db   # conserva la base
./generate-manual.sh --module=report_zpl_direct_print --headed     # ver el navegador
./generate-manual.sh --module=l10n_do_hr_holidays \
  --extra-modules=l10n_do_hr_payroll,hr_work_entry_holidays        # instala mas modulos
```

```bash
./generate-manual.sh --module=l10n_do_ecf_purchase_reception \
  --config=configs/l10n_do_ecf_purchase_reception_usuario.json \
  --name=manual-usuario                                            # segundo manual
```

`--config` y `--name` sirven para un segundo manual del mismo módulo —uno corto
para el usuario final junto al de pruebas, por ejemplo—: la base y el seed son
los mismos, y los archivos salen como `<name>.md`, `<name>.html` y `<name>.pdf`
en la misma carpeta, sin pisar al primero. Las capturas conviven en el mismo
`img/`, así que los `id` de los flujos tienen que ser distintos.

`--extra-modules` instala modulos que el manual necesita para ilustrar el
contexto pero que **no** son dependencias del modulo documentado (nomina y work
entries, por ejemplo). Es preferible a instalarlos desde el seed: un
`button_immediate_install()` dentro de `odoo shell` recarga el registry y deja
el `env` del script a medias.

Salida, toda en `docs/manuals/<módulo>/`:

| Archivo | Qué es |
|---------|--------|
| `manual.pdf` | El entregable: portada, tabla de datos generales, revisión de casos de uso, barras de sección y capturas |
| `manual.html` | El mismo documento, para revisar la maqueta en el navegador sin reimprimir |
| `README.md` | El manual en Markdown, para leerlo en el repo |
| `img/*.png` | Una captura por flujo |

El diseño del PDF (portada, paleta `#0091c4`/`#073763`, tipografía Open Sans
incrustada) vive en `template.mjs` y es el mismo para todos los módulos: un
manual nuevo sólo escribe contenido en `configs/<módulo>.json`.

Para iterar el texto o la maqueta sin volver a manejar Odoo —que es la parte
lenta— se rearma desde las capturas que ya están en disco:

```bash
node capture.mjs --config=configs/<módulo>.json --db=test_v19_<módulo> --render-only
```

## Documentar un módulo nuevo

1. Crea `configs/<módulo>.json` (estructura del manual + flujos a capturar).
2. Opcional: `configs/<módulo>.seed.py` para precargar datos de ejemplo
   (se ejecuta dentro de `odoo shell`; el global `env` está disponible; termina
   con `env.cr.commit()`).
3. Corre `./generate-manual.sh --module=<módulo>`.

### Estructura de `configs/<módulo>.json`

```jsonc
{
  "module": "mi_modulo",
  "title": "Mi Módulo — Manual de usuario",
  "intro": "Texto introductorio (markdown).",
  "requirements": ["Requisito 1", "Requisito 2"],
  "flows": [
    {
      "id": "01-algo",                // nombre del archivo de captura (01-algo.png)
      "title": "1. Paso",
      "description": "Texto del paso (markdown).",
      "steps": [                       // acciones de Playwright para llegar a la pantalla
        { "goto": "/odoo/action-mi_modulo.mi_accion" },
        { "waitFor": ".o_list_view", "timeout": 30000 },
        { "fill": ".o_searchview_input", "value": "texto" },
        { "press": "Enter" },
        { "click": ".o_data_row:first-child .o_data_cell" },
        { "wait": 1000 }
      ]
    },
    {
      "id": "99-final",
      "title": "Paso solo texto",
      "description": "Sin captura.",
      "image": false                   // image:false => no toma screenshot
    }
  ],
  "notes": "Notas finales (markdown)."
}
```

Acciones soportadas en `steps`: `goto` (+`navbar`), `gotoXmlId` (+`action`),
`waitFor` (+`timeout`), `click`, `fill`+`value`, `press` (+`sel`), `scrollTo`,
`expand`, `wait` (ms).

`goto` espera el `.o_main_navbar` del cliente web; con `"navbar": false` no lo
espera, que es lo que hace falta para pantallas completas sin navbar como el
punto de venta (`/pos/ui/<id>`). En ese caso el `waitFor` del flujo decide
cuándo la pantalla está lista.

`gotoXmlId` resuelve el id por RPC (`ir.model.data.check_object_reference`, con
`active_test: False` para que un registro archivado —un cron que se instala
apagado, por ejemplo— también resuelva), así que sobrevive a una base
reconstruida y no depende del idioma de la interfaz como buscar el registro por
nombre. `expand` estira el viewport hasta el `scrollHeight` del elemento, para
paneles que hacen scroll por dentro (ajustes, `account_reports`).

Un flujo con `element: "<selector>"` captura sólo ese bloque (primer plano de un
recuadro de ajustes, por ejemplo); con `fullPage: true` captura la página
completa; `image: false` es una sección de sólo texto. `viewport: {"height": 620}`
acorta la ventana de ese flujo, para que una lista de diez líneas no salga con
media captura en blanco.

Claves del config que consume la maqueta del PDF: `cover` (`program`, `subject`),
`general` (filas de la tabla de datos generales), `cases` (revisión de casos de
uso, con `groups`/`items` y `ok: false` para marcar lo que no funcionó),
`database`, `notes`, y `section` en cada flujo para agruparlos bajo su barra azul.

## Componentes

| Archivo | Rol |
|---------|-----|
| `generate-manual.sh` | Orquestador (base → instalar → seed → capturar → render) |
| `capture.mjs` | Login JSON-RPC + navegación + capturas (Playwright) y armado de `README.md`/`manual.html`/`manual.pdf` |
| `template.mjs` | Maqueta del PDF: portada, paleta, barras de sección, checklists |
| `assets/` | Ilustración de portada, logo Progressa y la fuente Open Sans incrustada |
| `configs/<módulo>.json` | Contenido del manual + flujos |
| `configs/<módulo>.seed.py` | (opcional) datos de ejemplo vía `odoo shell` |
