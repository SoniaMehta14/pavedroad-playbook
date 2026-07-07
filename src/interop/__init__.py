"""Semantic interoperability layer.

Mid-market companies run their business across systems that were never designed to
agree with each other: the CRM, the billing system, and the PSA tool each hold a
partial, inconsistent view of the same customers. This package normalizes that
fragmented data into a single typed tool-calling surface that an orchestration
layer can trust — deterministic entity resolution first, LLM assistance only for
the ambiguous residual, and a human review queue for anything below the
confidence bar.
"""
