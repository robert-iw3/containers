"""Shared implementation for the per-format Cribl pipeline provisioners.

The four formats differ only in which pipeline template they load and which
collector they create. Everything else - reading configuration, authenticating,
creating the pipeline, committing and deploying it - is here in one copy, so a
fix reaches every format rather than one of four.
"""
