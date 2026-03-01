# Only4BMS

<img width="2556" height="1439" alt="스크린샷 2026-02-24 230333" src="https://github.com/user-attachments/assets/68d1891b-891b-4927-ab81-96f7bbc098f7" />

[![Only4BMS AI Battle1](https://img.youtube.com/vi/mrSUp4h7DnE/0.jpg)](https://youtu.be/mrSUp4h7DnE)

¿7 teclas? No, gracias. 

Este es un controlador BMS basado en Pygame que **reorganiza forzosamente** todos los gráficos BMS en **4 teclas (DFJK)** para su reproducción.

## Descripción del Proyecto

Only4BMS fue creado para puristas de 4 teclas que se enfrentan a gráficos BMS complejos como los de 7 o 14 teclas y piensan: "¿Cómo se supone que voy a tocar todo esto?"

Este proyecto utiliza Pygame para analizar archivos BMS y proporciona un entorno donde puedes disfrutar de cualquier formato de gráfico **remapeado en 4 carriles** junto con sonidos de teclas (keysounds).

## Características Principales

**Mapeo Forzado de 4 Teclas**: Asigna automáticamente gráficos de 5, 7, 10 y 14 teclas a 4 carriles (D, F, J, K) utilizando algoritmos matemáticos.

**Verificador de Densidad**: Comprueba y visualiza la densidad de las notas cuando los gráficos de 7 teclas se consolidan en 4 teclas.

## 🛠️ Stack Tecnológico

**Lenguaje**: Python 3.x

**Librería**: Pygame (Sonido y Renderizado)

**Formato**: Be-Music Script (.bms, .bme, .bml)

## Cómo Jugar (Añadir Canciones y Ejecutar)

1. **Obtener el Juego**: Descarga el `Only4BMS.exe` precompilado o compílalo tú mismo.
2. **Iniciar**: Simplemente ejecuta `Only4BMS.exe` desde cualquier carpeta. 
3. **La Carpeta `bms`**: Al iniciar, el juego crea automáticamente una carpeta `bms` en el mismo directorio que el ejecutable. Si no se encuentran canciones, genera una canción de demostración básica.
4. **Añadir Tus Propias Canciones**: 
   - Descarga archivos BMS/BME/BML y sus archivos multimedia asociados (audio/vídeos BGA).
   - Extráelos en sus propias subcarpetas dentro del directorio `bms/`.
   - Ejemplo de estructura:
     ```text
     [Directorio que contiene Only4BMS.exe]
     ├── Only4BMS.exe
     └── bms/
         ├── Awesome Track/
         │   ├── song.bms
         │   ├── audio.wav
         │   └── video.mp4
         └── Another Track/
             └── ...
     ```

## 🤖 Entrenamiento de IA y Multijugador

Only4BMS cuenta con un modo Multijugador de IA impulsado por **Aprendizaje por Refuerzo (PPO)**.

### Cómo Funciona
- La IA se entrena utilizando `stable-baselines3` en pistas de ritmo generadas por procedimientos y canciones de demostración libres de derechos.
- **Cumplimiento Legal**: Para garantizar estándares éticos, las versiones oficiales incluyen modelos entrenados *exclusivamente* con datos no comerciales durante el proceso de CI/CD.
- **Dificultades**:
  - **NORMAL**: Entrenado durante 25,000 pasos. Alta precisión pero con errores ocasionales similares a los humanos.
  - **HARD**: Entrenado durante 40,000 pasos. Sincronización y mantenimiento de combos casi perfectos.

### Entrenamiento Local
Si deseas entrenar tus propios modelos localmente:
1. Instala las dependencias: `pip install stable-baselines3 shimmy gymnasium torch`
2. Ejecuta el script de entrenamiento: `python -m only4bms.ai.train`
3. Los archivos `model_normal.zip` y `model_hard.zip` generados se guardarán en `src/only4bms/ai/`.

### CI/CD Automatizado
Nuestro flujo de trabajo de GitHub Actions entrena automáticamente los modelos de IA desde cero utilizando la `Mock Song Demo` para cada lanzamiento. Esto asegura que el binario distribuido a los usuarios esté siempre "limpio" y optimizado.

<a href="https://minwook-shin.itch.io/only4bms" class="btn">Jugar en itch.io</a>

## Declaración de Transparencia:

Only4BMS es un proyecto personal apasionado.

Para agilizar el proceso de producción, he incorporado tecnología asistida por IA para el código.

Esto me permitió superar los límites de lo que una sola persona puede crear, asegurando que el juego final se sienta pulido y completo.

## 🤝 Contribuir

¡Los informes de errores y las sugerencias de funciones de los usuarios de 4 teclas son siempre bienvenidos!

## 📜 Licencia

Licencia MIT: siéntete libre de modificar y distribuir. Solo, por favor, mantén la paz para los usuarios de 4 teclas.
