# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/_voz_sapi.py — una voz LIMPIA de referencia (SAPI de Windows, por COM) para los casos sintéticos de probar_director_sonido.py.
"""Una voz limpia de referencia (SAPI de Windows, por COM) para los casos sintéticos del arnés del director."""
import sys
from pathlib import Path
import comtypes.client

destino = Path(sys.argv[1])
texto = ('Hoy te voy a contar tres errores que cometen casi todos al grabar con el celular. '
         'El primero es la luz. Si grabas de espaldas a la ventana, tu cara se queda oscura. '
         'El segundo es el sonido. Un micrófono de diez dólares cambia todo. '
         'Y el tercero, el más importante, es no tener un guion claro. '
         'Sígueme para más consejos como este.')
v = comtypes.client.CreateObject('SAPI.SpVoice')
voces = v.GetVoices()
elegida = None
for i in range(voces.Count):
    d = voces.Item(i).GetDescription()
    print('voz:', d)
    if any(k in d for k in ('Spanish', 'Español', 'Sabina', 'Helena', 'Laura', 'Pablo')) and elegida is None:
        elegida = voces.Item(i)
if elegida is not None:
    v.Voice = elegida
s = comtypes.client.CreateObject('SAPI.SpFileStream')
fmt = comtypes.client.CreateObject('SAPI.SpAudioFormat')
fmt.Type = 38                                   # SAFT48kHz16BitMono
s.Format = fmt
s.Open(str(destino), 3, False)                  # SSFMCreateForWrite
v.AudioOutputStream = s
v.Rate = 0
v.Speak(texto)
s.Close()
print('ok', destino, destino.stat().st_size)
