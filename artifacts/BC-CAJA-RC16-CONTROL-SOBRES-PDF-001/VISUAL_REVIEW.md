# Visual review — 14 páginas

Datos exclusivamente sintéticos. Se renderizaron todas las páginas a PNG a 1.7×.

- Iteración 1: FAIL; una receta extrema dentro de una tabla anidada invadía header/footer.
- Iteración 2: FAIL; el chrome estático no era consistente con el canvas diferido.
- Iteración 3: FAIL en QA independiente; páginas de continuación alternas podían tapar el chrome.
- Iteración 4: FAIL en QA independiente; el canvas diferido aún ocultaba chrome en páginas pares.
- Iteración 5: inconclusa por caché de rutas PNG reutilizadas durante QA.
- Iteración 6: FAIL; el canvas de Platypus seguía condicionado por estado gráfico de flowables.
- Iteración 7: FAIL; el stream original conservaba un clip sin aislar antes de fusionar la capa.
- Iteración 8: FAIL; la capa externa no garantizaba por sí sola la visibilidad en todos los viewers.
- Iteración final: PASS; cada continuación incluye dentro del flujo un encabezado identificable y
  la banda `Observaciones / receta`, agrupados con su margen para impedir separación al paginar.
  El chrome y la numeración se fusionan además como capa independiente con `pypdf`.
  La receta usa fragmentos de 15 líneas y banda física de continuación.
  Las catorce páginas respetan márgenes, repiten encabezados, conservan texto 001–090, muestran
  Página X/Y y mantienen legibles las secciones finales y firmas. Los PNG finales usan nombres
  inmutables `release-v6-page-01.png` a `release-v6-page-14.png` para impedir evidencia visual cacheada.

La tipografía mínima autoral es 7.4 pt en celdas auxiliares y 8.2 pt en cuerpo; el contenido
se pagina en lugar de comprimirse.
