# CineCaptions · By Cinema Productions
# 1_codigo/audio_compatible.py — v5.4.52 (auditoría de los renders: el video quedaba MUDO): los videos bajados de Pinterest / Instagram / TikTok
# suelen traer el audio en HE-AAC v1/v2 (estéreo paramétrico). Resolve lo importa (lo ve como 1 canal) pero lo renderiza como SILENCIO, aunque
# CineCaptions lo transcriba bien. Antes de llevar un video así a Resolve se hace una COPIA con la imagen tal cual (sin recodificar) y el audio en
# AAC-LC estéreo a 48 kHz, que Resolve sí lee; la copia lleva el mismo nombre de archivo (en ~/DaVinciSubtitles/audio_compatible/<huella>/).
"""
    necesita(ruta) -> bool
    para_resolve(ruta, al_estado=None) -> ruta (la copia compatible o, si no hace falta o no se pudo, la original)
"""
import hashlib
from pathlib import Path

CARPETA = Path.home() / 'DaVinciSubtitles' / 'audio_compatible'


def necesita(ruta) -> bool:
    try:
        import av
        with av.open(str(ruta)) as c:
            if not c.streams.audio:
                return False
            cc = c.streams.audio[0].codec_context
            return cc.name == 'aac' and 'HE' in str(cc.profile or '').upper()
    except Exception:
        return False


def para_resolve(ruta, al_estado=None):
    origen = Path(str(ruta))
    if not necesita(origen):
        return str(origen)
    try:
        huella = hashlib.sha1(f'{origen.resolve()}|{origen.stat().st_size}|{origen.stat().st_mtime_ns}'.encode('utf-8')).hexdigest()[:12]
        destino = CARPETA / huella / origen.with_suffix('.mp4').name
        if destino.is_file() and destino.stat().st_size > 1000:
            return str(destino)
        if al_estado:
            al_estado('Preparando el audio de tu video para Resolve (HE-AAC → AAC)…')
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.stem + '.tmp.mp4')
        import av
        with av.open(str(origen)) as i, av.open(str(tmp), 'w', format='mp4') as o:
            vin = i.streams.video[0] if i.streams.video else None
            ain = i.streams.audio[0]
            vout = o.add_stream_from_template(vin) if vin is not None else None
            aout = o.add_stream('aac', rate=48000)
            aout.layout = 'stereo'
            aout.bit_rate = 256000
            rs = av.AudioResampler(format='fltp', layout='stereo', rate=48000)
            flujos = [s for s in (vin, ain) if s is not None]
            for pk in i.demux(*flujos):
                if vin is not None and pk.stream is vin:
                    if pk.dts is None:
                        continue
                    pk.stream = vout
                    o.mux(pk)
                    continue
                try:
                    cuadros = pk.decode()
                except av.error.InvalidDataError:
                    continue                                             # un paquete dañado: se salta
                for fr in cuadros:
                    for f2 in rs.resample(fr):
                        f2.pts = None
                        for p2 in aout.encode(f2):
                            o.mux(p2)
            for f2 in rs.resample(None):
                f2.pts = None
                for p2 in aout.encode(f2):
                    o.mux(p2)
            for p2 in aout.encode(None):
                o.mux(p2)
        tmp.replace(destino)
        return str(destino)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return str(origen)
