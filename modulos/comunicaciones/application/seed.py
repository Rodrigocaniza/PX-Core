"""Catálogo inicial de BC Comunicaciones.

Mensajes reales de mostrador de óptica, en español natural y listos para enviar
por WhatsApp. Se cargan una sola vez, la primera vez que la base está vacía: a
partir de ahí son plantillas normales que el operador puede editar, desactivar o
marcar como favoritas sin que una actualización se las pise.
"""

from __future__ import annotations

from typing import Sequence

from ..domain.models import Category, Template, VariableSpec


INITIAL_CATEGORIES: tuple[Category, ...] = (
    Category(slug="cristales-productos", name="Cristales y productos", position=10),
    Category(slug="pedidos-estados", name="Pedidos y estados", position=20),
    Category(slug="aseguradoras-recetas", name="Aseguradoras y recetas", position=30),
    Category(slug="recomendaciones-cuidados", name="Recomendaciones y cuidados", position=40),
    Category(slug="generales", name="Mensajes generales", position=50),
)

CATEGORY_SLUGS: tuple[str, ...] = tuple(category.slug for category in INITIAL_CATEGORIES)


def _spec(name: str, label: str, example: str) -> VariableSpec:
    return VariableSpec(name=name, label=label, example=example)


CLIENTE = _spec("cliente", "Nombre del cliente", "María González")
SUCURSAL = _spec("sucursal", "Sucursal", "Casa Central")
PRODUCTO = _spec("producto", "Producto", "cristales antirreflejo")
FECHA = _spec("fecha", "Fecha", "martes 18/08")
ESTADO = _spec("estado", "Estado del pedido", "en laboratorio")
PEDIDO = _spec("pedido", "N° de pedido / sobre", "1245")
MONTO = _spec("monto", "Importe", "850.000 Gs.")


_SEED: tuple[dict, ...] = (
    # ------------------------------------------------ Cristales y productos
    {
        "category_slug": "cristales-productos",
        "title": "Presupuesto de cristales",
        "keywords": "presupuesto precio cotización cristales lentes",
        "body": (
            "Hola {{cliente}}, ¿cómo estás? Te paso el presupuesto de {{producto}}: {{monto}}.\n\n"
            "El precio incluye el armado y la garantía del laboratorio. Si querés, te lo reservamos "
            "y lo mandamos a preparar hoy mismo.\n\n"
            "Quedo atenta a tu confirmación. ¡Gracias!"
        ),
        "variable_specs": (CLIENTE, PRODUCTO, MONTO),
    },
    {
        "category_slug": "cristales-productos",
        "title": "Diferencia entre cristales recomendados",
        "keywords": "opciones antirreflejo blue fotocromático comparación",
        "body": (
            "Hola {{cliente}}, te resumo las opciones que vimos para tu receta:\n\n"
            "• {{opcion_1}}\n"
            "• {{opcion_2}}\n\n"
            "Las dos corrigen igual tu graduación; la diferencia está en la comodidad y en la "
            "duración del tratamiento. Con gusto te ayudo a elegir la que mejor se adapte a tu día a día.\n\n"
            "¿Te reservo alguna?"
        ),
        "variable_specs": (
            CLIENTE,
            _spec("opcion_1", "Opción 1", "Antirreflejo estándar — 620.000 Gs."),
            _spec("opcion_2", "Opción 2", "Antirreflejo con filtro azul — 780.000 Gs."),
        ),
    },
    {
        "category_slug": "cristales-productos",
        "title": "Armazón disponible en stock",
        "keywords": "armazón marco modelo stock disponible",
        "body": (
            "Hola {{cliente}}, buenas noticias: tenemos disponible el armazón {{producto}} en "
            "{{sucursal}}.\n\n"
            "Te lo puedo apartar hasta {{fecha}} para que vengas a probártelo sin apuro.\n\n"
            "¿Te lo reservo?"
        ),
        "variable_specs": (CLIENTE, PRODUCTO, SUCURSAL, FECHA),
    },
    {
        "category_slug": "cristales-productos",
        "title": "Producto sin stock con alternativa",
        "keywords": "sin stock agotado alternativa reposición",
        "body": (
            "Hola {{cliente}}, gracias por tu paciencia. Por el momento no tenemos {{producto}} "
            "disponible; la reposición llega aproximadamente el {{fecha}}.\n\n"
            "Mientras tanto tenemos una alternativa muy parecida: {{alternativa}}. Si preferís esperar "
            "el original, te aviso apenas entre.\n\n"
            "¿Cómo te resulta más cómodo?"
        ),
        "variable_specs": (
            CLIENTE,
            PRODUCTO,
            FECHA,
            _spec("alternativa", "Alternativa ofrecida", "el mismo modelo en color negro mate"),
        ),
    },
    {
        "category_slug": "cristales-productos",
        "title": "Presupuesto de lentes de contacto",
        "keywords": "lentes de contacto pupilentes presupuesto caja",
        "body": (
            "Hola {{cliente}}, te paso el detalle de tus lentes de contacto:\n\n"
            "• Producto: {{producto}}\n"
            "• Duración estimada: {{duracion}}\n"
            "• Precio: {{monto}}\n\n"
            "Si es tu primera vez, te enseñamos en el local cómo colocarlos y retirarlos sin costo.\n\n"
            "Cualquier consulta quedo a disposición."
        ),
        "variable_specs": (
            CLIENTE,
            PRODUCTO,
            MONTO,
            _spec("duracion", "Duración estimada", "un mes por caja"),
        ),
    },
    # ------------------------------------------------ Pedidos y estados
    {
        "category_slug": "pedidos-estados",
        "title": "Pedido listo para retirar",
        "keywords": "listo retirar terminado entrega aviso",
        "body": (
            "¡Hola {{cliente}}! Te avisamos que tu pedido N° {{pedido}} ya está listo para retirar en "
            "{{sucursal}}.\n\n"
            "Te esperamos en nuestro horario de atención: {{horario}}.\n\n"
            "Cuando vengas te lo ajustamos y te lo dejamos cómodo. ¡Gracias por elegirnos!"
        ),
        "variable_specs": (
            CLIENTE,
            PEDIDO,
            SUCURSAL,
            _spec("horario", "Horario de atención", "lunes a viernes de 08:00 a 18:00 y sábados de 08:00 a 12:00"),
        ),
    },
    {
        "category_slug": "pedidos-estados",
        "title": "Estado del pedido en curso",
        "keywords": "estado seguimiento avance en proceso laboratorio",
        "body": (
            "Hola {{cliente}}, ¿cómo estás? Te cuento cómo viene tu pedido N° {{pedido}}: "
            "actualmente está {{estado}}.\n\n"
            "La fecha estimada de entrega es el {{fecha}}. Apenas esté listo te aviso por acá para que "
            "vengas a retirarlo.\n\n"
            "¡Gracias por la paciencia!"
        ),
        "variable_specs": (CLIENTE, PEDIDO, ESTADO, FECHA),
    },
    {
        "category_slug": "pedidos-estados",
        "title": "Demora en el laboratorio",
        "keywords": "demora atraso retraso laboratorio disculpas",
        "body": (
            "Hola {{cliente}}, quería avisarte personalmente que tu pedido N° {{pedido}} va a demorar "
            "un poco más de lo previsto. El laboratorio nos confirmó la entrega para el {{fecha}}.\n\n"
            "Lamentamos la espera; estamos siguiendo el trabajo de cerca para que salga perfecto. "
            "Apenas lo recibamos te aviso enseguida.\n\n"
            "Gracias por la comprensión, {{cliente}}."
        ),
        "variable_specs": (CLIENTE, PEDIDO, FECHA),
    },
    {
        "category_slug": "pedidos-estados",
        "title": "Recordatorio de retiro pendiente",
        "keywords": "recordatorio pendiente sin retirar aviso segundo",
        "body": (
            "Hola {{cliente}}, ¿cómo estás? Te recordamos que tu pedido N° {{pedido}} sigue esperándote "
            "en {{sucursal}} desde el {{fecha}}.\n\n"
            "Podés pasar a retirarlo cuando te quede cómodo. Si necesitás que te lo guardemos unos días "
            "más, avisanos sin problema.\n\n"
            "¡Te esperamos!"
        ),
        "variable_specs": (CLIENTE, PEDIDO, SUCURSAL, FECHA),
    },
    {
        "category_slug": "pedidos-estados",
        "title": "Saldo pendiente del pedido",
        "keywords": "saldo seña pago pendiente cobro",
        "body": (
            "Hola {{cliente}}, te paso el detalle de tu pedido N° {{pedido}}:\n\n"
            "• Saldo pendiente: {{monto}}\n\n"
            "Podés abonarlo al momento de retirar, en efectivo o con tarjeta. Si preferís coordinar otra "
            "forma de pago, decime y lo vemos.\n\n"
            "¡Gracias!"
        ),
        "variable_specs": (CLIENTE, PEDIDO, MONTO),
    },
    {
        "category_slug": "pedidos-estados",
        "title": "Confirmación de pedido tomado",
        "keywords": "confirmación encargo tomado recibido comprobante",
        "body": (
            "Hola {{cliente}}, confirmamos tu pedido:\n\n"
            "• N° de pedido: {{pedido}}\n"
            "• Trabajo: {{producto}}\n"
            "• Entrega estimada: {{fecha}}\n\n"
            "Ya lo enviamos a preparar. Te vamos avisando por acá cómo avanza.\n\n"
            "¡Gracias por confiar en nosotros!"
        ),
        "variable_specs": (CLIENTE, PEDIDO, PRODUCTO, FECHA),
    },
    # ------------------------------------------------ Aseguradoras y recetas
    {
        "category_slug": "aseguradoras-recetas",
        "title": "Documentos necesarios para la cobertura",
        "keywords": "seguro cobertura documentos requisitos aseguradora",
        "body": (
            "Hola {{cliente}}, para tramitar tu cobertura con {{aseguradora}} necesitamos que nos "
            "acerques:\n\n"
            "• Cédula de identidad\n"
            "• Carnet del seguro vigente\n"
            "• Receta del oftalmólogo (no mayor a 6 meses)\n"
            "• {{documento_extra}}\n\n"
            "Con eso presentamos el trámite y te confirmamos el monto que cubre el seguro.\n\n"
            "Cualquier duda escribime."
        ),
        "variable_specs": (
            CLIENTE,
            _spec("aseguradora", "Aseguradora", "tu seguro médico"),
            _spec("documento_extra", "Documento adicional", "orden de autorización del seguro"),
        ),
    },
    {
        "category_slug": "aseguradoras-recetas",
        "title": "Cobertura aprobada",
        "keywords": "aprobado autorizado cobertura seguro confirmación",
        "body": (
            "¡Buenas noticias, {{cliente}}! {{aseguradora}} aprobó la cobertura de tu pedido.\n\n"
            "• Cubre el seguro: {{monto_cubierto}}\n"
            "• Queda a tu cargo: {{monto}}\n\n"
            "Ya podemos mandar tu trabajo a preparar. ¿Te lo enviamos?"
        ),
        "variable_specs": (
            CLIENTE,
            _spec("aseguradora", "Aseguradora", "tu seguro médico"),
            _spec("monto_cubierto", "Monto cubierto", "500.000 Gs."),
            MONTO,
        ),
    },
    {
        "category_slug": "aseguradoras-recetas",
        "title": "Receta vencida o ilegible",
        "keywords": "receta vencida ilegible oftalmólogo actualizar graduación",
        "body": (
            "Hola {{cliente}}, revisamos la receta que nos dejaste y necesitamos una actualizada: "
            "{{motivo}}.\n\n"
            "Para que tus cristales queden exactos conviene una graduación reciente. Si querés, te "
            "ayudamos a coordinar un control con el oftalmólogo.\n\n"
            "Apenas la tengas, mandámela por acá y seguimos con tu pedido."
        ),
        "variable_specs": (
            CLIENTE,
            _spec("motivo", "Motivo", "la receta tiene más de un año"),
        ),
    },
    {
        "category_slug": "aseguradoras-recetas",
        "title": "Solicitud de la receta por WhatsApp",
        "keywords": "enviar receta foto pedir graduación",
        "body": (
            "Hola {{cliente}}, ¿cómo estás? Para avanzar con tu pedido necesitamos la receta del "
            "oftalmólogo.\n\n"
            "Podés mandarnos una foto por acá; que se vea completa y con buena luz. Con eso ya "
            "preparamos todo.\n\n"
            "¡Gracias!"
        ),
        "variable_specs": (CLIENTE,),
    },
    {
        "category_slug": "aseguradoras-recetas",
        "title": "Cobertura rechazada con alternativa",
        "keywords": "rechazo denegado seguro no cubre alternativa",
        "body": (
            "Hola {{cliente}}, te cuento que {{aseguradora}} no autorizó la cobertura en este caso. "
            "El motivo que nos informaron es: {{motivo}}.\n\n"
            "No te preocupes, tenemos alternativas para que igual puedas usar tus lentes: {{alternativa}}.\n\n"
            "Contame cómo querés seguir y lo resolvemos juntos."
        ),
        "variable_specs": (
            CLIENTE,
            _spec("aseguradora", "Aseguradora", "tu seguro médico"),
            _spec("motivo", "Motivo informado", "el plan no incluye este tipo de cristal"),
            _spec("alternativa", "Alternativa ofrecida", "financiación en 3 cuotas sin interés"),
        ),
    },
    # ------------------------------------------------ Recomendaciones y cuidados
    {
        "category_slug": "recomendaciones-cuidados",
        "title": "Cuidados de los lentes nuevos",
        "keywords": "cuidados limpieza mantenimiento consejos entrega",
        "body": (
            "¡Gracias por tu compra, {{cliente}}! Te dejo algunos consejos para que tus lentes duren "
            "como el primer día:\n\n"
            "• Limpialos con agua y jabón neutro, y secalos con el paño de microfibra.\n"
            "• Evitá el papel o la ropa: rayan el tratamiento.\n"
            "• Sacátelos y ponételos con las dos manos.\n"
            "• Guardalos siempre en su estuche, nunca apoyados sobre los cristales.\n\n"
            "Cualquier ajuste que necesites, pasá por {{sucursal}} y te lo hacemos sin cargo."
        ),
        "variable_specs": (CLIENTE, SUCURSAL),
    },
    {
        "category_slug": "recomendaciones-cuidados",
        "title": "Adaptación a lentes multifocales",
        "keywords": "multifocal progresivo adaptación mareo primeros días",
        "body": (
            "Hola {{cliente}}, como son tus primeros multifocales, te dejo algunas recomendaciones para "
            "los primeros días:\n\n"
            "• Usalos todo el día, aunque al principio cueste un poco.\n"
            "• Para mirar de cerca, bajá la vista sin bajar la cabeza.\n"
            "• Al bajar escaleras, mirá el escalón moviendo la cabeza.\n\n"
            "La adaptación suele llevar entre 5 y 15 días. Si pasada esa semana seguís incómodo, "
            "escribime y lo revisamos juntos en el local."
        ),
        "variable_specs": (CLIENTE,),
    },
    {
        "category_slug": "recomendaciones-cuidados",
        "title": "Cuidado de lentes de contacto",
        "keywords": "lentes de contacto higiene solución cuidados",
        "body": (
            "Hola {{cliente}}, te dejo los cuidados importantes de tus lentes de contacto:\n\n"
            "• Lavate bien las manos antes de tocarlos.\n"
            "• Usá siempre solución nueva; nunca agua ni saliva.\n"
            "• Respetá la duración indicada: {{duracion}}.\n"
            "• No duermas con ellos salvo indicación médica.\n\n"
            "Si sentís ardor, enrojecimiento o visión borrosa, retiralos y consultá enseguida."
        ),
        "variable_specs": (
            CLIENTE,
            _spec("duracion", "Duración indicada", "un mes desde la apertura"),
        ),
    },
    {
        "category_slug": "recomendaciones-cuidados",
        "title": "Recordatorio de control anual",
        "keywords": "control anual revisión chequeo recordatorio vista",
        "body": (
            "Hola {{cliente}}, ¿cómo estás? Pasó un año desde tu último control de vista con nosotros.\n\n"
            "Es buen momento para revisar si tu graduación sigue igual y para que dejemos tus lentes "
            "bien ajustados.\n\n"
            "¿Querés que te agende un turno para {{fecha}}?"
        ),
        "variable_specs": (CLIENTE, FECHA),
    },
    {
        "category_slug": "recomendaciones-cuidados",
        "title": "Garantía y ajustes sin cargo",
        "keywords": "garantía ajuste servicio postventa reparación",
        "body": (
            "Hola {{cliente}}, te recuerdo que tu compra incluye {{garantia}} de garantía del laboratorio.\n\n"
            "Además, los ajustes de armazón y la limpieza profunda son siempre sin cargo en {{sucursal}}: "
            "pasá cuando quieras.\n\n"
            "Si notás algo raro en la visión o en el calce, avisame y lo revisamos."
        ),
        "variable_specs": (
            CLIENTE,
            _spec("garantia", "Plazo de garantía", "6 meses"),
            SUCURSAL,
        ),
    },
    # ------------------------------------------------ Mensajes generales
    {
        "category_slug": "generales",
        "title": "Bienvenida y horarios",
        "keywords": "bienvenida horario dirección ubicación contacto",
        "body": (
            "¡Hola {{cliente}}! Gracias por escribir a {{sucursal}}.\n\n"
            "Nuestro horario de atención es {{horario}} y estamos en {{direccion}}.\n\n"
            "Contame en qué te podemos ayudar y con gusto te asesoramos."
        ),
        "variable_specs": (
            CLIENTE,
            SUCURSAL,
            _spec("horario", "Horario de atención", "lunes a viernes de 08:00 a 18:00 y sábados de 08:00 a 12:00"),
            _spec("direccion", "Dirección", "Av. Mcal. López 1234"),
        ),
    },
    {
        "category_slug": "generales",
        "title": "Confirmación de turno",
        "keywords": "turno cita agenda confirmación consultorio",
        "body": (
            "Hola {{cliente}}, te confirmamos tu turno:\n\n"
            "• Fecha y hora: {{fecha}}\n"
            "• Lugar: {{sucursal}}\n\n"
            "Te pedimos llegar 10 minutos antes y traer tus lentes actuales y la última receta, si la tenés.\n\n"
            "Si no podés venir, avisanos por acá y lo reprogramamos sin problema."
        ),
        "variable_specs": (CLIENTE, FECHA, SUCURSAL),
    },
    {
        "category_slug": "generales",
        "title": "Agradecimiento posterior a la compra",
        "keywords": "gracias agradecimiento postventa satisfacción",
        "body": (
            "Hola {{cliente}}, ¡gracias por confiar en nosotros!\n\n"
            "Esperamos que estés muy cómodo con {{producto}}. Si necesitás un ajuste o tenés cualquier "
            "consulta, escribime por acá sin dudar.\n\n"
            "¡Que lo disfrutes!"
        ),
        "variable_specs": (CLIENTE, PRODUCTO),
    },
    {
        "category_slug": "generales",
        "title": "Respuesta fuera del horario de atención",
        "keywords": "fuera de horario cerrado respuesta automática ausencia",
        "body": (
            "¡Hola {{cliente}}! Gracias por escribirnos. En este momento estamos fuera del horario de "
            "atención.\n\n"
            "Te vamos a responder apenas abramos: {{horario}}.\n\n"
            "Si es una urgencia, dejanos tu consulta por acá y la vemos primero."
        ),
        "variable_specs": (
            CLIENTE,
            _spec("horario", "Próximo horario", "mañana desde las 08:00"),
        ),
    },
    {
        "category_slug": "generales",
        "title": "Medios de pago disponibles",
        "keywords": "pago cuotas tarjeta transferencia financiación",
        "body": (
            "Hola {{cliente}}, te cuento las formas de pago que manejamos:\n\n"
            "• Efectivo\n"
            "• Tarjetas de débito y crédito\n"
            "• {{financiacion}}\n"
            "• Transferencia bancaria\n\n"
            "Cualquiera de estas opciones podés usarla al momento de retirar. ¿Te reservo el trabajo?"
        ),
        "variable_specs": (
            CLIENTE,
            _spec("financiacion", "Financiación", "hasta 6 cuotas sin interés"),
        ),
    },
)


def initial_categories() -> Sequence[Category]:
    return INITIAL_CATEGORIES


def initial_templates() -> Sequence[Template]:
    return tuple(Template(origin="seed", **item) for item in _SEED)
