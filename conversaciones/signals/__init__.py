# Los receivers de invalidación por patrón que vivían acá invalidaban claves
# que nunca se cacheaban (con KEYS bloqueante sobre Redis en cada mensaje).
# Las señales vigentes de la app viven en signals/alertas.py (registradas en
# ConversacionesConfig.ready).
