"""Vérification d'un mot de passe SMTP par connexion authentifiée, sans envoi de mail."""
import smtplib
import time

from .common import RotationError


def smtp_login(host, port, user, password, attempts=7, delay=10):
    """Réessaie quelques fois : un mot de passe d'application tout juste créé peut mettre
    quelques secondes à être accepté."""
    last = None
    for i in range(attempts):
        try:
            with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
                smtp.login(user, password)
            return
        except smtplib.SMTPAuthenticationError as exc:
            last = f"authentification refusée ({exc.smtp_code})"
        except (OSError, smtplib.SMTPException) as exc:
            last = type(exc).__name__
        if i + 1 < attempts:
            time.sleep(delay)
    raise RotationError(f"SMTP {host}:{port} avec l'identifiant {user} : {last} "
                        f"après {attempts} essais sur {(attempts - 1) * delay} s")
