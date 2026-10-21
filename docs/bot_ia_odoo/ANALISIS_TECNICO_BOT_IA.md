# Bot de migración / corrección / desarrollo Odoo con IA (Claude Code)

**Tarea:** [#75227](https://www.progressa.group/odoo/project.task/75227) · [TI] Ingeniería – BACKLOG
**Tipo de documento:** Análisis técnico y propuesta de arquitectura (para validación)
**Versión:** 3 · 2026-10-01
**Estado:** Decisiones de diseño validadas – pendiente servidor y cuenta

### Cambios respecto a la versión 1

| Antes (v1) | Ahora |
|---|---|
| Cron en Odoo que encola tareas | **Acción automatizada** (`base.automation`) que se dispara al pasar la tarea a **«1 In Progress»** con los tags correspondientes |
| Cola de trabajos y límite de paralelismo | **Sin cola**: cada disparo abre **una sesión nueva de Claude Code**; sesiones ilimitadas (el límite real es el servidor, §10) |
| Workspace efímero por trabajo | **Un workspace (worker) por versión** — 17, 19, 20, master — igual que el entorno local `dev_env_odoo_pro-XX` |
| Etiqueta nueva `[CLAUDE]` + `MIGRACION/BUG/NUEVO` | **Un único tag nuevo de activación** `0. Team - Claude 🤖` + **tags que ya existen** (`1. Type - …`, `3. Versión - …`, tags de módulo, `5. Complejidad - …`) |
| Claude Agent SDK | **Claude Code CLI** en modo no interactivo con `--dangerously-skip-permissions` |
| — | **Preguntas por chatter**: Claude publica la pregunta como nota interna mencionando al responsable; la respuesta con `/claude …` reanuda la misma sesión |
| Migración por saltos | **Migración directa** origen → destino (17→19 salta 18) |
| Etapa `Specification` para análisis | **Todo en `1 In Progress`**: si falta análisis, Claude lo hace y pide `/claude aprobar` |
| Dumps anonimizados de clientes | **Sin acceso a datos de clientes** |

---

## 1. Resumen en simple

Un desarrollador mueve una tarea a **«1 In Progress»**. Si la tarea tiene el tag **`0. Team - Claude 🤖`**
y un tag de tipo (`1. Type - BUG 🐞`, `1. Type - MIG 🏃‍♂️💨`, …), Odoo avisa al **servidor del bot**,
que abre **una sesión de Claude Code** en el **workspace de la versión** indicada por el tag
`3. Versión - XX`. Claude trabaja igual que hoy en local: reproduce, corrige o migra, prueba, saca
capturas, genera el manual y abre el PR. Si tiene una duda, la escribe en el chatter de la tarea
(nota interna) mencionando a los usuarios asignados; cuando alguien responde con `/claude <respuesta>`,
la **misma sesión** continúa con ese contexto. Los usuarios asignados a la tarea no cambian: son
quienes le dan seguimiento.

Piezas:

| Pieza | Qué es | Dónde vive |
|---|---|---|
| **Acción automatizada + módulo ligero `project_ai_bot`** | Dispara el webhook al cambiar de etapa; detecta comandos `/claude` en el chatter; guarda el id de sesión y el estado. | Instancia Progressa (19e) |
| **Servidor del bot** | Recibe el webhook, abre/reanuda sesiones de Claude Code, una por tarea. Tiene un **workspace por versión** (17, 19, 20, master). | Servidor propio (VM dedicada) |
| **Paquete de contexto** | CLAUDE.md, skills, memorias y herramientas (manual-generator, i18n-generator, plantillas `setup_*`/`replicate_*`) — lo mismo que hoy está en `~/.claude` y `dev_env_odoo_pro-XX`. | Repo privado en GitHub, clonado en el servidor |

Reglas que no cambian: **el bot nunca hace merge, nunca toca producción y nunca corrige lo que no pudo reproducir.**

---

## 2. Validación de los requisitos

| # | Requisito | Validación | Resultado |
|---|---|---|---|
| 1 | Capacidad del servidor | Medido en el entorno local: Odoo en reposo 160–440 MB por contenedor, Postgres ~340 MB, cada proceso de Claude Code ~360 MB. En carga (tests + navegador) una sesión activa llega a ~3 GB. | **Recomendado: 16 vCPU, 64 GB RAM, 500 GB NVMe** para ~12 sesiones activas a la vez. Fórmula y escalones en §10. |
| 2 | Un worker por versión | Viable y es el mismo modelo del entorno local. **Ajuste necesario:** si dos sesiones trabajan en la misma versión a la vez, no pueden compartir el mismo checkout de git (una cambiaría la rama de la otra). | Un workspace + contenedor Odoo por versión (hoy 17, 19, 20, master; se agregan más versiones mayores o menores por configuración, §6.5); **cada sesión usa un `git worktree` propio** y su propia base de datos (§6). |
| 3 | Tareas ilimitadas, una sesión nueva de Claude Code por tarea | Viable: no hay cola; cada disparo lanza un proceso `claude -p` independiente. Límites reales: RAM/CPU del servidor, límites de tasa de la cuenta de Anthropic y costo. | Sin cola. Tope de sesiones simultáneas **configurable y apagado**; alerta de memoria (≥ 85 %) (§6.4). |
| 4 | Acción automatizada en lugar de cron | Odoo 19 trae nativo `base.automation` con trigger **«Stage is set to»** (`on_stage_set`) y acción **«Send Webhook Notification»**. `base_automation` ya está instalado en la instancia. | Viable **sin código** para el disparo. Limitaciones del webhook nativo (1 s de timeout, sin reintento, sin cabeceras de autenticación) y cómo se cubren en §4. |
| 5 | Usar los tags existentes | Revisados los 293 tags de la instancia. Existen tipo, versión, módulo, complejidad y área. **No existe ningún tag que diga "esto lo hace la IA"**: si sólo se usan tags de tipo, *toda* tarea BUG que un desarrollador pase a In Progress dispararía el bot. | Se usan los existentes (§5) + **un único tag nuevo de activación `0. Team - Claude 🤖`**, siguiendo la convención `0. Team - …`. Los usuarios asignados se mantienen. |
| 6 | `--dangerously-skip-permissions` y que igual se detiene a preguntar | El flag elimina los prompts de permisos, pero **no** evita que el modelo decida preguntar o que termine su turno con una duda. En modo no interactivo (`-p`) no hay nadie para contestar. | Sesión en `-p` + `--permission-prompts none` (nada se queda esperando) + salida JSON obligatoria con `status: needs_input` para las dudas (§7). |
| 7 | Pregunta por chatter + respuesta que reanuda | Las automatizaciones nativas de mensajes (`on_message_received/sent`) **ignoran las notas internas** (código de `base_automation`: si el mensaje es interno, sale sin disparar). | Hace falta un **hook pequeño** en el módulo `project_ai_bot` que detecte el comando `/claude …` en notas internas y llame al webhook (§8). |
| 8 | Etapas | Proyecto `[TI] Ingeniería - BACKLOG`: `1 Backlog` · `Specification` · `To Do` · `1 In Progress` · `Review` · `Testing` · `1 Delivered` · `Cancelled`. | Todo ocurre en `1 In Progress` (incluido el análisis y su aprobación); el bot deja la tarea en `Review` al abrir el PR. |

Nota: la tarea #75227 está ahora en `To Do` (alguien la movió desde `1 In Progress`).

---

## 3. Arquitectura general

```
┌──────────────────────────── Instancia Progressa (Odoo 19e) ─────────────────────────────┐
│                                                                                           │
│  project.task ── etapa → «1 In Progress»                                                  │
│      │  + tag «0. Team - Claude 🤖» + tag «1. Type - …»                                   │
│      ▼                                                                                    │
│  base.automation  (on_stage_set)  ──►  Send Webhook Notification  ──────────────┐         │
│                                                                                 │         │
│  Nota interna «/claude …»  ──►  hook project_ai_bot  ──►  webhook  ─────────────┤         │
│                                                                                 │         │
│  ◄── notas internas (@asignados), PR, adjuntos, etapa Review ──── json2 API ──┐ │         │
└────────────────────────────────────────────────────────────────────────────────┼─┼────────┘
                                                                                 │ │ HTTPS
┌────────────────────────────── Servidor del bot ────────────────────────────────┼─▼────────┐
│  bot-gateway (Python, HTTP)                                                    │          │
│   · valida secreto · lee la tarea por json2 · elige workspace por versión ─────┘          │
│   · nueva sesión  → claude -p … --session-id <uuid>                                       │
│   · respuesta     → claude -p … --resume <uuid>                                           │
│                                                                                           │
│  /srv/aibot/                                                                              │
│  ├── v17/   odoo · enterprise · odoo-pro · contenedor bot_v17   worktrees/<tarea>/ …      │
│  ├── v19/   odoo · enterprise · odoo-pro · contenedor bot_v19   worktrees/<tarea>/ …      │
│  ├── v20/   …                                                                              │
│  ├── master/…                                                                              │
│  ├── upgrade-util/   context-pack/   postgres (compartido)                                │
│                                                                                           │
│  Sesión Claude Code (una por tarea, ilimitadas en paralelo)                               │
│   cwd = vXX/worktrees/<tarea>   DB = bot_<tarea>   puerto http propio                     │
└───────────────────────────────────────────┬───────────────────────────────────────────────┘
                                            │ push rama / PR / reviewers
                                     ┌──────▼──────┐
                                     │   GitHub    │  CI (pre-commit, Test Modules)
                                     └─────────────┘
```

Cambio de modelo respecto a v1: ahora **Odoo empuja** (webhook) en lugar de que el servidor consulte.
Consecuencia: el servidor del bot necesita una **URL HTTPS accesible desde Odoo** (dominio propio +
certificado, o un túnel tipo Cloudflare Tunnel si el servidor está detrás de NAT).

---

## 4. Disparo: acción automatizada

### 4.1 Regla «Claude – iniciar sesión» (configurable desde la interfaz, sin código)

| Campo | Valor |
|---|---|
| Modelo | Tarea (`project.task`) |
| Disparador | **Stage is set to** → `1 In Progress` |
| Aplicar en (filtro) | `tag_ids` contiene **`0. Team - Claude 🤖`** **y** `tag_ids` contiene alguno de: `1. Type - BUG 🐞`, `1. Type - MIG 🏃‍♂️💨`, `1. Type - NEW 🌟`, `1. Type - IMP ✅`, `1. Type - REF ⚠️`, `1. Type - QA 👮🏻‍♂️` |
| Acción | **Send Webhook Notification** |
| URL | `https://aibot.<dominio>/hooks/<secreto>/task` |
| Campos enviados | `id`, `name`, `project_id`, `stage_id`, `tag_ids`, `user_ids` |

No hay regla para `Specification`: análisis, aprobación y desarrollo ocurren en `1 In Progress` (§9.3).

### 4.2 Limitaciones del webhook nativo y cómo se cubren

| Limitación (verificada en `ir_actions.py` de Odoo 19) | Cobertura |
|---|---|
| Se envía después del commit con **timeout de 1 s** y estrategia "enviar y olvidar" | El gateway responde `202` de inmediato y lanza la sesión en segundo plano |
| **Sin reintento**: si el servidor está caído, el aviso se pierde | Al arrancar, el gateway consulta por json2 las tareas en `1 In Progress` con el tag `0. Team - Claude 🤖` sin sesión registrada y las lanza (reconciliación, no es un cron de Odoo) |
| **Sin cabeceras de autenticación** | Secreto largo en la URL + HTTPS + lista de IPs permitidas (la IP de la instancia) |
| Sólo envía los campos elegidos | El gateway lee descripción, chatter y adjuntos por json2 con el usuario técnico Claude Bot |
| Si la tarea sale y vuelve a `1 In Progress` se dispara otra vez | Si la tarea ya tiene sesión, el gateway la **reanuda** (`--resume`) en vez de abrir otra |

---

## 5. Tags existentes → comportamiento

Tags reales de la instancia, sin crear ninguno nuevo:

| Grupo | Tag | Uso en el bot |
|---|---|---|
| **Activación** | `0. Team - Claude 🤖` *(único tag nuevo)* | Sin este tag el bot no toma la tarea, aunque tenga tipo y esté en `1 In Progress` |
| **Tipo** | `1. Type - BUG 🐞` | Corrección con puerta de reproducción (§9.2) |
| | `1. Type - MIG 🏃‍♂️💨` (o `Migración`) | Migración directa origen → destino (§9.1) |
| | `1. Type - NEW 🌟` | Desarrollo nuevo: exige análisis aprobado (§9.3) |
| | `1. Type - IMP ✅` | Mejora: mismo flujo que NEW |
| | `1. Type - REF ⚠️` | Refactor: mismo flujo que NEW |
| | `1. Type - QA 👮🏻‍♂️` | Prueba funcional en navegador + manual con capturas, sin tocar código (§9.4) |
| **Versión** | `3. Versión - 17` / `19` / `20` … | Workspace donde corre la sesión. En MIG: con dos tags, el menor es el **origen** y el mayor el **destino**; con uno solo, es el destino y el origen se detecta por la rama donde vive hoy el módulo |
| | `3. Versión - FWP` | Tras corregir en la versión indicada (p. ej. 17.0), **evaluar** el fix en las demás versiones configuradas donde exista el módulo y llevarlo sólo donde haga falta (§9.2) |
| **Módulo** | `l10n_do_accounting`, `payment_azul`, … (≈200 tags con nombre técnico) | Módulo(s) objetivo. Si no hay, Claude lo deduce de la descripción y pregunta por chatter si hay duda |
| **Complejidad** | `5. Complejidad - 👶🏼` / `🥶` / `🔥` | Nivel de esfuerzo de Claude: `medium` / `high` / `xhigh` |
| **Área** | `4. Base - Account`, `4. Base - Payroll`, … | Contexto adicional en el prompt (qué skills y memorias cargar) |
| **Otros** | `Documentación` | Fuerza generar/actualizar el manual aunque el tipo no lo exija |
| **Usuarios asignados** | `user_ids` (sin cambios) | Son quienes dan seguimiento: reciben la mención cuando Claude pregunta o termina |

Al terminar una migración se mantiene la práctica actual: se añade `3. Versión - <destino>` y se quita el de origen.

---

## 6. Workspaces por versión y sesiones ilimitadas

### 6.1 Estructura (igual que local, una carpeta por versión)

```
/srv/aibot/
├── v17/                     # = dev_env_odoo_pro-17
│   ├── odoo/  enterprise/  odoo-pro/ (con submódulos OCA)
│   ├── docker-compose.yml   # contenedor bot_v17 (worker de la versión)
│   └── worktrees/
│       ├── 75301-mig-payment_azul/     # git worktree de odoo-pro, rama de la tarea
│       └── 75310-bug-l10n_do_hr/
├── v19/   (ídem)            # = dev_env_odoo_pro-19
├── v20/   (ídem)            # = dev_env_odoo_pro-20
├── master/(ídem)
├── upgrade-util/
├── context-pack/            # CLAUDE.md, skills, memorias, tools
└── postgres/                # un solo servidor Postgres para todas las versiones
```

### 6.2 Qué comparte y qué no cada sesión

| Recurso | Compartido por versión | Propio de la sesión |
|---|---|---|
| Core `odoo/` y `enterprise/` | ✔ (sólo lectura) | |
| Contenedor Odoo de la versión (imagen, dependencias Python) | ✔ | |
| Submódulos OCA | ✔ (sólo lectura, vía `addons_path`) | |
| Código de `odoo-pro` | | ✔ `git worktree` en su propia rama |
| Base de datos | | ✔ `bot_<tarea>` (+ `bot_<tarea>_origen` en migraciones) |
| Proceso Odoo para pruebas en navegador | | ✔ `odoo-bin` dentro del contenedor de la versión, con su `--addons-path` y un puerto del rango 9100–9999 |
| Sesión Claude Code (historial) | | ✔ `--session-id` = uuid guardado en la tarea |

**Por qué el worktree:** en local trabajas una tarea a la vez por versión. El bot puede tener 5 tareas
de v19 al mismo tiempo; con un solo checkout, cada `git checkout` de una sesión rompería a las otras.
El worktree comparte el historial de git (no duplica el repo) y cuesta ~300–400 MB de disco.

### 6.3 Ciclo de vida

1. Disparo → crear worktree y rama (`{versión}-{tipo}-{módulo}-bot`), crear DB, lanzar `claude`.
2. Mientras espera una respuesta por chatter, el worktree y la DB **se conservan** (la reanudación necesita el mismo directorio).
3. Al cerrarse la tarea (`1 Delivered` / `Cancelled`) o al hacer merge del PR → se borran worktree, DB y procesos; los logs se guardan N días.

### 6.4 "Ilimitado" en la práctica

No hay cola: cada disparo abre su sesión de inmediato. Lo que pone el techo:

| Límite | Efecto si se pasa | Recomendación |
|---|---|---|
| RAM del servidor | El sistema empieza a matar procesos (OOM) — fallan sesiones al azar | Dimensionar al pico esperado (§10) + alerta al 85 % |
| Límites de tasa de la cuenta Anthropic (tokens/minuto según el nivel de la organización) | Respuestas `429`; Claude Code reintenta y las sesiones se vuelven lentas | Subir el nivel de la cuenta según uso |
| Conexiones a Postgres | Errores de conexión en Odoo | `max_connections` ≥ 300 y `db_maxconn` bajo por proceso |
| Costo | — | Reporte mensual; tope opcional por sesión con `--max-budget-usd` (apagado por defecto) |

Parámetro `max_concurrent_sessions` en la configuración: **apagado** (sin tope) por ahora; si se activa, las sesiones que excedan el tope esperan a que se libere un cupo.

### 6.5 Agregar versiones

Las versiones no están fijas en el código. Cada versión es una entrada de configuración:

| Campo | Ejemplo |
|---|---|
| Clave | `19.0`, `20.0`, `saas-19.2`, `master` |
| Tag de la instancia | `3. Versión - 19` |
| Rama base de `odoo-pro` / `odoo` / `enterprise` | `19.0` |
| Carpeta de workspace | `/srv/aibot/v19` |
| Imagen / Dockerfile | `images/v19` |
| Activa | sí / no |

Agregar una versión (mayor o menor) = clonar sus repos en una carpeta nueva, construir su imagen,
registrar la entrada y, si no existe, crear el tag `3. Versión - XX`. El checklist de migración de esa
versión se agrega al skill `odoo-migrate`.

---

## 7. La sesión de Claude Code

### 7.1 Cómo se lanza

```bash
# nueva sesión
claude -p "$PROMPT_DE_LA_TAREA" \
  --session-id "$UUID" \
  --dangerously-skip-permissions \
  --permission-prompts none \
  --disallowedTools AskUserQuestion \
  --output-format stream-json --verbose \
  --json-schema "$RESULT_SCHEMA" \
  --append-system-prompt-file /srv/aibot/context-pack/prompts/bot.md \
  --effort "$EFFORT" \
  --model claude-opus-5-5

# respuesta desde el chatter
claude -p "$RESPUESTA_CON_CONTEXTO" --resume "$UUID" \
  --dangerously-skip-permissions --permission-prompts none \
  --disallowedTools AskUserQuestion \
  --output-format stream-json --verbose --json-schema "$RESULT_SCHEMA"
```

`cwd` = el worktree de la tarea. CLAUDE.md, skills y memorias se cargan desde el paquete de contexto
(instalado en `~/.claude` del usuario `aibot`), igual que en local.

### 7.2 Por qué Claude "se detiene a preguntar" aunque se salten los permisos

| Causa | Qué pasa en interactivo | Cómo se resuelve en el bot |
|---|---|---|
| Prompt de permisos | Se salta con `--dangerously-skip-permissions` | Igual + `--permission-prompts none`: cualquier cosa que aún pidiera permiso se **deniega sola** y Claude sigue por otro camino, nunca se queda colgado |
| Claude usa la herramienta de preguntas (`AskUserQuestion`) | Muestra opciones y espera | Herramienta deshabilitada (`--disallowedTools`) |
| Claude termina su turno con una duda en texto | Espera a que escribas | En `-p` el proceso **termina**; la salida JSON obligatoria trae `status: "needs_input"` + pregunta → se publica en el chatter (§8) |
| Proceso colgado (comando que no termina, servidor Odoo en primer plano) | Lo cortas a mano | El gateway mata la sesión si no hay actividad en N minutos y deja nota con el último log |

### 7.3 Salida estructurada (`--json-schema`)

```json
{
  "status": "done | needs_input | needs_approval | blocked | failed",
  "summary": "qué se hizo",
  "question": "sólo si needs_input / needs_approval",
  "options": ["opción A", "opción B"],
  "pr_urls": ["https://github.com/indexa-git/odoo-pro/pull/…"],
  "artifacts": ["ruta/al/manual.pdf", "replicate_…sh"],
  "blocked_reason": "sólo si blocked"
}
```

El gateway actúa según `status`: publica nota, adjunta archivos, mueve la tarea a `Review` (si hay PR) o la deja donde está.

---

## 8. Preguntas por chatter y reanudación

### 8.1 Flujo

```
Claude termina con status = needs_input
        │
        ▼
Gateway publica NOTA INTERNA en la tarea:
   "🤖 Claude necesita una respuesta para continuar:
    <pregunta>  (A) …  (B) …
    Responde con:  /claude <tu respuesta>"
   mencionando a los usuarios asignados a la tarea (user_ids)
   → les llega la notificación aunque sea nota interna
        │
        ▼
Cualquier usuario escribe nota interna:  /claude B, y usa el diario de ventas
        │
        ▼
Hook de project_ai_bot detecta "/claude" → webhook al gateway
   { task_id, message_id, author, body }
        │
        ▼
Gateway: claude -p "Respuesta de <autor>: B, y usa el diario de ventas" --resume <uuid>
        │
        ▼
La sesión continúa con TODO su contexto anterior
```

### 8.2 Comandos en el chatter

| Comando (nota interna) | Efecto |
|---|---|
| `/claude <texto>` | Responde la pregunta pendiente o da una instrucción adicional; reanuda la sesión |
| `/claude aprobar` | Aprueba el análisis técnico → Claude pasa a desarrollar |
| `/claude rechazar <motivo>` | Claude rehace el análisis con el comentario |
| `/claude detener` | Mata la sesión en curso (conserva worktree y rama) |
| `/claude estado` | Claude publica en qué va (último paso, PR, costo acumulado) |

Cualquier usuario que escriba el comando en una **nota interna** puede responder o aprobar. Los mensajes
de clientes/portal no son notas internas, así que no disparan nada.

### 8.3 Por qué hace falta código (y no sólo una automatización)

En Odoo 19, `base_automation` sólo dispara con mensajes **no internos** (si el mensaje es nota interna
o tiene subtipo interno, la automatización ni se evalúa). Como el chatter del bot es **siempre nota
interna**, se necesita un override pequeño de `project.task.message_post` en `project_ai_bot` que:
1. detecte notas de usuarios internos cuyo texto empieza por `/claude`,
2. envíe el webhook después del commit (mismo patrón que el webhook nativo),
3. marque el mensaje como procesado (evita disparos dobles).

---

## 9. Flujos por tipo

### 9.1 MIGRACIÓN (`1. Type - MIG`) — siempre directa

**La migración va directo de la versión origen a la destino.** 17→19 salta 18: una rama, un PR, sin
instalar versiones intermedias. Los cambios de API de las versiones saltadas se aplican **acumulados**
(17→19 = checklist 18 + checklist 19 del skill `odoo-migrate`) y se verifica sólo contra el core destino.

Workspaces: trabaja en el de **destino**; lee el módulo del de **origen** y usa el contenedor de origen
para crear la DB de origen con datos semilla y probar la actualización.

1. Verificar dependencias en la versión destino (OCA no portado → `blocked` con la lista).
2. Rama `{destino}-mig-{módulo}-bot`, traer el módulo (forward-port con historial cuando aplique).
3. Aplicar checklists acumulados; scripts de `migrations/` y `upgrade-util` para el salto completo.
4. Instalar en DB limpia + actualizar desde la DB de origen → sin errores.
5. Tests del módulo; `.po` con `generate-po.sh` (sólo traducir `msgstr`).
6. Manual + capturas (§9.5). Tags: `+3. Versión - <destino>`, `−3. Versión - <origen>`.

### 9.2 BUG (`1. Type - BUG`) — con puerta de reproducción

1. Leer tarea, chatter y adjuntos. ¿Faltan datos (pasos, versión, módulo)? → `needs_input` por chatter.
2. Crear DB + `replicate_<bug>.sh`. **¿Falla igual que en el reporte?** No → `blocked: no reproducible` con diagnóstico.
3. Fix mínimo + test automatizado. `replicate` pasa, tests pasan, el flujo anterior no se rompe.
4. Con `3. Versión - FWP` (forward-port), por cada otra versión configurada donde exista el módulo:
   - correr el `replicate_<bug>.sh` (adaptado) en el workspace de esa versión;
   - **si el bug se reproduce** → aplicar el fix adaptado + test, un PR por versión;
   - **si no se reproduce** (el código ya es distinto o ya estaba corregido) → no se toca;
   - nota interna final con la tabla versión → *corregido (PR)* / *no aplica (motivo)*.

Reproducible al 100 % = mismo error o mismo resultado incorrecto con un script re-ejecutable sobre
datos de demo/semilla. **El bot no tiene acceso a datos de clientes**: si el bug depende de datos reales,
Claude pide por chatter (`needs_input`) los pasos o la configuración para recrearlo con datos de prueba;
si aun así no se reproduce, queda `blocked` con el diagnóstico.

### 9.3 NEW / IMP / REF — análisis antes de desarrollar

```
¿La tarea tiene análisis aprobado? (nota "/claude aprobar" posterior al análisis)
   │no                                          │sí
   ▼                                            ▼
Claude genera el análisis técnico,          Claude desarrolla según el análisis:
lo adjunta y publica nota:                  tests por criterio de aceptación,
"responde /claude aprobar o                 setup_vXX_<módulo>.sh, manual,
 /claude rechazar <motivo>"                 PR → Review
status = needs_approval
```

Todo ocurre con la tarea en `1 In Progress`. Claude decide si la descripción y los adjuntos ya son un
análisis suficiente (modelos, vistas, reglas, criterios de aceptación); si no, lo genera y espera
`/claude aprobar`. Si durante el desarrollo aparece algo no cubierto, vuelve a `needs_approval` con un anexo.

### 9.4 QA (`1. Type - QA`)

Recorre los flujos del módulo en navegador con `manual-generator` (Playwright), valida que cada paso
aparezca en pantalla, toma capturas y adjunta el manual PDF. No toca código; si encuentra un fallo,
lo reporta en el chatter con captura y propone crear una tarea BUG.

### 9.5 Cierre común (tipos con código)

1. Revisión de código (skill de revisión) + `pre-commit`.
2. Push, PR en inglés con evidencia (tests, scripts, capturas) y enlace a la tarea.
3. Espera CI; si falla, corrige (máx. N intentos) o pasa a `blocked` con el log.
4. Pide revisores; PR en la descripción + nota interna (`odoo-tasks pr`); tarea → `Review`.
5. Manual: `manual-generator` levanta la DB con `setup_vXX_<módulo>.sh`, recorre los flujos, falla si un paso no aparece y genera MD/HTML/PDF adjunto a la tarea.
6. No se registran horas de timesheet automáticamente.

---

## 10. Capacidad del servidor

### 10.1 Mediciones (entorno local, hoy)

| Componente | Memoria |
|---|---|
| Contenedor Odoo en reposo (v17 / v20) | 436 MB / 162 MB |
| Postgres compartido en reposo | 341 MB |
| Proceso Claude Code | ~360 MB |
| Checkout por versión (odoo + enterprise + odoo-pro) | v19 ≈ 2,2 GB · v17 ≈ 1,9 GB |

### 10.2 Consumo estimado por sesión activa (pico)

| Elemento | RAM | CPU |
|---|---|---|
| Claude Code | 0,4–0,5 GB | bajo (espera a la API la mayor parte del tiempo) |
| `odoo-bin` con tests o `-u` del módulo | 1–1,5 GB | 1 vCPU sostenido |
| Chromium (Playwright, manual/QA) | 0,5–1 GB | 0,5–1 vCPU |
| Conexiones/consultas en Postgres | 0,2–0,5 GB | variable |
| **Total pico por sesión** | **~3 GB** | **~1,5 vCPU** |

Una sesión que espera respuesta en el chatter casi no consume (sólo su DB en disco).

### 10.3 Fórmula y escalones

- **RAM** ≈ 10 GB base (SO, Docker, Postgres con caché, 4 contenedores de versión) + **3 GB × sesiones activas a la vez**
- **vCPU** ≈ 2 + **1,5 × sesiones activas**
- **Disco** ≈ 4 versiones × ~3 GB fuentes + ~10 GB imágenes Docker + **~1,5 GB × sesión abierta** (worktree + DB + filestore) + 50 GB logs/capturas

| Escalón | Sesiones activas simultáneas | vCPU | RAM | Disco NVMe |
|---|---|---|---|---|
| Inicial | hasta 6 | 8 | 32 GB | 250 GB |
| **Recomendado** | **hasta 12** | **16** | **64 GB** | **500 GB** |
| Alto | hasta 25 | 32 | 128 GB | 1 TB |

Recomendaciones adicionales: Linux x86_64 (Chromium/Playwright sin las particularidades de arm64),
Postgres con `max_connections` ≥ 300, swap de 8–16 GB como colchón, y medir el uso real las primeras
dos semanas antes de subir de escalón.

---

## 11. Módulo Odoo `project_ai_bot` (ligero)

Con la acción automatizada nativa, el módulo queda pequeño:

| Elemento | Para qué |
|---|---|
| Campos en `project.task`: `ai_session_id`, `ai_state` (`running` / `needs_input` / `needs_approval` / `blocked` / `done` / `failed`), `ai_workspace` (versión), `ai_cost_usd` | Saber si la tarea ya tiene sesión (reanudar vs. nueva) y mostrar el estado |
| Override de `message_post` para comandos `/claude` | §8.3 |
| Datos: tag `0. Team - Claude 🤖`, usuario técnico **Claude Bot** (autor de las notas y dueño de la API key; no se asigna a tareas), la `base.automation` (§4.1) | Instalación reproducible |
| Parámetros: URL del gateway, secreto, `max_concurrent_sessions` (apagado), versiones configuradas (§6.5) | Configuración |
| Vista: pestaña "Claude" en la tarea (estado, sesión, costo, último resumen) + filtro "Tareas del bot" | Seguimiento |

El resto (lanzar sesiones, workspaces, GitHub) vive en el servidor, no en Odoo.

---

## 12. Paquete de contexto

Repo privado `claude-odoo-context` con `CLAUDE.md`, `skills/` (migrar, corregir, desarrollar, analizar,
manual, i18n, revisión, `odoo-tasks`), `memory/` (gotchas por versión), `tools/` (manual-generator,
i18n-generator, plantillas `setup_*`/`replicate_*`) y `prompts/` (plantilla por tipo de tarea + `bot.md`
con las reglas de salida JSON). El mismo paquete sirve en local y en el servidor: lo que un
desarrollador aprende, el bot lo usa en la siguiente sesión.

---

## 13. Seguridad (importante con `--dangerously-skip-permissions`)

El propio Claude Code advierte que este flag es "recomendado sólo para sandboxes sin acceso a internet".
El bot sí necesita internet (API de Anthropic, GitHub, Odoo), así que **el aislamiento lo da el
servidor**, no Claude:

| Medida | Por qué |
|---|---|
| VM dedicada sólo para el bot, sin nada más instalado | Con el flag, Claude puede ejecutar cualquier comando que el usuario `aibot` pueda ejecutar |
| Usuario no-root `aibot` | Limita daños; no correr Claude Code con este flag como root |
| Tener en cuenta que el grupo `docker` equivale a root en el host | Otra razón para que la VM sea exclusiva |
| Sin acceso a datos de clientes: ni credenciales, ni red hacia sus instancias, ni dumps | Un error o una instrucción maliciosa no puede llegar a datos reales |
| Firewall de salida: sólo Anthropic, GitHub, la instancia Progressa, PyPI/npm | Reduce fuga de datos |
| GitHub App/token del bot con push sólo a ramas `*-bot`; ramas base protegidas | Nunca merge ni push a `17.0`/`19.0` |
| Usuario Claude Bot en Odoo con permisos mínimos (leer tareas, notas internas, adjuntos, mover etapa) | La API key del bot no sirve para otra cosa |
| Texto de tareas/chatter tratado como dato, no como órdenes | Las tareas las escriben personas, a veces clientes; el prompt del sistema lo delimita |
| Cuenta de Anthropic: en pruebas, la cuenta actual de Luis; la cuenta definitiva (organización, presupuesto) se evaluará después | Al pasar a operación, separar el consumo del bot del uso de los desarrolladores |

---

## 14. Costos estimados (orden de magnitud)

Referencia `claude-opus-5-5`: USD 4 / MTok entrada, USD 20 / MTok salida, ~USD 0,20 / MTok en lecturas de
caché (la mayor parte del contexto de una sesión larga se lee de caché).

| Tipo | Por tarea |
|---|---|
| Análisis técnico | USD 1 – 5 |
| QA + manual | USD 3 – 10 |
| Bug reproducible sencillo | USD 3 – 15 |
| Migración de módulo mediano (directa, con manual) | USD 10 – 40 |
| Desarrollo nuevo mediano | USD 15 – 60 |

Cada sesión reporta su costo real (`total_cost_usd` en la salida de Claude Code) y se guarda en la tarea.
Servidor: costo fijo mensual según el escalón de §10.

---

## 15. Riesgos

| Riesgo | Mitigación |
|---|---|
| Muchas sesiones a la vez agotan la RAM | Dimensionar al pico, alerta al 85 %, tope opcional |
| Bug que sólo ocurre con datos de un cliente | `needs_input` pidiendo pasos para recrearlo con datos de prueba; si no, `blocked` |
| Webhook perdido (servidor caído) | Reconciliación al arrancar el gateway (§4.2) |
| Disparos accidentales en tareas de humanos | Activación sólo con el tag `0. Team - Claude 🤖`, no por tag de tipo |
| Pregunta sin respuesta durante días | Worktree y DB conservados; recordatorio en chatter a los N días; se limpia al cerrar la tarea |
| Fix que parece funcionar sin serlo | Puerta de reproducción + test + revisión humana |
| Dependencias OCA no portadas | `blocked` temprano con la lista |
| `--dangerously-skip-permissions` | §13 |
| Contexto desactualizado | Paquete de contexto versionado y revisado por PR |

---

## 16. Plan por fases

| Fase | Alcance | Esfuerzo aprox. |
|---|---|---|
| **0. Servidor + paquete de contexto** | VM, workspaces v17/v19/v20/master, Postgres, usuario `aibot`, extraer CLAUDE.md/skills/memorias/tools a un repo | 4–5 días |
| **1. Disparo + BUG + chatter** | `project_ai_bot` (campos, hook `/claude`, tag de activación, usuario técnico, automatización), gateway con nueva sesión / reanudar, flujo BUG en v19 | 2–3 semanas |
| **2. MIG directa** | Checklists acumulados por versión, workspace origen + destino, upgrade-util, `.po`, tags de versión | 2 semanas |
| **3. NEW/IMP/REF + QA** | Análisis → `/claude aprobar` → desarrollo; QA con manual-generator | 2 semanas |
| **4. Operación** | Métricas de costo/RAM, limpieza automática, FWP, nuevas versiones | continuo |


---

## 17. Pendientes

| Tema | Estado |
|---|---|
| Servidor (nube o propio) y dominio HTTPS para el webhook | Se definirá luego; dimensionamiento de referencia en §10 |
| Cuenta de Anthropic definitiva y presupuesto | Se evaluará luego; pruebas con la cuenta actual de Luis |
