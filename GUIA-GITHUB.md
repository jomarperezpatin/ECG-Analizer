# Publicación de ECG Analyzer 1.0.0

## 1. Preparar el repositorio
- Instala Git para Windows desde https://git-scm.com/download/win e inicia sesión en GitHub.
- Crea un repositorio vacío en https://github.com/new con nombre `ECG-Analyzer`, preferiblemente privado al comienzo. No inicialices README, licencia ni .gitignore porque el proyecto ya contiene archivos.
- Extrae el ZIP en una carpeta nueva y abre PowerShell dentro de `ECG-Analyzer` (donde está `package.json`). Ejecuta lo siguiente, sustituyendo TU-USUARIO por el nombre de tu cuenta.

```powershell
git init -b main
git add .
git status --short
```

Antes del commit revisa que **solo** se hayan agregado fuentes, documentación, firmware y pruebas sintéticas. El `.gitignore` ayuda, pero no garantiza que archivos sensibles queden excluidos. Nunca subas estudios, nombres reales, capturas con datos de pacientes, respaldos, exportaciones, `.env`, tokens ni bases de datos. No subas `node_modules`, `.venv` ni `release`.

```powershell
git commit -m "ECG Analyzer v1.0.0"
git remote add origin https://github.com/TU-USUARIO/ECG-Analyzer.git
git push -u origin main
```

Autentícate en el navegador cuando Git Credential Manager lo solicite. Si Git requiere configurar identidad, usa `git config --global user.name "Tu nombre"` y `git config --global user.email "tu-correo"`. Para un repositorio existente, usa su copia clonada, revisa el remoto y haz commit de los cambios; no fuerces el push. Si construyes en local, conserva y agrega el `package-lock.json` generado por npm para mejorar la reproducibilidad.

## 2. Compilar el EXE en Windows
En el equipo de compilación instala Node.js 22 LTS (https://nodejs.org/) y Python 3.12 x64 (https://www.python.org/downloads/), con el lanzador `py`. Ejecuta `generar-actualizacion.cmd` desde la carpeta del proyecto. Se necesita internet para instalar dependencias. El resultado esperado es `release/ECG-Analyzer-Setup-1.0.0-x64.exe`. No se incluye un EXE ya compilado ni firmado.

Alternativa: el archivo `.github/workflows/windows-installer.yml` permite intentar la compilación en GitHub Actions. Desde el repositorio entra a Actions > Compilar instalador Windows > Run workflow (rama main). Si termina correctamente, abre la ejecución y descarga `ECG-Analyzer-Windows-x64` en Artifacts; extrae el EXE del ZIP. El workflow es nuevo y no se ha ejecutado aquí. Revisa los registros si falla. No publiques una compilación sin probarla en Windows.

## 3. Publicar el instalador como Release
En GitHub, entra en Releases > Draft a new release. Crea la etiqueta `v1.0.0` desde main; título `ECG Analyzer v1.0.0`. Adjunta el EXE probado como asset (no como archivo del repositorio). Añade notas de versión, requisitos y advertencia de uso académico. Publica la release. GitHub genera archivos de código fuente desde la etiqueta. Un repositorio privado restringe el acceso a colaboradores autorizados; si deseas acceso general al instalador, haz público el repositorio solo después de revisar los archivos y derechos de distribución. El instalador se podrá obtener en `https://github.com/TU-USUARIO/ECG-Analyzer/releases`.

## 4. Instalar en otro equipo
- Windows 10/11 x64 compatible con los requisitos de Electron y MongoDB. Instala MongoDB Community por separado como servicio local (https://www.mongodb.com/try/download/community), conservando el acceso en localhost. Revisa los requisitos del sistema de la versión MongoDB antes de instalar.
- Ejecuta el instalador EXE de ECG Analyzer. Puede aparecer una advertencia de SmartScreen por falta de firma. No desactives la seguridad: verifica el origen y la integridad antes de instalar.
- Python, Node.js y Arduino IDE no se necesitan para ejecutar el EXE; Python se empaqueta dentro del instalador. Arduino IDE y el controlador USB apropiado sí se necesitan para cargar firmware si aún no está cargado.
- Abre Configuración y verifica Python y MongoDB. Prueba simulación y captura de banco sin conectar electrodos a personas. Para adquisición experimental, requiere hardware validado y firmware ECG/1 con LO y tiempo, bajo supervisión competente.
- La base de datos de cada equipo es independiente. Usa respaldo/restauración solo por canales privados, nunca GitHub. Los archivos y la base de datos no están cifrados por la aplicación. Restringe el acceso a equipos que almacenen datos personales.

Documentación: https://docs.github.com/es/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github ; https://docs.github.com/es/repositories/releasing-projects-on-github/managing-releases-in-a-repository ; https://www.mongodb.com/docs/v8.0/tutorial/install-mongodb-on-windows/
