# Colección Bruno — recepción de e-CF (Fixcal API v3)

Herramienta de desarrollo, no parte de ningún módulo: sirve para probar a mano
los mismos endpoints que consume `odoo-pro/l10n_do_ecf_purchase_reception`.
Abrir con [Bruno](https://www.usebruno.com/): *Open Collection* → esta carpeta.

## Antes de correr nada

1. Elegir el entorno arriba a la derecha: **test** o **prod**.
2. Poner la **API key**. En los dos entornos `api_key` está declarada como
   variable **secreta**: Bruno la guarda en tu máquina, fuera de la colección, y
   por eso ninguna key vive en este repo. El valor está en
   `odoo-pro/l10n_do_ecf_invoicing/lib/ecf_config.py` →
   `ECFConfig._API_KEYS`, entrada `V3` / `TEST` o `PRODUCTION`.
3. Poner `buyer_rnc` (el RNC de tu compañía) y `provider_rnc` / `issuer_rnc`
   (el RNC del proveedor emisor).

## Las trampas que esta colección deja a la vista

| # | Trampa | Dónde se nota |
|---|---|---|
| 1 | Las fechas del rango van en **headers** y en formato **DD-MM-YYYY**, mientras los bodies JSON usan ISO-8601 | `start_date` / `end_date` del entorno |
| 2 | `/invoices/all` **no tiene paginación**: hay que cortar por día y contrastar con `/invoices/count` | requests 1 y 3 |
| 3 | La respuesta del listado **no trae líneas**, sólo cabecera | request 1 |
| 4 | `xml_gcs_path` es un URI `gs://`, **no descargable por HTTP**; el XML se baja por `GET /{encf}/xml?issuer_rnc=` (documentado bajo *Emission*, no *Reception*) | request 4 |
| 5 | `total_amount` llega como **string** | request 1 |
| 6 | `date_issued` puede ser años anterior a `date_received`; el cron filtra por `date_received` | request 1 |
| 7 | En `POST /acecf/` **no se envían** `xml_gcs_path` ni `xml_checksum`: los genera el servicio | request 6 |
| 8 | Los endpoints de recepción **no requieren** `x-token` de DGII, sólo `x-api-key` + `env` | todos |

## Requests

1. `01-invoices-all` — motor del cron: todo lo recibido en un rango
2. `02-invoices-by-provider` — lo recibido de un proveedor
3. `03-invoices-count` — conteo y monto del período (control de completitud)
4. `04-ecf-xml` — XML firmado completo (aquí están las líneas)
5. `05-arecf` — acuse de recibo firmado (auditoría)
6. `06-acecf-approve` — aprobación comercial (`approval_status: 1`)
7. `07-acecf-reject` — rechazo comercial (`approval_status: 2` + `rejection_code`)
8. `08-commercial-approval-status` — estado de la aprobación comercial
9. `09-taxpayer-directory` — razón social de un RNC (crear el proveedor faltante)
