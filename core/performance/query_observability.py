"""Contrato de métricas de consultas recolectadas durante solicitudes HTTP."""


def query_metrics(session_stats):
    """Expone el origen y alcance de los contadores de consultas."""
    source = session_stats["metrics_source"]
    available = source == "measured"
    return {
        "source": source,
        "scope": "process_since_start" if available else None,
        "value": session_stats["total_queries"] if available else None,
        "details_source": "unavailable",
    }


def query_observability_report(session_stats):
    """Construye un reporte solo con datos realmente instrumentados."""
    metrics = query_metrics(session_stats)
    if metrics["source"] != "measured":
        return {
            "total_queries": None,
            "total_requests": None,
            "slow_requests": None,
            "slow_queries_count": None,
            "slow_queries": None,
            "n1_detected": None,
            "n1_affected_requests": None,
            "performance_score": None,
            "recommendations": [],
            "metrics": {"queries": metrics},
        }

    n1_affected_requests = session_stats["n1_affected_requests"]
    score = max(
        20,
        100 - min(50, session_stats["slow_requests"] * 5) - min(30, n1_affected_requests * 3),
    )
    recommendations = []
    if n1_affected_requests:
        recommendations.append(
            {
                "type": "N+1 Detection",
                "suggestion": "Revisar las solicitudes instrumentadas con patrones N+1.",
                "count": n1_affected_requests,
            }
        )
    if session_stats["slow_queries_count"]:
        recommendations.append(
            {
                "type": "Slow Queries",
                "suggestion": "Revisar las consultas lentas de las solicitudes instrumentadas.",
                "count": session_stats["slow_queries_count"],
            }
        )

    return {
        "total_queries": session_stats["total_queries"],
        "total_requests": session_stats["total_requests"],
        "slow_requests": session_stats["slow_requests"],
        "slow_queries_count": session_stats["slow_queries_count"],
        "slow_queries": None,
        "n1_detected": n1_affected_requests > 0,
        "n1_affected_requests": n1_affected_requests,
        "performance_score": score,
        "recommendations": recommendations,
        "metrics": {"queries": metrics},
    }
