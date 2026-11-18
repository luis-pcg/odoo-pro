# Bot de migración / corrección / desarrollo Odoo con IA (Claude Code)

**Tarea:** [#75227](https://www.progressa.group/odoo/project.task/75227) · [TI] Ingeniería – BACKLOG  
**Repositorio:** `indexa-git/bot_ia_odoo` (privado)  
**Tipo de documento:** Análisis técnico y propuesta de arquitectura  
**Versión:** 4 · 2026-10-26  
**Estado:** Prototipo validado (gateway + nube de Claude, §18) – pendiente GitHub, token de routine y contenedor  

### Cambios respecto a la versión 3 (daily 2026-10-26)

| v3 | v4 |
|---|---|
| VM dedicada de 16 vCPU / 64 GB / 500 GB | **Prototipo en un contenedor ya creado** (4 vCPU, ~12 GB RAM, 40 GB disco) para 2–3 sesiones a la vez; se escala sólo con mediciones reales (§10) |
| Todas las sesiones corren en el servidor propio | **Las sesiones corren en la nube de Claude** (Claude Code cloud sessions); el servidor sólo **orquesta** (gateway). Validado que se maneja desde consola (§3, §2) |
| Sin flujo de forward-port | **Nuevo flujo de forward-port**: el bot de forward-port de Eric abre el PR a la siguiente versión **al hacer merge**; un revisor IA valida que el cambio aplica en la versión destino (§9.6) |
| Revisión secundaria con Claude | **Evaluar GitHub Copilot como revisor secundario** (ya pagado, lee `CLAUDE.md` y documentación del repo); Claude queda como alternativa (§9.6.3) |
| Servidor "a definir" | **Desplegar como servicio**: repo con `requirements`, `bin/`, README y guía de despliegue (variables de entorno, instalación); Claude puede instalarlo por SSH; firewall/puertos los abre infraestructura (§12) |

---

## 1. Resumen en simple

Un desarrollador mueve una tarea a **«1 In Progress»**. Si la tarea tiene el tag **`0. Team - Claude 🤖`**
y un tag de tipo (`1. Type - BUG 🐞`, `1. Type - MIG 🏃‍♂️💨`, …), Odoo avisa al **gateway del bot**, que
abre **una sesión de Claude Code en la nube de Claude** con los repos de la versión indicada por el tag
`3. Versión - XX`. Claude trabaja igual que hoy en local: reproduce, corrige o migra, prueba, saca
capturas, genera el manual y abre el PR. Si tiene una duda, la escribe en el chatter de la tarea
(nota interna) mencionando a los usuarios asignados; cuando alguien responde con `/claude <respuesta>`,
la **misma sesión** continúa con ese contexto.

Aparte, para los cambios que ya existen: cuando un PR de una versión se **mergea**, el **bot de
forward-port** abre el PR equivalente en la siguiente versión y un **revisor IA** (Copilot o Claude)
comprueba que el cambio aplica bien en esa versión antes de que lo revise una persona.

Piezas:

| Pieza | Qué es | Dónde vive |
|---|---|---|
| **Acción automatizada + módulo ligero `project_ai_bot`** | Dispara el webhook al cambiar de etapa; detecta comandos `/claude` en el chatter; guarda el id de sesión y el estado | Instancia Progressa (19e) |
| **Gateway** (`bot_ia_odoo`) | Servicio pequeño (Python) que recibe el webhook y abre/reanuda la sesión en la nube | Contenedor de pruebas (4 vCPU / 12 GB / 40 GB) |
| **Sesión de Claude Code** | Una por tarea; repos de la versión, Postgres y Docker incluidos | Nube de Claude (por defecto) o el propio contenedor (alternativa, §3.3) |
| **Bot de forward-port + revisor IA** | Abre el PR a la siguiente versión al hacer merge y pide revisión IA | GitHub (Actions) |
| **Paquete de contexto** | CLAUDE.md, skills, memorias y herramientas (manual-generator, i18n-generator, plantillas `setup_*`/`replicate_*`) | Carpeta `context-pack/` del repo del bot |

Reglas que no cambian: **el bot nunca hace merge, nunca toca producción y nunca corrige lo que no pudo reproducir.**

---

## 2. Validación de los requisitos

### 2.1 Requisitos originales (v3)

| # | Requisito | Resultado |
|---|---|---|
| 1 | Capacidad del servidor | Con sesiones en la nube el contenedor sólo corre el gateway (< 1 GB). Si se ejecuta localmente, 12 GB alcanzan para **2–3 sesiones** activas de una versión (§10) |
| 2 | Un worker por versión | Se mantiene como **entorno** por versión (en la nube: un *cloud environment* por versión; en local: una carpeta por versión con `git worktree` por sesión) |
| 3 | Sesión nueva por tarea, sin cola | Viable. Límites: tope de sesiones simultáneas de la organización en la nube (no publicado), 100 disparos por hora por cuenta, costo |
| 4 | Acción automatizada en lugar de cron | `base.automation` nativo con «Stage is set to» + «Send Webhook Notification». Sin código para el disparo (§4) |
| 5 | Usar los tags existentes | Se usan los existentes + un único tag nuevo `0. Team - Claude 🤖` (§5) |
| 6 | No detenerse a preguntar | `--permission-prompts none` existe (CLI 2.1.259+) y deniega lo que pediría permiso; `AskUserQuestion` deshabilitado; las dudas van al chatter (§7) |
| 7 | Pregunta por chatter + reanudación | Hook `/claude` en `project_ai_bot` (las automatizaciones nativas ignoran notas internas). La reanudación en la nube se hace con `claude -p "<respuesta>" --cloud <session_id>` (§8) |
| 8 | Etapas | Todo en `1 In Progress`; la tarea pasa a `Review` al abrir el PR |

### 2.2 Puntos validados tras la daily

| # | Punto | Validación (documentación oficial) | Resultado |
|---|---|---|---|
| 9 | **¿Las sesiones pueden crearse en la nube y no en el equipo local?** | Claude Code *cloud sessions*: cada sesión corre en una VM aislada de Anthropic (Ubuntu 24.04) con **4 vCPU, 16 GB RAM y 30 GB de disco**, sigue corriendo aunque se cierre el equipo, y clona los repos desde GitHub. Disponible en planes Pro, Max, Team y Enterprise (asientos con Claude Code). [cloud-environments](https://code.claude.com/docs/en/cloud-environments) | **Sí.** Elimina la necesidad de disco y RAM grandes en el servidor propio |
| 10 | **¿Se puede manejar desde consola (no sólo la web)?** | CLI verificado (v2.1.310): `claude --cloud "<tarea>"` crea la sesión **sólo en modo interactivo** (con `-p` falla: *"--cloud cannot be combined with --print"*); `claude -p "<mensaje>" --cloud <session_id>` envía un mensaje a una sesión existente y sale (`--output-format json` devuelve `session_id` y `url`). Además, las **tareas programadas (routines)** tienen un disparo HTTP: `POST https://api.anthropic.com/v1/claude_code/routines/<trig_id>/fire` con token propio de la tarea. [claude-code-on-the-web](https://code.claude.com/docs/en/claude-code-on-the-web) · [routines](https://code.claude.com/docs/en/routines) | **Sí.** El gateway dispara con la API de routines y reanuda con `--cloud` |
| 11 | **¿Qué hay que configurar en GitHub?** | Instalar la **Claude GitHub App** en `indexa-git` (requerida para repos privados) o conectar el token de `gh` con `/web-setup`. En plan Team/Enterprise un *Owner* habilita el método. Una sesión puede tener **varios repos** adjuntos (odoo-pro + enterprise) | Pendiente: instalar la app en la organización (owner) |
| 12 | **¿Se pueden correr Odoo, Postgres y pruebas en la nube?** | La VM trae **PostgreSQL 16, Docker + compose, Python, Node y chromedriver**. El *setup script* corre como root (apt/pip) y su resultado se guarda como snapshot si termina en ~5 min (imágenes Docker incluidas). Red: lista de dominios permitidos configurable (se agrega `www.progressa.group`); los **network secrets** se inyectan en las peticiones sin que la sesión los vea (API key de Odoo) | **Sí.** Imagen `odoo:19` de Docker Hub para el core community + `enterprise` y `odoo-pro` adjuntos; master/20 con `indexa-git/odoo-docker-master` |
| 13 | **Autenticación del bot** | `--cloud` exige sesión iniciada con una cuenta de claude.ai (no API key). El token de control de sesiones dura **30 días** como máximo; `claude setup-token` (1 año) sólo sirve para inferencia, no para crear sesiones. El disparo por routines usa un token propio por routine | Iniciar: routine `/fire` (token de larga duración). Reanudar: login de claude.ai en el gateway, **renovar cada 30 días** (riesgo §15). Para operación, pedir a Anthropic identidad de máquina |
| 14 | **Alternativa: ejecutar en nuestro hardware, orquestado por claude.ai** | *Self-hosted environments* (beta pública, Team/Enterprise): `claude self-hosted-runner` en nuestro servidor; las sesiones se crean con `claude -p "…" --environment <ccpool_id>`. El código y los artefactos quedan en el host; la conversación sigue yendo a la API de Anthropic. Cada runner se bloquea al dueño de la primera sesión; capacidad por defecto 1 | Plan B si se necesita más disco/RAM que 30 GB/16 GB por sesión o datos en casa |
| 15 | **Copilot como revisor secundario** | Ver §9.6.3. Copilot code review lee `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, `AGENTS.md` y **`CLAUDE.md`**; no permite elegir modelo; el ruleset automático **no filtra por label**; con una Action se puede filtrar y pedirlo por API (`copilot-pull-request-reviewer[bot]`). Créditos IA mensuales que **se reinician el día 1 a las 00:00 UTC** | Viable para revisar PRs de forward-port. Consumo actual: sólo lo puede ver un owner/billing manager de `indexa-git` (el usuario `luis-pcg` es *member*) |
| 16 | **Servidor de pruebas** | Contenedor creado en la daily: 4 cores, ~12 GB RAM (12 196 MB), 40 GB disco | Suficiente para el gateway + 2–3 sesiones en la nube (o 1–2 locales de una sola versión) |

---

## 3. Arquitectura general

### 3.1 Modo por defecto: sesiones en la nube de Claude

```
┌──────────────────────────── Instancia Progressa (Odoo 19e) ─────────────────────────────┐
│  project.task ── etapa → «1 In Progress» + tag «0. Team - Claude 🤖» + «1. Type - …»     │
│      ▼                                                                                    │
│  base.automation (on_stage_set) ──► Send Webhook Notification ─────────────┐              │
│  Nota interna «/claude …» ──► hook project_ai_bot ──► webhook ─────────────┤              │
│  ◄── notas internas (@asignados), PR, adjuntos, etapa Review ── json2 API ─┼──────┐       │
└────────────────────────────────────────────────────────────────────────────┼──────┼───────┘
                                                                             │HTTPS │
┌──────────────── Contenedor del bot (4 vCPU / 12 GB / 40 GB) ───────────────▼──┐   │
│  bot-gateway (systemd)                                                         │   │
│   · valida secreto · lee la tarea por json2 · elige el entorno por versión     │   │
│   · nueva sesión → POST routines/<trig_id>/fire  {"text": <contexto tarea>}     │   │
│   · respuesta    → claude -p "<respuesta>" --cloud <session_id>                │   │
│   · guarda session_id/url en la tarea; reconciliación al arrancar              │   │
└──────────────────────────────────────────┬─────────────────────────────────────┘   │
                                           │                                         │
┌──────────────── Nube de Claude (una VM por sesión: 4 vCPU / 16 GB / 30 GB) ────────┴───┐
│  Entorno «odoo-19»: repos odoo-pro (rama 19.0) + enterprise · imagen odoo:19 · PG 16    │
│  Entorno «odoo-17», «odoo-20», …                                                         │
│  Claude: reproduce/corrige/migra → tests → manual → push rama *-bot → PR                 │
│          publica notas internas en la tarea (odoo-tasks, API key como network secret)    │
└──────────────────────────────────────────┬──────────────────────────────────────────────┘
                                           │ PR / reviewers
                                    ┌──────▼──────┐   merge   ┌──────────────────────────┐
                                    │   GitHub    │──────────►│ Bot forward-port + revisor│
                                    │ CI + reviews│◄──────────│ IA (Copilot / Claude)     │
                                    └─────────────┘  PR vN+1  └──────────────────────────┘
```

Diferencia clave con v3: el contenedor **no** clona las versiones ni levanta Odoo; sólo recibe
webhooks y lanza/reanuda sesiones. La sesión en la nube publica sus propias notas en la tarea, así que
el gateway no necesita esperar la salida del proceso.

### 3.2 Entornos en la nube (uno por versión)

| Campo | Ejemplo `odoo-19` |
|---|---|
| Repos adjuntos | `indexa-git/odoo-pro` (rama `19.0`), `indexa-git/enterprise` (rama `19.0`) |
| Core community | Imagen Docker `odoo:19` (setup script la descarga y queda en el snapshot) |
| Setup script | `docker pull odoo:19`, dependencias Python de `odoo-pro`, Playwright + Chromium, `context-pack` en `~/.claude` |
| Red | *Custom*: dominios por defecto + `www.progressa.group` |
| Network secrets | API key del usuario Claude Bot en Odoo |
| Variables | `ODOO_URL`, `ODOO_DB`, `ODOO_LOGIN` |

Agregar una versión = crear el entorno con sus ramas e imagen (`odoo:17`, `odoo:19`,
`indexa-git/odoo-docker-master` para 20/master) y registrar la routine correspondiente.

### 3.3 Modo alternativo: ejecución en el contenedor

Si una tarea no cabe en la VM de la nube (30 GB / 16 GB) o la nube no está disponible:

- **Self-hosted environment**: `claude self-hosted-runner` en el contenedor, sesiones con
  `--environment <ccpool_id>`. Mismo flujo, cómputo en casa.
- **Headless local** (diseño v3): `claude -p … --session-id <uuid>` / `--resume <uuid>` con un
  `git worktree` por tarea. Con 12 GB, máximo 2–3 sesiones de una sola versión.

---

## 4. Disparo: acción automatizada

### 4.1 Regla «Claude – iniciar sesión» (sin código)

| Campo | Valor |
|---|---|
| Modelo | Tarea (`project.task`) |
| Disparador | **Stage is set to** → `1 In Progress` |
| Aplicar en (filtro) | `tag_ids` contiene **`0. Team - Claude 🤖`** **y** alguno de: `1. Type - BUG 🐞`, `1. Type - MIG 🏃‍♂️💨`, `1. Type - NEW 🌟`, `1. Type - IMP ✅`, `1. Type - REF ⚠️`, `1. Type - QA 👮🏻‍♂️` |
| Acción | **Send Webhook Notification** |
| URL | `https://<host-del-bot>/hooks/<secreto>/task` |
| Campos enviados | `id`, `name`, `project_id`, `stage_id`, `tag_ids`, `user_ids` |

### 4.2 Limitaciones del webhook nativo y cobertura

| Limitación (Odoo 19, `ir_actions.py`) | Cobertura |
|---|---|
| Timeout de 1 s, "enviar y olvidar" | El gateway responde `202` de inmediato y dispara la sesión en segundo plano |
| Sin reintento | Reconciliación al arrancar: tareas en `1 In Progress` con el tag y sin sesión registrada |
| Sin cabeceras de autenticación | Secreto largo en la URL + HTTPS + IP permitida de la instancia (firewall a cargo de infraestructura) |
| Sólo envía los campos elegidos | La sesión lee descripción, chatter y adjuntos con el usuario técnico Claude Bot |
| La tarea vuelve a `1 In Progress` | Si ya tiene sesión, se **reanuda** en vez de abrir otra |

---

## 5. Tags existentes → comportamiento

| Grupo | Tag | Uso en el bot |
|---|---|---|
| **Activación** | `0. Team - Claude 🤖` *(único tag nuevo)* | Sin este tag el bot no toma la tarea |
| **Tipo** | `1. Type - BUG 🐞` | Corrección con puerta de reproducción (§9.2) |
| | `1. Type - MIG 🏃‍♂️💨` | Migración directa origen → destino (§9.1) |
| | `1. Type - NEW 🌟` / `IMP ✅` / `REF ⚠️` | Análisis aprobado antes de desarrollar (§9.3) |
| | `1. Type - QA 👮🏻‍♂️` | Prueba funcional + manual con capturas (§9.4) |
| **Versión** | `3. Versión - 17` / `19` / `20` … | Entorno donde corre la sesión. En MIG: el menor es origen, el mayor destino |
| | `3. Versión - FWP` | Tras corregir, llevar el fix a las versiones siguientes vía el flujo de forward-port (§9.6) |
| **Módulo** | `l10n_do_accounting`, `payment_azul`, … | Módulo(s) objetivo |
| **Complejidad** | `5. Complejidad - 👶🏼` / `🥶` / `🔥` | Esfuerzo: `medium` / `high` / `xhigh` |
| **Área** | `4. Base - Account`, `4. Base - Payroll`, … | Skills y memorias a cargar |
| **Otros** | `Documentación` | Fuerza generar/actualizar el manual |
| **Usuarios asignados** | `user_ids` (sin cambios) | Reciben la mención cuando Claude pregunta o termina |

---

## 6. Sesiones

### 6.1 Ciclo de vida (modo nube)

1. Disparo → el gateway arma el contexto (id, tipo, versión, módulos, asignados) y llama a la routine
   del entorno de esa versión; guarda `session_id` y `url` en la tarea.
2. La sesión crea la rama `{versión}-{tipo}-{módulo}-bot`, levanta Postgres/Odoo, trabaja y publica notas.
3. Si pregunta, la sesión queda en pausa; la respuesta `/claude …` se envía con `--cloud <session_id>`.
   Las sesiones inactivas pueden reciclarse: todo avance se **empuja a la rama** antes de preguntar,
   para poder retomar desde GitHub.
4. Al cerrar la tarea o hacer merge del PR → se archiva la sesión; la rama se borra con el merge.

### 6.2 Límites reales

| Límite | Efecto | Recomendación |
|---|---|---|
| Sesiones simultáneas por organización (nube, número no publicado) | Nuevas sesiones esperan o fallan | Medir en el prototipo; tope configurable en el gateway (apagado) |
| 100 disparos/hora por cuenta, 30/hora por routine | `429` | Suficiente para el volumen esperado |
| Uso del plan de Claude | Sesiones lentas o bloqueadas al agotar el uso | Separar la cuenta del bot de la de los desarrolladores al pasar a operación |
| VM de la nube: 30 GB disco, comandos de 2–10 min | Migraciones con DB grande o tests largos | Modo alternativo §3.3 |

---

## 7. La sesión de Claude Code

### 7.1 Cómo se lanza

```bash
# nueva sesión en la nube (routine del entorno odoo-19)
curl -X POST "https://api.anthropic.com/v1/claude_code/routines/$TRIG_ID/fire" \
  -H "Authorization: Bearer $ROUTINE_TOKEN" \
  -H "anthropic-beta: experimental-cc-routine-2026-04-01" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"text": "<contexto de la tarea>"}'
# → claude_code_session_id, claude_code_session_url

# respuesta desde el chatter
claude -p "Respuesta de <autor>: <texto>" --cloud "$SESSION_ID" --output-format json
```

El `text` llega a la sesión marcado como no confiable; el prompt guardado en la routine indica
explícitamente que debe tratarlo como la tarea a trabajar (y como dato, no como órdenes del sistema).

Modo alternativo (local), sin cambios respecto a v3:

```bash
claude -p "$PROMPT" --session-id "$UUID" --dangerously-skip-permissions \
  --permission-prompts none --disallowedTools AskUserQuestion \
  --output-format stream-json --verbose --json-schema "$RESULT_SCHEMA" \
  --append-system-prompt-file context-pack/prompts/bot.md --effort "$EFFORT"
```

### 7.2 Por qué no se queda esperando

| Causa | Solución |
|---|---|
| Prompt de permisos | Nube: sin prompts. Local: `--dangerously-skip-permissions` + `--permission-prompts none` |
| `AskUserQuestion` | Deshabilitada; las dudas se publican en el chatter |
| Termina el turno con una duda | Publica la nota con `status: needs_input` y empuja la rama |
| Proceso colgado | Timeout de comandos de la nube; en local el gateway mata la sesión inactiva |

### 7.3 Estado que la sesión publica

Cada nota de la sesión termina con un bloque de estado que el módulo guarda en la tarea:
`done | needs_input | needs_approval | blocked | failed`, resumen, PRs y costo.

---

## 8. Preguntas por chatter y reanudación

```
Sesión termina con needs_input → nota interna «🤖 Claude necesita una respuesta…  Responde con /claude <respuesta>»
   mencionando a user_ids
Usuario escribe nota interna: /claude B, y usa el diario de ventas
Hook project_ai_bot → webhook al gateway {task_id, message_id, author, body}
Gateway → claude -p "Respuesta de <autor>: …" --cloud <session_id>
La sesión continúa con su contexto
```

| Comando (nota interna) | Efecto |
|---|---|
| `/claude <texto>` | Responde o da una instrucción adicional |
| `/claude aprobar` | Aprueba el análisis → Claude desarrolla |
| `/claude rechazar <motivo>` | Rehace el análisis |
| `/claude detener` | Detiene la sesión (conserva la rama) |
| `/claude estado` | Publica en qué va |

Hace falta el override de `project.task.message_post` en `project_ai_bot` porque `base_automation`
no evalúa mensajes internos.

---

## 9. Flujos por tipo

### 9.1 MIGRACIÓN (`1. Type - MIG`) — siempre directa

17→19 salta 18: una rama, un PR, checklists acumulados (`odoo-migrate`), verificación contra el core destino.
Dependencias OCA no portadas → `blocked`. Instalar en DB limpia + actualizar desde DB de origen, tests, `.po`,
manual. Tags: `+3. Versión - <destino>`, `−3. Versión - <origen>`. Los PRs de migración llevan el label
`migration` y **no** entran al flujo de forward-port (§9.6).

### 9.2 BUG (`1. Type - BUG`) — con puerta de reproducción

1. Leer tarea, chatter y adjuntos; si faltan datos → `needs_input`.
2. `replicate_<bug>.sh` sobre datos de demo/semilla. No se reproduce → `blocked` con diagnóstico.
3. Fix mínimo + test.
4. Con `3. Versión - FWP`: el fix sigue el flujo de forward-port al hacer merge (§9.6); ya no se abren
   PRs por versión desde la misma sesión.

El bot **no tiene acceso a datos de clientes**.

### 9.3 NEW / IMP / REF — análisis antes de desarrollar

Sin análisis aprobado → Claude lo genera y pide `/claude aprobar`. Con análisis → desarrollo con tests
por criterio de aceptación, `setup_vXX_<módulo>.sh`, manual y PR.

### 9.4 QA (`1. Type - QA`)

Recorre los flujos con `manual-generator` (Playwright), adjunta el manual PDF, no toca código.

### 9.5 Cierre común

Revisión de código + `pre-commit` → push → PR en inglés con evidencia → CI (máx. N reintentos) →
revisores, PR en la descripción + nota interna (`odoo-tasks pr`) → tarea a `Review`. No registra horas.

### 9.6 FORWARD-PORT (nuevo, acordado en la daily)

#### 9.6.1 Qué hace

El bot de forward-port (Eric, sobre la base del trabajo de este bot) replica el comportamiento del
forward-port de Odoo: un cambio hecho en `17.0` se lleva a la siguiente versión (`19.0`, luego `20.0`)
con un PR automático y un label propio.

#### 9.6.2 Cuándo se dispara

| Opción | Decisión |
|---|---|
| Al aprobarse el PR (dos reviews) | Descartada por ahora: puede haber cambios después de la aprobación |
| **Al hacer merge** | **Elegida.** Tras el segundo review se hace merge de inmediato; disparar en el merge evita gastar tokens en cambios que aún pueden moverse |

Filtros:

| Regla | Motivo |
|---|---|
| Sólo PRs mergeados a una rama de versión (`17.0`, `19.0`) con siguiente versión configurada | La cadena 17.0 → 19.0 → master/20.0 |
| **Excluir PRs con label `migration`** | Una migración ya es la versión destino |
| El PR de forward-port lleva un label (`forward-port`) puesto por el bot | Identificarlo y filtrar la revisión IA |
| Si el cherry-pick tiene conflictos *(propuesta)* | El PR se abre en borrador con el conflicto marcado y se asigna al autor original |

#### 9.6.3 Revisión IA del PR de forward-port

Objetivo de la revisión: que el cambio **aplica y no rompe** la versión destino, y que el formato es
correcto (p. ej. `tree` → `list`, prefijo de versión del manifiesto, APIs renombradas, tests).

| Opción | Cómo | A favor | En contra |
|---|---|---|---|
| **A. Copilot por ruleset** | Regla «Automatically request Copilot code review» en `19.0` / `master` | Sin código; ya pagado; lee `CLAUDE.md` e instrucciones por ruta; PRs de bots se cobran a la organización | Revisa **todos** los PRs a esas ramas (no filtra por label ni autor); no elige modelo; sólo comenta |
| **B. Copilot pedido por una Action** *(recomendada para empezar)* | Workflow en `pull_request` con `if:` autor = bot de FW y sin label `migration` → pide `copilot-pull-request-reviewer[bot]` por REST | Mismo costo que A, con el filtro que necesitamos; pocas líneas de YAML | Verificar si basta `GITHUB_TOKEN` o hace falta un token de app/PAT |
| **C. Claude (`anthropics/claude-code-action`)** | Workflow con prompt propio | Control total: diff contra el commit original, código del core destino, correr tests, elegir modelo | Facturación aparte (API key o token de suscripción), más mantenimiento |
| **D. Agente Claude dentro de Copilot** (`@claude`) | Agentes de terceros en Copilot (vista previa) | Usa créditos de Copilot | Es agente de código, no revisor; sin disparo por API documentado |

Instrucciones para Copilot (viajan con la rama del PR, así cada versión revisa con sus reglas):

```
.github/copilot-instructions.md                     # reglas generales odoo-pro
.github/instructions/forward-port.instructions.md   # applyTo: "**" — checklist de la versión destino
```

Copilot factura en **créditos IA** (Business 1 900 / Enterprise 3 900 por asiento al mes, en bolsa
común). La bolsa se **reinicia el día 1 de cada mes a las 00:00 UTC**; el uso pagado por encima está
activado por defecto en organizaciones. Una revisión cuesta aprox. USD 0,05–1 (Lite) o 0,25–5 (Balanced).

#### 9.6.4 Pendientes del flujo

- Ubicación del código del bot de forward-port (no está en `indexa-git`; el repo `Claudebot-pcg` sólo tiene README).
- Crear los labels `forward-port` y `migration` en `odoo-pro` (hoy no existen).
- Un owner de `indexa-git` revisa el consumo de Copilot del mes y la política de uso pagado.

---

## 10. Capacidad del servidor

### 10.1 Prototipo (contenedor creado en la daily)

| Recurso | Asignado | Uso en modo nube | Uso en modo local (§3.3) |
|---|---|---|---|
| vCPU | 4 | Gateway: < 0,2 | 2 base + 1,5 por sesión → **1–2 sesiones** |
| RAM | ~12 GB | Gateway + CLI: < 1 GB | ~3 GB base (una versión) + 3 GB por sesión → **2–3 sesiones** |
| Disco | 40 GB | < 5 GB (código, logs) | Una versión ≈ 2,2 GB fuentes + ~5 GB imágenes + 1,5 GB por sesión → 1–2 versiones |

Por qué v3 pedía 500 GB: 4 versiones clonadas, ~12 sesiones con su worktree y su DB, imágenes y logs en
el mismo servidor. Con las sesiones en la nube ese disco lo pone cada VM (30 GB c/u) y el servidor
propio no lo necesita.

### 10.2 Escalones (sólo si se descarta la nube)

| Escalón | Sesiones activas | vCPU | RAM | Disco |
|---|---|---|---|---|
| Prototipo | 2–3 | 4 | 12 GB | 40 GB |
| Inicial | hasta 6 | 8 | 32 GB | 250 GB |
| Amplio | hasta 12 | 16 | 64 GB | 500 GB |

Medir el uso real del prototipo dos semanas antes de subir de escalón.

---

## 11. Módulo Odoo `project_ai_bot` (odoo-pro PR #1386)

Toda la configuración del bot vive en Odoo (*Proyecto › Configuración › Claude Bot*); el gateway sólo
recibe el contexto ya resuelto. Agregar una versión, un repositorio o una etiqueta no requiere tocar el bot.

| Modelo | Para qué |
|---|---|
| `project.ai.bot.config` | Gateway (URL, secreto), usuario técnico, tope de sesiones, prefijo `/claude`, etiquetas de activación y documentación, etapas de inicio y revisión, proyectos (many2many) |
| `project.ai.bot.flow` | Corrección / migración / desarrollo / QA, con sus etiquetas de tipo (many2many) y si exige aprobación |
| `project.ai.bot.version` | Etiquetas de versión, rama, imagen Docker, entorno y routine (ID + token), forward-port (`next_version_id`) y destino de migración (`migration_target_id`). Semilla: 17.0 → 19.0 → 20.0/master |
| `project.ai.bot.repository` + líneas por versión | Repos y rama por versión: `odoo/odoo`, `indexa-git/enterprise`, `indexa-git/odoo-pro`, `indexa-git/upgrade-util`, `indexa-git/pyazul` |
| `project.ai.bot.effort` / `project.ai.bot.area` | Complejidad → esfuerzo; área → skills e instrucciones |
| `project.task` | `ai_session_id/url`, `ai_state`, `ai_cost_usd`; flujo y versiones calculados; pestaña «Claude», botón «Enviar a Claude», filtro |

- Mover una tarea activa a una etapa de inicio envía el contexto al gateway tras el commit; una nota
  interna `/claude …` se reenvía a la sesión (las del usuario del bot no).
- Migración: con dos etiquetas de versión, de la menor a la mayor; con una, al destino de esa versión.
- El gateway responde con `ai_bot_register_session` y la sesión informa con `ai_bot_set_state`.
- Al instalar enlaza las etiquetas y etapas de Progressa por nombre y crea `0. Team - Claude 🤖` si falta.
- Probado: 14 tests en una base 19.0 limpia y el ciclo real módulo → gateway → API `/fire` → nota de vuelta.

---

## 12. Despliegue como servicio (repo `indexa-git/bot_ia_odoo`)

Siguiendo el modelo de los servicios ya desplegados en el equipo: todo lo necesario para instalar
está en el repo y Claude puede hacer la instalación entrando por SSH al contenedor.

```
bot_ia_odoo/
├── README.md                 # qué es, cómo correrlo en local
├── requirements.txt
├── .env.example              # variables de entorno (sin secretos)
├── bin/                      # install.sh, bot-gateway (entrypoint), healthcheck
├── bot_gateway/              # servicio Python: webhook → routine / --cloud
├── deploy/
│   ├── DEPLOY.md             # requisitos, instalación, variables, puertos, firewall
│   └── bot-gateway.service   # unidad systemd
├── cloud/                    # setup scripts y prompts de cada entorno de la nube
├── context-pack/             # CLAUDE.md, skills, memorias, tools del bot
├── .github/workflows/        # forward-port review (Copilot/Claude) — se copia a odoo-pro
└── docs/                     # este análisis y su PDF
```

| Variable | Uso |
|---|---|
| `BOT_LISTEN_HOST` / `BOT_LISTEN_PORT` | Dirección del gateway |
| `BOT_WEBHOOK_SECRET` | Secreto de la URL del webhook |
| `BOT_ALLOWED_IPS` | IP(s) de la instancia Progressa |
| `ODOO_URL`, `ODOO_DB`, `ODOO_LOGIN`, `ODOO_API_KEY` | Usuario técnico Claude Bot (json2) |
| `ROUTINE_<VERSION>_ID`, `ROUTINE_<VERSION>_TOKEN` | Routine de la nube por versión |
| `BOT_MAX_CONCURRENT_SESSIONS` | Tope (vacío = sin tope) |

A cargo de infraestructura: abrir el puerto/HTTPS hacia el gateway (o túnel), restringir a la IP de la
instancia y el firewall de salida.

---

## 13. Paquete de contexto

Carpeta `context-pack/` del repo: `CLAUDE.md`, `skills/` (migrar, corregir, desarrollar, analizar,
manual, i18n, revisión, `odoo-tasks`), `memory/`, `tools/` y `prompts/` (plantilla por tipo + reglas de
salida). El setup script de cada entorno de la nube lo copia a `~/.claude`. El mismo paquete alimenta
las instrucciones de Copilot para la revisión de forward-port.

---

## 14. Seguridad

| Medida | Por qué |
|---|---|
| Sesiones en VMs aisladas de la nube; credenciales de GitHub tras el proxy de Anthropic | Un comando erróneo no afecta al servidor propio |
| API key de Odoo como **network secret** | La sesión la usa sin poder leerla |
| Red de la nube en *Custom*: GitHub, Docker Hub, PyPI/npm, `www.progressa.group` | Reduce fuga de datos |
| Contenedor del gateway: usuario no-root, sólo el puerto del webhook, IP de la instancia | Superficie mínima |
| Push sólo a ramas `*-bot`; ramas de versión protegidas | Nunca merge ni push a `17.0`/`19.0` |
| Usuario Claude Bot en Odoo con permisos mínimos | La API key no sirve para otra cosa |
| Sin datos de clientes (credenciales, red, dumps) | Nada real al alcance del bot |
| Texto de tareas/chatter y payload de la routine tratados como datos | Los escriben personas, a veces clientes |
| Modo local: `--dangerously-skip-permissions` sólo en el contenedor exclusivo | El aislamiento lo da el contenedor |

---

## 15. Riesgos

| Riesgo | Mitigación |
|---|---|
| Token de control de sesiones de la nube vence a los 30 días | Renovación programada del login + alerta; pedir a Anthropic identidad de máquina |
| Funciones de la nube en vista previa (routines `/fire`, self-hosted) | Mantener el modo local (§3.3) como respaldo |
| Sesión en pausa reciclada | Empujar la rama antes de preguntar; la reanudación parte de GitHub |
| Tope de sesiones simultáneas de la organización | Medir en el prototipo; tope del gateway |
| Copilot revisa sin ver el commit original | El PR de forward-port incluye el commit/PR de origen en la descripción; si no basta, opción C |
| Revisión automática de Copilot sobre todos los PRs (opción A) | Usar la opción B (Action con filtro) |
| Consumo de Copilot o Claude fuera de presupuesto | Política de uso pagado y presupuesto por owner; reporte mensual |
| Bug que sólo ocurre con datos de cliente | `needs_input` para recrearlo con datos de prueba; si no, `blocked` |
| Webhook perdido | Reconciliación al arrancar el gateway |

---

## 16. Plan por fases

| Fase | Alcance | Esfuerzo aprox. |
|---|---|---|
| **0. Prototipo** | Repo `bot_ia_odoo`; gateway como servicio en el contenedor de pruebas; entorno `odoo-19` en la nube; instalar la Claude GitHub App; prueba de una sesión iniciada por webhook y reanudada desde consola | 3–4 días |
| **1. Forward-port + revisión IA** | Integrar el bot de Eric; disparo al merge; labels; Action de revisión con Copilot (opción B); medir créditos | 1 semana |
| **2. Disparo + BUG + chatter** | `project_ai_bot` (campos, hook `/claude`, tag, usuario técnico, automatización); flujo BUG en v19 | 2 semanas |
| **3. MIG directa** | Entornos 17 y 20/master; checklists acumulados; upgrade-util | 2 semanas |
| **4. NEW/IMP/REF + QA** | Análisis → aprobar → desarrollo; QA con manual-generator | 2 semanas |
| **5. Operación** | Métricas de costo, renovación de credenciales, nuevas versiones | continuo |

---

## 17. Pendientes

| Tema | Responsable | Estado |
|---|---|---|
| Instalar la Claude GitHub App en `indexa-git` y habilitar sesiones en la nube en la organización de Claude | Owner GitHub / admin Claude | Pendiente |
| Revisar consumo y política de Copilot del mes (reinicio 1 de noviembre) | Owner `indexa-git` | Pendiente — `luis-pcg` es *member* y no tiene acceso |
| Código del bot de forward-port y su repositorio | Eric | Pendiente |
| Labels `forward-port` y `migration` en `odoo-pro` | Equipo | Pendiente |
| Acceso SSH al contenedor de pruebas, puerto/HTTPS del webhook y firewall | Infraestructura | Contenedor creado; falta acceso y puertos |
| Cuenta de Claude definitiva del bot (plan, presupuesto) | Dirección | Pruebas con la cuenta actual de Luis |

---

## 18. Pruebas realizadas (2026-10-26)

| # | Prueba | Cómo | Resultado |
|---|---|---|---|
| 1 | Tests unitarios del gateway | `python -m unittest` en contenedor `python:3.12-slim` | **10/10 OK** (13/13 tras el punto 9) |
| 2 | Gateway contra la instancia Progressa real (json2, sólo lectura) | Gateway en contenedor Linux, `POST /hooks/<secreto>/task` con la tarea #75227 | **OK** tras corregir: la instancia respondía `403` al user agent por defecto de Python; ahora envía `bot-ia-odoo-gateway/1.0`. La tarea se leyó y se **descartó** correctamente por no tener el tag `0. Team - Claude 🤖` |
| 3 | Seguridad del webhook | Secreto incorrecto → `404`; el secreto ya no aparece en el log de acceso | **OK** (fuga del secreto en el log detectada y corregida) |
| 4 | Sesión nueva en la nube de Claude | Routine de prueba sin repos, disparada por API | **OK** en ~10 s: 4 vCPU, 15 GB RAM, 31 GB libres, PostgreSQL 16.15, Docker 29.9 |
| 5 | Respuesta del chatter → misma sesión | `send_to_cloud_session()` del gateway (`claude -p "Reply from Luis: …" --cloud <session_id>`) | **OK**: la sesión respondió en el mismo hilo, con su contexto anterior |
| 6 | Contexto de la tarea en el disparo | Disparo de la routine con el JSON de la tarea como texto | **OK**: la sesión leyó `task_id` y `version`. La nube entrega el texto envuelto en `<routine-fire-payload>` **como datos, no como instrucciones**; por eso el prompt de la routine (`cloud/prompts/routine.md`) es el que ordena trabajar esa tarea |
| 7 | Endpoint `/fire` real con el código del gateway | `bin/cloud-test 19` con token inválido | **OK**: `HTTP 401 Invalid bearer token` → URL y cabeceras correctas; sólo falta el token real |
| 8 | Sesión nueva sin routine | `claude -p "…" --cloud "<descripción>"` | **No soportado**: crear sesiones sin intervención sólo es posible con el disparo `/fire` de una routine |
| 9 | Fallos visibles en la tarea | Tests: disparo rechazado o sesión inalcanzable (p. ej. login vencido) | **OK** (13/13 tests): el gateway publica una nota interna con el error y `status: failed`, y no registra la sesión |

Para repetir el ciclo completo en el servidor (disparo + respuesta en la misma sesión) una vez cargado el token: `bin/cloud-test 19`.

Falta para la prueba de punta a punta:

| Paso | Bloqueo | Quién |
|---|---|---|
| Disparo con el token `/fire` de la routine (lo que usa el gateway en producción) | El token del disparo por API se genera desde claude.ai/code/routines | Luis |
| Sesión con `odoo-pro` y `enterprise` adjuntos | GitHub no está conectado a la cuenta de Claude; la Claude GitHub App no está instalada en `indexa-git` | Luis / owner de la organización |
| Tarea de prueba con el tag `0. Team - Claude 🤖` | El tag no existe en la instancia | Equipo |
| Gateway en el contenedor de pruebas | Acceso SSH y puerto HTTPS | Infraestructura |
