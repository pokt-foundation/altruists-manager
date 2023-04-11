from django.core.management.base import BaseCommand, CommandError
from manager.models import Chain, Altruist

import logging
import os
# import requests
from http import HTTPStatus
from jinja2 import FileSystemLoader, Environment, BaseLoader
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import hashlib

#K8s ns where to deploy the ConfigMap
NAMESPACE = os.environ.get('NAMESPACE')
#SCRAPE_CONFIGMAP
SCRAPE_CONFIGMAP = os.environ.get('SCRAPE_CONFIGMAP')
SCRAPE_INTERVAL = os.environ.get('SCRAPE_INTERVAL', '5m')
SCRAPE_TIMEOUT = os.environ.get('SCRAPE_TIMEOUT', '30s')
# Black Box Exporter address
BB_EXPORTER_ADDRESS = os.environ.get('BB_EXPORTER_ADDRESS', 'blackbox-blockchain-exporter:9000')

JOB_TMPL = """
#### {{chain_id}}
- job_name: "{{chain_id}}"
  metrics_path: /probe
  params:
    chainid: ["{{chain_id}}"]
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: instance
    - target_label: __address__
      replacement: {{bb_exporter_address}}
  static_configs:
    - targets:
{%- for url in urls %}
      - {{ url }}
{%- endfor -%}
"""

SCRAPE_TMPL = """
global:
  scrape_interval: {{scrape_interval}}
  scrape_timeout: {{scrape_timeout}}
scrape_configs:
{{ jobs }}
"""
logging.basicConfig(
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

def update_configmap(cm_data: str, k8s_client):
    cm_data_md5 = hashlib.md5(cm_data.encode()).hexdigest()

    cm_body = {
        "kind": "ConfigMap",
        "apiVersion": "v1",
        "metadata": {
            "name": SCRAPE_CONFIGMAP,
            "annotations": {
                "config_md5": cm_data_md5
            }
        },
        "data": {
            "scrape.yml": cm_data,
        },
    }

    try:
        resp = k8s_client.read_namespaced_config_map(name=SCRAPE_CONFIGMAP, namespace=NAMESPACE)

        if resp.metadata.annotations != None:
            if "config_md5" in resp.metadata.annotations:
                if resp.metadata.annotations["config_md5"] == cm_data_md5:
                    logging.warning(f"No changes in VM scrape config.")
                    return False

        resp = k8s_client.patch_namespaced_config_map(name=SCRAPE_CONFIGMAP, namespace=NAMESPACE, body=cm_body)
        logging.warning(f"VM scrape config updated.")
    except ApiException as e:
        if e.status == 404:
            logging.warning(f"CM not exist, creating.")
            resp = k8s_client.create_namespaced_config_map(namespace=NAMESPACE, body=cm_body)
        else:
            raise Exception(f"Exception when calling CoreV1Api->read_namespaced_config_map: {e}")

    return True

class Command(BaseCommand):
    help = 'Generate and update VM scrape config from altruists DB'

    def handle(self, *args, **options):

        altruists = Altruist.objects.filter(enabled = True)
        altruist_by_chain = dict()
        for a in altruists:
            chain_id = a.chain_id.chain_id
            if chain_id in altruist_by_chain:
                altruist_by_chain[chain_id].append(a.url)
            else:
                altruist_by_chain[chain_id] = [a.url]

        env = Environment(loader=BaseLoader)
        jobs = ""
        for chain_id in sorted(altruist_by_chain.keys()):
            jobs += env.from_string(JOB_TMPL).render(chain_id=chain_id, urls=sorted(altruist_by_chain[chain_id]), bb_exporter_address=BB_EXPORTER_ADDRESS)

        cm_data = env.from_string(SCRAPE_TMPL).render(jobs=jobs, cm_name=SCRAPE_CONFIGMAP, scrape_timeout=SCRAPE_TIMEOUT, scrape_interval=SCRAPE_INTERVAL)

        # Deploy the config map
        config.load_incluster_config()
        v1 = client.CoreV1Api()

        update_configmap(cm_data, v1)

        self.stdout.write(self.style.SUCCESS(f"Scrape ConfigMap {SCRAPE_CONFIGMAP} updated."))

