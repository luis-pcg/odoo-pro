# Preajuste de PdV según el origen de la orden — Manual de usuario

> Manual generado con `tools/manual-generator`: `node capture.mjs --config=/Users/luisfernandez/repos/dev_env_odoo_pro-19/tools/manual-generator/configs/pos_preset_by_order_origin.json --db=test_v19_pos_preset_by_order_origin`. Las capturas se regeneran corriendo ese comando contra la base de pruebas.

El preajuste (*preset*) de una orden del punto de venta es lo que le dice al sistema qué **tarifa** y qué **posición fiscal** usar, es decir, qué impuestos y qué propina legal llevan las líneas. Hasta ahora dependía de que el cajero se acordara de elegirlo en cada orden.

Con el módulo **POS Preset by Order Origin** el preajuste se pone solo, según dónde nace la orden:

- Orden que **nace en una mesa** → preajuste de mesa (*Comer en el local*).
- Orden que **nace sin mesa**, en el mostrador → preajuste de venta directa (*Para llevar*).
- Venta directa que **después se lleva a una mesa** → cambia sola a *Comer en el local*.

El cajero conserva la última palabra: si cambia el preajuste a mano, el automatismo deja de corregir esa orden.

## Requisitos previos

- Odoo 19 con `point_of_sale` y `pos_restaurant` instalados.
- Módulo `pos_preset_by_order_origin` instalado.
- El PdV en modo restaurante (**Es un bar/restaurante**) y con al menos un piso con mesas.
- Preajustes activados en el PdV (**Para llevar / Entrega / Miembros**), con los dos preajustes del flujo en la lista *Disponible*.

## 1. Elegir los dos preajustes del PdV

Entra a **Ajustes → Punto de venta**, elige tu punto de venta y baja hasta **Para llevar / Entrega / Miembros**. Debajo de *Predeterminado* aparecen los dos campos del módulo:

1. **En mesa**: el preajuste de las órdenes que nacen en una mesa o que se pasan a una mesa. Normalmente *Comer en el local*.
2. **Venta directa**: el preajuste de las órdenes que nacen sin mesa, en el mostrador. Normalmente *Para llevar*.
3. **Predeterminado**: déjalo igual al de **Venta directa**. Si no, al tocar una mesa queda una orden vacía suelta en las pestañas.

Los dos campos sólo ofrecen preajustes de la lista *Disponible*, y sólo se ven cuando el PdV está en modo restaurante.

![1. Elegir los dos preajustes del PdV](img/01-ajustes-pdv.png)

## 2. Revisar los preajustes

Entra a **Punto de venta → Configuración → Preajustes** y abre los dos preajustes que acabas de elegir.

**Tarifa y posición fiscal**: cada preajuste lleva las suyas y **no tienen que coincidir**. Al contrario: es justo la posición fiscal del preajuste la que le dice al sistema qué impuestos aplicar, así que *Comer en el local* lleva la que incluye la propina legal del 10 % y *Para llevar* la que no. Cuando una orden cambia de preajuste, sus líneas se recalculan con la posición fiscal nueva y el total cambia. Eso es lo esperado.

**Lo único a tener en cuenta**: el módulo pone el preajuste mientras se crea la orden, sin abrir los diálogos del preajuste. Por eso, si el preajuste pide algo, Odoo lo reclama después, al cobrar:

- *Identificación* = **Nombre** o **Dirección** → al cobrar pide el nombre o el cliente. Con **No requerida** no pregunta nada.
- *Gestionar órdenes por tiempo* **encendido** → al cobrar pide la franja horaria. Se elige con el botón de la hora, en la barra superior del PdV. Déjalo encendido sólo si de verdad trabajas con franjas.

Ninguna de las dos cosas impide vender: sólo mueven la pregunta al momento del cobro.

![2. Revisar los preajustes](img/02-preajustes.png)

## 3. Tener mesas en el piso

Entra a **Punto de venta → Configuración → Mapa de pisos y mesas** y confirma que el piso tiene mesas. Sin mesas no hay dos orígenes que distinguir y el módulo no tiene nada que hacer.

En las capturas se usa un piso *Salón* con cuatro mesas.

![3. Tener mesas en el piso](img/03-mesas.png)

## 4. Abrir el punto de venta

Abre la caja registradora. El PdV entra al plano de mesas, y desde aquí salen los dos orígenes posibles: **tocar una mesa** o pulsar **Nueva orden** (venta directa en el mostrador).

![4. Abrir el punto de venta](img/04-plano-mesas.png)

## 5. Orden que nace en una mesa

Toca la **mesa 2** y captura un producto —aquí un *Café con leche*—.

La orden nace ya con el preajuste **Comer en el local**: se ve en el botón de preajuste, en la fila de acciones de la comanda. No hubo que elegir nada ni apareció ningún diálogo.

Ese botón recorta los nombres largos; el nombre completo se ve en **Órdenes** (paso 9).

![5. Orden que nace en una mesa](img/05-orden-en-mesa.png)

## 6. Venta directa en el mostrador

Vuelve al plano con **Mesas** y pulsa **Nueva orden**: eso crea una orden sin mesa. Captura un producto —aquí un *Brownie de nuez*, RD$ 140.00—.

El preajuste aplicado es **Para llevar**, y la etiqueta *Venta directa* de la barra superior confirma el origen.

![6. Venta directa en el mostrador](img/06-venta-directa.png)

## 7. El cliente se queda: asignar una mesa

El cliente decide quedarse. Pulsa **Asignar mesa**, escribe el número de mesa —la **4**— y confirma con **Asignar**.

Éste es el caso que más se repite en el mostrador: la orden ya existe, ya tiene líneas, y su origen cambia a mitad de camino.

![7. El cliente se queda: asignar una mesa](img/07-asignar-mesa.png)

## 8. La orden pasa a Comer en el local

Al asignar la mesa 4 el preajuste cambia solo a **Comer en el local**, sin tocar nada más.

En esta captura el total sigue siendo **RD$ 140.00** porque los dos preajustes de la base de ejemplo usan la misma tarifa y la misma posición fiscal. En una configuración real, donde *Comer en el local* lleva la posición fiscal con la propina legal del 10 % y *Para llevar* no, **el total se recalcula al asignar la mesa**: la propina entra y el total sube. Es el comportamiento correcto.

El mismo criterio vale para la tarifa: si los dos preajustes tienen tarifas distintas, al pasar la orden a la mesa se vuelven a calcular los precios de las líneas ya capturadas.

![8. La orden pasa a Comer en el local](img/08-mesa-asignada.png)

## 9. Verificar el preajuste de cada orden

Pulsa **Órdenes**: la lista muestra las órdenes abiertas con el preajuste de cada una en una etiqueta de color.

Se ven las dos del ejemplo, ambas ya en mesa y con **Comer en el local**: la que nació en la mesa 2 y la venta directa que acabó en la mesa 4.

Ésta es la pantalla donde conviene verificar: el botón de la comanda recorta los nombres largos, esta etiqueta no.

![9. Verificar el preajuste de cada orden](img/09-ordenes.png)

## 10. Cambiar el preajuste a mano

El botón de preajuste sigue funcionando. Aquí se pasa la orden de la mesa 4 a **Para llevar** a mano, porque el cliente cambió de idea y se lleva el pedido.

Desde ese momento el automatismo no vuelve a corregir **esa** orden: se sale al plano de mesas, se vuelve a entrar a la mesa 4 y la elección manual se mantiene.

Es una decisión por orden: la siguiente orden de esa misma mesa vuelve a nacer como *Comer en el local*.

![10. Cambiar el preajuste a mano](img/10-preajuste-manual.png)

## 11. Qué hace y qué no hace el módulo

- **Lo único que decide es el preajuste.** La tarifa, la posición fiscal y los impuestos los sigue aplicando Odoo igual que siempre, a partir del preajuste que quedó en la orden.
- **Al cambiar el preajuste, los totales cambian.** Si los preajustes tienen posiciones fiscales distintas (propina legal en mesa, sin propina para llevar), pasar una orden a una mesa recalcula sus impuestos. Con tarifas distintas, también sus precios.
- **No pregunta al crear la orden.** Si el preajuste pide identificación o franja horaria, Odoo lo reclama al cobrar, no al abrir la orden.
- **Pantalla de cocina.** Cambiar el preajuste después de mandar la orden a preparación se ve en cocina como un cambio de la orden.
- **No toca la numeración fiscal.** El preajuste no interviene en el NCF/e-CF ni en el cierre de sesión.
- **Fuera de alcance:** autopedido por celular y quioscos (`pos_self_order`).

Sin modo restaurante, o con los preajustes desactivados, el módulo queda inerte y el punto de venta se comporta exactamente como de fábrica.
