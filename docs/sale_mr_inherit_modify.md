# Ventas por Dimensiones (sale_mr_inherit_modify)

> Guía de usuario — no se requieren conocimientos técnicos.

## ¿Qué hace este módulo?

Este módulo está pensado para empresas que venden materiales **por dimensiones**: láminas, telas, vidrios, mallas, materiales de construcción, etc. En estos negocios, la cantidad que se vende no es un número directo, sino el resultado de multiplicar dos medidas.

**Ejemplo:** un cliente pide 5 piezas de tela de 3 metros de alto. La cantidad total es 5 × 3 = **15 metros**.

Sin este módulo, el vendedor tendría que hacer esa multiplicación a mano y escribir "15" en el pedido. Con este módulo, solo escribe **Piezas = 5** y **Altura = 3**, y Odoo calcula la cantidad automáticamente.

Además, esa información de piezas y altura **viaja con el pedido**: se puede consultar en el almacén (cuando se prepara la entrega) y en producción (cuando se fabrica el producto), para que todo el equipo trabaje con los mismos datos.

## ¿A quién beneficia?

| Rol | Beneficio |
|---|---|
| **Vendedor** | No hace cálculos manuales; menos errores al capturar pedidos |
| **Almacén** | Ve las piezas y altura vendidas directamente en la entrega |
| **Producción** | Ve qué cliente pidió, qué vendedor vendió y las dimensiones solicitadas |
| **Gerencia** | Información consistente de ventas a entrega y fabricación |

---

## Paso 1 — Instalación

1. Entrar a Odoo con un usuario administrador.
2. Ir al menú **Aplicaciones**.
3. En la barra de búsqueda, quitar el filtro "Aplicaciones" si está activo y buscar: `sale_mr_inherit_modify`.
4. Hacer clic en **Instalar**.
5. Esperar a que termine. Odoo instalará también, si no están ya, las aplicaciones de las que depende: **Ventas**, **Inventario** y **Fabricación**.

> No requiere configuración adicional. Una vez instalado, los campos nuevos aparecen automáticamente.

## Paso 2 — Crear un pedido de venta con dimensiones

1. Ir a **Ventas → Pedidos → Nuevo**.
2. Seleccionar el **Cliente**.
3. En las líneas del pedido, hacer clic en **Agregar producto** y elegir el producto.
4. En la línea del producto aparecen dos columnas nuevas (antes de la unidad de medida):
   - **Piece (Piezas):** cuántas piezas pide el cliente.
   - **Height (Altura):** la medida de cada pieza.
5. Al escribir cualquiera de los dos valores, la columna **Cantidad** se calcula sola:

   ```
   Cantidad = Piezas × Altura
   ```

   **Ejemplo:** Piezas = 5, Altura = 3 → Cantidad = 15.

6. Confirmar el pedido con el botón **Confirmar**.

> 💡 Si se cambia después el valor de Piezas o de Altura, la Cantidad se vuelve a calcular automáticamente.
>
> ⚠️ El cálculo automático funciona al editar el pedido en pantalla. Si la cantidad se modifica directamente (sin tocar Piezas/Altura), Odoo respeta el valor escrito.

## Paso 3 — Ver las dimensiones en la entrega (Almacén)

Al confirmar el pedido, Odoo crea automáticamente una **entrega** (albarán) para el almacén.

1. Desde el pedido de venta, hacer clic en el botón inteligente **Entrega** (arriba a la derecha), o ir a **Inventario → Órdenes de entrega**.
2. Abrir la entrega del pedido.
3. Hacer clic en el botón **Ver Cantidades**.
4. Odoo busca el pedido de venta de origen y copia las **Piezas** y la **Altura** de cada producto a las líneas de la entrega.
5. En el detalle de operaciones de la entrega aparecen ahora las columnas **Piece** y **Height** con los valores de la venta.

Así, la persona de almacén sabe exactamente cuántas piezas y de qué altura debe preparar, sin tener que abrir el pedido de venta.

> ⚠️ Si un mismo pedido tiene **dos líneas con el mismo producto** pero dimensiones distintas, el botón no puede distinguirlas: todas las líneas de ese producto en la entrega quedarán con los valores de una sola de ellas. En ese caso, conviene usar productos o variantes distintas por dimensión.

## Paso 4 — Ver las dimensiones en Fabricación

Si el producto vendido se fabrica (por ejemplo, se corta o se produce bajo pedido), Odoo genera una **orden de fabricación** a partir de la venta.

1. Ir a **Fabricación → Órdenes de fabricación**.
2. Abrir la orden generada desde el pedido de venta.
3. En el formulario aparecen, sin hacer nada adicional, los datos de la venta de origen:
   - **Cliente** que hizo el pedido.
   - **Vendedor** responsable de la venta.
   - **Piezas vendidas** y **Altura vendida**.
   - **Línea de venta** de origen (el vínculo con el pedido).

Con esto, producción sabe para quién fabrica y con qué dimensiones, sin salir de su pantalla.

> 💡 Si una orden de fabricación perdió el vínculo con su venta (caso poco común), existe una función interna de reparación (`find_qty`) que el equipo técnico puede ejecutar para reconectarla.

---

## El flujo completo de un vistazo

```
┌─────────────────────┐
│ 1. PEDIDO DE VENTA  │  Vendedor escribe Piezas y Altura
│    (Ventas)         │  → Cantidad = Piezas × Altura (automático)
└─────────┬───────────┘
          │ Confirmar pedido
          ├──────────────────────────────┐
          ▼                              ▼
┌─────────────────────┐      ┌─────────────────────────┐
│ 2. ENTREGA          │      │ 3. ORDEN DE FABRICACIÓN │
│    (Inventario)     │      │    (Fabricación)        │
│                     │      │                         │
│ Botón               │      │ Muestra automático:     │
│ "Ver Cantidades"    │      │ • Cliente               │
│ → copia Piezas y    │      │ • Vendedor              │
│   Altura de la venta│      │ • Piezas y Altura       │
└─────────────────────┘      └─────────────────────────┘
```

1. **Ventas** captura el pedido con dimensiones; la cantidad se calcula sola.
2. **Almacén** pulsa "Ver Cantidades" en la entrega y obtiene las dimensiones.
3. **Producción** ve cliente, vendedor y dimensiones en la orden de fabricación automáticamente.

## Preguntas frecuentes

**¿Tengo que configurar algo después de instalar?**
No. Los campos aparecen automáticamente en pedidos, entregas y órdenes de fabricación.

**¿Qué pasa si solo lleno Piezas pero no Altura?**
La cantidad será 0 (cualquier número × 0 = 0). Hay que llenar ambos campos.

**¿Las columnas Piece y Height no aparecen en mi pedido?**
Son columnas opcionales. Hacer clic en el icono de columnas (⚙ / ajustes de la lista de líneas) y activarlas.

**¿Funciona con productos que no se venden por dimensiones?**
Sí. Si no se llenan Piezas y Altura, el pedido funciona como siempre: se escribe la cantidad directamente.

**¿En la entrega no veo las dimensiones?**
Hay que pulsar el botón **Ver Cantidades** en la entrega; la copia no es automática.

---

*Módulo desarrollado por INDEXA SRL — versión 19.0 para Odoo 19.*
