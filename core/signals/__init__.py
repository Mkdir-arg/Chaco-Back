# La invalidación de cache por clave exacta vive en core/performance/cache_utils.py
# (registrada en CoreConfig.ready). Los receivers de patrón que vivían acá
# invalidaban claves que nunca se cacheaban, con KEYS bloqueante sobre Redis.
