import json
import time
import logging
from flask import Flask, request, abort
from prometheus_client import Info, Gauge, Counter, generate_latest, CollectorRegistry
import requests
from datetime import datetime

# PHD api address
# LOGGING = os.environ.get('LOGGING', 'INFO')
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

#Timeout     (Connect, Read)
REQ_TIMEOUT = (5,15)

NOT_DEFINED = -1
ERROR = -2
ERROR_LAST_BLOCK = 2
ERROR_PREV_BLOCK = 3
ERROR_HEALTH     = 5

# Maximum allowed age of the last block per chain
# Required if eth_syncing returns not standard values
METER_LAST_BLOCK_MAX_AGE = 15

####################
app = Flask(__name__)

reg = CollectorRegistry()
# Latest block metrics
lastBlockNumber     = Gauge('last_block_number', "Number of the node's latest block", [], registry=reg)
lastBlockAge        = Gauge('last_block_age', "How many seconds old is the node's latest block", [], registry=reg)
lastBlockHash       =  Info('last_block_hash', "Latest block hash", [], registry=reg)
lastBlockParentHash =  Info('last_block_parent_hash', "Latest block parent hash", [], registry=reg)
lastBlockDuration   = Gauge('last_block_duration_ns', 'How many nanoseconds took to get the latest block', [], registry=reg)
# Latest-1 block metrics
prevBlockNumber     = Gauge('prev_block_number', "Number of the node's latest block", [], registry=reg)
prevBlockAge        = Gauge('prev_block_age', "How many seconds old is the node's latest block", [], registry=reg)
prevBlockHash       =  Info('prev_block_hash', "Latest block hash", [], registry=reg)
prevBlockParentHash =  Info('prev_block_parent_hash', "Latest block parent hash", [], registry=reg)
prevBlockDuration   = Gauge('prev_block_duration_ns', 'How many nanoseconds took to get the latest block', [], registry=reg)

nodeSyncing         = Gauge('node_syncing', "Is the node syncing 0/1", [], registry=reg)
nodeSyncingDuration = Gauge('node_syncing_duration_ns', 'How many nanoseconds took to get syncing status', [], registry=reg)

probeSuccess       = Gauge('probe_success', 'Displays whether or not the probe was a successful (1 - success, >1 falure)', [], registry=reg)
totalDuration      = Gauge('total_duration_ns', 'How many nanoseconds took whole job', [], registry=reg)

def atoi(a: str):
    # logging.debug(f"Given: {a}, {a[:2]}")
    if a[:2] == "0x":
        return int(a, 16), "hex"
    else:
        return int(a), "dec"

def rpcRequest(target: str, data: str = None, method: str = "post"):
    headers = {"Content-Type": "application/json"}
    try:
        if method == "post":
            resp = requests.post(target, data=data, headers=headers, timeout=REQ_TIMEOUT)
        elif method == "get":
            resp = requests.get(f"{target}", timeout=REQ_TIMEOUT)

        if resp.status_code == 200 :
            return resp.json()
        logging.error(resp.text)
        raise Exception(f"Reply status_code: {resp.status_code} != 200")
    except Exception as e:
        logging.warning(f"Failed to request: {e}")

@app.route('/probe')
def get_metrics():
    t00 = time.perf_counter_ns()
    try:
        target  = request.args.get('target')
        chainid = request.args.get('chainid')

        # INit probe status
        probeStatus = 1
        ########## POKT
        if chainid in ["0001"]:
            t0 = time.perf_counter_ns()
            block = rpcRequest(f"{target}/v1/query/height",
                                '{"height": 0}'
                                )
            lastBlockDuration.set(time.perf_counter_ns() - t0)
            # Cannot determine timestamp
            lastBlockAge.set(NOT_DEFINED)

            lastBlockNumber.set(int(block["height"]))
            #########                                                        
            # t0 = time.perf_counter_ns()
            # syncing = rpcRequest(target,
            #                     '{"jsonrpc":"2.0","id":1, "method":"getHealth"}'
            #                     )
            # # response has result key only if node is synced otherwise 
            # # it ll have error key instead
            # # https://docs.ethereum-goerli.com/api/http#gethealth
            # try:
            #     if syncing["result"] == "ok":
            #         nodeSyncing.set(0)
            #     else:
            #         nodeSyncing.set(1)
            # except Exception as e:
            #     logging.warning(f"Failed to request: {e}")
            #     nodeSyncing.set(1)
            # nodeSyncing.set(0)
            # nodeSyncingDuration.set(time.perf_counter_ns() - t0)
            # # Don't know how to get th einfo
            # nodeNetVersion.set(NOT_DEFINED)
            # nodeNetVersionDuration.set(NOT_DEFINED)

        ########## ethereum-goerli VELAS
        elif chainid in ["0006","0067","0068"]:
            getSlotData   = '{"jsonrpc":"2.0","id":1, "method":"getSlot"}'
            getBlockData   = '''{{
                                "jsonrpc": "2.0","id":1,
                                "method":"getBlock",
                                "params": [
                                    {slot},
                                    {{
                                    "encoding": "json",
                                    "maxSupportedTransactionVersion":0,
                                    "transactionDetails":"none",
                                    "rewards":false
                                    }}
                                ]
                                }}'''
            getSyncingData = '{"jsonrpc":"2.0","id":1, "method":"getHealth"}'
            fTimestamp   = "blockTime"
            fBlockNumber = "blockHeight"
            fBlockHash   = "blockhash"
            fParentHash  = "previousBlockhash"

            try:
                t0 = time.perf_counter_ns()
                slot = rpcRequest(target, getSlotData)["result"]
                block = rpcRequest(target, getBlockData.format(slot=slot))["result"]
                lastBlockDuration.set(time.perf_counter_ns() - t0)
                b_timestamp = block[fTimestamp]

                lastBlockAge.set(int(time.time()) - b_timestamp)
                blockNum = block[fBlockNumber]
                lastBlockNumber.set(blockNum)
                lastBlockHash.info({"hash": str(block[fBlockHash])})
                lastBlockParentHash.info({"hash": str(block[fParentHash])})
            except Exception as e:
                logging.warning(f"Failed to get latest block: {e}")
                probeStatus *= ERROR_LAST_BLOCK

            try:
                t0 = time.perf_counter_ns()
                block = rpcRequest(target, getBlockData.format(slot=block["parentSlot"]))["result"]
                prevBlockDuration.set(time.perf_counter_ns() - t0)
                b_timestamp = block[fTimestamp]
                prevBlockAge.set(int(time.time()) - b_timestamp)

                blockNum = block[fBlockNumber]
                prevBlockNumber.set(blockNum)
                prevBlockHash.info({"hash": str(block[fBlockHash])})
                prevBlockParentHash.info({"hash": str(block[fParentHash])})
            except Exception as e:
                logging.warning(f"Failed to get previouse block: {e}")
                probeStatus *= ERROR_PREV_BLOCK

            # response has result key only if node is synced otherwise 
            # it ll have error key instead
            # https://docs.ethereum-goerli.com/api/http#gethealth
            try:
                sync = 1
                t0 = time.perf_counter_ns()
                syncing = rpcRequest(target, getSyncingData)
                if "result" in syncing.keys():
                    if syncing["result"] == "ok":
                        sync = 0

                nodeSyncing.set(sync)
                nodeSyncingDuration.set(time.perf_counter_ns() - t0)

            except Exception as e:
                logging.warning(f"Failed to get syncing status: {e}")
                probeStatus *= ERROR_HEALTH

        # OSMOSIS
        elif chainid in ["0054"]:

            t0 = time.perf_counter_ns()
            block = rpcRequest(target=f"{target}/block", method='get')["result"]["block"]
            lastBlockDuration.set(time.perf_counter_ns() - t0)

            last_block_age = int(time.time()) - int(datetime.fromisoformat(block["header"]["time"]).timestamp())
            lastBlockAge.set(last_block_age)

            lastBlockNumber.set(int(block["header"]["height"]))

            t0 = time.perf_counter_ns()
            syncing = rpcRequest(f"{target}/status", method='get')["result"]["sync_info"]

            sync = 1
            if syncing["catching_up"] == False:
                sync = 0
            nodeSyncing.set(sync)
            nodeSyncingDuration.set(time.perf_counter_ns() - t0)

        # NEAR
        elif chainid in ["0052"]:
            t0 = time.perf_counter_ns()
            block = rpcRequest(target,
                                '{"jsonrpc": "2.0", "id": "dontcare", "method": "block", "params": {"finality": "final"}}'
                                )["result"]
            lastBlockDuration.set(time.perf_counter_ns() - t0)
            # print(block)
            last_block_age = int(time.time()) - int(block["header"]["timestamp"]/1000000000)
            lastBlockAge.set(last_block_age)

            lastBlockNumber.set(int(block["header"]["height"]))

            t0 = time.perf_counter_ns()
            syncing = rpcRequest(target,
                                '{"jsonrpc": "2.0", "id": "dontcare", "method": "status", "params": []}'
                                )["result"]["sync_info"]["syncing"]
            if syncing == False:
                sync = 0
            else:
                sync = 1
            nodeSyncing.set(sync)
            nodeSyncingDuration.set(time.perf_counter_ns() - t0)

        else:
            # Default do EVM requests

            getBlockData   = '{{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":[{height}, false],"id":1}}'
            getSyncingData = '{"jsonrpc":"2.0","method":"eth_syncing","params":[],"id":1}'
            fTimestamp   = "timestamp"
            fBlockNumber = "number"
            fBlockHash   = "hash"
            fParentHash  = "parentHash"

            # on AVAX + subnets we need to adjust URL path
            if chainid in ["0003"]:
                target = f"{target}/ext/bc/C/rpc"
            elif chainid in ["03DF"]:
                target = f"{target}/ext/bc/q2aTwKuyzgs8pynF7UXBZCU7DejbZbZ6EUyHr3JQzYgwNPUPi/rpc"
            elif chainid in ["03CB"]:
                target = f"{target}/ext/bc/2K33xS9AyP9oCDiHYKVrHe7F54h2La5D8erpTChaAhdzeSu2RX/rpc"
            elif chainid in ["0060", "0061"]:
                getBlockData   = '{{"jsonrpc":"2.0","method":"starknet_getBlockWithTxHashes","params":[{height}],"id":1}}'
                getSyncingData = '{"jsonrpc":"2.0","method":"starknet_syncing","params":[],"id":1}'
                fTimestamp   = "timestamp"
                fBlockNumber = "block_number"
                fBlockHash   = "block_hash"
                fParentHash  = "parent_hash"

            try:
                logging.debug(getBlockData.format(height='"latest"'))
                t0 = time.perf_counter_ns()
                block = rpcRequest(target, getBlockData.format(height='"latest"'))["result"]
                lastBlockDuration.set(time.perf_counter_ns() - t0)
                b_timestamp, base = atoi(str(block[fTimestamp]))

                lastBlockAge.set(int(time.time()) - b_timestamp)
                blockNum, base = atoi(str(block[fBlockNumber]))
                lastBlockNumber.set(blockNum)
                lastBlockHash.info({"hash": str(block[fBlockHash])})
                lastBlockParentHash.info({"hash": str(block[fParentHash])})
            except Exception as e:
                logging.warning(f"Failed to get latest block: {e}")
                probeStatus *= ERROR_LAST_BLOCK

            if not (chainid in ["0060", "0061"]):
            # Don't know how to get the previous block
            # TODO!!! TBD
                try:
                    height = blockNum-1
                    if base == "hex":
                        height = str(hex(blockNum-1))
                    logging.debug(getBlockData.format(height=f'"{height}"'))
                    t0 = time.perf_counter_ns()

                    block = rpcRequest(target, getBlockData.format(height=f'"{height}"'))["result"]

                    prevBlockDuration.set(time.perf_counter_ns() - t0)
                    b_timestamp, base = atoi(str(block[fTimestamp]))
                    prevBlockAge.set(int(time.time()) - b_timestamp)

                    blockNum, base = atoi(str(block[fBlockNumber]))
                    prevBlockNumber.set(blockNum)
                    prevBlockHash.info({"hash": str(block[fBlockHash])})
                    prevBlockParentHash.info({"hash": str(block[fParentHash])})
                except Exception as e:
                    logging.warning(f"Failed to get previouse block: {e}")
                    probeStatus *= ERROR_PREV_BLOCK

            try:
                if chainid in ["0074"]:
                    t0 = time.perf_counter_ns()
                    syncing = rpcRequest(target, getSyncingData)["result"]
                    sync = 1
                    if syncing['currentBlock'] == syncing['highestBlock'] or syncing['highestBlock'] == "0x0":                       
                        sync = 0

                else:
                    t0 = time.perf_counter_ns()
                    syncing = rpcRequest(target, getSyncingData)["result"]
                    sync = 1
                    if syncing == False:
                        sync = 0
                    elif 'current_block_num' in syncing.keys() and 'highest_block_num' in syncing.keys():
                        if syncing['current_block_num'] == syncing['highest_block_num']:
                            sync = 0
                    elif 'currentBlock' in syncing.keys() and 'highestBlock' in syncing.keys():
                        if syncing['currentBlock'] == syncing['highestBlock']:
                        #  last_block_age < METER_LAST_BLOCK_MAX_AGE:
                            sync = 0

                nodeSyncing.set(sync)
                nodeSyncingDuration.set(time.perf_counter_ns() - t0)

            except Exception as e:
                logging.warning(f"Failed to get syncing status: {e}")
                probeStatus *= ERROR_HEALTH

    except Exception as e:
        probeStatus *= 7
        logging.error(f"Caught exception: {e}")

    if probeStatus % ERROR_LAST_BLOCK == 0:
        # Invalidate all the metrics
        lastBlockDuration.set(ERROR)
        lastBlockAge.set(ERROR)
        lastBlockNumber.set(ERROR)
        lastBlockHash.info({"hash": "none"})
        lastBlockParentHash.info({"hash": "none"})

    if probeStatus % ERROR_PREV_BLOCK == 0:
        prevBlockDuration.set(ERROR)
        prevBlockAge.set(ERROR)
        prevBlockNumber.set(ERROR)
        prevBlockHash.info({"hash": "none"})
        prevBlockParentHash.info({"hash": "none"})

    if probeStatus % ERROR_HEALTH == 0:
        nodeSyncing.set(ERROR)
        nodeSyncingDuration.set(ERROR)

    probeSuccess.set(probeStatus)
    totalDuration.set(time.perf_counter_ns() - t00)

    return generate_latest(registry=reg)

@app.route('/health')
def health():
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=9000, debug=True)
    # app.run()
