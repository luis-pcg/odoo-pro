# Estimación de esfuerzo — Integración Odoo → API de ventas MsMall (Sambil)

Módulo personalizado que envía de forma automatizada las ventas del punto de venta **SAMBIL** al API de recepción de ventas de MsMall, contrato `msmall_sales_v1`, conforme al manual técnico del proveedor (v1.0, 3-ago-2026).

La instancia del cliente tiene varios puntos de venta; **solo uno de ellos (SAMBIL) envía datos al API**. Los demás puntos de venta no se ven afectados.

La estimación se desglosa en los tres componentes solicitados.

---

## 1. Desarrollo del módulo

Cubre el alcance del documento de requerimiento: extracción y transformación de las ventas, autenticación con rotación de tokens, envío con idempotencia, manejo de errores y reintentos, y conciliación de lotes.

| # | Partida | Horas |
|---|---|---|
| 1 | Configuración del módulo: activación por punto de venta, identificadores `mall_id` / `local_id`, modalidad y almacenamiento seguro de credenciales | 1 h |
| 2 | Autenticación: obtención del token, renovación anticipada con rotación obligatoria, revocación y control de concurrencia | 1 h |
| 3 | Extracción y transformación de las ventas de SAMBIL al contrato `msmall_sales_v1` | 1.5 h |
| 4 | Envío de lotes: armado del payload, fragmentación, idempotencia y conservación del envío original | 1.5 h |
| 5 | Manejo de errores, reintentos con espera progresiva, cola de revisión y programación automática del envío | 1 h |
| 6 | Conciliación de contadores, pantalla de seguimiento de lotes y bitácora sin exposición de credenciales | 1 h |
| | **Total** | **7 h** |
| | **Rango** | **6 – 8 h** |

---

## 2. Puesta en marcha y certificación

**Este componente corre por cuenta del cliente** y se refleja como partida separada en la cotización. Comprende las pruebas y el proceso de certificación formal con el proveedor (casos T01–T12 del manual) hasta la activación en producción.

| # | Actividad | Horas |
|---|---|---|
| 1 | Carga de credenciales e identificadores, prueba de conectividad y prueba en vacío | 0.5 h |
| 2 | Ejecución y documentación de los casos de certificación T01–T12 | 1.5 h |
| 3 | Coordinación con MsMall, lote controlado y activación en producción | 1 h |
| | **Total** | **3 h** |
| | **Rango** | **2 – 4 h** |

Los doce casos cubren: disponibilidad del servicio, autenticación válida, prueba en vacío, inserción de una transacción, reenvío sin duplicar, rechazo por identificadores ajenos, rechazo por campo obligatorio faltante, renovación de token, envío de resumen diario, simulación de corte de comunicación, lote fragmentado y conciliación monetaria.

La ejecución depende de que MsMall entregue las credenciales y confirme la modalidad habilitada para el local.

---

## 3. Migraciones futuras

Costo recurrente que asume el cliente en cada actualización de versión de Odoo. El módulo es de trastienda —no modifica la pantalla del cajero— y su acoplamiento con el resto de Odoo es bajo.

| # | Actividad por versión | Horas |
|---|---|---|
| 1 | Revisión de los cambios de la nueva versión que afectan al módulo | 0.5 h |
| 2 | Ajuste de código y de vistas | 1 h |
| 3 | Repruebas y validación funcional contra el API | 1 h |
| | **Total por versión** | **2.5 h** |
| | **Rango** | **2 – 3 h** |

Aplica a la migración a Odoo 19 y a cada versión posterior. Si MsMall publica una versión 2 del contrato de datos, el ajuste no es una migración: se trata como desarrollo nuevo y requiere recertificación.

---

## 4. Consolidado

| Componente | Horas | Rango | Naturaleza |
|---|---|---|---|
| 1. Desarrollo del módulo | 7 h | 6 – 8 h | Una sola vez |
| 2. Puesta en marcha y certificación T01–T12 | 3 h | 2 – 4 h | Una sola vez, **a cargo del cliente** |
| 3. Migración por cada versión de Odoo | 2.5 h | 2 – 3 h | **Recurrente, a cargo del cliente** |
