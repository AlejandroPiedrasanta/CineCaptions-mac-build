// =============================================================================================================================
// CineCaptions · By Cinema Productions
// 7_mac/instalador/instalador_mac.swift — Contents/MacOS/instalar de «Instalar CineCaptions.app» (la app del .dmg): la ventana del
// instalador, NATIVA (AppKit + SwiftUI), para que se vea AL INSTANTE al hacer doble clic.
// v5.92 (el usuario: «necesito que funcione el instalador como el de CineSlide»; eligió «sí, en Mac»): copia de CineSlide 9.62
// (CINESLIDE/PROGRAMA/2_CONSTRUIR_INSTALADORES/GITHUB/instalador_mac.swift) con los colores de CineCaptions (azul noche y verde).
// - Si CineCaptions ya está instalado con esta versión o una más nueva, solo lo abre.
// - Si no: la ventana (panel con el logo y un anillo de luz, barra con degradado y los 6 pasos), ejecuta Resources/instalar.sh y
//   sigue el avance que escribe en CINECAPTIONS_AVANCE (una línea por evento: PASO / OK / AVISO / DETALLE / FALLO / FIN, tabulador,
//   texto). Al terminar abre CineCaptions de inmediato, se cierra y expulsa el disco. Si falla: el motivo, «Ver registro» y «Cerrar».
//   instalar --demo | --demo-error      simula una instalación (para ver el diseño en las pruebas)
// La app nueva viaja OCULTA en el disco, junto a esta («.CineCaptions.app»: oculta por el punto, sin marcas que se copien) y no dentro:
// así esta app pesa poco y macOS no verifica 1,4 GB antes de abrir la ventana. Si macOS la abre «trasladada» (App Translocation: copia
// aparte, sin lo que tiene al lado), se busca en /Volumes.
// Lo compila 7_mac/Construir_Instalador_Mac.sh con swiftc en la propia Mac (Windows no puede).
// =============================================================================================================================
import AppKit
import SwiftUI

// ---------------------------------------------------------------------------------------------------------------- colores
extension Color {
    init(hex: UInt32, a: Double = 1) {
        self.init(.sRGB, red: Double((hex >> 16) & 0xff) / 255, green: Double((hex >> 8) & 0xff) / 255,
                  blue: Double(hex & 0xff) / 255, opacity: a)
    }
}

let VERDE = Color(hex: 0x24d18f), AGUA = Color(hex: 0x7af0c2), AZUL = Color(hex: 0x4589ff), CIAN = Color(hex: 0x00c8ff)
let TEXTO = Color(hex: 0xe8f1ff), SUAVE = Color(hex: 0x8d9bb5), TENUE = Color(hex: 0x5c6b88)
let ROJO = Color(hex: 0xff6b6b), AMBAR = Color(hex: 0xf5b84b)

// ---------------------------------------------------------------------------------------------------------------- textos
let ES = (Locale.preferredLanguages.first ?? "es").hasPrefix("es")
func T(_ es: String, _ en: String) -> String { ES ? es : en }
let PASOS = [T("CineCaptions en Aplicaciones", "CineCaptions in Applications"), T("Permiso para abrirlo", "Permission to open it"),
             T("Scripts de DaVinci Resolve", "DaVinci Resolve scripts"), T("Tipografías de los estilos", "Style fonts"),
             T("Actualizaciones automáticas", "Automatic updates"), T("App en el Dock", "App in the Dock"),
             T("Motor de voz e IA", "Voice and AI engine")]                // (v5.92: se deja bajando aparte, el primer GO no lo espera)
let NPASOS = 7
// porcentaje al empezar y al terminar cada paso (0 = preparar) y segundos típicos: dentro de un paso la barra avanza sola hacia
// su final sin llegar, así nunca se ve detenida (copiar la app, ~1,4 GB, es lo largo)
let TRAMOS: [(Double, Double)] = [(0, 3), (3, 60), (60, 64), (64, 78), (78, 88), (88, 93), (93, 96), (96, 99)]
let DURACION: [Double] = [1, 9, 1, 3, 4, 2, 1, 1]
let RESTO_S = 5.0                                   // segundos típicos de los pasos 2-6 (medido en Macs de GitHub, 2026-11-16)

let HOME = NSHomeDirectory()

func quitarANSI(_ s: String) -> String {
    let rx = try! NSRegularExpression(pattern: "\u{1B}\\[[0-9;?]*[A-Za-z]")
    return rx.stringByReplacingMatches(in: s, range: NSRange(s.startIndex..., in: s), withTemplate: "")
}

func numeroVersion(_ v: String) -> Int {
    let p = v.split(separator: ".").map { Int($0) ?? 0 }
    return (p.count > 0 ? p[0] : 0) * 1_000_000 + (p.count > 1 ? p[1] : 0) * 1_000 + (p.count > 2 ? p[2] : 0)
}

func versionDe(_ app: String) -> String? {
    guard let d = NSDictionary(contentsOfFile: app + "/Contents/Info.plist") else { return nil }   // (sin caché: Bundle(path:) la guarda)
    return d["CFBundleShortVersionString"] as? String
}

// la CineCaptions instalada MÁS NUEVA (puede haber dos: la de /Applications de otra cuenta o de root y la de este usuario en ~/Applications)
func appInstalada() -> String? {
    var mejor: (ruta: String, v: Int)? = nil
    for ruta in ["/Applications/CineCaptions.app", HOME + "/Applications/CineCaptions.app"]
        where FileManager.default.isExecutableFile(atPath: ruta + "/Contents/MacOS/CineCaptions") {
        let v = numeroVersion(versionDe(ruta) ?? "0")
        if mejor == nil || v > mejor!.v { mejor = (ruta, v) }
    }
    return mejor?.ruta
}

func versionInstalada() -> String? { appInstalada().flatMap(versionDe) }

// las tarjetas del aviso de actualizaciones SON CineCaptions (`--tarea aviso_mac`): con una abierta, abrir CineCaptions solo la traería al
// frente (MEDIDO en el servicio). Se cierran antes de abrirlo
func cerrarTarjetasDelAviso() {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
    p.arguments = ["-f", "--", "--tarea aviso_mac"]
    p.standardOutput = FileHandle.nullDevice
    p.standardError = FileHandle.nullDevice
    try? p.run()
    p.waitUntilExit()
}

func abrir(_ app: String) {
    cerrarTarjetasDelAviso()
    NSWorkspace.shared.openApplication(at: URL(fileURLWithPath: app), configuration: NSWorkspace.OpenConfiguration()) { _, _ in }
}

// la app que trae el disco: junto a esta; si macOS la trasladó, en el disco montado (/Volumes) que trae esta versión
func buscarPaquete(_ version: String) -> (app: String, volumen: String?)? {
    let fm = FileManager.default
    func esApp(_ r: String) -> Bool { fm.isExecutableFile(atPath: r + "/Contents/MacOS/CineCaptions") }
    func volumen(_ r: String) -> String? {
        let c = (r as NSString).pathComponents
        return c.count > 2 && c[1] == "Volumes" ? "/Volumes/" + c[2] : nil
    }
    let alLado = (Bundle.main.bundlePath as NSString).deletingLastPathComponent + "/.CineCaptions.app"
    if esApp(alLado) { return (alLado, volumen(alLado)) }
    let dentro = (Bundle.main.resourcePath ?? "") + "/CineCaptions.app"           // (pruebas: la app dentro del instalador)
    if esApp(dentro) { return (dentro, nil) }
    var otra: String? = nil
    // (solo los discos «CineCaptions …»: mirar dentro de otros —externos, de red— podía pedir permiso o colgar la ventana con uno dormido)
    for v in (try? fm.contentsOfDirectory(atPath: "/Volumes")) ?? [] where v.hasPrefix("CineCaptions") {
        let r = "/Volumes/" + v + "/.CineCaptions.app"
        guard esApp(r) else { continue }
        if versionDe(r) == version { return (r, "/Volumes/" + v) }
        if otra == nil { otra = r }
    }
    if let o = otra { return (o, volumen(o)) }
    return nil
}

// ---------------------------------------------------------------------------------------------------------------- avance
final class Avance: ObservableObject {
    @Published var paso = 0
    @Published var detalles = Array(repeating: [String](), count: NPASOS + 1)
    @Published var avisos = Array(repeating: "", count: NPASOS + 1)
    @Published var vivo = ""
    @Published var estado = "instalando"           // instalando | listo | error
    var appFinal: String? = nil                     // la ruta que instaló instalar.sh (FIN<TAB>versión<TAB>ruta): esa se abre
    @Published var mensaje = ""
    @Published var valor: Double = 0
    @Published var quedan: Double? = nil            // la cuenta atrás que se enseña (segundos), sin saltos; nil = aún sin estimar
    @Published var mbHecho: Double = 0
    @Published var mbTotal: Double = 0
    var tPaso = Date()
    var tEstado = Date()
    var copiado: Double = 0                         // (paso 1) lo copiado de la app, 0-1: el anillo lo sigue («Copiando… X de Y MB»)
    var tCopia0: Date? = nil
    var mb0: Double = 0
    private let rxPaso = try! NSRegularExpression(pattern: "([0-9])\\s*/\\s*[0-9]")
    private let rxMB = try! NSRegularExpression(pattern: "([0-9]+)[^0-9]+([0-9]+) MB")

    func evento(_ bruto: String) {
        guard estado == "instalando" else { return }
        let limpio = quitarANSI(bruto).trimmingCharacters(in: CharacterSet(charactersIn: "\r\n"))
        let partes = limpio.split(separator: "\t", maxSplits: 1, omittingEmptySubsequences: false)
        let tipo = partes.first.map { String($0) } ?? ""
        let texto = partes.count > 1 ? String(partes[1]).trimmingCharacters(in: .whitespaces) : ""
        switch tipo {
        case "PASO":
            var n = 0
            if let m = rxPaso.firstMatch(in: texto, range: NSRange(texto.startIndex..., in: texto)),
               let r = Range(m.range(at: 1), in: texto) { n = Int(texto[r]) ?? 0 }
            if n > paso { paso = n; tPaso = Date(); vivo = "" }
        case "OK":
            if !texto.isEmpty { detalles[paso].append(texto.replacingOccurrences(of: HOME, with: "~")) }
        case "AVISO":
            if !texto.isEmpty { avisos[paso] = texto }
        case "DETALLE":
            if !texto.isEmpty { vivo = texto }
            if paso == 1, let m = rxMB.firstMatch(in: texto, range: NSRange(texto.startIndex..., in: texto)),
               let r1 = Range(m.range(at: 1), in: texto), let r2 = Range(m.range(at: 2), in: texto),
               let hecho = Double(texto[r1]), let total = Double(texto[r2]), total > 0 {
                copiado = min(1, hecho / total)
                if tCopia0 == nil { tCopia0 = Date(); mb0 = hecho }
                mbHecho = hecho; mbTotal = total
            }
        case "FALLO":
            estado = "error"; mensaje = texto.isEmpty ? T("Algo salió mal.", "Something went wrong.") : texto; tEstado = Date()
        case "FIN":
            let campos = texto.split(separator: "\t", omittingEmptySubsequences: false)
            if campos.count > 1, campos[1].hasSuffix(".app") { appFinal = String(campos[1]) }
            estado = "listo"; tEstado = Date()
        default:
            break
        }
    }

    func objetivo() -> Double {
        if estado == "listo" { return 100 }
        let i = min(max(paso, 0), NPASOS)
        let (a, b) = TRAMOS[i]
        let k = Date().timeIntervalSince(tPaso)
        let tiempo = a + (b - a) * min(1, 0.9 * (1 - exp(-k / DURACION[i])))
        return i == 1 && copiado > 0 ? max(tiempo, a + (b - a) * 0.97 * copiado) : tiempo
    }

    // cuánto falta: copiar al ritmo medido (MB/s) + lo que tardan los pasos 3-7 (medido en Macs de GitHub: ~5 s en total)
    func estimacion() -> Double? {
        let resto = RESTO_S
        if paso == 1 {
            guard let t0 = tCopia0, mbTotal > 0 else { return nil }
            let k = Date().timeIntervalSince(t0)
            guard k >= 1, mbHecho > mb0 else { return nil }
            return (mbTotal - mbHecho) / ((mbHecho - mb0) / k) + resto
        }
        if paso >= 2 && paso <= NPASOS {
            let faltan = Double(NPASOS + 1 - paso) / Double(NPASOS - 1)        // (los pasos 2-6 se reparten el resto)
            return max(resto * (faltan - 0.2), resto * faltan - Date().timeIntervalSince(tPaso))
        }
        return nil
    }

    func avanzar(_ dt: Double) {
        let obj = objetivo()
        valor += (obj - valor) * min(1, dt * (estado == "listo" ? 5 : 2.4))
        // la cuenta atrás baja al ritmo del reloj y se corrige SIN saltos (memoria del autor: «exacta y sin saltos», como la de GO)
        guard estado == "instalando", let e = estimacion() else { if estado != "instalando" { quedan = nil }; return }
        guard var q = quedan else { quedan = e; return }
        q -= dt
        if e < q { q = max(e, q - dt * 2) } else if e > q + 1 { q += dt * 0.6 }
        quedan = max(0.5, q)
    }
}

// ---------------------------------------------------------------------------------------------------------------- vista
// v5.92 (el usuario eligió la propuesta B, «minimal»): compacta y centrada, 600 × 430. El anillo alrededor del logo ES el progreso; debajo,
// qué está haciendo (los MB mientras copia), el porcentaje grande con la cuenta atrás y seis puntos, uno por paso. Sin lista de pasos.
struct BotonPildora: ButtonStyle {
    var principal = true
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: principal ? .bold : .semibold))
            .foregroundColor(principal ? Color(hex: 0x05110c) : .white)
            .padding(.horizontal, 26).frame(height: 40)
            .background(
                Group {
                    if principal {
                        Capsule().fill(LinearGradient(colors: [VERDE, AGUA], startPoint: .leading, endPoint: .trailing))
                    } else {
                        Capsule().fill(Color.white.opacity(0.06)).overlay(Capsule().stroke(Color(hex: 0x24304a), lineWidth: 1))
                    }
                }
            )
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

let ANCHO: CGFloat = 600, ALTO: CGFloat = 430

struct VistaInstalador: View {
    @ObservedObject var av: Avance
    let version: String
    let icono: NSImage?
    let verRegistro: () -> Void
    let cerrar: () -> Void

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30.0)) { ctx in
            let t = ctx.date.timeIntervalSinceReferenceDate
            ZStack(alignment: .top) {
                // v6.02 (el usuario: «instaladores más modernos»): el degradado deja ver un poco el vidrio de macOS de detrás (NSVisualEffectView)
                LinearGradient(colors: [Color(hex: 0x10203f).opacity(0.86), Color(hex: 0x080c14).opacity(0.93)], startPoint: .topLeading, endPoint: UnitPoint(x: 0.75, y: 1))
                Ellipse()
                    .fill(RadialGradient(colors: [colorEstado.opacity(0.16 + 0.04 * sin(t * 1.6)), colorEstado.opacity(0)], center: .center,
                                         startRadius: 0, endRadius: 230))
                    .frame(width: 520, height: 420).offset(y: -140)
                VStack(spacing: 0) {
                    anillo(t).frame(width: 150, height: 150).padding(.top, 44)
                    titulo.padding(.top, 20)
                    detalle.padding(.top, 8).padding(.horizontal, 40)
                    cifra.padding(.top, 8)
                    puntos.padding(.top, 14)
                    Spacer(minLength: 0)
                    pie.padding(.bottom, 22)
                }
                .frame(width: ANCHO, height: ALTO)
            }
            .frame(width: ANCHO, height: ALTO)
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .circular))          // (v6.02: la misma curva que la máscara del vidrio: sin asomar 1 pt)
            .overlay(RoundedRectangle(cornerRadius: 24, style: .circular).stroke(colorBorde, lineWidth: 1.2))
        }
    }

    var colorEstado: Color { av.estado == "error" ? ROJO : VERDE }
    var colorBorde: Color {
        av.estado == "listo" ? VERDE.opacity(0.6) : (av.estado == "error" ? ROJO.opacity(0.6) : Color(hex: 0x24304a))
    }

    // ---- el logo dentro del anillo de progreso
    func anillo(_ t: Double) -> some View {
        let frac = av.estado == "listo" ? 1 : max(0.02, min(1, av.valor / 100))
        let colores: [Color] = av.estado == "error" ? [Color(hex: 0xc2444a), ROJO] : (av.estado == "listo" ? [VERDE, AGUA, VERDE] : [VERDE, AGUA, CIAN])
        let ang = (frac * 360 - 90) * .pi / 180
        return ZStack {
            Circle().stroke(Color.white.opacity(0.08), lineWidth: 5).frame(width: 145, height: 145)
            Circle().trim(from: 0, to: frac)
                .stroke(AngularGradient(gradient: Gradient(colors: colores), center: .center, startAngle: .degrees(0), endAngle: .degrees(360 * frac)),
                        style: StrokeStyle(lineWidth: 5, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .frame(width: 145, height: 145)
            if av.estado == "instalando" {                     // la punta, con brillo que late
                Circle().fill(VERDE).frame(width: 12, height: 12)
                    .shadow(color: AGUA.opacity(0.6 + 0.3 * sin(t * 4)), radius: 7)
                    .offset(x: cos(ang) * 72.5, y: sin(ang) * 72.5)
            }
            Group {
                if let icono = icono {
                    Image(nsImage: icono).resizable().interpolation(.high).frame(width: 88, height: 88)
                        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                }
            }
            .offset(y: av.estado == "instalando" ? sin(t * 1.7) * 2 : 0)
            if av.estado != "instalando" {
                Circle().fill(colorEstado).frame(width: 32, height: 32)
                    .overlay(Circle().stroke(Color(hex: 0x0b1324), lineWidth: 3))
                    .overlay(av.estado == "listo"
                             ? AnyView(Image(systemName: "checkmark").font(.system(size: 14, weight: .heavy)).foregroundColor(.white))
                             : AnyView(Text("!").font(.system(size: 19, weight: .black)).foregroundColor(.white)))
                    .offset(x: 40, y: 40)
            }
        }
    }

    // ---- textos
    var titulo: some View {
        Group {
            if av.estado == "listo" {
                Text(T("¡CineCaptions está listo!", "CineCaptions is ready!")).foregroundColor(TEXTO)
            } else if av.estado == "error" {
                Text(T("No se pudo instalar", "Could not install")).foregroundColor(TEXTO)
            } else {
                Text(T("Instalando ", "Installing ")).foregroundColor(TEXTO) + Text("Cine").foregroundColor(TEXTO)
                    + Text("Captions").foregroundColor(VERDE) + Text(" \(version)").foregroundColor(TEXTO)
            }
        }
        .font(.system(size: 24, weight: .bold)).lineLimit(1)
    }

    var detalle: some View {
        let texto: String
        var color = SUAVE
        if av.estado == "listo" {
            texto = T("Abriendo CineCaptions…", "Opening CineCaptions…"); color = VERDE
        } else if av.estado == "error" {
            texto = av.mensaje; color = ROJO
        } else if av.paso == 0 {
            texto = T("Preparando…", "Preparing…")
        } else if av.paso == 1 {
            texto = av.mbTotal > 0
                ? T("Copiando a Aplicaciones · \(Int(av.mbHecho)) de \(Int(av.mbTotal)) MB", "Copying to Applications · \(Int(av.mbHecho)) of \(Int(av.mbTotal)) MB")
                : (av.vivo.isEmpty ? T("Copiando a Aplicaciones…", "Copying to Applications…") : av.vivo)   // (la app de root: su servicio)
        } else if !av.avisos[av.paso].isEmpty {
            texto = PASOS[av.paso - 1] + " · " + av.avisos[av.paso]; color = AMBAR.opacity(0.9)
        } else {
            texto = PASOS[av.paso - 1]
        }
        return Text(texto).font(.system(size: 14, weight: .medium)).foregroundColor(color)
            .multilineTextAlignment(.center).lineLimit(2).frame(maxWidth: .infinity)
    }

    var cifra: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            if av.estado != "error" {
                Text("\(Int(av.valor.rounded())) %").font(.system(size: 40, weight: .bold)).monospacedDigit().foregroundColor(TEXTO)
                if av.estado == "instalando", let q = av.quedan {
                    Text(q < 1.5 ? T("casi listo", "almost done") : T("quedan \(Int(q.rounded(.up))) s", "\(Int(q.rounded(.up))) s left"))
                        .font(.system(size: 14, weight: .medium)).monospacedDigit().foregroundColor(AGUA)
                }
            }
        }
        .frame(height: 50)
    }

    var puntos: some View {
        HStack(spacing: 10) {
            ForEach(1...NPASOS, id: \.self) { i in
                let hecho = av.estado == "listo" || i < av.paso
                let actual = av.estado != "listo" && i == max(1, av.paso)
                Capsule()
                    .fill(actual ? (av.estado == "error" ? ROJO : VERDE) : (hecho ? VERDE.opacity(0.75) : SUAVE.opacity(0.35)))
                    .frame(width: actual ? 22 : 6, height: 6)
            }
        }
    }

    @ViewBuilder var pie: some View {
        if av.estado == "error" {
            HStack(spacing: 12) {
                Button(T("Ver registro", "Show log"), action: verRegistro).buttonStyle(BotonPildora(principal: false))
                Button(T("Cerrar", "Close"), action: cerrar).buttonStyle(BotonPildora(principal: true))
            }
        } else {
            Text(T("Sin contraseña  ·  Scripts de Resolve, tipografías y actualizaciones incluidas",
                   "No password  ·  Resolve scripts, fonts and updates included"))
                .font(.system(size: 12, weight: .medium)).foregroundColor(TENUE)
        }
    }
}

// ---------------------------------------------------------------------------------------------------------------- app
/// v6.02: la máscara del vidrio: un rectángulo redondeado que se estira sin deformar las esquinas.
func mascaraRedondeada(_ radio: CGFloat) -> NSImage {
    let lado = radio * 2 + 1
    let img = NSImage(size: NSSize(width: lado, height: lado), flipped: false) { r in
        NSColor.black.setFill()
        NSBezierPath(roundedRect: r, xRadius: radio, yRadius: radio).fill()
        return true
    }
    img.capInsets = NSEdgeInsets(top: radio, left: radio, bottom: radio, right: radio)
    img.resizingMode = .stretch
    return img
}

final class VentanaSinMarco: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

final class Instalador: NSObject, NSApplicationDelegate {
    let av = Avance()
    var ventana: NSWindow?
    var reloj: Timer?
    var proceso: Process?
    var rutaAvance = ""
    var rutaRegistro = ""
    var pos: UInt64 = 0
    var resto = Data()
    var antes = Date()
    var terminado = false
    var demo: [(Double, String)] = []
    var tDemo = Date()
    let args = CommandLine.arguments
    var esDemo: Bool { args.contains("--demo") || args.contains("--demo-error") }
    lazy var recursos = Bundle.main.resourcePath ?? "."
    lazy var version = (Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String) ?? "?"
    lazy var paquete = buscarPaquete(version)

    func applicationDidFinishLaunching(_ n: Notification) {
        // ya instalado (igual o más nuevo): solo se abre CineCaptions (y se expulsa el disco, que ya no hace falta)
        if !esDemo, let inst = versionInstalada(), let app = appInstalada(), numeroVersion(inst) >= numeroVersion(version) {
            av.estado = "listo"                         // (si no, applicationShouldTerminate no lo deja cerrarse: medido en GitHub)
            abrir(app)
            // sin esperar la confirmación de macOS (con algunas apps tarda o no llega: medido en GitHub)
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { self.expulsarDisco(); NSApp.terminate(nil) }
            return
        }
        let icono = NSImage(contentsOfFile: recursos + "/logo_cinecaptions.png") ?? NSApp.applicationIconImage
        let vista = VistaInstalador(av: av, version: version, icono: icono,
                                    verRegistro: { [weak self] in self?.verRegistro() },
                                    cerrar: { NSApp.terminate(nil) })
        let w = VentanaSinMarco(contentRect: NSRect(x: 0, y: 0, width: ANCHO, height: ALTO), styleMask: [.borderless],
                                backing: .buffered, defer: false)
        w.isOpaque = false
        w.backgroundColor = .clear
        w.hasShadow = true
        w.isMovableByWindowBackground = true
        w.title = T("Instalar CineCaptions", "Install CineCaptions")
        // v6.02: vidrio nativo de macOS (desenfoque de lo que hay detrás), recortado con las mismas esquinas continuas de 24 que la vista
        let vidrio = NSVisualEffectView(frame: NSRect(x: 0, y: 0, width: ANCHO, height: ALTO))
        vidrio.material = .hudWindow
        vidrio.blendingMode = .behindWindow
        vidrio.state = .active
        vidrio.maskImage = mascaraRedondeada(24)
        let host = NSHostingView(rootView: vista)
        host.frame = vidrio.bounds
        host.autoresizingMask = [.width, .height]
        vidrio.addSubview(host)
        w.contentView = vidrio
        w.center()
        w.makeKeyAndOrderFront(nil)
        ventana = w
        ponerMenu()
        NSApp.activate(ignoringOtherApps: true)
        if esDemo { empezarDemo() } else { empezar() }
        antes = Date()
        reloj = Timer.scheduledTimer(withTimeInterval: 1.0 / 30.0, repeats: true) { [weak self] _ in self?.tic() }
    }

    // ⌘Q (menú) se puede siempre: nunca queda nada a medias (instalar.sh, al recibir SIGTERM, borra la copia aún sin renombrar y la
    // instalada sigue como estaba). Antes se cancelaba y, con la ventana sin marco, solo quedaba «Forzar salida» (y no dejaba apagar)
    func applicationShouldTerminate(_ s: NSApplication) -> NSApplication.TerminateReply {
        if let p = proceso, p.isRunning { p.terminate() }
        return .terminateNow
    }

    func ponerMenu() {
        let barra = NSMenu()
        let item = NSMenuItem()
        barra.addItem(item)
        let menu = NSMenu()
        menu.addItem(withTitle: T("Salir de Instalar CineCaptions", "Quit Install CineCaptions"),
                     action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        item.submenu = menu
        NSApp.mainMenu = barra
    }

    // ---- la instalación de verdad: instalar.sh
    func empezar() {
        let fm = FileManager.default
        try? fm.createDirectory(atPath: HOME + "/DaVinciSubtitles", withIntermediateDirectories: true)
        rutaRegistro = HOME + "/DaVinciSubtitles/instalacion_mac.log"
        rutaAvance = NSTemporaryDirectory() + "cinecaptions_avance_\(ProcessInfo.processInfo.processIdentifier).txt"
        fm.createFile(atPath: rutaAvance, contents: Data())
        guard let origen = paquete?.app else {
            av.evento("FALLO\t" + T("No encuentro CineCaptions en el disco. Abre otra vez el .dmg que descargaste y haz doble clic en «Instalar CineCaptions».",
                                    "CineCaptions is not on the disk. Open the downloaded .dmg again and double-click «Install CineCaptions»."))
            return
        }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/bash")
        p.arguments = [recursos + "/instalar.sh"]
        var env = ProcessInfo.processInfo.environment
        env["CINECAPTIONS_ORIGEN"] = origen
        env["CINECAPTIONS_VERSION"] = version
        env["CINECAPTIONS_AVANCE"] = rutaAvance
        env["CINECAPTIONS_LOG"] = rutaRegistro
        env["CINECAPTIONS_IDIOMA"] = ES ? "es" : "en"
        p.environment = env
        p.standardInput = FileHandle.nullDevice
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        p.terminationHandler = { [weak self] proc in
            let st = proc.terminationStatus
            DispatchQueue.main.async { self?.termino(st) }
        }
        do {
            try p.run()
            proceso = p
        } catch {
            av.evento("FALLO\t" + T("No se pudo empezar la instalación: ", "The installation could not start: ") + error.localizedDescription)
        }
    }

    func leer() {
        guard !rutaAvance.isEmpty, let fh = FileHandle(forReadingAtPath: rutaAvance) else { return }
        defer { try? fh.close() }
        do { try fh.seek(toOffset: pos) } catch { return }
        let datos = fh.readDataToEndOfFile()
        if datos.isEmpty { return }
        pos += UInt64(datos.count)
        resto.append(datos)
        while let i = resto.firstIndex(of: 0x0A) {
            let linea = Data(resto[resto.startIndex..<i])
            resto = Data(resto[resto.index(after: i)...])
            av.evento(String(decoding: linea, as: UTF8.self))
        }
    }

    func termino(_ st: Int32) {
        leer()
        if av.estado == "instalando" {
            if st == 0 {
                av.evento("FIN\t")
            } else {
                av.evento("FALLO\t" + T("El instalador se detuvo antes de terminar (código \(st)). Ábrelo otra vez; si se repite, envíanos el registro.",
                                        "The installer stopped before finishing (code \(st)). Open it again; if it happens again, send us the log."))
            }
        }
    }

    func tic() {
        let ahora = Date()
        let dt = min(0.1, max(0, ahora.timeIntervalSince(antes)))
        antes = ahora
        if esDemo { alimentarDemo() } else { leer() }
        av.avanzar(dt)
        if av.estado == "listo" && !terminado && !esDemo {
            terminado = true
            abrirCineCaptionsYSalir()
        }
    }

    // ---- al terminar: CineCaptions YA (sin cuenta atrás), el instalador se cierra y el disco se expulsa
    func abrirCineCaptionsYSalir() {
        if let app = av.appFinal ?? appInstalada() {                 // (la que acaba de instalar: podía no ser la de /Applications)
            abrir(app)
        }
        expulsarDisco()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { NSApp.terminate(nil) }
    }

    // el disco del que vino, cuando este instalador ya se cerró (un proceso aparte que espera; si sigue ocupado, a la fuerza)
    func expulsarDisco() {
        guard let vol = paquete?.volumen ?? buscarPaquete(version)?.volumen, !CommandLine.arguments.contains("--sin-expulsar") else { return }
        let expulsar = Process()
        expulsar.executableURL = URL(fileURLWithPath: "/bin/sh")
        // (MEDIDO en macOS 26: con la ventana del disco abierta en el Finder, el primer intento sale «ocupado»: se insiste y al final a la fuerza)
        expulsar.arguments = ["-c", "sleep 2; for i in 1 2 3 4; do /usr/bin/hdiutil detach \"$1\" -quiet && exit 0; sleep 2; done; " +
                              "/usr/bin/hdiutil detach \"$1\" -force -quiet; exit 0", "expulsar", vol]
        expulsar.standardInput = FileHandle.nullDevice
        expulsar.standardOutput = FileHandle.nullDevice
        expulsar.standardError = FileHandle.nullDevice
        try? expulsar.run()
    }

    func verRegistro() {
        guard !rutaRegistro.isEmpty, let texto = try? String(contentsOfFile: rutaRegistro, encoding: .utf8) else { return }
        let limpio = (rutaRegistro as NSString).deletingPathExtension + "_para_leer.txt"
        try? quitarANSI(texto).write(toFile: limpio, atomically: true, encoding: .utf8)
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        p.arguments = ["-e", limpio]
        try? p.run()
    }

    // ---- simulación (--demo / --demo-error)
    func empezarDemo() {
        tDemo = Date()
        demo = [(0.0, "PASO\tPreparando"), (0.4, "PASO\t1/7  App"), (0.6, "DETALLE\t" + T("Copiando… 640 de 1256 MB", "Copying… 640 of 1256 MB")),
                (4.2, "OK\t/Applications/CineCaptions.app"), (4.4, "PASO\t2/7  Permiso"), (4.9, "OK\t" + T("Lista para abrir", "Ready to open")),
                (5.1, "PASO\t3/7  Scripts")]
        if args.contains("--demo-error") {
            demo.append((6.0, "FALLO\t" + T("No se pudieron copiar los scripts de DaVinci Resolve.", "The DaVinci Resolve scripts could not be copied.")))
        } else {
            demo += [(6.0, "OK\t" + T("14 scripts en el menú de Resolve", "14 scripts in the Resolve menu")), (6.2, "PASO\t4/7  Fuentes"),
                     (7.4, "OK\t" + T("21 tipografías", "21 fonts")), (7.6, "PASO\t5/7  Servicio"),
                     (8.4, "OK\t" + T("Cada hora, sin contraseña", "Every hour, no password")), (8.6, "PASO\t6/7  Dock"),
                     (9.2, "OK\t" + T("Fijado en el Dock", "Pinned to the Dock")), (9.4, "PASO\t7/7  Motor"),
                     (9.8, "OK\t" + T("Bajando en segundo plano", "Downloading in the background")), (10.2, "FIN\t\(version)")]
        }
    }

    func alimentarDemo() {
        let k = Date().timeIntervalSince(tDemo)
        while let e = demo.first, e.0 <= k {
            demo.removeFirst()
            av.evento(e.1)
        }
    }
}

@main
struct Principal {
    static func main() {
        let app = NSApplication.shared
        let delegado = Instalador()
        app.delegate = delegado
        app.setActivationPolicy(.regular)
        app.run()
    }
}
