# Gateway Modbus a Web

Base de un sistema de gestión de comunicaciones industriales desarrollado con
Python 3.12, Django 5.2, Django REST Framework y SQLite. Incluye autenticación
de usuarios y de la API mediante token, gestión web de dispositivos y usuarios,
histórico de mediciones y un dashboard preparado con Tailwind CSS y Plotly.js.

## Requisitos

- Python 3.12.
- PowerShell en Windows (los comandos siguientes usan esa terminal).
- Acceso a Internet para instalar dependencias y cargar Tailwind CSS y Plotly.js
  desde sus CDN en las plantillas.

## Instalación y ejecución

Desde la carpeta del proyecto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Si PowerShell bloquea la activación del entorno virtual, puedes ejecutar los
comandos de Django directamente con `.\.venv\Scripts\python.exe`.

Abre <http://127.0.0.1:8000/> para el dashboard y
<http://127.0.0.1:8000/admin/> para el sitio de administración de Django.
Las páginas web requieren iniciar sesión; al visitar el dashboard sin sesión,
la aplicación redirige al formulario en `/accounts/login/`.

## Cuentas de prueba

En la base de datos local de desarrollo ya creada:

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `test_admin` | `ModbusTest2026!` |
| Operador | `test_operador` | `OperadorTest2026!` |

El usuario `test_admin` tiene rol Administrador y es superusuario, por lo que
puede acceder a `/admin/`. `test_operador` tiene rol Operador y acceso de solo
lectura a las páginas de dashboard, dispositivos y registros.

Si se crea otra base de datos o se elimina la existente, estas cuentas no se
crean automáticamente. Se pueden crear con:

```powershell
python manage.py createsuperuser
```

Para administrar usuarios desde la interfaz, inicia sesión como administrador
y visita `/accounts/users/`. Los formularios permiten crear usuarios con rol
Administrador u Operador. Para conceder acceso al sitio `/admin/`, el usuario
también debe tener `is_staff` habilitado; la cuenta de prueba `test_admin` ya
lo tiene.

> Estas contraseñas son exclusivamente para pruebas locales. Cámbialas antes de
> desplegar o exponer el servicio en una red.

## Roles y permisos

- **Administrador:** puede ver el dashboard, listar y crear, editar o eliminar
  dispositivos y gestionar usuarios desde la interfaz web. El superusuario de
  prueba también tiene acceso al panel `/admin/`.
- **Operador:** puede consultar el dashboard, dispositivos y registros, pero
  no puede modificar dispositivos ni gestionar usuarios.
- **API:** cualquier usuario autenticado activo con un token válido puede
  enviar registros. El descubrimiento de dispositivos requiere rol
  Administrador. La API autentica al usuario; no vincula el token a un
  dispositivo Modbus individual.
- **Análisis y exportación:** Administradores y Operadores autenticados pueden
  consultar análisis y descargar reportes Excel; ambas acciones son de solo
  lectura.

## Datos y aplicaciones

### `accounts`

Define el modelo `User`, derivado de `AbstractUser`, con el campo `role` y las
opciones `Administrador` y `Operador`. La configuración del proyecto activa el
modelo con `AUTH_USER_MODEL = "accounts.User"`.

### `iot_core`

- `Device`: nombre, dirección Modbus (rango validado de 1 a 247), ubicación y
  estado activo/inactivo, además del tipo de sensor (voltaje, temperatura,
  posición de válvula u otro).
- `DataRecord`: dispositivo relacionado, valor numérico y marca de tiempo
  generada automáticamente al insertar el registro.

La base de datos inicial es SQLite y el archivo se guarda como `db.sqlite3` en
la carpeta raíz del proyecto.

## API para el microcontrolador

Todos los endpoints:

| Método | Ruta | Uso |
|---|---|---|
| `POST` | `/api/token/` | Obtener un token con las credenciales de un usuario. |
| `POST` | `/api/records/` | Guardar una medición autenticada. |
| `POST` | `/api/devices/scan/` | Registrar direcciones detectadas (solo Administrador). |

### 1. Solicitar un token

Envía el usuario y la contraseña de una cuenta activa:

```powershell
$login = @{
    username = "test_operador"
    password = "OperadorTest2026!"
} | ConvertTo-Json

$tokenResponse = Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/api/token/" `
    -ContentType "application/json" `
    -Body $login

$tokenResponse.token
```

La respuesta contiene un objeto JSON similar a:

```json
{"token": "token-generado-por-django"}
```

### 2. Enviar una medición

El cuerpo JSON debe incluir el identificador de un dispositivo activo y el
valor numérico decodificado por el hardware. El timestamp se asigna en el
servidor:

```powershell
$measurement = @{
    device = 1
    value = 21.5
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/api/records/" `
    -Headers @{ Authorization = "Token $($tokenResponse.token)" } `
    -ContentType "application/json" `
    -Body $measurement
```

La respuesta satisfactoria tiene estado HTTP `201 Created` e incluye el ID, el
dispositivo, el valor y la marca de tiempo. Sin token válido, el endpoint
rechaza la solicitud. Para probarlo, primero crea un dispositivo desde
`/devices/create/` como administrador o desde el panel `/admin/`; el valor
`device` del JSON debe ser su ID real.

### Descubrir dispositivos desde el gateway

El hardware o gateway puede comunicar las direcciones Modbus encontradas. La
ruta solo acepta tokens de usuarios con rol Administrador y valida direcciones
del rango Modbus 1–247 sin duplicados:

```powershell
$scan = @{ discovered_ids = @(1, 2, 5) } | ConvertTo-Json
Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/api/devices/scan/" `
    -Headers @{ Authorization = "Token <token-del-administrador>" } `
    -ContentType "application/json" `
    -Body $scan
```

Las direcciones ya registradas se devuelven en `already_registered`. Para
cada dirección nueva, la API crea `Sensor Autodetectado [ID]` con estado
inactivo y ubicación pendiente de configuración. Un administrador puede
clasificar, editar y activar los sensores desde `/devices/`.

## Rutas web

| Ruta | Acceso |
|---|---|
| `/` | Dashboard autenticado, datos recientes y gráfico. |
| `/devices/` | Consulta de dispositivos. |
| `/devices/create/` | Alta de dispositivos, solo Administrador. |
| `/devices/<id>/edit/` | Edición de dispositivos, solo Administrador. |
| `/devices/<id>/delete/` | Eliminación de dispositivos, solo Administrador. |
| `/devices/<id>/analytics/` | Análisis de lecturas, Administrador u Operador autenticado. |
| `/devices/<id>/export/` | Descarga del reporte Excel con rango opcional de fechas. |
| `/records/` | Consulta paginada del histórico. |
| `/accounts/users/` | Gestión de usuarios, solo Administrador. |
| `/accounts/users/create/` | Alta de usuarios, solo Administrador. |
| `/accounts/users/<id>/edit/` | Edición de usuarios, solo Administrador. |
| `/accounts/users/<id>/delete/` | Eliminación de usuarios, solo Administrador. |
| `/accounts/login/` | Inicio de sesión. |
| `/admin/` | Administración de Django para usuarios con `is_staff`. |

El dashboard carga Tailwind CSS y Plotly.js desde CDN. Grafica las últimas
mediciones disponibles y separa las series por tipo de sensor, con una gráfica
y unidad propia para voltaje (V), temperatura (°C) y posición de válvula (%).
Los gráficos, contadores y tabla se actualizan automáticamente cada 5 segundos
consultando el endpoint autenticado `/api/dashboard-data/`, sin recargar la
página. No es una conexión WebSocket: cada actualización hace una solicitud
HTTP nueva.

El análisis individual ofrece filtros `fecha_inicio` y `fecha_fin` con formato
`AAAA-MM-DD`, además de promedio, máximo, mínimo, desviación estándar y
varianza poblacional. El reporte Excel contiene las hojas **Métricas** y
**Registro Histórico**. Sus encabezados están en negrita, las columnas se
ajustan al contenido y el rango temporal se puede enviar como parámetros GET,
por ejemplo:

```text
/devices/1/export/?fecha_inicio=2026-01-01&fecha_fin=2026-01-31
```

Las rutas web `/devices/<id>/analytics/` y `/devices/<id>/export/` requieren
sesión iniciada y son de solo lectura para ambos roles. Los filtros de fechas
son opcionales; cuando se informan ambos, la fecha inicial debe ser anterior o
igual a la final. La API `POST /api/devices/scan/` requiere un token de un
Administrador y recibe `{"discovered_ids": [1, 2, 5]}`. Cada dirección
desconocida se registra inactiva para que un Administrador la configure antes
de recibir telemetría.

Las dependencias para estos reportes están declaradas en `requirements.txt`
(`pandas` y `openpyxl`); instala o actualiza el entorno con:

```powershell
python -m pip install -r requirements.txt
```
El tipo se selecciona al crear o editar cada dispositivo. Las lecturas antiguas
se mantienen y los dispositivos existentes reciben inicialmente el tipo
“Otro”; selecciona el tipo apropiado en la edición de cada dispositivo para
clasificarlos.

## Referencia de hardware y Modbus

### Topología RS-485 sugerida

Ejemplo inicial para una placa ESP32 DevKit clásica con UART2 y un transceptor
RS-485. Confirma los GPIO disponibles y el pinout de tu placa antes de cablear;
los nombres `TX2` y `RX2` no corresponden a los mismos pines en todos los
modelos de ESP32.

| ESP32 | Transceptor RS-485 | Función |
|---|---|---|
| GPIO17 / TX2 | DI / TXD | Datos UART del ESP32 hacia el bus RS-485. |
| GPIO16 / RX2 | RO / RXD | Datos recibidos del bus hacia el ESP32. |
| GPIO4 | DE y `/RE` unidos | Control de dirección: alto transmite; bajo recibe. |
| GND | GND | Referencia común de señal. |
| Alimentación apropiada | VCC | Según las especificaciones del módulo. |
| — | A y B | Par diferencial hacia los equipos RS-485. |

En un módulo con `DE` y `/RE` unidos, GPIO4 alto habilita el transmisor y
deshabilita el receptor; GPIO4 bajo habilita la recepción. El firmware debe
conmutarlo alrededor de cada transmisión. Respeta las tensiones de alimentación
y lógica: el ESP32 usa lógica de 3.3 V; un módulo MAX485 alimentado a 5 V puede
no ser compatible directamente con sus GPIO. Prefiere un transceptor compatible
con 3.3 V, como SP3485, o añade adaptación de nivel adecuada. La terminación y
las resistencias de polarización dependen de la topología y de los extremos del
bus.

### Mapa Modbus de referencia

Esta aplicación web **no implementa un cliente Modbus**: recibe un valor que el
firmware del ESP32 ya leyó y decodificó. Por tanto, los siguientes códigos son
una referencia para el firmware, no una configuración ya aplicada al Gateway:

- **Función 03 (Read Holding Registers):** lee registros de retención de 16
  bits. La escala, el signo, el orden de bytes/palabras y la conversión a `float`
  dependen del mapa de registros del equipo.
- **Función 02 (Read Discrete Inputs):** lee entradas discretas, es decir,
  estados binarios. Si se guardan en el campo actual `value`, el firmware debe
  definir cómo representarlos numéricamente, por ejemplo `0.0` o `1.0`.

El ESP32 debe decodificar la lectura en el hardware y enviar JSON como
`{"device": 1, "value": 21.5}`. `device` es el **ID de la fila `Device` en
Django**, no la dirección Modbus del esclavo. El modelo actual guarda un único
valor numérico por registro; no almacena función, dirección del registro ni el
dato bruto. Para conservar varias variables por dispositivo, habrá que ampliar
el modelo y el contrato API.

## Simulador de varios dispositivos

El archivo `simulador_red.py` usa solo la biblioteca estándar de Python. Crea
primero tres dispositivos activos desde el panel de administración o
`/devices/create/`, asigna sus tipos (por ejemplo, Voltaje, Temperatura y
Posición de válvula) y anota sus IDs reales. El script usa `1,2,3` por defecto;
si tus IDs son otros, pásalos con `--devices`.

1. Inicia Django en una terminal:

   ```powershell
   python manage.py runserver
   ```

2. En una segunda terminal, activa el mismo entorno virtual y ejecuta:

   ```powershell
   python simulador_red.py --devices 1,2,3
   ```

   Para enviar una solicitud por dispositivo en paralelo y observar el
   comportamiento de SQLite bajo concurrencia local:

   ```powershell
   python simulador_red.py --devices 1,2,3 --workers 3
   ```

   También puedes personalizar servidor, usuario, contraseña e IDs:

   ```powershell
   $env:GATEWAY_BASE_URL = "http://127.0.0.1:8000"
   $env:GATEWAY_USERNAME = "test_operador"
   $env:GATEWAY_PASSWORD = "OperadorTest2026!"
   $env:GATEWAY_DEVICE_IDS = "1,2,3"
   python simulador_red.py
   ```

3. Abre <http://127.0.0.1:8000/> y actualiza la página para consultar las
   mediciones que el script va guardando. El dashboard muestra un gráfico
   independiente por categoría de sensor y separa en cada gráfico los
   dispositivos de ese tipo, pero **no actualiza el gráfico automáticamente**.

Detén el proceso con `Ctrl+C`. Con `--workers 1` (por defecto), el simulador
envía solicitudes de forma secuencial; con `--workers 3`, envía una solicitud
por cada uno de los tres dispositivos en paralelo en cada ciclo. Los errores
HTTP o de conexión se informan en la consola. SQLite serializa las escrituras;
la prueba concurrente no garantiza que no haya bloqueos. Si aparece
`database is locked`, reduce trabajadores/frecuencia; para múltiples escritores
o una carga sostenida, evalúa PostgreSQL.

## Retención y limpieza de registros

No hay una purga automática: `DataRecord` conserva el histórico hasta ejecutar
el comando. La vista del dashboard muestra hasta 100 registros recientes y la
vista histórica pagina de 50 en 50, pero la paginación no limita el crecimiento
de la base de datos. A modo de referencia, un dispositivo que envía una
medición cada 10 segundos genera 8.640 registros diarios o aproximadamente
259.200 en 30 días; tres dispositivos generarían unos 777.600 registros en ese
periodo.

El comando `purge_data_records` elimina los registros con más de 30 días por
defecto. Primero puedes hacer una simulación sin borrar:

```powershell
python manage.py purge_data_records --dry-run
```

Para borrar los registros que superen 30 días:

```powershell
python manage.py purge_data_records
```

El periodo se puede cambiar con `--days` (debe ser mayor que cero):

```powershell
python manage.py purge_data_records --days 14
```

Programa este comando periódicamente con el Programador de tareas de Windows o
cron en Linux. Haz copias de seguridad antes de activar la purga, puesto que la
eliminación es permanente.

## Solución de problemas de la API

| HTTP | Causas habituales | Comprobaciones |
|---|---|---|
| `400 Bad Request` | JSON mal formado, falta `device` o `value`, valor no numérico, o el ID no existe. Un dispositivo inactivo también se rechaza con este estado. | Envía JSON válido con `device` como ID existente de un dispositivo activo y `value` numérico. La API espera `device`, no `device_id`. |
| `401 Unauthorized` | Falta el token, el encabezado está mal formado, el token no existe/revocado, o el usuario está inactivo. Las credenciales incorrectas al pedir token también fallan; en `/api/token/` DRF las responde como `400`. | Solicita un token nuevo en `/api/token/` con credenciales correctas y envía `Authorization: Token <token>`. Django REST Framework no hace expirar automáticamente estos tokens. |
| `403 Forbidden` | Usuario autenticado sin permiso para una vista web protegida; también puede deberse a una capa proxy o a una política de permisos añadida en otra configuración. | En el código actual `/api/records/` permite escribir a cualquier usuario autenticado con token válido, sin comprobar su rol. El rol Operador no causa por sí mismo un `403` en esa API. En las vistas web de edición/gestión sí se requiere Administrador. |
| `5xx` o error de conexión | Servidor detenido, error interno, fallo de red, o base SQLite temporalmente ocupada por otra escritura. | Confirma que el servidor responde, revisa la consola de Django y reduce la concurrencia/frecuencia de envío si aparece `database is locked`. |

## Pruebas y migraciones

Ejecuta las pruebas automatizadas:

```powershell
python manage.py test iot_core
```

Las pruebas incluyen autenticación, permisos web, validación de dispositivos y
el comando de retención.

Verifica el estado de la configuración y las migraciones:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
```

Si cambias los modelos, crea migraciones y aplícalas:

```powershell
python manage.py makemigrations
python manage.py migrate
```

## Configuración

Los ajustes principales están en `config/settings.py`:

- `AUTH_USER_MODEL = "accounts.User"` selecciona el usuario personalizado.
- `INSTALLED_APPS` incluye `rest_framework`, `rest_framework.authtoken`,
  `accounts` e `iot_core`.
- `REST_FRAMEWORK` define `TokenAuthentication` y requiere usuarios
  autenticados por defecto.
- `DATABASES` configura SQLite.

Para un despliegue, define al menos las variables de entorno
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` y `DJANGO_ALLOWED_HOSTS` con los dominios
autorizados. No uses las credenciales de demostración en producción y sirve la
API únicamente a través de HTTPS.
