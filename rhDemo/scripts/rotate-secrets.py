#!/usr/bin/env -S python3 -I
"""Renouvellement des secrets RHDemo (docs/ROTATION_SECRETS.md, étude : docs/ETUDE_ROTATION_SECRETS.md).

Exécuté sur le poste, jamais dans Jenkins (il doit pouvoir réparer un Jenkins compromis).
Inventaire : secrets/inventory.yaml. Journal local : ~/.config/rhdemo-rotation/journal.jsonl.

Usage :
  rotate-secrets.py --list                  inventaire et méthode de chaque secret
  rotate-secrets.py --check                 âge des secrets ; code retour 1 si l'un est en retard
  rotate-secrets.py --preflight             accès Jenkins, cibles et outils, sans rien modifier
  rotate-secrets.py <id> [<id>...]          renouveler ces secrets
  rotate-secrets.py --level C|H|M           renouveler les secrets automatisés de ce niveau et au-dessus
  rotate-secrets.py --record <id>           tracer une rotation faite à la main (méthodes manual)
  rotate-secrets.py --if-missing <id>...    k8s-sa-token : créer le token seulement s'il n'en
                                            existe aucun (appelé par init-stagingkub.sh)

Les secrets de méthode per-build (ephemere) sont régénérés à chaque build : --check les affiche
sans les compter en retard, la rotation et --record les refusent.
Options : --dry-run (montre le plan après les lectures, ne crée ni ne révoque rien),
          --no (répond non à toute confirmation : aucun token non géré n'est révoqué).

Les identifiants maîtres (mot de passe admin Jenkins, mot de passe de l'utilisateur admin
d'OpenBao, mots de passe et codes TOTP des bots, valeurs créées à la main) sont demandés au
lancement et oubliés à la fin ; la session OpenBao est révoquée.
"""
import argparse
import datetime
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rotation_lib import inventory as inv_mod  # noqa: E402
from rotation_lib.common import (Journal, Prompter, RotationError, Skipped,  # noqa: E402
                                 log, redact, warn)
from rotation_lib.rotations import METHODS, Context, check_targets  # noqa: E402


def cmd_list(inv):
    log(f"{'#':<4}{'id':<38}{'criticité':<11}{'expo':<10}rotation")
    for e in inv_mod.ordered(inv["secrets"]):
        method = e["rotation"]["method"]
        detail = f"{method}, phase {e['rotation']['phase']}" if method == "planned" else method
        m = f"{inv_mod.METHOD_KINDS[method]} ({detail})"
        if e.get("blocking"):
            m += ", bloquant"
        crit = inv_mod.LEVEL_LABELS[e["criticality"]]
        log(f"{e['num']:<4}{e['id']:<38}{crit:<11}{e['exposure']:<10}{m}")


def cmd_check(inv, journal, today=None):
    today = today or datetime.datetime.now().astimezone()
    last = journal.last_rotations()
    late = late_blocking = 0
    log(f"{'#':<4}{'id':<38}{'criticité':<11}{'dernière rotation':<20}état")
    for e in inv_mod.ordered(inv["secrets"]):
        period = inv["periods"][e["criticality"]]
        life = e.get("lifetime_days")
        # Un secret bloquant doit être renouvelé avant son expiration, marge comprise.
        limit = min(period, life - inv_mod.EXPIRY_MARGIN_DAYS) if life else period
        ts = last.get(e["id"])
        is_late = True
        if e["rotation"]["method"] in inv_mod.NO_ROTATION:
            state, when, is_late = "régénéré à chaque build", "-", False
        elif ts is None:
            state, when = "aucune rotation journalisée", "-"
        else:
            age = (today - ts).days
            when = ts.strftime("%Y-%m-%d")
            if life and age > life:
                state = f"EXPIRÉ ({age} j > {life} j)"
            elif age > limit:
                state = (f"EN RETARD ({age} j > {limit} j)" if limit == period
                         else f"EN RETARD (expire dans {life - age} j)")
            else:
                state, is_late = f"ok, {limit - age} j restants", False
        if e.get("blocking"):
            state += " (bloquant)"
        if is_late:
            late += 1
            late_blocking += bool(e.get("blocking"))
        crit = inv_mod.LEVEL_LABELS[e["criticality"]]
        log(f"{e['num']:<4}{e['id']:<38}{crit:<11}{when:<20}{state}")
    log(f"\n{late} secret(s) en retard ou sans rotation journalisée, dont {late_blocking} bloquant(s) : "
        "ils cessent de fonctionner s'ils ne sont pas renouvelés à temps.")
    return 1 if late else 0


def cmd_preflight(ctx):
    ok = True
    for tool in ("gpg", "gpgconf", "kubectl"):
        if not shutil.which(tool):
            warn(f"outil absent : {tool}")
            ok = False
    for e in inv_mod.ordered(ctx.inv["secrets"]):
        if e["rotation"]["method"] not in METHODS:
            continue
        try:
            check_targets(ctx, e)
            log(f"  ✓ {e['id']} : cibles accessibles")
        except Exception as exc:  # noqa: BLE001 - le preflight rapporte tout, secret par secret
            warn(f"{e['id']} : {exc if isinstance(exc, RotationError) else type(exc).__name__ + ' : ' + str(exc)}")
            ok = False
    return 0 if ok else 1


def select(inv, ids, level):
    if ids:
        entries = [inv_mod.by_id(inv, i) for i in ids]
    else:
        allowed = inv_mod.LEVELS[:inv_mod.LEVELS.index(level) + 1]
        entries = [e for e in inv["secrets"] if e["criticality"] in allowed]
    return inv_mod.ordered(entries)


def cmd_rotate(ctx, entries):
    failures = 0
    for e in entries:
        method = e["rotation"]["method"]
        log(f"\n── #{e['num']} {e['id']} ({e['label']})")
        if method == "planned":
            log(f"  pas encore automatisé (phase {e['rotation']['phase']}), voir l'étude")
            continue
        if method in inv_mod.NO_ROTATION:
            log(f"  rien à faire : {e['rotation']['note']}")
            continue
        if method == "manual":
            log(f"  manuel : {e['rotation']['procedure']}")
            log(f"  une fois fait : rotate-secrets.py --record {e['id']}")
            continue
        try:
            detail = METHODS[method](ctx, e)
        except RotationError as exc:
            warn(f"{e['id']} : ÉCHEC — {exc}")
            ctx.journal.append(e["id"], "failed", redact(str(exc))[:200])
            failures += 1
            continue
        if isinstance(detail, Skipped):
            log(f"  {detail}")
        elif ctx.dry_run:
            log("  (dry-run : rien n'a été modifié)")
        else:
            ctx.journal.append(e["id"], "rotated", detail)
            log(f"  ✓ {detail}")
    return 1 if failures else 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ids", nargs="*")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--list", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--level", choices=inv_mod.LEVELS)
    g.add_argument("--record", metavar="ID")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no", action="store_true")
    p.add_argument("--if-missing", action="store_true")
    p.add_argument("--inventory", default=inv_mod.DEFAULT_PATH)
    args = p.parse_args(argv)

    try:
        inv = inv_mod.load(args.inventory)
        journal = Journal()
        if args.list:
            cmd_list(inv)
            return 0
        if args.check:
            return cmd_check(inv, journal)
        if args.record:
            entry = inv_mod.by_id(inv, args.record)
            if entry["rotation"]["method"] in inv_mod.NO_ROTATION:
                raise RotationError(f"{args.record} est régénéré à chaque build : "
                                    "aucune rotation à tracer")
            journal.append(args.record, "recorded", "rotation manuelle déclarée")
            log(f"rotation de {args.record} tracée")
            return 0
        if not args.ids and not args.level and not args.preflight:
            p.error("indiquer un ou plusieurs identifiants, --level, --check, --list ou --preflight")
        if args.if_missing:
            others = [e["id"] for e in select(inv, args.ids, None)
                      if e["rotation"]["method"] != "k8s-sa-token"] if args.ids else []
            if others or not args.ids or args.level:
                raise RotationError("--if-missing ne s'applique qu'à des identifiants de méthode "
                                    f"k8s-sa-token{' (pas : ' + ', '.join(others) + ')' if others else ''}")
        prompter = Prompter(assume_no=args.no)
        ctx = Context(inv, prompter, journal, dry_run=args.dry_run, if_missing=args.if_missing)
        try:
            if args.preflight:
                return cmd_preflight(ctx)
            return cmd_rotate(ctx, select(inv, args.ids, args.level))
        finally:
            ctx.close()
            prompter.forget()
    except RotationError as exc:
        warn(str(exc))
        return 2
    except KeyboardInterrupt:
        warn("interrompu")
        return 130


if __name__ == "__main__":
    sys.exit(main())
