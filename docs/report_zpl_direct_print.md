# report_zpl_direct_print — Impresión directa de reportes vía QZ Tray (Odoo 19)

**Autor:** INDEXA SRL. (licencia propietaria)
**Versión:** 19.0.1.0.0
**Ubicación:** `odoo-pro/store-addons/report_zpl_direct_print`
**Dependencias Odoo:** `web`
**Dependencia Python externa:** `zplgrf` (`pip install zplgrf`) — solo para la ruta PDF→ZPL
**Dependencia de escritorio:** [QZ Tray](https://qz.io/) instalado en la máquina del usuario (cliente de impresión local vía websocket)

Reemplazo *clean-room* del módulo legado de Webkul `wk_odoo_directly_print_reports` (ver [doc del módulo legado](wk_odoo_directly_print_reports.md)). Paridad funcional, reescrito de forma idiomática para Odoo 19.

---

## 1. Qué cambió (resumen)

1. **Módulo nuevo `report_zpl_direct_print`** creado desde cero en `store-addons`, con paridad funcional al legado pero arquitectura Odoo-nativa.
2. **Dependiente migrado a v19:** `product_label_for_zebra_printer` ahora depende del módulo nuevo, hereda `report.zpl.template`, y se le eliminó su override `ir_action_report.py` (ya innecesario).
3. **Script de migración** en `upgrade-util` (`l10n_do_banks/19.0.1.0.0/pre-report-zpl-direct-print-merge.py`) que renombra modelos, re-homa toda la data al módulo nuevo y retira el legado.

## 2. Propósito a alto nivel

Al pulsar "Imprimir" en cualquier reporte configurado, el documento se **envía directamente a una impresora física (Zebra/ZPL)** en lugar de descargarse como PDF. Elimina el paso manual de: descargar PDF → abrir → Ctrl+P → elegir impresora. Pensado para impresión de **etiquetas** (productos, envíos, códigos de barras) en almacenes y puntos de venta.

## 3. Cómo funciona (arquitectura)

```
Usuario pulsa "Imprimir" (visor de reporte O menú "Imprimir" de lista/formulario)
        │
        ▼
doAction → _executeReportAction → registry "ir.actions.report handlers"
        │
        ▼
Handler "zpl_direct_print"  (orm.read de la config del reporte)
        │
        ├── report_user_action != 'send_to_printer' ──► return false ──► flujo estándar de Odoo (PDF/HTML/text)
        │
        └── report_user_action == 'send_to_printer'
                │
                ▼
        Servicio qz_tray: connect (websocket local en la PC del usuario)
                │
                ├── impresora configurada y detectada, sin multi-copia ──► imprime directo (1 copia)
                └── si no ──► diálogo OWL (selector de impresora y/o nº de copias)
                │
                ▼
        RPC: ir.actions.report.render_zpl(res_ids)
                │
                ├── use_template + plantilla   ──► render de la plantilla ZPL por registro (safe_eval)
                ├── reporte qweb-text          ──► texto renderizado tal cual (decodificado a str)
                └── reporte qweb-pdf           ──► PDF → ZPL/GRF con zplgrf (optimiza códigos de barras)
                │
                ▼
        qz.print(config, labels) con altPrinting:true ──► impresora Zebra  (disconnect en finally)
```

### Componentes

| Capa | Archivo | Rol |
|------|---------|-----|
| Backend | `models/ir_actions_report.py` | Extiende `ir.actions.report`; config + render/conversión a ZPL (`render_zpl`) |
| Backend | `models/report_zpl_printer.py` | Modelo `report.zpl.printer` (catálogo de impresoras, tipo ZPL) |
| Backend | `models/report_zpl_template.py` | Modelo `report.zpl.template` (plantillas ZPL con placeholders) |
| Frontend | `static/src/js/report_print_handler.js` | Handler registrado en `ir.actions.report handlers` |
| Frontend | `static/src/js/printer_dialog.js` / `.xml` | Diálogo OWL (impresora / copias) |
| Frontend | `static/src/js/qz_tray_service.js` | Servicio `report_zpl_qz_tray`: wrapper sobre el global `qz` (Promise nativa) |
| Frontend | `static/src/js/lib/` (qz-tray, rsvp, sha-256) | Librerías de terceros de QZ Industries (sin modificar) |

## 4. Modelos y campos

### `ir.actions.report` (extendido)

Nombres de campos idénticos al módulo legado para que la migración de datos sea copia directa (las columnas no se renombran).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `report_user_action` | Selection | `default` (acción normal de Odoo) o `send_to_printer` |
| `printer_id` | Many2one → `report.zpl.printer` | Impresora destino. Si no se define o QZ no la encuentra, el usuario elige en un diálogo |
| `printer_type` | related | Tipo de la impresora (solo `zpl`) |
| `use_template` | Boolean | Usar plantilla ZPL en lugar del render qweb |
| `report_template_id` | Many2one → `report.zpl.template` | Plantilla ZPL (dominio filtrado al mismo modelo del reporte) |
| `multi_copy_print` | Boolean | Pregunta el nº de copias en un diálogo |
| `default_copies` | Integer | Nº de copias por defecto (constraint: ≥ 1 cuando hay multi-copia) |

Configuración en **Ajustes → Técnico → Reportes**, pestaña **"Direct Printing"** del formulario de cada reporte.

Comportamiento: `onchange` limpia `use_template` si la impresora no es ZPL y fuerza `default_copies = 1` al desactivar multi-copia; `@api.constrains` exige `default_copies ≥ 1` con multi-copia.

Método de render (llamado desde JS vía ORM sobre el recordset del reporte):

- **`render_zpl(res_ids)`** → `list[str]`: un documento ZPL/texto por registro (plantilla) o por documento/página. Rutas: plantilla → qweb-text (decodifica bytes→str) → qweb-pdf (zplgrf; `UserError` si la librería falta). La config del reporte se lee en el handler JS vía `orm.read`.

### `report.zpl.printer` (nuevo)

Catálogo simple: `name` + `printer_type` (solo `zpl`). El nombre debe coincidir con el de la impresora registrada en QZ Tray. Menú: **Ajustes → Técnico → Reportes → Printers** (modo desarrollador).

### `report.zpl.template` (nuevo)

Plantillas ZPL escritas a mano con placeholders evaluados con **`safe_eval`** (no `eval()` como el legado):

- `{object.campo}` / `{record.campo}` / `{self.campo}` — el registro actual (`self` es alias por compatibilidad con plantillas migradas)
- `{template.campo}` / `{template_id.campo}` — la propia plantilla (usado por la geometría de etiquetas)
- Expresión inválida → `UserError` nombrando el placeholder que falló
- Pestaña "Help" en el formulario con la sintaxis y referencia a [labelary.com](http://labelary.com/)

Menú: **Ajustes → Técnico → Reportes → Report Templates** (modo desarrollador).

## 5. Flujo frontend (UX)

1. Usuario imprime un reporte. El handler hace `orm.read` de la config; si `report_user_action != 'send_to_printer'` retorna `false` y Odoo sigue su flujo normal (PDF).
2. JS conecta a QZ Tray. Si falla → notificación de error (tipo `danger`, sticky) y termina (sin fallback a PDF, paridad con el legado).
3. Si el reporte tiene `printer_id` y QZ la detecta:
   - Sin `multi_copy_print`: imprime 1 copia directo, sin diálogo.
   - Con `multi_copy_print`: diálogo OWL pidiendo nº de copias (prellenado con `default_copies`).
4. Si no hay impresora configurada o no se detecta: diálogo **selector de impresora** con la lista detectada por QZ Tray (+ campo de copias si aplica).
5. Se imprime con `altPrinting: true` (modo raw) y siempre se desconecta el websocket en `finally`.

## 6. Seguridad / permisos

- `ir.model.access.csv`: usuarios internos (`base.group_user`) **solo lectura** sobre impresoras y plantillas; administración (`base.group_system`) CRUD completo. (El legado daba CRUD a todos los usuarios sin grupo.)
- Placeholders evaluados con `safe_eval` (el legado usaba `eval()` sin sandbox).
- Menús ocultos tras `base.group_no_one` (modo desarrollador).

## 7. Diferencias vs `wk_odoo_directly_print_reports`

| Aspecto | Legado (Webkul) | `report_zpl_direct_print` |
|---------|------------------|----------------------------|
| **Intercepción de reportes** | **Copia completa** (~1700 líneas) del `makeActionManager` del core con `patch(actionService)` para sobreescribir `_executeReportAction` | Un **handler** en `registry.category("ir.actions.report handlers")` — el core ya enruta ahí; cero copia de código del action service |
| **Menú "Imprimir" de listas** | Segundo parche a `ActionMenus` (`inherit_action_menu.js`), con código roto (`this._super`, `this` mal ligado, llama `read` donde debía `get_zpl_data`) | **No hace falta**: el menú Print y el visor pasan ambos por `_executeReportAction` → el mismo handler los cubre |
| **Diálogos** | Modales jQuery/Bootstrap construidos a mano (`$('body').append(...)`, `.modal('show')`) | Componente **OWL** + servicio de diálogo |
| **Acceso a QZ Tray** | Lógica `qz.*` duplicada en los 2 archivos JS | Un único **servicio** `report_zpl_qz_tray`; usa **Promise nativa** (override de RSVP) |
| **Eval de plantillas** | `eval()` sin sandbox (riesgo de inyección) | `safe_eval` de Odoo, namespace acotado, `UserError` claro |
| **Render backend** | `report_routes()` reimplementaba el controlador HTTP de reportes | Llama directo `_render_qweb_pdf` / `_render_qweb_text` |
| **Modelos** | `wk_printer.printer`, `report.template` (prefijo vendor / nombre genérico) | `report.zpl.printer`, `report.zpl.template` (namespaced) |
| **Permisos** | CRUD para todos los usuarios | Lectura `group_user`, CRUD `group_system` |
| **Higiene de código** | `except` desnudos, spam de `_logger.info`, `templates.xml` referenciando un JS inexistente | Sin `except` ciegos, logging mínimo, sin assets muertos |
| **Compatibilidad de versión** | `pre_init_check` que bloquea fuera de Odoo 17; `installable: False` | v19 nativo, `installable: True` |
| **Sostenibilidad** | Se rompe en cada bump de Odoo (depende de la estructura interna del action service) | Solo depende del contrato público del registry → sobrevive upgrades |

## 8. Migración de datos (upgrade-util)

`upgrade-util/src/l10n_do_banks/19.0.1.0.0/pre-report-zpl-direct-print-merge.py` (corre solo si el legado está instalado):

1. **`rename_model`** ×2 (`report.template`→`report.zpl.template`, `wk_printer.printer`→`report.zpl.printer`): renombra tablas, relaciones m2o y conserva la data. Las columnas custom de `ir.actions.report` mantienen su nombre → migran intactas.
2. **`merge_module(legado → nuevo)`**: re-homa registro de módulo, dependencias (incluida la de `product_label_for_zebra_printer`), XML IDs y view keys; **luego** borra el registro del módulo legado y fuerza la instalación del nuevo. La data se migra **antes** de retirar el viejo (desinstalar antes lo borraría).
3. **Desinstalación defensiva**: si el legado siguiera presente tras el merge, `uninstall_module`.

## 9. Dependiente migrado: `product_label_for_zebra_printer`

- Manifest a v19 (`19.0.1.0.0`, `installable: True`, `depends: ['product', 'report_zpl_direct_print']`); se quitó `pre_init_check`.
- `product_barcode_config.py` ahora hereda `report.zpl.template`.
- **Se eliminó `ir_action_report.py`**: su único motivo era pasar `template_id` al parser; el módulo nuevo ya expone `template`/`template_id` en el namespace de `safe_eval`.
- El registro de plantilla y la report action de etiqueta se repuntan al modelo nuevo; la report action queda cableada (`use_template` + `report_template_id` + `send_to_printer`) para imprimir vía plantilla.

## 10. Requisitos de instalación

1. `pip install zplgrf` en el entorno Python del servidor (solo para reportes PDF).
2. Instalar QZ Tray en cada PC cliente que imprima.
3. Crear la impresora en Odoo con el mismo nombre que en QZ Tray.
4. Configurar el reporte: pestaña "Direct Printing" → *Send to Printer* + impresora (+ plantilla ZPL y/o copias opcionales).
