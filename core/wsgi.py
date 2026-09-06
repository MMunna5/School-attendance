"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os
import threading

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()


def start_sms_worker():
	print('SMS queue worker starting from WSGI.', flush=True)
	try:
		from attendance.management.commands.process_sms_queue import Command

		Command().handle()
	except Exception as exc:
		print(f'SMS queue worker stopped: {exc}', flush=True)
		raise


if (
	os.environ.get('DEBUG', 'False').lower() not in ('true', '1', 'yes')
	and os.environ.get('SMS_QUEUE_WORKER_MANAGED') != '1'
):
	threading.Thread(target=start_sms_worker, name='sms-queue-worker', daemon=True).start()
