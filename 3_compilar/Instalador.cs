// CineCaptions · By Cinema Productions
// 3_compilar/Instalador.cs — el instalador y desinstalador (C#, .NET Framework 4): pasos, banner, registro.
// Instalar_CineCaptions.exe
// ---------------------------------------------------------------------------
// Instalador con pasos a la vista. El programa compilado (PyInstaller) va PEGADO al final de este .exe como un .zip,
// seguido de 16 bytes: posicion del zip (Int64) + firma "CINECAP1". El mismo .exe SIN el zip es el desinstalador
// (<instalacion>\Desinstalar.exe /desinstalar).
//
// Se instala SOLO para el usuario (sin UAC): %LOCALAPPDATA%\Programs\CineCaptions.
// Lo que sabe hacer el programa (scripts de Resolve, tipografias, modelo de voz, autoprueba) se lo pide al .exe recien
// instalado con "--tarea <nombre> <estado.txt>" (tareas_instalador.py): una sola logica, la del programa.
//
// Opciones: /desinstalar  /silencioso  /dir=<carpeta>  /sinmodelo  /sinescritorio  /noabrir
//           /empezar (con ventana, sin esperar al boton)
//           /sinaccesos (sin accesos directos ni registro)  /sinlimpiar (no toca instalaciones anteriores)
// Se compila con Construir_Instalador.ps1 (csc.exe de .NET Framework 4, que ya viene con Windows).
// ---------------------------------------------------------------------------
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("Instalar CineCaptions")]
[assembly: AssemblyProduct("CineCaptions")]
[assembly: AssemblyDescription("Instalador de CineCaptions")]
[assembly: AssemblyCompany("Cinema Productions")]
[assembly: AssemblyCopyright("© 2026 Cinema Productions")]
[assembly: AssemblyVersion("__VERSION_ENSAMBLADO__")]
[assembly: AssemblyFileVersion("__VERSION_ENSAMBLADO__")]

static class Programa
{
    public const string Nombre = "CineCaptions";
    public const string ExePrograma = "CineCaptions.exe";
    public const string ClaveDesinstalar = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\CineCaptions";
    public const string Version = "__VERSION_APP__";

    [STAThread]
    static int Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Opciones op = Opciones.Leer(args);
        // Un proceso que arranca con su carpeta de trabajo DENTRO de la carpeta del programa impide renombrarla («está siendo utilizado en otro
        // proceso»). Pasa justo al actualizar desde el propio programa (v5.3.8): CineCaptions.exe corre con esa carpeta de trabajo (así lo dejan los accesos
        // directos) y el instalador que lanza la hereda. Se pasa a la carpeta temporal ANTES de hacer nada; la ruta de /dir se fija a absoluta antes.
        try
        {
            if (!string.IsNullOrEmpty(op.Dir)) op.Dir = Path.GetFullPath(op.Dir);
            Directory.SetCurrentDirectory(Path.GetTempPath());
        }
        catch { }
        Registro.EnTemp = op.Desinstalar;          // el registro del desinstalador NO va a DaVinciSubtitles (se recrearia la carpeta que se acaba de borrar)
        try
        {
            if (op.Desinstalar && !op.YaReubicado && DentroDe(Application.ExecutablePath, op.Dir))
                return ReubicarDesinstalador(op);
            if (!op.Desinstalar && !Paquete.Existe(Application.ExecutablePath))
            {
                MessageBox.Show("Este instalador está incompleto (no trae el programa). Descárgalo de nuevo.", Nombre,
                                MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 2;
            }
            if (op.Silencioso)
            {
                Instalacion ins = new Instalacion(op, null);
                ins.Correr();
                if (op.Desinstalar && op.YaReubicado)
                {
                    if (!ins.HuboError) Registro.Borrar();
                    AutoBorrar();
                }
                return ins.HuboError ? 1 : 0;
            }
            Ventana v = new Ventana(op);
            Application.Run(v);
            return v.CodigoSalida;
        }
        catch (Exception ex)
        {
            Registro.Escribir("ERROR inesperado: " + ex);
            if (!op.Silencioso)
                MessageBox.Show("No se pudo continuar:\r\n\r\n" + ex.Message + "\r\n\r\nDetalle en:\r\n" + Registro.Ruta, Nombre,
                                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    public static bool DentroDe(string archivo, string carpeta)
    {
        try
        {
            string a = Path.GetFullPath(archivo).TrimEnd('\\') + "\\";
            string c = Path.GetFullPath(carpeta).TrimEnd('\\') + "\\";
            return a.StartsWith(c, StringComparison.OrdinalIgnoreCase);
        }
        catch { return false; }
    }

    // El desinstalador vive DENTRO de la carpeta que va a borrar: se copia a %TEMP% y sigue desde ahi.
    static int ReubicarDesinstalador(Opciones op)
    {
        string copia = Path.Combine(Sitio.Temp, "cinecaptions_desinstalar_" + Guid.NewGuid().ToString("N").Substring(0, 8) + ".exe");
        File.Copy(Application.ExecutablePath, copia, true);
        ProcessStartInfo psi = new ProcessStartInfo(copia, op.ComoArgumentos() + " /reubicado");
        psi.UseShellExecute = false;
        Process.Start(psi);
        return 0;
    }

    // La copia del desinstalador en %TEMP% se borra sola cuando termina (despues de unos segundos, ya cerrado).
    public static void AutoBorrar()
    {
        try
        {
            string yo = Application.ExecutablePath;
            ProcessStartInfo psi = new ProcessStartInfo("cmd.exe", "/c ping 127.0.0.1 -n 4 > nul & del /f /q \"" + yo + "\"");
            psi.CreateNoWindow = true;
            psi.UseShellExecute = false;
            Process.Start(psi);
        }
        catch { }
    }
}

// ---------------------------------------------------------------------------
// Las carpetas y claves de registro que toca el programa, en UN sitio. Con la variable CINECAPTIONS_PRUEBA_RAIZ (solo para probar el instalador)
// todo se redirige a esa carpeta y a la clave Software\CineCaptionsPrueba, sin tocar el equipo de verdad.
static class Sitio
{
    public static string Prueba { get { return Environment.GetEnvironmentVariable("CINECAPTIONS_PRUEBA_RAIZ"); } }
    public static bool EsPrueba { get { return !string.IsNullOrEmpty(Prueba); } }
    public static string Usuario { get { return EsPrueba ? Path.Combine(Prueba, "usuario") : Environment.GetFolderPath(Environment.SpecialFolder.UserProfile); } }
    public static string Local { get { return EsPrueba ? Path.Combine(Usuario, @"AppData\Local") : Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData); } }
    public static string Roaming { get { return EsPrueba ? Path.Combine(Usuario, @"AppData\Roaming") : Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData); } }
    public static string MenuInicio { get { return EsPrueba ? Path.Combine(Roaming, @"Microsoft\Windows\Start Menu\Programs") : Environment.GetFolderPath(Environment.SpecialFolder.Programs); } }
    public static string Escritorio { get { return EsPrueba ? Path.Combine(Usuario, "Desktop") : Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory); } }
    public static string Documentos { get { return EsPrueba ? Path.Combine(Usuario, "Documents") : Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments); } }
    public static string ProgramData { get { return EsPrueba ? Path.Combine(Prueba, "programdata") : Environment.GetEnvironmentVariable("PROGRAMDATA") ?? @"C:\ProgramData"; } }
    public static string Temp
    {
        get
        {
            if (!EsPrueba) return Path.GetTempPath();
            string t = Path.Combine(Prueba, "temp");
            try { Directory.CreateDirectory(t); } catch { }
            return t + "\\";
        }
    }
    public static string DatosUsuario { get { return Path.Combine(Usuario, "DaVinciSubtitles"); } }
    public static string Fuentes { get { return Path.Combine(Local, @"Microsoft\Windows\Fonts"); } }
    public static string CacheModelos
    {
        get
        {
            string hub = EsPrueba ? null : Environment.GetEnvironmentVariable("HF_HUB_CACHE");
            if (string.IsNullOrEmpty(hub))
            {
                string home = EsPrueba ? null : Environment.GetEnvironmentVariable("HF_HOME");
                if (string.IsNullOrEmpty(home)) home = Path.Combine(Usuario, @".cache\huggingface");
                hub = Path.Combine(home, "hub");
            }
            return hub;
        }
    }
    public static RegistryKey RaizRegistro()
    {
        if (EsPrueba) return Registry.CurrentUser.CreateSubKey(@"Software\CineCaptionsPrueba");
        return Registry.CurrentUser;
    }
}

// ---------------------------------------------------------------------------
// Borrado a fondo: rutas largas (PyTorch las tiene), solo lectura, enlaces, procesos que sostienen archivos, y lo que no se pueda borrar ahora
// se deja programado para el proximo inicio de sesion (RunOnce de HKCU, sin administrador).
static class Borrado
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct WIN32_FIND_DATA
    {
        public uint dwFileAttributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME ftCreationTime, ftLastAccessTime, ftLastWriteTime;
        public uint nFileSizeHigh, nFileSizeLow, dwReserved0, dwReserved1;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string cFileName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 14)] public string cAlternateFileName;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr FindFirstFileW(string nombre, out WIN32_FIND_DATA datos);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool FindNextFileW(IntPtr h, out WIN32_FIND_DATA datos);
    [DllImport("kernel32.dll")] static extern bool FindClose(IntPtr h);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool DeleteFileW(string n);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool RemoveDirectoryW(string n);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool SetFileAttributesW(string n, uint a);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern uint GetFileAttributesW(string n);
    [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr OpenProcess(uint acceso, bool heredar, int pid);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool QueryFullProcessImageNameW(IntPtr h, int flags, StringBuilder sb, ref int tam);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [DllImport("user32.dll", SetLastError = true)] static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam, uint flags, uint timeout, out IntPtr resultado);

    const uint INVALIDO = 0xFFFFFFFF, DIRECTORIO = 0x10, ENLACE = 0x400;

    // \\?\ delante: sin el limite de 260 caracteres
    public static string Largo(string p)
    {
        if (p.StartsWith(@"\\?\")) return p;
        if (p.StartsWith(@"\\")) return @"\\?\UNC\" + p.Substring(2);
        return @"\\?\" + p;
    }

    public static bool Existe(string ruta) { return GetFileAttributesW(Largo(ruta.TrimEnd('\\'))) != INVALIDO; }

    /// Borra un archivo o una carpeta entera. Devuelve true si ya no existe.
    public static bool Arbol(string ruta, Action<string> log)
    {
        string r = Largo(ruta.TrimEnd('\\'));
        uint a = GetFileAttributesW(r);
        if (a == INVALIDO) return true;
        if ((a & DIRECTORIO) == 0) return UnArchivo(r, log);
        if ((a & ENLACE) != 0) return Quitar(r, true, log);              // un enlace/junction: se quita el enlace, nunca su contenido
        for (int vuelta = 0; vuelta < 3; vuelta++)
        {
            Contenido(r, log);
            if (Quitar(r, true, log)) return true;
            Thread.Sleep(500);
        }
        if (GetFileAttributesW(r) == INVALIDO) return true;
        try                                                              // ultimo recurso: el propio Windows
        {
            ProcessStartInfo psi = new ProcessStartInfo("cmd.exe", "/c rd /s /q \"" + r + "\"");
            psi.CreateNoWindow = true; psi.UseShellExecute = false;
            Process p = Process.Start(psi);
            p.WaitForExit(120000);
        }
        catch { }
        return GetFileAttributesW(r) == INVALIDO;
    }

    static void Contenido(string r, Action<string> log)
    {
        List<string> carpetas = new List<string>(), archivos = new List<string>(), enlaces = new List<string>();
        WIN32_FIND_DATA d;
        IntPtr h = FindFirstFileW(r + @"\*", out d);
        if (h == new IntPtr(-1)) return;
        try
        {
            do
            {
                if (d.cFileName == "." || d.cFileName == "..") continue;
                string completa = r + "\\" + d.cFileName;
                if ((d.dwFileAttributes & DIRECTORIO) != 0) { if ((d.dwFileAttributes & ENLACE) != 0) enlaces.Add(completa); else carpetas.Add(completa); }
                else archivos.Add(completa);
            } while (FindNextFileW(h, out d));
        }
        finally { FindClose(h); }
        foreach (string f in archivos) UnArchivo(f, log);
        foreach (string e in enlaces) Quitar(e, true, log);
        foreach (string c in carpetas) { Contenido(c, log); Quitar(c, true, log); }
    }

    static bool UnArchivo(string r, Action<string> log)
    {
        for (int i = 0; i < 4; i++)
        {
            SetFileAttributesW(r, 0x80);                                   // quita solo-lectura / oculto / sistema
            if (DeleteFileW(r)) return true;
            if (GetFileAttributesW(r) == INVALIDO) return true;
            int err = Marshal.GetLastWin32Error();
            if (i == 3 && log != null) log("No pude borrar " + r.Replace(@"\\?\", "") + " (error " + err + ")");
            Thread.Sleep(300);
        }
        return false;
    }

    static bool Quitar(string r, bool dir, Action<string> log)
    {
        for (int i = 0; i < 3; i++)
        {
            SetFileAttributesW(r, 0x80);
            if (RemoveDirectoryW(r) || GetFileAttributesW(r) == INVALIDO) return true;
            Thread.Sleep(250);
        }
        return false;
    }

    // ---- procesos ------------------------------------------------------------------------
    public static string RutaDe(Process p)
    {
        IntPtr h = IntPtr.Zero;
        try
        {
            h = OpenProcess(0x1000, false, p.Id);                         // PROCESS_QUERY_LIMITED_INFORMATION
            if (h == IntPtr.Zero) return null;
            StringBuilder sb = new StringBuilder(1024);
            int tam = sb.Capacity;
            return QueryFullProcessImageNameW(h, 0, sb, ref tam) ? sb.ToString() : null;
        }
        catch { return null; }
        finally { if (h != IntPtr.Zero) CloseHandle(h); }
    }

    /// Cierra todo proceso cuyo ejecutable viva dentro de esas carpetas (el programa, sus motores de voz / IA, lo que sostenga archivos). Devuelve cuantos.
    public static int CerrarEn(List<string> carpetas, Action<string> log, string excepto)
    {
        int n = 0;
        int yo = Process.GetCurrentProcess().Id;
        foreach (Process p in Process.GetProcesses())
        {
            try
            {
                if (p.Id == yo) continue;
                string ruta = RutaDe(p);
                if (ruta == null) continue;
                if (excepto != null && string.Equals(ruta, excepto, StringComparison.OrdinalIgnoreCase)) continue;
                bool nuestro = false;
                foreach (string c in carpetas) if (Programa.DentroDe(ruta, c)) { nuestro = true; break; }
                if (!nuestro) continue;
                if (log != null) log("Cerrando " + p.ProcessName + " (pid " + p.Id + ") de " + Path.GetDirectoryName(ruta));
                try { p.Kill(); p.WaitForExit(6000); n++; } catch (Exception ex) { if (log != null) log("No pude cerrar pid " + p.Id + ": " + ex.Message); }
            }
            catch { }
            finally { try { p.Dispose(); } catch { } }
        }
        return n;
    }

    // ---- lo que no se pudo borrar ahora: al proximo inicio de sesion ----------------------
    public static bool ProgramarBorrado(List<string> rutas, Action<string> log)
    {
        if (rutas.Count == 0) return true;
        try
        {
            StringBuilder sb = new StringBuilder("cmd.exe /c ");
            for (int i = 0; i < rutas.Count; i++)
            {
                string r = rutas[i].TrimEnd('\\');
                if (i > 0) sb.Append(" & ");
                sb.Append("(rd /s /q \"" + r + "\" 2>nul & del /f /q \"" + r + "\" 2>nul)");
            }
            using (RegistryKey k = Sitio.RaizRegistro().CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\RunOnce"))
                k.SetValue("CineCapsLimpieza", sb.ToString());
            if (log != null) log("Quedaron " + rutas.Count + " elemento/s en uso: se borrarán solos al iniciar sesión de nuevo.");
            return true;
        }
        catch (Exception ex) { if (log != null) log("No pude programar el borrado: " + ex.Message); return false; }
    }

    // ---- registro de Windows: lo que el propio Windows apunta de un .exe ---------------------------
    static readonly string[] ClavesRastros = new string[] {
        @"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store",
        @"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers",
        @"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache",
        @"Software\Microsoft\Windows\ShellNoRoam\MUICache",
        @"Software\Microsoft\Windows\CurrentVersion\Explorer\FeatureUsage\AppSwitched",
        @"Software\Microsoft\Windows\CurrentVersion\Explorer\FeatureUsage\AppLaunch",
        @"Software\Microsoft\Windows\CurrentVersion\Search\JumplistData",
        @"Software\Microsoft\Windows\CurrentVersion\RunOnce",
        @"Software\Microsoft\Windows\CurrentVersion\Run"
    };

    /// Quita las entradas cuyo nombre o valor apunta a esas carpetas / archivos, y las claves propias de nuestros .exe. Devuelve cuantas.
    public static int LimpiarRastros(List<string> prefijos, Action<string> log)
    {
        int n = 0;
        RegistryKey raiz = Sitio.RaizRegistro();
        foreach (string clave in ClavesRastros)
        {
            try
            {
                using (RegistryKey k = raiz.OpenSubKey(clave, true))
                {
                    if (k == null) continue;
                    foreach (string nombre in k.GetValueNames())
                    {
                        if (nombre == "CineCapsLimpieza") continue;           // la limpieza programada se queda hasta que corra
                        string dato = "";
                        try { object v = k.GetValue(nombre); dato = v == null ? "" : (v is string[] ? string.Join(" ", (string[])v) : v.ToString()); } catch { }
                        bool es = false;
                        foreach (string p in prefijos)
                            if (p.Length > 3 && (nombre.IndexOf(p, StringComparison.OrdinalIgnoreCase) >= 0 || dato.IndexOf(p, StringComparison.OrdinalIgnoreCase) >= 0)) { es = true; break; }
                        if (es) { try { k.DeleteValue(nombre, false); n++; if (log != null) log("Registro: quitado " + clave + "\\" + nombre); } catch { } }
                    }
                }
            }
            catch { }
        }
        foreach (string clave in new string[] { @"Software\Classes\Applications\CineCaptions.exe", @"Software\Classes\Applications\Desinstalar.exe" })
        {
            try
            {
                using (RegistryKey k = raiz.OpenSubKey(clave))
                {
                    if (k == null) continue;
                    object abrir = null;
                    try { using (RegistryKey c = k.OpenSubKey(@"shell\open\command")) { if (c != null) abrir = c.GetValue(""); } } catch { }
                    bool nuestro = abrir == null;                            // sin comando: es solo la marca de «abrir con»
                    if (!nuestro) foreach (string p in prefijos) if (abrir.ToString().IndexOf(p, StringComparison.OrdinalIgnoreCase) >= 0) nuestro = true;
                    if (!nuestro) continue;
                }
                raiz.DeleteSubKeyTree(clave, false); n++;
                if (log != null) log("Registro: quitada la clave " + clave);
            }
            catch { }
        }
        return n;
    }

    public static void AvisarFuentes()
    {
        try { IntPtr r; SendMessageTimeout(new IntPtr(0xFFFF), 0x1D, IntPtr.Zero, IntPtr.Zero, 2, 1500, out r); } catch { }       // WM_FONTCHANGE
    }
}

// ---------------------------------------------------------------------------
class Opciones
{
    public bool Desinstalar, Silencioso, SinModelo, SinEscritorio, NoAbrir, SinAccesos, SinLimpiar, YaReubicado, Empezar;
    public bool BorrarDatos, BorrarModelos;      // al desinstalar: tambien tus datos / licencia y los modelos descargados (/borrardatos /borrarmodelos /todo)
    public string Dir;

    public static string DirPorDefecto()
    {
        return Path.Combine(Sitio.Local, @"Programs\" + Programa.Nombre);
    }

    public static Opciones Leer(string[] args)
    {
        Opciones o = new Opciones();
        o.Dir = null;
        foreach (string a0 in args)
        {
            string a = a0.Trim();
            string l = a.ToLowerInvariant().TrimStart('/', '-');
            if (l == "desinstalar" || l == "uninstall") o.Desinstalar = true;
            else if (l == "silencioso" || l == "silent" || l == "s") o.Silencioso = true;
            else if (l == "sinmodelo") o.SinModelo = true;
            else if (l == "sinescritorio") o.SinEscritorio = true;
            else if (l == "noabrir") o.NoAbrir = true;
            else if (l == "sinaccesos") o.SinAccesos = true;
            else if (l == "sinlimpiar") o.SinLimpiar = true;
            else if (l == "reubicado") o.YaReubicado = true;
            else if (l == "empezar") o.Empezar = true;
            else if (l == "borrardatos") o.BorrarDatos = true;
            else if (l == "borrarmodelos") o.BorrarModelos = true;
            else if (l == "todo") { o.BorrarDatos = true; o.BorrarModelos = true; }
            else if (l.StartsWith("dir=")) o.Dir = a.Substring(a.IndexOf('=') + 1).Trim().Trim('"');
        }
        if (string.IsNullOrEmpty(o.Dir))
        {
            o.Dir = DirPorDefecto();
            if (o.Desinstalar)
            {
                // Desinstalar.exe vive en la carpeta instalada; si no, la que diga el registro
                string propia = Path.GetDirectoryName(Application.ExecutablePath);
                string reg = Registro.LeerHKCU(Programa.ClaveDesinstalar, "InstallLocation");
                if (File.Exists(Path.Combine(propia, Programa.ExePrograma))) o.Dir = propia;
                else if (!string.IsNullOrEmpty(reg)) o.Dir = reg;
            }
        }
        return o;
    }

    public string ComoArgumentos()
    {
        StringBuilder sb = new StringBuilder();
        if (Desinstalar) sb.Append(" /desinstalar");
        if (Silencioso) sb.Append(" /silencioso");
        if (SinAccesos) sb.Append(" /sinaccesos");
        if (Empezar) sb.Append(" /empezar");
        if (BorrarDatos) sb.Append(" /borrardatos");
        if (BorrarModelos) sb.Append(" /borrarmodelos");
        sb.Append(" \"/dir=" + Dir + "\"");
        return sb.ToString().Trim();
    }
}

// ---------------------------------------------------------------------------
static class Registro
{
    static readonly object cerrojo = new object();
    static string ruta;
    public static bool EnTemp;          // al desinstalar: el log va a %TEMP% (y se borra al terminar bien)

    public static string Ruta
    {
        get
        {
            if (ruta == null)
            {
                string d;
                try
                {
                    if (EnTemp) d = Sitio.Temp;
                    else
                    {
                        d = Path.Combine(Sitio.DatosUsuario, "instalador");
                        Directory.CreateDirectory(d);
                    }
                }
                catch { d = Path.GetTempPath(); }
                ruta = Path.Combine(d, (EnTemp ? "cinecaptions_desinstalar_" : "instalador_") + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".log");
            }
            return ruta;
        }
    }

    /// Borra el archivo de registro (cuando todo salio bien y no debe quedar ni el log).
    public static void Borrar()
    {
        lock (cerrojo)
        {
            try { if (ruta != null && File.Exists(ruta)) File.Delete(ruta); } catch { }
        }
    }

    public static void Escribir(string texto)
    {
        lock (cerrojo)
        {
            try { File.AppendAllText(Ruta, DateTime.Now.ToString("HH:mm:ss") + "  " + texto + Environment.NewLine, Encoding.UTF8); }
            catch { }
        }
    }

    public static string LeerHKCU(string clave, string valor)
    {
        try
        {
            using (RegistryKey k = Sitio.RaizRegistro().OpenSubKey(clave))
            {
                if (k == null) return null;
                object v = k.GetValue(valor);
                return v == null ? null : v.ToString();
            }
        }
        catch { return null; }
    }
}

// ---------------------------------------------------------------------------
// El zip pegado al final del .exe
static class Paquete
{
    const string Firma = "CINECAP1";

    sealed class Tramo : Stream
    {
        readonly Stream s; readonly long ini, largo; long pos;
        public Tramo(Stream s, long ini, long largo) { this.s = s; this.ini = ini; this.largo = largo; }
        public override bool CanRead { get { return true; } }
        public override bool CanSeek { get { return true; } }
        public override bool CanWrite { get { return false; } }
        public override long Length { get { return largo; } }
        public override long Position { get { return pos; } set { pos = value; } }
        public override int Read(byte[] b, int o, int n)
        {
            long resto = largo - pos;
            if (resto <= 0) return 0;
            if (n > resto) n = (int)resto;
            s.Position = ini + pos;
            int r = s.Read(b, o, n);
            pos += r;
            return r;
        }
        public override long Seek(long o, SeekOrigin origen)
        {
            if (origen == SeekOrigin.Begin) pos = o; else if (origen == SeekOrigin.Current) pos += o; else pos = largo + o;
            return pos;
        }
        public override void Flush() { }
        public override void SetLength(long v) { throw new NotSupportedException(); }
        public override void Write(byte[] b, int o, int n) { throw new NotSupportedException(); }
    }

    public static bool Existe(string exe)
    {
        try
        {
            using (FileStream fs = new FileStream(exe, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                if (fs.Length < 16) return false;
                byte[] pie = new byte[16];
                fs.Seek(-16, SeekOrigin.End);
                fs.Read(pie, 0, 16);
                return Encoding.ASCII.GetString(pie, 8, 8) == Firma;
            }
        }
        catch { return false; }
    }

    public static ZipArchive Abrir(FileStream fs)
    {
        byte[] pie = new byte[16];
        fs.Seek(-16, SeekOrigin.End);
        fs.Read(pie, 0, 16);
        if (Encoding.ASCII.GetString(pie, 8, 8) != Firma) throw new Exception("El instalador está incompleto. Descárgalo de nuevo.");
        long ini = BitConverter.ToInt64(pie, 0);
        return new ZipArchive(new Tramo(fs, ini, fs.Length - 16 - ini), ZipArchiveMode.Read);
    }
}

// ---------------------------------------------------------------------------
enum EstadoPaso { Pendiente, EnCurso, Hecho, Aviso, Error, Omitido }

class Paso
{
    public string Titulo;              // en la lista de PASOS (corto)
    public string Accion;              // titulo grande de la derecha mientras corre ("Copiando el programa...")
    public string Detalle = "";
    public EstadoPaso Estado = EstadoPaso.Pendiente;
    public int Progreso = -1;          // 0-100 dentro del paso, -1 = sin dato
    public double Peso = 1;            // cuanto pesa en la barra general
    public Paso(string t, string accion, double peso) { Titulo = t; Accion = accion; Peso = peso; }
}

// ---------------------------------------------------------------------------
// La instalacion / desinstalacion en si. Corre en un hilo; avisa a la ventana por eventos.
class Instalacion
{
    readonly Opciones op;
    readonly Ventana ventana;
    public readonly List<Paso> Pasos = new List<Paso>();
    public bool HuboError, HuboAviso;
    public string Resumen = "";
    public readonly List<string> Avisos = new List<string>();
    volatile Process tareaActual;
    volatile bool omitirModelo;

    Paso pPreparar, pCopiar, pVerificar, pScripts, pFuentes, pModelo, pMotorIA, pAccesos;
    Paso dCerrar, dLicencia, dScripts, dFuentes, dAccesos, dArchivos, dDatos, dRastros;

    public bool DescargarModelo = true, AccesoEscritorio = true;

    public Instalacion(Opciones op, Ventana v)
    {
        this.op = op;
        ventana = v;
        DescargarModelo = !op.SinModelo;
        AccesoEscritorio = !op.SinEscritorio;
        if (op.Desinstalar)
        {
            dCerrar = Nuevo("Cerrar el programa y sus motores", "Cerrando el programa y sus motores...", 1);
            dLicencia = Nuevo("Liberar la licencia de este equipo", "Liberando la licencia...", 1);
            dScripts = Nuevo("Scripts del menú de DaVinci Resolve", "Quitando los scripts de Resolve...", 1);
            dFuentes = Nuevo("Tipografías de las plantillas", "Quitando las tipografías...", 1);
            dAccesos = Nuevo("Accesos directos y registro", "Quitando los accesos directos...", 1);
            dArchivos = Nuevo("Programa y motor de voz e IA", "Borrando los archivos del programa...", 4);
            dDatos = Nuevo("Tus datos y modelos descargados", "Borrando tus datos y modelos...", 4);
            dRastros = Nuevo("Rastros y comprobación final", "Comprobando que no quede nada...", 1);
        }
        else
        {
            pPreparar = Nuevo("Preparar el equipo", "Preparando el equipo...", 1);
            pCopiar = Nuevo("Programa CineCaptions", "Copiando el programa...", 10);
            pVerificar = Nuevo("Comprobar que funciona en este equipo", "Comprobando que todo funciona...", 2);
            pScripts = Nuevo("Scripts de DaVinci Resolve", "Instalando los scripts en Resolve...", 1);
            pFuentes = Nuevo("Tipografías de las plantillas", "Instalando las tipografías...", 1);
            pModelo = Nuevo("Voz de respaldo: Whisper turbo (1,6 GB)", "Descargando el modelo de voz...", 8);
            pMotorIA = Nuevo("Motor de voz e IA: Qwen3 (4-15 GB)", "Instalando Qwen3-ASR y la IA de texto...", 20);
            pAccesos = Nuevo("Accesos directos", "Creando los accesos directos...", 1);
        }
    }

    Paso Nuevo(string t, string accion, double peso) { Paso p = new Paso(t, accion, peso); Pasos.Add(p); return p; }

    // ---- avisos a la ventana -------------------------------------------------
    void Cambio(Paso p) { if (ventana != null) ventana.PasoCambiado(p); }
    void Log(string texto)
    {
        Registro.Escribir(texto);
        if (ventana != null) ventana.AgregarLog(texto);
    }
    void Empezar(Paso p, string detalle) { p.Estado = EstadoPaso.EnCurso; p.Detalle = detalle; p.Progreso = -1; Log(">> " + p.Titulo); Cambio(p); }
    void Detalle(Paso p, string detalle, int pct) { p.Detalle = detalle; p.Progreso = pct; Cambio(p); }
    void Terminar(Paso p, EstadoPaso e, string detalle)
    {
        if (p.Estado == EstadoPaso.Pendiente) Log(">> " + p.Titulo);
        p.Estado = e; p.Detalle = detalle; p.Progreso = 100;
        if (e == EstadoPaso.Error) HuboError = true;
        if (e == EstadoPaso.Aviso) { HuboAviso = true; Avisos.Add(p.Titulo + ": " + detalle); }
        if (e == EstadoPaso.Error) Avisos.Add(p.Titulo + ": " + detalle);
        Log("   " + e + ": " + detalle);
        Cambio(p);
    }

    public string ExeInstalado { get { return Path.Combine(op.Dir, Programa.ExePrograma); } }
    public bool DescargandoModelo { get { return (pModelo != null && pModelo.Estado == EstadoPaso.EnCurso) || (pMotorIA != null && pMotorIA.Estado == EstadoPaso.EnCurso); } }

    public void OmitirDescarga()
    {
        omitirModelo = true;
        Process t = tareaActual;
        try { if (t != null && !t.HasExited) t.Kill(); } catch { }
    }

    // ==========================================================================
    public void Correr()
    {
        Log("=== " + (op.Desinstalar ? "Desinstalacion" : "Instalacion") + " de " + Programa.Nombre + " " + Programa.Version + " ===");
        Log("Carpeta: " + op.Dir + " | Windows " + Environment.OSVersion.Version + (Environment.Is64BitOperatingSystem ? " x64" : " x86"));
        try
        {
            if (op.Desinstalar) Desinstalar(); else Instalar();
        }
        catch (Exception ex)
        {
            HuboError = true;
            Log("ERROR: " + ex);
            foreach (Paso p in Pasos)
                if (p.Estado == EstadoPaso.EnCurso) Terminar(p, EstadoPaso.Error, ex.Message);
            Resumen = ex.Message;
        }
        Log("=== Fin: " + (HuboError ? "con errores" : HuboAviso ? "con avisos" : "OK") + " ===");
    }

    // ==========================================================================
    void Instalar()
    {
        // 1) equipo ---------------------------------------------------------------
        Empezar(pPreparar, "Revisando Windows y el espacio libre");
        if (!Environment.Is64BitOperatingSystem)
            throw new Exception("CineCaptions necesita Windows 10 u 11 de 64 bits.");
        long tamPrograma = 0;
        using (FileStream fs = new FileStream(Application.ExecutablePath, FileMode.Open, FileAccess.Read, FileShare.Read))
        using (ZipArchive zip = Paquete.Abrir(fs))
            foreach (ZipArchiveEntry e in zip.Entries) tamPrograma += e.Length;
        long libre = EspacioLibre(op.Dir);
        long margen = 200L * 1024 * 1024;
        if (libre >= 0 && libre < tamPrograma + margen)
            throw new Exception(string.Format("No hay espacio suficiente en el disco: hacen falta {0:N0} MB y quedan {1:N0} MB libres.",
                                              (tamPrograma + margen) / 1048576, libre / 1048576));
        if (DescargarModelo && ModeloYaDescargado())
        {
            DescargarModelo = false;
            pModelo.Titulo = "Modelo de voz (Whisper)";
        }
        if (DescargarModelo && libre >= 0 && libre < tamPrograma + margen + 1700L * 1048576)
        {
            DescargarModelo = false;
            Avisos.Add("No hay espacio para descargar ahora el modelo de voz (1,5 GB): se descargará la primera vez que transcribas.");
        }
        Detalle(pPreparar, "Cerrando CineCaptions si estaba abierto", -1);
        int cerrados = CerrarPrograma();
        string notas = cerrados > 0 ? "Se cerró el programa que estaba abierto. " : "";
        Terminar(pPreparar, EstadoPaso.Hecho, (notas + string.Format("Windows de 64 bits, {0:N1} GB libres.", libre / 1073741824.0)).Trim());

        // 2) copiar -----------------------------------------------------------------
        Empezar(pCopiar, "Abriendo el paquete");
        CopiarPrograma(tamPrograma);

        // 3) autoprueba ---------------------------------------------------------------
        Empezar(pVerificar, "Cargando cada parte del programa");
        Tarea(pVerificar, "verificar", 300, EstadoPaso.Error);

        // 4) scripts de Resolve ---------------------------------------------------------
        Empezar(pScripts, "Buscando DaVinci Resolve");
        Tarea(pScripts, "scripts", 180, EstadoPaso.Aviso);

        // 5) tipografias -------------------------------------------------------------
        Empezar(pFuentes, "Revisando las tipografías");
        Tarea(pFuentes, "fuentes", 300, EstadoPaso.Aviso);

        // 6) modelo de voz -------------------------------------------------------------
        if (!DescargarModelo)
        {
            if (ModeloYaDescargado()) Terminar(pModelo, EstadoPaso.Hecho, "Ya estaba en este equipo");
            else Terminar(pModelo, EstadoPaso.Omitido, "Se descargará la primera vez que transcribas");
        }
        else
        {
            Empezar(pModelo, "Conectando con huggingface.co");
            if (ventana != null) ventana.MostrarOmitir(true);
            Tarea(pModelo, "modelo", 4 * 3600, EstadoPaso.Aviso);
            if (ventana != null) ventana.MostrarOmitir(false);
        }

        // 6b) v5.1: el motor de voz e IA (Qwen3-ASR + IA de texto) -----------------------
        // va en su propio Python 3.12 (lo instala el programa: --tarea motor_ia). Si
        // falla o se omite, CineCaptions funciona igual con Whisper.
        if (op.SinModelo)
        {
            Terminar(pMotorIA, EstadoPaso.Omitido, "Omitido (/sinmodelo): se instala desde Ajustes > General");
        }
        else if (MotorIAYaInstalado())
        {
            // v5.2 (pedido: «que revise si las IAs ya están instaladas y no haga ese paso»)
            pMotorIA.Titulo = "Motor de voz e IA: Qwen3";
            Terminar(pMotorIA, EstadoPaso.Hecho, "Ya estaba instalado en este equipo");
        }
        else
        {
            omitirModelo = false;
            Empezar(pMotorIA, "Preparando el motor (Python 3.12 + PyTorch)");
            if (ventana != null) ventana.MostrarOmitir(true);
            Tarea(pMotorIA, "motor_ia", 6 * 3600, EstadoPaso.Aviso);
            if (ventana != null) ventana.MostrarOmitir(false);
        }

        // 7) accesos directos, desinstalador, limpieza ------------------------------------
        Empezar(pAccesos, "Menú Inicio");
        if (op.SinAccesos)
        {
            Terminar(pAccesos, EstadoPaso.Omitido, "Omitido (/sinaccesos)");
        }
        else
        {
            List<string> hechos = new List<string>();
            string exe = ExeInstalado;
            string menu = Sitio.MenuInicio;
            CrearAcceso(Path.Combine(menu, Programa.Nombre + ".lnk"), exe, op.Dir);
            hechos.Add("Menú Inicio");
            BorrarCarpetaSiExiste(Path.Combine(menu, Programa.Nombre));        // la del Setup original (subcarpeta)
            string esc = Path.Combine(Sitio.Escritorio, Programa.Nombre + ".lnk");
            if (AccesoEscritorio) { CrearAcceso(esc, exe, op.Dir); hechos.Add("Escritorio"); }
            else if (File.Exists(esc) && ApuntaAInstalacionVieja(esc)) BorrarArchivo(esc);
            Detalle(pAccesos, "Registrando el desinstalador", -1);
            RegistrarDesinstalador();
            hechos.Add("Agregar o quitar programas");
            Terminar(pAccesos, EstadoPaso.Hecho, string.Join(" · ", hechos.ToArray()));
        }

        Resumen = HuboError
            ? "Se instaló, pero algo no funciona en este equipo. Mira los detalles."
            : "Listo. Ya puedes usar CineCaptions.";
    }

    // ---- 1) ------------------------------------------------------------------------
    static long EspacioLibre(string dir)
    {
        try { return new DriveInfo(Path.GetPathRoot(Path.GetFullPath(dir))).AvailableFreeSpace; }
        catch { return -1; }
    }

    public static long LibreEn(string dir) { return EspacioLibre(dir); }

    public static long TamanoPrograma()
    {
        try
        {
            long total = 0;
            using (FileStream fs = new FileStream(Application.ExecutablePath, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (ZipArchive zip = Paquete.Abrir(fs))
                foreach (ZipArchiveEntry e in zip.Entries) total += e.Length;
            return total;
        }
        catch { return 0; }
    }

    static string GB(long b)
    {
        if (b < 0) return "?";
        return b >= 1073741824L ? string.Format("{0:N1} GB", b / 1073741824.0) : string.Format("{0:N0} MB", b / 1048576.0);
    }

    /// Todas las rutas que toca la instalacion (la del programa se puede cambiar; las demas son las estandar de Windows).
    public static List<RutaInfo> Rutas(Opciones op)
    {
        string user = Sitio.Usuario;
        string roaming = Sitio.Roaming;
        string local = Sitio.Local;
        string menu = Sitio.MenuInicio;
        string escritorio = Sitio.Escritorio;
        List<RutaInfo> l = new List<RutaInfo>();
        long tam = TamanoPrograma();
        l.Add(new RutaInfo { Titulo = "Programa CineCaptions", Ruta = op.Dir, Editable = true,
                             Nota = tam > 0 ? "ocupa ~" + GB(tam) : "", Libre = "libres " + GB(EspacioLibre(op.Dir)) });
        string motor = CarpetaMotorIA();
        l.Add(new RutaInfo { Titulo = "Motor de voz e IA (Qwen3: Python + PyTorch)", Ruta = motor,
                             Nota = MotorIAYaInstalado() ? "ya instalado" : "4-15 GB al instalarlo", Libre = "libres " + GB(EspacioLibre(motor)) });
        string hub = Path.GetDirectoryName(CarpetaModelo());
        l.Add(new RutaInfo { Titulo = "Modelos de voz (Whisper y Qwen3, cache de Hugging Face)", Ruta = hub,
                             Nota = ModeloYaDescargado() ? "Whisper ya descargado" : "Whisper 1,6 GB", Libre = "libres " + GB(EspacioLibre(hub)) });
        l.Add(new RutaInfo { Titulo = "Scripts de DaVinci Resolve (menu Scripts > Utility)",
                             Ruta = Path.Combine(roaming, @"Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"), Nota = "los copia el programa" });
        l.Add(new RutaInfo { Titulo = "Tipografias de las plantillas (solo para tu usuario)", Ruta = Path.Combine(local, @"Microsoft\Windows\Fonts"), Nota = "sin permisos de administrador" });
        l.Add(new RutaInfo { Titulo = "Acceso directo del Menu Inicio", Ruta = Path.Combine(menu, Programa.Nombre + ".lnk"), Nota = "" });
        l.Add(new RutaInfo { Titulo = "Tus datos: proyectos, licencia y ajustes", Ruta = Path.Combine(user, "DaVinciSubtitles"), Nota = "no se tocan al instalar; al desinstalar tú eliges" });
        l.Add(new RutaInfo { Titulo = "Registro de esta instalacion", Ruta = Registro.Ruta, Nota = "por si algo falla" });
        return l;
    }

    public static string CarpetaModelo()
    {
        return Path.Combine(Sitio.CacheModelos, "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo");
    }

    // v5.2: el motor Qwen3 ya instalado (listo.json + su Python + los modelos en la cache de Hugging Face):
    // el paso se salta en el acto, sin abrir el programa ni pip.
    public static string CarpetaMotorIA()
    {
        return Path.Combine(Sitio.Local, @"CineCaptions\motor_qwen");
    }

    static bool TieneSnapshot(string carpetaModelo, long minimo)
    {
        try
        {
            string snaps = Path.Combine(carpetaModelo, "snapshots");
            if (!Directory.Exists(snaps)) return false;
            foreach (string d in Directory.GetDirectories(snaps))
            {
                long total = 0;
                foreach (string a in Directory.GetFiles(d, "*.safetensors")) total += new FileInfo(a).Length;
                if (total >= minimo) return true;
            }
        }
        catch { }
        return false;
    }

    public static bool MotorIAYaInstalado()
    {
        try
        {
            string m = CarpetaMotorIA();
            string listo = Path.Combine(m, "listo.json");
            if (!File.Exists(listo) || !File.Exists(Path.Combine(m, @"python\python.exe"))) return false;
            string txt = File.ReadAllText(listo);
            if (txt.IndexOf("\"modelo_texto\"") < 0 || txt.IndexOf("\"modelo_texto\": null") >= 0) return false;
            string hub = Path.GetDirectoryName(CarpetaModelo());
            bool voz = TieneSnapshot(Path.Combine(hub, "models--Qwen--Qwen3-ASR-1.7B"), 1000000000L)
                    || TieneSnapshot(Path.Combine(hub, "models--Qwen--Qwen3-ASR-0.6B"), 400000000L);
            bool alineador = TieneSnapshot(Path.Combine(hub, "models--Qwen--Qwen3-ForcedAligner-0.6B"), 400000000L);
            bool texto = TieneSnapshot(Path.Combine(hub, "models--Qwen--Qwen3-4B-Instruct-2507"), 3000000000L)
                      || TieneSnapshot(Path.Combine(hub, "models--Qwen--Qwen3-1.7B"), 1000000000L);
            return voz && alineador && texto;
        }
        catch { return false; }
    }

    public static bool ModeloYaDescargado()
    {
        try
        {
            string snaps = Path.Combine(CarpetaModelo(), "snapshots");
            if (!Directory.Exists(snaps)) return false;
            foreach (string d in Directory.GetDirectories(snaps))
            {
                FileInfo f = new FileInfo(Path.Combine(d, "model.bin"));
                if (f.Exists && f.Length > 1000000000L && File.Exists(Path.Combine(d, "tokenizer.json"))) return true;
            }
        }
        catch { }
        return false;
    }

    // Cierra el programa si esta abierto: el .exe compilado o la version del .bat (pythonw con la ventana del programa)
    int CerrarPrograma()
    {
        int n = 0;
        List<Process> procesos = new List<Process>();
        // solo los CineCaptions.exe de ESTA instalacion (con la variable de prueba, nunca el programa real del usuario)
        foreach (Process p in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(Programa.ExePrograma)))
        {
            string ruta = Borrado.RutaDe(p);
            if (ruta != null ? Programa.DentroDe(ruta, op.Dir) : !Sitio.EsPrueba) procesos.Add(p);
        }
        if (!Sitio.EsPrueba)
            foreach (string nombre in new string[] { "pythonw", "python" })
                foreach (Process p in Process.GetProcessesByName(nombre))
                {
                    try { if (p.MainWindowTitle == Programa.Nombre) procesos.Add(p); } catch { }
                }
        foreach (Process p in procesos)
        {
            try
            {
                if (p.HasExited) continue;
                Log("Cerrando " + p.ProcessName + " (pid " + p.Id + ")");
                p.CloseMainWindow();
                if (!p.WaitForExit(8000)) { p.Kill(); p.WaitForExit(5000); }
                n++;
            }
            catch (Exception ex) { Log("No pude cerrar pid " + p.Id + ": " + ex.Message); }
        }
        // sus motores y procesos hijos (Python de la voz / IA...) que sigan sosteniendo archivos de la carpeta del programa o del motor
        List<string> carpetas = new List<string>();
        carpetas.Add(op.Dir);
        carpetas.Add(CarpetaMotorIA());
        n += Borrado.CerrarEn(carpetas, Log, Application.ExecutablePath);
        return n;
    }

    // ---- 2) ------------------------------------------------------------------------
    static bool EsNuestra(string dir)
    {
        if (!Directory.Exists(dir)) return true;
        if (File.Exists(Path.Combine(dir, Programa.ExePrograma)) || File.Exists(Path.Combine(dir, "Desinstalar.exe"))) return true;
        if (File.Exists(Path.Combine(dir, "unins000.exe"))) return true;   // restos del Setup original
        return Directory.GetFileSystemEntries(dir).Length == 0;
    }

    void CopiarPrograma(long total)
    {
        string dir = Path.GetFullPath(op.Dir).TrimEnd('\\');
        if (!EsNuestra(dir))
            throw new Exception("La carpeta " + dir + " ya tiene otros archivos que no son de CineCaptions. Elige otra carpeta.");
        string anterior = dir + ".anterior";
        BorrarCarpetaSiExiste(anterior);
        bool habiaAnterior = false;
        if (Directory.Exists(dir) && Directory.GetFileSystemEntries(dir).Length > 0)
        {
            Detalle(pCopiar, "Apartando la versión instalada", -1);
            // el antivirus o un proceso que acaba de cerrarse pueden retener la carpeta unos segundos: se reintenta antes de rendirse
            Exception ultimo = null;
            for (int intento = 1; intento <= 12 && !habiaAnterior; intento++)
            {
                try { Directory.Move(dir, anterior); habiaAnterior = true; }
                catch (Exception ex)
                {
                    ultimo = ex;
                    Log("No pude apartar la versión instalada (intento " + intento + " de 12): " + ex.Message);
                    if (intento == 4 || intento == 8) { try { CerrarPrograma(); } catch { } }
                    Thread.Sleep(1000);
                }
            }
            if (!habiaAnterior)
            {
                // v5.4.51: DaVinci Resolve vigila las carpetas de los medios que importó; si alguno salió de la carpeta del programa (los sonidos de la
                // Edición PRO de versiones anteriores), la retiene mientras esté abierto. Se dice claro qué cerrar.
                bool resolveAbierto = false;
                try { resolveAbierto = System.Diagnostics.Process.GetProcessesByName("Resolve").Length > 0; } catch { }
                if (resolveAbierto)
                    throw new Exception("DaVinci Resolve está usando archivos de la carpeta de CineCaptions (sonidos de una versión anterior). Cierra DaVinci Resolve y pulsa REINTENTAR.\r\n" + (ultimo != null ? ultimo.Message : ""));
                throw new Exception("No puedo reemplazar la versión instalada (algún archivo está en uso: cierra CineCaptions y vuelve a intentarlo).\r\n" + (ultimo != null ? ultimo.Message : ""));
            }
        }
        try
        {
            Directory.CreateDirectory(dir);
            long hecho = 0;
            int ultimoPct = -1;
            DateTime ultimo = DateTime.MinValue;
            using (FileStream fs = new FileStream(Application.ExecutablePath, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (ZipArchive zip = Paquete.Abrir(fs))
            {
                foreach (ZipArchiveEntry e in zip.Entries)
                {
                    string rel;
                    if (e.FullName.StartsWith("programa/")) rel = e.FullName.Substring("programa/".Length);
                    else if (e.FullName == "Desinstalar.exe") rel = e.FullName;
                    else continue;
                    if (rel.Length == 0) continue;
                    string destino = Path.GetFullPath(Path.Combine(dir, rel.Replace('/', '\\')));
                    if (!destino.StartsWith(dir + "\\", StringComparison.OrdinalIgnoreCase)) continue;
                    if (rel.EndsWith("/")) { Directory.CreateDirectory(destino); continue; }
                    Directory.CreateDirectory(Path.GetDirectoryName(destino));
                    using (Stream a = e.Open())
                    using (FileStream b = new FileStream(destino, FileMode.Create, FileAccess.Write))
                    {
                        byte[] buf = new byte[1 << 20];
                        int n;
                        while ((n = a.Read(buf, 0, buf.Length)) > 0)
                        {
                            b.Write(buf, 0, n);
                            hecho += n;
                            int pct = total > 0 ? (int)(100 * hecho / total) : 0;
                            if (pct != ultimoPct && (DateTime.Now - ultimo).TotalMilliseconds > 120)
                            {
                                ultimoPct = pct; ultimo = DateTime.Now;
                                Detalle(pCopiar, string.Format("{0}  ({1:N0} de {2:N0} MB)", rel.Replace('/', '\\'), hecho / 1048576, total / 1048576), pct);
                            }
                        }
                    }
                    try { File.SetLastWriteTime(destino, e.LastWriteTime.DateTime); } catch { }
                }
            }
            File.WriteAllText(Path.Combine(dir, "version.txt"), Programa.Version, Encoding.ASCII);
            if (!File.Exists(Path.Combine(dir, Programa.ExePrograma))) throw new Exception("El paquete no trae " + Programa.ExePrograma);
        }
        catch
        {
            if (habiaAnterior)
            {
                Log("Fallo la copia: vuelvo a dejar la version anterior");
                BorrarCarpetaSiExiste(dir);
                try { Directory.Move(anterior, dir); } catch (Exception ex) { Log("No pude restaurar: " + ex.Message); }
            }
            throw;
        }
        if (habiaAnterior) BorrarCarpetaSiExiste(anterior);
        Terminar(pCopiar, EstadoPaso.Hecho, string.Format("{0:N0} MB en {1}", total / 1048576, dir));
    }

    // ---- tareas del programa instalado ---------------------------------------------------
    // Corre "<exe> --tarea <nombre> <estado.txt>" y va leyendo el estado. Devuelve true si termino OK.
    bool Tarea(Paso paso, string nombre, int timeoutSeg, EstadoPaso siFalla)
    {
        string exe = ExeInstalado;
        if (Sitio.EsPrueba && (nombre == "fuentes" || nombre == "modelo" || nombre == "motor_ia"))      // pruebas del instalador: nada que toque el sistema real
        {
            Terminar(paso, EstadoPaso.Omitido, "Omitido en la prueba");
            return true;
        }
        string estado = Path.Combine(Path.GetTempPath(), "cinecaptions_tarea_" + nombre + "_" + Guid.NewGuid().ToString("N").Substring(0, 6) + ".txt");
        string final = null, finalTexto = "";
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo(exe, "--tarea " + nombre + " \"" + estado + "\"");
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.WorkingDirectory = op.Dir;
            Process p = Process.Start(psi);
            tareaActual = p;
            long leido = 0;
            DateTime inicio = DateTime.Now;
            bool termino = false;
            while (!termino)
            {
                termino = p.WaitForExit(250);
                leido = LeerEstado(estado, leido, paso, ref final, ref finalTexto);
                if (!termino && (DateTime.Now - inicio).TotalSeconds > timeoutSeg)
                {
                    try { p.Kill(); } catch { }
                    finalTexto = "No terminó en " + timeoutSeg / 60 + " minutos";
                    final = "ERROR";
                    break;
                }
            }
            leido = LeerEstado(estado, leido, paso, ref final, ref finalTexto);
            tareaActual = null;
            if (final == null)
            {
                final = "ERROR";
                finalTexto = "El programa se cerró sin responder (código " + (p.HasExited ? p.ExitCode.ToString() : "?") + ")";
            }
        }
        catch (Exception ex)
        {
            final = "ERROR";
            finalTexto = "No pude ejecutar el programa instalado: " + ex.Message;
        }
        finally
        {
            tareaActual = null;
            try { File.Delete(estado); } catch { }
        }
        if (final == "OK") { Terminar(paso, EstadoPaso.Hecho, finalTexto); return true; }
        if (paso == pModelo && omitirModelo)
        {
            Terminar(paso, EstadoPaso.Omitido, "Omitido: se descargará la primera vez que transcribas");
            return false;
        }
        if (paso == pMotorIA && omitirModelo)
        {
            Terminar(paso, EstadoPaso.Omitido, "Omitido: se instala desde Ajustes > General (mientras, Whisper)");
            return false;
        }
        Terminar(paso, siFalla, finalTexto);
        return false;
    }

    long LeerEstado(string archivo, long desde, Paso paso, ref string final, ref string finalTexto)
    {
        try
        {
            if (!File.Exists(archivo)) return desde;
            using (FileStream fs = new FileStream(archivo, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            {
                if (fs.Length <= desde) return desde;
                fs.Seek(desde, SeekOrigin.Begin);
                byte[] b = new byte[fs.Length - desde];
                int n = fs.Read(b, 0, b.Length);
                string texto = Encoding.UTF8.GetString(b, 0, n);
                int corte = texto.LastIndexOf('\n');
                if (corte < 0) return desde;                         // linea a medio escribir: la proxima vez
                texto = texto.Substring(0, corte + 1);
                foreach (string l0 in texto.Split('\n'))
                {
                    string l = l0.TrimEnd('\r');
                    if (l.Length == 0) continue;
                    string[] p = l.Split(new char[] { '|' }, 3);
                    if (p[0] == "PROGRESO" && p.Length >= 2)
                    {
                        int pct; int.TryParse(p[1], out pct);
                        Detalle(paso, p.Length > 2 && p[2].Length > 0 ? p[2] : paso.Detalle, pct);
                    }
                    else if (p[0] == "INFO" && p.Length >= 2) Log("   " + l.Substring(5));
                    else if ((p[0] == "OK" || p[0] == "ERROR") && p.Length >= 1)
                    {
                        final = p[0];
                        finalTexto = l.Length > p[0].Length + 1 ? l.Substring(p[0].Length + 1) : "";
                    }
                }
                return desde + Encoding.UTF8.GetByteCount(texto);
            }
        }
        catch { return desde; }
    }

    // ---- 7) ------------------------------------------------------------------------
    [DllImport("shell32.dll")] static extern void SHChangeNotify(int evento, int flags, IntPtr a, IntPtr b);
    // (5.3) Windows guarda el icono de cada acceso directo en una cache: sin esto se seguia viendo el icono ANTERIOR
    void RefrescarIconos()
    {
        try { SHChangeNotify(0x08000000, 0, IntPtr.Zero, IntPtr.Zero); } catch { }      // SHCNE_ASSOCCHANGED
        try
        {
            ProcessStartInfo ie = new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, "ie4uinit.exe"), "-show");
            ie.CreateNoWindow = true; ie.UseShellExecute = false;
            Process.Start(ie);
        }
        catch { }
    }
    void CrearAcceso(string lnk, string destino, string carpeta)
    {
        try
        {
            try { Directory.CreateDirectory(Path.GetDirectoryName(lnk)); } catch { }          // el Menu Inicio / Escritorio pueden no existir aun (perfiles nuevos o redirigidos)
            Type t = Type.GetTypeFromProgID("WScript.Shell");
            object shell = Activator.CreateInstance(t);
            object acceso = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { lnk });
            Type ta = acceso.GetType();
            ta.InvokeMember("TargetPath", BindingFlags.SetProperty, null, acceso, new object[] { destino });
            ta.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, acceso, new object[] { carpeta });
            ta.InvokeMember("IconLocation", BindingFlags.SetProperty, null, acceso, new object[] { destino + ",0" });
            ta.InvokeMember("Description", BindingFlags.SetProperty, null, acceso, new object[] { "Subtitulos automaticos para DaVinci Resolve" });
            ta.InvokeMember("Save", BindingFlags.InvokeMethod, null, acceso, null);
            Log("Acceso directo: " + lnk);
            RefrescarIconos();
        }
        catch (Exception ex) { Log("No pude crear " + lnk + ": " + ex.Message); }
    }

    static string LeerDestinoAcceso(string lnk)
    {
        try
        {
            Type t = Type.GetTypeFromProgID("WScript.Shell");
            object shell = Activator.CreateInstance(t);
            object acceso = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { lnk });
            return (string)acceso.GetType().InvokeMember("TargetPath", BindingFlags.GetProperty, null, acceso, null);
        }
        catch { return ""; }
    }

    static bool ApuntaAInstalacionVieja(string lnk)
    {
        string d = LeerDestinoAcceso(lnk) ?? "";
        return d.EndsWith(Programa.ExePrograma, StringComparison.OrdinalIgnoreCase);
    }

    void RegistrarDesinstalador()
    {
        try
        {
            using (RegistryKey k = Sitio.RaizRegistro().CreateSubKey(Programa.ClaveDesinstalar))
            {
                string exe = ExeInstalado;
                string des = Path.Combine(op.Dir, "Desinstalar.exe");
                k.SetValue("DisplayName", Programa.Nombre);
                k.SetValue("DisplayVersion", Programa.Version);
                k.SetValue("Publisher", "Cinema Productions");
                k.SetValue("DisplayIcon", exe + ",0");
                k.SetValue("InstallLocation", op.Dir);
                k.SetValue("UninstallString", "\"" + des + "\" /desinstalar");
                k.SetValue("QuietUninstallString", "\"" + des + "\" /desinstalar /silencioso");
                // v5.2: sin enlace personal (una version anterior lo dejo: se borra)
                try { k.DeleteValue("URLInfoAbout", false); } catch { }
                k.SetValue("InstallDate", DateTime.Now.ToString("yyyyMMdd"));
                k.SetValue("NoModify", 1, RegistryValueKind.DWord);
                k.SetValue("NoRepair", 1, RegistryValueKind.DWord);
                k.SetValue("EstimatedSize", (int)(TamanoCarpeta(op.Dir) / 1024), RegistryValueKind.DWord);
            }
        }
        catch (Exception ex) { Log("No pude registrar el desinstalador: " + ex.Message); }
    }

    static long TamanoCarpeta(string dir)
    {
        long t = 0;
        try { foreach (string f in Directory.GetFiles(dir, "*", SearchOption.AllDirectories)) t += new FileInfo(f).Length; } catch { }
        return t;
    }

    // Borra una carpeta entera (rutas largas, solo lectura, enlaces). Devuelve true si ya no existe; si no, la apunta para el proximo inicio de sesion.
    bool BorrarCarpetaSiExiste(string dir)
    {
        if (!Borrado.Existe(dir)) return true;
        if (Borrado.Arbol(dir, Log)) { Log("Borrado: " + dir); return true; }
        Log("No pude borrar del todo " + dir + ": se intentará de nuevo al iniciar sesión");
        pendientes.Add(dir);
        return false;
    }
    readonly List<string> pendientes = new List<string>();

    void BorrarArchivo(string f) { try { File.Delete(f); Log("Borrado: " + f); } catch { } }

    // ==========================================================================
    // Las tipografias que el programa trae (las que instalo para tu usuario): la carpeta fonts del programa instalado.
    List<string> CarpetasDeFuentes()
    {
        List<string> l = new List<string>();
        foreach (string c in new string[] { Path.Combine(op.Dir, @"_internal\fonts"), Path.Combine(op.Dir, "fonts") })
            if (Directory.Exists(c)) l.Add(c);
        return l;
    }

    // Los nombres de los scripts que el programa dejo en el menu de Resolve (los de su carpeta resolve_scripts).
    List<string> NombresDeScripts()
    {
        List<string> l = new List<string>();
        foreach (string c in new string[] { Path.Combine(op.Dir, @"_internal\resolve_scripts"), Path.Combine(op.Dir, "resolve_scripts") })
        {
            if (!Directory.Exists(c)) continue;
            try { foreach (string f in Directory.GetFiles(c)) l.Add(Path.GetFileName(f)); } catch { }
        }
        return l;
    }

    // Respaldo de la tarea del programa: barre las carpetas de scripts de Resolve y quita lo nuestro (por nombre conocido o por empezar con «CineCaptions»).
    int QuitarScriptsDeResolve(List<string> nombres)
    {
        int n = 0;
        List<string> raices = new List<string>();
        raices.Add(Path.Combine(Sitio.Roaming, @"Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts"));
        raices.Add(Path.Combine(Sitio.ProgramData, @"Blackmagic Design\DaVinci Resolve\Fusion\Scripts"));
        foreach (string raiz in raices)
            foreach (string sub in new string[] { "Utility", "Edit", "Comp", "Color", "Deliver" })
            {
                string c = Path.Combine(raiz, sub);
                if (!Directory.Exists(c)) continue;
                Log("Scripts de Resolve: reviso " + c);
                try
                {
                    foreach (string f in Directory.GetFiles(c))
                    {
                        string nombre = Path.GetFileName(f);
                        if (nombres.Contains(nombre) || nombre.StartsWith("CineCaptions", StringComparison.OrdinalIgnoreCase))
                        {
                            if (Borrado.Arbol(f, Log)) { Log("Borrado: " + f); n++; }
                        }
                    }
                }
                catch (Exception ex) { Log("No pude revisar " + c + ": " + ex.Message); }
            }
        return n;
    }

    int QuitarFuentes()
    {
        int n = 0;
        string destino = Sitio.Fuentes;
        if (!Directory.Exists(destino)) return 0;
        List<string> rutasBorradas = new List<string>();
        foreach (string carpeta in CarpetasDeFuentes())
        {
            foreach (string origen in Directory.GetFiles(carpeta))
            {
                try
                {
                    string copia = Path.Combine(destino, Path.GetFileName(origen));
                    // solo la que es IGUAL a la del programa: una tipografia tuya con el mismo nombre pero otra no se toca
                    if (!File.Exists(copia) || new FileInfo(copia).Length != new FileInfo(origen).Length) continue;
                    if (!Sitio.EsPrueba) RemoveFontResourceExW(copia, 0, IntPtr.Zero);
                    if (Borrado.Arbol(copia, Log)) { rutasBorradas.Add(copia); n++; }
                }
                catch (Exception ex) { Log("Tipografía " + Path.GetFileName(origen) + ": " + ex.Message); }
            }
        }
        try
        {
            using (RegistryKey k = Sitio.RaizRegistro().OpenSubKey(@"Software\Microsoft\Windows NT\CurrentVersion\Fonts", true))
            {
                if (k != null)
                    foreach (string nombre in k.GetValueNames())
                    {
                        object v = k.GetValue(nombre);
                        if (v == null) continue;
                        foreach (string r in rutasBorradas)
                            if (string.Equals(v.ToString(), r, StringComparison.OrdinalIgnoreCase)) { k.DeleteValue(nombre, false); break; }
                    }
            }
        }
        catch (Exception ex) { Log("Registro de tipografías: " + ex.Message); }
        if (n > 0 && !Sitio.EsPrueba) Borrado.AvisarFuentes();
        return n;
    }
    [DllImport("gdi32.dll", CharSet = CharSet.Unicode)] static extern int RemoveFontResourceExW(string nombre, uint flags, IntPtr reservado);

    // Libera la activacion de este equipo en la tienda (para poder usar la licencia en otro). Necesita internet; si falla, se avisa y se sigue.
    bool LiberarLicencia()
    {
        if (!File.Exists(ExeInstalado)) return false;
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo(ExeInstalado, "--licencia-liberar");
            psi.UseShellExecute = false; psi.CreateNoWindow = true; psi.RedirectStandardOutput = true;
            psi.WorkingDirectory = op.Dir;
            using (Process p = Process.Start(psi))
            {
                if (!p.WaitForExit(50000)) { try { p.Kill(); } catch { } Log("La liberación de la licencia no respondió"); return false; }
                Log("Licencia: " + p.StandardOutput.ReadToEnd().Trim());
                return p.ExitCode == 0;
            }
        }
        catch (Exception ex) { Log("No pude liberar la licencia: " + ex.Message); return false; }
    }

    static readonly string[] ModelosDeCineCaptions = new string[] {
        "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo", "models--Systran--faster-whisper-large-v3", "models--Systran--faster-whisper-medium",
        "models--Systran--faster-whisper-small", "models--Systran--faster-whisper-base", "models--Systran--faster-whisper-tiny",
        "models--Qwen--Qwen3-ASR-1.7B", "models--Qwen--Qwen3-ASR-0.6B", "models--Qwen--Qwen3-ForcedAligner-0.6B",
        "models--Qwen--Qwen3-4B-Instruct-2507", "models--Qwen--Qwen3-1.7B" };

    public static List<string> RutasDeModelos()
    {
        List<string> l = new List<string>();
        string hub = Sitio.CacheModelos;
        foreach (string m in ModelosDeCineCaptions) l.Add(Path.Combine(hub, m));
        foreach (string a in new string[] { @".local\share\argos-translate", @".local\cache\argos-translate", @".config\argos-translate" })
            l.Add(Path.Combine(Sitio.Usuario, a));
        return l;
    }

    // ---- la desinstalacion completa --------------------------------------------------------------
    void Desinstalar()
    {
        bool completo = op.BorrarDatos || op.BorrarModelos;
        List<string> prefijosRastro = new List<string>();
        prefijosRastro.Add(op.Dir);
        prefijosRastro.Add(CarpetaMotorIA());
        prefijosRastro.Add(Path.Combine(Sitio.Local, "CineCaptions"));

        // 1) cerrar el programa y todo lo que sostenga sus archivos (motores de voz / IA)
        Empezar(dCerrar, "");
        int n = CerrarPrograma();
        Terminar(dCerrar, EstadoPaso.Hecho, n > 0 ? "Se cerró el programa y sus motores (" + n + " procesos)" : "No estaba abierto");

        // 2) la licencia de este equipo
        Empezar(dLicencia, "");
        if (!op.BorrarDatos) Terminar(dLicencia, EstadoPaso.Omitido, "Tu licencia se conserva (sigue activa en este equipo)");
        else if (Sitio.EsPrueba) Terminar(dLicencia, EstadoPaso.Omitido, "Omitido en la prueba");
        else if (LiberarLicencia()) Terminar(dLicencia, EstadoPaso.Hecho, "Este equipo quedó libre: puedes activarla en otro");
        else Terminar(dLicencia, EstadoPaso.Aviso, "No pude liberarla (¿sin internet?). Libérala desde tu cuenta de la tienda si la vas a usar en otro equipo");

        // 3) scripts de Resolve (la tarea del programa los conoce todos; el barrido propio cubre que el programa ya no abra)
        Empezar(dScripts, "");
        List<string> nombresScripts = NombresDeScripts();
        int barridos = 0;
        try { barridos = QuitarScriptsDeResolve(nombresScripts); } catch (Exception ex) { Log("Scripts: " + ex.Message); }
        if (File.Exists(ExeInstalado) && !Sitio.EsPrueba) Tarea(dScripts, "quitar_scripts", 120, EstadoPaso.Aviso);
        else Terminar(dScripts, EstadoPaso.Hecho, barridos + " scripts quitados del menú de Resolve");

        // 4) tipografias
        Empezar(dFuentes, "");
        int fuentes = 0;
        try { fuentes = QuitarFuentes(); } catch (Exception ex) { Log("Tipografías: " + ex.Message); }
        Terminar(dFuentes, EstadoPaso.Hecho, fuentes > 0 ? fuentes + " tipografías quitadas" : "No había tipografías del programa");

        // 5) accesos directos y claves del programa
        Empezar(dAccesos, "");
        List<string> quitados = new List<string>();
        foreach (string lnk in new string[] { Path.Combine(Sitio.MenuInicio, Programa.Nombre + ".lnk"), Path.Combine(Sitio.Escritorio, Programa.Nombre + ".lnk") })
            if (File.Exists(lnk) && Programa.DentroDe(LeerDestinoAcceso(lnk), op.Dir)) { BorrarArchivo(lnk); quitados.Add(Path.GetFileName(lnk)); }
        // anclados a la barra de tareas / al menu Inicio
        foreach (string ancla in new string[] { @"Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar", @"Microsoft\Internet Explorer\Quick Launch\User Pinned\StartMenu" })
        {
            string carpeta = Path.Combine(Sitio.Roaming, ancla);
            if (!Directory.Exists(carpeta)) continue;
            try
            {
                foreach (string lnk in Directory.GetFiles(carpeta, "*.lnk"))
                    if (Programa.DentroDe(LeerDestinoAcceso(lnk), op.Dir)) { BorrarArchivo(lnk); quitados.Add("anclado"); }
            }
            catch { }
        }
        string subMenu = Path.Combine(Sitio.MenuInicio, Programa.Nombre);              // la carpeta del Setup original
        if (Directory.Exists(subMenu)) BorrarCarpetaSiExiste(subMenu);
        try
        {
            string clave = Programa.ClaveDesinstalar;
            string dir = Registro.LeerHKCU(clave, "InstallLocation");
            if (dir == null || string.Equals(dir.TrimEnd('\\'), op.Dir.TrimEnd('\\'), StringComparison.OrdinalIgnoreCase))
                Sitio.RaizRegistro().DeleteSubKeyTree(clave, false);
        }
        catch { }
        RefrescarIconos();
        Terminar(dAccesos, EstadoPaso.Hecho, quitados.Count > 0 ? "Menú Inicio, Escritorio y Agregar o quitar programas" : "Agregar o quitar programas");

        // 6) el programa, su motor de voz / IA y la carpeta propia en AppData
        Empezar(dArchivos, op.Dir);
        bool ajena = !EsNuestra(op.Dir);
        if (ajena)
        {
            Log("No borro " + op.Dir + ": tiene archivos que no son del programa");
        }
        else
        {
            BorrarCarpetaSiExiste(op.Dir);
            BorrarCarpetaSiExiste(op.Dir.TrimEnd('\\') + ".anterior");
        }
        BorrarCarpetaSiExiste(CarpetaMotorIA());
        BorrarCarpetaSiExiste(Path.Combine(Sitio.Local, "CineCaptions"));
        if (ajena) Terminar(dArchivos, EstadoPaso.Aviso, "No borré " + op.Dir + ": tiene archivos que no son del programa");
        else if (Borrado.Existe(op.Dir)) Terminar(dArchivos, EstadoPaso.Aviso, "Algún archivo estaba en uso: se borra solo al iniciar sesión de nuevo");
        else Terminar(dArchivos, EstadoPaso.Hecho, "Programa, motor de voz e IA y carpeta de AppData borrados");

        // 7) tus datos y los modelos descargados (solo lo que se marco)
        Empezar(dDatos, "");
        List<string> hechosDatos = new List<string>();
        if (op.BorrarDatos)
        {
            BorrarCarpetaSiExiste(Sitio.DatosUsuario);
            BorrarCarpetaSiExiste(Path.Combine(Sitio.Usuario, ".cinecaptions.lock"));
            string copias = Path.Combine(Sitio.Documentos, "CineCaptions");
            if (Directory.Exists(copias)) BorrarCarpetaSiExiste(copias);
            hechosDatos.Add("datos, licencia y ajustes");
        }
        if (op.BorrarModelos)
        {
            foreach (string m in RutasDeModelos()) if (Borrado.Existe(m)) BorrarCarpetaSiExiste(m);
            hechosDatos.Add("modelos de voz e idioma");
        }
        // estas carpetas del sistema se quitan solo si quedaron vacias por nuestra causa
        foreach (string vacia in new string[] { Path.Combine(Sitio.Usuario, @".cache\huggingface\hub"), Path.Combine(Sitio.Usuario, @".cache\huggingface"), Path.Combine(Sitio.Usuario, @".local\share"),
                                                Path.Combine(Sitio.Usuario, @".local\cache"), Path.Combine(Sitio.Usuario, ".local") })
        {
            try { if (op.BorrarModelos && Directory.Exists(vacia) && Directory.GetFileSystemEntries(vacia).Length == 0) Directory.Delete(vacia); } catch { }
        }
        if (hechosDatos.Count == 0)
            Terminar(dDatos, EstadoPaso.Omitido, "Se conservan tus datos en " + Sitio.DatosUsuario + " y los modelos descargados");
        else if (op.BorrarDatos && Borrado.Existe(Sitio.DatosUsuario))
            Terminar(dDatos, EstadoPaso.Aviso, "Quedaron archivos en uso en " + Sitio.DatosUsuario + ": se borran solos al iniciar sesión de nuevo");
        else
            Terminar(dDatos, EstadoPaso.Hecho, "Borrado: " + string.Join(" y ", hechosDatos.ToArray()) + (op.BorrarDatos && !op.BorrarModelos ? ". Se conservan los modelos descargados" : "")
                                                 + (!op.BorrarDatos ? ". Se conservan tus datos en " + Sitio.DatosUsuario : ""));

        // 8) rastros y comprobacion final
        Empezar(dRastros, "");
        int claves = 0;
        try { claves = Borrado.LimpiarRastros(prefijosRastro, Log); } catch (Exception ex) { Log("Rastros: " + ex.Message); }
        int temporales = 0;
        try
        {
            foreach (string f in Directory.GetFileSystemEntries(Sitio.Temp, "cinecaptions_*"))
            {
                string nombre = Path.GetFileName(f);
                if (nombre.StartsWith("cinecaptions_desinstalar_", StringComparison.OrdinalIgnoreCase)) continue;       // esta propia copia y su log
                if (Borrado.Arbol(f, null)) temporales++;
            }
        }
        catch { }
        List<string> restos = new List<string>();
        foreach (string p in new string[] { op.Dir, op.Dir.TrimEnd('\\') + ".anterior", CarpetaMotorIA(), Path.Combine(Sitio.Local, "CineCaptions") })
            if (Borrado.Existe(p)) restos.Add(p);
        if (op.BorrarDatos && Borrado.Existe(Sitio.DatosUsuario)) restos.Add(Sitio.DatosUsuario);
        if (op.BorrarModelos) foreach (string m in RutasDeModelos()) if (Borrado.Existe(m)) restos.Add(m);
        foreach (string p in pendientes) if (!restos.Contains(p) && Borrado.Existe(p)) restos.Add(p);
        if (restos.Count > 0)
        {
            Borrado.ProgramarBorrado(restos, Log);
            Terminar(dRastros, EstadoPaso.Aviso, restos.Count + " elemento/s en uso se borran solos al iniciar sesión de nuevo (cierra Resolve si lo tenías abierto)");
        }
        else Terminar(dRastros, EstadoPaso.Hecho, claves + " entradas de Windows y " + temporales + " temporales quitados; no queda nada del programa");

        Resumen = HuboError ? "La desinstalación tuvo problemas. Mira los detalles."
                            : (completo ? "CineCaptions se desinstaló por completo." : "CineCaptions se desinstaló.");
    }
}


// ---------------------------------------------------------------------------
// Interfaz: el mismo diseno que el instalador de CineSlide (ventana sin bordes redondeada, banner con un fotograma real,
// botones circulares fijar / minimizar / maximizar / cerrar, PASOS a la izquierda, barra y boton pildora en degradado a la
// derecha, "Ver detalles" que despliega el registro hacia abajo), con los colores de CineCaptions.
static class Tema
{
    public static readonly Color Fondo = Color.FromArgb(8, 12, 20);          // BG_COLOR del programa
    public static readonly Color FondoLog = Color.FromArgb(4, 7, 13);
    public static readonly Color Suave = Color.FromArgb(150, 165, 192);
    public static readonly Color Pendiente = Color.FromArgb(118, 132, 158);
    public static readonly Color Linea = Color.FromArgb(30, 42, 66);          // BORDER_COLOR
    public static readonly Color Acento = Color.FromArgb(22, 163, 106);       // esmeralda (como el programa nuevo)
    public static readonly Color Cian = Color.FromArgb(70, 228, 170);
    public static readonly Color EnCurso = Color.FromArgb(96, 236, 178);
    public static readonly Color Ok = Color.FromArgb(98, 209, 150);
    public static readonly Color Aviso = Color.FromArgb(255, 184, 107);
    public static readonly Color Error = Color.FromArgb(255, 107, 107);
}

static class Dibujo
{
    [DllImport("user32.dll")] static extern bool ReleaseCapture();
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, int msg, int wp, int lp);
    [DllImport("uxtheme.dll", CharSet = CharSet.Unicode)] static extern int SetWindowTheme(IntPtr h, string app, string id);

    public static void Arrastrar(Form f)
    {
        if (f.WindowState == FormWindowState.Maximized) return;
        ReleaseCapture();
        SendMessage(f.Handle, 0xA1, 2, 0);
    }
    public static GraphicsPath Redondeado(RectangleF r, float radio)
    {
        GraphicsPath g = new GraphicsPath();
        float d = Math.Max(1f, Math.Min(radio * 2, Math.Min(r.Width, r.Height)));
        g.AddArc(r.X, r.Y, d, d, 180, 90);
        g.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        g.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        g.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        g.CloseFigure();
        return g;
    }
    public static void Oscuro(Control c) { try { SetWindowTheme(c.Handle, "DarkMode_Explorer", null); } catch { } }
    public static void Brillo(Graphics g, GraphicsPath forma, RectangleF r, float fase, int alfa, float ancho)
    {
        float x = r.X + fase * r.Width;
        RectangleF rb = new RectangleF(x - ancho / 2, r.Y, ancho, r.Height);
        using (LinearGradientBrush lb = new LinearGradientBrush(rb, Color.Transparent, Color.Transparent, 0f))
        {
            ColorBlend cb = new ColorBlend();
            cb.Colors = new Color[] { Color.FromArgb(0, 255, 255, 255), Color.FromArgb(alfa, 255, 255, 255), Color.FromArgb(0, 255, 255, 255) };
            cb.Positions = new float[] { 0f, 0.5f, 1f };
            lb.InterpolationColors = cb;
            Region antes = g.Clip;
            g.SetClip(forma, CombineMode.Intersect);
            g.FillRectangle(lb, rb);
            g.Clip = antes;
        }
    }
}

/// Boton principal en forma de pildora con degradado. Deshabilitado = "trabajando": mismo diseno con un brillo que lo
/// recorre y el texto SIEMPRE blanco.
class BotonPildora : Control
{
    bool hover;
    float fase = -0.6f;
    readonly System.Windows.Forms.Timer reloj;
    public Color ColorA = Tema.Acento;
    public Color ColorB = Tema.Cian;
    public BotonPildora()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint |
                 ControlStyles.SupportsTransparentBackColor | ControlStyles.ResizeRedraw, true);
        BackColor = Color.Transparent;
        ForeColor = Color.White;
        Cursor = Cursors.Hand;
        Font = new Font("Segoe UI", 14f, FontStyle.Bold);
        reloj = new System.Windows.Forms.Timer();
        reloj.Interval = 40;
        reloj.Tick += delegate { fase += 0.018f; if (fase > 1.6f) fase = -0.6f; Invalidate(); };
    }
    public void Colores(Color a, Color b) { ColorA = a; ColorB = b; Invalidate(); }
    static Color Oscurecer(Color c, float k) { return Color.FromArgb((int)(c.R * k), (int)(c.G * k), (int)(c.B * k)); }
    protected override void OnEnabledChanged(EventArgs e)
    {
        if (Enabled) reloj.Stop(); else { fase = -0.6f; reloj.Start(); }
        Cursor = Enabled ? Cursors.Hand : Cursors.Default;
        Invalidate();
        base.OnEnabledChanged(e);
    }
    protected override void OnTextChanged(EventArgs e) { Invalidate(); base.OnTextChanged(e); }
    protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
    protected override void OnMouseLeave(EventArgs e) { hover = false; Invalidate(); base.OnMouseLeave(e); }
    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAliasGridFit;
        RectangleF r = new RectangleF(1.5f, 1.5f, Width - 3f, Height - 3f);
        using (GraphicsPath p = Dibujo.Redondeado(r, r.Height / 2f))
        {
            Color a = Enabled ? ColorA : Oscurecer(ColorA, 0.6f), b = Enabled ? ColorB : Oscurecer(ColorB, 0.6f);
            using (LinearGradientBrush lg = new LinearGradientBrush(r, a, b, LinearGradientMode.Horizontal)) g.FillPath(lg, p);
            using (LinearGradientBrush ls = new LinearGradientBrush(r, Color.Transparent, Color.Transparent, LinearGradientMode.Vertical))
            {
                ColorBlend cb = new ColorBlend();
                cb.Colors = new Color[] { Color.FromArgb(hover && Enabled ? 95 : 62, 255, 255, 255), Color.FromArgb(8, 255, 255, 255), Color.FromArgb(28, 0, 0, 0) };
                cb.Positions = new float[] { 0f, 0.5f, 1f };
                ls.InterpolationColors = cb;
                g.FillPath(ls, p);
            }
            if (!Enabled) Dibujo.Brillo(g, p, r, fase, 110, r.Height * 2.5f);
            using (Pen pen = new Pen(Color.FromArgb(hover && Enabled ? 230 : 150, 190, 225, 255), 1.2f)) g.DrawPath(pen, p);
        }
        StringFormat sf = new StringFormat();
        sf.Alignment = StringAlignment.Center;
        sf.LineAlignment = StringAlignment.Center;
        using (SolidBrush sombra = new SolidBrush(Color.FromArgb(90, 0, 0, 0))) g.DrawString(Text, Font, sombra, new RectangleF(r.X, r.Y + 1.5f, r.Width, r.Height), sf);
        using (SolidBrush b = new SolidBrush(Color.White)) g.DrawString(Text, Font, b, r, sf);
    }
    protected override void Dispose(bool d) { if (d && reloj != null) { reloj.Stop(); reloj.Dispose(); } base.Dispose(d); }
}

/// Barra de progreso: pista redondeada y relleno en degradado azul -> cian con un brillo que la recorre.
class BarraModerna : Control
{
    double valor;
    float brillo = -0.4f;
    readonly System.Windows.Forms.Timer reloj;
    public BarraModerna()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint |
                 ControlStyles.SupportsTransparentBackColor | ControlStyles.ResizeRedraw, true);
        BackColor = Color.Transparent;
        reloj = new System.Windows.Forms.Timer();
        reloj.Interval = 40;
        reloj.Tick += delegate { brillo += 0.012f; if (brillo > 1.4f) brillo = -0.4f; if (valor > 0 && valor < 1) Invalidate(); };
        reloj.Start();
    }
    public double Valor { get { return valor; } set { double v = Math.Max(0, Math.Min(1, value)); if (Math.Abs(v - valor) > 0.0005) { valor = v; Invalidate(); } } }
    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        RectangleF r = new RectangleF(0.5f, 0.5f, Width - 1, Height - 1);
        using (GraphicsPath p = Dibujo.Redondeado(r, r.Height / 2))
        using (SolidBrush b = new SolidBrush(Color.FromArgb(28, 38, 60))) g.FillPath(b, p);
        if (valor <= 0) return;
        float w = (float)Math.Max(r.Height, r.Width * valor);
        RectangleF rf = new RectangleF(r.X, r.Y, w, r.Height);
        using (GraphicsPath p = Dibujo.Redondeado(rf, r.Height / 2))
        {
            using (LinearGradientBrush lg = new LinearGradientBrush(r, Tema.Acento, Tema.Cian, LinearGradientMode.Horizontal)) g.FillPath(lg, p);
            if (valor < 1) Dibujo.Brillo(g, p, rf, brillo, 150, Math.Min(120, rf.Width));
        }
    }
    protected override void Dispose(bool d) { if (d && reloj != null) { reloj.Stop(); reloj.Dispose(); } base.Dispose(d); }
}

/// Boton circular de la barra superior (fijar, minimizar, maximizar, cerrar) con un glifo de Segoe MDL2 Assets.
class BotonCirculo : Control
{
    bool hover;
    public string Glifo = "", GlifoMarcado = null;
    public Color Tono = Color.FromArgb(240, 101, 92);
    public bool Marcable, Marcado;
    public BotonCirculo()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint |
                 ControlStyles.SupportsTransparentBackColor, true);
        BackColor = Color.Transparent;
        Cursor = Cursors.Hand;
    }
    protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
    protected override void OnMouseLeave(EventArgs e) { hover = false; Invalidate(); base.OnMouseLeave(e); }
    protected override void OnClick(EventArgs e) { if (Marcable) { Marcado = !Marcado; Invalidate(); } base.OnClick(e); }
    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAliasGridFit;
        Color c = (Marcable && !Marcado) ? Color.FromArgb(125, 140, 160) : Tono;
        float m = Width * 0.09f;
        RectangleF r = new RectangleF(m, m, Width - 2 * m - 1, Height - 2 * m - 1);
        using (SolidBrush b = new SolidBrush(Color.FromArgb(hover || (Marcable && Marcado) ? 80 : 30, c))) g.FillEllipse(b, r);
        using (Pen p = new Pen(Color.FromArgb(235, c), 1.6f)) g.DrawEllipse(p, r);
        string gl = (Marcable && Marcado && GlifoMarcado != null) ? GlifoMarcado : Glifo;
        using (Font f = new Font("Segoe MDL2 Assets", 9f))
        using (SolidBrush b = new SolidBrush(Color.FromArgb(240, 245, 248)))
        {
            StringFormat sf = new StringFormat();
            sf.Alignment = StringAlignment.Center;
            sf.LineAlignment = StringAlignment.Center;
            g.DrawString(gl, f, b, new RectangleF(0, 1, Width, Height), sf);
        }
    }
}

/// Banner animado: la escena (banner.jpg) con el astrolabio de CineCaptions dibujado capa a capa que GIRA (runas, engranaje y filigrana en
/// sentidos y velocidades distintos), un halo que respira, motas de luz, un destello que cruza de vez en cuando y el titulo que
/// entra deslizandose. Estado: 0 reposo, 1 trabajando (gira mas rapido, halo fuerte), 2 listo (ondas verdes), 3 error (rojo).
/// La escena y los degradados se dibujan UNA vez en una imagen (cache); cada cuadro solo pinta lo que se mueve.
class Banner : Control
{
    public Image Imagen, Logo, CapaRunas, CapaEngr, CapaFili, CapaNucleo;
    public string Titulo = "", Frase = "", Ficha = "";
    public float Esc = 1f;
    int estado;
    public int Estado
    {
        get { return estado; }
        set { if (value != estado) { estado = value; finT = (value >= 2) ? 0f : -1f; } }
    }
    readonly System.Windows.Forms.Timer reloj;
    DateTime ultimo = DateTime.Now;
    float t, giroA, giroB, giroC, vel = 1f, entra, finT = -1f;
    Bitmap cache; Size cacheTam;
    Bitmap bRunas, bEngr, bFili, bNucleo; int ladoCapas;
    struct Mota { public float x, y, vy, vx, r, fase; }
    readonly Mota[] motas = new Mota[70];

    // la escena de la imagen: el astrolabio vive en estas coordenadas de banner.jpg (1760 x 472)
    const float AstroX = 1385f, AstroY = 236f, AstroLado = 400f, ImgAncho = 1760f;

    public Banner()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
        BackColor = Tema.Fondo;
        Random r = new Random(7);
        for (int i = 0; i < motas.Length; i++)
            motas[i] = new Mota { x = (float)r.NextDouble(), y = (float)r.NextDouble(), vy = 0.012f + (float)r.NextDouble() * 0.03f,
                                  vx = ((float)r.NextDouble() - 0.5f) * 0.01f, r = 0.8f + (float)r.NextDouble() * 2.2f, fase = (float)r.NextDouble() * 6.28f };
        reloj = new System.Windows.Forms.Timer();
        reloj.Interval = 33;
        reloj.Tick += delegate { Avanzar(); Invalidate(); };
        reloj.Start();
    }

    void Avanzar()
    {
        DateTime ahora = DateTime.Now;
        float dt = (float)Math.Min(0.1, (ahora - ultimo).TotalSeconds);
        ultimo = ahora;
        t += dt;
        entra = Math.Min(1f, entra + dt / 1.0f);
        float obj = estado == 1 ? 3.4f : estado == 2 ? (finT < 2.5f ? 0.25f : 1f) : estado == 3 ? 0.12f : 1f;
        vel += (obj - vel) * Math.Min(1f, dt * 3f);
        giroA += 2.4f * vel * dt;
        giroB -= 3.6f * vel * dt;
        giroC += 5.6f * vel * dt;
        if (finT >= 0f) finT += dt;
        for (int i = 0; i < motas.Length; i++)
        {
            motas[i].y -= motas[i].vy * dt * (0.6f + 0.4f * vel);
            motas[i].x += motas[i].vx * dt;
            if (motas[i].y < -0.02f) { motas[i].y = 1.02f; }
            if (motas[i].x < 0f) motas[i].x += 1f; else if (motas[i].x > 1f) motas[i].x -= 1f;
        }
    }

    int E(float v) { return (int)Math.Round(v * Esc); }

    Bitmap Escalar(Image img, int lado)
    {
        if (img == null) return null;
        Bitmap b = new Bitmap(lado, lado, System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
        using (Graphics g = Graphics.FromImage(b))
        {
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            g.DrawImage(img, new Rectangle(0, 0, lado, lado));
        }
        return b;
    }

    void Preparar(Rectangle r)
    {
        float esc = Imagen != null ? Math.Max(r.Width / (float)Imagen.Width, r.Height / (float)Imagen.Height) : 1f;
        int lado = Math.Max(16, (int)Math.Round(AstroLado * esc * (Imagen != null ? Imagen.Width / ImgAncho : 1f)));
        if (cache == null || cacheTam != r.Size)
        {
            if (cache != null) cache.Dispose();
            cacheTam = r.Size;
            cache = new Bitmap(Math.Max(1, r.Width), Math.Max(1, r.Height), System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
            using (Graphics g = Graphics.FromImage(cache))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.Clear(Tema.Fondo);
                Rectangle rr = new Rectangle(0, 0, r.Width, r.Height);
                if (Imagen != null)
                {
                    float w = Imagen.Width * esc, h = Imagen.Height * esc;
                    g.DrawImage(Imagen, new RectangleF((r.Width - w) / 2f, (r.Height - h) * 0.45f, w, h));
                }
                // solo se oscurece la zona del titulo (izquierda) y una franja corta abajo para fundirse con la ventana
                using (LinearGradientBrush lg = new LinearGradientBrush(rr, Color.Transparent, Color.Transparent, LinearGradientMode.Horizontal))
                {
                    ColorBlend cb = new ColorBlend();
                    int a0 = Imagen != null ? 246 : 255;
                    cb.Colors = new Color[] { Color.FromArgb(a0, 5, 10, 14), Color.FromArgb(Imagen != null ? 205 : 255, 5, 10, 14),
                                              Color.FromArgb(Imagen != null ? 0 : 255, 5, 10, 14), Color.FromArgb(Imagen != null ? 0 : 255, 5, 10, 14) };
                    cb.Positions = new float[] { 0f, 0.42f, 0.6f, 1f };
                    lg.InterpolationColors = cb;
                    g.FillRectangle(lg, rr);
                }
                using (LinearGradientBrush lg2 = new LinearGradientBrush(rr, Color.Transparent, Color.Transparent, LinearGradientMode.Vertical))
                {
                    ColorBlend cb = new ColorBlend();
                    cb.Colors = new Color[] { Color.FromArgb(0, 8, 12, 20), Color.FromArgb(0, 8, 12, 20), Color.FromArgb(235, 8, 12, 20) };
                    cb.Positions = new float[] { 0f, 0.80f, 1f };
                    lg2.InterpolationColors = cb;
                    g.FillRectangle(lg2, rr);
                }
            }
        }
        if (ladoCapas != lado)
        {
            ladoCapas = lado;
            if (bRunas != null) bRunas.Dispose();
            if (bEngr != null) bEngr.Dispose();
            if (bFili != null) bFili.Dispose();
            if (bNucleo != null) bNucleo.Dispose();
            bRunas = Escalar(CapaRunas, lado); bEngr = Escalar(CapaEngr, lado); bFili = Escalar(CapaFili, lado); bNucleo = Escalar(CapaNucleo, lado);
        }
    }

    void Capa(Graphics g, Bitmap b, float cx, float cy, float giro)
    {
        if (b == null) return;
        GraphicsState s0 = g.Save();
        g.TranslateTransform(cx, cy);
        g.RotateTransform(giro);
        g.DrawImage(b, -b.Width / 2f, -b.Height / 2f, b.Width, b.Height);
        g.Restore(s0);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Rectangle r = ClientRectangle;
        if (r.Width < 8 || r.Height < 8) return;
        Preparar(r);
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.InterpolationMode = InterpolationMode.HighQualityBilinear;
        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
        g.DrawImageUnscaled(cache, 0, 0);
        // posicion del astrolabio en el control (misma transformacion que la imagen)
        float esc = Imagen != null ? Math.Max(r.Width / (float)Imagen.Width, r.Height / (float)Imagen.Height) : 1f;
        float k = Imagen != null ? esc * Imagen.Width / ImgAncho : 1f;
        float ox = Imagen != null ? (r.Width - Imagen.Width * esc) / 2f : 0f, oy = Imagen != null ? (r.Height - Imagen.Height * esc) * 0.45f : 0f;
        float ek = Imagen != null ? esc * Imagen.Width / ImgAncho : 1f;
        float cx = ox + AstroX * ek, cy = oy + AstroY * ek;
        Color col = estado == 3 ? Color.FromArgb(255, 90, 90) : Color.FromArgb(58, 230, 140);
        // el halo que respira
        float pulso = 0.5f + 0.5f * (float)Math.Sin(t * 1.6);
        float radio = AstroLado * 0.95f * ek;
        int alfaHalo = (int)((estado == 1 ? 80 : 46) + 26 * pulso);
        using (GraphicsPath gp = new GraphicsPath())
        {
            gp.AddEllipse(cx - radio, cy - radio, radio * 2, radio * 2);
            using (PathGradientBrush pg = new PathGradientBrush(gp))
            {
                pg.CenterColor = Color.FromArgb(alfaHalo, col);
                pg.SurroundColors = new Color[] { Color.FromArgb(0, col) };
                g.FillPath(pg, gp);
            }
        }
        // las capas giratorias y el nucleo fijo
        Capa(g, bRunas, cx, cy, giroA);
        Capa(g, bEngr, cx, cy, giroB);
        Capa(g, bFili, cx, cy, giroC);
        if (bNucleo != null) g.DrawImageUnscaled(bNucleo, (int)(cx - bNucleo.Width / 2f), (int)(cy - bNucleo.Height / 2f));
        // ondas al terminar
        if (finT >= 0f && finT < 2.4f)
            for (int i = 0; i < 3; i++)
            {
                float u = (finT - i * 0.22f) / 1.6f;
                if (u <= 0f || u >= 1f) continue;
                float rr = (60f + 700f * (1f - (float)Math.Pow(1f - u, 2.4))) * ek;
                using (Pen p = new Pen(Color.FromArgb((int)(190 * (1f - u) * (1f - u)), estado == 3 ? Color.FromArgb(255, 110, 110) : Color.FromArgb(120, 255, 190)), 2.4f * ek + 6f * u))
                    g.DrawEllipse(p, cx - rr, cy - rr * 0.92f, rr * 2, rr * 1.84f);
            }
        // motas de luz (a la derecha, donde vive la escena)
        float x0 = r.Width * 0.40f, ancho = r.Width - x0;
        using (SolidBrush sb = new SolidBrush(Color.White))
            for (int i = 0; i < motas.Length; i++)
            {
                float tw = 0.5f + 0.5f * (float)Math.Sin(t * 2.2f + motas[i].fase);
                int a = (int)(40 + 150 * tw);
                float x = x0 + motas[i].x * ancho, y = motas[i].y * r.Height, rad = motas[i].r * Math.Max(0.8f, ek * 0.9f);
                sb.Color = i % 3 == 0 ? Color.FromArgb(a, 150, 255, 200) : i % 3 == 1 ? Color.FromArgb(a, 255, 255, 255) : Color.FromArgb(a, 90, 220, 255);
                g.FillEllipse(sb, x - rad, y - rad, rad * 2, rad * 2);
            }
        // un destello diagonal que cruza cada ~7 s
        float fase = (t % 7f) / 7f * 1.6f - 0.3f;
        if (fase > -0.2f && fase < 1.2f)
        {
            float bx = r.Width * fase;
            PointF[] banda = { new PointF(bx, 0), new PointF(bx + r.Width * 0.10f, 0), new PointF(bx - r.Width * 0.06f, r.Height), new PointF(bx - r.Width * 0.16f, r.Height) };
            using (LinearGradientBrush lb = new LinearGradientBrush(new RectangleF(bx - r.Width * 0.16f, 0, r.Width * 0.26f, r.Height), Color.Transparent, Color.Transparent, 0f))
            {
                ColorBlend cb = new ColorBlend();
                cb.Colors = new Color[] { Color.FromArgb(0, 255, 255, 255), Color.FromArgb(34, 190, 255, 225), Color.FromArgb(0, 255, 255, 255) };
                cb.Positions = new float[] { 0f, 0.5f, 1f };
                lb.InterpolationColors = cb;
                g.FillPolygon(lb, banda);
            }
        }
        // logo + CINECAPTIONS + titulo (entran deslizandose)
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAlias;
        float u0 = 1f - (float)Math.Pow(1f - entra, 3);
        int x1 = E(38), y1 = E(32);
        float desl = (1f - u0) * E(22);
        int al = (int)(255 * u0);
        if (Logo != null) { g.DrawImage(Logo, new Rectangle(x1 - (int)desl, y1, E(40), E(40))); x1 += E(52); }
        using (Font f = new Font("Segoe UI", 15f, FontStyle.Bold))
        using (SolidBrush b1 = new SolidBrush(Color.FromArgb(al, 255, 255, 255)))
        using (SolidBrush b2 = new SolidBrush(Color.FromArgb(al, 58, 230, 140)))
        {
            SizeF s1 = g.MeasureString("CINE", f, 1000, StringFormat.GenericTypographic);
            g.DrawString("CINE", f, b1, x1 - desl, y1 + E(6), StringFormat.GenericTypographic);
            g.DrawString("CAPTIONS", f, b2, x1 - desl + s1.Width + E(1), y1 + E(6), StringFormat.GenericTypographic);
        }
        float u1 = Math.Max(0f, Math.Min(1f, (entra - 0.15f) / 0.85f)); u1 = 1f - (float)Math.Pow(1f - u1, 3);
        using (Font f = new Font("Segoe UI", 26f, FontStyle.Bold))
        using (SolidBrush b = new SolidBrush(Color.FromArgb((int)(255 * u1), 255, 255, 255)))
            g.DrawString(Titulo, f, b, E(33) - (1f - u1) * E(26), E(88), StringFormat.GenericTypographic);
        float u2 = Math.Max(0f, Math.Min(1f, (entra - 0.3f) / 0.7f)); u2 = 1f - (float)Math.Pow(1f - u2, 3);
        using (Font f = new Font("Segoe UI", 12f))
        using (SolidBrush b = new SolidBrush(Color.FromArgb((int)(255 * u2), 205, 218, 238)))
            g.DrawString(Frase, f, b, E(38) - (1f - u2) * E(26), E(140), StringFormat.GenericTypographic);
        float u3 = Math.Max(0f, Math.Min(1f, (entra - 0.45f) / 0.55f)); u3 = 1f - (float)Math.Pow(1f - u3, 3);
        using (Font f = new Font("Segoe UI", 9.5f, FontStyle.Bold))
        {
            SizeF s = g.MeasureString(Ficha, f, 2000, StringFormat.GenericTypographic);
            RectangleF rc = new RectangleF(E(38) - (1f - u3) * E(26), E(176), s.Width + E(24), s.Height + E(12));
            using (SolidBrush b = new SolidBrush(Color.FromArgb((int)(225 * u3), 10, 36, 30))) g.FillRectangle(b, rc);
            using (Pen p = new Pen(Color.FromArgb((int)(120 * u3), 58, 230, 140), 1f)) g.DrawRectangle(p, rc.X, rc.Y, rc.Width, rc.Height);
            using (SolidBrush b = new SolidBrush(Color.FromArgb((int)(255 * u3), 120, 255, 200)))
                g.DrawString(Ficha, f, b, rc.X + E(12), rc.Y + E(6), StringFormat.GenericTypographic);
        }
    }

    protected override void Dispose(bool d)
    {
        if (d)
        {
            if (reloj != null) { reloj.Stop(); reloj.Dispose(); }
            if (cache != null) cache.Dispose();
            if (bRunas != null) bRunas.Dispose();
            if (bEngr != null) bEngr.Dispose();
            if (bFili != null) bFili.Dispose();
            if (bNucleo != null) bNucleo.Dispose();
        }
        base.Dispose(d);
    }
}

/// La lista de PASOS: un circulo por paso (· pendiente, arco que gira = en curso, ✓ hecho con un saltito, ! aviso, ✗ error, – omitido)
/// y el nombre, a color. El paso en curso late y su circulo gira (reloj de 40 ms solo mientras hay uno en curso).
class ListaPasos : Control
{
    public List<Paso> Pasos;
    public float Esc = 1f;
    readonly System.Windows.Forms.Timer reloj;
    float fase;
    readonly Dictionary<Paso, float> popup = new Dictionary<Paso, float>();
    readonly Dictionary<Paso, EstadoPaso> vistos = new Dictionary<Paso, EstadoPaso>();
    public ListaPasos()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
        BackColor = Tema.Fondo;
        reloj = new System.Windows.Forms.Timer();
        reloj.Interval = 33;
        reloj.Tick += delegate
        {
            fase += 0.045f;
            bool hay = false;
            if (Pasos != null)
                foreach (Paso p in Pasos)
                {
                    if (p.Estado == EstadoPaso.EnCurso) hay = true;
                    EstadoPaso antes;
                    if (!vistos.TryGetValue(p, out antes)) antes = EstadoPaso.Pendiente;
                    if (antes != p.Estado) { vistos[p] = p.Estado; if (p.Estado == EstadoPaso.Hecho) popup[p] = 0f; }
                }
            List<Paso> fin = new List<Paso>();
            foreach (Paso p in new List<Paso>(popup.Keys)) { popup[p] += 0.06f; hay = true; if (popup[p] >= 1f) fin.Add(p); }
            foreach (Paso p in fin) popup.Remove(p);
            if (hay) Invalidate();
        };
        reloj.Start();
    }
    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;
        using (Font fp = new Font("Segoe UI", 9f, FontStyle.Bold))
            TextRenderer.DrawText(g, "PASOS", fp, new Point((int)(4 * Esc), 0), Tema.Suave, TextFormatFlags.NoPadding);
        if (Pasos == null) return;
        using (Font f = new Font("Segoe UI", 10.5f))
        using (Font fb = new Font("Segoe UI", 10.5f, FontStyle.Bold))
        {
            int y = (int)(26 * Esc), alto = (int)(32 * Esc);
            foreach (Paso p in Pasos)
            {
                Color c;
                switch (p.Estado)
                {
                    case EstadoPaso.EnCurso: c = Tema.EnCurso; break;
                    case EstadoPaso.Hecho: c = Tema.Ok; break;
                    case EstadoPaso.Aviso: c = Tema.Aviso; break;
                    case EstadoPaso.Error: c = Tema.Error; break;
                    default: c = Tema.Pendiente; break;
                }
                float cx = 13 * Esc, cy = y + alto / 2f, rad = 8.5f * Esc;
                float pop = 0f;
                if (popup.ContainsKey(p)) pop = (float)Math.Sin(popup[p] * Math.PI) * 0.35f;
                rad *= 1f + pop;
                if (p.Estado == EstadoPaso.EnCurso)
                {
                    float late = 0.5f + 0.5f * (float)Math.Sin(fase * 2.2f);
                    using (SolidBrush b = new SolidBrush(Color.FromArgb((int)(30 + 40 * late), c))) g.FillEllipse(b, cx - rad * 1.7f, cy - rad * 1.7f, rad * 3.4f, rad * 3.4f);
                    using (Pen pp = new Pen(Color.FromArgb(70, c), 2f * Esc)) g.DrawEllipse(pp, cx - rad, cy - rad, rad * 2, rad * 2);
                    using (Pen pa = new Pen(c, 2.6f * Esc)) { pa.StartCap = LineCap.Round; pa.EndCap = LineCap.Round; g.DrawArc(pa, cx - rad, cy - rad, rad * 2, rad * 2, fase * 360f / 1.2f, 110f); }
                }
                else if (p.Estado == EstadoPaso.Hecho)
                {
                    using (SolidBrush b = new SolidBrush(c)) g.FillEllipse(b, cx - rad, cy - rad, rad * 2, rad * 2);
                    using (Pen pc = new Pen(Color.FromArgb(6, 22, 14), 2.2f * Esc))
                    {
                        pc.StartCap = LineCap.Round; pc.EndCap = LineCap.Round; pc.LineJoin = LineJoin.Round;
                        g.DrawLines(pc, new PointF[] { new PointF(cx - rad * 0.45f, cy + rad * 0.02f), new PointF(cx - rad * 0.1f, cy + rad * 0.38f), new PointF(cx + rad * 0.5f, cy - rad * 0.34f) });
                    }
                }
                else if (p.Estado == EstadoPaso.Aviso || p.Estado == EstadoPaso.Error)
                {
                    using (SolidBrush b = new SolidBrush(c)) g.FillEllipse(b, cx - rad, cy - rad, rad * 2, rad * 2);
                    TextRenderer.DrawText(g, p.Estado == EstadoPaso.Aviso ? "!" : "✗", fb, new Rectangle((int)(cx - rad), (int)(cy - rad), (int)(rad * 2), (int)(rad * 2)),
                                          Color.FromArgb(10, 14, 20), TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix);
                }
                else
                {
                    using (Pen pp = new Pen(Color.FromArgb(120, c), 1.6f * Esc)) g.DrawEllipse(pp, cx - rad, cy - rad, rad * 2, rad * 2);
                    if (p.Estado == EstadoPaso.Omitido) using (Pen pp = new Pen(c, 1.6f * Esc)) g.DrawLine(pp, cx - rad * 0.4f, cy, cx + rad * 0.4f, cy);
                }
                string t = p.Titulo;
                if (p.Estado == EstadoPaso.EnCurso && p.Progreso >= 0 && p.Progreso < 100) t += "   " + p.Progreso + " %";
                TextRenderer.DrawText(g, t, p.Estado == EstadoPaso.EnCurso ? fb : f, new Rectangle((int)(34 * Esc), y, Width - (int)(34 * Esc), alto), p.Estado == EstadoPaso.EnCurso ? Color.White : c,
                                      TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix);
                y += alto;
            }
        }
    }
    protected override void Dispose(bool d) { if (d && reloj != null) { reloj.Stop(); reloj.Dispose(); } base.Dispose(d); }
}

/// Una carpeta o archivo que toca la instalacion: donde va cada cosa.
class RutaInfo
{
    public string Titulo, Ruta, Nota, Libre;
    public bool Editable;
    public bool Existe { get { try { return Directory.Exists(Ruta) || File.Exists(Ruta); } catch { return false; } } }
}

/// La lista de RUTAS DE INSTALACION: cada fila con su titulo, la ruta completa, una nota (tamano, si ya esta) y los enlaces
/// «Cambiar» (solo la del programa) y «Abrir» (si ya existe).
class ListaRutas : Control
{
    public List<RutaInfo> Items = new List<RutaInfo>();
    public float Esc = 1f;
    public event Action<int> Cambiar;
    public event Action<int> Abrir;
    int hover = -1, hoverEnlace = -1;           // fila y enlace (0 = cambiar, 1 = abrir)
    readonly List<Rectangle[]> zonas = new List<Rectangle[]>();
    public ListaRutas()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
        BackColor = Tema.FondoLog;
    }
    public int AltoFila { get { return (int)(35 * Esc); } }
    protected override void OnMouseMove(MouseEventArgs e)
    {
        int f = -1, l = -1;
        for (int i = 0; i < zonas.Count; i++)
        {
            for (int k = 0; k < 2; k++) if (zonas[i][k].Contains(e.Location)) { f = i; l = k; }
            if (f < 0 && i * AltoFila <= e.Y && e.Y < (i + 1) * AltoFila) f = i;
        }
        if (f != hover || l != hoverEnlace) { hover = f; hoverEnlace = l; Cursor = l >= 0 ? Cursors.Hand : Cursors.Default; Invalidate(); }
        base.OnMouseMove(e);
    }
    protected override void OnMouseLeave(EventArgs e) { hover = -1; hoverEnlace = -1; Invalidate(); base.OnMouseLeave(e); }
    protected override void OnMouseClick(MouseEventArgs e)
    {
        if (hover >= 0 && hoverEnlace == 0 && Cambiar != null) Cambiar(hover);
        else if (hover >= 0 && hoverEnlace == 1 && Abrir != null) Abrir(hover);
        base.OnMouseClick(e);
    }
    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;
        zonas.Clear();
        int ah = AltoFila, pad = (int)(14 * Esc);
        using (Font ft = new Font("Segoe UI", 9f, FontStyle.Bold))
        using (Font fr = new Font("Consolas", 8f))
        using (Font fn = new Font("Segoe UI", 8f))
        using (Font fe = new Font("Segoe UI", 9f, FontStyle.Bold))
        {
            for (int i = 0; i < Items.Count; i++)
            {
                RutaInfo it = Items[i];
                int y = i * ah;
                if (i == hover) using (SolidBrush b = new SolidBrush(Color.FromArgb(18, 255, 255, 255))) g.FillRectangle(b, 0, y, Width, ah);
                if (i > 0) using (Pen p = new Pen(Color.FromArgb(24, 255, 255, 255))) g.DrawLine(p, pad, y, Width - pad, y);
                // punto de estado: verde si ya existe, gris si se creara
                using (SolidBrush b = new SolidBrush(it.Existe ? Tema.Ok : Tema.Pendiente)) g.FillEllipse(b, pad, y + ah / 2f - 3.5f * Esc, 7 * Esc, 7 * Esc);
                int x = pad + (int)(18 * Esc);
                int ancho = Width - x - pad;
                // enlaces a la derecha
                int xe = Width - pad;
                Rectangle[] z = new Rectangle[] { Rectangle.Empty, Rectangle.Empty };
                if (it.Existe)
                {
                    Size s = TextRenderer.MeasureText(g, "Abrir", fe, Size.Empty, TextFormatFlags.NoPadding);
                    xe -= s.Width; z[1] = new Rectangle(xe, y + (int)(4 * Esc), s.Width, ah / 2 - (int)(4 * Esc));
                    TextRenderer.DrawText(g, "Abrir", fe, z[1], (i == hover && hoverEnlace == 1) ? Color.White : Tema.Cian, TextFormatFlags.NoPadding | TextFormatFlags.VerticalCenter);
                    xe -= (int)(14 * Esc);
                }
                if (it.Editable)
                {
                    Size s = TextRenderer.MeasureText(g, "Cambiar…", fe, Size.Empty, TextFormatFlags.NoPadding);
                    xe -= s.Width; z[0] = new Rectangle(xe, y + (int)(4 * Esc), s.Width, ah / 2 - (int)(4 * Esc));
                    TextRenderer.DrawText(g, "Cambiar…", fe, z[0], (i == hover && hoverEnlace == 0) ? Color.White : Tema.Cian, TextFormatFlags.NoPadding | TextFormatFlags.VerticalCenter);
                }
                zonas.Add(z);
                int limite = Math.Max(40, xe - x - (int)(10 * Esc));
                TextRenderer.DrawText(g, it.Titulo, ft, new Rectangle(x, y + (int)(3 * Esc), limite, ah / 2 - (int)(2 * Esc)), Color.White,
                                      TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
                string linea2 = it.Ruta;
                TextRenderer.DrawText(g, linea2, fr, new Rectangle(x, y + ah / 2 - (int)(1 * Esc), (int)(ancho * 0.60f), ah / 2 - (int)(2 * Esc)), Tema.Suave,
                                      TextFormatFlags.PathEllipsis | TextFormatFlags.NoPrefix | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
                string nota = it.Nota + (string.IsNullOrEmpty(it.Libre) ? "" : "  ·  " + it.Libre);
                int xn = x + (int)(ancho * 0.62f);
                TextRenderer.DrawText(g, nota, fn, new Rectangle(xn, y + ah / 2 - (int)(1 * Esc), Width - xn - pad, ah / 2 - (int)(2 * Esc)), Tema.Pendiente,
                                      TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.Right);
            }
        }
    }
}

class Ventana : Form
{
    readonly Opciones op;
    public int CodigoSalida = 0;
    Instalacion ins;
    Thread hilo;
    bool trabajando, terminado;
    float esc = 1f;
    const int AltoBanner = 236, AnchoBase = 880, AltoBase = 580, ExtraDetalles = 230, ExtraRutas = 340;
    string panel = "";                                        // el panel de abajo: "" (cerrado), "log" o "rutas"
    bool detallesAbiertos { get { return panel == "log"; } }
    ListaRutas rutas;
    LinkLabel lnkRutas;
    Panel sep;
    bool verRutas;

    Banner banner;
    BotonCirculo bPin, bMin, bMax, bCer;
    Panel cuerpo;
    ListaPasos lista;
    Label lblEstado, lblInfo, lblFirma;
    BarraModerna barra;
    BotonPildora boton;
    LinkLabel lnkDetalles, lnkOmitir;
    CheckBox chkDatos, chkModelos;
    PictureBox picMarca;
    RichTextBox log;

    public Ventana(Opciones op)
    {
        this.op = op;
        using (Graphics g = CreateGraphics()) esc = g.DpiX / 96f;
        Text = op.Desinstalar ? "Desinstalar " + Programa.Nombre : "Instalar " + Programa.Nombre;
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Tema.Fondo;
        ForeColor = Color.White;
        ClientSize = new Size(E(AnchoBase), E(AltoBase));
        MinimumSize = new Size(E(AnchoBase), E(AltoBase));
        DoubleBuffered = true;
        Opacity = 0;                      // entra con un fundido (Entrar)
        TopMost = true;                   // como CineSlide: al frente (la chincheta lo quita)
        ins = new Instalacion(op, this);
        Armar();
        if (op.Desinstalar && op.YaReubicado) ProgramarAutoBorrado();     // la copia en %TEMP% se va tambien si se cancela
        Resize += delegate { Centrar(); };
        Shown += delegate
        {
            Centrar();
            Dibujo.Oscuro(log);
            Activate();
            Entrar();
            if (op.Desinstalar) CalcularTamanos();
            if (!op.Desinstalar || op.Empezar) Empezar();     // doble clic = instala solo; desinstalar espera el boton (las rutas se ven con el enlace, sin cambiar el flujo)
        };
    }

    int E(float v) { return (int)Math.Round(v * esc); }

    static Image Recurso(string nombre)
    {
        try { return Image.FromStream(Assembly.GetExecutingAssembly().GetManifestResourceStream(nombre)); } catch { return null; }
    }

    void Armar()
    {
        // ---------------- banner
        banner = new Banner();
        banner.Esc = esc;
        banner.Dock = DockStyle.Top;
        banner.Height = E(AltoBanner);
        banner.Imagen = Recurso("banner.jpg");
        banner.Logo = Recurso("logo.png");
        banner.CapaRunas = Recurso("astro_runas.png");
        banner.CapaEngr = Recurso("astro_engr.png");
        banner.CapaFili = Recurso("astro_fili.png");
        banner.CapaNucleo = Recurso("astro_nucleo.png");
        banner.Titulo = op.Desinstalar ? "Desinstalar CineCaptions" : "Instalar CineCaptions";
        banner.Frase = "Subtítulos automáticos para DaVinci Resolve";
        banner.Ficha = op.Desinstalar ? "limpieza completa  ·  tú eliges qué se conserva"
                                      : "v" + Programa.Version + "  ·  todo incluido  ·  no necesita Python";
        banner.MouseDown += delegate(object s, MouseEventArgs e) { if (e.Button == MouseButtons.Left) Dibujo.Arrastrar(this); };
        banner.DoubleClick += delegate { Maximizar(); };
        Controls.Add(banner);

        // ---------------- botones de ventana
        bPin = Circulo("", Color.FromArgb(0, 200, 255), "Fijar al frente");
        bPin.Marcable = true; bPin.GlifoMarcado = ""; bPin.Marcado = true;
        bPin.Click += delegate { TopMost = bPin.Marcado; };
        bMin = Circulo("", Color.FromArgb(109, 157, 240), "Minimizar");
        bMin.Click += delegate { WindowState = FormWindowState.Minimized; };
        bMax = Circulo("", Color.FromArgb(95, 214, 160), "Maximizar / restaurar");
        bMax.Click += delegate { Maximizar(); };
        bCer = Circulo("", Color.FromArgb(240, 101, 92), "Cerrar");
        bCer.Click += delegate { Close(); };

        // ---------------- cuerpo (centrado; crece hacia abajo con los detalles)
        cuerpo = new Panel();
        cuerpo.BackColor = Tema.Fondo;
        cuerpo.Size = new Size(E(AnchoBase), E(AltoBase - AltoBanner));
        Controls.Add(cuerpo);
        cuerpo.BringToFront();

        lista = new ListaPasos();
        lista.Esc = esc;
        lista.Pasos = ins.Pasos;
        lista.SetBounds(E(36), E(16), E(372), E(30 + 32 * ins.Pasos.Count));
        cuerpo.Controls.Add(lista);

        sep = new Panel();
        sep.BackColor = Tema.Linea;
        sep.SetBounds(E(424), E(18), Math.Max(1, E(1)), E(290));
        cuerpo.Controls.Add(sep);

        lblEstado = Etiqueta(op.Desinstalar ? "Listo para desinstalar" : "Preparando la instalación...", 14f, true, Color.White);
        lblEstado.SetBounds(E(450), E(30), E(400), E(64));
        barra = new BarraModerna();
        barra.SetBounds(E(452), E(104), E(396), E(14));
        cuerpo.Controls.Add(barra);
        lblInfo = Etiqueta(TextoInfo(), 9.5f, false, Tema.Suave);
        lblInfo.SetBounds(E(450), E(132), E(400), E(70));
        lblInfo.AutoEllipsis = true;
        if (op.Desinstalar)
        {
            // las dos casillas de la limpieza completa (marcadas: «sin dejar rastro»); los tamaños se calculan aparte, sin frenar la ventana
            chkDatos = Casilla("Borrar mis datos, licencia y ajustes", E(450), E(128), op.BorrarDatos || !op.Silencioso);
            chkModelos = Casilla("Borrar los modelos de voz e idioma descargados", E(450), E(158), op.BorrarModelos || !op.Silencioso);
            new ToolTip().SetToolTip(chkDatos, "DaVinciSubtitles: proyectos, marcas, ajustes, caches y copias de seguridad. También libera la licencia de este equipo.");
            new ToolTip().SetToolTip(chkModelos, "Whisper, Qwen3 y los paquetes de traducción que bajó CineCaptions. Si otro programa usa los mismos modelos, los volverá a bajar.");
            lblInfo.SetBounds(E(450), E(188), E(400), E(20));
        }

        boton = new BotonPildora();
        boton.Text = op.Desinstalar ? "DESINSTALAR" : "INSTALAR";
        if (op.Desinstalar) boton.Colores(Color.FromArgb(226, 92, 80), Color.FromArgb(150, 44, 60));
        boton.SetBounds(E(452), E(211), E(398), E(56));
        boton.Click += delegate
        {
            if (!boton.Enabled) return;
            if (terminado && !ins.HuboError) Close();
            else if (terminado && !op.Desinstalar) Reintentar();
            else if (terminado) Close();
            else Empezar();
        };
        cuerpo.Controls.Add(boton);

        lnkDetalles = Enlace("Ver detalles", E(452), E(284));
        lnkDetalles.LinkClicked += delegate { AlternarDetalles(); };
        lnkOmitir = Enlace("Omitir la descarga (se hará al transcribir)", E(560), E(284));
        lnkOmitir.Visible = false;
        lnkOmitir.LinkClicked += delegate { lnkOmitir.Enabled = false; lnkOmitir.Text = "Omitiendo..."; ins.OmitirDescarga(); };

        // v5.3.5: la firma es el LOGO «CINEMA PRODUCTIONS» (blanco, transparente, atenuado) en vez del texto «By Cinema Productions»; sin el recurso queda el texto de siempre
        Image marca = Recurso("marca.png");
        if (marca != null)
        {
            lblFirma = Etiqueta("CineCaptions", 9f, false, Color.FromArgb(78, 96, 126));
            lblFirma.SetBounds(E(40), E(314), E(74), E(20));
            int altoM = E(15), anchoM = (int)Math.Round(altoM * (double)marca.Width / marca.Height);
            Bitmap tenue = new Bitmap(anchoM, altoM);
            using (Graphics g = Graphics.FromImage(tenue))
            using (ImageAttributes ia = new ImageAttributes())
            {
                ColorMatrix cm = new ColorMatrix();
                cm.Matrix33 = 0.62f;                                              // opacidad: que acompañe sin gritar
                ia.SetColorMatrix(cm);
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.DrawImage(marca, new Rectangle(0, 0, anchoM, altoM), 0, 0, marca.Width, marca.Height, GraphicsUnit.Pixel, ia);
            }
            picMarca = new PictureBox();
            picMarca.Image = tenue;
            picMarca.SizeMode = PictureBoxSizeMode.Normal;
            picMarca.BackColor = Tema.Fondo;
            picMarca.SetBounds(E(40) + E(74), E(317), anchoM, altoM);
            cuerpo.Controls.Add(picMarca);
        }
        else
        {
            lblFirma = Etiqueta("CineCaptions  ·  By Cinema Productions", 9f, false, Color.FromArgb(78, 96, 126));
            lblFirma.SetBounds(E(40), E(314), E(380), E(20));
        }

        lnkRutas = Enlace("Rutas de instalación", E(452), E(306));
        lnkRutas.Visible = !op.Desinstalar;
        lnkRutas.BringToFront();
        lnkRutas.LinkClicked += delegate { AlternarRutas(); };
        rutas = new ListaRutas();
        rutas.Esc = esc;
        rutas.SetBounds(E(36), E(8), E(812), E(284));
        rutas.Visible = false;
        rutas.Cambiar += CambiarCarpeta;
        rutas.Abrir += AbrirRuta;
        cuerpo.Controls.Add(rutas);
        log = new RichTextBox();
        log.SetBounds(E(36), E(344), E(812), E(ExtraDetalles - 16));
        log.ReadOnly = true;
        log.BackColor = Tema.FondoLog;
        log.ForeColor = Color.FromArgb(170, 190, 210);
        log.Font = new Font("Consolas", 8.5f);
        log.BorderStyle = BorderStyle.None;
        log.Visible = false;
        cuerpo.Controls.Add(log);
    }

    string TextoInfo()
    {
        string carpeta = op.Dir.Replace(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "%USERPROFILE%");
        if (op.Desinstalar)
            return "Se quita el programa, sus motores, scripts, tipografías y accesos. Lo marcado arriba se borra para siempre.";
        string t = "Se instala solo para tu usuario (sin permisos de administrador) en " + carpeta +
                   ". Tus proyectos, tu licencia y tus ajustes no se tocan.";
        string v = Registro.LeerHKCU(Programa.ClaveDesinstalar, "DisplayVersion");
        if (v != null) t += " Reemplaza la versión " + v + " ya instalada.";
        return t;
    }

    BotonCirculo Circulo(string glifo, Color tono, string ayuda)
    {
        BotonCirculo b = new BotonCirculo();
        b.Glifo = glifo; b.Tono = tono;
        b.Size = new Size(E(34), E(34));
        new ToolTip().SetToolTip(b, ayuda);
        banner.Controls.Add(b);
        return b;
    }

    Label Etiqueta(string texto, float tam, bool negrita, Color color)
    {
        Label l = new Label();
        l.Text = texto;
        l.Font = new Font("Segoe UI", tam, negrita ? FontStyle.Bold : FontStyle.Regular);
        l.ForeColor = color;
        l.BackColor = Tema.Fondo;
        cuerpo.Controls.Add(l);
        return l;
    }

    CheckBox Casilla(string texto, int x, int y, bool marcada)
    {
        CheckBox c = new CheckBox();
        c.Text = texto;
        c.Checked = marcada;
        c.Font = new Font("Segoe UI", 9.5f);
        c.ForeColor = Color.White;
        c.BackColor = Tema.Fondo;
        c.FlatStyle = FlatStyle.Flat;
        c.FlatAppearance.BorderColor = Color.FromArgb(110, 150, 200);
        c.FlatAppearance.CheckedBackColor = Color.FromArgb(40, 80, 130);
        c.SetBounds(x, y, E(402), E(26));
        cuerpo.Controls.Add(c);
        return c;
    }

    // Tamaño de lo que se borraria, para ponerlo en las casillas (en un hilo: son GB y miles de archivos)
    void CalcularTamanos()
    {
        Thread t = new Thread(delegate()
        {
            long datos = 0, modelos = 0;
            try { datos = Tamano(Sitio.DatosUsuario); } catch { }
            try { foreach (string m in Instalacion.RutasDeModelos()) modelos += Tamano(m); } catch { }
            try
            {
                BeginInvoke(new MethodInvoker(delegate
                {
                    if (chkDatos != null && datos > 0) chkDatos.Text = "Borrar mis datos, licencia y ajustes (" + GBtxt(datos) + ")";
                    if (chkModelos != null && modelos > 0) chkModelos.Text = "Borrar los modelos de voz e idioma (" + GBtxt(modelos) + ")";
                }));
            }
            catch { }
        });
        t.IsBackground = true;
        t.Start();
    }

    static string GBtxt(long b) { return b >= 1073741824L ? string.Format("{0:N1} GB", b / 1073741824.0) : string.Format("{0:N0} MB", b / 1048576.0); }

    static long Tamano(string dir)
    {
        long t = 0;
        try
        {
            if (!Directory.Exists(dir)) return 0;
            foreach (string f in Directory.GetFiles(dir, "*", SearchOption.AllDirectories)) { try { t += new FileInfo(f).Length; } catch { } }
        }
        catch { }
        return t;
    }

    LinkLabel Enlace(string texto, int x, int y)
    {
        LinkLabel d = new LinkLabel();
        d.Text = texto;
        d.LinkColor = Color.FromArgb(110, 150, 200);
        d.ActiveLinkColor = Color.White;
        d.LinkBehavior = LinkBehavior.HoverUnderline;
        d.Font = new Font("Segoe UI", 9.5f);
        d.BackColor = Tema.Fondo;
        d.Location = new Point(x, y);
        d.AutoSize = true;
        cuerpo.Controls.Add(d);
        return d;
    }

    void Maximizar() { WindowState = WindowState == FormWindowState.Maximized ? FormWindowState.Normal : FormWindowState.Maximized; }

    void Centrar()
    {
        int x = ClientSize.Width - E(4 * 42 + 14);
        foreach (BotonCirculo b in new BotonCirculo[] { bPin, bMin, bMax, bCer }) { b.Location = new Point(x, E(14)); x += E(42); }
        cuerpo.Left = Math.Max(0, (ClientSize.Width - cuerpo.Width) / 2);
        cuerpo.Top = banner.Height + Math.Max(0, (ClientSize.Height - banner.Height - cuerpo.Height) / 2);
        if (WindowState == FormWindowState.Maximized) Region = null;
        else using (GraphicsPath p = Dibujo.Redondeado(new RectangleF(0, 0, Width, Height), E(18))) Region = new Region(p);
        Invalidate();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        if (WindowState == FormWindowState.Maximized) return;
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using (Pen pen = new Pen(Color.FromArgb(48, 80, 130), 2))
        using (GraphicsPath p = Dibujo.Redondeado(new RectangleF(1, 1, Width - 2, Height - 2), E(18)))
            e.Graphics.DrawPath(pen, p);
    }

    int ExtraDe(string modo) { return modo == "log" ? ExtraDetalles : 0; }

    /// Abre el panel de abajo (registro o rutas), o lo cierra si ya era ese. La ventana crece hacia abajo.
    void MostrarPanel(string modo)
    {
        if (panel == modo) modo = "";
        int antes = E(ExtraDe(panel)), despues = E(ExtraDe(modo));
        panel = modo;
        log.Visible = modo == "log";
        if (WindowState != FormWindowState.Maximized)
        {
            // el minimo se pone despues de crecer y antes de encoger (si no, el minimo nuevo ya estira la ventana)
            MinimumSize = new Size(E(AnchoBase), E(AltoBase));
            ClientSize = new Size(ClientSize.Width, ClientSize.Height + (despues - antes));
            MinimumSize = new Size(E(AnchoBase), E(AltoBase) + despues);
            Rectangle area = Screen.FromControl(this).WorkingArea;
            if (Bottom > area.Bottom) Top = Math.Max(area.Top, area.Bottom - Height);
        }
        cuerpo.Height = E(AltoBase - AltoBanner) + despues;
        lnkDetalles.Text = modo == "log" ? "Ocultar detalles" : "Ver detalles";
        Centrar();
    }

    void AlternarDetalles() { MostrarPanel("log"); }

    /// La pagina de RUTAS cubre el cuerpo de la ventana (con el boton principal abajo a la derecha y «Volver» a la izquierda).
    void AlternarRutas()
    {
        verRutas = !verRutas;
        if (verRutas && panel == "log") MostrarPanel("log");          // el registro se cierra: no cabrian los dos
        lista.Visible = !verRutas; sep.Visible = !verRutas; lblEstado.Visible = !verRutas; barra.Visible = !verRutas;
        lblInfo.Visible = !verRutas; lblFirma.Visible = !verRutas; lnkDetalles.Visible = !verRutas;
        if (picMarca != null) picMarca.Visible = !verRutas;
        rutas.Visible = verRutas;
        boton.Bounds = verRutas ? new Rectangle(E(452), E(296), E(398), E(44)) : new Rectangle(E(452), E(211), E(398), E(56));
        lnkRutas.Text = verRutas ? "←  Volver a los pasos" : "Rutas de instalación";
        lnkRutas.Location = verRutas ? new Point(E(40), E(308)) : new Point(E(452), E(306));
        if (verRutas) RefrescarRutas();
    }

    void Entrar()
    {
        System.Windows.Forms.Timer t = new System.Windows.Forms.Timer();
        t.Interval = 16;
        t.Tick += delegate { Opacity = Math.Min(1.0, Opacity + 0.08); if (Opacity >= 1.0) { t.Stop(); t.Dispose(); } };
        t.Start();
    }

    /// Antes de instalar: se ven todas las rutas y se espera al boton INSTALAR (la carpeta del programa se puede cambiar).
    void Preparar()
    {
        lblEstado.Text = "Listo para instalar";
        lblInfo.Text = "Mira dónde se instala cada cosa en «Rutas de instalación» y cambia la carpeta del programa si quieres. Pulsa INSTALAR cuando estés listo.";
        RefrescarRutas();
        if (!verRutas) AlternarRutas();
    }

    void RefrescarRutas()
    {
        rutas.Items = Instalacion.Rutas(op);
        foreach (RutaInfo ri in rutas.Items) ri.Editable = false;      // la instalacion ya arranco sola: aqui solo se miran las rutas
        rutas.Invalidate();
    }

    void CambiarCarpeta(int fila)
    {
        if (fila != 0 || trabajando) return;
        using (FolderBrowserDialog d = new FolderBrowserDialog())
        {
            d.Description = "Elige la carpeta donde se instalará CineCaptions";
            d.ShowNewFolderButton = true;
            try { d.SelectedPath = op.Dir; } catch { }
            if (d.ShowDialog(this) != DialogResult.OK) return;
            string nueva = d.SelectedPath;
            try
            {
                // una carpeta ajena con cosas dentro: se instala en una subcarpeta propia, para no mezclar ni borrar nada
                if (Directory.Exists(nueva) && Directory.GetFileSystemEntries(nueva).Length > 0 &&
                    !File.Exists(Path.Combine(nueva, Programa.ExePrograma)) && !File.Exists(Path.Combine(nueva, "Desinstalar.exe")))
                    nueva = Path.Combine(nueva, Programa.Nombre);
            }
            catch { }
            op.Dir = nueva;
            RefrescarRutas();
            lblInfo.Text = TextoInfo();
        }
    }

    void AbrirRuta(int fila)
    {
        try
        {
            string r = rutas.Items[fila].Ruta;
            if (Directory.Exists(r)) Process.Start("explorer.exe", "\"" + r + "\"");
            else if (File.Exists(r)) Process.Start("explorer.exe", "/select,\"" + r + "\"");
        }
        catch { }
    }

    // ---- flujo -----------------------------------------------------------------------
    void Empezar()
    {
        if (trabajando) return;
        trabajando = true;
        terminado = false;
        if (verRutas) AlternarRutas();                    // al empezar se vuelve a los pasos
        if (op.Desinstalar && chkDatos != null)
        {
            op.BorrarDatos = chkDatos.Checked;             // lo elegido al desinstalar (la copia en TEMP ya arranca con las casillas de la linea de comandos)
            op.BorrarModelos = chkModelos.Checked;
            chkDatos.Visible = false; chkModelos.Visible = false;
            lblInfo.SetBounds(E(450), E(132), E(400), E(70));
        }
        boton.Enabled = false;
        banner.Estado = 1;
        foreach (RutaInfo ri in rutas.Items) ri.Editable = false;      // ya no se cambia la carpeta
        rutas.Invalidate();
        boton.Text = op.Desinstalar ? "DESINSTALANDO..." : "INSTALANDO...";
        lblEstado.Text = ins.Pasos[0].Accion;
        hilo = new Thread(delegate()
        {
            ins.Correr();
            try { BeginInvoke(new MethodInvoker(Terminado)); } catch { }
        });
        hilo.IsBackground = true;
        hilo.Start();
    }

    void Reintentar()
    {
        ins = new Instalacion(op, this);
        lista.Pasos = ins.Pasos;
        lista.Invalidate();
        barra.Valor = 0;
        boton.Colores(Tema.Acento, Tema.Cian);
        AgregarLog("");
        AgregarLog("--- Reintento ---");
        Empezar();
    }

    void Terminado()
    {
        trabajando = false;
        terminado = true;
        lista.Invalidate();
        lnkOmitir.Visible = false;
        CodigoSalida = ins.HuboError ? 1 : 0;
        bool ok = !ins.HuboError;
        banner.Estado = ok ? 2 : 3;
        if (ok) barra.Valor = 1;                // con error la barra se queda donde se corto
        if (op.Desinstalar)
            lblEstado.Text = ok ? "Listo, se desinstaló" : "La desinstalación tuvo problemas";
        else
            lblEstado.Text = ok ? (ins.Avisos.Count == 0 ? "¡Listo! Ya está instalado" : "Instalado, con avisos") : "No se pudo terminar";
        StringBuilder sb = new StringBuilder();
        if (ins.Avisos.Count > 0)
        {
            foreach (string a in ins.Avisos) sb.AppendLine("•  " + a);
        }
        else if (op.Desinstalar) sb.Append(ins.Resumen + (op.BorrarDatos ? " No queda nada del programa en este equipo." : " Tus proyectos, tu licencia y tus ajustes siguen en tu carpeta DaVinciSubtitles."));
        else sb.Append("En DaVinci Resolve los scripts están en  Área de trabajo > Scripts > Utility  (si Resolve estaba abierto, ciérralo y vuelve a abrirlo).");
        lblInfo.Text = sb.ToString().Trim();
        lblInfo.ForeColor = ins.HuboError ? Tema.Error : ins.Avisos.Count > 0 ? Tema.Aviso : Tema.Suave;
        if (!ok && !detallesAbiertos) AlternarDetalles();
        boton.Text = ok || op.Desinstalar ? "CERRAR" : "REINTENTAR";
        boton.Enabled = true;
        if (!op.Desinstalar && ok && !op.NoAbrir && File.Exists(ins.ExeInstalado))
        {
            TopMost = false;            // que el programa quede encima
            bPin.Marcado = false; bPin.Invalidate();
            AbrirPrograma();
            if (ins.Avisos.Count == 0)
            {
                lblInfo.Text = "Abriendo CineCaptions...  " + lblInfo.Text;
                System.Windows.Forms.Timer t = new System.Windows.Forms.Timer();
                t.Interval = 5000;
                t.Tick += delegate { t.Stop(); if (!detallesAbiertos) Close(); };
                t.Start();
            }
        }
    }

    void AbrirPrograma()
    {
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo(ins.ExeInstalado);
            psi.WorkingDirectory = op.Dir;
            psi.UseShellExecute = true;
            Process.Start(psi);
        }
        catch (Exception ex) { Registro.Escribir("No pude abrir el programa: " + ex.Message); }
    }

    // la copia del desinstalador en %TEMP% se borra sola al cerrarse
    void ProgramarAutoBorrado()
    {
        FormClosed += delegate
        {
            if (terminado && !ins.HuboError) Registro.Borrar();            // si todo salio bien no queda ni el registro de la desinstalacion
            Programa.AutoBorrar();
        };
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        if (trabajando && !terminado)
        {
            if (ins.DescargandoModelo)
            {
                ins.OmitirDescarga();
                lblInfo.Text = "Omitiendo la descarga del modelo de voz: se hará la primera vez que transcribas.";
            }
            else lblInfo.Text = "Espera un momento: hay un paso en curso que no se puede cortar a la mitad.";
            e.Cancel = true;
            return;
        }
        base.OnFormClosing(e);
    }

    // ---- avisos desde el hilo de la instalacion ---------------------------------------------
    public void PasoCambiado(Paso p)
    {
        if (!IsHandleCreated) return;
        try
        {
            BeginInvoke(new MethodInvoker(delegate
            {
                lista.Invalidate();
                if (p.Estado == EstadoPaso.EnCurso)
                {
                    lblEstado.Text = p.Accion;
                    if (!string.IsNullOrEmpty(p.Detalle)) lblInfo.Text = p.Detalle;
                }
                double total = 0, hecho = 0;
                foreach (Paso x in ins.Pasos)
                {
                    total += x.Peso;
                    if (x.Estado == EstadoPaso.EnCurso) hecho += x.Peso * Math.Max(0, x.Progreso) / 100.0;
                    else if (x.Estado != EstadoPaso.Pendiente) hecho += x.Peso;
                }
                barra.Valor = total > 0 ? hecho / total : 0;
            }));
        }
        catch { }
    }

    public void AgregarLog(string texto)
    {
        if (!IsHandleCreated) return;
        try { BeginInvoke(new MethodInvoker(delegate { log.AppendText(texto + Environment.NewLine); })); } catch { }
    }

    public void MostrarOmitir(bool v)
    {
        if (!IsHandleCreated) return;
        try
        {
            BeginInvoke(new MethodInvoker(delegate
            {
                lnkOmitir.Visible = v;
                lnkOmitir.Enabled = true;
                lnkOmitir.Text = "Omitir la descarga (se hará al transcribir)";
            }));
        }
        catch { }
    }
}
