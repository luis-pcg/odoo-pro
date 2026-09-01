# Manual Generator — Odoo Pro v20

Genera manuales de usuario (capturas + `README.md`) para cualquier módulo de
Odoo Pro v20, de forma reproducible. Crea una base limpia `test_v20_<módulo>`,
instala el módulo, opcionalmente siembra datos de ejemplo, navega la interfaz
con Playwright (Chrome del sistema) y arma el manual en
`docs/manuals/<módulo>/`.

## Requisitos

- **Docker Desktop** corriendo y el contenedor de Odoo arriba:
  ```bash
  docker-compose up -d        # contenedor ${ODOO_DEVELOPER}_v20
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
```

Salida: `docs/manuals/<módulo>/README.md` + `docs/manuals/<módulo>/img/*.png`.

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

Acciones soportadas en `steps`: `goto`, `waitFor` (+`timeout`), `fill`+`value`,
`click`, `press`, `wait` (ms). Un flujo con `screenshotEl: "<selector>"` captura
solo ese elemento; por defecto captura la página completa.

## Componentes

| Archivo | Rol |
|---------|-----|
| `generate-manual.sh` | Orquestador (base → instalar → seed → capturar → render) |
| `capture.mjs` | Login JSON-RPC + navegación + capturas (Playwright) |
| `render-manual.mjs` | Arma `README.md` desde el config y las capturas |
| `configs/<módulo>.json` | Contenido del manual + flujos |
| `configs/<módulo>.seed.py` | (opcional) datos de ejemplo vía `odoo shell` |
