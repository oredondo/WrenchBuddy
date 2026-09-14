"""
Migra todos los archivos de media/ local a S3/MinIO.

Uso:
    USE_S3=true DB_PASSWORD=wrenchbuddy_dev_2024 .venv/bin/python migrate_media_to_s3.py
    USE_S3=true DB_PASSWORD=wrenchbuddy_dev_2024 .venv/bin/python migrate_media_to_s3.py --dry-run
"""
import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wrench_buddy.settings')

import django
django.setup()

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import File

from maintenance.models import EventAttachment
from vehicles.models import VehicleDocument


def migrate_field(instance, field_name, dry_run, stats):
    field = getattr(instance, field_name)
    if not field.name:
        return

    local_path = settings.BASE_DIR / 'media' / field.name
    if not local_path.exists():
        print(f"  [MISSING]  {field.name}")
        stats['missing'] += 1
        return

    if default_storage.exists(field.name):
        print(f"  [EXISTS]   {field.name}")
        stats['skipped'] += 1
        return

    print(f"  [UPLOAD]   {field.name}")
    if not dry_run:
        with open(local_path, 'rb') as f:
            default_storage.save(field.name, File(f))
    stats['uploaded'] += 1


def main(dry_run):
    if not settings.USE_S3:
        print("ERROR: USE_S3 no está activado. Ejecuta con USE_S3=true")
        sys.exit(1)

    if dry_run:
        print("=== DRY RUN — no se sube nada ===\n")

    print(f"Endpoint : {settings.AWS_S3_ENDPOINT_URL}")
    print(f"Bucket   : {settings.AWS_STORAGE_BUCKET_NAME}\n")

    stats = {'uploaded': 0, 'skipped': 0, 'missing': 0}

    print("── EventAttachment ──")
    for att in EventAttachment.objects.exclude(file=''):
        migrate_field(att, 'file', dry_run, stats)

    print("\n── VehicleDocument ──")
    for doc in VehicleDocument.objects.exclude(file=''):
        migrate_field(doc, 'file', dry_run, stats)

    print(f"\n{'DRY RUN — ' if dry_run else ''}Resultado: "
          f"{stats['uploaded']} subidos, "
          f"{stats['skipped']} ya existían, "
          f"{stats['missing']} no encontrados en local")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    main(dry_run=args.dry_run)
