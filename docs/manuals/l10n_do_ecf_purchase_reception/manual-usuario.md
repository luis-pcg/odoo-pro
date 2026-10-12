# Recepción de e-CF de Proveedores — Manual de usuario

> Manual generado con `tools/manual-generator`: `node capture.mjs --config=configs/l10n_do_ecf_purchase_reception_usuario.json --db=test_v19_l10n_do_ecf_purchase_reception`. Las capturas se regeneran corriendo ese comando contra la base de pruebas.

Sus proveedores emiten facturas electrónicas (e-CF) y se las reportan a la DGII. Este módulo las trae solas a Odoo todas las noches y las deja en una bandeja.

Usted hace una sola cosa: decir a qué producto suyo corresponde cada línea de la factura del proveedor. Después da un botón y Odoo crea la orden de compra o la factura de proveedor, ya con su e-NCF, su código de seguridad y el XML firmado. Nada se contabiliza solo.

## Requisitos previos

- El administrador prende el módulo una vez; usted no configura nada.
- Hace falta el permiso **Administrador de facturación** para ver el menú.
- Todo vive en **Contabilidad ▸ Proveedores ▸ Recepciones**.

## La bandeja: qué le llegó de sus proveedores

**Contabilidad ▸ Proveedores ▸ Recepciones ▸ e-CF recibido.** Cada línea es una factura que un proveedor ya le reportó a la DGII.

El estado dice qué falta:

- **Por vincular** — hay que decirle a Odoo qué producto es cada línea.
- **Listo** — no falta nada, sólo dar el botón.
- **Hecho** — ya tiene su factura en Odoo.
- **Duplicado** — esa factura ya la digitaron a mano.
- **Error** — los montos del documento no cuadran.

La columna **Por vincular** dice cuántas líneas le faltan a cada documento.

![La bandeja: qué le llegó de sus proveedores](img/u01-bandeja.png)

## Cómo se lee un documento

Arriba, quién le facturó y con qué documento. Abajo, en **Líneas**, lo que le vendieron: artículo, cantidad, precio, ITBIS y total.

Nada de eso se escribe a mano ni se puede cambiar: es lo que el proveedor le reportó a la DGII, tal como salió del XML firmado. Lo único que le toca a usted es la columna **Producto de Odoo**.

![Cómo se lee un documento](img/u02-documento.png)

## Diga qué producto suyo es cada línea

Es la única tarea manual, y sólo la primera vez que ese proveedor le vende ese artículo.

- En **Producto de Odoo**, escoja el producto que corresponde al artículo del proveedor.
- La **varita** guarda el vínculo: la próxima factura de ese proveedor se vincula sola.
- El **+** crea el producto en Odoo cuando todavía no existe, con el nombre y el impuesto de la factura.

El icono a la izquierda del artículo dice cómo va cada línea:

- Visto verde — vínculo guardado; ese artículo se reconoce solo de aquí en adelante.
- Triángulo amarillo — producto puesto, vínculo sin guardar: dé la varita.
- Equis roja — todavía sin producto: escójalo, o créelo con el **+**.

Cuando ya ninguna línea queda pendiente, el documento pasa a **Listo**.

![Diga qué producto suyo es cada línea](img/u03-vincular.png)

## Cree la orden o la factura

Con el documento en **Listo**, escoja el botón según cómo se compró:

- **Crear factura** — compra sin orden: sale la factura de proveedor.
- **Crear orden** — sólo la orden de compra, para recibir la mercancía después.
- **Ordenar y facturar** — la orden, la recepción y la factura de un tirón.
- **Recibir y facturar** — aparece en lugar de los otros cuando la orden ya existe.

La factura nace en **borrador**, con el e-NCF, el código de seguridad y el XML del proveedor. Revísela y contabilícela como cualquier otra.

![Cree la orden o la factura](img/u04-crear.png)

## ¿Ya tenía la orden de compra o la factura? Vincúlela

Si a ese proveedor ya le había hecho la orden de compra o ya había digitado su factura (en borrador), no vincule las líneas una por una: dé **Vincular OC o factura** y escoja en **Vincular a** si es una **Orden de compra** o una **Factura de proveedor**.

Odoo le sugiere la orden que el proveedor puso en su factura, o la factura que tiene el e-NCF en la referencia; si no, la única que coincide. Si no sugiere ninguna, escójala usted: sólo aparecen documentos de ese proveedor y en la misma moneda.

Abajo verá cada artículo de la factura del proveedor al lado de la línea de su orden que le tocó. Odoo los empareja por producto, código o nombre; y si su orden llama al artículo de otra forma (*Mantenimiento* donde el proveedor puso *Servicio de instalación*), por **precio, ITBIS y cantidad**.

Con el aviso verde, dé **Vincular**: las líneas toman los productos del otro documento y Odoo los recuerda para la próxima vez.

- **Con una orden**, el documento pasa a **Listo**; dé **Recibir y facturar**. Se recibe y se factura sólo lo que trae la factura del proveedor; si la orden pedía más, el resto queda pendiente para la próxima.
- **Con una factura**, la factura recibe el e-NCF, el código de seguridad y el XML del proveedor, y el documento queda en **Hecho**.

Una misma orden puede recibir **varias facturas** del proveedor: cada una se vincula sólo con lo que trae. Lo que ya tomó otra factura vinculada no se le ofrece a la siguiente.

![¿Ya tenía la orden de compra o la factura? Vincúlela](img/u09-vincular-oc.png)

## Si Odoo no sabe cuál línea de la orden es, escójala usted

Cuando dos líneas de su orden tienen el mismo precio, ITBIS y cantidad, Odoo no adivina: el artículo queda en rojo y el botón **Vincular** no aparece.

Haga clic en la columna **Línea de la orden** de ese artículo y escoja la línea correcta. El aviso pasa a verde y ya puede dar **Vincular**. Con esa misma columna puede corregir cualquier línea que Odoo haya emparejado mal.

![Si Odoo no sabe cuál línea de la orden es, escójala usted](img/u13-elegir-linea.png)

## Vincular la factura que ya había digitado

Si digitó la factura del proveedor antes de que llegara el e-CF y la dejó en **borrador**, escoja **Factura de proveedor** en **Vincular a**. Si en la **Referencia** puso el e-NCF, Odoo se la sugiere sola.

Para vincular, su factura tiene que tener exactamente las mismas líneas, cantidades, precios e ITBIS que la del proveedor, y el mismo total. Al dar **Vincular**, su factura recibe el e-NCF, el código de seguridad y el XML, y queda lista para contabilizar.

![Vincular la factura que ya había digitado](img/u11-vincular-factura.png)

## Orden que ya tenía su factura: se vinculan las dos

Si la orden de compra ya se había facturado (factura en borrador esperando el comprobante), al vincular la orden Odoo vincula también esa factura. El documento queda en **Hecho** con los dos botones arriba: **Compra** y **Factura**.

Y al revés: si vincula una factura que salió de una orden, la orden también queda vinculada.

![Orden que ya tenía su factura: se vinculan las dos](img/u12-oc-y-factura.png)

## «Esa factura ya la digité a mano»

El documento llega marcado **Duplicado** y le dice con cuál factura suya coincide.

Dé **Vincular factura**: no se crea nada nuevo; su factura de siempre se queda con el XML y el código de seguridad del proveedor.

![«Esa factura ya la digité a mano»](img/u05-duplicado.png)

## «El ITBIS del producto no es el que facturó el proveedor»

La línea sale en rojo y arriba aparece el aviso. Odoo respeta el impuesto de su producto y no deja crear la factura hasta que se aclare, porque uno de los dos está mal:

- Si el equivocado es su producto, corrija el impuesto en la ficha del producto.
- Si el equivocado es el proveedor, pídale la nota de crédito o use **Rechazar**.

![«El ITBIS del producto no es el que facturó el proveedor»](img/u06-impuesto.png)

## «Los montos no cuadran»

Estado **Error**: lo que suman las líneas no da el total que declaró el proveedor. Eso no se arregla en Odoo.

**Reintentar** vuelve a bajar el documento por si falló la descarga. Si sigue igual, es el proveedor quien tiene que corregirlo.

![«Los montos no cuadran»](img/u07-error.png)

## «La factura no coincide con la orden o la factura»

Odoo sólo vincula si **todo** coincide. El aviso rojo le dice qué no coincide, línea por línea:

- un artículo de la factura del proveedor que **no está** en su orden o en su factura;
- un artículo que podría ser **cualquiera de dos líneas** de su orden: escoja usted la correcta;
- con una orden, cantidad que **ya tomó otra factura** del proveedor vinculada a la misma orden;
- un **precio** o un **ITBIS** distinto;
- con una orden, **más cantidad** de la que le queda por facturar;
- con una factura, **otra cantidad**, una **línea de más** o **otro total**.

En ese caso el botón **Vincular** no aparece. Corrija su documento si el equivocado es él, o pídale al proveedor que corrija su factura.

![«La factura no coincide con la orden o la factura»](img/u10-oc-no-coincide.png)

## Aprobar o rechazar ante la DGII

La pestaña **Aprobación comercial** es su respuesta al proveedor delante de la DGII.

- **Aprobar** — usted reconoce la compra.
- **Rechazar** — usted no la reconoce: la DGII avisa al proveedor, que tendrá que emitir una nota de crédito o anular el documento.

Hay una **Fecha límite de aprobación** contada desde que el documento llegó. Rechazar no toca la factura que ya se haya creado.

![Aprobar o rechazar ante la DGII](img/u08-aprobacion.png)

## Notas

**Hay proveedores que se facturan solos.** Si el administrador marcó un proveedor con *Facturar sus e-CF automáticamente*, sus documentos aparecen ya en **Hecho** y con la factura en borrador esperando, siempre que todas las líneas se hayan vinculado solas. Lo que se automatiza es la digitación, nunca la contabilización.

**Cada documento sale por un solo camino.** Al escoger orden o factura, los demás botones desaparecen: un e-CF termina en una sola factura, que es como la DGII lo tiene registrado.

**Facturas con retenciones.** Cuando el e-CF trae retenciones, el documento se lo avisa arriba: se muestran aquí pero no se calculan en la factura. Revíselas antes de contabilizar.

**Si no ve un documento en la bandeja**, quite el filtro de la barra de búsqueda: la lista abre mostrando sólo lo pendiente.
