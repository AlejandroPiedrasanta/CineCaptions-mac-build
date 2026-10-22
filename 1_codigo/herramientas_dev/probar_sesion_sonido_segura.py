# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_sesion_sonido_segura.py — regresiones de destino, instrucciones y estado de la sesión de Sonido.
"""Regresiones de la página Sonido: estado/prefs en memoria y Resolve simulado.

Ejecutar con el Python del proyecto. No abre Resolve, no genera audio y no lee ni
escribe preferencias o proyectos reales del usuario.
"""
import copy
import sys
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import director_sonido as D
import director_sonido_estado as E
import director_sonido_sesion as S


class SesionSegura(unittest.TestCase):
    def setUp(self):
        self.pila = ExitStack()
        self.addCleanup(self.pila.close)
        self.destino = {'proyecto': 'Proyecto A', 'timeline': 'Edición', 'timeline_id': 'tl-1'}
        self.estados = {'A.mp4': self.estado()}
        self.general = {}
        self.prefs = {}
        self.colocar = Mock(return_value=(True, 'Colocado'))
        ajustes = types.SimpleNamespace(leer_prefs=lambda: copy.deepcopy(self.prefs),
                                        guardar_prefs=lambda cambios: self.prefs.update(copy.deepcopy(cambios)))
        self.pila.enter_context(patch.dict(sys.modules, {
            'ajustes_ui': ajustes,
            'efectos_visuales': types.SimpleNamespace(aplicar=self.colocar),
            'resolve_mcp': types.SimpleNamespace(ruta_exe=lambda: None, resolve_abierto=lambda: True),
        }))
        for modulo, nombre, valor in (
            (E, 'cargar', lambda video: copy.deepcopy(self.estados.get(str(video), {}))),
            (E, 'guardar', self.guardar), (E, 'general', lambda: copy.deepcopy(self.general)),
            (E, 'poner_general', lambda **c: self.general.update(copy.deepcopy(c))),
            (D, 'activo', lambda: True), (D, 'controles', lambda: copy.deepcopy(self.prefs.get(D.PREF_CONTROLES, {}))),
            (D, 'cargar_contexto', lambda video: {'video': video, 'palabras': []}),
            (D, 'destino_actual_resolve', lambda: copy.deepcopy(self.destino)),
            (S, '_nota_material', lambda: {'clave': 'material'}),
        ):
            self.pila.enter_context(patch.object(modulo, nombre, valor, create=True))
        self.pila.enter_context(patch.object(Path, 'is_file', return_value=True))

    def estado(self):
        return {'sound_events': [], 'analisis': {'voz': {'duracion': 60}}, 'sound_score': 81,
                'sfx_plan': [{'tipo': 'sonido', 'archivo': 's.wav', 'ai': {'clave': 'evento-1'}}],
                'pendiente_resolve': True, 'ultimo_go': {'con_director': True, 'destino': copy.deepcopy(self.destino)}}

    def guardar(self, video, estado):
        self.estados[str(video)] = copy.deepcopy(estado)
        return copy.deepcopy(estado)

    def test_resumen_no_sustituye_el_video_elegido(self):
        self.estados['B.mp4'] = self.estado()
        self.estados['A.mp4'] = {}
        self.general['ultimo_video'] = 'B.mp4'
        r = S.resumen('A.mp4')
        self.assertEqual(r['video'], 'A.mp4')
        self.assertFalse(r['hay'])
        self.assertFalse(r['otro_video'])
        self.assertFalse(r['puede_aplicar'])
        self.assertEqual(r['ultimo_disponible']['video'], 'B.mp4')

    def test_resumen_expone_medicion_pendiente_y_destino_sin_resolve(self):
        self.estados['A.mp4']['sound_score_viejo'] = True
        with patch.object(D, 'destino_actual_resolve', side_effect=AssertionError('No consultar Resolve al resumir')):
            r = S.resumen('A.mp4')
        self.assertTrue(r['sound_score_viejo'])
        self.assertEqual(r['destino'], self.destino)
        r['destino']['timeline'] = 'No debe mutar el estado'
        self.assertEqual(self.estados['A.mp4']['ultimo_go']['destino']['timeline'], 'Edición')

    def test_controles_conservan_su_alcance_global(self):
        S.poner_control('musica', 'poco')
        self.assertEqual(self.prefs[D.PREF_CONTROLES], {'musica': 'poco'})
        self.assertNotIn('controles', self.estados['A.mp4'])
        S.poner_control('musica', 'auto')
        self.assertEqual(self.prefs[D.PREF_CONTROLES], {})

    def test_negacion_no_invierte_la_intencion(self):
        r = S.interpretar('No quiero más sonidos')
        self.assertIn(('control', 'densidad', 'poco'), r['acciones'])
        self.assertNotIn(('control', 'densidad', 'mucho'), r['acciones'])
        for pedido in ('No quiero menos sonidos', 'Nunca más música', 'No reset'):
            with self.subTest(pedido=pedido):
                r = S.interpretar(pedido)
                self.assertFalse(r['acciones'])
                self.assertTrue(r['requiere_aclaracion'])

    def test_orden_por_tramo_no_cambia_controles_globales(self):
        for pedido in ('Sin música al final', 'Más ambiente desde el segundo 10', 'Menos sonidos en esta parte'):
            with self.subTest(pedido=pedido):
                r = S.interpretar(pedido, 60)
                self.assertFalse(r['acciones'])
                self.assertTrue(r['requiere_aclaracion'])
                with patch.object(S, '_rehacer') as rehacer:
                    S.ejecutar('A.mp4', r['acciones'])
                rehacer.assert_not_called()
        self.assertEqual(self.prefs, {})

    def test_orden_combinada_recalcula_capas_y_solo_varia_el_tramo(self):
        self.estados['A.mp4']['sound_events'] = [{'clave': 'intro', 'ancla': 2}, {'clave': 'final', 'ancla': 58}]
        r = S.interpretar('Sin música y rediseña el final', 60)
        self.assertIn(('control', 'musica', 'nada'), r['acciones'])
        with patch.object(S, '_rehacer', return_value={}) as rehacer:
            S.ejecutar('A.mp4', r['acciones'])
        self.assertTrue(rehacer.call_args.kwargs['capas'])
        self.assertIn('final', self.estados['A.mp4']['ajustes'])
        self.assertNotIn('intro', self.estados['A.mp4']['ajustes'])
        self.assertEqual(self.prefs[D.PREF_CONTROLES]['musica'], 'nada')

    def test_redisenar_total_tambien_conserva_cambio_de_capas(self):
        with patch.object(S, '_rehacer', return_value={}) as rehacer:
            S.ejecutar('A.mp4', [('control', 'ambiente', 'mucho'), ('redisenar',)])
        self.assertTrue(rehacer.call_args.kwargs['capas'])
        self.assertEqual(self.estados['A.mp4']['ronda'], 1)

    def test_plan_es_una_copia_y_conserva_la_guardia_de_destino(self):
        plan = S.plan_para_resolve('A.mp4')
        self.assertEqual(plan['destino_ai'], self.destino)
        plan['eventos'][0]['ai']['clave'] = 'Otra'
        plan['destino_ai']['timeline'] = 'Otro'
        self.assertEqual(self.estados['A.mp4']['sfx_plan'][0]['ai']['clave'], 'evento-1')
        self.assertEqual(self.estados['A.mp4']['ultimo_go']['destino']['timeline'], 'Edición')

    def test_diseno_anterior_sin_destino_pide_go_y_no_coloca(self):
        self.estados['A.mp4']['ultimo_go'].pop('destino')
        ok, mensaje = S.aplicar('A.mp4')
        self.assertFalse(ok)
        self.assertIn('GO', mensaje)
        self.colocar.assert_not_called()
        self.assertFalse(S.resumen('A.mp4')['puede_aplicar'])

    def test_destino_distinto_bloquea_antes_de_colocar(self):
        for clave in ('proyecto', 'timeline', 'timeline_id'):
            with self.subTest(clave=clave):
                actual = dict(self.destino, **{clave: 'Otro'})
                with patch.object(D, 'destino_actual_resolve', return_value=actual):
                    ok, _ = S.aplicar('A.mp4')
                self.assertFalse(ok)
        self.colocar.assert_not_called()

    def test_destino_no_disponible_no_declara_exito(self):
        with patch.object(D, 'destino_actual_resolve', return_value={}):
            ok, _ = S.aplicar('A.mp4')
        self.assertFalse(ok)
        self.colocar.assert_not_called()

    def test_exito_confirmado_actualiza_estado(self):
        ok, _ = S.aplicar('A.mp4', offset_frames=15)
        self.assertTrue(ok)
        self.assertFalse(self.estados['A.mp4']['pendiente_resolve'])
        self.assertTrue(self.estados['A.mp4']['en_resolve'])
        self.assertTrue(self.general['ai_puesto'])
        self.assertEqual(self.colocar.call_args.kwargs['offset_frames'], 15)
        self.assertEqual(self.colocar.call_args.args[0]['destino_ai'], self.destino)

    def test_resultado_sin_confirmacion_no_marca_sincronia(self):
        for respuesta in (False, None, 'pendiente', {'ok': True}):
            with self.subTest(respuesta=respuesta):
                self.colocar.return_value = (respuesta, '')
                ok, _ = S.aplicar('A.mp4')
                self.assertFalse(ok)
                self.assertTrue(self.estados['A.mp4']['pendiente_resolve'])
                self.assertNotIn('en_resolve', self.estados['A.mp4'])
        self.assertEqual(self.general, {})

    def test_cambio_de_destino_durante_envio_no_marca_sincronia(self):
        otro = dict(self.destino, timeline_id='tl-2')
        with patch.object(D, 'destino_actual_resolve', side_effect=[self.destino, otro]):
            ok, _ = S.aplicar('A.mp4')
        self.assertFalse(ok)
        self.assertTrue(self.estados['A.mp4']['pendiente_resolve'])
        self.assertNotIn('en_resolve', self.estados['A.mp4'])

    def test_resultado_tardio_no_sobrescribe_diseno_nuevo(self):
        def colocar(*a, **kw):
            self.estados['A.mp4']['sfx_plan'][0]['archivo'] = 'nuevo.wav'
            return True, 'Colocado'
        self.colocar.side_effect = colocar
        ok, _ = S.aplicar('A.mp4')
        self.assertFalse(ok)
        self.assertEqual(self.estados['A.mp4']['sfx_plan'][0]['archivo'], 'nuevo.wav')
        self.assertTrue(self.estados['A.mp4']['pendiente_resolve'])
        self.assertNotIn('en_resolve', self.estados['A.mp4'])

    def test_destino_sin_id_usa_nombres_y_compatibilidad_api(self):
        self.estados['A.mp4']['ultimo_go']['destino'].pop('timeline_id')
        ok, _ = S.aplicar_al_momento('A.mp4')
        self.assertTrue(ok)
        self.assertFalse(self.estados['A.mp4']['pendiente_resolve'])

    def test_medicion_anterior_se_marca_pendiente_si_no_se_recalcula(self):
        self.estados['A.mp4']['analisis']['voz']['duracion'] = 700
        with patch.object(D, 'preparar_sfx', return_value={}), patch.object(D, '_guardar_sfx'):
            r = S._rehacer('A.mp4')
        self.assertTrue(r['sound_score_viejo'])
        self.assertEqual(r['sound_score'], 81)


if __name__ == '__main__':
    unittest.main(verbosity=2)
