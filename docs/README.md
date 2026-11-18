# Certificación de Retención — Guía de pruebas funcionales

Este documento es el guion para validar el módulo **Certificación de Retención**
antes de ponerlo en producción. Está escrito para que lo ejecute un consultor
funcional o un usuario de contabilidad, paso a paso desde la pantalla de Odoo.

No hace falta conocimiento técnico. Solo hay que seguir cada escenario, comparar
con el resultado esperado y marcar la casilla.

---

## ¿Qué hace el módulo?

Cuando la empresa le paga a un proveedor y le retiene una parte del monto (ISR,
ITBIS retenido, etc.), la DGII exige entregarle al proveedor un **Certificado de
Retención**: un documento formal que declara cuánto se le pagó y cuánto se le retuvo.

El módulo genera ese certificado en PDF **desde el pago**, con un botón.
Detecta automáticamente si el pago tuvo retención, sin importar la forma en que
se haya registrado contablemente, y arma el documento con el formato legal
correcto (hay dos: uno para sector público y otro para empresa privada).

---

## Cómo usar esta guía

- Cada escenario tiene **Objetivo**, **Pasos** y **Resultado esperado**.
- Marca `[x]` solo cuando el resultado esperado se cumpla tal cual.
- Si algo no coincide, anótalo en la tabla de la sección 10 con el número del escenario.
- Los ítems marcados con ⚠️ son **puntos de atención conocidos**. Si fallan, no es
  sorpresa, pero hay que documentar exactamente qué pasó para decidir si se corrige.

---

## 1. Preparación del ambiente

Antes de empezar hay que tener la base lista.

- [ ] La empresa está configurada con **país República Dominicana**.
- [ ] La empresa tiene **RNC** cargado en su ficha.
- [ ] La moneda de la empresa es **Peso Dominicano (DOP)**.
- [ ] El plan de cuentas dominicano está instalado.
- [ ] La ficha de la empresa tiene **logo, dirección, ciudad, provincia, teléfono y página web** cargados (todos salen impresos en el certificado).
- [ ] Existe al menos un proveedor de prueba con **RNC o Cédula** cargado.
- [ ] Existe un proveedor de prueba que sea **persona física** con su **tratamiento** (Sr./Sra./Lic.) cargado.
- [ ] El usuario de prueba tiene permisos de **Contabilidad**.

---

## 2. Configuración de las cuentas de retención

El módulo necesita saber **cuáles cuentas contables representan retenciones**.
Sin esto, nada funciona: el sistema no detecta ninguna retención.

**Ruta:** Contabilidad → Configuración → Plan de Cuentas → abrir una cuenta

- [ ] Al abrir una cuenta contable aparece la casilla **"Es una cuenta de retención"**.
- [ ] Mientras la casilla está desmarcada, los campos **"Base legal"** y **"Nombre del impuesto"** permanecen ocultos.
- [ ] Al marcar la casilla, ambos campos aparecen.

Configura al menos **dos** cuentas de retención para poder probar certificados
con varias retenciones a la vez:

- [ ] Cuenta de **ISR retenido**:
  - Nombre del impuesto: `ISR`
  - Base legal: `el Art. 309 del Código Tributario`
- [ ] Cuenta de **ITBIS retenido 30%**:
  - Nombre del impuesto: `ITBIS`
  - Base legal: `la Norma 02-05`
- [ ] Guardar y volver a abrir las cuentas: los datos quedaron grabados.

> **Importante para el usuario:** el "Nombre del impuesto" es el texto que sale como
> **encabezado de columna** en la tabla del certificado, y la "Base legal" es la frase
> que se cita en el párrafo legal. Si quedan vacíos, el certificado sale con la
> columna sin título o la frase legal incompleta.

- [ ] Dejar una cuenta de retención **sin** "Nombre del impuesto" e imprimir un certificado: verificar que el PDF sale igual (con la columna sin título) y **no** da error.
- [ ] Dejar una cuenta de retención **sin** "Base legal" e imprimir: el párrafo legal sale incompleto pero el PDF **no** da error.

---

## 3. Configuración del formato del certificado

**Ruta:** Ajustes → Ajustes generales → sección **Empresas** → **Certificación de Retención** → botón **"Setup document layout"**

- [ ] El botón abre una ventana de configuración.
- [ ] El campo **"Tipo de Certificación"** ofrece dos opciones: **Empresa Privada** y **Sector Público**.
- [ ] Al elegir **Empresa Privada**, los campos "Mostrar cabecera", "Mostrar pie de página" y "Slogan del año" **desaparecen** (solo aplican al formato público).
- [ ] Al elegir **Sector Público**, esos tres campos **aparecen**.
- [ ] El campo **"Firmas"** está disponible en ambos tipos.
- [ ] Guardar y volver a abrir la ventana: los valores quedaron grabados.

Prueba cada control:

- [ ] Con **Sector Público**, desmarcar **"Mostrar cabecera"** → el certificado sale **sin** el escudo nacional, el logo ni la dirección.
- [ ] Con **Sector Público**, desmarcar **"Mostrar pie de página"** → el certificado sale **sin** pie de página.
- [ ] Cambiar el texto de **"Slogan del año"** (por ejemplo, al lema oficial del año en curso) → el texto nuevo sale en la parte superior del certificado.
- [ ] Cambiar la tabla de **"Firmas"** poniendo los nombres y cargos reales de quienes firman → salen al final del certificado, en **ambos** formatos.
- [ ] Un usuario **sin** permisos de contabilidad no puede abrir esta ventana de configuración.

---

## 4. Escenarios de generación de retención

El módulo reconoce **cuatro formas distintas** de registrar una retención. Hay que
probar las cuatro, porque el certificado se arma de manera diferente en cada una.

### Escenario 4.1 — Retención descontada al momento de pagar

*La más común. Se paga menos de lo que dice la factura y la diferencia se manda a la cuenta de retención.*

**Pasos:**
1. Crear una factura de proveedor con NCF, por ejemplo por **RD$ 600.00**.
2. Confirmarla.
3. Presionar **Registrar Pago**.
4. Poner un monto **menor** al total, por ejemplo **RD$ 549.72**.
5. En "Diferencia de pago" elegir **Marcar como pagado completamente**.
6. En la cuenta de contrapartida elegir la **cuenta de retención de ISR**.
7. Confirmar el pago.

**Resultado esperado:**
- [ ] La factura queda **totalmente pagada** (saldo pendiente en cero).
- [ ] En el pago aparece el botón **"Imprimir Certificación"**.
- [ ] Al imprimir, el certificado muestra la retención de **RD$ 50.28** bajo la columna **ISR**.
- [ ] El "Total bruto" de la línea es **RD$ 600.00** y el "Total Pagado" es **RD$ 549.72**.

### Escenario 4.2 — Retención aplicada como impuesto en la factura

*La retención viene desde los impuestos de las líneas de la factura.*

**Pasos:**
1. Verificar que los impuestos de retención de compra (ej. `ISR 10%`, `ITBIS Retenido 30%`) estén configurados y que apunten a cuentas marcadas como retención (ver sección 2).
2. Crear una factura de proveedor con NCF.
3. En la línea, aplicar el **ITBIS 18%** más los **impuestos de retención**.
4. Confirmar la factura y verificar que el total a pagar ya viene **neto de retenciones**.
5. Registrar el pago por el monto pendiente completo.

**Resultado esperado:**
- [ ] El botón **"Imprimir Certificación"** aparece en el pago.
- [ ] El certificado muestra **una columna por cada retención** aplicada (ISR e ITBIS).
- [ ] Los montos de cada columna coinciden con los impuestos de retención de la factura.

### Escenario 4.3 — Un solo pago para varias facturas

**Pasos:**
1. Crear **dos** facturas de proveedor con retención en impuestos, al mismo proveedor.
2. Confirmarlas.
3. Seleccionar ambas desde la lista → **Registrar Pago** → activar **Agrupar pagos**.
4. Confirmar el pago único.

**Resultado esperado:**
- [ ] El certificado lista **las dos facturas**, una fila por cada una, con su NCF correspondiente.
- [ ] La fila de **Totales** suma las dos facturas.
- [ ] El monto en letras del párrafo coincide con el total pagado.

### Escenario 4.4 — Varios pagos parciales para una misma factura

**Pasos:**
1. Crear una factura de proveedor con retención en impuestos.
2. Confirmarla y pagarla en **dos abonos parciales** en fechas distintas.

**Resultado esperado:**
- [ ] Al imprimir desde **cualquiera** de los dos pagos, el certificado consolida la información completa de esa factura.
- [ ] La fecha que muestra el certificado es la del **pago más reciente**.
- [ ] No se generan dos certificados con montos duplicados.

### Escenario 4.5 — Retención registrada en un asiento contable aparte

*Se usa cuando la retención se contabiliza por separado y luego se concilia.*

**Pasos:**
1. Crear una factura de proveedor con NCF y confirmarla.
2. Crear un asiento contable manual: **débito** a la cuenta por pagar del proveedor, **crédito** a la cuenta de retención.
3. Confirmar el asiento.
4. Desde la factura, conciliar ese asiento contra el saldo pendiente.
5. Registrar el pago por el saldo restante.

**Resultado esperado:**
- [ ] El botón **"Imprimir Certificación"** aparece en el pago.
- [ ] El certificado muestra el monto retenido en el asiento manual.
- [ ] ⚠️ **Caso a vigilar:** si el asiento manual tiene **dos retenciones distintas por el mismo monto exacto**, el sistema puede asignarlas a la columna equivocada. Probar este caso específico y documentar el resultado.

---

## 5. Impresión del certificado

**Ruta:** Contabilidad → Proveedores → Pagos → abrir un pago

- [ ] En un pago **a proveedor** con retención, el botón **"Imprimir Certificación"** está visible.
- [ ] En un pago **recibido de un cliente**, el botón **no** aparece.
- [ ] En un pago a proveedor **sin** retención, el botón **no** aparece.
- [ ] En un pago en **borrador**, el botón **no** aparece.
- [ ] Si nadie ha configurado el "Tipo de Certificación" en la empresa, el sistema muestra el mensaje: *"No Withholding Certification Type found. Select one in company settings."* y **no** genera el PDF.
- [ ] Con el tipo configurado, al presionar el botón se **descarga el PDF**.
- [ ] En el historial del pago (la conversación de abajo) queda registrado el mensaje **"New Withholding Certification printed"**.
- [ ] El PDF queda **adjunto** al pago y se puede volver a descargar desde ahí.
- [ ] ⚠️ Al imprimir **dos veces** el mismo pago se generan **dos archivos adjuntos** con el mismo nombre. Confirmar con el cliente si esto es aceptable o si hay que evitar duplicados.

### Impresión desde la lista

- [ ] Desde la lista de Pagos, seleccionando varios pagos con retención, la opción de imprimir el certificado genera **un certificado por cada pago** en el mismo PDF.
- [ ] ⚠️ Si en esa selección se incluye un pago **sin** retención, ese pago sale como **página en blanco** en vez de mostrar un aviso. Documentar el comportamiento.

### Filtro de búsqueda

- [ ] En la lista de Pagos existe el filtro **"Tiene Retención"**.
- [ ] El filtro devuelve únicamente los pagos que tienen retención.
- [ ] Es útil para el cierre de mes: verificar que el conteo del filtro cuadre con los certificados que se deben emitir.

---

## 6. Revisión del certificado — formato **Empresa Privada**

Configurar "Tipo de Certificación" = **Empresa Privada**, imprimir y revisar el PDF.

- [ ] Usa el encabezado estándar de la empresa (logo y datos), **sin** escudo nacional.
- [ ] Arriba a la izquierda salen la **ciudad**, la **provincia** y la **fecha** en formato corto (ej. *18 de septiembre 2026*).
- [ ] El destinatario dice: **"Señores: DIRECCIÓN GENERAL DE IMPUESTOS INTERNOS — Ciudad."**
- [ ] El párrafo usa el verbo **"CERTIFICAMOS"**.
- [ ] Sale el **nombre completo** del proveedor y su **RNC/Cédula**, correctos.
- [ ] Si el proveedor es **persona física** con tratamiento, sale **"el/la Sr./Sra. Nombre"**.
- [ ] Si el proveedor es **empresa**, **no** sale el "el/la" delante.
- [ ] El monto total sale **en letras** y también en números.
- [ ] Por cada retención sale la frase: *"<Nombre del impuesto> por un monto de RD$ X"*.
- [ ] La frase legal final cita la **Base legal** configurada en la cuenta.
- [ ] Con **una sola** retención, la frase legal sale simple.
- [ ] Con **dos o más** retenciones, las bases legales se unen con **" y "** y la frase termina en **", respectivamente"**.
- [ ] La tabla tiene las columnas: **Fecha · Total bruto · NCF · (una por cada retención) · Total Pagado**.
- [ ] El **NCF** que aparece es el número fiscal real de la factura.
- [ ] La fila de **Totales** cuadra con la suma de las filas de arriba.
- [ ] Al final salen las **firmas** configuradas.

---

## 7. Revisión del certificado — formato **Sector Público**

Cambiar "Tipo de Certificación" a **Sector Público**, imprimir **el mismo pago** y revisar.

- [ ] El PDF cambió de formato respecto al anterior (mismo pago, documento distinto).
- [ ] En la cabecera salen el **escudo nacional**, el **logo de la institución**, la **dirección** y el **teléfono**.
- [ ] Debajo sale la línea: **PRESIDENCIA DE LA REPÚBLICA** · **RNC de la institución** · **página web**.
- [ ] Sale el **slogan del año** configurado.
- [ ] El párrafo usa el verbo **"CERTIFICA"** (singular, no "CERTIFICAMOS").
- [ ] El bloque de retenciones y la frase legal salen igual que en el formato privado.
- [ ] La tabla tiene las mismas columnas y los mismos montos.
- [ ] El párrafo de cierre menciona la **ciudad** y la **provincia** de la institución.
- [ ] La fecha de cierre sale escrita en letras y números, ej.: *"a los dieciocho (18) días del mes de septiembre del año dos mil veintiséis (2026)"*.
- [ ] Verificar que el **mes** salga bien escrito en español (probar imprimiendo en distintos meses o cambiando la fecha del sistema).
- [ ] Al final salen las **firmas** configuradas.
- [ ] ⚠️ **Revisar con lupa:** en este formato, las celdas de **Fecha** y de **NCF** pueden salir con el **signo de peso delante** (ej. `$18-09-2026`, `$B0100010001`). Si aparece así, reportarlo — es un defecto de presentación, no afecta los montos.

---

## 8. Validación de los montos

Esta es la parte que realmente le importa al cliente y a la DGII.

- [ ] **Total bruto** de cada línea = lo que se le pagó al proveedor **más** lo retenido.
- [ ] **Total Pagado** de cada línea = lo que efectivamente salió del banco.
- [ ] La diferencia entre el Total bruto y el Total Pagado de la fila de Totales **es exactamente** la suma de todas las retenciones.
- [ ] El **monto en letras** del párrafo coincide **exactamente** con el monto en números que aparece a su lado.
- [ ] Los centavos salen bien: un monto de `1,234.56` debe decir *"... Pesos con 56/100"*.
- [ ] Un monto cerrado como `1,000.00` debe decir *"... Pesos con 0/100"*.
- [ ] Los montos salen con **separador de miles** y **dos decimales**.
- [ ] Con **dos cuentas de retención** distintas, salen **dos columnas** y cada una suma solo lo suyo.
- [ ] Los montos del certificado **cuadran con el asiento contable** del pago (comparar contra el asiento).
- [ ] Los montos del certificado **cuadran con el reporte 606 / de retenciones** del mismo período.

### Casos de monto a vigilar

- [ ] ⚠️ **Facturas con distinta cantidad de retenciones en el mismo certificado:** hacer un pago agrupado donde **una factura tenga dos retenciones (ISR e ITBIS) y la otra solo una (ISR)**. Revisar que los montos queden **debajo de la columna correcta** y no corridos. Este caso es obligatorio probarlo.
- [ ] ⚠️ **Factura saldada con nota de crédito:** si una factura se concilió contra una nota de crédito o un asiento en vez de un pago, el certificado puede **no generarse o dar error**. Probar y documentar.
- [ ] ⚠️ **Retenciones con más de dos decimales:** probar una retención que dé, por ejemplo, `32.4108`. Verificar cómo redondea el certificado.

### Moneda extranjera

- [ ] Factura y pago en **dólares** → el certificado los convierte a la moneda de la empresa usando la tasa de la fecha del pago.
- [ ] ⚠️ El monto en letras **siempre dice "Pesos"** (es una exigencia de la DGII), pero el símbolo del número usa la moneda de la empresa. Si la empresa no opera en DOP, letras y símbolo no coinciden. Confirmar con el cliente si es aceptable.

---

## 9. Casos que **NO** deben generar certificado

- [ ] Pago a proveedor **sin** ninguna retención → sin botón, sin certificado.
- [ ] Pago **recibido de un cliente** → sin botón.
- [ ] Pago en **borrador** → sin botón.
- [ ] Pago **cancelado** → sin botón.
- [ ] Confirmar un pago con retención, imprimir, luego **restablecer a borrador** → el botón desaparece.
- [ ] Empresa configurada en **otro país** (no RD) → el botón no aparece aunque haya cuentas de retención marcadas.

---

## 10. Empresas múltiples

Solo aplica si el cliente maneja más de una empresa en la misma base.

- [ ] Cada empresa puede tener su **propio tipo de certificado, cabecera y firmas**.
- [ ] Estando en la Empresa A, abrir un pago de la Empresa B e imprimir el certificado.
- [ ] ⚠️ **Verificar con cuidado:** el certificado podría salir con el **formato de la empresa activa** en vez del de la empresa dueña del pago (por ejemplo, formato privado cuando debería ser público). Revisar que el logo, el RNC y las firmas correspondan a la **empresa del pago**.
- [ ] Las cuentas de retención de una empresa no aparecen en los certificados de la otra.

---

## 11. Verificación de no-regresión

Confirmar que el módulo no dañó lo que ya funcionaba.

- [ ] El flujo normal de facturas y pagos **sin** retención funciona igual que antes.
- [ ] La conciliación bancaria funciona normalmente.
- [ ] El widget de pagos en la factura (los enlaces azules de "pagado el...") sigue abriendo el asiento correcto.
- [ ] Las facturas de **cliente** no se vieron afectadas.
- [ ] La lista de Pagos con muchos registros (500+) carga sin lentitud notable.
- [ ] Si la base viene de una versión anterior del módulo: los certificados impresos antes de la actualización **siguen accesibles** como adjuntos, y reimprimir un pago antiguo da el mismo resultado.

---

## 12. Registro de resultados

| # Escenario | Fecha | Probado por | Resultado | Observaciones |
|---|---|---|---|---|
| 2 — Configuración de cuentas | | | ☐ OK ☐ Falla | |
| 3 — Configuración de formato | | | ☐ OK ☐ Falla | |
| 4.1 — Retención al pagar | | | ☐ OK ☐ Falla | |
| 4.2 — Retención en impuestos | | | ☐ OK ☐ Falla | |
| 4.3 — Un pago, varias facturas | | | ☐ OK ☐ Falla | |
| 4.4 — Varios pagos, una factura | | | ☐ OK ☐ Falla | |
| 4.5 — Retención en asiento | | | ☐ OK ☐ Falla | |
| 5 — Impresión | | | ☐ OK ☐ Falla | |
| 6 — Formato Empresa Privada | | | ☐ OK ☐ Falla | |
| 7 — Formato Sector Público | | | ☐ OK ☐ Falla | |
| 8 — Validación de montos | | | ☐ OK ☐ Falla | |
| 9 — Casos negativos | | | ☐ OK ☐ Falla | |
| 10 — Empresas múltiples | | | ☐ OK ☐ Falla | |
| 11 — No-regresión | | | ☐ OK ☐ Falla | |

**Criterio para aprobar el módulo:**

1. Los cinco escenarios de generación (4.1 a 4.5) generan certificado.
2. Los montos del certificado cuadran con la contabilidad y con el reporte de retenciones.
3. Ambos formatos de certificado salen completos y legibles.
4. Ningún punto ⚠️ quedó sin documentar.

---

## Anexo — Puntos de atención conocidos

Resumen de los ⚠️ repartidos en la guía, para revisarlos de un vistazo:

| # | Punto | Dónde probarlo |
|---|---|---|
| 1 | Columnas corridas cuando las facturas de un mismo certificado tienen distinta cantidad de retenciones | §8 |
| 2 | Posible error al certificar una factura saldada con nota de crédito o asiento en vez de pago | §8 |
| 3 | Signo de peso delante de la Fecha y el NCF en el formato Sector Público | §7 |
| 4 | El formato del certificado puede tomarse de la empresa activa y no de la empresa del pago | §10 |
| 5 | Dos retenciones del mismo monto exacto en un asiento manual pueden asignarse a la columna equivocada | §4.5 |
| 6 | El monto en letras siempre dice "Pesos" aunque la empresa opere en otra moneda | §8 |
| 7 | Imprimir un pago sin retención desde la lista produce una página en blanco | §5 |
| 8 | Imprimir dos veces el mismo pago genera adjuntos duplicados | §5 |
