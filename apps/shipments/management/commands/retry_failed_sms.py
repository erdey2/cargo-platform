"""
Management command to batch retry failed SMS OTP deliveries.

Usage:
    python manage.py retry_failed_sms --limit 50
    python manage.py retry_failed_sms --dry-run
"""
from django.core.management.base import BaseCommand
from apps.shipments.services.batch_retry_service import batch_retry_failed_sms
import json


class Command(BaseCommand):
    help = 'Batch retry failed OTP SMS messages with configurable limits'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of failed SMS to retry (default: 100)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be retried without making changes'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Print detailed information about each retry'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        dry_run = options['dry_run']
        verbose = options['verbose']

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting batch retry of failed SMS (limit={limit}, dry_run={dry_run})"
            )
        )

        results = batch_retry_failed_sms(limit=limit, dry_run=dry_run)

        # Print summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'=' * 70}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Batch Retry Summary:\n"
                f"  Total Processed: {results['total_processed']}\n"
                f"  Successful Retries: {results['successful_retries']}\n"
                f"  Failed Retries: {results['failed_retries']}\n"
                f"  Marked Ineligible: {results['marked_ineligible']}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'=' * 70}\n"
            )
        )

        # Print details if verbose
        if verbose and results['details']:
            self.stdout.write("\nDetailed Results:")
            self.stdout.write("-" * 70)
            for detail in results['details']:
                status_style = self.style.SUCCESS if detail.get('success', True) else self.style.ERROR
                self.stdout.write(
                    status_style(
                        f"Receipt #{detail['receipt_id']} | OTP #{detail['otp_id']} | "
                        f"Phone: {detail['phone']} | Retry #{detail['retry_count']}"
                    )
                )
                if detail.get('error'):
                    self.stdout.write(
                        self.style.ERROR(f"  Error: {detail['error']}")
                    )

