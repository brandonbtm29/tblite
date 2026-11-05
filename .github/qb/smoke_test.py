"""Smoke test for a tblite wheel: import, GFN2/GFN1 water single points, ALPB/GBSA and CPCM (ddX) water, dipole.

Usage: python qb_smoke_test.py [--json out.json] [--check]

The geometry is ase.build.molecule("H2O"), hard-coded so ASE is not needed, converted with
1 bohr = 0.529177210903 Angstrom (CODATA 2018). --check compares with reference values computed with the
PyPI tblite 0.8.0 manylinux wheel and exits 1 if any value differs by more than its tolerance.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys

import numpy as np

BOHR_ANG = 0.529177210903
WATER_NUMBERS = np.array([8, 1, 1])
WATER_ANG = np.array([[0.0, 0.0, 0.119262], [0.0, 0.763239, -0.477047], [0.0, -0.763239, -0.477047]])

# PyPI tblite 0.8.0 (manylinux x86_64 wheel), OMP_NUM_THREADS=1, Linux. Energies in Hartree, dipole in e*bohr.
REFERENCE: dict[str, float] = {
    "gfn2_energy": -5.070222289322534,
    "gfn2_dipole_z": -0.8995483509331234,
    "gfn2_gradient_norm": 0.018344199377349147,
    "gfn1_energy": -5.768449492529489,
    "gfn2_alpb_water_energy": -5.084802151419029,
    "gfn2_gbsa_water_energy": -5.079879346432425,
    "gfn2_cpcm_water_energy": -5.076034283135089,
}
TOL_ENERGY = 1e-7      # Hartree
TOL_DIPOLE = 1e-5      # e*bohr


def singlepoint(method: str, solvation: tuple | None = None):
    from tblite.interface import Calculator

    calc = Calculator(method, WATER_NUMBERS, WATER_ANG / BOHR_ANG, 0.0, 0)
    calc.set("verbosity", 0)
    if solvation is not None:
        calc.add(*solvation)
    return calc.singlepoint()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the results to this file")
    ap.add_argument("--check", action="store_true", help="compare with the Linux reference values")
    args = ap.parse_args()

    import tblite
    import tblite.library as lib

    out: dict = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "tblite_file": tblite.__file__,
        "tblite_version": ".".join(str(x) for x in lib.get_version()),
        "features": {flag: bool(lib.get_feature(flag)) for flag in ("ddx", "hdf5", "trexio")},
    }
    res = singlepoint("GFN2-xTB")
    dip = np.asarray(res.get("dipole"), float)
    out["gfn2_energy"] = float(res.get("energy"))
    out["gfn2_dipole_x"], out["gfn2_dipole_y"], out["gfn2_dipole_z"] = (float(x) for x in dip)
    out["gfn2_dipole_debye"] = float(np.linalg.norm(dip) * BOHR_ANG * 4.80320471)
    out["gfn2_gradient_norm"] = float(np.linalg.norm(res.get("gradient")))
    out["gfn1_energy"] = float(singlepoint("GFN1-xTB").get("energy"))
    out["gfn2_alpb_water_energy"] = float(singlepoint("GFN2-xTB", ("alpb-solvation", "water")).get("energy"))
    out["gfn2_gbsa_water_energy"] = float(singlepoint("GFN2-xTB", ("gbsa-solvation", "water")).get("energy"))
    try:
        out["gfn2_cpcm_water_energy"] = float(
            singlepoint("GFN2-xTB", ("ddX-solvation", 78.36, "cpcm")).get("energy"))
    except Exception as exc:  # a build without ddX
        out["gfn2_cpcm_water_energy"] = None
        out["cpcm_error"] = f"{type(exc).__name__}: {exc}"

    print(json.dumps(out, indent=2))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)

    if not args.check:
        return 0
    bad = []
    for key, ref in REFERENCE.items():
        got = out.get(key)
        tol = TOL_DIPOLE if "dipole" in key else TOL_ENERGY
        if got is None or abs(got - ref) > tol:
            bad.append(f"{key}: got {got}, reference {ref} (tolerance {tol})")
        else:
            print(f"OK {key}: {got:.10f} (reference {ref:.10f}, diff {got - ref:+.2e})")
    for line in bad:
        print("MISMATCH", line)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
