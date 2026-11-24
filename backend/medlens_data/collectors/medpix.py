"""MedPix (NLM) - intentionally NOT implemented.

Terms/licence do not allow automated bulk collection with per-item open licences and the host was unreachable from the
sandbox; see data/datasets/medpix/README.txt for the findings and how to add it if NLM grants permission.
"""
SOURCE = "medpix"


def run(*args, **kwargs):
    raise SystemExit("MedPix not collected: terms/licence unclear. See data/datasets/medpix/README.txt")


if __name__ == "__main__":
    run()
