#!/usr/bin/env python3
# CineCaptions · By Cinema Productions
# 2_recursos/resolve_scripts/CineCaptions - Puente.py — el Puente en Python: vigila ~/DaVinciSubtitles/jobs y ejecuta las órdenes.
"""
CineCaptions - Puente.py
-------------------------------------
Script que corre DENTRO de Resolve (Área de trabajo > Scripts > Utility).
En ingles el menu es Workspace > Scripts > Utility.

PARA QUE SIRVE
==============
La version gratuita de Resolve cerro el scripting externo en 19.1: un
programa de afuera no puede pedirle nada a Resolve. La unica via es correr
Python DESDE ADENTRO, y eso solo pasa cuando el usuario entra al menu.

Este puente se corre UNA SOLA VEZ por sesion de Resolve. Se queda vigilando
la carpeta de trabajos y ejecuta lo que la ventana de CineCaptions le vaya
dejando. Con el puente andando, todos los botones del
programa funcionan solos, sin volver a tocar el menu.

Con Resolve **Studio** no hace falta: ahi la app habla directo por la API.

COMO SE USA
===========
1. Abre tu proyecto en Resolve.
2. Área de trabajo > Scripts > Utility > CineCaptions - Puente
3. Listo. Deja esa consola abierta y usa el programa normalmente.

Para apagarlo: cierra la consola de scripts, o borra el archivo
~/DaVinciSubtitles/puente.stop

QUE HACE POR DENTRO
===================
  ~/DaVinciSubtitles/
      puente.heartbeat      <- reescribe el reloj cada 2 s (asi la app sabe
                               que esta vivo)
      puente.stop           <- si aparece, el puente termina
      jobs/<id>.json        <- trabajo pendiente que dejo la app
      jobs/<id>.done.json   <- respuesta del puente

Cada trabajo dice que accion correr ('detectar', 'subtitulos' o 'sfx'). El
puente importa el script correspondiente y llama a su main() pasandole el
'resolve' que Resolve inyecta en este archivo.
"""

import json
import sys
import time
import traceback
from pathlib import Path

VERSION = "2026-08-10 (puente)"

CARPETA_COMPARTIDA = Path.home() / "DaVinciSubtitles"
CARPETA_TRABAJOS = CARPETA_COMPARTIDA / "jobs"
ARCHIVO_LATIDO = CARPETA_COMPARTIDA / "puente.heartbeat"
ARCHIVO_STOP = CARPETA_COMPARTIDA / "puente.stop"

# Cada cuanto miramos si hay trabajo nuevo.
INTERVALO_S = 0.25
# Cada cuanto reescribimos el latido.
LATIDO_CADA_S = 2.0
# Si no llega ningun trabajo en todo este tiempo, el puente se apaga solo
# para no quedar colgado si el usuario cerro el programa (8 horas).
INACTIVIDAD_MAXIMA_S = 8 * 60 * 60

# Nombre del archivo de cada accion. Tiene que coincidir con SCRIPTS de
# resolve_bridge.py del lado de la app.
SCRIPTS = {
    "detectar": "CineCaptions - Detectar Video.py",
    "subtitulos": "CineCaptions.py",
    "sfx": "CineCaptions - Insertar SFX.py",
}


def _carpeta_de_scripts():
    """Donde estan los otros scripts: al lado de este archivo."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        # Resolve a veces ejecuta sin __file__ definido.
        return Path.cwd()


def _latir():
    try:
        ARCHIVO_LATIDO.write_text(str(time.time()), encoding="utf-8")
    except Exception:
        pass


def _correr_accion(accion, resolve_obj):
    """Importa el script de la accion y corre su main().

    Devuelve (ok, mensaje). Captura todo para que un fallo en un trabajo
    no tumbe el puente entero.
    """
    nombre = SCRIPTS.get(accion)
    if not nombre:
        return False, f"Acción desconocida: {accion}"

    ruta = _carpeta_de_scripts() / nombre
    if not ruta.exists():
        return False, f"No encuentro el script: {ruta}"

    import importlib.util
    mod_name = "_cinecaptions_puente_" + accion
    spec = importlib.util.spec_from_file_location(mod_name, ruta)
    modulo = importlib.util.module_from_spec(spec)
    # Los scripts esperan encontrar 'resolve' como global, igual que cuando
    # Resolve los corre desde el menu.
    modulo.__dict__["resolve"] = resolve_obj

    try:
        spec.loader.exec_module(modulo)
        if hasattr(modulo, "main"):
            modulo.main()
        return True, ""
    except SystemExit as e:
        # Los scripts usan fail() -> SystemExit con el motivo ya impreso.
        msg = str(e)
        if msg.isdigit():
            msg = "El script terminó con error (mira la consola de Resolve)."
        return False, msg
    except Exception as e:
        detalle = traceback.format_exc()
        print(f"[Puente] ERROR en '{accion}':\n{detalle}")
        return False, f"{type(e).__name__}: {e}"


def _responder(job_id, ok, mensaje):
    destino = CARPETA_TRABAJOS / f"{job_id}.done.json"
    try:
        destino.write_text(json.dumps({
            "id": job_id,
            "ok": bool(ok),
            "mensaje": mensaje or "",
            "respondido_en": time.time(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Puente] No pude escribir la respuesta: {e}")


def _pendientes():
    """Trabajos sin atender, del mas viejo al mas nuevo."""
    if not CARPETA_TRABAJOS.is_dir():
        return []
    archivos = [p for p in CARPETA_TRABAJOS.glob("*.json")
                if not p.name.endswith(".done.json")]
    return sorted(archivos, key=lambda p: p.stat().st_mtime)


def main():
    try:
        resolve_obj = resolve            # noqa: F821  (lo inyecta Resolve)
    except NameError:
        print("[Puente] ERROR: este script tiene que correrse DESDE Resolve:")
        print("         Área de trabajo > Scripts > Utility > "
              "CineCaptions - Puente")
        return

    CARPETA_TRABAJOS.mkdir(parents=True, exist_ok=True)

    # Si quedo una orden de apagado vieja, la limpiamos antes de arrancar.
    if ARCHIVO_STOP.exists():
        try:
            ARCHIVO_STOP.unlink()
        except Exception:
            pass

    # Trabajos que quedaron de una sesion anterior no valen: los tiramos
    # para no ejecutar algo que el usuario pidio hace horas.
    for viejo in _pendientes():
        try:
            viejo.unlink()
        except Exception:
            pass

    print("=" * 58)
    print(f"  CineCaptions - Puente  |  {VERSION}")
    print("=" * 58)
    print()
    print("  Puente ACTIVO. Ya puedes usar el programa normalmente:")
    print("  los botones van a ejecutarse solos.")
    print()
    print("  Deja esta ventana abierta mientras trabajas.")
    print("  Para apagarlo, cierra esta consola.")
    print()

    _latir()
    ultimo_latido = time.time()
    ultima_actividad = time.time()
    atendidos = 0

    while True:
        ahora = time.time()

        if ARCHIVO_STOP.exists():
            print("[Puente] Recibí la orden de apagado. Chau.")
            try:
                ARCHIVO_STOP.unlink()
            except Exception:
                pass
            break

        if ahora - ultimo_latido >= LATIDO_CADA_S:
            _latir()
            ultimo_latido = ahora

        if ahora - ultima_actividad > INACTIVIDAD_MAXIMA_S:
            print("[Puente] Muchas horas sin trabajos. Me apago.")
            break

        trabajos = _pendientes()
        if not trabajos:
            time.sleep(INTERVALO_S)
            continue

        for archivo in trabajos:
            try:
                trabajo = json.loads(archivo.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[Puente] Trabajo ilegible ({archivo.name}): {e}")
                try:
                    archivo.unlink()
                except Exception:
                    pass
                continue

            job_id = trabajo.get("id") or archivo.stem
            accion = trabajo.get("accion")

            # Lo borramos ANTES de ejecutar: si el script revienta feo, no
            # queremos que el trabajo quede dando vueltas y se repita.
            try:
                archivo.unlink()
            except Exception:
                pass

            print(f"\n[Puente] -> {accion}")
            inicio = time.time()
            ok, mensaje = _correr_accion(accion, resolve_obj)
            tardo = time.time() - inicio

            estado = "OK" if ok else "FALLO"
            print(f"[Puente] {estado} ({tardo:.1f}s)"
                  + (f": {mensaje}" if mensaje else ""))

            _responder(job_id, ok, mensaje)
            atendidos += 1
            ultima_actividad = time.time()
            # Un trabajo largo puede haberse comido varios latidos.
            _latir()
            ultimo_latido = time.time()

    # Al salir, borramos el latido para que la app sepa enseguida que el
    # puente ya no esta.
    try:
        if ARCHIVO_LATIDO.exists():
            ARCHIVO_LATIDO.unlink()
    except Exception:
        pass
    print(f"\n[Puente] Cerrado. Trabajos atendidos: {atendidos}.")


if __name__ == "__main__":
    main()
