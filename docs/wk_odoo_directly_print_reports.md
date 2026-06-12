# wk_odoo_directly_print_reports — Print Odoo Reports via Zebra Printer

> **⚠️ Módulo reemplazado en v19.** Este módulo fue sustituido por [`report_direct_print`](report_direct_print.md), una reimplementación *clean-room* para Odoo 19 que migra automáticamente impresoras, plantillas y configuración de reportes (hooks de instalación + script `migrate_wk_direct_print_v19.sh`). Este documento se conserva solo como referencia del comportamiento legado.

**Autor:** Webkul Software Pvt. Ltd. (módulo de pago, licencia propietaria)
**Versión:** 1.0.4
**Dependencias Odoo:** `base`, `web`
**Dependencia Python externa:** `zplgrf` (`pip install zplgrf`)
**Dependencia de escritorio:** [QZ Tray](https://qz.io/) instalado en la máquina del usuario (cliente de impresión local vía websocket)

---

## 1. Propósito a alto nivel

El módulo permite que, al pulsar "Imprimir" en cualquier reporte de Odoo, el documento se **envíe directamente a una impresora física (Zebra/ZPL)** en lugar de descargarse como PDF en el navegador.

El flujo elimina el paso manual de: descargar PDF → abrir → Ctrl+P → elegir impresora. Es útil sobre todo para impresión de **etiquetas** (productos, envíos, códigos de barras) en almacenes y puntos de venta.

## 2. Cómo funciona (arquitectura)

```
Usuario pulsa "Imprimir"
        │
        ▼
JS intercepta ir.actions.report (parche al action service / ActionMenus)
        │
        ├── report_user_action = 'default'  ──► comportamiento estándar de Odoo (descarga PDF)
        │
        └── report_user_action = 'send_to_printer'
                │
                ▼
        Conecta con QZ Tray (websocket local en la PC del usuario)
                │
                ▼
        RPC al backend: ir.actions.report.get_zpl_data()
                │
                ├── Reporte con plantilla ZPL configurada ──► parsea template con datos del registro
                ├── Reporte qweb-text "ZPL"               ──► renderiza texto tal cual
                └── Reporte qweb-pdf                      ──► renderiza PDF y lo convierte a ZPL/GRF
                                                              con la librería zplgrf (optimiza códigos de barras)
                │
                ▼
        qz.print(config, zpl_data) ──► impresora Zebra
```

### Componentes

| Capa | Archivo | Rol |
|------|---------|-----|
| Backend | `models/ir_actions_report.py` | Extiende `ir.actions.report`; renderiza/convierte el reporte a ZPL |
| Backend | `models/printer.py` | Modelo `wk_printer.printer` (catálogo de impresoras, solo tipo ZPL) |
| Backend | `models/report_template.py` | Modelo `report.template` (plantillas ZPL crudas con placeholders) |
| Frontend | `static/src/js/report_action_inherit.js` | Parche al action service: intercepta ejecución de `ir.actions.report` |
| Frontend | `static/src/js/inherit_action_menu.js` | Parche a `ActionMenus` (menú de impresión en vistas lista) |
| Frontend | `static/src/js/lib/qz-tray.js` (+ rsvp, sha-256) | Librería cliente de QZ Tray |

## 3. Modelos y campos

### `ir.actions.report` (extendido)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `report_user_action` | Selection | `default` (acción normal de Odoo) o `send_to_printer` |
| `printer_id` | Many2one → `wk_printer.printer` | Impresora destino. Si no se define, el usuario elige en un popup |
| `printer_type` | related | Tipo de la impresora (solo `zpl`) |
| `use_template` | Boolean | Usar plantilla ZPL en lugar del render qweb |
| `report_template_id` | Many2one → `report.template` | Plantilla ZPL (dominio filtrado al mismo modelo del reporte) |
| `multi_copy_print` | Boolean | Habilita impresión de múltiples copias (muestra popup con cantidad) |
| `default_copies` | Integer | Nº de copias por defecto (constraint: > 0) |

La configuración se hace en **Ajustes → Técnico → Reportes**, pestaña nueva **"Report Printing"** en el formulario de cada reporte.

### `wk_printer.printer` (nuevo)

Catálogo simple: `name` + `printer_type` (solo opción `zpl`). El nombre debe coincidir con el nombre de la impresora registrada en QZ Tray. Menú: **Ajustes → Técnico → Reportes → Printers** (visible solo en modo desarrollador).

### `report.template` (nuevo)

Plantillas ZPL escritas a mano con placeholders:

- `{self.campo}` — interpola campos/métodos del registro (se evalúa con `eval()` en el servidor)
- Pestaña "Help" en el formulario incluye ejemplo ZPL y referencia a [labelary.com](http://labelary.com/)

Menú: **Ajustes → Técnico → Reportes → Report Templates** (modo desarrollador).

Ejemplo de plantilla:
```
^XA
^CFA,30
^FO50,100^FD {self.name} ^FS
^FO50,140^FD {self.street} ^FS
^BY5,2,270
^FO100,350^BC^FD 11223344 ^FS
^XZ
```

## 4. Métodos backend clave (`ir_actions_report.py`)

- **`get_zpl_data(qweb_url, zpl_report, ctx_data, printer_name)`** — punto de entrada RPC desde JS. Decide ruta:
  1. Si el reporte tiene `use_template` → parsea plantilla por cada registro (`parse_template`).
  2. Si es reporte `qweb-text` con "ZPL" en el nombre → renderiza texto directo.
  3. Si es PDF → renderiza qweb-pdf, lo convierte página a página a ZPL con `GRF.from_pdf()` y `grf.to_zpl()` (con `optimise_barcodes()`).
- **`parse_template(template_text, model_name, model_id)`** — sustituye `{self.xxx}` evaluando contra el registro. ⚠️ Usa `eval()` sin sandbox — riesgo de inyección de código si usuarios no confiables editan plantillas.
- **`report_routes(reportname, docids, converter, data)`** — renderiza el reporte (pdf o text) replicando la lógica del controlador HTTP de reportes.
- **`get_zpl_report_data(id)`** — devuelve acción y nombre de impresora del reporte (con `sudo()`).

## 5. Flujo frontend (UX)

1. Usuario imprime un reporte configurado como `send_to_printer`.
2. JS conecta a QZ Tray (websocket local). Si falla → popup de error "Could Not Connect To QzTray."
3. Si el reporte tiene `printer_id` y QZ la encuentra:
   - Con `multi_copy_print`: popup pidiendo nº de copias (prellenado con `default_copies`).
   - Sin él: imprime 1 copia directo, sin diálogo.
4. Si no hay impresora configurada o no se encuentra: popup **"Select Printer"** con la lista de impresoras detectadas por QZ Tray (+ campo de copias si aplica).
5. Se imprime con `altPrinting: true` (modo raw de QZ) y se desconecta el websocket.

## 6. Seguridad / permisos

- `ir.model.access.csv`: acceso total (CRUD) a `report.template` y `wk_printer.printer` para **todos los usuarios** (sin grupo). Punto a revisar si se quiere restringir.
- Menús ocultos tras `base.group_no_one` (modo desarrollador).

## 7. Puntos de atención para migración a v19

- **`installable: False`** en el manifest actual y `pre_init_check` en `__init__.py` bloquea instalación fuera de Odoo 17 (`if not 16.0 < float(server_serie) <= 17.0: raise`). Hay que actualizar ambos.
- `report_action_inherit.js` **copia completa** del action service de Odoo 17 con parche vía `patch(actionService, ...)` — frágil; en v19 la estructura de `@web/webclient/actions/action_service` cambió y este archivo necesita reescritura (idealmente usar el registry `ir.actions.report handlers` en vez de reemplazar todo el servicio).
- `inherit_action_menu.js` tiene código muerto/roto: usa `this._super` con `patch()` moderno (no existe), `this.orm` dentro de callbacks `function()` (contexto `this` incorrecto), y llama `read` donde debería llamar `get_zpl_data` (línea 156).
- `views/templates.xml` referencia `action_manager_report.js` que **no existe** en el módulo (los assets reales se cargan vía manifest `assets`); el template parece legado y no está en `data` del manifest.
- Dependencia de jQuery (`$`) para los popups — desaconsejado en v19; migrar a diálogos OWL.
- `parse_template` usa `eval()` — considerar `safe_eval` de Odoo.

## 8. Requisitos de instalación

1. `pip install zplgrf` en el entorno Python del servidor.
2. Instalar QZ Tray en cada PC cliente que imprima.
3. Crear impresora en Odoo con el mismo nombre que en QZ Tray.
4. Configurar el reporte deseado: pestaña "Report Printing" → `Send To Printer` + impresora (+ plantilla ZPL opcional).
