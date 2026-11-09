// CineCaptions · By Cinema Productions
// 2_recursos/premiere/com.cinecaptions.premiere/js/cc.js — cada segundo pregunta a ExtendScript (jsx/colocar.jsx) si GO dejó un pedido.
// Toda la lógica está en el .jsx (lee y escribe los archivos de la cola); aquí solo el reloj y el estado del panel.
(function () {
  var cep = window.__adobe_cep__;
  var ocupado = false;
  var vueltas = 0;

  function pintar(texto, tono) {
    var e = document.getElementById('estado');
    var p = document.getElementById('punto');
    if (e) { e.textContent = texto; }
    if (p) { p.className = 'punto' + (tono ? ' ' + tono : ''); }
  }

  function tic() {
    if (!cep || ocupado) { return; }
    ocupado = true;
    vueltas += 1;
    var latir = (vueltas % 3 === 1) ? 'true' : 'false';
    cep.evalScript('(typeof CC !== "undefined" && CC.revisar) ? CC.revisar(' + latir + ') : "sin_jsx"', function (r) {
      ocupado = false;
      if (r === 'colocado') {
        pintar('Listo: GO colocó tu video en una secuencia nueva.', 'ok');
      } else if (r === 'error') {
        pintar('GO no pudo colocar: mira el Registro de CineCaptions.', 'mal');
      } else if (r === 'sin_jsx' || (r && r.indexOf && r.indexOf('EvalScript error') === 0)) {
        pintar('Premiere no cargó el script de CineCaptions.', 'mal');
      } else if (r === 'nada' || r === 'ocupado') {
        if (vueltas < 3 || document.getElementById('estado').textContent === 'Conectando…') {
          pintar('Conectado con CineCaptions', 'ok');
        }
      }
    });
  }

  setInterval(tic, 1000);
  setTimeout(tic, 300);
})();
