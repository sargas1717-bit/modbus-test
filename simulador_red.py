import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import os
import random
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def parse_device_ids(value):
    try:
        device_ids = [int(item.strip()) for item in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "indica IDs numéricos separados por comas, por ejemplo 1,2,3"
        ) from exc

    if not device_ids or any(device_id < 1 for device_id in device_ids):
        raise argparse.ArgumentTypeError("todos los IDs deben ser mayores que cero")
    if len(set(device_ids)) != len(device_ids):
        raise argparse.ArgumentTypeError("no repitas IDs de dispositivos")
    return device_ids


def post_json(url, payload, headers=None):
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {details}") from exc
    except (TimeoutError, URLError) as exc:
        raise RuntimeError(f"No se pudo conectar con el servidor: {exc}") from exc


def obtain_token(base_url, username, password):
    _, response = post_json(
        f"{base_url}/api/token/",
        {"username": username, "password": password},
    )
    token = response.get("token")
    if not token:
        raise RuntimeError("La respuesta de autenticación no contiene un token.")
    return token


def simulated_value(index):
    ranges = ((215.0, 225.0), (35.5, 45.0), (0.0, 100.0))
    lower, upper = ranges[index % len(ranges)]
    return round(random.uniform(lower, upper), 2)


def send_measurement(base_url, device_id, value, token):
    status, _ = post_json(
        f"{base_url}/api/records/",
        {"device": device_id, "value": value},
        headers={"Authorization": f"Token {token}"},
    )
    if status != 201:
        raise RuntimeError(
            f"Respuesta inesperada para dispositivo {device_id}: HTTP {status}"
        )
    return device_id, value


def simulate(
    base_url, device_ids, token, sample_delay, cycle_delay, workers
):
    print(
        "Enviando telemetría simulada "
        f"({workers} trabajador(es)). Presiona Ctrl+C para detener."
    )
    while True:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    send_measurement,
                    base_url,
                    device_id,
                    simulated_value(index),
                    token,
                )
                for index, device_id in enumerate(device_ids)
            }
            for future in as_completed(futures):
                device_id, value = future.result()
                print(f"[OK] dispositivo={device_id}, valor={value}")
                time.sleep(sample_delay)

        print(f"Ciclo completado; esperando {cycle_delay:g} segundos.")
        time.sleep(cycle_delay)


def main():
    parser = argparse.ArgumentParser(
        description="Simula dispositivos que envían mediciones a la API Modbus."
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GATEWAY_BASE_URL", "http://127.0.0.1:8000"),
        help="URL base del servidor (o GATEWAY_BASE_URL).",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("GATEWAY_USERNAME", "test_operador"),
        help="Usuario de la API (o GATEWAY_USERNAME).",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("GATEWAY_PASSWORD", "OperadorTest2026!"),
        help="Contraseña (o GATEWAY_PASSWORD).",
    )
    parser.add_argument(
        "--devices",
        type=parse_device_ids,
        default=parse_device_ids(os.environ.get("GATEWAY_DEVICE_IDS", "1,2,3")),
        help="IDs existentes separados por comas (o GATEWAY_DEVICE_IDS).",
    )
    parser.add_argument(
        "--sample-delay",
        type=float,
        default=0.5,
        help="Pausa entre dispositivos, en segundos (por defecto: 0.5).",
    )
    parser.add_argument(
        "--cycle-delay",
        type=float,
        default=5.0,
        help="Pausa entre ciclos, en segundos (por defecto: 5).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Solicitudes concurrentes por ciclo (por defecto: 1).",
    )
    args = parser.parse_args()

    if (
        not math.isfinite(args.sample_delay)
        or not math.isfinite(args.cycle_delay)
        or args.sample_delay < 0
        or args.cycle_delay < 0
    ):
        parser.error("las pausas deben ser finitas y no negativas")
    if args.workers < 1:
        parser.error("--workers debe ser al menos 1")
    base_url = args.base_url.rstrip("/")

    try:
        token = obtain_token(base_url, args.username, args.password)
        print("Autenticación correcta.")
        simulate(
            base_url,
            args.devices,
            token,
            args.sample_delay,
            args.cycle_delay,
            args.workers,
        )
    except KeyboardInterrupt:
        print("\nSimulación detenida.")
    except RuntimeError as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
