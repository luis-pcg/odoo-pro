# bsc_bank_statement_import — soporte del formato CSV 2026 de Banco Santa Cruz

| | |
|---|---|
| Tarea | #75495 — EXTRACTO BANCARIO - BANCO SANTA CRUZ |
| Módulo | `odoo-pro/bsc_bank_statement_import` (19.0.1.0.0) |
| Archivo analizado | `Transactions-export-20260930 (1).csv` (adjunto de la tarea, cliente INSUMED, enero 2026) |
| Fecha | 2026-10-05 |

## 1. Problema

Al importar el estado de cuenta CSV que hoy descarga Banco Santa Cruz, Odoo responde *"Could not make sense of the given file. Did you install the module to support this type of file?"* (el "formato no compatible" que reportan los clientes).

Causa: el banco cambió la estructura del archivo y el módulo solo reconoce el formato anterior (2019).

Flujo actual en `models/account_journal.py`:

1. `_parse_bank_statement_file` decodifica en `latin1` y llama a `_is_bsc_file`.
2. `_is_bsc_file` exige un número exacto de columnas en las 8 primeras filas: `{0: 6, 1: 6, 2: 1, 3: 2, 4: 4, 5: 0, 6: 6, 7: 3}`.
3. El archivo nuevo trae 1 columna en la fila 0. `_is_bsc_file` devuelve `False`, se llama a `super()` y la cadena termina en el `RedirectWarning` de `account_bank_statement_import`.

Aunque se quitara la validación, el parser leería mal el archivo, porque usa posiciones fijas del formato viejo: `line[0]` fecha, `line[1]` descripción, `line[2]` débito, `line[3]` crédito, y empieza en la fila 8.

## 2. Formato anterior vs. formato nuevo

### Formato anterior (soportado hoy, fixture `bsc_stmt_file/bsc_stmt.csv`)

```
Titular,Cuenta,Alias,Fecha del reporte,Sucursal,Balance
"XXX XXXXXXXXXXXL, X.X.X.",XXXXX-0XX,{Alias},22/11/2019,XXXXX XXXXXXXXXXXXX,"1,478,965.62"
Oficial que maneja su cuenta es : ...
Período,
Desde:,01/10/2019,Hasta:,31/10/2019

Fecha,Descripción,Débito,Crédito,Balance,
BALANCE AL INICIO DEL: ,"2,639,237.96",
04/10/2019,Por Transferencia Para Pago Nominas,"9,520.00",,"2,629,717.96",
```

### Formato nuevo (2026)

```
Banco Santa Cruz
ESTADO DE CUENTA,,,,,,Fecha Desde:,01/01/2026
,,,,,,Fecha Hasta:,31/01/2026
<TITULAR>,,,,,,Cuenta:,<NUMERO_CUENTA>
<DIRECCION>,,,,,,,
,,,,,,,


Fecha de Posteo,Fecha Efectiva,No. Cheque,No. Referencia,Descripci�n,Retiros,Dep�sitos,Balance,
"07/01/2026","07/01/2026","","214976585","Imp. 2.0 Por 1000 S/Ley 30-26",3.00,0.00,297.22,
...
"","","","","Totales:",957773.69,948718.40,0.00,
```

### Diferencias que afectan el parser

| Aspecto | Anterior | Nuevo | Impacto |
|---|---|---|---|
| Encabezado | 8 filas de forma fija | 6 filas de 8 columnas + 2 vacías; fila 0 de 1 columna | `_is_bsc_file` lo rechaza |
| Fila de títulos | índice 6 | índice 8, empieza por `Fecha de Posteo` | Debe ubicarse por contenido, no por índice |
| Columnas de detalle | 5: Fecha, Descripción, Débito, Crédito, Balance | 8: Fecha de Posteo, Fecha Efectiva, No. Cheque, No. Referencia, Descripción, Retiros, Depósitos, Balance | Mapeo nuevo |
| Saldo inicial | fila `BALANCE AL INICIO DEL:` | no existe | Se calcula (ver §3.4) |
| Montos | separador de miles (`"1,056,000.00"`), columna vacía si no aplica | sin separador (`400000.00`), la columna sin monto viene en `0.00` | `amount = Depósitos − Retiros` |
| Referencia | no existe | `No. Referencia`, única en el archivo (38/38) | Sirve como `unique_import_id` |
| Cuenta | anonimizada | `Cuenta:` en fila 3, columna 7 | Opcional (ver §3.5) |
| Orden | ascendente | fechas ascendentes, pero **dentro de cada día las filas van de la más reciente a la más antigua** | Hay que reordenar (ver §3.4) |
| Pie | ninguno | fila `Totales:` con fechas vacías | Hay que descartarla |
| Codificación | latin-1 | UTF-8 con el carácter `U+FFFD` (`EF BF BD`) ya grabado en lugar de los acentos | Texto irrecuperable; ver §3.6 |
| Fin de línea | LF | CRLF | `csv` lo maneja si se lee desde `io.StringIO` |
| Columna final | coma final | coma final (9 columnas efectivas) | Ignorar la columna 8 |

## 3. Cambios requeridos en el módulo

Todo el cambio vive en `bsc_bank_statement_import/models/account_journal.py`. El formato viejo se conserva, porque puede haber clientes con exportaciones antiguas o con otra variante del portal.

### 3.1 Detección de formato

Reemplazar la decisión binaria `_is_bsc_file` por dos detectores:

- `_is_bsc_legacy_file(rows)`: la validación actual de conteo de columnas, sin cambios.
- `_is_bsc_2026_file(rows)`: existe una fila cuyas 4 primeras celdas son `Fecha de Posteo`, `Fecha Efectiva`, `No. Cheque`, `No. Referencia`. Se compara solo con esas 4 porque las columnas 4 a 6 tienen los acentos dañados (`Descripci�n`, `Dep�sitos`) y no sirven como ancla.

Si ninguno coincide, `super()` como hoy.

### 3.2 Lectura del archivo

- Quitar la escritura a `/tmp/statement.csv`. Es un archivo compartido entre workers y entre bases de datos: dos importaciones simultáneas pueden pisarse. Se lee en memoria con `io.StringIO`.
- Decodificación: intentar `utf-8-sig` y, si falla, `latin1`. El archivo nuevo es UTF-8 válido y el viejo es latin-1; decodificar el nuevo como latin-1 convierte cada `�` en `ï¿½`.
- Se mantiene el filtro de `\0` que ya existe.

### 3.3 Mapeo de columnas (formato 2026)

| Índice | Columna | Uso |
|---|---|---|
| 0 | Fecha de Posteo | `date` (`%d/%m/%Y`) |
| 1 | Fecha Efectiva | no se usa (en la muestra siempre igual a la de posteo) |
| 2 | No. Cheque | `ref` si viene informado; si no, `No. Referencia` |
| 3 | No. Referencia | `unique_import_id` |
| 4 | Descripción | `payment_ref` |
| 5 | Retiros | negativo |
| 6 | Depósitos | positivo |
| 7 | Balance | saldo posterior al movimiento; se usa para `balance_start` / `balance_end_real` |

`amount = float(Depósitos or 0) - float(Retiros or 0)`. Se descartan las filas con menos de 8 columnas o con la columna 0 vacía; así se elimina la fila `Totales:`.

### 3.4 Orden y saldos

Dentro de un mismo día el banco lista primero el movimiento más reciente. Ejemplo del 09/01/2026:

| Fila | Movimiento | Balance |
|---|---|---|
| 1ª | Imp. 2.0 Por 1000 −10.65 | 17,738.20 |
| 2ª | Débito préstamo −7,101.15 | 17,748.85 |
| 3ª | Comisión −150.00 | 24,850.00 |
| 4ª | Transferencia recibida +25,000.00 | 25,000.00 ← primero del día |

Orden correcto: agrupar por fecha, fechas ascendentes e invertir las filas de cada día. Con ese orden, el `Balance` de cada fila es igual al saldo anterior más `amount`.

- `balance_start` = `Balance` de la primera transacción ya ordenada − su `amount`.
- `balance_end_real` = `Balance` de la última transacción ya ordenada.

Validado con el archivo de INSUMED: 38 líneas, saldo inicial **22,330.22**, final **13,274.93**, cero quiebres en la cadena de saldos. Retiros 957,773.69 y depósitos 948,718.40, que coinciden con la fila `Totales:` del banco.

Las líneas de extracto se crean en el orden de la lista, así que el reordenamiento también deja la conciliación en orden cronológico real.

**Interacción con `account_bank_statement_import_csv_patch`**: si la compañía tiene `create_statement_draft` activo, `account.bank.statement.create` sobrescribe `balance_start`/`balance_end_real` con el saldo del extracto anterior. Ese comportamiento se respeta; los saldos del archivo solo aplican cuando la opción está apagada.

### 3.5 Número de cuenta

El archivo trae `Cuenta:` (`11431000001331` en la muestra). Recomendación: **seguir devolviendo `None`** como cuenta del triplete `(currency, account, stmts)`, igual que hoy. Si se devuelve, `_find_additional_data` exige que coincida con `bank_account_id.sanitized_acc_number` del diario, y cualquier diferencia de formato en la cuenta configurada (guiones, ceros, cuenta sin cargar) produce *"The account of this statement (...) is not the same as the journal (...)"*, un error nuevo para clientes que hoy no lo tienen.

Si se quiere aprovechar como control, debe ir detrás de una comparación propia, tolerante a formato, y no por el contrato estándar.

### 3.6 Acentos dañados

El banco exporta el carácter de reemplazo `U+FFFD` en lugar de las letras acentuadas (`Comisi�n Por Cuota No Cobrada`, `M�DICOS`). El texto original no se puede reconstruir desde el archivo. Opciones:

- **Dejarlo como viene** (recomendado). Los montos, fechas y referencias no se ven afectados; solo la descripción muestra `�`.
- Sustitución de palabras conocidas (`Comisi�n` → `Comisión`). Frágil y sin fin; no se recomienda.

Conviene que el cliente lo reporte al banco: es un defecto de su exportación.

### 3.7 Nombre y fecha del extracto

Mantener `name = "BSC <fecha de hoy> Bank Statement"` como hoy, o usar el período del encabezado (`Fecha Desde` / `Fecha Hasta`, filas 1 y 2, columna 7). `date` = fecha de la última transacción.

### 3.8 Duplicados

Hoy `unique_import_id` es `False`, así que importar el mismo archivo dos veces duplica las líneas. Con `No. Referencia` como `unique_import_id`, el núcleo antepone el id del diario y descarta las repetidas (*"N transactions had already been imported and were ignored."*). Solo aplica al formato 2026; el viejo no trae referencia.

### 3.9 Defecto existente en el formato viejo (opcional)

En el parser actual, `amount` es `float` en los débitos pero `str` en los créditos (`str(line[3]).replace(",", "")`). Odoo lo convierte al crear la línea, pero `_create_bank_statements` compara `line_vals['amount'] != 0` y suma `float(line_vals['amount'])`. Conviene convertir a `float` en ambos casos al tocar el archivo.

## 4. Esqueleto propuesto

Referencia de estructura; el nombre de los métodos y el detalle quedan a criterio de la implementación.

```python
import csv
import io
from datetime import datetime as dt

from odoo import _, fields, models

BSC_2026_HEADER = ("Fecha de Posteo", "Fecha Efectiva", "No. Cheque", "No. Referencia")


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _bsc_rows(self, data_file):
        try:
            text = data_file.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data_file.decode("latin1")
        return list(csv.reader(io.StringIO(text.replace("\0", "")), delimiter=",", quotechar='"'))

    def _bsc_2026_header_index(self, rows):
        return next(
            (i for i, row in enumerate(rows) if tuple(cell.strip() for cell in row[:4]) == BSC_2026_HEADER),
            None,
        )

    def _parse_bsc_2026(self, rows, header_index):
        by_date = {}
        for row in rows[header_index + 1 :]:
            if len(row) < 8 or not row[0].strip():
                continue
            line_date = dt.strptime(row[0].strip(), "%d/%m/%Y").date()
            by_date.setdefault(line_date, []).append(
                {
                    "date": line_date,
                    "payment_ref": row[4].strip(),
                    "ref": row[2].strip() or row[3].strip(),
                    "amount": float(row[6] or 0) - float(row[5] or 0),
                    "unique_import_id": row[3].strip() or False,
                    "balance": float(row[7] or 0),
                }
            )
        transactions = [line for day in sorted(by_date) for line in reversed(by_date[day])]
        if not transactions:
            return []
        balance_start = transactions[0]["balance"] - transactions[0]["amount"]
        balance_end = transactions[-1]["balance"]
        for line in transactions:
            del line["balance"]
        return [
            {
                "name": _("BSC %s Bank Statement", fields.Date.context_today(self)),
                "date": transactions[-1]["date"],
                "balance_start": balance_start,
                "balance_end_real": balance_end,
                "transactions": transactions,
            }
        ]

    def _parse_bank_statement_file(self, data_file):
        if not self._is_bsc_bank():
            return super()._parse_bank_statement_file(data_file)
        try:
            rows = self._bsc_rows(data_file)
        except csv.Error:
            return super()._parse_bank_statement_file(data_file)
        header_index = self._bsc_2026_header_index(rows)
        if header_index is not None:
            return [(None, None, self._parse_bsc_2026(rows, header_index))]
        if self._is_bsc_file(iter(rows)):
            return [(None, None, self._parse_bsc_legacy(rows))]
        return super()._parse_bank_statement_file(data_file)
```

`_parse_bsc_legacy` es el bucle actual (`for i, line in enumerate(reader): if i > 7: ...`) movido a su propio método, con el `float` corregido (§3.9).

Al pasar a `_()` con argumentos se arregla también el uso actual de `_(f"...")`, que impide la traducción del texto.

## 5. Pruebas

Fixture nuevo `bsc_stmt_file/bsc_stmt_2026.csv`, construido a partir del archivo de la tarea **anonimizado**: reemplazar titular, dirección, número de cuenta y los nombres de contrapartes en las descripciones (`INSUMOS MEDICOS DEL CARIBE INSUMED`, `NISSI WHOLESALE GROUP S.R.L.`). Mantener los `�` para cubrir el caso real.

Casos nuevos en `tests/test_account_bank_statement_import.py`:

| Caso | Verifica |
|---|---|
| Importación formato 2026 | Se crea el extracto; 38 líneas; montos y fechas coinciden con un `stmt_lines_2026` |
| Orden dentro del día | Las líneas del 09/01 quedan: +25,000.00, −150.00, −7,101.15, −10.65 |
| Saldos | `balance_start = 22330.22`, `balance_end_real = 13274.93` (con `create_statement_draft` apagado) |
| Fila `Totales:` | No genera línea |
| Reimportación | Segunda importación del mismo archivo no crea líneas nuevas (`unique_import_id`) |
| Formato viejo | `test_001` actual sigue pasando sin cambios |
| Diario no BSC | Archivo 2026 en diario sin `l10n_do_bank = "santa_cruz"` → `RedirectWarning` |
| Archivo UTF-8 con `U+FFFD` | `payment_ref` conserva `Comisi�n Por Cuota No Cobrada` (no `ï¿½`) |

```bash
odoo -d <db> -u bsc_bank_statement_import --test-tags /bsc_bank_statement_import --stop-after-init
```

Validación funcional: importar el adjunto original de la tarea en una base con un diario Banco Santa Cruz y comparar el saldo final contra el `Balance` de la primera fila del 30/01/2026 (13,274.93).

## 6. Alcance y pendientes

- Versión: 19.0. Evaluar el backport a 17.0 si los clientes afectados (Novomat, Insumed, SCS) están en esa serie.
- Subir la versión del manifiesto a `19.0.1.1.0`.
- Novomat y SCS: confirmar que también son clientes de Banco Santa Cruz y pedir un archivo de cada uno. Si usan otro banco, hay que revisar el importador de ese banco por separado; este documento no los cubre.
- Confirmar con el banco si el portal ofrece otras variantes (cuentas en USD, cuentas de nómina); la muestra es una cuenta corriente en DOP.
