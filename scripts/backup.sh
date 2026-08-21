#!/bin/sh
# Sauvegarde quotidienne de la base PostgreSQL — tourne dans le service
# db_backup (docker-compose.prod.yml). Conserve BACKUP_RETENTION_DAYS jours
# de sauvegardes dans le volume /backups.
set -e

RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
export PGPASSWORD="$DB_PASSWORD"

while true; do
    timestamp=$(date +%Y%m%d_%H%M%S)
    filename="/backups/intelya_${timestamp}.sql.gz"

    echo "[BACKUP] $(date) — sauvegarde vers ${filename}"
    if pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" | gzip > "$filename"; then
        echo "[BACKUP] OK ($(du -h "$filename" | cut -f1))"
    else
        echo "[BACKUP] ECHEC de la sauvegarde"
        rm -f "$filename"
    fi

    # Nettoyage des sauvegardes plus vieilles que RETENTION_DAYS
    find /backups -name "intelya_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete

    # Une sauvegarde par jour
    sleep 86400
done
