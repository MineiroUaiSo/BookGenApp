"""ECG Library (ecglibrary.com) collector - intentionally a stub.

Checked 2026-11-24: the site is reachable, but its terms say "The ECGs and associated images on
ecglibrary.com may only be used with the permission of the authors" (Dean Jenkins, Stephen Gerred).
That is not an educational/non-commercial reuse grant, so nothing is collected. See
data/datasets/ecglibrary/README.txt. Re-enable only after written permission is obtained.
"""
from __future__ import annotations

import sys

TERMS = ("The ECGs and associated images on ecglibrary.com may only be used with the permission of the authors.")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--permission-granted" not in argv:
        print("ecglibrary: refusing to collect - terms require author permission. " + TERMS)
        return 2
    print("ecglibrary: permission flag given but no crawler implemented; add one after agreeing terms with the authors.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
