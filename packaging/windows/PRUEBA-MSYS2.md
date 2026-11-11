# Primera prueba de Grepleo en Windows (MSYS2)

Objetivo: comprobar **sin empaquetar nada** si Grepleo arranca en Windows 10 con GTK4 y qué falla. Es una
prueba de viabilidad; todavía no hay instalador. Se hace dentro de la máquina virtual, en limpio.

Estado: rama `windows`, sin probar. Los nombres de paquete de MSYS2 son los habituales, pero hay que
confirmarlos con `pacman -Ss` si alguno no se encuentra.

## 1. Instalar MSYS2

1. Descarga el instalador desde <https://www.msys2.org> y ejecútalo con las opciones por defecto
   (carpeta `C:\msys64`).
2. Al terminar, abre **MSYS2 MINGW64** desde el menú Inicio (el icono azul, **no** el «MSYS2 MSYS»
   ni el UCRT64). Todo lo que sigue se escribe en esa terminal.
3. Actualiza el sistema (puede pedir cerrar la terminal y repetir una vez):

```bash
pacman -Syu
```

## 2. Instalar lo que necesita Grepleo

```bash
pacman -S --needed git mingw-w64-x86_64-python mingw-w64-x86_64-python-gobject \
  mingw-w64-x86_64-gtk4 mingw-w64-x86_64-python-keyring mingw-w64-x86_64-python-pytest \
  mingw-w64-x86_64-libshumate
```

Anota si algún paquete **no existe** (sobre todo `libshumate`): eso decide si el mapa entra en la
versión de Windows. Para buscarlo:

```bash
pacman -Ss shumate
```

La terminal VTE no se instala: no existe en Windows. Grepleo la trata como opcional.

## 3. Obtener el código

```bash
git clone --branch windows https://github.com/seguidodoblado/grepleo.git
cd grepleo
```

## 4. Probar la lógica (sin ventana)

```bash
PYTHONPATH=src python -m pytest -q
```

Anota cuántas pasan y cuáles fallan. Se esperan fallos en las pruebas de la interfaz y en las que dependen
de `~/.local/share` o `/proc/self/exe`.

## 5. Arrancar la aplicación

Usa un perfil de pruebas, no tus datos reales (aquí no hay datos, pero así se comprueba con una base vacía).

```bash
PYTHONPATH=src python -m grepleo
```

Mira esto y anótalo:

- ¿Abre la ventana? ¿Con qué aspecto (tema, iconos, fuentes)?
- ¿Se crea la carpeta de datos? Mira dónde: `ls -a ~` y busca `.local/share/grepleo` y `.config/grepleo`.
  Con MSYS2 `~` es `C:\msys64\home\<usuario>`: de momento Grepleo usa las rutas de Linux.
- Pestañas **Mercado** y **Mapa**: ¿se ven? ¿el mapa carga teselas?
- **Preferencias**: ¿guarda el token de Apify? (usa el Administrador de credenciales de Windows). Para
  probarlo pega un valor de prueba, no uno real, y bórralo después.
- Cambiar el idioma desde Preferencias: se espera que falle el reinicio (usa `/proc/self/exe`).
- El asistente con terminal: se espera que no esté disponible.

## 6. Qué me tienes que pasar

Copia el texto de la terminal (los errores completos) y dime:

1. Qué paquetes de `pacman` no existían.
2. El resultado de `pytest` (resumen y fallos).
3. Lo que ves al arrancar: capturas o descripción, y los mensajes de la terminal.
4. Si el mapa sale o no.

Con eso se decide el alcance: rutas, reinicio, terminal y mapa.

## Notas

- No hace falta instalar Python de python.org ni GTK por separado: MSYS2 lo trae todo.
- Esto no genera un `.exe` ni un instalador: eso es un paso posterior (PyInstaller más un instalador).
- Si prefieres no mezclar nada con tu sistema, haz una instantánea de la VM antes de empezar.
