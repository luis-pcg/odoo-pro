# Odoo IoT Box en Windows — Guía de Instalación y Configuración

Guía completa para instalar el IoT Box de Odoo en Windows (producción) y
conectarlo a una instancia en Odoo.sh. Una vez conectado, Odoo detecta
automáticamente todos los dispositivos (impresoras, lectores, básculas, etc.).

---

## Tabla de contenido

1. [Arquitectura del sistema](#1-arquitectura-del-sistema)
2. [Requisitos previos](#2-requisitos-previos)
3. [Preparar el equipo Windows](#3-preparar-el-equipo-windows)
4. [Ejecutar el instalador](#4-ejecutar-el-instalador)
5. [Verificar la instalación](#5-verificar-la-instalación)
6. [Conectar el IoT Box a Odoo.sh](#6-conectar-el-iot-box-a-odoosh)
7. [Configurar el POS para usar el IoT Box](#7-configurar-el-pos-para-usar-el-iot-box)
8. [Certificado SSL: opciones y consideraciones](#8-certificado-ssl-opciones-y-consideraciones)
9. [Mantenimiento y operación](#9-mantenimiento-y-operación)
10. [Solución de problemas](#10-solución-de-problemas)

---

## 1. Arquitectura del sistema

```
 ┌──────────────────┐          HTTPS / WebSocket
 │  Odoo.sh (cloud) │ ◄──────────────────────────────────────┐
 └──────────────────┘                                         │ outbound
          │ Odoo RPC                                          │
          │                                                   │
 ┌────────▼─────────────────────────────────────────────┐    │
 │  PC Windows (IoT Box)                                │    │
 │                                                      │    │
 │  ┌───────────┐     ┌───────────────────────────┐     │    │
 │  │   Nginx   │     │   Odoo IoT Process        │     │    │
 │  │ :443 HTTPS│────►│   :8069 (hw_drivers,      │─────┘    │
 │  │   :80 redir     │    hw_escpos, iot, …)      │          │
 │  └───────────┘     └────────────┬──────────────┘          │
 │                                 │                          │
 │                    ┌────────────▼──────────────┐           │
 │                    │  Windows Printer Spooler  │           │
 │                    │  / USB / Red (ESC/POS)    │           │
 │                    └───────────────────────────┘           │
 └──────────────────────────────────────────────────┘         │
          ▲  LAN                                               │
          │                                                    │
 ┌────────┴─────────┐                                         │
 │  Terminal POS    │  browser → https://IoT-IP               │
 │  (navegador)     │─────────────────────────────────────────┘
 └──────────────────┘
```

**Flujo de comunicación:**

- El IoT Box inicia una conexión **outbound** hacia Odoo.sh (no necesita IP pública ni puertos abiertos hacia internet).
- Los terminales POS se conectan al IoT Box por la **LAN local** usando HTTPS.
- El IoT Box traduce los comandos de Odoo en acciones sobre hardware local (impresora, báscula, lector, etc.).

---

## 2. Requisitos previos

### Hardware

| Componente | Mínimo | Recomendado |
|-----------|--------|-------------|
| CPU | 2 núcleos | 4 núcleos |
| RAM | 2 GB | 4 GB |
| Disco libre | 6 GB | 20 GB |
| Red | Ethernet (LAN fija) | Ethernet Gigabit |

> **Importante:** Usar IP estática o reserva DHCP para el PC del IoT Box.
> Los terminales POS necesitan conocer su IP para conectarse.

### Software del sistema

| Requisito | Versión | Notas |
|-----------|---------|-------|
| Windows | 10 (Build 17763) o Windows 11 | 64 bits obligatorio |
| PowerShell | 5.1+ | Incluido en Windows 10/11 |
| Acceso a internet | — | Para descarga inicial |

### Información necesaria antes de instalar

- [ ] URL de la instancia Odoo.sh (ej. `https://miempresa.odoo.com`)
- [ ] Token de emparejamiento IoT (obtenido en Odoo, ver sección 6)
- [ ] Nombre o IP de la impresora (USB o red)
- [ ] Certificado SSL (si no usas auto-firmado)

---

## 3. Preparar el equipo Windows

### 3.1 Asignar IP estática

1. Abrir **Configuración** > **Red e Internet** > **Ethernet** > **Editar**
2. Configurar:
   - Dirección IP: `192.168.1.XXX` (acorde a tu red)
   - Máscara: `255.255.255.0`
   - Puerta de enlace: IP de tu router
   - DNS: `8.8.8.8` / `8.8.4.4` (o DNS corporativo)
3. Anotar la IP asignada — se usará en la configuración del POS.

### 3.2 Habilitar ejecución de scripts PowerShell

Abrir PowerShell **como Administrador** y ejecutar:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine
```

### 3.3 Descargar el script de instalación

Copiar `install-odoo-iot.ps1` al equipo Windows.
Puede usarse cualquier directorio; el script se puede mover libremente.

> Los dispositivos (impresoras, básculas, lectores, etc.) **no necesitan
> configurarse antes de instalar**. Conectarlos al PC es suficiente.
> Odoo los detecta automáticamente después del emparejamiento.

---

## 4. Ejecutar el instalador

Abrir PowerShell **como Administrador** y navegar al directorio del script:

```powershell
cd C:\ruta\al\script
```

### 4.1 Selección de versión de Odoo

Si no se pasa el parámetro `-OdooVersion`, el script muestra un menú interactivo:

```
  Seleccionar version de Odoo a instalar:
  ─────────────────────────────────────────
*  [1] Odoo 17.0 — LTS (recomendado)
   [2] Odoo 16.0
   [3] Odoo 15.0
   [4] Odoo 14.0

  Opcion [1-4] (Enter = 1):
```

Presionar **Enter** selecciona 17.0 directamente.

Para pasar la versión directamente sin menú:

```powershell
.\install-odoo-iot.ps1 -OdooUrl "https://miempresa.odoo.com" -SelfSigned -OdooVersion "16.0"
```

### 4.2 Instalación básica (certificado auto-firmado)

```powershell
.\install-odoo-iot.ps1 `
    -OdooUrl   "https://miempresa.odoo.com" `
    -SelfSigned
```

El script pedirá seleccionar la versión de Odoo si no se especifica.

### 4.3 Instalación con certificado propio

```powershell
.\install-odoo-iot.ps1 `
    -OdooUrl      "https://miempresa.odoo.com" `
    -OdooVersion  "17.0" `
    -CertFile     "C:\certs\iot-server.crt" `
    -KeyFile      "C:\certs\iot-server.key"
```

### 4.4 Instalación completa con todos los parámetros

```powershell
.\install-odoo-iot.ps1 `
    -OdooUrl      "https://miempresa.odoo.com" `
    -OdooVersion  "17.0" `
    -IoTToken     "TU_TOKEN_AQUI" `
    -SelfSigned `
    -InstallDir   "D:\odoo-iot" `
    -HttpsPort    443 `
    -IoTPort      8069 `
    -ServiceName  "OdooIoT" `
    -CertCN       "iot-box.miempresa.local"
```

### 4.5 Parámetros disponibles

| Parámetro | Obligatorio | Default | Descripción |
|-----------|-------------|---------|-------------|
| `-OdooUrl` | **Sí** | — | URL de tu Odoo.sh |
| `-OdooVersion` | No | menú interactivo | Versión: `17.0`, `16.0`, `15.0`, `14.0` |
| `-IoTToken` | No | `""` | Token de emparejamiento (puede configurarse después) |
| `-InstallDir` | No | `C:\odoo-iot` | Directorio de instalación |
| `-HttpsPort` | No | `443` | Puerto HTTPS para el IoT Box |
| `-IoTPort` | No | `8069` | Puerto interno del proceso Odoo |
| `-CertFile` | Condicional | — | Ruta al certificado SSL propio |
| `-KeyFile` | Condicional | — | Ruta a la clave privada SSL |
| `-SelfSigned` | Condicional | — | Generar certificado auto-firmado |
| `-CertCN` | No | hostname | CN del certificado auto-firmado |
| `-ServiceName` | No | `OdooIoT` | Nombre base de los servicios Windows |
| `-Force` | No | false | Forzar reinstalación de componentes |
| `-SkipSourceDownload` | No | false | Usar fuente existente en `$InstallDir\odoo-src` |
| `-Proxy` | No | `""` | Proxy HTTP para descargas (entornos corporativos) |

### 4.5 Tiempo estimado

| Fase | Tiempo aprox. |
|------|--------------|
| Descarga Python | 2–3 min |
| Descarga Git | 1–2 min |
| Clonado Odoo (GitHub) | 5–15 min |
| Instalación dependencias Python | 5–10 min |
| Descarga/config Nginx + NSSM | 1–2 min |
| **Total** | **15–35 min** |

---

## 5. Verificar la instalación

### 5.1 Verificar servicios Windows

Abrir PowerShell y ejecutar:

```powershell
Get-Service OdooIoT, OdooIoTNginx | Select-Object Name, Status, StartType
```

Resultado esperado:

```
Name          Status  StartType
----          ------  ---------
OdooIoT       Running Automatic
OdooIoTNginx  Running Automatic
```

### 5.2 Verificar acceso web

Abrir un navegador en el mismo PC y navegar a:

```
https://localhost
```

Deberías ver la **homepage del IoT Box de Odoo** con:
- Estado de conexión a Odoo.sh
- Lista de dispositivos detectados
- Botón para configurar el servidor

> Si usaste certificado auto-firmado, el navegador mostrará una advertencia de seguridad.
> Hacer clic en **Avanzado** > **Continuar de todos modos**.

### 5.3 Verificar desde otro PC de la red

Desde cualquier terminal POS en la misma red LAN:

```
https://192.168.1.XXX
```

(Reemplazar con la IP estática del PC del IoT Box)

### 5.4 Verificar logs

```powershell
# Log principal de Odoo IoT
Get-Content "C:\odoo-iot\logs\odoo-iot.log" -Tail 30

# Log de Nginx
Get-Content "C:\odoo-iot\logs\nginx-error.log" -Tail 20

# Log en tiempo real
Get-Content "C:\odoo-iot\logs\odoo-iot.log" -Tail 10 -Wait
```

---

## 6. Conectar el IoT Box a Odoo.sh

### 6.1 Obtener el token de emparejamiento en Odoo

1. Iniciar sesión en tu instancia Odoo.sh.
2. Ir al módulo **IoT** (si no está instalado: Ajustes > Aplicaciones > buscar "IoT").
3. Clic en **IoT Boxes** > **Conectar**.
4. Se muestra un código/token de emparejamiento y un enlace de configuración.

   > Anotar el token. Tiene formato similar a: `eyJ0eXAiOiJKV1QiLCJhbG...`

### 6.2 Configurar el IoT Box

**Opción A — Vía web UI (recomendada):**

1. Abrir `https://<IP-del-IoT-Box>` en un navegador.
2. En la sección **Configuración del servidor**, ingresar:
   - **URL del servidor Odoo**: `https://miempresa.odoo.com`
   - **Token**: pegar el token obtenido en el paso anterior
3. Clic en **Conectar**.
4. El IoT Box se reiniciará y establecerá la conexión.

**Opción B — Editar el archivo de configuración:**

```powershell
notepad "C:\odoo-iot\conf\odoo.conf"
```

Modificar las líneas:

```ini
odoo_url  = https://miempresa.odoo.com
iot_token = TU_TOKEN_AQUI
```

Luego reiniciar el servicio:

```powershell
Restart-Service OdooIoT
```

### 6.3 Verificar conexión desde Odoo.sh

1. En Odoo.sh > módulo **IoT** > **IoT Boxes**.
2. El nuevo IoT Box debe aparecer con estado **Conectado** (punto verde).
3. Hacer clic en el IoT Box para ver dispositivos detectados.

---

## 7. Configurar el POS para usar el IoT Box

### 7.1 Activar IoT Box en la configuración del POS

1. En Odoo.sh ir a **Punto de Venta** > **Configuración** > **Ajustes**.
2. Seleccionar el POS que usará el IoT Box.
3. Sección **Dispositivos conectados** > **IoT Box**:
   - Activar el toggle.
   - Clic en **Agregar un IoT Box**.
   - Seleccionar el IoT Box recién conectado de la lista.
4. **Guardar**.

### 7.2 Detección automática de dispositivos

Una vez que el IoT Box está conectado a Odoo.sh, **todos los dispositivos
físicos conectados al PC son detectados automáticamente** por Odoo: impresoras
(USB y de red), lectores de código de barras, básculas, pantallas de cliente, etc.

En la misma pantalla de configuración del POS, sección **Dispositivos conectados**,
asignar cada dispositivo seleccionando desde la lista que Odoo presenta:

| Dispositivo | Acción |
|-------------|--------|
| Impresora de recibos | Seleccionar desde lista de dispositivos IoT |
| Lector de código de barras | Seleccionar desde lista de dispositivos IoT |
| Báscula | Seleccionar desde lista de dispositivos IoT |
| Pantalla de cliente | Seleccionar desde lista de dispositivos IoT |
| Terminal de pago | Configurar según proveedor |

> No se requiere configurar manualmente los dispositivos en el IoT Box.
> Si un dispositivo no aparece, verificar que está físicamente conectado
> al PC y reiniciar el servicio `OdooIoT`.

---

## 8. Certificado SSL: opciones y consideraciones

### 8.1 Certificado auto-firmado (desarrollo / red interna)

**Pros:** Instalación inmediata, sin costo.  
**Contras:** El navegador muestra advertencia de seguridad. Requiere que cada
terminal POS acepte la excepción de seguridad o importe el certificado raíz.

**Para instalar el certificado en los terminales POS (Chrome/Edge):**

1. Copiar el archivo `C:\odoo-iot\certs\server.crt` al terminal POS.
2. Hacer doble clic > **Instalar certificado**.
3. Seleccionar **Máquina local** > **Colocar en el siguiente almacén** > **Entidades de certificación raíz de confianza**.
4. Reiniciar el navegador.

**PowerShell — instalación masiva del certificado en terminales:**

```powershell
# Ejecutar en cada terminal POS como Administrador
Import-Certificate -FilePath "\\iot-box\compartido\server.crt" `
    -CertStoreLocation "Cert:\LocalMachine\Root"
```

### 8.2 Certificado de CA corporativa

Si tu empresa tiene una CA interna:

```powershell
.\install-odoo-iot.ps1 `
    -OdooUrl      "https://miempresa.odoo.com" `
    -OdooVersion  "17.0" `
    -CertFile     "\\servidor-ca\certs\iot-box.crt" `
    -KeyFile      "\\servidor-ca\certs\iot-box.key"
```

### 8.3 Renovar el certificado

```powershell
# Detener servicios
Stop-Service OdooIoTNginx

# Copiar nuevos archivos
Copy-Item "C:\nuevos-certs\server.crt" "C:\odoo-iot\certs\server.crt" -Force
Copy-Item "C:\nuevos-certs\server.key" "C:\odoo-iot\certs\server.key" -Force

# Reiniciar
Start-Service OdooIoTNginx
```

---

## 9. Mantenimiento y operación

### 9.1 Comandos de gestión de servicios

```powershell
# Estado de servicios
Get-Service OdooIoT, OdooIoTNginx

# Reiniciar todo
Restart-Service OdooIoT, OdooIoTNginx

# Detener
Stop-Service OdooIoT, OdooIoTNginx

# Iniciar
Start-Service OdooIoT, OdooIoTNginx

# Ver logs en tiempo real
Get-Content "C:\odoo-iot\logs\odoo-iot.log" -Tail 20 -Wait
```

### 9.2 Actualizar el token de emparejamiento

Si el token expira o se regenera en Odoo:

```powershell
# Editar configuración
$conf = "C:\odoo-iot\conf\odoo.conf"
(Get-Content $conf) -replace "^iot_token\s*=.*", "iot_token = NUEVO_TOKEN" | Set-Content $conf

# Reiniciar
Restart-Service OdooIoT
```

### 9.3 Actualizar Odoo IoT

```powershell
# Detener servicios
Stop-Service OdooIoT, OdooIoTNginx

# Actualizar fuente
Push-Location "C:\odoo-iot\odoo-src"
git pull origin 17.0
Pop-Location

# Actualizar dependencias Python
& "C:\odoo-iot\venv\Scripts\pip.exe" install -r "C:\odoo-iot\odoo-src\requirements.txt"

# Reiniciar
Start-Service OdooIoT, OdooIoTNginx
```

### 9.4 Estructura de directorios de instalación

```
C:\odoo-iot\
├── certs\
│   ├── server.crt          # Certificado SSL público
│   ├── server.key          # Clave privada SSL
│   └── thumbprint.txt      # Thumbprint del cert auto-firmado
├── conf\
│   └── odoo.conf           # Configuración principal de Odoo IoT
├── logs\
│   ├── odoo-iot.log        # Log del proceso Odoo
│   ├── nginx-access.log    # Peticiones HTTP/HTTPS
│   ├── nginx-error.log     # Errores de Nginx
│   └── install.log         # Log de instalación
├── nginx\                  # Nginx binario y configuración
├── nssm\
│   └── nssm.exe            # Gestor de servicios Windows
├── odoo-src\               # Código fuente de Odoo 17 (IoT)
├── venv\                   # Entorno virtual Python
└── tmp\                    # Archivos temporales de instalación
```

### 9.5 Configurar inicio automático tras reinicio

Los servicios se configuran como `Automatic` por defecto.
Verificar en **Servicios de Windows** (`services.msc`):
- `Odoo IoT Box` — Inicio: Automático
- `Odoo IoT Box (Nginx)` — Inicio: Automático

---

## 10. Solución de problemas

### Servicio no arranca

```powershell
# Ver error de inicio
Get-Content "C:\odoo-iot\logs\odoo-stderr.log" -Tail 30
Get-Content "C:\odoo-iot\logs\odoo-stdout.log" -Tail 30

# Probar manualmente (fuera del servicio)
& "C:\odoo-iot\venv\Scripts\python.exe" `
    "C:\odoo-iot\odoo-src\odoo-bin" `
    --config "C:\odoo-iot\conf\odoo.conf"
```

---

### Puerto 443 en uso

```powershell
# Identificar qué proceso usa el puerto
netstat -ano | findstr ":443"
# Luego:
Get-Process -Id <PID>
```

Si es IIS u otro servidor web, cambiar `-HttpsPort 8443` en el instalador.

---

### IoT Box no aparece en Odoo.sh

**Checklist:**

1. Verificar que el servicio `OdooIoT` está corriendo.
2. Verificar que la URL de Odoo en `odoo.conf` es correcta (sin barra final).
3. Verificar conectividad a internet desde el PC del IoT Box:
   ```powershell
   Test-NetConnection -ComputerName miempresa.odoo.com -Port 443
   ```
4. Verificar que el token no ha expirado en Odoo.sh.
5. Revisar el log en busca de errores de autenticación:
   ```powershell
   Select-String "error\|token\|auth" "C:\odoo-iot\logs\odoo-iot.log" | Select-Object -Last 20
   ```

---

### Un dispositivo no aparece en Odoo

1. Verificar que el dispositivo está físicamente conectado al PC del IoT Box.
2. Reiniciar el servicio:
   ```powershell
   Restart-Service OdooIoT
   ```
3. Esperar ~30 segundos y refrescar la lista en Odoo > IoT > Dispositivos.
4. Revisar logs:
   ```powershell
   Select-String "device\|driver\|usb" "C:\odoo-iot\logs\odoo-iot.log" | Select-Object -Last 20
   ```

---

### El POS no puede conectar al IoT Box

1. Verificar que el terminal POS puede alcanzar la IP del IoT Box:
   ```
   ping 192.168.1.XXX
   ```
2. Verificar que el puerto 443 está permitido en el firewall del PC IoT Box.
3. Verificar que el certificado SSL está importado o aceptado en el terminal.
4. Abrir `https://192.168.1.XXX` directamente desde el terminal POS — debe mostrar la homepage.

---

### Error de certificado SSL en el navegador

Para certificado auto-firmado, importar el certificado como CA raíz de confianza:

```powershell
# En el terminal POS, ejecutar como Admin
certutil -addstore "Root" "\\<IP-IoT-Box>\c$\odoo-iot\certs\server.crt"
# O usando PowerShell:
Import-Certificate -FilePath "\\<IP-IoT-Box>\share\server.crt" -CertStoreLocation "Cert:\LocalMachine\Root"
```

---

### Reinstalar desde cero

```powershell
# Detener y eliminar servicios
Stop-Service OdooIoT, OdooIoTNginx -Force
& "C:\odoo-iot\nssm\nssm.exe" remove OdooIoT confirm
& "C:\odoo-iot\nssm\nssm.exe" remove OdooIoTNginx confirm

# Eliminar directorio
Remove-Item "C:\odoo-iot" -Recurse -Force

# Volver a instalar
.\install-odoo-iot.ps1 -OdooUrl "https://miempresa.odoo.com" -SelfSigned -Force
```

---

## Referencias

- [Documentación oficial IoT Box — Odoo](https://www.odoo.com/documentation/17.0/applications/general/iot.html)
- [Configuración de POS con IoT Box](https://www.odoo.com/documentation/17.0/applications/sales/point_of_sale/configuration/pos_iot.html)
- [NSSM — Non-Sucking Service Manager](https://nssm.cc/)
