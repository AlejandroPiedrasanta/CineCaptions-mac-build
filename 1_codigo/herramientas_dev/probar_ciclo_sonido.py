# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_ciclo_sonido.py — regresiones de confirmación de GO y cierre del trabajador tardío de Sonido.
"""Pruebas en memoria: no abren Resolve, no leen preferencias ni escriben el estado del usuario."""
import copy
import sys
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import director_sonido as D
import director_sonido_estado as E


class CicloSonido(unittest.TestCase):
    def setUp(self):
        self.estados, self.general = {}, {}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(E, 'cargar', side_effect=lambda v: copy.deepcopy(self.estados.get(v, {}))))
        self.stack.enter_context(patch.object(E, 'guardar', side_effect=self.guardar))
        self.stack.enter_context(patch.object(E, 'general', side_effect=lambda: copy.deepcopy(self.general)))
        self.stack.enter_context(patch.object(E, 'poner_general', side_effect=lambda **k: self.general.update(k)))
        self.stack.enter_context(patch.object(D, 'activo', return_value=True))
        self.stack.enter_context(patch.object(D, 'log'))
        self.stack.enter_context(patch.object(D, 'fallback'))
        self.stack.enter_context(patch.object(D, '_pistas_sfx_captions', return_value=['SFX']))
        self.destino = {'proyecto': 'Proyecto de prueba', 'timeline': 'Video', 'timeline_id': 'tl-1'}
        self.voz = {'tipo': 'voz_ai', 'archivo': 'voz.wav', 'ini': 0.0, 'dur': 30.0}

    def guardar(self, video, estado):
        self.estados[video] = copy.deepcopy(estado)
        return copy.deepcopy(estado)

    def plan(self):
        return D.al_colocar({'eventos': [{'tipo': 'icono', 'ini': 2.0}], 'zonas': [(2, 3)]},
                            {'evento_voz': self.voz}, 'video.mp4', destino=self.destino)

    def test_plan_preparado_no_anuncia_sincronizacion(self):
        plan = self.plan()
        estado = self.estados['video.mp4']
        self.assertTrue(estado['pendiente_resolve'])
        self.assertIsNone(estado['en_resolve'])
        self.assertFalse(self.general.get('ai_puesto'))
        self.assertEqual(plan['destino_ai'], self.destino)
        self.assertEqual(plan['zonas'], [(2, 3)])
        self.assertEqual([e for e in plan['eventos'] if e['tipo'] != 'voz_ai'], [{'tipo': 'icono', 'ini': 2.0}])

    def test_solo_acuse_exitoso_confirma_pistas_y_sincronia(self):
        plan = self.plan()
        self.assertFalse(D.confirmar_colocacion(plan, False, 'Destino distinto'))
        self.assertTrue(self.estados['video.mp4']['pendiente_resolve'])
        self.assertEqual(self.estados['video.mp4']['error_resolve'], 'Destino distinto')
        self.assertFalse(self.general.get('ai_puesto'))
        self.assertTrue(D.confirmar_colocacion(plan, True))
        self.assertFalse(self.estados['video.mp4']['pendiente_resolve'])
        self.assertTrue(self.estados['video.mp4']['en_resolve'])
        self.assertTrue(self.general['ai_puesto'])
        self.assertTrue(self.general['voz_ai_puesta'])

    def test_acuse_de_otro_go_no_pisa_sesion_nueva(self):
        viejo, nuevo = self.plan(), self.plan()
        self.assertNotEqual(viejo['_ai_sound_sesion'], nuevo['_ai_sound_sesion'])
        self.assertFalse(D.confirmar_colocacion(viejo, True))
        self.assertTrue(self.estados['video.mp4']['pendiente_resolve'])
        self.assertIsNone(self.estados['video.mp4']['en_resolve'])

    def test_trabajador_tardio_no_borra_confirmacion_ni_cambia_plan(self):
        empezado, continuar = threading.Event(), threading.Event()
        analisis = {'tema': 'Tema 1', 'perfil': {}, 'paleta': {}, 'ambiente': {},
                    'musica': {'estado_sugerido': {}}, 'voz': {'nivel_voz_db': -20.0}}
        sfx = {'diseno': {'eventos': [], 'captions': [], 'motions': [], 'viejos': [], 'resumen': {}},
               'puestos': [], 'eventos': [], 'modo': 'hibrido', 'nivel_voz_db': -20.0}
        capas = {'musica': {'plan': []}, 'ambiente': {'plan': []}}
        res = {}

        def voz_lenta(*a, **k):
            empezado.set()
            if not continuar.wait(5):
                raise AssertionError('No se liberó el trabajador de prueba')
            return {'archivo': 'voz_tardia.wav', 'ganancia_db': 0.0}, self.voz

        with patch.object(D.os.path, 'isfile', return_value=True), \
                patch.object(D, 'analizar', return_value=(analisis, {})), \
                patch.object(D, 'guardar_contexto'), \
                patch.object(D, 'preparar_sfx', return_value=sfx), \
                patch.object(D, 'preparar_capas', return_value=capas), \
                patch.object(D, 'preparar_voz', side_effect=voz_lenta), \
                patch.object(D, 'mezclar') as mezcla:
            hilo = threading.Thread(target=D.preparar, args=({'video': 'video.mp4'},), kwargs={'res': res}, daemon=True)
            hilo.start()
            try:
                self.assertTrue(empezado.wait(5), 'El trabajador alcanzó la fase de voz')
                foto = D.cerrar_preparacion(res)
                plan = D.al_colocar(None, foto, 'video.mp4', destino=self.destino)
                self.assertTrue(D.confirmar_colocacion(plan, True))
                confirmado = copy.deepcopy(self.estados['video.mp4'])
            finally:
                continuar.set()
                hilo.join(5)
            self.assertFalse(hilo.is_alive())
            self.assertEqual(self.estados['video.mp4'], confirmado)
            self.assertIsNone(foto['evento_voz'])
            mezcla.assert_not_called()

    def test_rearme_de_go_actualiza_guardia_sin_cambiar_el_audio(self):
        plan = self.plan()
        viejo = copy.deepcopy(plan)
        eventos = copy.deepcopy(plan['eventos'])
        nuevo = dict(self.destino, timeline_id='tl-recreado')
        self.assertTrue(D.revincular_colocacion(plan, nuevo))
        self.assertEqual(plan['eventos'], eventos)
        self.assertEqual(plan['destino_ai'], nuevo)
        self.assertFalse(D.confirmar_colocacion(viejo, True))
        self.assertTrue(D.confirmar_colocacion(plan, True))

    def test_rearme_sin_destino_verificable_no_mueve_la_vinculacion(self):
        plan = self.plan()
        antes = copy.deepcopy(plan)
        self.assertFalse(D.revincular_colocacion(plan, {}))
        self.assertEqual(plan, antes)

    def test_nueva_medicion_limpia_marca_de_score_anterior(self):
        estado = {'sound_score_viejo': True}
        qc = {'score': 89, 'partes': {}, 'mix': {}, 'master': {}, 'medidas': {}, 'correcciones': [], 'formula': {}}
        D._guardar_qc(estado, qc)
        self.assertFalse(estado['sound_score_viejo'])
        self.assertEqual(estado['sound_score'], 89)


if __name__ == '__main__':
    unittest.main(verbosity=2)
