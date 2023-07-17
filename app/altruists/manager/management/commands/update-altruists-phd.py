from django.core.management.base import BaseCommand, CommandError
from manager.models import Chain, Altruist, AltruistServingLog
from django.db.models import Count, Sum, Value, Case, When
from django.utils import timezone
from django.conf import settings

import logging
import os
import requests
from http import HTTPStatus
import sys
import json
import datetime
from urllib.parse import urlparse

# Victoria Metrics/Prom address
VM_ADDRESS = os.environ.get('VM_ADDRESS')
# PHD api address
PHD_BASE_URL = os.environ.get('PHD_BASE_URL')
# PHD auth key
PHD_API_KEY = os.environ.get('PHD_API_KEY')

#Timeout     (Connect, Read)
REQ_TIMEOUT = (5,15)

if os.environ.get('DJANGO_DEBUG', 'True').upper() == "TRUE":
    logging.getLogger().setLevel(logging.DEBUG)

logging.debug('DEBUG level active')
##################################
def update_servinglog(altruist: Altruist):

    # Close previous log for the chain
    previous_log = AltruistServingLog.objects.filter(chain_id=altruist.chain_id.chain_id).order_by('-start_time')  #.latest("start_time")
    if len(previous_log) == 0:
        new_log = AltruistServingLog(altruist=altruist)
        new_log.save()
    else:
        previous_log[0].save()
        new_log = AltruistServingLog(altruist=altruist)
        new_log.save()

def update_altruist_phd(
    chain_id: str,
    altruist: str
):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"{PHD_API_KEY}"
    }

    altruist_parsed = urlparse(altruist)
    if altruist_parsed.port == None:
        if altruist_parsed.scheme == "https":
            port = 443
        elif altruist_parsed.scheme == "http":
            port = 80
        else:
            logging.error(f"Wrong altruist's scheme: {altruist}")
            port = altruist_parsed.port # it'll be None so will fail on the request
    else:
        port = altruist_parsed.port

    noauth_url = f"{altruist_parsed.scheme}://{altruist_parsed.hostname}:{port}{altruist_parsed.path}"
    if altruist_parsed.username == None:
        auth_type = "none"
        auth = ""
    else:
        auth_type = "basic_auth"
        auth = f"{altruist_parsed.username}:{altruist_parsed.password}"

    logging.debug(f"Altruist: {altruist}")
    logging.debug(f"Altruist parsed noauth_url: {noauth_url} auth: {auth} auth_type: {auth_type}")

    chain_conf = {
        "altruists": {
            noauth_url: {
                "url": noauth_url,
                "auth": auth,
                "authType": auth_type
            }
        }
    }
    logging.debug(f"New chain's conf: \n{json.dumps(chain_conf, indent=4)}" )

    resp = requests.put(f"{PHD_BASE_URL}/v2/chain/{chain_id}",
                            headers = headers,
                            json = chain_conf,
                            timeout=REQ_TIMEOUT)
    logging.debug(f"PUT request response text: \n{json.dumps(json.loads(resp.text), indent=4)}" )

    if resp.status_code == HTTPStatus.OK :
        logging.info(f"Updated altruist {chain_id}: {noauth_url}")
        return True

    logging.error(f"""Couldn't update altruist {chain_id}: {noauth_url}
                            Response code: {resp.status_code}, content: {resp.content}""")
    return False

def get_healthy_altruists(
    chainid: str,
    interval: str = '30m'
):
    query = ('sort('
        f'sum_over_time(last_block_duration_ns{{job="{chainid}"}}[{interval}])'
        f'+sum_over_time(node_syncing_duration_ns{{job="{chainid}"}}[{interval}])'
        f' and node_syncing{{job="{chainid}"}}[{interval}]==0' # Node is synced
        f' and probe_success{{job="{chainid}"}}[{interval}]==1' # Probe successful
        ')')

    query_url = VM_ADDRESS + '/api/v1/query?query=' + requests.utils.quote(query)
    try:
        resp = requests.get(query_url, timeout=REQ_TIMEOUT)

        if resp.status_code == HTTPStatus.OK :
            altruists = []
            for alt in resp.json()["data"]["result"]:
                altruists.append(alt['metric']['instance'])
            # print(altruists)
            return altruists
        else:
            raise Exception(f"Reply status_code: {resp.status_code} != 200")
    except Exception as e:
        logging.error(f"Failed to request: {e}")
        raise e

class Command(BaseCommand):
    help = 'Get healthy altruists from VM/Prom and update them on PHD'

    def handle(self, *args, **options):

        now_minus_1h = timezone.now() - datetime.timedelta(hours=1)
        ERROR_COUNTER = 0
        for chain in Chain.objects.all():    #filter(chain_id = "0070"):  #
            healthy_altruists = get_healthy_altruists(chainid = chain.chain_id)

            # select available altruists ordered by num of logs wthin last hour
            # If 'chains.cc.nodepilot.tech' in the DNS name then will be prioritised
            altruists = Altruist.objects.filter(chain_id=chain, enabled=True)\
                                        .select_related()\
                                        .annotate(last_hour_sessions_number=Sum(Case(\
                                            When(altruistservinglog__start_time__gte=now_minus_1h, then=Value(1)),\
                                            When(altruistservinglog__start_time__lt=now_minus_1h, then=Value(0)) ), default=Value(0)))\
                                        .annotate(is_community_chains=Case(\
                                            When(url__contains=settings.GLOBAL_SETTINGS["CC_DOMAIN"], then=Value(1)),\
                                            default=Value(0)))\
                                        .order_by('-is_community_chains', 'last_hour_sessions_number')

            for a in altruists:
                if a.url in healthy_altruists:
                    # Update altruist in PHD and add log
                    if update_altruist_phd(chain.chain_id, a.url) :
                        update_servinglog(a)
                        logging.info(f"Changed altruist for {a.chain_id}, served {a.last_hour_sessions_number} times within last hour.")
                        break
                    else:
                        logging.error(f"Couldn't update altruist {a.chain_id}")
                        ERROR_COUNTER+=1


        if ERROR_COUNTER > 0 :
            sys.exit(1)
