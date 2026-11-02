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
  enviar registros. La API autentica al usuario; no vincula el token a un
  dispositivo Modbus individual.

## Datos y aplicaciones

### `accounts`

Define el modelo `User`, derivado de `AbstractUser`, con el campo `role` y las
opciones `Administrador` y `Operador`. La configuración del proyecto activa el
modelo con `AUTH_USER_MODEL = "accounts.User"`.

### `iot_core`

- `Device`: nombre, dirección Modbus (rango validado de 1 a 247), ubicación y
  estado activo/inactivo.
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

## Rutas web

| Ruta | Acceso |
|---|---|
| `/` | Dashboard autenticado, datos recientes y gráfico. |
| `/devices/` | Consulta de dispositivos. |
| `/devices/create/` | Alta de dispositivos, solo Administrador. |
| `/devices/<id>/edit/` | Edición de dispositivos, solo Administrador. |
| `/devices/<id>/delete/` | Eliminación de dispositivos, solo Administrador. |
| `/records/` | Consulta paginada del histórico. |
| `/accounts/users/` | Gestión de usuarios, solo Administrador. |
| `/accounts/users/create/` | Alta de usuarios, solo Administrador. |
| `/accounts/users/<id>/edit/` | Edición de usuarios, solo Administrador. |
| `/accounts/users/<id>/delete/` | Eliminación de usuarios, solo Administrador. |
| `/accounts/login/` | Inicio de sesión. |
| `/admin/` | Administración de Django para usuarios con `is_staff`. |

El dashboard carga Tailwind CSS y Plotly.js desde CDN. Grafica las últimas
mediciones disponibles y separa las series por dispositivo.

## Pruebas y migraciones

Ejecuta las pruebas automatizadas:

```powershell
python manage.py test iot_core
```

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
