# report_direct_print — Impresión directa de reportes vía QZ Tray (Odoo 19)

**Autor:** INDEXA SRL. (licencia propietaria)
**Versión:** 19.0.1.0.0
**Dependencias Odoo:** `web`
**Dependencia Python externa:** `zplgrf` (`pip install zplgrf`) — solo para la ruta PDF→ZPL
**Dependencia de escritorio:** [QZ Tray](https://qz.io/) instalado en la máquina del usuario (cliente de impresión local vía websocket)

Reemplazo *clean-room* del módulo legado de Webkul `wk_odoo_directly_print_reports` (ver [doc del módulo legado](wk_odoo_directly_print_reports.md)). Paridad funcional, pero reescrito de forma idiomática para Odoo 19: handler del registry `ir.actions.report handlers` en vez de parchear el action service, diálogos OWL en vez de jQuery, `safe_eval` en vez de `eval()`, y migración automática de los datos del módulo legado.

---

## 1. Propósito a alto nivel

Al pulsar "Imprimir" en cualquier reporte configurado, el documento se **envía directamente a una impresora física (Zebra/ZPL)** en lugar de descargarse como PDF. Elimina el paso manual de: descargar PDF → abrir → Ctrl+P → elegir impresora. Pensado para impresión de **etiquetas** (productos, envíos, códigos de barras) en almacenes y puntos de venta.

## 2. Cómo funciona (arquitectura)

```
Usuario pulsa "Imprimir"
        │
        ▼
Handler "direct_print" en registry.category("ir.actions.report handlers")
        │
        ├── get_direct_print_config() devuelve False ──► comportamiento estándar de Odoo (descarga PDF)
        │
        └── reporte configurado como 'send_to_printer'
                │
                ▼
        Conecta con QZ Tray (websocket local en la PC del usuario)
                │
                ├── impresora configurada y detectada, sin multi-copia ──► imprime directo (1 copia)
                └── si no ──► diálogo OWL (selector de impresora y/o nº de copias)
                │
                ▼
        RPC: ir.actions.report.render_direct_print_documents()
                │
                ├── use_template + plantilla       ──► render de la plantilla ZPL por registro (safe_eval)
                ├── reporte qweb-text              ──► texto renderizado tal cual
                └── reporte qweb-pdf               ──► PDF → ZPL/GRF con zplgrf (optimiza códigos de barras)
                │
                ▼
        qz.print(config, docs) con altPrinting: true ──► impresora Zebra
```

### Componentes

| Capa | Archivo | Rol |
|------|---------|-----|
| Backend | `models/ir_actions_report.py` | Extiende `ir.actions.report`; config + render/conversión a ZPL |
| Backend | `models/direct_print_printer.py` | Modelo `direct.print.printer` (catálogo de impresoras, tipo ZPL) |
| Backend | `models/direct_print_template.py` | Modelo `direct.print.template` (plantillas ZPL con placeholders) |
| Backend | `hooks.py` | Migración desde los módulos legados (snapshot → uninstall → restore) |
| Frontend | `static/src/direct_print/direct_print_handler.js` | Handler registrado en `ir.actions.report handlers` |
| Frontend | `static/src/direct_print/direct_print_dialog.js/.xml` | Diálogo OWL (impresora / copias) |
| Frontend | `static/src/direct_print/qz_bridge.js` | Wrapper fino sobre el objeto global `qz` |
| Frontend | `static/src/lib/` (qz-tray, rsvp, sha-256) | Librerías de terceros de QZ Industries (sin modificar) |

## 3. Modelos y campos

### `ir.actions.report` (extendido)

Nombres de campos idénticos al módulo legado para que la migración de datos sea copia directa.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `report_user_action` | Selection | `default` (acción normal de Odoo) o `send_to_printer` |
| `printer_id` | Many2one → `direct.print.printer` | Impresora destino. Si no se define o QZ no la encuentra, el usuario elige en un diálogo |
| `printer_type` | related | Tipo de la impresora (solo `zpl`) |
| `use_template` | Boolean | Usar plantilla ZPL en lugar del render qweb |
| `report_template_id` | Many2one → `direct.print.template` | Plantilla ZPL (dominio filtrado al mismo modelo del reporte) |
| `multi_copy_print` | Boolean | Pregunta el nº de copias en un diálogo |
| `default_copies` | Integer | Nº de copias por defecto (constraint: ≥ 1) |

Configuración en **Ajustes → Técnico → Reportes**, pestaña **"Direct Print"** del formulario de cada reporte.

Métodos públicos (llamados desde JS vía ORM, ambos `@api.model`):

- **`get_direct_print_config(report_name)`** — devuelve `False` si el reporte no existe o no está configurado como `send_to_printer`; si no, dict con `report_id`, `printer_name`, `multi_copy_print`, `default_copies`. Búsqueda con `sudo()` (solo configuración).
- **`render_direct_print_documents(report_name, docids, data=None)`** — devuelve `list[str]` (un documento ZPL/texto por registro o página). La configuración se lee con `sudo()`, pero el **render corre con el entorno del usuario actual** (aplican record rules). Rutas: plantilla → qweb-text → qweb-pdf (zplgrf, import protegido con `UserError` si falta). Tipo de reporte no soportado → `UserError`.

### `direct.print.printer` (nuevo)

Catálogo simple: `name` (único) + `printer_type` (solo `zpl`) + `active`. El nombre debe coincidir con el de la impresora registrada en QZ Tray. Menú: **Ajustes → Técnico → Reporting → Direct Print Printers** (modo desarrollador).

### `direct.print.template` (nuevo)

Plantillas ZPL escritas a mano con placeholders:

- `{object.campo}` — interpola campos del registro; se evalúa con **`safe_eval`** (no `eval()` como el legado)
- `{self.campo}` — alias aceptado por compatibilidad con plantillas migradas del módulo legado
- Expresión inválida → `UserError` nombrando el placeholder que falló
- Pestaña "Help" en el formulario con la sintaxis y referencia a [labelary.com](http://labelary.com/viewer.html)

Menú: **Ajustes → Técnico → Reporting → Direct Print Templates** (modo desarrollador).

## 4. Flujo frontend (UX)

1. Usuario imprime un reporte. El handler consulta `get_direct_print_config()`; si devuelve `False`, retorna `false` y Odoo sigue su flujo normal (PDF).
2. JS conecta a QZ Tray. Si falla → notificación de error (tipo `danger`) y el flujo termina (sin fallback a PDF, paridad con el legado).
3. Si el reporte tiene `printer_id` y QZ la detecta:
   - Sin `multi_copy_print`: imprime 1 copia directo, sin diálogo.
   - Con `multi_copy_print`: diálogo pidiendo nº de copias (prellenado con `default_copies`).
4. Si no hay impresora configurada o no se detecta: diálogo **selector de impresora** con la lista detectada por QZ Tray (+ campo de copias si aplica).
5. Se imprime con `altPrinting: true` (modo raw) y siempre se desconecta el websocket en `finally`.

## 5. Seguridad / permisos

- `ir.model.access.csv`: usuarios internos (`base.group_user`) solo lectura sobre impresoras y plantillas; administración (`base.group_system`) CRUD completo. (El legado daba CRUD a todos los usuarios.)
- Placeholders evaluados con `safe_eval` (el legado usaba `eval()` sin sandbox).
- Menús ocultos tras `base.group_no_one` (modo desarrollador).

## 6. Migración desde el módulo legado (hooks.py)

Diseño: **snapshot → uninstall → restore**, todo dentro de la instalación de `report_direct_print`.

- **`pre_init_hook(env)`**
  1. `_snapshot_legacy_data(cr)`: copia a tablas temporales (`_report_direct_print_migr_*`) las filas de `wk_printer_printer`, `report_template` (incluyendo, si existen, las 8 columnas de geometría de `product_label_for_zebra_printer`) y la configuración de `ir_actions_report` (solo filas configuradas). Columnas opcionales protegidas con `_column_exists` (fallback `NULL`).
  2. `_remove_legacy_modules(cr)`: desinstala `product_label_for_zebra_printer` y `wk_odoo_directly_print_reports` con `upgrade-util` (`util.remove_module`) — esto elimina tablas y columnas legadas, por eso el snapshot va primero.
- **`post_init_hook(env)`** — `_restore_legacy_data(env)`: recrea impresoras (reutiliza por nombre), plantillas (resuelve `ir.model` por nombre; **hornea la geometría** reemplazando los tokens `{template_id.<col>}` por su valor numérico, de modo que las plantillas siguen funcionando sin el módulo de etiquetas), y reescribe la configuración sobre los mismos `ir.actions.report`. Al final dropea las tablas snapshot y loguea un resumen.
- Ambos hooks son no-op en bases de datos frescas.

### Script de migración

`migrate_wk_direct_print_v19.sh` (raíz del entorno dev) automatiza la corrida contra la BD dockerizada:

```bash
./migrate_wk_direct_print_v19.sh --db=MIBD --dry-run   # solo pre-checks (conteos legados)
./migrate_wk_direct_print_v19.sh --db=MIBD             # migra: -i report_direct_print
```

Post-checks: conteos de los modelos nuevos, estado `uninstalled` de los módulos legados, y falla (exit 1) si quedan tablas legadas o tablas snapshot huérfanas.

## 7. Requisitos de instalación

1. `pip install zplgrf` en el entorno Python del servidor (solo para reportes PDF).
2. Instalar QZ Tray en cada PC cliente que imprima.
3. Crear la impresora en Odoo con el mismo nombre que en QZ Tray.
4. Configurar el reporte: pestaña "Direct Print" → *Send to printer* + impresora (+ plantilla ZPL y/o copias opcionales).

## 8. Tests

- `tests/test_direct_print_template.py` — render de plantillas (`{object.x}` y alias `{self.x}`), múltiples registros, expresión inválida, unicidad de impresora.
- `tests/test_ir_actions_report.py` — constraint de copias, `get_direct_print_config`, ruta de plantilla end-to-end, tipo de reporte no soportado.
- `tests/test_migration_hooks.py` — crea tablas legadas falsas vía SQL, ejecuta `_snapshot_legacy_data` + `_restore_legacy_data` y verifica restauración + geometría horneada.
