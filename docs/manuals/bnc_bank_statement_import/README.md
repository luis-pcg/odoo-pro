# Importación de extractos Banesco — Manual de usuario (bnc_bank_statement_import)

> Manual generado con `tools/manual-generator`. Las capturas se regeneran ejecutando el generador contra una base `test_v20_<módulo>`.

Este módulo permite importar en Odoo el estado de cuenta tal como lo descarga la banca en línea de **Banesco**, sin reformatearlo. Formato: archivo de texto `.txt` separado por comas.

Se activa solo en los diarios cuya cuenta bancaria tiene *Entidad Bancaria* = **Banesco**; en cualquier otro diario el archivo sigue el camino estándar de Odoo.

## Requisitos previos

- Módulo **`bnc_bank_statement_import`** instalado (v `20.0.1.0.0`, Odoo 20.0).
- Dependencias: **`account_bank_statement_import`** (Enterprise) y **`l10n_do_banks`**.
- Un **diario de banco** cuya cuenta bancaria tenga *Entidad Bancaria* = **Banesco** y el mismo número de cuenta que trae el archivo (en el ejemplo `123456789`).
- Permiso de **Contabilidad** para importar extractos.

## 1. Marcar la cuenta bancaria del diario

En *Contabilidad → Configuración → Diarios*, el diario de banco apunta a una **cuenta bancaria**. En esa cuenta, pestaña *Información bancaria*, el campo **Entidad Bancaria** debe decir **Banesco (Banreservas)**. Es lo que el módulo consulta (`journal.bank_account_id.l10n_do_bank == "banesco"`) para saber que el archivo es de este banco.

En 20.0 el banco se guarda en la cuenta bancaria y no en un registro *Banco* aparte. Por eso el campo está aquí.

![1. Marcar la cuenta bancaria del diario](img/01-cuenta.png)

## 2. Subir el archivo desde la tarjeta del diario

En el *Tablero* de Contabilidad, botón **Subir** de la tarjeta del diario, se elige el archivo del banco (en el ejemplo `bnc_stmt.txt`). No aparece el asistente de columnas de Odoo: el módulo lee el formato del banco directamente y Odoo abre la conciliación bancaria con las transacciones del extracto nuevo.

![2. Subir el archivo desde la tarjeta del diario](img/02-importar.png)

## 3. Transacciones importadas

La lista de transacciones del diario muestra fecha, etiqueta, importe, saldo acumulado y el extracto al que pertenece cada una. A partir de aquí se concilian como cualquier otra transacción bancaria.

![3. Transacciones importadas](img/03-transacciones.png)

## 4. Qué pasa con otros diarios u otros archivos

- Si la cuenta del diario **no** está marcada como Banesco (Banreservas), el módulo no hace nada y el archivo sigue al siguiente lector (OFX, CAMT, CSV genérico…).
- Si el diario es de Banesco (Banreservas) pero el archivo no tiene su formato, también se deja pasar. Si ningún lector lo reconoce, Odoo responde *Could not make sense of the given file*.
- El módulo también pasa el contexto `skip_csv_check` para que el archivo no caiga en el asistente genérico de columnas.

## Notas

Verificado sobre Odoo 20.0 con Enterprise: el archivo de ejemplo del módulo se subió desde la tarjeta del diario en el cliente web.
