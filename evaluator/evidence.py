"""Missing evidence is distinct from contradiction or an attributed model failure."""
class InsufficientEvidence(ValueError):
    """A claim cannot be reconstructed from the retained evidence."""
