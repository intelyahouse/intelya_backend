"""
Audit Log — trace toutes les actions sensibles
"""
import logging
from django.utils import timezone

audit_logger = logging.getLogger('intelya.audit')


def log_action(user, action, target=None, details=None, request=None):
    """
    Enregistre une action sensible dans les logs d'audit.
    
    Actions importantes à tracer :
    - Validation/rejet de compte
    - Blocage/déblocage utilisateur
    - Bannissement
    - Décision de litige
    - Libération d'escrow
    - Accès admin aux données sensibles
    """
    ip = None
    if request:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            ip = x_forwarded.split(',')[0]

    log_data = {
        'timestamp': timezone.now().isoformat(),
        'user_id': str(user.id) if user else 'system',
        'user_email': user.email if user else 'system',
        'user_role': user.role if user else 'system',
        'action': action,
        'target': str(target) if target else None,
        'details': details or {},
        'ip': ip,
    }

    audit_logger.info(f"AUDIT | {log_data}")
    return log_data


# Actions prédéfinies
def log_account_validated(admin, user, request=None):
    log_action(admin, 'ACCOUNT_VALIDATED', user.email, {'role': user.role}, request)

def log_account_rejected(admin, user, note, request=None):
    log_action(admin, 'ACCOUNT_REJECTED', user.email, {'note': note}, request)

def log_user_blocked(admin, user, request=None):
    log_action(admin, 'USER_BLOCKED', user.email, {}, request)

def log_user_banned(admin, user, reason, request=None):
    log_action(admin, 'USER_BANNED', user.email, {'reason': reason}, request)

def log_dispute_decided(admin, dispute, decision, request=None):
    log_action(admin, 'DISPUTE_DECIDED', str(dispute.id), {'decision': decision}, request)

def log_escrow_released(user, escrow, reason, request=None):
    log_action(user, 'ESCROW_RELEASED', str(escrow.id), {'amount': float(escrow.amount), 'reason': reason}, request)

def log_payment_initiated(user, reference, amount, method, request=None):
    log_action(user, 'PAYMENT_INITIATED', reference, {'amount': float(amount), 'method': method}, request)
